"""Validate a full or reduced pipeline artifact independently of training."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def verify(snapshot):
    manifest = json.loads((snapshot/"manifest.json").read_text())
    for item, digest in manifest["files"].items():
        if hashlib.sha256((snapshot/item).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Snapshot checksum failed for {item}")
    profile = json.loads((snapshot/"data_report.json").read_text())
    scores = pd.read_parquet(snapshot/"scores.parquet")
    evaluation = pd.read_parquet(snapshot/"evaluation_only.parquet")
    simulation = pd.read_csv(snapshot/"scenarios.csv")
    if set(scores) & set(evaluation) != {"claim_id"} or not scores.claim_id.equals(evaluation.claim_id):
        raise ValueError("Replay identifiers or ground-truth isolation failed")
    if (len(scores) != manifest["queue_claims"] or not scores.claim_id.is_unique
            or not scores.risk.between(0,1).all() or scores.conditional_amount.lt(0).any()
            or sum(profile["checks"].values()) or len(profile["sql_questions"]) != 19):
        raise ValueError("Snapshot quality checks failed")
    np.testing.assert_allclose(scores.expected_exposure,scores.risk*scores.conditional_amount)
    np.testing.assert_allclose(simulation.net,simulation.gross-simulation.review_expense-simulation.operational_harm)
    if simulation.groupby(["scenario","seed"]).strategy.nunique().ne(6).any():
        raise ValueError("Incomplete strategy comparison")
    print(f"Verified {manifest['claims']:,} claims, {len(scores):,} replay records and {len(simulation)} strategy runs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot",nargs="?",type=Path,default=Path("deployment/snapshot"))
    verify(parser.parse_args().snapshot)
