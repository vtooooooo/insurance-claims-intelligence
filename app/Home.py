"""Northstar Mutual's synthetic claims operations workspace."""
import json
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.decision import Scenario, prioritize
from src.simulation import simulate, summarize

SNAPSHOT = ROOT / "deployment/snapshot"
VIEWS = ("Executive Overview", "Claims Diagnostics", "Leakage Risk Intelligence",
         "Intervention Queue", "Vendor Intelligence", "Adjuster Operations",
         "Intervention Simulator", "Model Governance")

st.set_page_config(page_title="Northstar Mutual | Claims Intelligence", page_icon="◈",
                   layout="wide")
st.markdown("""
<style>
[data-testid="stMetric"] {background:#ffffff; border:1px solid #dbe5ed;
  border-radius:12px; padding:1rem 1.15rem;}
[data-testid="stSidebar"] {border-right:1px solid #dbe5ed;}
[data-testid="stHeadingWithActionElements"] h1 {letter-spacing:-.035em;}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def read_json(name):
    return json.loads((SNAPSHOT / f"{name}.json").read_text())


@st.cache_data
def sql(name):
    return pd.read_csv(SNAPSHOT / "analytics" / f"{name}.csv")


@st.cache_data
def scores():
    return pd.read_parquet(SNAPSHOT / "scores.parquet")


@st.cache_data(max_entries=32)
def run_scenario(scenario, coverage):
    frame = scores()
    if coverage != "All coverages":
        frame = frame[frame.coverage == coverage]
    labels = pd.read_parquet(SNAPSHOT / "evaluation_only.parquet")
    return simulate(frame, labels, scenario)


def dollars(value):
    return f"${value:,.0f}"


def export(frame, filename):
    st.download_button("Download CSV", frame.to_csv(index=False),
                       filename, mime="text/csv")


def line(frame, x, y):
    st.line_chart(frame, x=x, y=y)


def executive():
    profile = read_json("data_report")["summary"]
    payments = sql("reconciliation").iloc[0]
    exposure = scores().expected_exposure.sum()
    metrics = [("Claims", f"{profile['claims']:,}"), ("Observed paid losses", dollars(payments.observed_paid)),
               ("Initial settlement rate", f"{profile['closure_rate']:.1%}"),
               ("Mean time to settlement", f"{profile['settlement_days']:.1f} days")]
    for col, (label, value) in zip(st.columns(4), metrics):
        col.metric(label, value)
    st.subheader("Claims intake and paid severity")
    left, right = st.columns(2)
    with left:
        line(sql("frequency"), "month", "claims")
    with right:
        line(sql("frequency"), "month", "mean_paid")
    st.metric("Estimated actionable exposure · 2024 Q1 replay", dollars(exposure))
    st.caption("Sum of risk × conditional amount across eligible replay claims. Exposure does not account for review costs, success, or recoverability.")
    st.dataframe(sql("coverage"), hide_index=True)


def diagnostics():
    analyses = {"Coverage": "coverage", "Severity and settlement": "settlement",
                "Reserve changes": "reserves", "Payment trends": "paid_losses",
                "Development cohorts": "cohorts", "Documentation bottlenecks": "bottlenecks",
                "Duplicate indicators": "duplicates", "Estimate accuracy": "estimate",
                "Supplements": "supplements", "Documentation": "documentation",
                "Reopens": "reopens", "Recoveries": "recoveries", "Ledger reconciliation": "reconciliation"}
    label = st.selectbox("Analysis", analyses)
    name = analyses[label]
    frame = sql(name)
    st.caption(read_json("data_report")["sql_questions"][name])
    if name == "cohorts":
        line(frame, "vintage", ["day_15", "day_30", "ultimate"])
    if name == "paid_losses":
        st.line_chart(frame, x="month", y="dollars", color="category")
    if name == "settlement":
        st.bar_chart(frame, x="severity", y="claims")
    st.dataframe(frame, hide_index=True)
    export(frame, f"{name}.csv")


def risk(frame):
    st.caption("Frozen predictions at 72 hours after first notice. Relative scores estimate actionable cost risk and are uncertain for individual claims.")
    st.subheader("Distribution of predicted probabilities")
    bins = pd.cut(frame.risk, bins=[-.00001,.025,.05,.075,.1,.15,.25,.5,1],
                  include_lowest=True).value_counts(sort=False)
    st.bar_chart(pd.DataFrame({"risk range": bins.index.astype(str), "claims": bins.values}),
                 x="risk range", y="claims")
    st.dataframe(frame[["claim_id","coverage","risk_category","risk","conditional_amount",
                        "conditional_low","conditional_high","expected_exposure","reason"]].sort_values("risk",ascending=False),hide_index=True)
    st.caption("Amount ranges use the 90th percentile of absolute validation residuals on actionable claims. Coverage may change out of time.")
    st.caption("The explanation names the largest positive score change under a single-feature comparison with a typical training value. Correlated fields can make this comparison unstable.")
    ci = read_json("model")["test"]["ap_month_block_ci"]
    st.caption(f"Out-of-time average precision interval (month-block bootstrap) {ci[0]:.3f}–{ci[1]:.3f}. This measures ranking uncertainty across time blocks.")
    export(frame, "risk_intelligence.csv")


def queue(frame):
    day = st.selectbox("Checkpoint date", frame.checkpoint.dt.date.drop_duplicates().sort_values().tolist())
    columns = st.columns(3)
    capacity = columns[0].slider("Daily claim cap", 0, 20, 4)
    budget = columns[1].slider("Daily review budget ($)", 0, 500, 140, 5)
    hours = columns[2].slider("Staff hours per day", 0., 12., 3., .25)
    daily = frame[frame.checkpoint.dt.date == day]
    result = prioritize(daily, Scenario(capacity=capacity, budget=budget, staff_hours=hours))
    cols = ["claim_id","action","risk","expected_exposure","net_benefit","hours","cost",
            "delay_hours","reason"]
    st.metric("Recommended reviews", len(result))
    if result.empty:
        st.info("No eligible review fits the current constraints with a positive modeled net benefit.")
    st.dataframe(result[cols],hide_index=True)
    export(result[cols], "review_queue.csv")


def vendors():
    frame = sql("vendors")
    specialization = st.selectbox("Repair specialization", ["All"] + sorted(frame.specialization.unique()))
    if specialization != "All":
        frame = frame[frame.specialization == specialization]
    st.bar_chart(frame, x="vendor_id", y="residual")
    st.caption("Residual is the difference from the mean within severity, coverage, and repair-complexity strata. Differences can reflect unmeasured case mix and warrant investigation only.")
    st.dataframe(frame,hide_index=True)
    trend = sql("vendor_trends")
    if specialization != "All":
        trend = trend[trend.specialization == specialization]
    st.subheader("Posted loss by repair specialization")
    st.line_chart(trend, x="month", y="net_paid", color="specialization")
    export(frame, "vendor_case_mix.csv")


def adjusters():
    frame = sql("workload")
    st.bar_chart(frame, x="team", y="workload")
    st.dataframe(frame,hide_index=True)
    st.caption("Team-level cycle residuals account for severity, complexity and coverage. Review capacity is planned separately in staff and specialist hours.")
    export(frame, "team_operations.csv")


def simulator(coverage):
    presets = json.loads((ROOT/"config/scenarios.json").read_text())
    name = st.selectbox("Scenario preset",list(presets))
    baseline = Scenario(**presets[name])
    with st.form(f"scenario-{name}"):
        a,b,c = st.columns(3)
        cap = a.slider("Review capacity / day",0,20,baseline.capacity)
        price = a.slider("Investigation cost multiplier",.25,3.,float(baseline.cost_scale),.05)
        budget = a.slider("Daily budget",0,500,int(baseline.budget),5)
        staff = a.slider("Staff hours per day",0.,10.,float(baseline.staff_hours),.25)
        specialist = a.slider("Specialist hours per day",0.,5.,float(baseline.specialist_hours),.25)
        efficacy = b.slider("Effectiveness multiplier",0.,2.,float(baseline.effectiveness),.05)
        vol = b.slider("Volume multiplier",.25,2.,float(baseline.volume),.05)
        prev = b.slider("Leakage prevalence multiplier",.25,2.,float(baseline.prevalence),.05)
        inflation = c.slider("Vendor inflation multiplier",.75,2.,float(baseline.inflation),.05)
        doc_shift = c.slider("Documentation disruption",0,3,baseline.documentation_delay)
        delay = c.slider("Extra delay per review hour",0.,1.5,float(baseline.delay_per_hour),.05)
        st.form_submit_button("Run simulation")
    scenario = Scenario(capacity=cap,budget=budget,staff_hours=staff,specialist_hours=specialist,
                        cost_scale=price,effectiveness=efficacy,volume=vol,prevalence=prev,
                        inflation=inflation,documentation_delay=doc_shift,delay_per_hour=delay)
    results = run_scenario(scenario,coverage)
    summary = summarize(results).reset_index()
    st.bar_chart(summary,x="strategy",y="net",horizontal=True)
    st.dataframe(summary,hide_index=True)
    st.caption("Means over three matched synthetic replays. Net = prevented + recovered − review expense − modeled delay expense. Downside is the worst replay of the three. A positive mean offers limited evidence with only three synthetic draws.")
    export(results, "simulation_replays.csv")


def governance():
    model = read_json("model")
    st.subheader(model["selected"])
    st.caption(f"Conditional amount model · {model['amount_model']} | Frozen cutoff · {model['threshold']:.3f}")
    result = model["test"]
    for col, key, label in zip(st.columns(4), ("ap","roc_auc","brier","conditional_mae"),
                               ("Test average precision","ROC AUC","Brier score","Conditional MAE ($)")):
        col.metric(label, f"{result[key]:.3f}")
    st.subheader("Calibration")
    calibration = pd.DataFrame(model["reliability"])
    chart = calibration.assign(ideal=calibration.mean_score)
    line(chart,"mean_score",["ideal","actual_rate"])
    st.dataframe(calibration,hide_index=True)
    st.subheader("Feature importance")
    if model["importance"]:
        st.bar_chart(pd.DataFrame(model["importance"]), x="feature", y="ap_drop")
    else:
        st.write("The selected operational rule uses documentation, reporting delay, workload and liability.")
    st.subheader("Temporal and segment validation")
    st.dataframe(pd.DataFrame(model["segments"])[["dimension","group","n","prevalence","ap","brier",
                                                  "precision_at_k","recall_at_k"]],hide_index=True)
    st.dataframe(pd.DataFrame(model["validation"])[["model","selection_ap","ap","brier","precision_at_k"]],
                 hide_index=True)
    st.info("Recommendations support human triage only. Validate source evidence and review urgency before acting. Claim payment and coverage decisions remain with authorized claims staff.")
    st.caption("All outcomes and response assumptions are synthetic. The results do not establish production accuracy, fairness, causality, or savings.")


st.sidebar.markdown("### Northstar Mutual")
st.sidebar.caption("Claims operations")
view = st.sidebar.radio("Navigate", VIEWS, label_visibility="collapsed")
cover = "All coverages"
if view in {"Leakage Risk Intelligence", "Intervention Queue", "Intervention Simulator"}:
    cover = st.sidebar.selectbox("Coverage", ["All coverages"]+sorted(scores().coverage.unique()))
st.title(view)
st.caption("Northstar Mutual Insurance · Synthetic personal auto portfolio · Human review only")
if view in {"Leakage Risk Intelligence", "Intervention Queue"}:
    filtered = scores() if cover == "All coverages" else scores().query("coverage == @cover")
    (risk if view == "Leakage Risk Intelligence" else queue)(filtered)
elif view == "Intervention Simulator":
    simulator(cover)
else:
    {"Executive Overview":executive,"Claims Diagnostics":diagnostics,"Vendor Intelligence":vendors,
     "Adjuster Operations":adjusters,"Model Governance":governance}[view]()
