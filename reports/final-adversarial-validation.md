# Final adversarial validation

Audit baseline was pushed commit `808943e` on `feature/claims-intelligence`. The review used the existing pipeline, a clean remote checkout, separate calculations on the synthetic ledger and replay inputs, and targeted regression fixes. Published results refer to the original seed-27 release and the frozen Q1 2024 replay.

## Verdict

**Go for portfolio demonstration and manual merge review. No-go for real-world operational adoption.** The modeling and financial arithmetic reproduce. Normal-scenario intervention loses money under both the published draws and an audit that integrates out the response draws. The small high-volume gain is too unstable for a savings claim. Production adoption would require independently sourced outcomes and as-of feature histories, local review cost estimates, protected service timelines, and a prospective evaluation of intervention effects and review burden.

## Data, temporal design, and model

| Check | Observed result |
| --- | --- |
| Ledger and SQL | Regenerated 120,000 claims, 115,131 eligible checkpoints, 11 integrity checks with zero violations, and 19 SQL result tables. Paid loss reconciled to $316,249,728.37. One posted claim exceeded its policy limit due to a deliberately duplicated payment. Legitimate paid loss is capped by the generator. |
| Maturity and chronology | Independent SQL used correlated timestamp lookups for events and last reserve. Train, calibration, validation and holdout contained 52,548, 6,932, 12,840 and 29,135 rows. Strict maturity excluded 4,590, 4,408 and 4,678 rows from the first three windows, and none from the holdout. This can underrepresent slower cases in earlier windows. |
| Point-in-time and vendor audit | The feature allowlist excludes payments, claim IDs, state, team, eventual duration, labels and final reserve. Post-checkpoint event and reserve mutations leave features unchanged. Exact-cutoff events are included. Vendor days and supplement rates are exogenous static inputs sampled before outcomes, with no settlement-derived rollup. In production, vendor assignments and histories and other static fields would require effective timestamps. |
| Model selection | The selector reads uncalibrated validation AP, then applies the predeclared 0.002 simpler-candidate tolerance. Logistic scored 0.121798, above the next candidate, depth-2 LightGBM at 0.1173. Isotonic calibration used a separate earlier window. The conditional amount selector uses validation RMSE. A holdout-label and amount mutation regression verifies that model choice, threshold, validation results and individual scores remain unchanged. |
| Independent scoring | Separate SQL, manually standardized inputs and freshly fitted logistic, isotonic and LightGBM estimators reproduced all 6,936 deployment scores and conditional amounts. The audit computed AP by probability-tie groups and applied the 10% review cutoff with claim-order tie handling. |
| Synthetic shortcuts | Early event count is exactly 3 plus the documentation flag for all 115,131 eligible rows, and reserve and estimate correlate at 0.999755. Observed documentation, workload, complexity, and liability also directly influence the data-generating risk equation, favoring a low-dimensional model. Estimate and true avoidable amount have Spearman correlation 0.824 on actionable holdout claims because both depend on latent underlying cost. |
| Synthetic difficulty | Outcome noise, unobserved mechanisms and uncertain feasibility limit ranking. Actionable prevalence is 8.89% without documentation and 6.15% with it. The generator omits independent policy, geography, claim behavior and timing effects that could add signal or confounding. The net direction of realism bias is unknown. |

| Holdout measure | Independently recalculated |
| --- | ---: |
| Actionable prevalence | 2,057 / 29,135 = 7.0602% |
| Average precision | 0.102558 |
| ROC AUC | 0.620807 |
| Precision at 10% | 387 / 2,913 = 13.2853% |
| Recall at 10% | 387 / 2,057 = 18.8138% |
| Conditional amount MAE | $199.1611 |
| Non-actionable high-estimate / other flag rates | 9.9422% / 6.0217%, gap 3.9204 percentage points |
| Zero-avoidable-cost high-estimate / other flag rates | 9.5238% / 5.7411%, gap 3.7827 percentage points |

The last two rows use the frozen calibrated threshold 0.104405 and the training estimate 90th percentile $6,451.274. The 541 non-actionable holdout claims with positive modeled avoidable cost demonstrate why the two populations must be named separately. The highest populated calibration bin predicts 22.23% against 16.61% observed, which matters for a policy driven by tail exposure. The AP lift is modest and the synthetic disparity is evidence of review burden within this generator.

## Financial and policy audit

An independent reconstruction sampled the matched populations and shared response uniforms from the committed replay inputs. It generated eligible actions using the published rates and verified actual queue outputs against independent ranking and feasibility checks. For the expected-value policy, it exhaustively enumerated feasible positive-action subsets each day and matched the solver objective. For each assigned action it independently computed labor expense, delay at $12 per added hour, prevention, recovery and net. All monetary amounts and counts matched across **144 committed scenario/seed/strategy rows**. Additional capacity-only and delay-only checks isolated those controls.

| Normal scenario, mean over seeds 11, 27 and 53 | Review expense | Delay charge | Prevented | Recovered | Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| No additional review | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 |
| Random review | $9,117.07 | $882.72 | $278.58 | $0.00 | −$9,721.21 |
| Highest amount | $8,902.73 | $870.24 | $3,780.61 | $0.00 | −$5,992.36 |
| Operational rules | $4,864.47 | $612.48 | $1,279.36 | $178.51 | −$4,019.09 |
| Highest risk | $5,424.87 | $642.72 | $2,039.59 | $121.49 | −$3,906.51 |
| Expected net benefit | $407.87 | $51.52 | $0.00 | $0.00 | −$459.39 |

Figures use unrounded inputs before computing net. The no-review baseline is incremental to routine claim handling, which continues outside the simulation. The expected-net policy projected +$181.72 on average when selecting the queue. It reviewed about 31 claims per replay, of which only two on average were actionable, and averaged 0.33 exact mechanism matches. None of the chosen normal reviews realized interception under the three published draws. Integrating the simulator's success probabilities over the realized actionable labels, known mechanisms and response heterogeneity gives a normal conditional expected net of **−$128.45**. The gap between planned and realized value reflects prediction and mechanism-match error, small replay samples, and response noise. It persists in expectation across those sampled queues. No arithmetic error explains it. Response costs and benefits remain hypothetical, and action mapping differs between the ranking baselines and the optimizer.

| Expected-net policy sensitivity | Mean realized net | Conditional expected net |
| --- | ---: | ---: |
| Normal | −$459.39 | −$128.45 |
| 1.7× prevalence | −$226.47 | +$179.10 |
| 0.35× effectiveness | $0.00 | $0.00 |
| 2× investigation costs | −$65.99 | −$65.99 |
| Two-review capacity only | −$379.49 | −$99.99 |
| Higher delay rate only | −$438.62 | −$243.72 |
| Delayed documents and higher delay rate | −$461.11 | −$266.21 |
| Vendor inflation | −$650.58 | −$285.19 |
| High volume | +$25.28 | −$29.65 |

High-volume replays produced **−$778.96, −$554.26 and +$1,409.07**. Only seed 53 intercepted any cost, recording $2,068.19 of prevention in that draw. The positive mean depends on that replay, and even the response-integrated mean remains negative. The experiment repeats templates, uses only three seeds, and holds scores fixed under shocks. The documentation screen and scenario change routing and costs while leaving frozen risk estimates in place.

## Defects corrected

- Corrected false-positive cohort terminology and exposed the corresponding zero-avoidable-cost audit. The original ranking and financial outcomes stand.
- Rounded two SQL case-mix residuals to eight decimal places to remove floating-point accumulation noise from generated hashes. Removed notebook execution timestamps from executed files.
- Strengthened snapshot verification. The prior verifier accepted a fully removed scenario or duplicate row after rehashing, skipped manifest membership checks, and could accept a fabricated delay charge with consistent net. The verifier now requires the full scenario × seed × policy matrix, complete manifest, aligned populations and accounting identities. Regression tests introduce each defect explicitly.
- Prevented an inner replay join from silently dropping scored claims that lack an evaluation outcome. Filters can still use a subset of the full evaluation fixture.
- Bounded custom simulator result caching, added a three-draw caveat alongside downside, pinned the directly used SciPy and Parquet dependencies, and added verification of the committed snapshot to CI.

## Application, reproduction, and deployment

- A clean remote checkout at `808943e` passed the original nine tests under Python 3.12.14. The full pipeline and all five notebooks executed there. Model and scenario results reproduced. That run exposed the two SQL hash differences and timestamp-only notebook churn described above.
- A clean export of the corrected tree used a new virtual environment installed from the checked-in requirements. Dependency checks, committed snapshot verification and the Streamlit HTTP smoke test passed. A fresh 120,000-claim build reproduced the corrected snapshot and all five executed notebooks byte-for-byte on that environment. A separate 5,000-claim CI-style build passed verification with 297 replay claims and 144 policy rows. Cross-platform byte identity and indefinite dependency resolution remain outside this check.
- The corrected suite passed all 15 tests. The small holdout-mutation fixture emitted scikit-learn feature-name warnings in the LightGBM permutation-importance path, where the fitted preprocessing pipeline supplies the feature array.
- Chromium rendered all eight views. Six browser downloads were checked against their expected filenames and contents. Diagnostics, risk, vendor, adjuster and default simulation exports matched the committed source tables. The default date's queue downloaded a valid empty export. A separate widget run checked a nonempty date, zero budget, zero staff hours, the coverage and specialization filters, and the output after setting all 11 simulator controls against a direct run on the corresponding scored subset.
- GitHub Actions specifies Python 3.12, a read-only job token, dependency setup, committed snapshot checks, the test suite, a reduced pipeline build and an HTTP smoke test. Those commands were exercised locally. Hosted Actions status and Streamlit Community Cloud provisioning were outside the verified runs.
- Tracked content is about 1 MB, including a roughly 0.55 MB snapshot. The largest blob is the scored Parquet file at about 350 KB. Generated ledgers and local environments are excluded. The app reads the committed tables, requires no credentials or external services, and has a root requirements file plus a declared OpenMP system package. It is ready for a manual Streamlit Community Cloud trial using `app/Home.py` with Python 3.12.
- The README, methodology, case study, deployment guide and analytical reports were reviewed for wording that could imply operational proof, public deployment, or real insurer savings. The release uses the stronger evidence qualifiers above. Older recorded development results remain labeled as exploratory.

From the repository root in a clean Python 3.12 environment:

```bash
python -m pip install -r requirements-dev.txt
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
python -m scripts.verify_snapshot
python -m scripts.pipeline --claims 120000 --seed 27
python -m scripts.notebooks
python -m scripts.report
python -m pytest -q
bash scripts/streamlit_smoke.sh
python -m scripts.pipeline --claims 5000 --db data/ci.duckdb --output data/ci-snapshot
python -m scripts.verify_snapshot data/ci-snapshot
```

[Model results](results.md) · [Prior critical review](critical-validation.md) · [Deployment instructions](../docs/deployment.md)
