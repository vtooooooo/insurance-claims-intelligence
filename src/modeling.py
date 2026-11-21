"""Temporal training, calibration, and frozen-policy out-of-time evaluation."""
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             mean_absolute_error, root_mean_squared_error, precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = ["severity", "complexity", "estimate", "reserve", "report_delay", "workload",
           "documented", "early_events", "liability", "vendor_days", "vendor_supp"]
FEATURES = NUMERIC + ["coverage"]
QUOTA = .10
TRAIN_END = pd.Timestamp("2023-01-01")
CAL_END = pd.Timestamp("2023-06-01")
TEST_START = pd.Timestamp("2024-01-01")
LABEL_FREEZE = pd.Timestamp("2025-06-01")


def temporal_frames(features, truth):
    data = features.merge(truth, on="claim_id", validate="one_to_one")
    time, mature = data.checkpoint, data.mature_at
    return {
        "train": data[(time < TRAIN_END) & (mature < TRAIN_END)],
        "calibration": data[(time >= TRAIN_END) & (time < CAL_END) & (mature < CAL_END)],
        "validation": data[(time >= CAL_END) & (time < TEST_START) & (mature < TEST_START)],
        "test": data[(time >= TEST_START) & (mature < LABEL_FREEZE)],
    }


def preprocess():
    return ColumnTransformer([("scaled", StandardScaler(), NUMERIC),
                              ("coverage", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["coverage"])])


def operational_rule(frame):
    return (2 * (frame.documented == 0) + (frame.report_delay >= 4) +
            (frame.workload >= 35) + frame.liability).to_numpy()


def at_capacity(frame, score):
    k = max(1, int(len(frame) * QUOTA))
    order = np.argsort(-np.asarray(score), kind="stable")[:k]
    reviewed = frame.iloc[order]
    detected = reviewed.actionable.sum()
    return dict(precision_at_k=detected/k, recall_at_k=detected/max(1, frame.actionable.sum()),
                dollars_at_k=reviewed.loc[reviewed.actionable, "avoidable_cents"].sum()/100)


def capacity_threshold(scores):
    """Choose the lowest calibrated cutoff that fits the validation flag rate."""
    levels, counts = np.unique(scores, return_counts=True)
    feasible = np.flatnonzero(np.cumsum(counts[::-1]) <= int(len(scores) * QUOTA))
    return float(levels[::-1][feasible[-1]]) if len(feasible) else float(np.nextafter(1., np.inf))


def metrics(frame, scores, threshold):
    y = frame.actionable.to_numpy()
    predicted = scores >= threshold
    return dict(ap=average_precision_score(y, scores),
                roc_auc=roc_auc_score(y, scores) if len(np.unique(y)) == 2 else None,
                brier=brier_score_loss(y, scores),
                precision=precision_score(y, predicted, zero_division=0),
                recall=recall_score(y, predicted, zero_division=0),
                confusion=confusion_matrix(y, predicted, labels=[False, True]).tolist(),
                **at_capacity(frame, scores))


def bootstrap_ap(frame, scores, seed):
    months = frame.checkpoint.dt.to_period("M").to_numpy()
    blocks = [np.flatnonzero(months == month) for month in np.unique(months)]
    rng = np.random.default_rng(seed)
    y = frame.actionable.to_numpy()
    values = []
    for draw in rng.integers(len(blocks), size=(200, len(blocks))):
        rows = np.concatenate([blocks[i] for i in draw])
        values.append(average_precision_score(y[rows], scores[rows]))
    return np.quantile(values, [.025, .975]).tolist()


def fit(features, truth, seed):
    parts = temporal_frames(features, truth)
    train, cal, val, test = (parts[x] for x in ("train", "calibration", "validation", "test"))
    estimators = {
        "Logistic regression": LogisticRegression(max_iter=800, C=.2),
        "Random forest": RandomForestClassifier(n_estimators=90,max_depth=7,min_samples_leaf=30,
                                                n_jobs=2,random_state=seed),
        "LightGBM depth 2": LGBMClassifier(n_estimators=100,max_depth=2,num_leaves=4,verbosity=-1,
                                         n_jobs=2,random_state=seed),
        "LightGBM depth 4": LGBMClassifier(n_estimators=140,max_depth=4,num_leaves=12,verbosity=-1,
                                         n_jobs=2,random_state=seed),
    }
    candidates = {}
    comparison = []
    for name, estimator in {"Operational rules": None, **estimators}.items():
        if estimator is not None:
            estimator = make_pipeline(preprocess(), estimator).fit(train[FEATURES], train.actionable)
        cal_raw = raw(estimator, cal)
        val_raw = raw(estimator, val)
        calibration = IsotonicRegression(out_of_bounds="clip").fit(cal_raw, cal.actionable)
        val_scores = calibration.predict(val_raw)
        threshold = capacity_threshold(val_scores)
        comparison.append(dict(model=name, selection_ap=average_precision_score(val.actionable,val_raw),
                               **metrics(val,val_scores,threshold)))
        candidates[name] = estimator, calibration, threshold

    # Use unbinned AP for selection; prefer simpler models within 0.002 AP.
    top_ap = max(row["selection_ap"] for row in comparison)
    selected = next(row["model"] for row in comparison if row["selection_ap"] >= top_ap - .002)
    estimator, calibration, threshold = candidates[selected]
    positive_train, positive_val = train[train.actionable], val[val.actionable]
    regressors = {
        "Severity mean": None,
        "Random forest": RandomForestRegressor(n_estimators=80,max_depth=6,min_samples_leaf=20,
                                               n_jobs=2,random_state=seed),
        "LightGBM": LGBMRegressor(n_estimators=90,max_depth=3,num_leaves=7,n_jobs=2,
                                 random_state=seed,verbosity=-1,objective="regression"),
    }
    mean = positive_train.groupby("severity").avoidable_cents.mean() / 100
    global_mean = positive_train.avoidable_cents.mean() / 100

    def amount_predict(model, data):
        if model is None:
            return data.severity.map(mean).fillna(global_mean).to_numpy()
        if hasattr(model[-1], "booster_"):
            return model[-1].booster_.predict(model[0].transform(data[FEATURES]), num_threads=2).clip(0)
        return model.predict(data[FEATURES]).clip(0)

    amount_validation = []
    for name, model in regressors.items():
        if model is not None:
            model = make_pipeline(preprocess(), model).fit(positive_train[FEATURES],positive_train.avoidable_cents/100)
            regressors[name] = model
        target = positive_val.avoidable_cents / 100
        pred = amount_predict(model, positive_val)
        amount_validation.append(dict(model=name, mae=mean_absolute_error(target,pred),
                                      rmse=root_mean_squared_error(target,pred)))
    best_amount = min(amount_validation, key=lambda row: row["rmse"])["model"]
    amount_model = regressors[best_amount]

    # All candidate, threshold and amount selection precede test scoring.
    scores = calibration.predict(raw(estimator, test))
    amounts = amount_predict(amount_model, test)
    test_final = metrics(test, scores, threshold)
    actionable = test.actionable.to_numpy()
    test_final["ap_month_block_ci"] = bootstrap_ap(test, scores, seed)
    test_final["conditional_mae"] = mean_absolute_error(test.avoidable_cents[actionable]/100, amounts[actionable])
    test_final["conditional_rmse"] = root_mean_squared_error(test.avoidable_cents[actionable]/100, amounts[actionable])
    interval_radius = float(np.quantile(abs(positive_val.avoidable_cents/100 - amount_predict(amount_model,positive_val)), .9))
    test_final["conditional_interval_coverage"] = float(np.mean(abs(test.avoidable_cents[actionable]/100 - amounts[actionable]) <= interval_radius))
    test_final["unconditional_mae"] = mean_absolute_error(np.where(actionable,test.avoidable_cents/100,0), scores*amounts)
    expensive = (~actionable) & (test.estimate >= train.estimate.quantile(.9))
    test_final["high_estimate_legitimate_flag_rate"] = float(np.mean(scores[expensive] >= threshold))
    test_final["other_legitimate_flag_rate"] = float(np.mean(scores[~actionable & ~expensive] >= threshold))
    test_baselines = {}
    for name, (candidate, calibrator, cutoff) in candidates.items():
        test_baselines[name] = metrics(test, calibrator.predict(raw(candidate,test)), cutoff)
    segment_rows = []
    for dimension, grouping in {"Coverage": test.coverage, "Quarter": test.checkpoint.dt.to_period("Q"),
                                 "State (audit)": test.state}.items():
        for group, indices in grouping.groupby(grouping).indices.items():
            part = test.iloc[indices]
            if part.actionable.any():
                segment_rows.append(dict(dimension=dimension,group=str(group),n=len(part),
                                         prevalence=part.actionable.mean(), **metrics(part,scores[indices],threshold)))
    reliability = (pd.DataFrame({"prediction": scores,"observed": actionable})
                   .assign(bin=np.minimum((scores*10).astype(int),9)).groupby("bin")
                   .agg(mean_score=("prediction","mean"),actual_rate=("observed","mean"),n=("observed","size")))
    if estimator is None:
        importance = pd.Series(dtype=float)
    else:
        values = permutation_importance(estimator,val[FEATURES],val.actionable,scoring="average_precision",
                                        n_repeats=4,random_state=seed)
        importance = pd.Series(values.importances_mean,index=FEATURES).sort_values(ascending=False)

    scored = test[["claim_id","checkpoint","coverage","severity","complexity","estimate","workload",
                   "documented","report_delay","liability","team"]].copy()
    scored["risk"] = scores
    scored["conditional_amount"] = amounts
    scored["conditional_low"] = np.maximum(0,amounts-interval_radius)
    scored["conditional_high"] = amounts+interval_radius
    scored["expected_exposure"] = scores * amounts
    scored["rule"] = operational_rule(test)
    scored["risk_category"] = np.where(scores >= threshold, "Elevated", "Standard")
    scored["reason"] = local_reasons(estimator, calibration, test, train, scores)
    report = dict(selected=selected, amount_model=best_amount, threshold=threshold,
                  sample_sizes={name: len(part) for name, part in parts.items()},
                  test_prevalence=float(actionable.mean()), validation=comparison,
                  amount_validation=amount_validation, test=test_final,test_baselines=test_baselines,
                  segments=segment_rows, reliability=reliability.reset_index().to_dict("records"),
                  importance=importance.rename("ap_drop").rename_axis("feature").reset_index().to_dict("records"))
    return scored, report


def raw(estimator, frame):
    if estimator is None:
        return operational_rule(frame)
    transformed = estimator[0].transform(frame[FEATURES])
    predictor = estimator[-1]
    if hasattr(predictor, "booster_"):
        return predictor.booster_.predict(transformed, num_threads=2)
    return predictor.predict_proba(transformed)[:,1]


def local_reasons(estimator, calibration, test, train, scores):
    reference = train[NUMERIC].median()
    reference["coverage"] = train.coverage.mode().iloc[0]
    contributions = []
    for feature in FEATURES:
        changed = test[FEATURES].assign(**{feature: reference[feature]})
        contributions.append(scores - calibration.predict(raw(estimator, changed)))
    matrix = np.column_stack(contributions)
    index = matrix.argmax(axis=1)
    strongest = matrix.max(axis=1)
    return np.where(strongest > 1e-5, np.asarray(FEATURES)[index], "No positive single-feature shift")
