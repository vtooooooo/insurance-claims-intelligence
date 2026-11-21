# Critical validation

## Portfolio decision

**Go for a synthetic portfolio demonstration. No-go for operational deployment or a savings claim.** The model adds modest ranking signal in this simulation. The main scenario does not justify additional discretionary reviews, even with the optimizer. A dashboard recommendation is a modeled candidate for human review, and the overall policy can still be economically unfavorable.

| Challenge | Test and result |
| --- | --- |
| Artificially easy labels | Rules test AP was 0.0877 and logistic test AP was 0.1026 at 7.06% prevalence. The classifier misses most actionable cases at practical review capacity. Generator relationships remain simpler than real claims. |
| Feature leakage | Mutating every future event detail, future reserve and all payments leaves the feature matrix unchanged. A documentation event exactly at 72 hours enters the feature matrix. Excluded fast closures are absent. The scored snapshot shares only claim ID with the replay truth file. |
| Maturity and tuning | Training, calibration and model-selection labels mature strictly before their respective cutoffs. Thresholds and model choices are made before test scoring. Calibration plateaus motivated a conservative tied-score cutoff that stays within the validation flag cap. Claims with slower-to-mature outcomes can be underrepresented near cutoffs. |
| Strong baselines | Raw validation AP was 0.1218 for logistic and 0.0940 for rules. Forest and shallow LightGBM did not beat logistic validation AP. Test AP declined for the selected model. At a 10% review budget, its recall was 18.81%. |
| Temporal generalization and calibration | Complete-quarter held-out AP ranged from 0.0846 to 0.1252. The highest populated probability bin averaged 22.23% estimated risk against 16.61% observed. Its 566 claims show how overconfidence can inflate review value. |
| Non-actionable claims with high estimates | 9.94% of non-actionable cases in the high-estimate band were flagged, versus 6.02% of other non-actionable cases. The high band uses the training 90th percentile initial estimate. Among claims with zero avoidable cost, the rates were 9.52% and 5.74%. This non-actionable disparity can increase review burden in complex files and should be monitored. |
| Vendor case mix | Raw cross-vendor SD of mean paid was $1,421.40. Adjusting for coverage, severity and repair complexity reduced residual SD to $53.61. Site differences cannot identify causal effects or misconduct. |
| Response optimism | The first development replay revealed that action scoring implicitly assumed perfect action matching and full realized share. The revised expected-benefit formula includes a 20% matching prior, a mismatch penalty, latent response variation in expectation and a 72% recoverable share. This was an exploratory policy correction after the initial replay, so the primary financial run is not an untouched confirmation of that policy. |
| Review expenses and capacity | In the final normal replay the optimizer averaged 30.7 reviews, 2.0 actionable detections, $0 gross intercepted and −$459.39 net. No discretionary review returned $0. Constrained resources are enforced per day by the optimizer. A regression fixture verifies that the solver exceeds greedy value when the budget binds. |
| Downside, shifts and seeds | The normal policy lost money in all three matched replays. High volume averaged +$25.28 with worst −$778.96. Lower efficacy produced no optimizer reviews. Higher costs produced −$65.99 mean net. A separate 5,000-claim, seed-81 rerun selected forest, reached AP 0.0836 at 6.74% prevalence and selected no normal-scenario expected-value reviews across the three replay seeds. That smaller rerun tests the pipeline under a different generator sample and retrains the model. |
| Safeguards | Same-day admission requires budget, count, staff time and specialist time. High-urgency claims require shorter permissible delays. Maximum modeled per-claim delay across the release's replays was 0.5525 hours. The simulator does not model real complaint rates, actual queueing spillover or legal review deadlines. |
| Reconciliation and reproducibility | The full ledger reports zero violations in 11 cross-row checks. Net paid reconciles to the cent. The replay reconciles prevention plus recovery to gross, and gross less review and delay expense to net. The artifact verifier checks 144 policy runs and snapshot digests. |

## Corrections and remaining uncertainty

The amount model now estimates a conditional mean selected on RMSE so that probability × amount has the intended expectation interpretation. Isotonic ties are handled separately from top-K. The scenario sliders now coerce preset values to Streamlit's expected numeric types. Solver and app tests cover abstention, resource exhaustion, action eligibility, zero review capacity and fixed-slider scenario changes.

The compact replay spans one quarter and starts from predictions made on that period's observed synthetic fields. In the documentation shock, action eligibility changes while the prediction remains frozen. Case-mix residuals use only observed synthetic covariates. The simulation assumes mechanism-match effects, and three seeds provide limited resolution for rare recoveries. Claims that appear promising under favorable inputs merit a measured human process trial before any operational adoption.

[Measured tables](results.md) · [SQL findings](sql-findings.md) · [Release replay CSV](../deployment/snapshot/scenarios.csv)
