# DuckDB analytical findings

Queries use the generated ledger and, where required, an offline simulation truth join.
[Executable SQL](../sql/analyses.sql)

## Frequency

How do reported volume and mean paid severity change by month?

Peak intake reaches 3,265 claims in a month. Use peak demand for staffing plans.

[Output CSV](../deployment/snapshot/analytics/frequency.csv)

## Paid losses

How much of each payment category posts by calendar month?

Calendar net loss totals $316,249,728.37. Finance can reconcile booking trends separately from first-notice volume.

[Output CSV](../deployment/snapshot/analytics/paid_losses.csv)

## Coverage

Where are paid costs concentrated by coverage?

Collision contributes $183,003,221.88 in observed payments, the largest coverage total. Use this for reserve monitoring.

[Output CSV](../deployment/snapshot/analytics/coverage.csv)

## Settlement

How long do claims take to settle by severity?

Median settlement ranges from 27 to 37 days across severity groups. Set cycle-time comparisons within severity.

[Output CSV](../deployment/snapshot/analytics/settlement.csv)

## Estimate

What is the signed difference between the early estimate and ultimate paid?

Mean final-minus-initial bias by severity ranges from -$228.38 to -$28.51. Monitor forecast bias by severity.

[Output CSV](../deployment/snapshot/analytics/estimate.csv)

## Reserves

How do aggregate reserves change by lifecycle event?

Net lifecycle reserve change is $0.00 for this closed extract. Reserve teams can inspect direction and magnitudes by lifecycle stage.

[Output CSV](../deployment/snapshot/analytics/reserves.csv)

## Supplements

How frequently do supplements post throughout the observation period?

Quarterly supplement incidence ranges from 29.9% to 31.7%. Review documentation trends separately from legitimate repair supplements.

[Output CSV](../deployment/snapshot/analytics/supplements.csv)

## Vendors

Which vendors have a cost residual after adjustment for severity, coverage and complexity?

Raw mean paid has cross-vendor SD $1,421.40, versus adjusted residual SD $53.61. Use adjusted results for file checks, with no inference of wrongdoing.

[Output CSV](../deployment/snapshot/analytics/vendors.csv)

## Workload

How do cycle time and expected cycle differences vary by team?

Team D has the highest mean workload at 25.4. Allocate support and examine backlog using case-mix-adjusted cycle time.

[Output CSV](../deployment/snapshot/analytics/workload.csv)

## Documentation

How often is documentation present by the 72-hour checkpoint?

Coverage-level documentation readiness ranges from 66.6% to 67.3%. Set coverage-specific collection priorities.

[Output CSV](../deployment/snapshot/analytics/documentation.csv)

## Duplicates

How many matching invoice and amount combinations appear more than once?

1,941 claims contain a duplicate indicator. Reconcile invoices and reversals before any recovery action.

[Output CSV](../deployment/snapshot/analytics/duplicates.csv)

## Recoveries

What is the simulated exposure attributable to missed recoveries?

887 claims contain a simulated missed opportunity. Triage on available evidence and allow time for substantiation.

[Output CSV](../deployment/snapshot/analytics/recoveries.csv)

## Reopens

How often are claims reopened after initial settlement?

4,068 files reopened. Link reopen cases to documentation and initial closure review.

[Output CSV](../deployment/snapshot/analytics/reopens.csv)

## Leakage

Which synthetic mechanisms contribute to avoidable cost exposure?

The simulator generates $4,661,875.07 of avoidable exposure. Resource allocation should account for feasibility and partial response.

[Output CSV](../deployment/snapshot/analytics/leakage.csv)

## Opportunities

How many claims with actionable labels were eligible by 72 hours?

115,131 claims reach the 72-hour checkpoint eligible for scoring. Early closures consume no review slots.

[Output CSV](../deployment/snapshot/analytics/opportunities.csv)

## Cohorts

How does cumulative paid development by claim vintage compare at fixed ages?

41.2% of net payments post by day 30 across cohorts. Finance can use vintage comparisons to distinguish maturity from cost level.

[Output CSV](../deployment/snapshot/analytics/cohorts.csv)

## Bottlenecks

How do cycle times differ by documentation status and complexity?

The slowest displayed group averages 43.2 days. Stratify service investigation by documentation and complexity.

[Output CSV](../deployment/snapshot/analytics/bottlenecks.csv)

## Reconciliation

How does legitimate cost reconcile to observed paid and avoidable costs?

Observed paid $316,249,728.37 = legitimate $312,027,525.96 + avoidable $4,661,875.07 − missed recovery $439,672.66. The signed difference is $0.00.

[Output CSV](../deployment/snapshot/analytics/reconciliation.csv)

## Vendor trends

How does posted loss move by booking month and repair specialization?

51 booking months appear in the specialization rollup. Compare payment and supplement development within comparable repair categories.

[Output CSV](../deployment/snapshot/analytics/vendor_trends.csv)
