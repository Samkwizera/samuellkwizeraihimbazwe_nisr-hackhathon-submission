"""List every variable and its label in each .dta file, without loading the data.

Usage:
    python src/inspect_files.py data/raw/Cross_Section
Writes reports/variable_labels.csv so you can search it for candidate features.
"""
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UnicodeWarning)


def main(folder: str) -> None:
    rows = []
    for path in sorted(Path(folder).glob("*.dta")):
        with pd.io.stata.StataReader(path) as reader:
            labels = reader.variable_labels()
        for var, label in labels.items():
            rows.append({"file": path.name, "variable": var, "label": label})
        print(f"{path.name}: {len(labels)} variables")
    out = Path("reports/variable_labels.csv")
    out.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nWrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/raw/Cross_Section")
