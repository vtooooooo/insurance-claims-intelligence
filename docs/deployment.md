# Deployment

The application supports Python 3.12. It uses the committed, checksummed `deployment/snapshot` artifacts and needs no external database, model training, credentials or local synthetic data. The compact claim-level dataset is the Q1 2024 slice of the original holdout predictions. Full ledger summaries and model evaluation metrics still come from the 120,000-claim run. The application is designed as a synthetic portfolio demonstration and the evaluation fixture is included for replay only.

For Streamlit Community Cloud, select this GitHub repository and the branch containing the reviewed changes. Set the main file to `app/Home.py` and choose Python 3.12 in advanced settings. Community Cloud installs the root requirements. The system package list supplies OpenMP for the LightGBM wheel. Confirm the app shows the seven other navigation views from Executive Overview and that a zero-capacity scenario returns zero reviews. Local and clean-export tests support readiness. A public instance requires a separate authorized deployment.

To run locally from a fresh checkout:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m scripts.verify_snapshot
python -m streamlit run app/Home.py
```

The application snapshot includes tabular SQL results, model evaluation metadata, frozen claim scores, a separate minimal evaluation fixture, scenario outputs and a SHA-256 manifest. It carries no fitted model pickle. Full training and reproducible scoring live in the pipeline. The UI serves a fixed replay, with controls for queue constraints and scenario response.
