"""Build a reproducible DuckDB ledger and versioned app snapshot."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics import run_analytics
from src.decision import Scenario
from src.generate import ROOT, generate
from src.modeling import fit
from src.simulation import simulate
from src.statistics import describe
from src.validate import verify


def json_write(path, data):
    path.write_text(json.dumps(data, indent=2, default=lambda value: value.item(), allow_nan=False) + "\n")


def build(db, output, n, seed):
    output.mkdir(parents=True, exist_ok=True)
    sql_output = output / "analytics"
    sql_output.mkdir(exist_ok=True)
    con, truth = generate(db,n,seed)
    try:
        checks = verify(con, truth)
        features = con.execute((ROOT/"sql/features.sql").read_text()).df()
        questions = {}
        for name, (question, frame) in run_analytics(con,features,truth).items():
            questions[name] = question
            frame.to_csv(sql_output/f"{name}.csv",index=False)
        executive = con.execute("""SELECT count(*) AS claims,
            count(DISTINCT state) AS states, count(DISTINCT vendor_id) AS vendors,
            avg((settled IS NOT NULL)::INTEGER) AS closure_rate,
            avg(date_diff('day',fnol,settled)) AS settlement_days,
            min(fnol)::DATE::VARCHAR AS first_report,max(fnol)::DATE::VARCHAR AS last_report
            FROM claims JOIN policies USING(policy_id)""").df().iloc[0].to_dict()
    finally:
        con.close()
    json_write(output/"data_report.json",dict(summary=executive, checks=checks,
               descriptive=describe(features,truth,seed), sql_questions=questions))

    scores, model = fit(features,truth,seed)
    json_write(output/"model.json",model)
    # Fixed 91-day replay from the untouched test partition. No prevalence-based sampling here.
    compact = scores[scores.checkpoint < pd.Timestamp("2024-04-01")].reset_index(drop=True)
    compact.to_parquet(output/"scores.parquet",index=False)
    outcomes = compact[["claim_id"]].merge(truth[["claim_id","actionable","avoidable_cents","mechanism",
                                                 "effectiveness"]], on="claim_id",validate="one_to_one")
    outcomes.to_parquet(output/"evaluation_only.parquet",index=False)

    scenarios = json.loads((ROOT/"config/scenarios.json").read_text())
    results = [simulate(compact,outcomes,Scenario(**parameters)).assign(scenario=name)
               for name,parameters in scenarios.items()]
    pd.concat(results,ignore_index=True).to_csv(output/"scenarios.csv",index=False)
    manifest = {str(x.relative_to(output)): hashlib.sha256(x.read_bytes()).hexdigest()
                for x in sorted(output.rglob("*")) if x.is_file() and x.name!="manifest.json"}
    json_write(output/"manifest.json",{"version":1,"seed":seed,"claims":n,"queue_claims":len(compact),
                                      "replay_start":"2024-01-01","replay_end_exclusive":"2024-04-01",
                                      "files":manifest})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims",type=int,default=120_000)
    parser.add_argument("--seed",type=int,default=27)
    parser.add_argument("--db",type=Path,default=ROOT/"data/claims.duckdb")
    parser.add_argument("--output",type=Path,default=ROOT/"deployment/snapshot")
    args = parser.parse_args()
    if args.claims < 2000:
        parser.error("--claims must be at least 2000 for temporal model and evaluation slices")
    build(args.db,args.output,args.claims,args.seed)
