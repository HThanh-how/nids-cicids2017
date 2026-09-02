"""
Bring main.tex within the SOICT page limit (12-15 pages including references)
by removing tables that only restate a figure.

Every figure in this paper carries direct value labels, so where a table and
a figure show the same measurement the table is pure duplication. This script
comments out those \\inputtable calls rather than deleting them, so the full
set can be restored for the artefact or for a longer version, and so it is
obvious to a later reader what was removed and why.

The generated .tex files are left in place: they are part of the released
artefact regardless of whether the paper includes them.

    python scripts/trim_for_page_limit.py            # apply
    python scripts/trim_for_page_limit.py --restore  # undo
"""

import argparse
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "main.tex")

# table name -> why it is safe to drop
DROP = {
    "optimism_gap": "the dumbbell figure carries the same means and the gap",
    "per_family": "the heatmap prints every cell value",
    "leave_one_out": "the bar chart prints every value",
    "feature_stability": "the bar chart prints every value",
    "feature_list": "released with the artefact; the count is given in text",
    "transfer": "the grouped bars carry the same values",
    "days": "the two day groups are named in the text",
    "alignment": "the seven aligned pairs are listed in the text",
}

MARK = "% [trimmed for page limit] "


def apply_trim(s):
    n = 0
    for name, why in DROP.items():
        pat = re.compile(r"^(\\inputtable\{" + re.escape(name) + r"\})\s*$",
                         re.MULTILINE)
        s, k = pat.subn(lambda m: f"{MARK}{why}\n%{m.group(1)}", s)
        n += k
    return s, n


def restore(s):
    pat = re.compile(r"^" + re.escape(MARK) + r".*\n%(\\inputtable\{[^}]+\})",
                     re.MULTILINE)
    return pat.subn(lambda m: m.group(1), s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    s = io.open(MAIN, encoding="utf-8").read()
    s, n = restore(s) if args.restore else apply_trim(s)
    io.open(MAIN, "w", encoding="utf-8", newline="\n").write(s)
    print(("restored" if args.restore else "trimmed") + f" {n} tables")


if __name__ == "__main__":
    main()
