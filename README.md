# Closing Rwanda's social-protection targeting gap

**NISR Big Data Hackathon 2026 — Track 2: Financial Inclusion & Poverty Reduction**

This project asks a practical question: **where does the Vision 2020 Umurenge Programme (VUP) miss poor households, and who should be prioritized when the budget is fixed?** It combines survey-weighted coverage measurement with an explainable, leakage-free proxy-targeting model and an aggregate-only Streamlit dashboard.

The analysis uses the NISR EICV7 2023/24 cross-sectional sample: 15,054 households across Rwanda's 30 districts, representing about 3.29 million households. No household microdata are included in this repository or exposed by the dashboard.

## What we found

- The five observable VUP components reach **15.9% of poor households** (95% CI: 14.7–17.1%) and **18.2% of extremely poor households**.
- **67.8% of reported recipients are non-poor** (95% CI: 65.5–70.1%). This is a survey-based targeting measure, not a claim that recipients are ineligible under every VUP criterion.
- The survey records only 67–76% of administrative beneficiaries for Direct Support, Nutrition-Sensitive Direct Support, Classic Public Works, and Expanded Public Works. After reconciling that undercount, a defensible exclusion-error range is **68–84%**, rather than the unadjusted 84.1% alone.
- Poverty and VUP coverage are only moderately aligned across districts (correlation 0.38). Nyagatare, Kamonyi, Rubavu, Kayonza, and Rusizi have the largest estimated numbers of poor households left uncovered. Kigali estimates are shown with warnings and are never ranked because their coefficients of variation are high.
- At the same survey-estimated budget of about 380,000 households, the preferred model reaches **268,000 poor households** under national ranking, compared with **122,000 currently reported**. Keeping current district budgets but re-ranking households reaches about 237,000.
- At administrative scale (about 500,000 households), modeled exclusion is 56.5–61.2%, compared with the estimated 68.4–79.0% range for current allocation after undercount correction.

These are **policy simulations**, not automated eligibility decisions. They show the potential value of better screening and geographic allocation; final selection should include transparent rules, current administrative data, local verification, appeals, and ongoing fairness monitoring.

## Dashboard

The Streamlit app has five views:

1. national coverage and the reconciled exclusion range;
2. district-level poverty, coverage, and uncovered-poor estimates;
3. results by VUP component;
4. same-budget targeting scenarios; and
5. methods and limitations.

Run it locally with:

```powershell
streamlit run app/streamlit_app.py
```

For Streamlit Community Cloud, select this repository, the `main` branch, and `app/streamlit_app.py`. The deployed app needs only `reports/*.csv`, `assets/rwanda_districts.geojson`, and `requirements.txt`; it does not need microdata.

## Method

### Outcomes and survey design

Poverty status comes from the official EICV7 poverty file. The annual poverty line is RWF 560,127 per adult equivalent and the extreme-poverty line is RWF 356,432, both in January 2024 prices.

- Published poverty rates are person-level estimates weighted by `pop_wt`. The validation script reproduces the NISR national rate of 27.4% and all 30 published district rates.
- Household coverage and targeting measures use the household weight, `weight`.
- Confidence intervals account for clusters (`clust`) and use district as the stratum.
- `vup_any` is the union of five observable components: Direct Support, Classic Public Works, Expanded Public Works, Nutrition-Sensitive Direct Support, and approved Financial Services loans.
- Asset Transfers and Skills Development are not observed in the cross-sectional programme files. They represent about 0.8% of the administrative frame.

### Coverage and reconciliation

Programme files can contain multiple rows per household, so each component is collapsed to one household flag before merging. Financial Services counts an approved loan, not an application. The separate VUP sample contains beneficiaries only and has its own weights; it is never pooled with the cross-sectional sample or used to estimate exclusion.

Survey totals are compared with the current MINALOC administrative list in `reports/vup_reconciliation.csv`. The component totals imply genuine survey undercount and/or timing differences: EICV asks about the previous 12 months, while the administrative list is current. The reported 68–84% exclusion range spans the raw survey estimate, a correction where missing beneficiaries resemble observed beneficiaries, and a conservative upper-bound correction.

### Proxy-targeting model

The preferred model is weighted logistic regression using 74 pre-transfer, non-consumption features. Candidate predictors cover household composition, the head's characteristics, district and urban/rural location, dwelling conditions, utilities, durable ownership counts, remittances, and shocks.

Consumption and expenditure variables are deliberately excluded because the poverty label is constructed from consumption. Prohibited features include section 8 expenditures, education spending, rent or imputed rent, utility spending, durable use values, and derived consumption, quintile, or poverty-line fields. The preferred `no_program` variant also drops CBHI insurance and Girinka receipt so it does not learn existing programme selection.

Validation uses five-fold `StratifiedGroupKFold`, grouped by enumeration cluster. Every out-of-fold score therefore comes from a model that did not train on that household's cluster. The logistic model achieved weighted AUC 0.856 and recalled 34.8% of poor households at the current 11.5% household-coverage budget, versus 15.9% under VUP as reported. The simpler logistic model slightly outperformed gradient boosting and is preferred for explainability.

The targeting simulation ranks these out-of-fold scores under three rules:

- **National ranking:** allocate to the highest scores nationwide.
- **Poverty-proportional district quotas:** allocate district budgets in proportion to estimated poor-household counts, then rank within districts.
- **Current district quotas:** preserve each district's current budget and improve only within-district ranking.

In implementation, poverty-proportional quotas should use NISR's published district poverty rates rather than survey-derived household counts.

## Limitations and responsible use

- Programme participation and poverty are survey-reported and may contain recall or classification error.
- Administrative and survey reference periods differ; reconciliation is a sensitivity analysis, not a record-level match.
- District estimates are less precise than national estimates. Kigali districts have CVs of roughly 17–19% and are flagged rather than ranked.
- Proxy models can reproduce historical and measurement bias. A high score is not proof of eligibility, and a low score must not remove an existing entitlement.
- EICV7 introduced a methodology break, so EICV5 is not used as a test set and poverty estimates are not compared directly across those rounds.
- Performance will drift as prices, livelihoods, and programme rules change. Any operational use requires fresh validation, subgroup audits, human review, an appeals channel, and data-protection controls.
- NISR's published models can achieve higher accuracy when expenditure variables are included (reported R² of 0.89 urban and 0.68 rural). This project accepts lower accuracy to avoid target leakage and support a deployable pre-assessment tool.

## Reproduce the analysis

Use Python 3.10 or newer. Download EICV7 from NISR under its applicable data-use terms and place files locally as follows:

```text
data/raw/Cross_Section/*.dta
data/raw/VUP/*.dta             # optional; never pooled with cross-section weights
```

Then run from the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python src/validate.py
python src/build_table.py
python src/build_features.py
python src/reconcile_vup.py
python src/coverage.py
python src/model.py
python src/targeting.py
streamlit run app/streamlit_app.py
```

Key aggregate outputs are committed in `reports/`. Household tables, features, predictions, `.dta`, `.parquet`, archives, and local reference PDFs are excluded by `.gitignore`.

## Repository structure

```text
app/        Streamlit dashboard
assets/     Rwanda district boundaries used by the map
reports/    Aggregate, disclosure-safe analysis outputs
src/        Reproducible data, estimation, modeling, and validation scripts
```

## AI-use disclosure

AI-assisted development tools, including **OpenAI Codex and Claude Code**, were used for code scaffolding, debugging support, interface styling, and documentation drafting. AI did not supply the survey data or independently determine the reported findings. The team reviewed the code, statistical choices, aggregate outputs, and written claims and accepts responsibility for the submission. No EICV7 household microdata are committed to the repository or sent to the deployed dashboard. This disclosure should remain in the final submission in accordance with the hackathon rules.

## Data protection and licensing

The public repository contains original code, aggregate outputs, and documentation only. EICV7 microdata remain subject to NISR's access and use conditions. Intellectual property for the hackathon submission is assigned according to the NISR competition rules; no separate open-source licence is asserted here.

## Citation

National Institute of Statistics of Rwanda (NISR). (2025). *Seventh Integrated Household Living Conditions Survey (EICV7) Report* and *Methodological Note*.

District boundaries: geoBoundaries Rwanda ADM2, sourced from NISR Open Data, CC BY 4.0 (Runfola et al., 2020).
