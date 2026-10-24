"""VUP targeting gaps - Streamlit dashboard.

Reads only aggregated outputs (reports/*.csv) and public district boundaries
(assets/rwanda_districts.geojson, geoBoundaries / NISR, CC BY 4.0). No household
rows are loaded or shown.

Run locally:  streamlit run app/streamlit_app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
GEO = ROOT / "assets" / "rwanda_districts.geojson"

# Validated categorical pair (dataviz reference palette, light + dark pass) and blue ramp.
CURRENT, MODEL = "#eb6834", "#2a78d6"
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MUTED = "#a8a7a2"
RULES = {"current": "Current VUP", "model_same_quota": "Model, same district quotas",
         "model_poor_quota": "Model, poverty-based quotas", "model_national": "Model, national ranking"}

st.set_page_config(page_title="VUP Targeting Gaps", page_icon="📍", layout="wide")


def rewind(geo):
    """Make exterior rings clockwise: Plotly's geo (d3) fills the outside of counter-clockwise rings."""
    def signed_area(ring):
        return sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:]))
    for f in geo["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for i, ring in enumerate(poly):
                ccw = signed_area(ring) > 0
                if (i == 0 and ccw) or (i > 0 and not ccw):  # holes run the other way
                    ring.reverse()
    return geo


@st.cache_data
def load():
    return {name: pd.read_csv(REPORTS / f"{name}.csv") for name in
            ["coverage_national", "coverage_district", "targeting_national", "targeting_district",
             "vup_reconciliation", "model_metrics", "model_importance"]}, rewind(json.loads(GEO.read_text()))


data, geo = load()
cn, cd, tn, td = data["coverage_national"], data["coverage_district"], data["targeting_national"], data["targeting_district"]
anyv = cn.iloc[0]
cur = tn[(tn.budget == "survey") & (tn.rule == "current")].iloc[0]
best = tn[(tn.budget == "survey") & (tn.rule == "model_poor_quota")].iloc[0]


def fmt_k(v):
    return f"{v / 1000:,.0f}k"


st.title("Who does VUP miss?")
st.caption("Social protection coverage of poor households in Rwanda · EICV7 2023/24 (NISR) · "
           "NISR Big Data Hackathon 2026, Track 2")

tab_over, tab_map, tab_comp, tab_target, tab_method = st.tabs(
    ["Overview", "District map", "By programme", "Better targeting", "Method & limits"])

# ---------------------------------------------------------------- Overview
with tab_over:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Poor households reached by VUP", f"{anyv.poor_coverage:.0f}%",
              help=f"95% CI {anyv.poor_coverage_lo:.1f}–{anyv.poor_coverage_hi:.1f}%. Survey-reported.")
    c2.metric("Exclusion error (range)", "68–84%",
              help="84% as reported; 68–79% after correcting for the survey undercount of beneficiaries "
                   "versus MINALOC administrative counts.")
    c3.metric("VUP recipients who are not poor", f"{anyv.inclusion_error:.0f}%",
              help=f"95% CI {anyv.inclusion_error_lo:.1f}–{anyv.inclusion_error_hi:.1f}%")
    c4.metric("Poor households reached, same budget", fmt_k(best.poor_reached),
              delta=f"+{fmt_k(best.poor_reached - cur.poor_reached)} vs today ({fmt_k(cur.poor_reached)})",
              help="Model-based targeting with district budgets proportional to poverty, "
                   "same number of beneficiaries as today.")
    st.markdown(
        f"""
**What we found.** About **{anyv.recipients / 1e3:,.0f}k households** report a VUP component, but only
**{anyv.poor_coverage:.0f}%** of poor households are among them, and **{anyv.inclusion_error:.0f}%** of recipients are not poor.
Extreme-poor households are barely better reached ({anyv.extreme_poor_coverage:.0f}%). District budgets follow poverty only
loosely: Nyagatare has the most poor households left out, while low-poverty Gicumbi and Ruhango have some of the highest coverage.

**What would help.** A proxy-means score built from information that is easy to verify (household size, assets, housing,
education) ranks households far better than today's allocation. With the **same number of beneficiaries**, it would reach
about **{best.poor_reached / cur.poor_reached:.1f}×** as many poor households and cut the share of non-poor recipients from
{cur.inclusion_error:.0f}% to {best.inclusion_error:.0f}%.
"""
    )
    st.info("Survey estimates. The survey records 67–76% of the beneficiaries in MINALOC's administrative list, "
            "so exclusion errors are shown as a range. See *Method & limits*.", icon="ℹ️")

# ---------------------------------------------------------------- Map
with tab_map:
    metrics = {
        "Poor households left uncovered": ("poor_uncovered", "{:,.0f}"),
        "Exclusion error (% of poor not reached)": ("exclusion_error", "{:.1f}%"),
        "Poverty rate (% of people)": ("poverty_rate", "{:.1f}%"),
        "VUP coverage (% of households)": ("coverage", "{:.1f}%"),
        "Non-poor share of recipients": ("inclusion_error", "{:.1f}%"),
    }
    left, right = st.columns([3, 2])
    with left:
        label = st.selectbox("Map metric", list(metrics))
        col, f = metrics[label]
        reliable = cd[~cd.kigali_flag]
        kig = cd[cd.kigali_flag]
        fig = go.Figure()
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="properties.shapeName", locations=reliable.district, z=reliable[col],
            colorscale=[[i / (len(BLUES) - 1), c] for i, c in enumerate(BLUES)],
            marker_line_color="white", marker_line_width=1.5,
            colorbar=dict(title=dict(text=""), thickness=12, len=0.7),
            customdata=pd.concat([reliable[col], reliable[["poverty_rate", "coverage", "exclusion_error"]]], axis=1).to_numpy(),
            hovertemplate="<b>%{location}</b><br>" + label + ": %{customdata[0]:,.1f}"
                          "<br>Poverty %{customdata[1]:.1f}% · Coverage %{customdata[2]:.1f}%"
                          "<br>Exclusion error %{customdata[3]:.1f}%<extra></extra>"))
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="properties.shapeName", locations=kig.district, z=[0] * len(kig),
            colorscale=[[0, MUTED], [1, MUTED]], showscale=False, marker_line_color="white", marker_line_width=1.5,
            hovertemplate="<b>%{location}</b><br>Kigali: estimates too imprecise to map (CV 17–19%)<extra></extra>"))
        fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
        fig.update_layout(height=520, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                          geo_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch", theme="streamlit")
        st.caption("Grey: Kigali districts (Nyarugenge, Gasabo, Kicukiro), muted because survey estimates "
                   "there are too imprecise to compare.")
    with right:
        st.markdown("**Poverty vs coverage by district**")
        sc = go.Figure(go.Scatter(
            x=reliable.poverty_rate, y=reliable.coverage, mode="markers+text", text=reliable.district,
            textposition="top center", textfont=dict(size=10),
            marker=dict(size=10, color=MODEL, line=dict(color="white", width=2)),
            hovertemplate="<b>%{text}</b><br>Poverty %{x:.1f}%<br>Coverage %{y:.1f}%<extra></extra>"))
        sc.update_layout(height=480, margin=dict(l=0, r=10, t=10, b=0), showlegend=False,
                         xaxis_title="Poverty rate (% of people)", yaxis_title="VUP coverage (% of households)")
        st.plotly_chart(sc, width="stretch", theme="streamlit")
    show = cd[["district", "province", "poverty_rate", "coverage", "exclusion_error", "exclusion_error_lo",
               "exclusion_error_hi", "inclusion_error", "poor_uncovered", "rank_poor_uncovered", "kigali_flag"]]
    with st.expander("District table (with 95% confidence intervals)"):
        st.dataframe(show.rename(columns={"exclusion_error_lo": "excl. CI low", "exclusion_error_hi": "excl. CI high",
                                          "rank_poor_uncovered": "rank (excl. Kigali)"}),
                     hide_index=True, width="stretch")

# ---------------------------------------------------------------- Components
with tab_comp:
    comp = cn.iloc[1:]
    st.markdown("**Share of poor households reached, and share of recipients who are not poor, by VUP component**")
    a, b = st.columns(2)
    for col_, title, lo, hi, box in [("poor_coverage", "Poor households reached (%)", "poor_coverage_lo", "poor_coverage_hi", a),
                                     ("inclusion_error", "Recipients who are not poor (%)", "inclusion_error_lo", "inclusion_error_hi", b)]:
        bar = go.Figure(go.Bar(
            y=comp.component, x=comp[col_], orientation="h", marker_color=MODEL,
            error_x=dict(type="data", symmetric=False, array=comp[hi] - comp[col_], arrayminus=comp[col_] - comp[lo],
                         thickness=1.5, width=4, color=MUTED),
            text=comp[col_].map("{:.1f}%".format), textposition="inside", insidetextanchor="start", textfont=dict(color="white"),
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
        bar.update_layout(title=title, height=330, margin=dict(l=0, r=30, t=40, b=0),
                          yaxis=dict(autorange="reversed"), xaxis=dict(range=[0, max(comp[hi]) * 1.15]))
        box.plotly_chart(bar, width="stretch", theme="streamlit")
    st.caption("Classic Public Works is the most pro-poor component; Financial Services (approved VUP loans) "
               "reaches mostly non-poor households. Error bars: 95% CI.")

# ---------------------------------------------------------------- Targeting
with tab_target:
    budget = st.radio("Budget", ["survey", "admin"], horizontal=True,
                      format_func=lambda b: "Today's beneficiaries as surveyed (~380k households)" if b == "survey"
                      else "Scaled to MINALOC administrative count (~500k households)")
    t = tn[tn.budget == budget].copy()
    t["label"] = t.rule.map(RULES)
    bar = go.Figure(go.Bar(
        y=t.label, x=t.exclusion_error, orientation="h",
        marker_color=[CURRENT if r == "current" else MODEL for r in t.rule],
        error_x=dict(type="data", symmetric=False, array=t.exclusion_error_hi - t.exclusion_error,
                     arrayminus=t.exclusion_error - t.exclusion_error_lo, thickness=1.5, width=4, color=MUTED),
        text=t.exclusion_error.map("{:.1f}%".format), textposition="inside", insidetextanchor="start", textfont=dict(color="white"),
        customdata=t[["poor_reached", "inclusion_error", "extreme_poor_reached_pct"]],
        hovertemplate="<b>%{y}</b><br>Exclusion error %{x:.1f}%<br>Poor reached %{customdata[0]:,.0f}"
                      "<br>Non-poor recipients %{customdata[1]:.1f}%<br>Extreme poor reached %{customdata[2]:.1f}%<extra></extra>"))
    bar.update_layout(title="Exclusion error: share of poor households not reached (lower is better)", height=300,
                      margin=dict(l=0, r=40, t=40, b=0), yaxis=dict(autorange="reversed"), xaxis=dict(range=[0, 100]))
    st.plotly_chart(bar, width="stretch", theme="streamlit")
    if budget == "admin":
        st.caption("Current VUP at administrative scale is not directly observed; after correcting for the survey "
                   "undercount its exclusion error is 68–79%.")
    st.dataframe(t[["label", "selected_hh", "poor_reached", "exclusion_error", "inclusion_error",
                    "extreme_poor_reached_pct"]].astype({"selected_hh": int, "poor_reached": int}).rename(columns={
                        "label": "rule", "selected_hh": "households selected", "poor_reached": "poor reached",
                        "exclusion_error": "exclusion error %", "inclusion_error": "non-poor recipients %",
                        "extreme_poor_reached_pct": "extreme poor reached %"}).round(1),
                 hide_index=True, width="stretch")

    st.markdown("**By district: poor households reached, today vs model (same budget)**")
    rule = st.selectbox("Model rule", ["model_same_quota", "model_poor_quota"], format_func=RULES.get)
    dd = td[~td.kigali_flag].sort_values(f"poor_reached_{rule}", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=dd.district, x=dd.poor_reached_current, orientation="h", name="Current VUP",
                         marker_color=CURRENT, hovertemplate="%{y}: %{x:,.0f} poor reached today<extra></extra>"))
    fig.add_trace(go.Bar(y=dd.district, x=dd[f"poor_reached_{rule}"], orientation="h", name=RULES[rule],
                         marker_color=MODEL, hovertemplate="%{y}: %{x:,.0f} poor reached with model<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.1, height=760, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.02, x=0), xaxis_title="Poor households reached")
    st.plotly_chart(fig, width="stretch", theme="streamlit")
    st.caption("Same district quotas: better ranking only, no money moves between districts. "
               "Poverty-based quotas: district budgets proportional to their poor households. Kigali omitted.")

# ---------------------------------------------------------------- Method
with tab_method:
    mm = data["model_metrics"]
    logit = mm[(mm.variant == "no_program") & (mm.model == "logit")].iloc[0]
    st.markdown(f"""
### Data
EICV7 2023/24 cross-sectional sample (NISR): 15,054 households in 30 districts. Our weights reproduce NISR's published
national (27.4%) and all 30 district poverty rates exactly. Poverty rates are person-weighted; coverage shares are
household-weighted. 95% confidence intervals account for the survey design (district strata, cluster sampling).

### Who counts as a VUP beneficiary
A household is a beneficiary if any member received Direct Support, Nutrition-Sensitive DS, Classic or Expanded Public
Works, or an approved VUP Financial Services loan in the last 12 months. Asset Transfers and Skills Development cannot be
identified in the data (0.8% of MINALOC's beneficiary list).

### Survey vs administrative counts
""")
    rec = data["vup_reconciliation"].iloc[:5][["component", "survey_hh", "ci_low", "ci_high", "admin", "survey_over_admin"]]
    st.dataframe(rec.rename(columns={"survey_hh": "survey estimate", "ci_low": "CI low", "ci_high": "CI high",
                                     "admin": "MINALOC count", "survey_over_admin": "survey / admin"}).round(2),
                 hide_index=True, width="stretch")
    st.markdown(f"""
The survey captures 67–76% of administrative beneficiaries for the four main components. We therefore report the exclusion
error as a range: 84% as reported, 79% if the missing beneficiaries resemble the reported ones, 68% if they were all poor.

### Targeting model
Logistic regression predicting household poverty from {int(logit.n_features)} features that are easy to observe: household
size and composition, head's age/sex/education, district, housing materials, utilities, livestock, and counts of durable
goods. **No expenditure or consumption variables** are used, because the poverty measure is built from them. Features that
reflect existing programmes (CBHI, Girinka) are excluded; including them did not change accuracy.
Validated with 5-fold cross-validation grouped by survey cluster: AUC **{logit.auc:.3f}**. At today's coverage (11.5% of
households) it reaches {100 * logit.recall_at_vup_coverage:.0f}% of poor households, with {100 * logit.precision_at_vup_coverage:.0f}% of
those selected being poor.

### Limits
- Survey-based: undercount of beneficiaries (above); 12-month recall vs current administrative list.
- Kigali districts have imprecise estimates and are not mapped or ranked.
- A proxy-means score misses some poor households by design; it should complement, not replace, community
  verification (Ubudehe-style) and appeals.
- The model uses survey-style information; deploying it requires collecting the same variables for applicants.

### Sources
National Institute of Statistics of Rwanda (2025). *EICV7 Report* and *Methodological Note*.
District boundaries: geoBoundaries (Runfola et al. 2020), source NISR Open Data, CC BY 4.0.
AI use: see the project README.
""")
    imp = data["model_importance"].head(12)
    with st.expander("Most important model features"):
        st.dataframe(imp, hide_index=True, width="stretch")
