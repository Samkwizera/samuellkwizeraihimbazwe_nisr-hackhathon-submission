"""Generate the public, aggregate-only two-page VUP targeting policy brief.

Usage:
    python src/generate_policy_brief.py

Writes output/pdf/vup_policy_brief.pdf. No household-level data are read.
"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle


OUT = Path("output/pdf/vup_policy_brief.pdf")
PREVIEW = Path("tmp/pdfs")
GREEN = "#147D64"
DARK = "#17211F"
BODY = "#3D4B46"
MUTED = "#68756F"
PALE = "#E4F1EC"
LINE = "#DDE7E2"
ORANGE = "#C46A32"


def text(ax, x, y, value, size=10, color=BODY, weight="normal", **kwargs):
    horizontal = kwargs.pop("ha", "left")
    return ax.text(x, y, value, transform=ax.transAxes, fontsize=size, color=color,
                   fontweight=weight, va="top", ha=horizontal, **kwargs)


def box(ax, x, y, w, h, face="white", edge=LINE, radius=0.018):
    patch = FancyBboxPatch((x, y), w, h, transform=ax.transAxes,
                           boxstyle=f"round,pad=0.012,rounding_size={radius}",
                           linewidth=1, edgecolor=edge, facecolor=face)
    ax.add_patch(patch)
    return patch


def footer(ax, page):
    ax.add_line(plt.Line2D([0.07, 0.93], [0.055, 0.055], transform=ax.transAxes, color=LINE, lw=1))
    text(ax, 0.07, 0.042, "VUP Lens | EICV7 2023/24 | Aggregate results only", 7.5, MUTED)
    text(ax, 0.91, 0.042, str(page), 7.5, MUTED, ha="right")


def page_one(pdf):
    fig = plt.figure(figsize=(8.27, 11.69), facecolor="#FBFCFB")
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    ax.add_patch(Rectangle((0, .91), 1, .09, transform=ax.transAxes, color=GREEN))
    text(ax, .07, .975, "VUP LENS", 9, "white", "bold")
    text(ax, .07, .948, "Policy brief | October 2026", 8, "white")

    text(ax, .07, .865, "How Rwanda can reach more poor families\nwith the same VUP budget", 23, DARK, "bold", linespacing=1.08)
    text(ax, .07, .775, "EICV7 evidence shows a large coverage gap. Poverty-informed district budgets,\n"
                       "transparent household prioritisation, and community verification could more than\n"
                       "double the number of poor households reached.", 10, BODY, linespacing=1.45)

    box(ax, .07, .59, .40, .14, PALE, "#B9D8CD")
    text(ax, .095, .705, "THE PROBLEM", 8, GREEN, "bold")
    text(ax, .095, .675, "84 in 100", 25, GREEN, "bold")
    text(ax, .095, .625, "poor households report no support\nfrom the five observed VUP components.", 10, BODY, linespacing=1.35)

    box(ax, .53, .59, .40, .14, "white")
    text(ax, .555, .705, "THE OPPORTUNITY", 8, GREEN, "bold")
    text(ax, .555, .675, "+138,000", 25, GREEN, "bold")
    text(ax, .555, .625, "additional poor households could be reached\nwith poverty-based quotas at the same budget.", 10, BODY, linespacing=1.35)

    text(ax, .07, .535, "What the evidence says", 15, DARK, "bold")
    findings = [
        ("16%", "of poor households report receiving an observed VUP component."),
        ("68-84%", "is the defensible range for poor households left uncovered after survey-admin reconciliation."),
        ("68%", "of reported recipient households are above the poverty line."),
        ("0.38", "is the district correlation between poverty and coverage, showing weak geographic alignment."),
    ]
    y = .49
    for number, description in findings:
        text(ax, .07, y, number, 15, ORANGE, "bold")
        text(ax, .18, y, description, 9.3, BODY, wrap=True)
        y -= .067

    text(ax, .07, .20, "Recommended decision", 15, DARK, "bold")
    text(ax, .07, .165, "Use published district poverty rates to distribute available places. Within districts, use a\n"
                        "leakage-free household priority score to create a shortlist. Make final decisions only after\n"
                        "community verification, clear explanations, and an accessible appeals process.", 10, BODY,
         linespacing=1.5)
    footer(ax, 1)
    pdf.savefig(fig, bbox_inches="tight", pad_inches=0)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    fig.savefig(PREVIEW / "vup_policy_brief-1.png", dpi=140, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def page_two(pdf):
    fig = plt.figure(figsize=(8.27, 11.69), facecolor="#FBFCFB")
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    text(ax, .07, .95, "A practical path from evidence to action", 21, DARK, "bold")
    text(ax, .07, .905, "The score supports decisions. It does not replace people, programme rules, or rights.", 10.5, BODY)

    steps = [
        ("1", "Measure", "NISR updates poverty evidence and validates model performance."),
        ("2", "Allocate", "MINALOC and LODA set poverty-informed district quotas."),
        ("3", "Prioritise", "Districts create transparent preliminary household shortlists."),
        ("4", "Verify", "Community review checks circumstances the data cannot observe."),
        ("5", "Learn", "Appeals and monitoring reveal errors and guide the next allocation."),
    ]
    y = .84
    for n, title, desc in steps:
        ax.add_patch(plt.Circle((.095, y - .012), .022, transform=ax.transAxes, color=GREEN))
        text(ax, .095, y, n, 9, "white", "bold", ha="center")
        text(ax, .14, y + .006, title, 11, DARK, "bold")
        text(ax, .14, y - .023, desc, 9.2, BODY)
        if n != "5":
            ax.add_line(plt.Line2D([.095, .095], [y - .038, y - .075], transform=ax.transAxes, color="#9DCABB", lw=2))
        y -= .075

    box(ax, .07, .285, .86, .165, PALE, "#B9D8CD")
    text(ax, .095, .425, "90-DAY PILOT", 8, GREEN, "bold")
    text(ax, .095, .397, "Weeks 1-3", 9.2, DARK, "bold"); text(ax, .23, .397, "Agree variables, safeguards, roles, and published rules.", 9.0)
    text(ax, .095, .368, "Weeks 4-7", 9.2, DARK, "bold"); text(ax, .23, .368, "Test in two high-gap and two comparison districts.", 9.0)
    text(ax, .095, .339, "Weeks 8-10", 9.2, DARK, "bold"); text(ax, .23, .339, "Run verification and an accessible appeals process.", 9.0)
    text(ax, .095, .31, "Weeks 11-13", 9.2, DARK, "bold"); text(ax, .23, .31, "Compare reach, errors, processing time, and appeals.", 9.0)

    text(ax, .07, .265, "National policy alignment", 15, DARK, "bold")
    text(ax, .07, .228, "NST2 Goal 26", 10, GREEN, "bold")
    text(ax, .28, .228, "Reduce poverty and improve standards of living.", 9.5)
    text(ax, .07, .195, "Social protection", 10, GREEN, "bold")
    text(ax, .28, .195, "Increase transfer coverage and adequacy and improve social-registry targeting.", 9.5)
    text(ax, .07, .162, "Vision 2050", 10, GREEN, "bold")
    text(ax, .28, .162, "Advance inclusive development and a high standard of living for all Rwandans.", 9.5)

    text(ax, .07, .115, "Safeguards", 12, DARK, "bold")
    text(ax, .07, .087, "No automatic eligibility decisions. No household records in the public dashboard. Monitor subgroup\n"
                        "outcomes, explain decisions, allow appeals, and revalidate as conditions change.", 9, BODY, linespacing=1.35)
    footer(ax, 2)
    pdf.savefig(fig, bbox_inches="tight", pad_inches=0)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    fig.savefig(PREVIEW / "vup_policy_brief-2.png", dpi=140, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUT, metadata={"Title": "VUP targeting policy brief", "Author": "NISR Hackathon Track 2 team"}) as pdf:
        page_one(pdf)
        page_two(pdf)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
