"""Paired synthetic counterfactuals. Evaluation outcomes never enter the queue."""
import numpy as np
import pandas as pd

from src.decision import MISMATCH_RESPONSE, RECOVERABLE_FRACTION, STRATEGIES, options, prioritize


def population(scores, labels, scenario, seed):
    rng = np.random.default_rng(seed)
    paired = scores.merge(labels, on="claim_id", validate="one_to_one")
    size = max(1, round(len(paired)*scenario.volume))
    baseline = paired.actionable.mean()
    target = np.clip(baseline*scenario.prevalence, 0, .95)
    if 0 < baseline < 1:
        weights = np.where(paired.actionable, target/baseline, (1-target)/(1-baseline))
    else:
        weights = np.ones(len(paired))
    # Resampling allows multiple synthetic copies of a template, each with separate review ID.
    cohort = paired.iloc[rng.choice(len(paired), size, p=weights/weights.sum())].reset_index(drop=True)
    cohort["claim_id"] = np.arange(1,size+1)
    cohort["response_draw"] = rng.random(size)
    if scenario.documentation_delay:
        mask = rng.random(size) < min(.8, .25*scenario.documentation_delay)
        newly_missing = mask & cohort.documented.gt(0)
        cohort.loc[newly_missing, "documented"] = 0
        cohort.loc[newly_missing, "rule"] += 2
    return cohort


def simulate(scores, labels, scenario, seeds=(11, 27, 53)):
    output = []
    for seed in seeds:
        cohort = population(scores, labels, scenario, seed)
        live = cohort[scores.columns]
        alternatives = options(live, scenario)
        for strategy in STRATEGIES:
            queue = prioritize(live, scenario, strategy, seed, alternatives)
            outcomes = queue.merge(cohort[["claim_id","actionable","avoidable_cents","mechanism",
                                           "effectiveness","response_draw"]], on="claim_id")
            detected = outcomes.actionable
            matching = outcomes.action.eq(outcomes.mechanism)
            response = (outcomes.assumed_success * outcomes.effectiveness *
                        np.where(matching,1,MISMATCH_RESPONSE)).clip(0,1)
            improved = detected & outcomes.response_draw.lt(response)
            exposure = outcomes.avoidable_cents / 100 * scenario.inflation
            intercepted = np.where(improved, exposure * RECOVERABLE_FRACTION, 0)
            recovered = float(intercepted[outcomes.mechanism.eq("subrogation")].sum())
            prevented = float(intercepted.sum() - recovered)
            gross = prevented+recovered
            costs, harm = outcomes.cost.sum(), outcomes.harm.sum()
            net = gross-costs-harm
            hours = outcomes.hours.sum()
            output.append(dict(seed=seed,strategy=strategy,claims=len(cohort),reviewed=len(queue),
                               actionable_detected=int(detected.sum()),false_positive=int((~detected).sum()),
                               missed=int(cohort.actionable.sum()-detected.sum()),
                               avoidable_identified=float(exposure[detected].sum()),
                               prevented=prevented,recovered=recovered,gross=gross,
                               review_expense=costs,operational_harm=harm,net=net,
                               review_hours=hours,delay_hours=outcomes.delay_hours.sum(),
                               max_claim_delay=outcomes.delay_hours.max() if len(queue) else 0.,
                               net_per_hour=net/hours if hours else 0.))
    return pd.DataFrame(output)


def summarize(results):
    return results.groupby("strategy",sort=False).agg(
        reviewed=("reviewed","mean"), detected=("actionable_detected","mean"),
        gross=("gross","mean"), expense=("review_expense","mean"),
        net=("net","mean"), net_sd=("net","std"), downside=("net","min"),
        hours=("review_hours","mean"), delay=("delay_hours","mean"))
