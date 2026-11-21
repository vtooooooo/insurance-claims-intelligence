"""Same-day, capacity-constrained human review. All dollar rates are assumptions."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, vstack


@dataclass(frozen=True)
class Scenario:
    capacity: int = 4
    staff_hours: float = 3
    specialist_hours: float = 1.25
    budget: float = 140
    volume: float = 1.
    inflation: float = 1.
    prevalence: float = 1.
    effectiveness: float = 1.
    cost_scale: float = 1.
    documentation_delay: int = 0
    delay_per_hour: float = .4


# (review hours, rate, modeled fraction recovered given actionable, specialist)
ACTIONS = {
    "documentation": (.35, 38, .47, False),
    "repair estimate": (.65, 54, .48, False),
    "duplicate payment": (.35, 42, .30, False),
    "vendor billing": (.75, 55, .47, False),
    "subrogation": (.65, 62, .56, True),
    "specialist escalation": (1., 70, .55, True),
}
MATCH_PRIOR = .20
MISMATCH_RESPONSE = .25
MEAN_EFFECTIVENESS = 5 / 8
RECOVERABLE_FRACTION = .72

STRATEGIES = ("No additional review", "Random review", "Highest amount", "Operational rules",
              "Highest risk", "Expected net benefit")


def options(frame, scenario):
    """Generate alternatives from checkpoint fields. Risk and conditional amount stay frozen."""
    coverage_shift = frame.coverage.ne("Property liability")
    eligible = {
        "documentation": frame.documented.eq(0),
        "repair estimate": coverage_shift,
        "duplicate payment": frame.workload.ge(30),
        "vendor billing": coverage_shift & frame.complexity.ge(3),
        "subrogation": frame.liability.eq(1),
        "specialist escalation": frame.severity.ge(4),
    }
    alternatives = []
    for action, (hours, rate, success, specialist) in ACTIONS.items():
        items = frame.loc[eligible[action]].copy()
        items["review_date"] = items.checkpoint.dt.normalize()
        items["action"] = action
        items["hours"] = hours
        items["specialist"] = specialist
        items["cost"] = hours * rate * scenario.cost_scale
        items["delay_hours"] = hours * scenario.delay_per_hour
        items["harm"] = items.delay_hours * 12
        items["assumed_success"] = np.clip(success * scenario.effectiveness, 0, 1)
        response_given_actionable = items.assumed_success * MEAN_EFFECTIVENESS * (
            MATCH_PRIOR + (1 - MATCH_PRIOR) * MISMATCH_RESPONSE)
        items["net_benefit"] = (items.expected_exposure * scenario.inflation * response_given_actionable
                                * RECOVERABLE_FRACTION - items.cost - items.harm)
        # Urgent claims are only eligible for brief, concurrent review.
        items["urgent"] = items.severity.ge(5)
        alternatives.append(items.loc[(items.delay_hours <= .75) &
                                      (~items.urgent | (items.delay_hours <= .35))])
    return pd.concat(alternatives, ignore_index=True)


def prioritize(frame, scenario, strategy="Expected net benefit", seed=27, alternatives=None):
    if strategy not in STRATEGIES:
        raise ValueError(strategy)
    choices = options(frame, scenario) if alternatives is None else alternatives
    if strategy == "No additional review":
        return choices.iloc[:0].copy()
    if strategy == "Expected net benefit":
        choices = choices[choices.net_benefit > 0].assign(priority=lambda x: x.net_benefit)
    else:
        # Baselines use the lowest-cost eligible action, fixed before ranking.
        choices = choices.sort_values(["cost", "action"]).drop_duplicates("claim_id").copy()
        if strategy == "Random review":
            choices["priority"] = np.random.default_rng(seed).random(len(choices))
        else:
            column = {"Highest amount": "estimate", "Operational rules": "rule",
                      "Highest risk": "risk"}[strategy]
            choices["priority"] = choices[column]
    choices = choices.sort_values(["review_date", "priority", "urgent", "claim_id", "action"],
                                  ascending=[True,False,False,True,True])
    if strategy == "Expected net benefit":
        selected = [index for _, day in choices.groupby("review_date", sort=False)
                    for index in optimize_day(day, scenario)]
        return choices.loc[selected].copy()
    selected = []
    for _, day in choices.groupby("review_date", sort=False):
        reviewed = set()
        hours, specialists, budget = scenario.staff_hours, scenario.specialist_hours, scenario.budget
        for row in day.itertuples():
            if len(reviewed) >= scenario.capacity:
                break
            if row.claim_id in reviewed or row.hours > hours+1e-8 or row.cost > budget+1e-8:
                continue
            if row.specialist and row.hours > specialists+1e-8:
                continue
            reviewed.add(row.claim_id)
            hours -= row.hours
            budget -= row.cost
            specialists -= row.hours * row.specialist
            selected.append(row.Index)
    return choices.loc[selected].copy()


def optimize_day(day, scenario):
    """Maximize total expected net benefit with binary claim/action assignments."""
    if not scenario.capacity or not scenario.staff_hours or not scenario.budget:
        return []
    n = len(day)
    claim_numbers, claims = pd.factorize(day.claim_id)
    claim_limits = csr_matrix((np.ones(n), (claim_numbers, np.arange(n))), shape=(len(claims), n))
    resources = np.vstack([np.ones(n), day.hours, day.hours * day.specialist, day.cost])
    upper = np.r_[np.ones(len(claims)), scenario.capacity, scenario.staff_hours,
                  scenario.specialist_hours, scenario.budget]
    constraint = LinearConstraint(vstack([claim_limits, csr_matrix(resources)]), 0, upper)
    result = milp(-day.net_benefit.to_numpy(), integrality=np.ones(n),
                  bounds=Bounds(0, 1), constraints=constraint, options={"mip_rel_gap": 0})
    if not result.success:
        raise RuntimeError(f"Review optimization failed: {result.message}")
    return day.index[result.x > .5].tolist()
