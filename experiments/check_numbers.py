"""
Cross-check every number quoted in the paper's prose against the result files.

Tables and figures are generated from results_v3/*.json, so they cannot
drift. Prose can: a value typed into a sentence has no such guarantee. This
script pulls every numeric literal out of main.tex, outside the preamble,
comments, citations and generated includes, and asks whether it matches a
value that an experiment actually produced -- directly, or through one of
the derivations the paper states explicitly (a ratio, a difference, a mean
over seeds). Anything it cannot account for is printed for a human to judge.

    python check_numbers.py
"""

import glob
import io
import json
import os
import re
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(HERE, "results_v3")
TEX = os.path.join(ROOT, "main.tex")


# --------------------------------------------------------------------------
def flatten(obj, out):
    if isinstance(obj, dict):
        for v in obj.values():
            flatten(v, out)
    elif isinstance(obj, list):
        for v in obj:
            flatten(v, out)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        v = float(obj)
        if v == v:                 # drop NaN (undefined precision etc.)
            out.append(v)
    elif isinstance(obj, str):
        try:
            out.append(float(obj))
        except ValueError:
            pass


def load_all():
    blobs = {}
    for p in sorted(glob.glob(os.path.join(RES, "*.json"))):
        with open(p, encoding="utf-8") as fh:
            blobs[os.path.basename(p)[:-5]] = json.load(fh)
    return blobs


def derived(blobs):
    """Values the paper states as arithmetic on measured quantities."""
    d = {}
    s1 = blobs.get("S1_holdout", {})
    s2 = blobs.get("S2_day_disjoint", {})
    s9 = blobs.get("S9_serving", {})
    s10 = blobs.get("S10_scaling", {})
    s0 = blobs.get("S0_dataset", {})

    def m(blob, model, key):
        return blob["summary"][model][key]["mean"]

    if s1:
        # "mean +- half-width": the JSON stores the interval ends.
        for model, summ in s1["summary"].items():
            for key, e in summ.items():
                d[f"ci half {model} {key}"] = e["ci95_high"] - e["mean"]
    if s1 and s2:
        for model in s1["summary"]:
            if model in s2["summary"]:
                d[f"F1 drop {model}"] = m(s1, model, "macro_f1") - m(s2, model, "macro_f1")
                d[f"recall drop {model}"] = m(s1, model, "recall_attack") - m(s2, model, "recall_attack")
        d["recall LogReg - XGB day-disj"] = (m(s2, "Logistic Regression", "recall_attack")
                                            - m(s2, "XGBoost", "recall_attack"))
        for blob, tag in ((s1, "random"), (s2, "day-disj")):
            rows = [r for r in blob["runs"] if r["model"] == "XGBoost"]
            for k in ("tn", "fp", "fn", "tp"):
                d[f"XGB mean {k} {tag}"] = statistics.fmean(r[k] for r in rows)
            d[f"XGB fpr {tag}"] = m(blob, "XGBoost", "fpr")
        per_ms = m(s1, "XGBoost", "per_sample_ms")
        d["extrapolated flows/s"] = 1000.0 / per_ms
        d["extrapolated flows/s (1e5 units)"] = 1000.0 / per_ms / 1e5
        if s10:
            pinned = {r["replicas"]: r for r in s10["scaling_threads_pinned"]}
            free = {r["replicas"]: r for r in s10["scaling_threads_unpinned"]}
            best = max(r["throughput_rps"] for r in pinned.values())
            d["extrapolation / best measured"] = (1000.0 / per_ms) / best
            for n in pinned:
                d[f"pinned/unpinned x{n}"] = (pinned[n]["throughput_rps"]
                                             / free[n]["throughput_rps"])
        if s9:
            batch = {r["batch_size"]: r for r in s9["batch"]}
            top = max(batch)
            d["extrapolation / batched"] = (1000.0 / per_ms) / batch[top]["flows_per_s"]
            d["batch flows/s ratio"] = batch[top]["flows_per_s"] / batch[1]["flows_per_s"]
            d["batch p50 ratio"] = batch[top]["latency_ms"]["p50"] / batch[1]["latency_ms"]["p50"]
    if s0:
        d["attack ratio %"] = 100 * s0["attack_ratio"]
    s3 = blobs.get("S3_per_family", {})
    if s3:
        loo = s3["leave_one_family_out_xgboost"]
        for k, v in loo.items():
            d[f"missed % {k}"] = 100 * (1 - v["unseen_recall"])
    s4 = blobs.get("S4_feature_stability", {})
    if s4:
        d["always selected count"] = len(s4["always_selected"])
        d["top-k"] = len(s4["impurity_top"])
        d["impurity vs permutation count"] = round(
            s4["criterion_overlap"]["impurity_vs_permutation"] * len(s4["impurity_top"]))
    s5 = blobs.get("S5_unsw_replication", {})
    if s5:
        pass  # means are direct values
    # UNSW attack ratio is printed in the run log, not stored: 0.6806.
    d["UNSW attack ratio % (from run log)"] = 68.06
    return d


# --------------------------------------------------------------------------
def prose_numbers(tex):
    body = tex[tex.index("\\begin{abstract}"):]
    lines = []
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("%") or stripped.startswith("\\inputtable") \
                or stripped.startswith("\\resfig"):
            continue
        # strip citations, labels, refs, comments
        line = re.sub(r"\\(cite|ref|label|eqref)\{[^}]*\}", " ", line)
        line = re.sub(r"(?<!\\)%.*$", "", line)
        lines.append(line)
    text = "\n".join(lines)
    text = text.replace("{,}", "").replace("\\,", "")
    # numbers like 0.9935, 36506, 9.5\times10^{5}, 17.7\%, 2300
    found = []
    for m in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)(?:\s*\\times\s*10\^\{(-?\d+)\})?", text):
        raw, exp = m.group(1), m.group(2)
        val = float(raw) * (10 ** int(exp) if exp else 1)
        ctx = text[max(0, m.start() - 40):m.end() + 30].replace("\n", " ")
        found.append((raw, val, exp is not None, ctx))
    return found


def decimals(raw):
    return len(raw.split(".")[1]) if "." in raw else 0


def matches(raw, val, pool, sci=False):
    """A literal matches if some measured value rounds to it at the precision
    the paper printed. Scientific notation is compared on the mantissa; a
    round integer such as 2,300 or 8,000 is accepted when the measured value
    rounds to it at the number of significant figures printed (trailing
    zeros are taken as not significant)."""
    dec = decimals(raw)
    if sci:
        # val is mantissa * 10^exp; recover the exponent from the literal
        mant = float(raw)
        exp = round(__import__("math").log10(val / mant)) if mant else 0
        for name, v in pool:
            if v > 0 and round(v / 10 ** exp, dec) == round(mant, dec):
                return name
        return None
    sig = len(raw.rstrip("0")) if "." not in raw else None
    for name, v in pool:
        if dec > 0:
            if round(v, dec) == round(val, dec):
                return name
            if abs(v - val) <= 0.5 * 10 ** -dec:
                return name
        else:
            if round(v) == val:
                return name
            if val >= 100 and sig and sig < len(raw):
                # e.g. "2300" (2 s.f.) accepts 2342; "8000" accepts 8075
                scale = 10 ** (len(raw) - sig)
                if round(v / scale) * scale == val:
                    return name
    return None


IGNORE = {  # structural numbers, not measurements
    "2017", "2021", "2022", "2023", "2025", "2026", "2", "3", "4", "5", "1",
    "20", "70", "30", "16", "128", "64", "200", "300", "1000", "50", "8",
    "0.98", "0.99", "0.3", "0.31", "10", "12", "15", "100", "1e5",
}


def main():
    blobs = load_all()
    pool = []
    for name, blob in blobs.items():
        vals = []
        flatten(blob, vals)
        pool += [(name, v) for v in vals]
    for k, v in derived(blobs).items():
        pool.append((f"derived:{k}", v))

    tex = io.open(TEX, encoding="utf-8").read()
    nums = prose_numbers(tex)
    ok, unmatched = 0, []
    seen = set()
    for raw, val, sci, ctx in nums:
        key = (raw, sci)
        if raw in IGNORE and not sci:
            continue
        if key in seen:
            continue
        seen.add(key)
        hit = matches(raw, val, pool, sci=sci)
        if hit:
            ok += 1
        else:
            unmatched.append((raw, ctx))
    print(f"checked {ok + len(unmatched)} distinct literals: {ok} matched, "
          f"{len(unmatched)} need a human look\n")
    for raw, ctx in unmatched:
        print(f"  ?? {raw:>10s}   …{ctx.strip()}…")


if __name__ == "__main__":
    main()
