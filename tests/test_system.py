import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analytics import run_analytics
from src.decision import Scenario, optimize_day, options, prioritize
from src.generate import ROOT, generate
from src.modeling import CAL_END, FEATURES, TEST_START, TRAIN_END, capacity_threshold, temporal_frames
from src.simulation import population, simulate
from src.validate import verify

SNAPSHOT = ROOT / "deployment/snapshot"


@pytest.fixture(scope="module")
def ledger(tmp_path_factory):
    con, truth = generate(tmp_path_factory.mktemp("ledger") / "claims.duckdb",3000)
    yield con, truth
    con.close()


def get_features(con):
    return con.execute((ROOT / "sql/features.sql").read_text()).df()


def test_integrity_and_sql(ledger):
    con, truth = ledger
    assert not any(verify(con,truth).values())
    assert all(name not in {"labels","truth"} for name, in con.execute("SHOW TABLES").fetchall())
    result = run_analytics(con,get_features(con),truth)
    assert len(result) == 19
    assert all(not frame.empty for _, frame in result.values())
    assert result["reconciliation"][1].iloc[0].difference == 0
    assert result["coverage"][1].claims.sum() == len(truth)
    assert result["duplicates"][1].iloc[0].flagged_claims == truth.mechanism.eq("duplicate payment").sum()


def test_future_mutation_and_exact_cutoff(ledger):
    con, truth = ledger
    before = get_features(con)
    cid = before.iloc[0].claim_id.item()
    con.execute("BEGIN")
    try:
        con.execute("UPDATE events SET detail=999 WHERE happened > (SELECT fnol FROM claims c WHERE c.claim_id=events.claim_id)+INTERVAL 72 HOURS")
        con.execute("UPDATE reserves SET new=999 WHERE changed > (SELECT fnol FROM claims c WHERE c.claim_id=reserves.claim_id)+INTERVAL 72 HOURS")
        con.execute("UPDATE payments SET amount=0")
        after = get_features(con)
        pd.testing.assert_frame_equal(before,after)
        con.execute("""INSERT INTO events SELECT 900000,claim_id,fnol+INTERVAL 72 HOURS,
                    'documentation',1,'test' FROM claims WHERE claim_id=?""",[cid])
        after = get_features(con)
        assert after.iloc[0].documented == before.iloc[0].documented + 1
        assert after.iloc[0].early_events == before.iloc[0].early_events + 1
    finally:
        con.execute("ROLLBACK")
    assert len(before) < len(truth)
    assert not set(FEATURES) & {"state","team","vendor_id","adjuster_id","mature_at",
                              "settled","duration","mechanism","actionable","avoidable_cents"}


def test_temporal_outcomes_mature_at_cutoffs(ledger):
    con, truth = ledger
    parts = temporal_frames(get_features(con),truth)
    for name, cutoff in [("train",TRAIN_END),("calibration",CAL_END),("validation",TEST_START)]:
        assert len(parts[name]) > 0
        assert parts[name].mature_at.max() < cutoff
        assert parts[name].checkpoint.max() < cutoff
    assert parts["test"].checkpoint.min() >= TEST_START
    assert not set(parts["train"].claim_id) & set(parts["test"].claim_id)


@pytest.fixture(scope="module")
def replay():
    return (pd.read_parquet(SNAPSHOT/"scores.parquet"),
            pd.read_parquet(SNAPSHOT/"evaluation_only.parquet"))


def test_snapshot_hash_and_prediction_integrity(replay):
    scores, labels = replay
    manifest = json.loads((SNAPSHOT/"manifest.json").read_text())
    for name,digest in manifest["files"].items():
        assert hashlib.sha256((SNAPSHOT/name).read_bytes()).hexdigest() == digest
    assert manifest["queue_claims"] == len(scores)
    assert scores.claim_id.is_unique and labels.claim_id.is_unique
    assert set(scores.claim_id) == set(labels.claim_id)
    assert set(scores.columns).intersection(labels.columns) == {"claim_id"}
    assert scores.risk.between(0,1).all()
    assert scores.conditional_amount.ge(0).all()
    np.testing.assert_allclose(scores.expected_exposure,scores.risk*scores.conditional_amount)


def test_edge_cases_and_capacity(replay):
    scores, _ = replay
    rows = scores.head(6).copy().assign(risk=.95,conditional_amount=2000,expected_exposure=1900.)
    rows["checkpoint"] = pd.Timestamp("2024-01-01")
    rows.loc[rows.index[0], ["estimate","risk","conditional_amount","expected_exposure"]] = [50000,0,0,0]
    rows.loc[rows.index[1], ["coverage","severity","workload","documented","liability"]] = [
        "Property liability",1,10,1,0]
    rows.loc[rows.index[2], ["severity","documented","report_delay","expected_exposure"]] = [5,0,30,.01]
    scenario = Scenario(capacity=2,budget=45,staff_hours=.8,specialist_hours=0)
    selected = prioritize(rows,scenario)
    assert 0 < len(selected) <= 2
    assert selected.claim_id.is_unique
    assert not set(rows.head(3).claim_id) & set(selected.claim_id)
    assert selected.hours.sum() <= .8 and selected.cost.sum() <= 45
    assert not selected.specialist.any()
    assert selected.net_benefit.gt(0).all()
    assert prioritize(rows,Scenario(cost_scale=100)).empty
    assert prioritize(rows,Scenario(capacity=0)).empty
    assert prioritize(rows,Scenario(effectiveness=0)).empty
    assert options(rows,Scenario(delay_per_hour=1.5)).query("urgent").empty


def test_paired_scenarios_and_net_arithmetic(replay):
    scores, labels = replay
    scores = scores.head(700)
    normal = simulate(scores,labels,Scenario(),seeds=(11,27))
    pd.testing.assert_frame_equal(normal,simulate(scores,labels,Scenario(),seeds=(11,27)))
    assert normal.groupby("seed").claims.nunique().eq(1).all()
    assert (normal.reviewed == normal.actionable_detected+normal.false_positive).all()
    np.testing.assert_allclose(normal.gross,normal.prevented+normal.recovered)
    np.testing.assert_allclose(normal.net,normal.gross-normal.review_expense-normal.operational_harm)
    assert normal.max_claim_delay.le(.75).all()
    assert normal[normal.strategy.eq("No additional review")].net.eq(0).all()
    larger = population(scores,labels,Scenario(volume=1.5,prevalence=2),11)
    base = population(scores,labels,Scenario(),11)
    assert len(larger) == int(len(base)*1.5)
    assert larger.actionable.mean() > base.actionable.mean()
    zero = simulate(scores,labels,Scenario(effectiveness=0,capacity=0),seeds=(11,))
    assert zero.net.eq(0).all() and zero.reviewed.eq(0).all()


def test_optimizer_beats_greedy_when_budget_binds():
    candidates = pd.DataFrame({"claim_id": [1, 2, 3], "hours": [1., .5, .5],
                               "cost": [60., 30., 30.], "specialist": [False]*3,
                               "net_benefit": [50., 35., 35.]})
    assert optimize_day(candidates,Scenario(capacity=2,staff_hours=1.,budget=60.)) == [1,2]


def test_score_ties_keep_validation_flag_rate_within_cap():
    scores = np.r_[np.full(80,.1),np.full(15,.2),np.full(5,.3)]
    assert (scores >= capacity_threshold(scores)).sum() == 5
    assert not (np.ones(100) >= capacity_threshold(np.ones(100))).any()
