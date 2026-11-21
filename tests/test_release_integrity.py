import hashlib
import json
import shutil

import pandas as pd
import pytest

from scripts.verify_snapshot import verify
from src.decision import Scenario
from src.generate import ROOT
from src.simulation import population

SNAPSHOT = ROOT / "deployment/snapshot"


@pytest.mark.parametrize("damage", ["missing scenario", "duplicate strategy", "missing checksum", "delay charge"])
def test_snapshot_rejects_coherent_hashes_for_incomplete_or_invalid_replay(tmp_path, damage):
    snapshot = tmp_path / "snapshot"
    shutil.copytree(SNAPSHOT, snapshot)
    path = snapshot / "scenarios.csv"
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if damage == "missing checksum":
        del manifest["files"]["analytics/vendors.csv"]
    else:
        data = pd.read_csv(path)
        if damage == "missing scenario":
            data = data[data.scenario.ne("High claim volume")]
        elif damage == "duplicate strategy":
            data = pd.concat([data, data.iloc[[0]]])
        else:
            index = data.index[data.strategy.eq("Random review")][0]
            data.loc[index, "operational_harm"] += 5
            data.loc[index, "net"] -= 5  # Net still reconciles to the fabricated fee.
        data.to_csv(path, index=False)
        manifest["files"]["scenarios.csv"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, AssertionError)):
        verify(snapshot)


def test_replay_rejects_missing_outcomes_but_accepts_coverage_subset():
    scores = pd.read_parquet(SNAPSHOT/"scores.parquet").head(10)
    labels = pd.read_parquet(SNAPSHOT/"evaluation_only.parquet")
    assert len(population(scores,labels,Scenario(),27)) == 10
    truncated = labels[labels.claim_id.ne(scores.claim_id.iloc[0])]
    with pytest.raises(ValueError, match="complete outcome"):
        population(scores,truncated,Scenario(),27)
