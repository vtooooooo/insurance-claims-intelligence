"""Integrity checks shared by training and CI."""
CHECKS = {
    "chronology": """SELECT count(*) FROM claims c JOIN policies p USING(policy_id)
        WHERE NOT (effective <= incident AND incident < expiration AND incident <= fnol
          AND fnol < settled AND (reopened IS NULL OR reopened > settled))""",
    "event timing": """SELECT count(*) FROM events e JOIN claims c USING(claim_id)
        WHERE happened < fnol OR (happened > settled AND kind NOT IN
        ('reopened','reclosed','recovery assessment'))""",
    "payments": """SELECT count(*) FROM payments p JOIN claims c USING(claim_id)
        WHERE paid < fnol OR paid > settled OR p.status <> 'posted'""",
    "reserve continuity": """SELECT count(*) FROM (
        SELECT *, lag(new,1,0) OVER(PARTITION BY claim_id ORDER BY changed) AS expected
        FROM reserves) WHERE previous <> expected""",
    "reserve closure": """SELECT count(*) FROM claims c JOIN
        (SELECT claim_id, arg_max(new,changed) AS last, max(changed) AS final
         FROM reserves GROUP BY claim_id) r USING(claim_id)
        WHERE last <> current_reserve OR final <> settled OR status NOT IN ('Closed','Reclosed')""",
    "reversals": """SELECT count(*) FROM payments r LEFT JOIN payments p ON r.reverses=p.payment_id
        WHERE r.category='reversal' AND (p.payment_id IS NULL OR p.claim_id<>r.claim_id
        OR p.amount<>r.amount OR p.paid>=r.paid OR p.category<>'adjustment')""",
    "intervention chronology": """SELECT count(*) FROM interventions i JOIN claims c USING(claim_id)
        WHERE reviewed < fnol OR reviewed > settled OR expense_cents < 0 OR recovered_cents < 0""",
    "payment adjustment references": """SELECT count(*) FROM payments
        WHERE (category='reversal') <> (reverses IS NOT NULL)""",
    "duplicate reversals": """SELECT count(*) FROM (SELECT reverses FROM payments
        WHERE reverses IS NOT NULL GROUP BY reverses HAVING count(*)>1)""",
    "financial reconciliation": """SELECT count(*) FROM labels t FULL OUTER JOIN (
        SELECT claim_id,sum(CASE WHEN category='reversal' THEN -amount ELSE amount END) net
        FROM payments GROUP BY claim_id) p USING(claim_id)
        WHERE net IS DISTINCT FROM paid_cents OR
        paid_cents <> legitimate_cents + avoidable_cents - opportunity_cents""",
    "duplicate indicator": """WITH flagged AS (SELECT DISTINCT claim_id FROM (
        SELECT claim_id, invoice, amount FROM payments WHERE category='initial'
        GROUP BY ALL HAVING count(*)>1))
        SELECT count(*) FROM labels LEFT JOIN flagged USING(claim_id)
        WHERE (flagged.claim_id IS NOT NULL) <> (mechanism='duplicate payment')""",
}


def verify(con, truth):
    con.register("labels", truth)
    try:
        results = {name: con.execute(query).fetchone()[0] for name, query in CHECKS.items()}
    finally:
        con.unregister("labels")
    if any(results.values()):
        raise ValueError(results)
    return results
