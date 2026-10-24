# NISR Big Data Hackathon 2026 - Track 2: VUP targeting gaps

Where do social protection programs (VUP) miss poor households, and who should be prioritized?
Built on the EICV7 2023-24 household survey (NISR).

## Setup (VS Code)

1. Open this folder in VS Code (`File > Open Folder`).
2. Create the environment and install packages:
   ```
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. VS Code: `Ctrl+Shift+P` > "Python: Select Interpreter" > pick `.venv`.
4. Unzip the NISR download so the files sit here:
   - `data/raw/Cross_Section/*.dta`  (EICV7 cross-sectional sample)
   - `data/raw/VUP/*.dta`            (EICV7 VUP sample, optional)

## Run order

```
python src/validate.py      # must pass: reproduces NISR's published district poverty rates
python src/build_table.py   # builds data/processed/hh_table.parquet
python src/build_features.py  # leakage-free model features -> data/processed/features.parquet
python src/reconcile_vup.py   # survey vs MINALOC admin VUP counts -> reports/vup_reconciliation.csv
python src/coverage.py        # coverage & targeting errors by component/district -> reports/coverage_*.csv
python src/model.py           # proxy-targeting model, cluster-grouped CV -> reports/model_*.csv
python src/targeting.py       # same-budget targeting simulation -> reports/targeting_*.csv
streamlit run app/streamlit_app.py   # dashboard (reads reports/ + assets/ only)
python src/inspect_files.py data/raw/Cross_Section   # lists every variable + label
```

## Dashboard

`app/streamlit_app.py` reads only the aggregated CSVs in `reports/` and the district boundaries in
`assets/rwanda_districts.geojson` (geoBoundaries RWA ADM2, source NISR Open Data, CC BY 4.0), so it runs on
Streamlit Community Cloud without any microdata. Deploy: share.streamlit.io > New app > this repo, branch `main`,
main file `app/streamlit_app.py`.

## Rules we follow

- **Never commit microdata.** `.gitignore` excludes `data/`. The hackathon needs a public repo, so only code, aggregated results and documentation go on GitHub. Check NISR's data-use terms before publishing anything derived from household rows.
- **Weights.** Poverty rates use `pop_wt` (person level, matches NISR). Shares of households (e.g. VUP coverage) use `weight`. Use `clust` as the cluster and `district` as the stratum for uncertainty. The VUP sample has its own weights - never pool it with the cross-section weights.
- **No leakage.** The poverty label is built from consumption, so features must not include: section 8 expenditure files, education spending, rent/imputed rent, water/electricity spending, durables' use value, or any column derived from them (`exp*`, `cons1*`, `sol_jan`, `food`, `quintile`, `hh_index`).
- **Validation.** Group cross-validation by cluster or district. Do not use EICV5 as a test set: its poverty measure is not comparable with EICV7.
- **VUP undercount.** The survey captures 67-76% of MINALOC's beneficiaries for DS, NSDS and public works (`reports/vup_reconciliation.csv`). Quote exclusion errors as a range (68-84% of poor households), not a single number.

## AI-use disclosure (required by the hackathon)

Fill in before submission: which AI tools were used, for what (e.g. code scaffolding, debugging, documentation drafting), and confirm all analysis choices and results were reviewed and are the team's responsibility.

## Citation

National Institute of Statistics of Rwanda (NISR) (2025). Seventh Integrated Household Living Conditions Survey (EICV7) Report.
