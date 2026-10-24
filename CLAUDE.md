# CLAUDE.md - NISR Big Data Hackathon 2026, Track 2

## Goal
Find where social protection (VUP) misses poor households in Rwanda, and show who should be prioritized.
Track 2: Financial Inclusion & Poverty Reduction. Data: EICV7 2023-24 (NISR).

## Hackathon constraints (hard)
- Submission deadline: 30 Oct 2026, 11:59 PM. Needs: public GitHub repo, deployed app link, documentation.
- Evaluation (20 pts each): problem relevance (NST2/Vision 2050), data use & methodology, tech innovation, usability/design, tangible impact.
- IP is assigned to NISR. Work must be original and never submitted elsewhere. AI use MUST be disclosed in the docs (see README).
- Team of 2, at least one Rwandan citizen.

## Rules for working in this repo
- NEVER commit microdata (`data/` is git-ignored). Public repo = code, aggregates, docs only. Dashboard shows aggregated results only, no household rows.
- Ask before running `git push`, deleting files, or installing packages outside requirements.txt.
- Keep everything reproducible: scripts in `src/`, no manual steps. Run from the project root.
- Run `python src/validate.py` after any change to loading/weights code. It must pass.

## Data (data/raw/Cross_Section/, EICV7 cross-sectional sample)
- 15,054 households, 30 districts. Weighted households = 3.29M (matches 2022 census frame).
- `CS_EICV7_poverty_file.dta`: label + weights + district. `poverty` = Non Poor / Moderately poor / Severely Poor; `pov_jan` = Poor/Non Poor; `epov_jan` = extreme poverty.
- Program files `CS_S9D1..S9D5`: DS, classic PW, expanded PW, NSDS, financial services. Every file repeats `s9d1q1` (any VUP). Some files have extra rows per household -> collapse by hhid.
- `src/build_table.py` -> `data/processed/hh_table.parquet` (141 columns; flags: ds, cpw, epw, nsds, fin, vup_any; poor, extreme_poor).
- Optional: VUP sample (`data/raw/VUP/`, 3,771 beneficiary households, own weights). Everyone in it is a beneficiary, so it cannot measure exclusion. Never pool its weights with the cross-section.
- Asset transfers and skills development are VUP components but have no program file in the cross-section.

## Statistical rules
- Poverty rates (person level): weight by `pop_wt`. Verified: reproduces NISR's 27.4% national and all 30 published district rates (Methodological Note, Appendix 1).
- Shares of households (coverage): weight by `weight`.
- Uncertainty: cluster = `clust`, strata = `district`. Published design effect is 1.9 nationally, up to 3.7 (Gasabo). Kigali districts (Nyarugenge, Gasabo, Kicukiro) have CVs of 17-19%: mute or flag them on maps, never rank them.
- Poverty line: RWF 560,127 per adult equivalent per year (Jan 2024 prices); extreme line 356,432.

## Modeling rules (proxy-targeting model)
- LEAKAGE: the poverty label is built from consumption. Do NOT use as features: section 8 expenditure files, education spending, rent/imputed rent, water/electricity spending, durables' use value, or derived columns (`exp1`-`exp11`, `cons1`, `cons1ae`, `sol_jan`, `food`, `quintile`, `hh_index`, `Poverty_line`, `Extreme_line`, `Food_at_school`).
- Good candidate features: head's age/sex/education/marital status, household size and composition shares, district, urban/rural, dwelling materials, utilities, land and animals, remittances, shocks, durable ownership (counts, not values).
- Validation: group CV by `clust` (or district). NOT EICV5 as a test set: EICV7 is a methodology break, poverty is not comparable.
- Report honestly that accuracy is lower without expenditure variables (NISR's own models with them reach R2 0.89 urban / 0.68 rural).
- Evaluate for targeting: recall of poor households at a fixed coverage budget, not just AUC.

## Preliminary findings (NOT final, do not quote without the reconciliation below)
- 11.5% of households (95% CI 11.0-12.1) report any of the 5 components (1,888 hh). Household-level: ~84% of poor households report none; ~68% of VUP households are non-poor; poverty among VUP households ~32% vs ~22% for the rest.
- Nationally: 15.9% of poor households covered (CI 14.7-17.1); extreme poor only 18.2%; 67.8% of recipients non-poor. FS is the least pro-poor (80% non-poor), cPW the most (58%).
- Districts: poverty vs coverage correlation only 0.38. Most poor left uncovered: Nyagatare (~50k, 96% exclusion), Kamonyi, Rubavu, Kayonza, Rusizi. Gicumbi/Ruhango: low poverty, high coverage. Nyaruguru best (60% exclusion).
- RECONCILED (src/reconcile_vup.py, reports/vup_reconciliation.csv): survey = 67-76% of admin for DS/NSDS/cPW/ePW (CIs exclude 100%); FS = 115%. Units agree (~1 beneficiary per household), so the gap is real undercount or frame timing (admin = current MINALOC list, survey = last 12 months). Exclusion error among poor households: 84.1% as reported, 79.0% if missing beneficiaries look like reported ones, 68.4% upper-bound correction. Quote the range, not 84% alone.
- "any VUP" = union of the 5 component flags (`vup_any`). The `s9d1q1` column in the files is NOT Q1: in each file it only marks that file's component. Asset Transfer / Skills Development (0.8% of admin frame) are not observable. FS beneficiary = loan approved (`s9d5q2`), not applied (`s9d5q1`).

## Next tasks (in order)
1. DONE (src/build_features.py, reports/feature_list.csv; no land variable found yet): run `src/inspect_files.py`; explore person, durables, access-to-services files; pick leakage-free features.
2. DONE: reconcile survey vs admin VUP counts; "any VUP" definition settled.
3. DONE (src/coverage.py -> reports/coverage_national.csv, coverage_district.csv): coverage and error analysis by component and district, weighted, with cluster-robust CIs.
4. DONE (src/model.py -> reports/model_metrics.csv, model_importance.csv; OOF scores in data/processed/oof_predictions.parquet): logit AUC 0.856, GBM 0.849 (cluster-grouped 5-fold). At the current 11.5% budget the model reaches 34.8% of poor households vs 15.9% for VUP as reported. Dropping CBHI/Girinka changes nothing (use the no_program variant). Logit >= GBM, so prefer logit (simpler, explainable). Top features: household size, district, durable types, mattresses, rooms per person, head education.
5. DONE (src/targeting.py -> reports/targeting_national.csv, targeting_district.csv): same ~380k beneficiaries, exclusion error 84.1% current -> 69.2% model within current district quotas -> 66.2% poverty-proportional district quotas -> 65.2% national ranking; inclusion error 67.8% -> 31-37%; extreme poor reached 18% -> 50-60%. Poor households reached 122k -> 237-268k. At admin scale (~500k) model exclusion 56.5-61.2% vs 68.4-79.0% corrected current. Biggest district gains from re-ranking: Nyamasheke, Musanze, Nyamagabe, Ruhango; biggest gains from reallocating budget: Nyagatare, Kamonyi, Kayonza, Rwamagana, Nyanza. District quotas use survey poor counts; in practice use NISR's published district rates.
6. App BUILT: Streamlit, app/streamlit_app.py (reads reports/*.csv + assets/rwanda_districts.geojson only; geojson rings rewound for Plotly). Tabs: Overview, District map, By programme, Better targeting, Method & limits. NOT YET DEPLOYED: needs the repo pushed to GitHub, then Streamlit Community Cloud.
7. Documentation: methodology, limitations, AI-use disclosure, citation to NISR (2025) EICV7 Report.

## Commands
```
python src/validate.py
python src/build_table.py
python src/build_features.py
python src/reconcile_vup.py
python src/coverage.py
python src/model.py
python src/targeting.py
streamlit run app/streamlit_app.py
python src/inspect_files.py data/raw/Cross_Section
```
