import re

from src.generate import ROOT


def run_analytics(con, features, truth):
    con.register("early", features)
    con.register("labels", truth)
    con.execute("""CREATE OR REPLACE TEMP VIEW ledger AS
        WITH p AS (
            SELECT claim_id,sum(CASE WHEN category='reversal' THEN -amount ELSE amount END) AS net,
                   sum(CASE WHEN category='supplement' THEN amount ELSE 0 END) AS supplement
            FROM payments GROUP BY claim_id
        )
        SELECT c.claim_id,c.fnol,c.settled,c.reopened,c.vendor_id,c.severity,c.complexity,
               c.initial_estimate,c.liability,policy.coverage,p.net,p.supplement,
               date_diff('day',c.fnol,c.settled) AS cycle
        FROM claims c JOIN policies policy USING(policy_id) JOIN p USING(claim_id)
    """)
    source = (ROOT / "sql/analyses.sql").read_text()
    chunks = re.split(r"^-- (\w+) \| (.+)\n", source, flags=re.M)
    try:
        return {name: (question, con.execute(query).df())
                for name, question, query in zip(chunks[1::3], chunks[2::3], chunks[3::3])}
    finally:
        con.execute("DROP VIEW ledger")
        con.unregister("early")
        con.unregister("labels")
