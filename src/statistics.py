"""Descriptive, time-block bootstrap summaries for the synthetic ledger."""
import numpy as np
import pandas as pd


def describe(features, truth, seed):
    merged = features.merge(truth, on="claim_id")
    monthly = (merged.assign(month=merged.checkpoint.dt.to_period("M"))
               .groupby("month").actionable.agg(["sum", "size"]).to_numpy())
    rng = np.random.default_rng(seed)
    resampled = monthly[rng.integers(len(monthly), size=(1000, len(monthly)))].sum(axis=1)
    return {
        "feature_missingness": features.isna().sum().to_dict(),
        "duplicate_claim_ids": int(features.claim_id.duplicated().sum()),
        "paid_quantiles": (truth.paid_cents / 100).quantile([.1, .5, .9, .99]).to_dict(),
        "avoidable_quantiles_positive": (truth.loc[truth.actionable, "avoidable_cents"] / 100)
        .quantile([.1, .5, .9, .99]).to_dict(),
        "eligible_prevalence": merged.actionable.mean(),
        "monthly_bootstrap_prevalence_ci": np.quantile(resampled[:, 0] / resampled[:, 1], [.025, .975]).tolist(),
        "severity_cycle_spearman": merged.severity.corr(merged.duration, method="spearman"),
        "documentation_cycle_gap": merged.groupby("documented").duration.mean().to_dict(),
    }
