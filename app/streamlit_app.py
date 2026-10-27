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
POLICY_BRIEF = ROOT / "output" / "pdf" / "vup_policy_brief.pdf"

# Rwanda-inspired, colour-blind-safe palette. Green is the interface accent;
# amber is reserved for the observed/current comparison series.
CURRENT, MODEL = "#C46A32", "#147D64"
GREENS = ["#E4F2ED", "#C2E2D7", "#94CDBA", "#62B49C", "#37987F", "#147D64", "#0B5B49"]
MUTED = "#8A918E"
RULES = {"current": "Current VUP", "model_same_quota": "Model, same district quotas",
         "model_poor_quota": "Model, poverty-based quotas", "model_national": "Model, national ranking"}

st.set_page_config(page_title="VUP Targeting Gaps", page_icon="📍", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Sora:wght@600;700&display=swap');

  :root {
    --ink: #121b19; --body: #3d4b46; --muted: #6a7672; --line: #e2eae6;
    --surface: #f4f8f6; --card: #ffffff; --canvas: #eef2f0;
    --accent: #147d64; --accent-dark: #0b5b49; --accent-soft: #e4f1ec;
    --radius: 16px; --sidebar-w: 268px;
  }

  html, body, .stApp, [class*="css"] { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; }
  .stApp { background: var(--canvas); color: var(--ink); }

  /* Every bit of Streamlit chrome text, stated explicitly so nothing inherits a
     light-on-light colour from the base theme. */
  .stApp, .stApp p, .stApp li, .stApp span, .stApp label, .stApp div,
  .stMarkdown, [data-testid="stMarkdownContainer"] { color: var(--body); }
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp strong, .stApp b { color: var(--ink); }
  .stApp a { color: var(--accent-dark); }
  [data-testid="stWidgetLabel"] p, .stRadio label p, .stSelectbox label p,
  [data-testid="stExpander"] summary p, [data-testid="stExpander"] summary {
    color: var(--ink) !important; font-weight: 600;
  }
  [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
    color: var(--muted) !important;
  }
  div[data-baseweb="select"] > div { background: var(--card); color: var(--ink); border-color: var(--line); }
  div[data-baseweb="select"] div, div[data-baseweb="popover"] li { color: var(--ink); }
  [data-testid="stDataFrame"] { background: var(--card); }
  #MainMenu, footer, [data-testid="stDecoration"] { visibility: hidden; }
  header[data-testid="stHeader"] { background: transparent; height: 0; }

  h1, h2, h3 { font-family: 'Sora', 'Inter', sans-serif; letter-spacing: -0.03em; }
  p, li { line-height: 1.65; }

  /* ---------------- floating sidebar ---------------- */
  section[data-testid="stSidebar"] {
    position: fixed; top: 1.1rem; left: 1.1rem;
    width: var(--sidebar-w) !important; min-width: var(--sidebar-w) !important;
    height: calc(100vh - 2.2rem);
    border: 1px solid var(--line); border-radius: 20px;
    background: linear-gradient(180deg, #ffffff 0%, #f6faf8 100%);
    box-shadow: 0 24px 60px rgba(18, 48, 39, .13);
    overflow: hidden auto; z-index: 100;
  }
  section[data-testid="stSidebar"] > div { padding: 1.5rem 1.15rem; height: auto; }
  section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] { display: none; }
  /* Streamlit reserves ~5rem of empty header space at the top of the sidebar */
  section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] { display: none; }
  section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 0; }
  section[data-testid="stSidebar"] hr { border-color: var(--line); }

  /* main pane sits beside the floating card */
  section[data-testid="stMain"] {
    margin: 1.1rem 1.1rem 1.1rem calc(var(--sidebar-w) + 2.2rem);
    border: 1px solid var(--line); border-radius: 22px;
    background: #fbfcfb; box-shadow: 0 20px 55px rgba(36, 58, 51, .08);
  }
  .block-container { max-width: 1240px; padding: 1.6rem 2.2rem 4rem; }

  .side-brand { display: flex; align-items: center; gap: .7rem; margin-bottom: 1.5rem; }
  .side-brand__mark {
    display: grid; place-items: center; width: 40px; height: 40px; border-radius: 12px;
    background: linear-gradient(135deg, var(--accent) 0%, #1aa37f 100%);
    color: #fff; font-size: .8rem; font-weight: 700; letter-spacing: -.02em;
    box-shadow: 0 6px 16px rgba(20, 125, 100, .3);
  }
  .side-brand__mark { color: #fff !important; }
  .side-brand__name { color: var(--ink); font-size: 1rem; font-weight: 700; line-height: 1.15; font-family: 'Sora', sans-serif; }
  .side-brand__name small { display: block; margin-top: .22rem; color: var(--muted); font-size: .67rem; font-weight: 500; font-family: 'Inter', sans-serif; }
  .side-label {
    margin: 1.25rem 0 .55rem; color: var(--muted); font-size: .66rem;
    font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  }
  .side-item {
    display: flex; align-items: center; gap: .5rem;
    padding: .5rem .7rem; margin: .2rem 0; border-radius: 9px;
    color: var(--body); font-size: .79rem; font-weight: 500;
  }
  .side-item:before { content: ""; width: 5px; height: 5px; border-radius: 50%; background: var(--accent); opacity: .55; flex: none; }

  section[data-testid="stSidebar"] div[role="radiogroup"] {
    display: flex; flex-direction: column; gap: .18rem; padding: 0; background: transparent;
  }
  section[data-testid="stSidebar"] div[role="radiogroup"] label {
    width: 100%; padding: .6rem .72rem; margin: 0; border-radius: 10px;
    font-size: .84rem; cursor: pointer; transition: background .15s ease, color .15s ease;
  }
  section[data-testid="stSidebar"] div[role="radiogroup"] label p { color: var(--body) !important; font-size: .84rem; font-weight: 550; }
  section[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: #edf4f1; }
  section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: var(--accent-soft); box-shadow: inset 2px 0 0 var(--accent);
  }
  section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
    color: var(--accent-dark) !important; font-weight: 700;
  }
  section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none; }

  .scope-card {
    padding: .9rem 1rem; margin-top: 1.4rem; border: 1px solid var(--line);
    border-radius: 14px; background: var(--card);
  }
  .scope-card strong { display: block; color: var(--ink); font-size: .8rem; }
  .scope-card span { display: block; margin-top: .35rem; color: var(--muted); font-size: .71rem; line-height: 1.5; }

  /* ---------------- masthead ---------------- */
  .masthead {
    display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 2.2rem;
    align-items: end; padding: .4rem .1rem 1.3rem; margin-bottom: 1rem;
    border-bottom: 1px solid var(--line);
  }
  .masthead__kicker {
    display: inline-block; margin: 0 0 .85rem; padding: .3rem .7rem;
    border-radius: 999px; background: var(--accent-soft);
    color: var(--accent-dark) !important; font-size: .7rem;
    font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  }
  .masthead h1 {
    max-width: 740px; margin: 0; font-size: clamp(2rem, 3.8vw, 3.1rem);
    font-weight: 700; line-height: 1.04;
  }
  .masthead__sub { max-width: 700px; margin: .8rem 0 0; color: var(--body) !important; font-size: .97rem; }
  .masthead__meta { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: 0; }
  .masthead__meta span {
    padding: .65rem .75rem; border: 1px solid var(--line); border-radius: 11px;
    background: var(--surface); color: var(--muted) !important; font-size: .7rem;
    font-weight: 600; letter-spacing: .03em; text-transform: uppercase;
  }
  .masthead__meta b { display: block; margin-top: .2rem; color: var(--ink); font-size: .88rem; letter-spacing: 0; text-transform: none; }

  /* ---------------- components ---------------- */
  div[data-baseweb="tab-list"] { gap: .2rem; padding: .3rem; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); }
  button[data-baseweb="tab"] { min-height: 42px; padding: .55rem 1rem; border-radius: 9px; font-weight: 600; }
  button[data-baseweb="tab"][aria-selected="true"] { background: #fff; color: var(--accent-dark); }
  div[data-baseweb="tab-highlight"] { display: none; }

  div[data-testid="stMetric"] {
    min-height: 146px; padding: 1.05rem 1.1rem; border: 1px solid var(--line);
    border-radius: var(--radius); background: var(--card);
    box-shadow: 0 8px 24px rgba(42, 68, 59, .05);
    transition: transform .18s ease, box-shadow .18s ease;
  }
  div[data-testid="stMetric"]:hover { transform: translateY(-2px); box-shadow: 0 14px 32px rgba(42, 68, 59, .1); }
  /* Streamlit truncates widget/metric labels with .stMarkdownEllipsis; let them wrap
     so no label is ever hidden behind an ellipsis. */
  .stMarkdownEllipsis, .stMarkdownEllipsis p,
  div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] > div {
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
  }
  div[data-testid="stMetricLabel"] p { color: var(--muted) !important; font-size: .78rem; font-weight: 600; line-height: 1.35; }
  div[data-testid="stMetricValue"] { color: var(--ink) !important; font-family: 'Sora', sans-serif; font-size: clamp(1.7rem, 2.7vw, 2.3rem); font-weight: 700; }
  div[data-testid="stMetricDelta"], div[data-testid="stMetricDelta"] div { font-weight: 600; font-size: .78rem; }

  .section-intro { max-width: 790px; margin: 1.2rem 0 1.1rem; }
  .section-intro h2 { margin: 0 0 .4rem; font-size: 1.6rem; }
  .section-intro p { margin: 0; color: var(--muted) !important; }

  .finding {
    padding: 1.15rem 1.3rem; margin: .9rem 0;
    border: 1px solid var(--line); border-left: 4px solid var(--accent);
    border-radius: 0 var(--radius) var(--radius) 0; background: var(--surface);
    color: var(--body);
  }
  .finding strong { color: var(--accent-dark); }

  .plain-hero {
    display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, .8fr);
    gap: 1rem; margin: 1rem 0 1.4rem;
  }
  .plain-hero__message, .plain-hero__result {
    padding: 1.35rem 1.45rem; border-radius: var(--radius); border: 1px solid var(--line);
  }
  .plain-hero__message { background: #fff; }
  .plain-hero__result { background: var(--accent-soft); border-color: #b9d8cd; }
  .plain-hero__number {
    display: block; margin-bottom: .35rem; color: var(--accent-dark) !important;
    font-family: 'Sora', sans-serif; font-size: clamp(2.3rem, 5vw, 4.2rem); font-weight: 700; line-height: 1;
  }
  .plain-hero h2, .plain-hero h3 { margin: 0 0 .5rem; }
  .plain-hero p { margin: 0; }
  .story-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem; margin: 1rem 0 1.5rem; }
  .story-step { padding: 1.1rem; border-top: 3px solid var(--accent); background: #fff; }
  .story-step strong { display: block; margin-bottom: .35rem; font-size: 1rem; }
  .story-step p { margin: 0; color: var(--muted) !important; font-size: .88rem; }
  .people-row { display: flex; flex-wrap: wrap; gap: 5px; margin: .9rem 0 .55rem; max-width: 530px; }
  .person { width: 17px; height: 17px; border-radius: 50%; background: #d6dfdb; }
  .person.reached { background: var(--accent); }
  .person.more { background: #71b9a4; }
  .simple-key { display: flex; gap: 1rem; flex-wrap: wrap; color: var(--muted); font-size: .78rem; }
  .simple-key span:before { content: ''; display: inline-block; width: 9px; height: 9px; margin-right: .35rem; border-radius: 50%; background: #d6dfdb; }
  .simple-key .key-current:before { background: var(--accent); }
  .simple-key .key-more:before { background: #71b9a4; }
  .action-box { padding: 1.25rem 1.4rem; margin: 1rem 0; border-radius: var(--radius); background: #fff; border: 1px solid var(--line); }
  .action-box h3 { margin-top: 0; }
  .action-box ol { margin-bottom: 0; }

  div[data-testid="stAlert"] { border-radius: var(--radius); border: 1px solid #cfe0da; background: var(--accent-soft); }
  div[data-testid="stAlert"] p { color: #11493b !important; }

  /* caveat note, in the project palette rather than Streamlit's blue info box */
  .note {
    display: flex; align-items: flex-start; gap: .8rem;
    padding: .85rem 1.1rem; margin: 1.1rem 0;
    border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface);
  }
  .note__tag {
    flex: none; margin-top: .1rem; padding: .18rem .5rem; border-radius: 6px;
    background: var(--accent-soft); color: var(--accent-dark) !important;
    font-size: .64rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  }
  .note p { margin: 0; color: var(--muted) !important; font-size: .86rem; }
  div[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: var(--radius); background: var(--card); }
  div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] { border-radius: var(--radius); }
  div[role="radiogroup"] { border-radius: 10px; }

  @media (max-width: 1100px) {
    section[data-testid="stSidebar"] { position: relative; top: 0; left: 0; height: auto; width: 100% !important; min-width: 0 !important; border-radius: 0; }
    section[data-testid="stMain"] { margin: 0; border-radius: 0; border: 0; }
    .block-container { padding: 1rem 1.1rem 2.5rem; }
    .masthead { grid-template-columns: 1fr; padding: 1rem 0; }
    .masthead h1 { font-size: 2.2rem; }
    button[data-baseweb="tab"] { padding: .45rem .6rem; font-size: .78rem; }
    .plain-hero, .story-grid { grid-template-columns: 1fr; }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *:before, *:after { scroll-behavior: auto !important; transition: none !important; animation: none !important; }
  }
</style>
""", unsafe_allow_html=True)


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

with st.sidebar:
    st.markdown("""
    <div class="side-brand">
      <div class="side-brand__mark">RW</div>
      <div class="side-brand__name">VUP Lens<small>Targeting evidence platform</small></div>
    </div>
    <div class="side-label">Explore</div>
    """, unsafe_allow_html=True)
    page = st.radio(
        "Dashboard section",
        ["Start here", "Where help is needed", "How programmes compare", "A better way to target", "Evidence & limits"],
        label_visibility="collapsed",
    )
    st.markdown("""
    <div class="side-label">Evidence standard</div>
    <div class="side-item">Survey-weighted estimates</div>
    <div class="side-item">Cluster-robust intervals</div>
    <div class="side-item">No household rows shown</div>
    <div class="scope-card">
      <strong>EICV7 2023/24</strong>
      <span>15,054 households across all 30 districts. Results are aggregated for safe public use.</span>
    </div>
    """, unsafe_allow_html=True)
    st.caption("NISR Big Data Hackathon 2026 | Track 2")


def fmt_k(v):
    return f"{v / 1000:,.0f}k"


def polish(fig):
    """Apply one visual language to every chart without changing its data."""
    fig.update_layout(
        font=dict(family="Segoe UI, Arial, sans-serif", color="#34413D", size=13),
        title_font=dict(size=17, color="#17211F"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="#17211F", font_color="#F7FAF8", bordercolor="#17211F"),
        legend=dict(font=dict(size=12)),
    )
    # automargin: category labels on horizontal bar charts were clipped by the zero left margin
    fig.update_xaxes(gridcolor="#E5ECE9", zeroline=False, title_font=dict(size=12),
                     tickfont=dict(size=12, color="#3D4B46"), automargin=True)
    fig.update_yaxes(gridcolor="#E5ECE9", zeroline=False, title_font=dict(size=12),
                     tickfont=dict(size=12, color="#3D4B46"), automargin=True)
    return fig


st.markdown("""
<section class="masthead">
  <div>
    <p class="masthead__kicker">A clearer path to social protection</p>
    <h1>Help VUP reach more poor families</h1>
    <p class="masthead__sub">See who is being missed, where the gap is largest, and how the same budget can reach more families.</p>
  </div>
  <div class="masthead__meta">
    <span>Source<br><b>EICV7 2023/24</b></span>
    <span>Coverage<br><b>30 districts</b></span>
    <span>Sample<br><b>15,054 households</b></span>
    <span>Privacy<br><b>Aggregates only</b></span>
  </div>
</section>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- Start here
if page == "Start here":
    st.markdown("""
    <div class="section-intro">
      <h2>The problem in one minute</h2>
      <p>VUP is designed to protect vulnerable Rwandan families. Survey evidence shows that many poor families are still outside the five programme components we can observe.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"""
    <div class="plain-hero">
      <div class="plain-hero__message">
        <span class="plain-hero__number">84 in 100</span>
        <h2>poor households report no observed VUP support</h2>
        <p>Even after allowing for beneficiaries missing from the survey, the estimate is still about 68 to 79 in every 100 poor households.</p>
      </div>
      <div class="plain-hero__result">
        <span class="plain-hero__number">+138k</span>
        <h3>more poor households reached</h3>
        <p>A poverty-based district budget and household priority score could reach about {best.poor_reached / 1000:,.0f}k poor households, compared with {cur.poor_reached / 1000:,.0f}k now, without increasing the number selected.</p>
      </div>
    </div>
    <div class="story-grid">
      <div class="story-step"><strong>1. Find the gap</strong><p>Measure how many poor households are missed in every district.</p></div>
      <div class="story-step"><strong>2. Put resources where need is greater</strong><p>Use published poverty rates to set fair district budgets.</p></div>
      <div class="story-step"><strong>3. Verify families locally</strong><p>Use a simple priority score as a shortlist, then confirm through community review and appeals.</p></div>
    </div>
    """, unsafe_allow_html=True)

    dots = '<span class="person reached"></span>' * 16 + '<span class="person more"></span>' * 19 + '<span class="person"></span>' * 65
    st.markdown(f"""
    <div class="action-box">
      <h3>Out of 100 poor households</h3>
      <div class="people-row">{dots}</div>
      <div class="simple-key">
        <span class="key-current">16 reached now</span>
        <span class="key-more">19 more reached with national model ranking</span>
        <span>65 still need other or expanded support</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="action-box">
      <h3>The recommendation</h3>
      <ol>
        <li>Use NISR's published district poverty rates when distributing the available VUP places.</li>
        <li>Within each district, use observable household conditions to create a transparent shortlist.</li>
        <li>Keep people in control: community verification, a clear explanation, and an appeals process are required before enrolment decisions.</li>
      </ol>
    </div>
    """, unsafe_allow_html=True)

    if POLICY_BRIEF.exists():
        st.download_button(
            "Download the 2-page policy brief",
            data=POLICY_BRIEF.read_bytes(),
            file_name="VUP_targeting_policy_brief.pdf",
            mime="application/pdf",
            width="stretch",
        )
    st.markdown("""
    <div class="note">
      <span class="note__tag">Why a range?</span>
      <p>The survey records fewer beneficiaries than MINALOC's administrative list. We show both the survey result and corrected scenarios instead of pretending there is one exact number. Details are under <em>Evidence &amp; limits</em>.</p>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------- Map
if page == "Where help is needed":
    st.markdown("""
    <div class="section-intro">
      <h2>Where are poor families most often missed?</h2>
      <p>Darker districts have a larger gap for the selected measure. Kigali is grey because its survey estimates are not precise enough for fair comparison.</p>
    </div>
    """, unsafe_allow_html=True)
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
            colorscale=[[i / (len(GREENS) - 1), c] for i, c in enumerate(GREENS)],
            marker_line_color="white", marker_line_width=1.5,
            colorbar=dict(title=dict(text=""), thickness=12, len=0.7),
            customdata=pd.concat([reliable[col], reliable[["poverty_rate", "coverage", "exclusion_error"]]], axis=1).to_numpy(),
            hovertemplate="<b>%{location}</b><br>" + label + ": %{customdata[0]:,.1f}"
                          "<br>Poverty %{customdata[1]:.1f}% · Coverage %{customdata[2]:.1f}%"
                          "<br>Exclusion error %{customdata[3]:.1f}%<extra></extra>"))
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="properties.shapeName", locations=kig.district, z=[0] * len(kig),
            colorscale=[[0, MUTED], [1, MUTED]], showscale=False, marker_line_color="white", marker_line_width=1.5,
            hovertemplate="<b>%{location}</b><br>Kigali: estimates too imprecise to map (CV 17-19%)<extra></extra>"))
        fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
        fig.update_layout(height=520, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                          geo_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(polish(fig), width="stretch", theme=None)
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
        st.plotly_chart(polish(sc), width="stretch", theme=None)
    show = cd[["district", "province", "poverty_rate", "coverage", "exclusion_error", "exclusion_error_lo",
               "exclusion_error_hi", "inclusion_error", "poor_uncovered", "rank_poor_uncovered", "kigali_flag"]]
    with st.expander("District table (with 95% confidence intervals)"):
        st.dataframe(show.rename(columns={"exclusion_error_lo": "excl. CI low", "exclusion_error_hi": "excl. CI high",
                                          "rank_poor_uncovered": "rank (excl. Kigali)"}),
                     hide_index=True, width="stretch")

# ---------------------------------------------------------------- Components
if page == "How programmes compare":
    st.markdown("""
    <div class="section-intro">
      <h2>Which VUP components reach poor families?</h2>
      <p>The left chart shows how many poor households each component reaches. The right chart shows how many recipients are above the poverty line. Thin lines show the reasonable range around each estimate.</p>
    </div>
    """, unsafe_allow_html=True)
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
        box.plotly_chart(polish(bar), width="stretch", theme=None)
    st.caption("Classic Public Works is the most pro-poor component; Financial Services (approved VUP loans) "
               "reaches mostly non-poor households. Error bars: 95% CI.")

# ---------------------------------------------------------------- Targeting
if page == "A better way to target":
    st.markdown("""
    <div class="section-intro">
      <h2>What happens if selection improves?</h2>
      <p>Every option below selects approximately the same number of households. A shorter bar means fewer poor households are left without support.</p>
    </div>
    """, unsafe_allow_html=True)
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
    st.plotly_chart(polish(bar), width="stretch", theme=None)
    if budget == "admin":
        st.caption("Current VUP at administrative scale is not directly observed; after correcting for the survey "
                   "undercount its exclusion error is 68-79%.")
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
    st.plotly_chart(polish(fig), width="stretch", theme=None)
    st.caption("Same district quotas: better ranking only, no money moves between districts. "
               "Poverty-based quotas: district budgets proportional to their poor households. Kigali omitted.")

# ---------------------------------------------------------------- Method
if page == "Evidence & limits":
    st.markdown("""
    <div class="section-intro">
      <h2>Why you can trust the evidence, and where to be careful</h2>
      <p>This section explains the data, the model, and its limits. Household records never appear in the public app.</p>
    </div>
    """, unsafe_allow_html=True)
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
The survey captures 67-76% of administrative beneficiaries for the four main components. We therefore report the exclusion
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

### From evidence to implementation
1. **NISR** publishes poverty evidence and supports model validation.
2. **MINALOC and LODA** set the national budget and programme rules.
3. **Districts** receive poverty-informed quotas and produce a preliminary shortlist.
4. **Community verification** checks circumstances the model cannot observe.
5. **Appeals and monitoring** correct errors and measure who is still being missed.

### 90-day pilot
- **Weeks 1-3:** agree variables, safeguards, roles, and published decision rules.
- **Weeks 4-7:** test in four districts: two with large uncovered-poor estimates and two comparison districts.
- **Weeks 8-10:** conduct community verification and an accessible appeals process.
- **Weeks 11-13:** compare poor-household reach, exclusion, inclusion, processing time, and appeal outcomes with current practice.

### Alignment with Rwanda's priorities
- **NST2 Goal 26:** reduced poverty and improved standards of living.
- **NST2 social protection priority:** increase the coverage and adequacy of transfers for poor and vulnerable people.
- **NST2 delivery approach:** use the social registry for targeting and strengthen joint monitoring across MINALOC, LODA, districts, civil society, and partners.
- **Vision 2050:** inclusive development and a high standard of living for all Rwandans.

This tool supports those goals by showing coverage gaps, proposing poverty-informed resource allocation, and giving government a measurable way to test whether targeting improves.

### Sources
[National Institute of Statistics of Rwanda](https://www.statistics.gov.rw/) (2025), *EICV7 Report* and *Methodological Note*.
[National Strategy for Transformation 2024-2029](https://www.minecofin.gov.rw/index.php?eID=dumpFile&f=112651&t=f&token=0d37e3b2e0b33ca65ec4fcc88d0c86132b3e6056).
[Social Protection Sector Strategic Plan 2024-2029](https://www.minaloc.gov.rw/fileadmin/user_upload/Minaloc/Publications/Useful_Documents/Social_Protection/Social_Protection_Sector_Strategic_Plan_2024_-_29_Full_version_.pdf).
District boundaries: geoBoundaries (Runfola et al. 2020), source NISR Open Data, CC BY 4.0.
AI use: see the project README.
""")
    imp = data["model_importance"].head(12)
    with st.expander("Most important model features"):
        st.dataframe(imp, hide_index=True, width="stretch")
