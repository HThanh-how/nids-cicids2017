"""
Generate every LaTeX table in the paper directly from results_v3/*.json.

This exists to enforce one rule mechanically: a number may appear in the paper
only if an experiment produced it. Nothing is typed by hand, so the tables
cannot drift from the measurements, and a missing stage produces a missing
table rather than a stale one.

    python make_tables.py            # writes ../tables/*.tex

Each table is a standalone file included from main.tex with \\input.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results_v3")
OUT = os.path.join(os.path.dirname(HERE), "tables")
os.makedirs(OUT, exist_ok=True)

MODEL_ORDER = ["Logistic Regression", "Random Forest", "XGBoost", "MLP"]


def load(stage):
    p = os.path.join(RES, f"{stage}.json")
    if not os.path.exists(p):
        print(f"[skip] {stage}: not produced yet")
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def esc(s):
    # Some CICIDS2017 labels carry a cp1252 en-dash that survives as U+FFFD
    # ("Web Attack <?> Brute Force"). Normalising it here keeps the label
    # readable and keeps pdfLaTeX from choking on a non-ASCII byte.
    t = "".join(c if ord(c) < 128 else "-" for c in str(s))
    while "- -" in t:
        t = t.replace("- -", "-")
    return (t.replace("\\", r"\textbackslash{}").replace("_", r"\_")
            .replace("%", r"\%").replace("&", r"\&").replace("#", r"\#"))


def write(name, body):
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body.rstrip() + "\n")
    print(f"[written] tables/{name}")


def table(caption, label, colspec, header, rows, note=None, small=True):
    lines = [r"\begin{table}[t]", r"\centering",
             rf"\caption{{{caption}}}", rf"\label{{{label}}}"]
    if small:
        lines.append(r"\footnotesize")
    lines += [rf"\begin{{tabular}}{{{colspec}}}", r"\hline",
              " & ".join(header) + r" \\", r"\hline"]
    lines += [" & ".join(r) + r" \\" for r in rows]
    lines += [r"\hline", r"\end{tabular}"]
    if note:
        lines.append(rf"\par\smallskip\footnotesize {note}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def mean_ci(entry, digits=4):
    """mean +- half-width of the 95% interval, as reported by _summarise."""
    m = entry["mean"]
    half = entry["ci95_high"] - m
    return f"{m:.{digits}f}\\,$\\pm$\\,{half:.{digits}f}"


def models_in(summary):
    return [m for m in MODEL_ORDER if m in summary] + \
           [m for m in summary if m not in MODEL_ORDER]


# --------------------------------------------------------------------------
def t_environment():
    env, hp = load("S8_environment"), load("S8b_hyperparameters")
    if env:
        keys = [("python", "Python"), ("platform", "Operating system"),
                ("cpu_model", "CPU"), ("cpu_count", "Logical cores"),
                ("memory", "Memory"), ("scikit_learn", "scikit-learn"),
                ("xgboost", "XGBoost"), ("imbalanced_learn", "imbalanced-learn"),
                ("numpy", "NumPy"), ("pandas", "pandas")]
        rows = [[esc(lab), esc(str(env[k]).split(" (")[0])]
                for k, lab in keys if env.get(k) is not None]
        write("environment.tex", table(
            "Execution environment for every timing measurement reported in "
            "this paper.", "tab:env", "ll", ["Component", "Value"], rows))

    if hp:
        rows = []
        interesting = {
            "Logistic Regression": ["penalty", "C", "solver", "max_iter"],
            "Random Forest": ["n_estimators", "max_depth", "min_samples_split",
                              "min_samples_leaf", "max_features", "criterion"],
            "XGBoost": ["n_estimators", "max_depth", "learning_rate",
                        "subsample", "colsample_bytree", "reg_lambda",
                        "tree_method"],
            "MLP": ["hidden_layer_sizes", "activation", "solver", "alpha",
                    "batch_size", "learning_rate_init", "max_iter",
                    "early_stopping"],
        }
        for m in MODEL_ORDER:
            if m not in hp:
                continue
            p = hp[m]
            spec = ", ".join(f"{k}={p[k]}" for k in interesting[m] if k in p)
            rows.append([esc(m), esc(spec)])
        write("hyperparameters.tex", table(
            "Complete hyperparameter specification. No tuning was performed; "
            "the values are fixed a priori and identical across every split, "
            "seed and dataset.", "tab:hyper", "lp{8.2cm}",
            ["Model", "Setting"], rows))


def t_dataset():
    d = load("S0_dataset")
    if not d:
        return
    fam = sorted(d["family_counts"].items(), key=lambda kv: -kv[1])
    rows = [[esc(k), f"{v:,}", f"{100 * v / d['n_rows']:.3f}"] for k, v in fam]
    frac_pct = round(100 * d["sample_frac"])
    write("dataset.tex", table(
        f"CICIDS2017 composition after cleaning, at a {frac_pct}\\,\\% "
        f"stratified subsample: {d['n_rows']:,} flows, {d['n_features']} "
        f"numeric features, attack ratio {d['attack_ratio']:.4f}.",
        "tab:dataset", "lrr", ["Label", "Flows", "Share (\\%)"], rows))

    dr = [[esc(k), f"{v:,}"] for k, v in sorted(d["day_counts"].items())]
    write("days.tex", table(
        "Flows per capture day. The day-disjoint protocol trains on "
        "Monday--Wednesday and tests on Thursday--Friday.",
        "tab:days", "lr", ["Capture day", "Flows"], dr))


PERF_COLS = ["accuracy", "macro_f1", "recall_attack", "precision_attack",
             "pr_auc", "mcc", "fpr"]
PERF_HEAD = ["Model", "Accuracy", "Macro-F1", "Recall", "Precision",
             "PR-AUC", "MCC", "FPR"]


def _perf_rows(summary, cols):
    rows = []
    for m in models_in(summary):
        s = summary[m]
        rows.append([esc(m)] + [mean_ci(s[c], 4 if c != "fpr" else 5)
                                for c in cols])
    return rows


def t_holdout():
    d = load("S1_holdout")
    if not d:
        return
    cfg = d["config"]
    # A bare "%" would comment out the rest of the caption line in LaTeX.
    tr_pct = round(100 * (1 - cfg["test_size"]))
    te_pct = round(100 * cfg["test_size"])
    write("holdout.tex", table(
        f"Repeated stratified holdout on CICIDS2017: mean $\\pm$ half-width of "
        f"the 95\\,\\% confidence interval over {len(cfg['seeds'])} seeds, "
        f"{tr_pct}\\,\\%/{te_pct}\\,\\% splits. Feature "
        f"selection, SMOTE and scaling are re-fitted inside every training "
        f"split.", "tab:holdout", "l" + "c" * len(PERF_COLS),
        PERF_HEAD, _perf_rows(d["summary"], PERF_COLS)))

    pt = d.get("paired_tests", {})
    rows = []
    for pair, v in pt.items():
        rows.append([esc(pair), f"{v['mean_diff_macro_f1']:+.5f}",
                     f"{v['t_stat']:.2f}", f"{v['p_value_paired_t']:.4f}",
                     f"{v['p_value_wilcoxon']:.4f}", str(v["n_seeds"])])
    if rows:
        write("paired_tests.tex", table(
            "Paired comparison of macro-F1 across the shared seeds. Positive "
            "differences favour the first model. Small absolute differences "
            "may still be statistically detectable; the paper reports both.",
            "tab:paired", "lrrrrr",
            ["Comparison", "$\\Delta$ macro-F1", "$t$", "$p$ (paired $t$)",
             "$p$ (Wilcoxon)", "$n$"], rows))


def t_day_disjoint():
    d2, d1 = load("S2_day_disjoint"), load("S1_holdout")
    if not d2:
        return
    write("day_disjoint.tex", table(
        "Day-disjoint evaluation: trained on "
        f"{'--'.join(d2['train_days'])}, tested on "
        f"{'--'.join(d2['test_days'])}. On CICIDS2017 each attack family is "
        "confined to a single capture day, so this split is also "
        "family-disjoint: every attack in the test set is of a type absent "
        "from training.", "tab:daydisjoint", "l" + "c" * len(PERF_COLS),
        PERF_HEAD, _perf_rows(d2["summary"], PERF_COLS)))

    if d1:
        rows = []
        for m in models_in(d2["summary"]):
            if m not in d1["summary"]:
                continue
            a = d1["summary"][m]["macro_f1"]["mean"]
            b = d2["summary"][m]["macro_f1"]["mean"]
            ra = d1["summary"][m]["recall_attack"]["mean"]
            rb = d2["summary"][m]["recall_attack"]["mean"]
            rows.append([esc(m), f"{a:.4f}", f"{b:.4f}", f"{b - a:+.4f}",
                         f"{ra:.4f}", f"{rb:.4f}", f"{rb - ra:+.4f}"])
        write("optimism_gap.tex", table(
            "The optimism of a random split. Same pipeline, same "
            "hyperparameters, same data; only the split protocol differs. "
            "The gap is the quantity this paper reports.",
            "tab:gap", "lrrrrrr",
            ["Model", "F1 random", "F1 day-disj.", "$\\Delta$",
             "Recall random", "Recall day-disj.", "$\\Delta$"], rows))


def t_family():
    d = load("S3_per_family")
    if not d:
        return
    per = d["per_family_random_split"]
    fams = sorted({f for m in per.values() for f in m})
    models = models_in(per)
    rows = []
    for f in fams:
        cells = []
        n = None
        for m in models:
            e = per[m].get(f, {})
            n = e.get("n", n)
            v = e.get("recall", e.get("false_positive_rate"))
            cells.append(f"{v:.4f}" if v is not None else "--")
        rows.append([esc(f), f"{n:,}" if n else "--"] + cells)
    write("per_family.tex", table(
        "Per-family detection rate under the random split. The BENIGN row "
        "reports the false-positive rate; all other rows report recall. "
        "Binary aggregation hides the spread shown here.",
        "tab:family", "lr" + "c" * len(models),
        ["Label", "$n$"] + [esc(m) for m in models], rows))

    loo = d.get("leave_one_family_out_xgboost", {})
    if loo:
        rows = [[esc(k), f"{v['n_heldout']:,}", f"{v['unseen_recall']:.4f}"]
                for k, v in sorted(loo.items(),
                                   key=lambda kv: kv[1]["unseen_recall"])]
        write("leave_one_out.tex", table(
            "Leave-one-family-out with XGBoost: the held-out family is removed "
            "from training entirely, so the score is the detector's ability to "
            "flag an attack type it has never seen.",
            "tab:loo", "lrr",
            ["Held-out family", "$n$", "Recall on unseen family"], rows))


def t_features():
    d = load("S4_feature_stability")
    if not d:
        return
    ov = d["criterion_overlap"]
    rows = [["Mean pairwise Jaccard across seeds",
             f"{d['mean_pairwise_jaccard']:.3f}"],
            ["Features selected by every seed",
             f"{len(d['always_selected'])} of {len(d['impurity_top'])}"],
            ["Overlap: impurity vs.\\ permutation",
             f"{ov['impurity_vs_permutation']:.2f}"],
            ["Overlap: impurity vs.\\ mutual information",
             f"{ov['impurity_vs_mutual_info']:.2f}"],
            ["Overlap: permutation vs.\\ mutual information",
             f"{ov['permutation_vs_mutual_info']:.2f}"]]
    write("feature_stability.tex", table(
        "Stability and criterion-dependence of the selected feature set. A "
        "high seed-to-seed Jaccard with a low agreement between criteria means "
        "the selection is reproducible but not canonical.",
        "tab:featstab", "lr", ["Quantity", "Value"], rows))

    core = d["always_selected"]
    rows = [[str(i + 1), esc(f), "yes" if f in core else "no"]
            for i, f in enumerate(d["impurity_top"])]
    write("feature_list.tex", table(
        "The selected features, ranked by impurity importance on the reference "
        "seed, with an indication of whether every seed selected them.",
        "tab:featlist", "rll", ["Rank", "Feature", "All seeds"], rows))


def t_unsw():
    d = load("S5_unsw_replication")
    if not d:
        return
    write("unsw.tex", table(
        "Independent-dataset replication on UNSW-NB15. Models are trained and "
        "tested \\emph{within} UNSW-NB15 under the identical pipeline; this "
        "checks whether the ordering of models replicates on independent data "
        "and makes no claim about transfer.",
        "tab:unsw", "l" + "c" * len(PERF_COLS), PERF_HEAD,
        _perf_rows(d["summary"], PERF_COLS)))


def t_transfer():
    d = load("S6_transfer")
    if not d:
        return
    if "error" in d:
        print("[skip] S6: " + str(d["error"]))
        return
    al = d["aligned_features"]
    rows = []
    for direction, per in d["results"].items():
        for m in models_in(per):
            e = per[m]
            rows.append([esc(direction), esc(m), f"{e['accuracy']:.4f}",
                         f"{e['macro_f1']:.4f}", f"{e['recall_attack']:.4f}",
                         f"{e['precision_attack']:.4f}", f"{e['fpr']:.4f}"])
    write("transfer.tex", table(
        f"Cross-dataset transfer on the {len(al)} aligned features: trained on "
        "one corpus, tested on the other, with no target-domain data. This is "
        "the experiment the earlier version of this work claimed but did not "
        "perform.", "tab:transfer", "llccccc",
        ["Direction", "Model", "Accuracy", "Macro-F1", "Recall", "Precision",
         "FPR"], rows))

    rows = [[esc(a["cicids"]), esc(a["unsw"]),
             ("$\\times 10^{-6}$" if abs(a["scale"] - 1e-6) < 1e-12
              else f"{a['scale']:g}")] for a in al]
    write("alignment.tex", table(
        "Feature alignment used for the transfer experiment. CICIDS2017 "
        "reports flow duration in microseconds and UNSW-NB15 in seconds, so "
        "the former is rescaled.", "tab:align", "lll",
        ["CICIDS2017", "UNSW-NB15", "Scale"], rows))


def t_operational():
    d = load("S7_operational")
    if not d:
        return
    pretty = {"S1_holdout": "Random split", "S2_day_disjoint": "Day-disjoint",
              "S5_unsw_replication": "UNSW-NB15"}
    rows = []
    for stage, per in d.items():
        for m in models_in(per):
            v = per[m]
            c = v["ppv_by_prevalence"]
            rows.append([
                esc(pretty.get(stage, stage)), esc(m),
                f"{v['tpr']:.4f}", f"{v['fpr']:.5f}",
                f"{c['0.1']['ppv']:.3f}", f"{c['0.01']['ppv']:.3f}",
                f"{c['0.001']['ppv']:.3f}", f"{c['0.0001']['ppv']:.4f}",
                f"{c['0.001']['false_alerts_per_million_flows']:,.0f}"])
    write("operational.tex", table(
        "Precision at operational prevalence. Benchmark attack ratios are far "
        "above what a production sensor sees, and precision degrades with "
        "prevalence even when TPR and FPR are held fixed. The last column is "
        "the analyst burden: false alerts per million flows at a "
        "0.1\\,\\% attack rate.", "tab:operational", "llrrrrrrr",
        ["Protocol", "Model", "TPR", "FPR", "PPV@10\\%", "PPV@1\\%",
         "PPV@0.1\\%", "PPV@0.01\\%", "FA/10$^6$"], rows))


def t_cost():
    d = load("S1_holdout")
    if not d:
        return
    rows = []
    for m in models_in(d["summary"]):
        s = d["summary"][m]
        rows.append([esc(m), mean_ci(s["train_s"], 2),
                     mean_ci(s["per_sample_ms"], 5)])
    write("cost.tex", table(
        "Training and amortised inference cost, measured with a discarded "
        "warm-up pass and five repeats per split on the environment of "
        "Table~\\ref{tab:env}. The per-sample figure is model cost amortised "
        "over a full test batch on all cores; it is a lower bound on service "
        "cost and is deliberately not converted into a throughput.",
        "tab:cost", "lrr",
        ["Model", "Training time (s)", "Amortised inference (ms/flow)"], rows))


def t_serving():
    d = load("S9_serving")
    if not d:
        return
    rows = []
    for r in d["single"]:
        lat = r["latency_ms"]
        rows.append([str(r["concurrency"]), f"{r['throughput_rps']:,.0f}",
                     f"{lat['p50']:.2f}", f"{lat['p95']:.2f}",
                     f"{lat['p99']:.2f}", f"{lat['p99.9']:.2f}",
                     f"{r['server_time_ms']['mean']:.3f}", str(r["errors"])])
    write("serving_latency.tex", table(
        "Measured end-to-end serving performance of the deployed service, "
        "single-flow endpoint, closed loop. The server-time column is the "
        "in-process scoring time reported by the service, so the difference "
        "from the p50 is queueing, parsing and transport.",
        "tab:serving", "rrrrrrrr",
        ["Clients", "Requests/s", "p50 (ms)", "p95 (ms)", "p99 (ms)",
         "p99.9 (ms)", "Server (ms)", "Errors"], rows))

    rows = []
    for r in d["batch"]:
        lat = r["latency_ms"]
        rows.append([str(r["batch_size"]), f"{r['throughput_rps']:,.0f}",
                     f"{r['flows_per_s']:,.0f}", f"{lat['p50']:.2f}",
                     f"{lat['p95']:.2f}", f"{lat['p99']:.2f}"])
    if rows:
        write("serving_batch.tex", table(
            "Batching trades latency for throughput. Flows per second is the "
            "quantity a deployment plan needs; request latency is what an "
            "inline sensor must tolerate.", "tab:servingbatch", "rrrrrr",
            ["Batch size", "Requests/s", "Flows/s", "p50 (ms)", "p95 (ms)",
             "p99 (ms)"], rows))


def main():
    for fn in (t_environment, t_dataset, t_holdout, t_day_disjoint, t_family,
               t_features, t_unsw, t_transfer, t_operational, t_cost,
               t_serving):
        try:
            fn()
        except Exception as exc:
            print(f"[error] {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\nTables in {OUT}")


if __name__ == "__main__":
    main()
