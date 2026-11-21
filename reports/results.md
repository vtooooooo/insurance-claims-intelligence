# Measured results

The seed-27 release generates 120,000 claims from 2021-01-01 through 2024-12-31. The compact replay retains 6,936 scored claims from Q1 2024. The risk and amount evaluation uses all 29,135 eligible holdout claims. The generated integrity checks report 0 violations across 11 cross-row checks.

## Risk and amount performance

| Risk candidate | Validation AP (raw) | Validation AP (calibrated) | Test AP (calibrated) |
| --- | --- | --- | --- |
| Operational rules | 0.0940 | 0.0928 | 0.0877 |
| Logistic regression | 0.1218 | 0.1138 | 0.1026 |
| Random forest | 0.1138 | 0.1068 | 0.0992 |
| LightGBM depth 2 | 0.1173 | 0.1109 | 0.1001 |
| LightGBM depth 4 | 0.1135 | 0.1069 | 0.0969 |

**Selected risk model** · Logistic regression. Test prevalence 7.06%. AP 0.1026 with 95% month-block bootstrap interval [0.0893, 0.1167]. ROC AUC 0.6208. Brier 0.0649. At the frozen cutoff 0.1044, precision was 13.78% and recall was 13.51%, with 25,339 true negatives, 1,739 false positives, 1,779 false negatives and 278 true positives. At a separate 10% review quota, precision was 13.29% and recall 18.81%, identifying $226,274.63 of synthetic actionable exposure before review costs or recoverability.

| Conditional amount candidate | Validation MAE | Validation RMSE |
| --- | --- | --- |
| Severity mean | $264.62 | $388.13 |
| Random forest | $191.59 | $306.14 |
| LightGBM | $191.27 | $302.68 |

**Selected conditional amount model** · LightGBM. Holdout conditional MAE was $199.16 and RMSE was $316.10. The validation-based 90% interval covered 90.57% of holdout actionable outcomes. All-claim MAE of probability × conditional amount was $63.16.

| Prediction quarter | Claims | Prevalence | AP | Brier |
| --- | --- | --- | --- | --- |
| 2024Q1 | 6,936 | 6.95% | 0.0972 | 0.0642 |
| 2024Q2 | 6,896 | 6.71% | 0.0944 | 0.0621 |
| 2024Q3 | 8,146 | 8.03% | 0.1252 | 0.0725 |
| 2024Q4 | 6,931 | 6.41% | 0.0846 | 0.0597 |
| 2025Q1 | 226 | 6.19% | 0.0899 | 0.0583 |

## Matched intervention replays

Mean normal-scenario results across seeds 11, 27 and 53. Net subtracts both expense and modeled delay cost. Gross includes simulated prevented and recovered amounts. Added delay is summed across discretionary reviews.

| Strategy | Reviews | Actionable cases | Gross | Review expense | Net | Worst net | Added hours |
| --- | --- | --- | --- | --- | --- | --- | --- |
| No additional review | 0.0 | 0.0 | $0.00 | $0.00 | $0.00 | $0.00 | 0.0 |
| Random review | 364.0 | 24.3 | $278.58 | $9,117.07 | -$9,721.21 | -$10,383.10 | 73.6 |
| Highest amount | 364.0 | 34.3 | $3,780.61 | $8,902.73 | -$5,992.36 | -$6,754.38 | 72.5 |
| Operational rules | 364.0 | 36.3 | $1,457.86 | $4,864.47 | -$4,019.09 | -$4,170.76 | 51.0 |
| Highest risk | 364.0 | 38.7 | $2,161.07 | $5,424.87 | -$3,906.51 | -$4,561.32 | 53.6 |
| Expected net benefit | 30.7 | 2.0 | $0.00 | $407.87 | -$459.39 | -$539.28 | 4.3 |

Expected-net-benefit policy sensitivity, in dollars per Q1 replay:

| Scenario | Mean net | Sample SD | Worst replay |
| --- | --- | --- | --- |
| Delayed documentation | -$461.11 | $114.83 | -$590.45 |
| High claim volume | $25.28 | $1,203.65 | -$778.96 |
| Higher investigation costs | -$65.99 | $43.20 | -$113.12 |
| Higher leakage prevalence | -$226.47 | $502.93 | -$524.30 |
| Limited adjuster capacity | -$379.49 | $60.54 | -$449.40 |
| Lower effectiveness | $0.00 | $0.00 | $0.00 |
| Normal | -$459.39 | $69.19 | -$539.28 |
| Vendor price inflation | -$650.58 | $417.03 | -$898.80 |

The raw file contains all six policies for all eight scenarios and three seeds. It includes false-positive reviews, missed cases, true avoidable amounts identified, separate prevention and recovery, net benefit per hour and maximum modeled delay.

[Critical review](critical-validation.md) · [Raw scenario runs](../deployment/snapshot/scenarios.csv) · [Model audit](../deployment/snapshot/model.json)
