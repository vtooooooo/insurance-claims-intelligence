"""Synthetic personal auto ledger. Financial columns store integer cents."""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MECHANISMS = ["documentation", "repair estimate", "duplicate payment",
              "vendor billing", "subrogation", "specialist escalation"]


def generate(path, n=120_000, seed=27):
    rng = np.random.default_rng(seed)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute("BEGIN")
    for name in ("interventions", "reserves", "payments", "events", "claims",
                 "adjusters", "vendors", "policies"):
        con.execute(f"DROP TABLE IF EXISTS {name}")
    con.execute((ROOT / "sql/schema.sql").read_text())

    def insert(table, **cols):
        frame = pd.DataFrame(cols)
        con.register("batch", frame)
        con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM batch")
        con.unregister("batch")

    ids = np.arange(1, n + 1)
    day = np.sort(rng.choice(1461, n, p=volume_weights()))
    fnol = pd.Timestamp("2021-01-01") + pd.to_timedelta(day, unit="D")
    delay = rng.negative_binomial(2, .50, n).clip(0, 35)
    incident = fnol - pd.to_timedelta(delay, unit="D")
    state = rng.choice(["CA", "TX", "OH", "AZ", "CO", "VA", "WA", "NC"], n)
    coverage = rng.choice(["Collision", "Comprehensive", "Property liability"], n, p=[.60,.24,.16])
    severity = rng.choice([1,2,3,4,5], n, p=[.26,.34,.25,.11,.04])
    complex_case = (severity + rng.integers(-2, 3, n)).clip(1, 5)
    vendor = (complex_case - 1) * 12 + rng.integers(1, 13, n)
    adj = rng.integers(1, 81, n)
    vendor_days = rng.uniform(4, 15, 60)
    vendor_supp = rng.uniform(.08, .28, 60)
    adj_load = rng.integers(14, 35, 80)
    shock = ((day % 365 >= 230) & (day % 365 <= 250))
    workload = adj_load[adj-1] + shock * 12 + rng.integers(-6, 7, n)
    docs_hours = rng.lognormal(3.8 + .06 * delay + .025 * (workload - 24), .8).clip(3, 600).astype(int)
    docs_time = fnol + pd.to_timedelta(docs_hours, unit="h")
    liability = (coverage != "Comprehensive") & (rng.random(n) < .32)
    deductible = np.where(coverage == "Property liability", 0, rng.choice([25000,50000,100000], n))
    limit = rng.choice([2500000,5000000,10000000], n)
    legitimate = np.maximum(18000, (severity**1.45 * 54000 + complex_case * 25000) *
                            rng.lognormal(0, .57, n) - deductible).astype(int)
    legitimate = np.minimum(legitimate, limit * 9 // 10)
    estimate = np.minimum(limit, (legitimate * rng.lognormal(0, .33, n)).astype(int))
    reserve = np.minimum(limit, (estimate * 1.12).astype(int))
    supplement = rng.random(n) < (vendor_supp[vendor-1] + .055 * complex_case)
    duration = np.ceil(5 + vendor_days[vendor-1] * .7 + 3 * complex_case + docs_hours / 35 +
                       np.maximum(workload - 25, 0) * .42 + rng.gamma(2, 5, n)).astype(int)
    fast = (severity == 1) & (rng.random(n) < .16)
    duration[fast] = 2
    settled = fnol + pd.to_timedelta(duration, unit="D")
    reopen = (~fast) & (rng.random(n) < .035)
    reopened = (settled + pd.to_timedelta(17, unit="D")).where(reopen)
    mechanism_weights = np.column_stack([
        1 + (docs_hours > 72) * 1.4, 1 + .28 * complex_case,
        .8 + .03 * workload, 1 + vendor_supp[vendor-1] * 3,
        .15 + liability * 2.3, .4 + .25 * severity])
    mechanism = (rng.random(n)[:, None] * mechanism_weights.sum(axis=1)[:, None] >
                 mechanism_weights.cumsum(axis=1)).sum(axis=1)
    logit = (-3.45 + .48 * (docs_hours > 72) + .047 * (workload - 24) +
             .13 * complex_case + .035 * delay + .40 * liability +
             .17 * (day > 730) + rng.normal(0, .65, n))
    latent = rng.random(n) < 1 / (1 + np.exp(-logit))
    feasible = (~fast) & (rng.random(n) < (.88 - .002 * np.maximum(docs_hours - 72, 0)))
    feasible &= (mechanism != 4) | liability
    candidate = (legitimate * rng.uniform(.025, .26, n)).astype(int) + rng.integers(1000, 18000, n)
    duplicate = latent & (mechanism == 2)
    base_piece = np.minimum(np.maximum(legitimate // 6, 1), candidate)
    avoidable = np.where(latent, np.minimum(candidate, limit - legitimate), 0)
    avoidable = np.where(duplicate, base_piece, avoidable)
    recovery = latent & (mechanism == 4)
    paid_total = legitimate + np.where(recovery, 0, avoidable)
    future_recovery = np.where(recovery, avoidable, 0)
    actionable = latent & feasible & (avoidable > 0)
    effectiveness = rng.beta(5, 3, n)
    mature_at = settled + pd.to_timedelta(30, unit="D")

    insert("policies", policy_id=ids, state=state, coverage=coverage, deductible=deductible,
           coverage_limit=limit, effective=incident-pd.to_timedelta(rng.integers(0,365,n),unit="D"),
           expiration=incident+pd.to_timedelta(365,unit="D"), condition="standard synthetic terms")
    insert("vendors", vendor_id=np.arange(1,61), category="repair network",
           specialization=np.repeat(["Basic","Light","Intermediate","Advanced","Structural"],12),
           baseline_days=vendor_days, supplement_history=vendor_supp)
    insert("adjusters", adjuster_id=np.arange(1,81), team=np.repeat(["A","B","C","D","E","F","G","H"],10),
           experience=np.tile(["Developing","Established","Senior","Established"],20),
           baseline_workload=adj_load)
    insert("claims", claim_id=ids, policy_id=ids, incident=incident, fnol=fnol,
           claim_type=np.where(coverage=="Comprehensive","Noncollision","Vehicle damage"),
           severity=severity, complexity=complex_case, initial_estimate=estimate, current_reserve=0,
           status=np.where(reopen,"Reclosed","Closed"), adjuster_id=adj, vendor_id=vendor,
           settled=settled, reopened=reopened, liability=liability)
    event_counter = 0
    for kind, happened, detail, mask in (
        ("FNOL", fnol, np.zeros(n), ids > 0),
        ("assignment", fnol, workload, ids > 0),
        ("assessment", fnol+pd.Timedelta(hours=18), complex_case, ids > 0),
        ("documentation", docs_time, np.ones(n), docs_time <= settled),
        ("repair complete", settled-pd.Timedelta(hours=6), complex_case, ids > 0),
        ("settlement", settled, np.zeros(n), ids > 0),
        ("reopened", reopened, np.ones(n), reopen),
        ("reclosed", reopened+pd.Timedelta(days=5), np.ones(n), reopen),
        ("recovery assessment", mature_at, liability, liability),
    ):
        count = mask.sum()
        insert("events", event_id=np.arange(event_counter+1,event_counter+count+1),
               claim_id=ids[mask], happened=happened[mask], kind=kind, detail=detail[mask], source="synthetic operations")
        event_counter += count

    reserve_mid = np.maximum(reserve, paid_total)
    for changed, previous, new, reason in (
        (fnol, np.zeros(n), reserve, "initial assessment"),
        (settled-pd.Timedelta(hours=12), reserve, reserve_mid, "repair assessment"),
        (settled, reserve_mid, np.zeros(n), "settlement"),
    ):
        insert("reserves", claim_id=ids, changed=changed, previous=previous, new=new, reason=reason)

    # Routine observed review records have no modeled treatment or cost recovery.
    regular_review = (~fast) & (np.random.default_rng(seed + 10001).random(n) < .08)
    insert("interventions", intervention_id=ids[regular_review], claim_id=ids[regular_review],
           kind="routine desk review", reviewed=fnol[regular_review] + pd.Timedelta(days=4),
           expense_cents=1200, outcome="review logged", recovered_cents=0)

    supp_amount = np.where(supplement, legitimate // 8, 0)
    reversed_mask = rng.random(n) < .015
    adjustment = legitimate // 25
    for block, category, amount, paid, mask, invoice, reverses in (
        (0,"initial",base_piece,fnol+pd.to_timedelta(np.maximum(1,duration//2),unit="D"),ids>0,"base",None),
        (1,"supplement",supp_amount,settled-pd.Timedelta(hours=2),supplement,"supp",None),
        (2,"final",paid_total-base_piece-supp_amount-np.where(duplicate,base_piece,0),settled,ids>0,"final",None),
        (3,"initial",base_piece,fnol+pd.to_timedelta(np.maximum(1,duration//2),unit="D")+pd.Timedelta(hours=2),duplicate,"base",None),
        (4,"adjustment",adjustment,settled-pd.Timedelta(hours=4),reversed_mask,"correction",None),
        (5,"reversal",adjustment,settled-pd.Timedelta(hours=1),reversed_mask,"reversal",4*n+ids[reversed_mask]),
    ):
        insert("payments", payment_id=block*n+ids[mask], claim_id=ids[mask], paid=paid[mask],
               amount=amount[mask], category=category, status="posted", vendor_id=vendor[mask],
               invoice=invoice, reverses=reverses)

    # Offline financial ledger and labels are physically separate from the database.
    truth = pd.DataFrame(dict(claim_id=ids, mature_at=mature_at, actionable=actionable,
                              mechanism=np.where(latent, np.array(MECHANISMS)[mechanism], "none"),
                              feasible=feasible, avoidable_cents=avoidable, effectiveness=effectiveness,
                              legitimate_cents=legitimate, paid_cents=paid_total,
                              opportunity_cents=future_recovery, duration=duration))
    con.execute("COMMIT")
    truth.to_parquet(path.with_suffix(".truth.parquet"), index=False)
    return con, truth


def volume_weights():
    days = np.arange(1461) % 365
    weights = np.where((days >= 230) & (days <= 250), 1.7, 1.)
    return weights / weights.sum()
