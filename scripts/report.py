"""Render measured release tables from the checked-in artifact set."""
import json
from pathlib import Path

import pandas as pd

from src.generate import ROOT
from src.simulation import summarize

SNAPSHOT = ROOT / "deployment/snapshot"
REPORTS = ROOT / "reports"


def table(headers, rows):
    def line(values):
        return "| " + " | ".join(map(str, values)) + " |"

    return "\n".join([line(headers), line(["---"]*len(headers)), *(line(row) for row in rows)])


def dollars(amount):
    return f"-${abs(amount):,.2f}" if amount < 0 else f"${amount:,.2f}"


def sql(name):
    return pd.read_csv(SNAPSHOT/"analytics"/f"{name}.csv")


def render_results(model, profile, manifest):
    test = model["test"]
    normal = summarize(pd.read_csv(SNAPSHOT/"scenarios.csv").query("scenario == 'Normal'"))
    all_runs = pd.read_csv(SNAPSHOT/"scenarios.csv")
    scenarios = all_runs[all_runs.strategy.eq("Expected net benefit")].groupby("scenario").net
    ap_lower, ap_upper = test["ap_month_block_ci"]
    tn, fp = test["confusion"][0]
    fn, tp = test["confusion"][1]
    ranking = table(["Risk candidate","Validation AP (raw)","Validation AP (calibrated)","Test AP (calibrated)"],
        [(row["model"], f'{row["selection_ap"]:.4f}', f'{row["ap"]:.4f}',
          f'{model["test_baselines"][row["model"]]["ap"]:.4f}') for row in model["validation"]])
    regression = table(["Conditional amount candidate","Validation MAE","Validation RMSE"],
        [(row["model"], dollars(row["mae"]), dollars(row["rmse"])) for row in model["amount_validation"]])
    policy = table(["Strategy","Reviews","Actionable cases","Gross","Review expense","Net","Worst net","Added hours"],
        [(name,f"{row.reviewed:.1f}",f"{row.detected:.1f}",dollars(row.gross),dollars(row.expense),
          dollars(row.net),dollars(row.downside),f"{row.delay:.1f}") for name,row in normal.iterrows()])
    stress = table(["Scenario","Mean net","Sample SD","Worst replay"],
        [(name,dollars(net.mean()),dollars(net.std()),dollars(net.min())) for name,net in scenarios])
    quarter = [r for r in model["segments"] if r["dimension"] == "Quarter"]
    time = table(["Prediction quarter","Claims","Prevalence","AP","Brier"],
        [(r["group"],f'{r["n"]:,}',f'{r["prevalence"]:.2%}',f'{r["ap"]:.4f}',f'{r["brier"]:.4f}') for r in quarter])
    age = profile["summary"]
    return f"""# Measured results

The seed-{manifest['seed']} release generates {age['claims']:,} claims from {age['first_report']} through {age['last_report']}. The compact replay retains {manifest['queue_claims']:,} scored claims from Q1 2024. The risk and amount evaluation uses all {model['sample_sizes']['test']:,} eligible holdout claims. The generated integrity checks report {sum(profile['checks'].values())} violations across {len(profile['checks'])} cross-row checks.

## Risk and amount performance

{ranking}

**Selected risk model** · {model['selected']}. Test prevalence {model['test_prevalence']:.2%}. AP {test['ap']:.4f} with 95% month-block bootstrap interval [{ap_lower:.4f}, {ap_upper:.4f}]. ROC AUC {test['roc_auc']:.4f}. Brier {test['brier']:.4f}. At the frozen cutoff {model['threshold']:.4f}, precision was {test['precision']:.2%} and recall was {test['recall']:.2%}, with {tn:,} true negatives, {fp:,} false positives, {fn:,} false negatives and {tp:,} true positives. At a separate 10% review quota, precision was {test['precision_at_k']:.2%} and recall {test['recall_at_k']:.2%}, identifying {dollars(test['dollars_at_k'])} of synthetic actionable exposure before review costs or recoverability.

{regression}

**Selected conditional amount model** · {model['amount_model']}. Holdout conditional MAE was {dollars(test['conditional_mae'])} and RMSE was {dollars(test['conditional_rmse'])}. The validation-based 90% interval covered {test['conditional_interval_coverage']:.2%} of holdout actionable outcomes. All-claim MAE of probability × conditional amount was {dollars(test['unconditional_mae'])}.

{time}

## Matched intervention replays

Mean normal-scenario results across seeds 11, 27 and 53. Net subtracts both expense and modeled delay cost. Gross includes simulated prevented and recovered amounts. Added delay is summed across discretionary reviews.

{policy}

Expected-net-benefit policy sensitivity, in dollars per Q1 replay:

{stress}

The raw file contains all six policies for all eight scenarios and three seeds. It includes false-positive reviews, missed cases, true avoidable amounts identified, separate prevention and recovery, net benefit per hour and maximum modeled delay.

[Critical review](critical-validation.md) · [Raw scenario runs](../deployment/snapshot/scenarios.csv) · [Model audit](../deployment/snapshot/model.json)
"""


def render_sql(profile):
    f = {name: sql(name) for name in profile["sql_questions"]}
    rec = f["reconciliation"].iloc[0]
    vendor = f["vendors"]
    risk_exposure = f["leakage"].set_index("mechanism")
    cohort = f["cohorts"]
    cover = f["coverage"].iloc[0]
    workload = f["workload"].sort_values("workload").iloc[-1]
    bottleneck = f["bottlenecks"].sort_values("mean_days").iloc[-1]
    observations = {
        "frequency": f'Peak intake reaches {f["frequency"].claims.max():,} claims in a month. Use peak demand for staffing plans.',
        "paid_losses": f'Calendar net loss totals {dollars(f["paid_losses"].dollars.sum())}. Finance can reconcile booking trends separately from first-notice volume.',
        "coverage": f'{cover.coverage} contributes {dollars(cover.paid)} in observed payments, the largest coverage total. Use this for reserve monitoring.',
        "settlement": f'Median settlement ranges from {f["settlement"].median_days.min():.0f} to {f["settlement"].median_days.max():.0f} days across severity groups. Set cycle-time comparisons within severity.',
        "estimate": f'Mean final-minus-initial bias by severity ranges from {dollars(f["estimate"].bias.min())} to {dollars(f["estimate"].bias.max())}. Monitor forecast bias by severity.',
        "reserves": f'Net lifecycle reserve change is {dollars(f["reserves"].aggregate_change.sum())} for this closed extract. Reserve teams can inspect direction and magnitudes by lifecycle stage.',
        "supplements": f'Quarterly supplement incidence ranges from {f["supplements"].rate.min():.1%} to {f["supplements"].rate.max():.1%}. Review documentation trends separately from legitimate repair supplements.',
        "vendors": f'Raw mean paid has cross-vendor SD {dollars(vendor.mean_paid.std())}, versus adjusted residual SD {dollars(vendor.residual.std())}. Use adjusted results for file checks, with no inference of wrongdoing.',
        "workload": f'Team {workload.team} has the highest mean workload at {workload.workload:.1f}. Allocate support and examine backlog using case-mix-adjusted cycle time.',
        "documentation": f'Coverage-level documentation readiness ranges from {f["documentation"].documented_by_72h.min():.1%} to {f["documentation"].documented_by_72h.max():.1%}. Set coverage-specific collection priorities.',
        "duplicates": f'{int(f["duplicates"].flagged_claims.iloc[0]):,} claims contain a duplicate indicator. Reconcile invoices and reversals before any recovery action.',
        "recoveries": f'{int(f["recoveries"].missed_opportunities.sum()):,} claims contain a simulated missed opportunity. Triage on available evidence and allow time for substantiation.',
        "reopens": f'{f["reopens"].reopened.sum():,} files reopened. Link reopen cases to documentation and initial closure review.',
        "leakage": f'The simulator generates {dollars(risk_exposure.exposure.sum())} of avoidable exposure. Resource allocation should account for feasibility and partial response.',
        "opportunities": f'{f["opportunities"].eligible.sum():,} claims reach the 72-hour checkpoint eligible for scoring. Early closures consume no review slots.',
        "cohorts": f'{cohort.day_30.sum()/cohort.ultimate.sum():.1%} of net payments post by day 30 across cohorts. Finance can use vintage comparisons to distinguish maturity from cost level.',
        "bottlenecks": f'The slowest displayed group averages {bottleneck.mean_days:.1f} days. Stratify service investigation by documentation and complexity.',
        "reconciliation": f'Observed paid {dollars(rec.observed_paid)} = legitimate {dollars(rec.legitimate)} + avoidable {dollars(rec.avoidable)} − missed recovery {dollars(rec.missed_recovery)}. The signed difference is {dollars(rec.difference)}.',
        "vendor_trends": f'{f["vendor_trends"].month.nunique()} booking months appear in the specialization rollup. Compare payment and supplement development within comparable repair categories.',
    }
    sections = ["# DuckDB analytical findings", "",
                "Queries use the generated ledger and, where required, an offline simulation truth join.",
                "[Executable SQL](../sql/analyses.sql)"]
    for name, question in profile["sql_questions"].items():
        sections += ["", f"## {name.replace('_',' ').capitalize()}", "", question, "",
                     observations[name], "", f"[Output CSV](../deployment/snapshot/analytics/{name}.csv)"]
    return "\n".join(sections)+"\n"


if __name__ == "__main__":
    model, profile, manifest = [json.loads((SNAPSHOT/f"{name}.json").read_text())
                                for name in ("model","data_report","manifest")]
    (REPORTS/"results.md").write_text(render_results(model,profile,manifest))
    (REPORTS/"sql-findings.md").write_text(render_sql(profile))
