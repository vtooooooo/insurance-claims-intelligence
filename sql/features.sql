WITH checkpoints AS (
    SELECT claim_id, fnol + INTERVAL 72 HOURS AS checkpoint
    FROM claims WHERE settled IS NULL OR settled > fnol + INTERVAL 72 HOURS
), early_events AS (
    SELECT x.claim_id, count(e.event_id) AS early_events,
           max(e.detail) FILTER (WHERE e.kind = 'assignment') AS workload,
           count(e.event_id) FILTER (WHERE e.kind = 'documentation') AS documented
    FROM checkpoints x LEFT JOIN events e
      ON e.claim_id=x.claim_id AND e.happened <= x.checkpoint
    GROUP BY x.claim_id
), early_reserves AS (
    SELECT x.claim_id, arg_max(r.new,r.changed) AS early_reserve
    FROM checkpoints x LEFT JOIN reserves r
      ON r.claim_id=x.claim_id AND r.changed <= x.checkpoint
    GROUP BY x.claim_id
)
SELECT c.claim_id, x.checkpoint, p.coverage, c.severity, c.complexity,
       c.initial_estimate / 100.0 AS estimate, r.early_reserve / 100.0 AS reserve,
       date_diff('day', c.incident, c.fnol) AS report_delay,
       e.workload, e.documented, e.early_events, c.liability::INTEGER AS liability,
       v.baseline_days AS vendor_days, v.supplement_history AS vendor_supp,
       a.team, p.state
FROM checkpoints x JOIN claims c USING (claim_id)
JOIN policies p USING (policy_id) JOIN vendors v USING (vendor_id)
JOIN adjusters a USING (adjuster_id) JOIN early_events e USING (claim_id)
JOIN early_reserves r USING (claim_id)
ORDER BY c.claim_id
