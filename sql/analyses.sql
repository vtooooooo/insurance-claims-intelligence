-- frequency | How do reported volume and mean paid severity change by month?
SELECT date_trunc('month',fnol)::DATE AS month,count(*) AS claims,round(avg(net)/100,2) AS mean_paid FROM ledger GROUP BY 1 ORDER BY 1;
-- paid_losses | How much of each payment category posts by calendar month?
SELECT date_trunc('month',paid)::DATE AS month,category,sum(CASE WHEN category='reversal' THEN -amount ELSE amount END)/100 AS dollars FROM payments GROUP BY 1,2 ORDER BY 1,2;
-- coverage | Where are paid costs concentrated by coverage?
SELECT coverage,count(*) AS claims,sum(net)/100 AS paid,avg(net)/100 AS mean_paid FROM ledger GROUP BY 1 ORDER BY paid DESC;
-- settlement | How long do claims take to settle by severity?
SELECT severity,count(*) AS claims,avg(cycle) AS mean_days,quantile_cont(cycle,.5) AS median_days,quantile_cont(cycle,.9) AS p90_days FROM ledger GROUP BY 1 ORDER BY 1;
-- estimate | What is the signed difference between the early estimate and ultimate paid?
SELECT severity,avg(initial_estimate)/100 AS initial_mean,avg(net)/100 AS paid_mean,avg(net-initial_estimate)/100 AS bias FROM ledger GROUP BY 1 ORDER BY 1;
-- reserves | How do aggregate reserves change by lifecycle event?
SELECT reason,count(*) AS changes,avg(new-previous)/100 AS mean_change,sum(new-previous)/100 AS aggregate_change FROM reserves GROUP BY 1 ORDER BY 1;
-- supplements | How frequently do supplements post throughout the observation period?
SELECT date_trunc('quarter',fnol)::DATE AS quarter,avg((supplement>0)::INTEGER) AS rate,avg(supplement)/100 AS mean_per_claim FROM ledger GROUP BY 1 ORDER BY 1;
-- vendors | Which vendors have a cost residual after adjustment for severity, coverage and complexity?
WITH strata AS (SELECT *,avg(net) OVER(PARTITION BY severity,coverage,complexity) AS expected FROM ledger)
SELECT vendor_id,any_value(specialization) AS specialization,count(*) AS claims,avg(net)/100 AS mean_paid,avg(net-expected)/100 AS residual,avg(cycle) AS days,avg((supplement>0)::INTEGER) AS supplement_rate,sum(net)/100 AS total_paid FROM strata JOIN vendors USING(vendor_id) GROUP BY 1 ORDER BY 1;
-- workload | How do cycle time and expected cycle differences vary by team?
WITH strata AS (SELECT *,avg(cycle) OVER (PARTITION BY severity,complexity,coverage) AS expected FROM ledger)
SELECT team,count(*) AS claims,avg(e.detail) AS workload,avg(cycle) AS mean_days,avg(cycle-expected) AS residual_days,count(*) FILTER(WHERE cycle>=40) AS older_than_40_days FROM strata JOIN claims c USING(claim_id) JOIN adjusters a ON c.adjuster_id=a.adjuster_id JOIN events e USING(claim_id) WHERE e.kind='assignment' GROUP BY 1 ORDER BY 1;
-- documentation | How often is documentation present by the 72-hour checkpoint?
SELECT coverage,count(*) AS eligible,avg(documented) AS documented_by_72h,avg(report_delay) AS mean_reporting_delay FROM early GROUP BY 1 ORDER BY 1;
-- duplicates | How many matching invoice and amount combinations appear more than once?
WITH d AS (SELECT claim_id, invoice, amount,count(*) AS instances FROM payments WHERE category='initial' GROUP BY ALL HAVING count(*)>1)
SELECT count(DISTINCT claim_id) AS flagged_claims,coalesce(sum((instances-1)*amount),0)/100 AS flagged_dollars FROM d;
-- recoveries | What is the simulated exposure attributable to missed recoveries?
SELECT coverage,count(*) FILTER(WHERE liability) AS liability_evidence,count(*) FILTER(WHERE opportunity_cents>0) AS missed_opportunities,sum(opportunity_cents)/100 AS exposure FROM ledger JOIN labels USING(claim_id) GROUP BY 1 ORDER BY 1;
-- reopens | How often are claims reopened after initial settlement?
SELECT coverage,count(*) AS claims,count(reopened) AS reopened,avg((reopened IS NOT NULL)::INTEGER) AS rate FROM ledger GROUP BY 1 ORDER BY 1;
-- leakage | Which synthetic mechanisms contribute to avoidable cost exposure?
SELECT mechanism,count(*) AS claims,count(*) FILTER(WHERE actionable) AS actionable,sum(avoidable_cents)/100 AS exposure,sum(avoidable_cents) FILTER(WHERE actionable)/100 AS actionable_exposure FROM labels GROUP BY 1 ORDER BY exposure DESC;
-- opportunities | How many claims with actionable labels were eligible by 72 hours?
SELECT extract(year FROM checkpoint)::INTEGER AS year,count(*) AS eligible,avg(actionable::INTEGER) AS prevalence,sum(CASE WHEN actionable THEN avoidable_cents ELSE 0 END)/100 AS actionable_exposure FROM early JOIN labels USING(claim_id) GROUP BY 1 ORDER BY 1;
-- cohorts | How does cumulative paid development by claim vintage compare at fixed ages?
SELECT date_trunc('quarter',fnol)::DATE AS vintage,sum(CASE WHEN paid <= fnol+INTERVAL 15 DAY THEN signed ELSE 0 END)/100 AS day_15,sum(CASE WHEN paid <= fnol+INTERVAL 30 DAY THEN signed ELSE 0 END)/100 AS day_30,sum(signed)/100 AS ultimate FROM claims JOIN (SELECT claim_id,paid,CASE WHEN category='reversal' THEN -amount ELSE amount END AS signed FROM payments) p USING(claim_id) GROUP BY 1 ORDER BY 1;
-- bottlenecks | How do cycle times differ by documentation status and complexity?
SELECT e.complexity,documented,count(*) AS claims,avg(cycle) AS mean_days,quantile_cont(cycle,.9) AS p90_days FROM early e JOIN ledger l USING(claim_id) GROUP BY 1,2 ORDER BY 1,2;
-- reconciliation | How does legitimate cost reconcile to observed paid and avoidable costs?
SELECT sum(legitimate_cents)/100 AS legitimate,sum(net)/100 AS observed_paid,sum(avoidable_cents)/100 AS avoidable,sum(opportunity_cents)/100 AS missed_recovery,sum(net-legitimate_cents-avoidable_cents+opportunity_cents)/100 AS difference FROM ledger JOIN labels USING(claim_id);
-- vendor_trends | How does posted loss move by booking month and repair specialization?
SELECT date_trunc('month',paid)::DATE AS month,specialization,count(DISTINCT claim_id) AS paid_claims,sum(CASE WHEN p.category='reversal' THEN -amount ELSE amount END)/100 AS net_paid,sum(CASE WHEN p.category='supplement' THEN amount ELSE 0 END)/100 AS supplements FROM payments p JOIN vendors USING(vendor_id) GROUP BY 1,2 ORDER BY 1,2;
