"""Validate a full or reduced pipeline artifact independently of training."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.decision import STRATEGIES
from src.generate import ROOT

REPLAY_SEEDS = (11, 27, 53)


def verify(snapshot):
    manifest = json.loads((snapshot/"manifest.json").read_text())
    profile = json.loads((snapshot/"data_report.json").read_text())
    files = {"data_report.json", "model.json", "scores.parquet", "evaluation_only.parquet",
             "scenarios.csv"} | {f"analytics/{name}.csv" for name in profile["sql_questions"]}
    if set(manifest["files"]) != files:
        raise ValueError("Incomplete snapshot checksum manifest")
    for item, digest in manifest["files"].items():
        if hashlib.sha256((snapshot/item).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Snapshot checksum failed for {item}")
    scores = pd.read_parquet(snapshot/"scores.parquet")
    evaluation = pd.read_parquet(snapshot/"evaluation_only.parquet")
    simulation = pd.read_csv(snapshot/"scenarios.csv")
    if set(scores) & set(evaluation) != {"claim_id"} or not scores.claim_id.equals(evaluation.claim_id):
        raise ValueError("Replay identifiers or ground-truth isolation failed")
    if (len(scores) != manifest["queue_claims"] or not scores.claim_id.is_unique
            or manifest["claims"] != profile["summary"]["claims"]
            or not scores.checkpoint.between(pd.Timestamp(manifest["replay_start"]),
                                             pd.Timestamp(manifest["replay_end_exclusive"]),
                                             inclusive="left").all()
            or not scores.risk.between(0,1).all()
            or not np.isfinite(scores.conditional_amount).all() or scores.conditional_amount.lt(0).any()
            or any(profile["checks"].values()) or len(profile["sql_questions"]) != 19):
        raise ValueError("Snapshot quality checks failed")
    np.testing.assert_allclose(scores.expected_exposure,scores.risk*scores.conditional_amount)
    scenarios = json.loads((ROOT/"config/scenarios.json").read_text())
    keys = list(simulation[["scenario", "seed", "strategy"]].itertuples(index=False, name=None))
    expected = set(itertools.product(scenarios, REPLAY_SEEDS, STRATEGIES))
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError("Incomplete or duplicated strategy comparison")
    groups = simulation.assign(positives=simulation.actionable_detected + simulation.missed).groupby(["scenario", "seed"])
    if not groups[["claims", "positives"]].nunique(dropna=False).eq(1).all().all():
        raise ValueError("Strategies do not share the same replay population")
    np.testing.assert_allclose(simulation.reviewed,simulation.actionable_detected+simulation.false_positive)
    np.testing.assert_allclose(simulation.gross,simulation.prevented+simulation.recovered)
    np.testing.assert_allclose(simulation.operational_harm,12*simulation.delay_hours)
    np.testing.assert_allclose(simulation.net,simulation.gross-simulation.review_expense-simulation.operational_harm)
    baseline = simulation[simulation.strategy.eq("No additional review")]
    if not baseline[["reviewed","gross","review_expense","operational_harm","net"]].eq(0).all().all():
        raise ValueError("No additional review must have zero incremental activity and net")
    print(f"Verified {manifest['claims']:,} claims, {len(scores):,} replay records and {len(simulation)} strategy runs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot",nargs="?",type=Path,default=Path("deployment/snapshot"))
    verify(parser.parse_args().snapshot)
