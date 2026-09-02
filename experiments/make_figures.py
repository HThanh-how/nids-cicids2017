"""
Generate every figure in the paper from results_v3/*.json.

Same rule as make_tables.py: nothing is drawn that an experiment did not
produce, and no value is typed by hand. A stage that has not run yet simply
yields no figure.

    python make_figures.py          # writes ../figures/*.pdf

Design constraints, chosen for print rather than for screen:

  * Vector PDF at the LNCS text width (122.5 mm), so nothing is resampled.
  * A serif face matching the body text, at sizes that stay legible at 100 %.
  * A categorical palette validated for colour-vision deficiency: the worst
    adjacent pair separates by dE 9.1 (protan, OKLab x100) against a >= 8
    target, and by dE 22.9 for normal vision against a >= 15 floor. Two of the
    four slots fall below 3:1 contrast on white, so every figure carries
    either direct value labels or the corresponding table -- the relief the
    palette's contrast warning requires.
  * Redundant encoding throughout: each model keeps a fixed hue *and* a fixed
    marker or hatch, so the figures survive greyscale printing and
    photocopying.
  * No dual-axis plots. Where two quantities of different scale belong to one
    story they are stacked as two panels sharing an x axis.
"""

import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results_v3")
OUT = os.path.join(os.path.dirname(HERE), "figures")
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)

# LNCS text width is 122.5 mm.
WIDTH = 122.5 / 25.4

MODELS = ["Logistic Regression", "Random Forest", "XGBoost", "MLP"]
SHORT = {"Logistic Regression": "LogReg", "Random Forest": "RF",
         "XGBoost": "XGBoost", "MLP": "MLP"}
# Validated categorical slots 1-4 (light surface).
COLOR = {"Logistic Regression": "#2a78d6", "Random Forest": "#eb6834",
         "XGBoost": "#1baf7a", "MLP": "#eda100"}
MARKER = {"Logistic Regression": "o", "Random Forest": "s",
          "XGBoost": "^", "MLP": "D"}
HATCH = {"Logistic Regression": "", "Random Forest": "///",
         "XGBoost": "...", "MLP": "xxx"}

INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d8d7d3"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8,
    "axes.labelsize": 8.5,
    "axes.titlesize": 9,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42,
})


def load(stage):
    p = os.path.join(RES, f"{stage}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def clean_label(s):
    """CICIDS2017 web-attack labels carry a cp1252 dash that survives as
    U+FFFD; render it as a plain hyphen."""
    t = "".join(c if ord(c) < 128 else "-" for c in str(s))
    while "- -" in t:
        t = t.replace("- -", "-")
    return t.replace("Web Attack ", "Web ").strip()


def tidy(ax, xgrid=False, ygrid=True):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y" if ygrid else "x", color=GRID, linewidth=0.5, zorder=0)
    if xgrid:
        ax.grid(axis="x", color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p)
    # A raster twin is written alongside the vector file purely for visual
    # inspection during writing; LaTeX picks up the PDF.
    fig.savefig(os.path.join(OUT, "preview",
                             name.replace(".pdf", ".png")), dpi=200)
    plt.close(fig)
    print(f"[figure] figures/{name}")


def models_of(summary):
    return [m for m in MODELS if m in summary]


# --------------------------------------------------------------------------
def fig_optimism_gap():
    """The headline: the same pipeline evaluated two ways.

    A dumbbell rather than grouped bars -- the quantity of interest is the
    *change* per model, and a dumbbell puts that change on the page as a
    length instead of asking the reader to subtract two bar heights.
    """
    d1, d2 = load("S1_holdout"), load("S2_day_disjoint")
    if not (d1 and d2):
        return
    shared = [m for m in models_of(d1["summary"]) if m in d2["summary"]]
    if not shared:
        return

    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 1.95), sharey=True)
    for ax, metric, title in zip(
            axes, ("recall_attack", "macro_f1"),
            ("Attack recall", "Macro-F1")):
        y = np.arange(len(shared))[::-1]
        for yi, m in zip(y, shared):
            a = d1["summary"][m][metric]["mean"]
            b = d2["summary"][m][metric]["mean"]
            ax.plot([b, a], [yi, yi], color=GRID, linewidth=2.5,
                    solid_capstyle="round", zorder=1)
            ax.scatter([a], [yi], s=32, color=COLOR[m], marker=MARKER[m],
                       edgecolor="white", linewidth=0.6, zorder=3)
            ax.scatter([b], [yi], s=32, facecolor="white", marker=MARKER[m],
                       edgecolor=COLOR[m], linewidth=1.1, zorder=3)
            ax.annotate(f"{b:.2f}", (b, yi), textcoords="offset points",
                        xytext=(-4, 0), ha="right", va="center",
                        fontsize=6.5, color=MUTED)
            ax.annotate(f"{a:.2f}", (a, yi), textcoords="offset points",
                        xytext=(4, 0), ha="left", va="center",
                        fontsize=6.5, color=MUTED)
        ax.set_yticks(y)
        ax.set_yticklabels([SHORT[m] for m in shared])
        ax.set_ylim(-0.65, len(shared) - 0.35)
        ax.set_xlim(0, 1.18)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_title(title, pad=6)
        tidy(ax, xgrid=True, ygrid=False)

    handles = [
        Line2D([], [], marker="o", linestyle="none", color=MUTED,
               markersize=5, label="random split"),
        Line2D([], [], marker="o", linestyle="none", markerfacecolor="white",
               markeredgecolor=MUTED, markersize=5, label="day-disjoint"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, -0.19))
    save(fig, "fig_optimism_gap.pdf")


def fig_seed_spread():
    """Why one seed is not a result: per-seed macro-F1 with the mean and its
    95 % interval."""
    d = load("S1_holdout")
    if not d:
        return
    runs = d["runs"]
    shared = models_of(d["summary"])
    fig, ax = plt.subplots(figsize=(WIDTH, 2.1))
    for i, m in enumerate(shared):
        vals = [r["macro_f1"] for r in runs if r["model"] == m]
        jitter = np.linspace(-0.13, 0.13, len(vals))
        ax.scatter(np.full(len(vals), i) + jitter, vals, s=16,
                   color=COLOR[m], marker=MARKER[m], alpha=0.85,
                   edgecolor="white", linewidth=0.4, zorder=3)
        s = d["summary"][m]["macro_f1"]
        lo, hi = s["ci95_low"], s["ci95_high"]
        ax.plot([i - 0.28, i + 0.28], [s["mean"]] * 2, color=INK,
                linewidth=1.2, zorder=4)
        ax.add_patch(plt.Rectangle((i - 0.28, lo), 0.56, max(hi - lo, 1e-6),
                                   facecolor=COLOR[m], alpha=0.18,
                                   edgecolor="none", zorder=2))
    ax.set_xticks(range(len(shared)))
    ax.set_xticklabels([SHORT[m] for m in shared])
    ax.set_ylabel("Macro-F1")
    ax.set_title("Per-seed spread, random split "
                 "(bar: mean; band: 95 % interval)", pad=6)
    ax.margins(y=0.10)
    tidy(ax)
    save(fig, "fig_seed_spread.pdf")


def fig_ppv():
    """Precision collapses with prevalence even when TPR and FPR do not
    move. One panel per protocol; a shared log-scaled x axis."""
    d = load("S7_operational")
    if not d:
        return
    order = [("S1_holdout", "Random split"),
             ("S2_day_disjoint", "Day-disjoint"),
             ("S5_unsw_replication", "UNSW-NB15")]
    panels = [(k, t) for k, t in order if k in d]
    if not panels:
        return
    fig, axes = plt.subplots(1, len(panels),
                             figsize=(WIDTH, 2.3), sharey=True)
    if len(panels) == 1:
        axes = [axes]
    for ax, (key, title) in zip(axes, panels):
        per = d[key]
        for m in models_of(per):
            curve = per[m]["ppv_by_prevalence"]
            xs = sorted((float(k) for k in curve), reverse=True)
            ys = [curve[str(x)]["ppv"] for x in xs]
            ax.plot(xs, ys, color=COLOR[m], marker=MARKER[m], markersize=3.5,
                    linewidth=1.2, label=SHORT[m], zorder=3)
        ax.set_xscale("log")
        ax.invert_xaxis()
        ax.set_xlabel("attack prevalence")
        ax.set_title(title, pad=5)
        ax.set_ylim(-0.03, 1.03)
        tidy(ax)
    axes[0].set_ylabel("Precision (PPV)")
    axes[-1].legend(frameon=False, loc="upper right")
    save(fig, "fig_ppv_prevalence.pdf")


def fig_per_family():
    """Binary aggregation hides this: detection rate varies by an order of
    magnitude across families."""
    d = load("S3_per_family")
    if not d:
        return
    per = d["per_family_random_split"]
    models = models_of(per)
    fams = [f for f in sorted({f for m in per.values() for f in m})
            if f.upper() != "BENIGN"]
    if not (models and fams):
        return
    M = np.array([[per[m].get(f, {}).get("recall", np.nan) for m in models]
                  for f in fams], dtype=float)

    fig, ax = plt.subplots(figsize=(WIDTH, 0.26 * len(fams) + 1.1))
    im = ax.imshow(M, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels([SHORT[m] for m in models])
    ax.set_yticks(range(len(fams)))
    ax.set_yticklabels([clean_label(f) for f in fams])
    for i in range(len(fams)):
        for j in range(len(models)):
            v = M[i, j]
            if np.isnan(v):
                continue
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.2,
                    color="white" if v > 0.55 else INK)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("recall", fontsize=7.5)
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0, labelsize=7)
    ax.set_title("Per-family recall, random split", pad=6)
    save(fig, "fig_per_family.pdf")


def fig_leave_one_out():
    """Recall on a family removed from training entirely."""
    d = load("S3_per_family")
    if not d or not d.get("leave_one_family_out_xgboost"):
        return
    loo = d["leave_one_family_out_xgboost"]
    items = sorted(loo.items(), key=lambda kv: kv[1]["unseen_recall"])
    names = [clean_label(k) for k, _ in items]
    vals = [v["unseen_recall"] for _, v in items]

    fig, ax = plt.subplots(figsize=(WIDTH, 0.24 * len(items) + 1.0))
    y = np.arange(len(items))
    ax.barh(y, vals, height=0.62, color=COLOR["XGBoost"], zorder=3)
    for yi, v in zip(y, vals):
        # Rounding a near-zero recall to "0.00" would read as exactly zero,
        # which is a different claim; show enough digits to tell them apart.
        lab = f"{v:.4f}" if 0 < v < 0.01 else f"{v:.2f}"
        ax.text(v + 0.015, yi, lab, va="center", fontsize=6.5, color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("recall on the held-out family (XGBoost)")
    ax.set_title("Detection of an attack type never seen in training", pad=6)
    tidy(ax, xgrid=True, ygrid=False)
    save(fig, "fig_leave_one_out.pdf")


def fig_cost():
    """Accuracy against what it costs to score a flow. Log x because the
    models differ by orders of magnitude."""
    d = load("S1_holdout")
    if not d:
        return
    fig, ax = plt.subplots(figsize=(WIDTH, 2.2))
    pts = []
    for m in models_of(d["summary"]):
        s = d["summary"][m]
        pts.append((s["per_sample_ms"]["mean"], s["macro_f1"]["mean"],
                    s["macro_f1"]["ci95_high"] - s["macro_f1"]["mean"], m))
    # Random Forest and XGBoost land almost on top of each other, so labels
    # placed identically would collide. Ordering by position and alternating
    # the offset separates them deterministically.
    pts.sort(key=lambda p: (p[1], p[0]))
    for i, (x, y, half, m) in enumerate(pts):
        ax.errorbar(x, y, yerr=half, fmt=MARKER[m], color=COLOR[m],
                    markersize=6, capsize=2.5, elinewidth=0.8,
                    markeredgecolor="white", markeredgewidth=0.5, zorder=3)
        dy, va = ((9, "bottom") if i % 2 else (-9, "top"))
        ax.annotate(SHORT[m], (x, y), textcoords="offset points",
                    xytext=(8, dy), fontsize=7.5, color=INK, va=va)
    ax.set_xscale("log")
    ax.set_xlabel("amortised inference cost (ms per flow, log scale)")
    ax.set_ylabel("Macro-F1")
    ax.set_title("Detection quality against model cost", pad=6)
    ax.margins(x=0.45, y=0.22)
    tidy(ax)
    save(fig, "fig_cost.pdf")


def fig_feature_stability():
    """How much the selected feature set depends on the seed, and on the
    importance criterion."""
    d = load("S4_feature_stability")
    if not d:
        return
    ov = d["criterion_overlap"]
    labels = ["seed-to-seed\n(Jaccard)", "impurity vs\npermutation",
              "impurity vs\nmutual info", "permutation vs\nmutual info"]
    vals = [d["mean_pairwise_jaccard"], ov["impurity_vs_permutation"],
            ov["impurity_vs_mutual_info"], ov["permutation_vs_mutual_info"]]
    colors = [COLOR["Random Forest"]] + [COLOR["Logistic Regression"]] * 3

    fig, ax = plt.subplots(figsize=(WIDTH, 2.0))
    x = np.arange(len(vals))
    ax.bar(x, vals, width=0.6, color=colors, zorder=3)
    for xi, v in zip(x, vals):
        ax.text(xi, v + 0.02, f"{v:.2f}", ha="center", fontsize=7,
                color=MUTED)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("agreement")
    ax.set_title("The selected features are reproducible across seeds "
                 "but not across criteria", pad=6)
    tidy(ax)
    save(fig, "fig_feature_stability.pdf")


def fig_transfer():
    """Train on one corpus, test on the other."""
    d = load("S6_transfer")
    if not d or "results" not in d:
        return
    dirs = list(d["results"])
    fig, axes = plt.subplots(1, len(dirs), figsize=(WIDTH, 2.2), sharey=True)
    if len(dirs) == 1:
        axes = [axes]
    metrics = [("macro_f1", "Macro-F1"), ("recall_attack", "Recall"),
               ("precision_attack", "Precision")]
    for ax, direction in zip(axes, dirs):
        per = d["results"][direction]
        models = models_of(per)
        x = np.arange(len(metrics))
        w = 0.8 / max(len(models), 1)
        for i, m in enumerate(models):
            vals = [per[m][k] for k, _ in metrics]
            ax.bar(x + i * w - 0.4 + w / 2, vals, width=w * 0.9,
                   color=COLOR[m], hatch=HATCH[m], edgecolor="white",
                   linewidth=0.5, label=SHORT[m], zorder=3)
        ax.set_xticks(x)
        ax.set_xticklabels([lab for _, lab in metrics])
        ax.set_ylim(0, 1.05)
        ax.set_title(direction.replace("->", "$\\rightarrow$"), pad=5,
                     fontsize=8)
        tidy(ax)
    axes[0].set_ylabel("score")
    axes[-1].legend(frameon=False, ncol=2, fontsize=6.8)
    save(fig, "fig_transfer.pdf")


def fig_serving():
    """Latency distribution and throughput against concurrency. Two stacked
    panels sharing x rather than one plot with two y axes."""
    d = load("S9_serving")
    if not d or not d.get("single"):
        return
    rows = sorted(d["single"], key=lambda r: r["concurrency"])
    c = [r["concurrency"] for r in rows]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(WIDTH, 3.4), sharex=True,
                                   gridspec_kw={"height_ratios": [1.25, 1]})
    for key, lab, col, mk in (
            ("p50", "p50", "#2a78d6", "o"),
            ("p95", "p95", "#eb6834", "s"),
            ("p99", "p99", "#1baf7a", "^")):
        ax1.plot(c, [r["latency_ms"][key] for r in rows], color=col,
                 marker=mk, markersize=3.5, linewidth=1.2, label=lab,
                 zorder=3)
    ax1.set_ylabel("latency (ms)")
    ax1.set_xscale("log", base=2)
    ax1.legend(frameon=False, ncol=3, loc="upper left")
    ax1.set_title("Measured service latency and throughput", pad=6)
    tidy(ax1)

    ax2.plot(c, [r["throughput_rps"] for r in rows], color=INK, marker="D",
             markersize=3.5, linewidth=1.2, zorder=3)
    ax2.set_ylabel("requests / s")
    ax2.set_xlabel("concurrent clients (log scale)")
    ax2.set_xticks(c)
    ax2.set_xticklabels([str(v) for v in c])
    tidy(ax2)
    save(fig, "fig_serving.pdf")

    if d.get("batch"):
        rows = sorted(d["batch"], key=lambda r: r["batch_size"])
        bs = [r["batch_size"] for r in rows]
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(WIDTH, 3.0), sharex=True)
        a1.plot(bs, [r["flows_per_s"] for r in rows], color="#2a78d6",
                marker="o", markersize=3.5, linewidth=1.2, zorder=3)
        a1.set_ylabel("flows / s")
        a1.set_title("Batching trades latency for throughput", pad=6)
        tidy(a1)
        a2.plot(bs, [r["latency_ms"]["p95"] for r in rows], color="#eb6834",
                marker="s", markersize=3.5, linewidth=1.2, zorder=3)
        a2.set_ylabel("p95 latency (ms)")
        a2.set_xlabel("batch size (log scale)")
        a2.set_xscale("log", base=2)
        a2.set_xticks(bs)
        a2.set_xticklabels([str(v) for v in bs])
        tidy(a2)
        save(fig, "fig_serving_batch.pdf")


def fig_confusion():
    """Where the errors move when the protocol changes."""
    d1, d2 = load("S1_holdout"), load("S2_day_disjoint")
    if not (d1 and d2):
        return
    target = "XGBoost"

    def agg(blob):
        rows = [r for r in blob["runs"] if r["model"] == target]
        if not rows:
            return None
        return np.array([[np.mean([r["tn"] for r in rows]),
                          np.mean([r["fp"] for r in rows])],
                         [np.mean([r["fn"] for r in rows]),
                          np.mean([r["tp"] for r in rows])]])

    A, B = agg(d1), agg(d2)
    if A is None or B is None:
        return
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.0))
    for ax, M, title in ((axes[0], A, "Random split"),
                         (axes[1], B, "Day-disjoint")):
        # Row-normalised: the question is what happens to an actual attack,
        # not how the class sizes compare.
        N = M / M.sum(axis=1, keepdims=True)
        ax.imshow(N, cmap="Blues", vmin=0, vmax=1)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, f"{N[i, j]:.3f}\n({M[i, j]:,.0f})",
                        ha="center", va="center", fontsize=6.5,
                        color="white" if N[i, j] > 0.55 else INK)
        ax.set_xticks([0, 1], ["pred. benign", "pred. attack"])
        ax.set_yticks([0, 1], ["benign", "attack"])
        ax.set_title(title, pad=5, fontsize=8)
        ax.tick_params(length=0)
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(False)
    fig.suptitle(f"{target}: row-normalised confusion, mean over seeds",
                 fontsize=8.5, y=1.04)
    save(fig, "fig_confusion.pdf")


def main():
    for fn in (fig_optimism_gap, fig_seed_spread, fig_ppv, fig_per_family,
               fig_leave_one_out, fig_cost, fig_feature_stability,
               fig_transfer, fig_serving, fig_confusion):
        try:
            fn()
        except Exception as exc:
            print(f"[error] {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\nFigures in {OUT}")


if __name__ == "__main__":
    main()
