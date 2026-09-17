"""
IDS benchmark v3 -- experimental protocol rebuilt to answer the ICTA 2026
reviewer report (submission 153).

What changed vs. v2 and which reviewer concern each stage answers:

  S1  Repeated stratified holdout, 5 seeds, ALL models, full pipeline
      (selection + SMOTE + scaling) re-fitted inside every training split,
      paired t-test + bootstrap CI.                      -> R1.4, R1.5
  S2  Day-disjoint evaluation (train Mon-Wed / test Thu-Fri): no flow from a
      capture day appears on both sides.                 -> R1.3
  S3  Per-attack-family recall + leave-one-family-out.   -> R1.6
  S4  Feature-selection stability (Jaccard across seeds) + impurity vs
      permutation vs mutual information.                 -> R1.10
  S5  UNSW-NB15 INDEPENDENT-DATASET REPLICATION (renamed; it was never
      cross-dataset transfer).                           -> R1.2, R2.3
  S6  TRUE cross-dataset transfer on an aligned feature space, both
      directions.                                        -> R1.2
  S7  Operational analysis: PPV/alert burden at realistic low prevalence,
      FPR/FNR/MCC/balanced accuracy/PR-AUC.              -> R1.7
  S8  Controlled timing (warm-up + repeats) and full environment capture.
                                                          -> R1.8, R1.5, R2.2

Every stage checkpoints to results_v3/<stage>.json so a Colab timeout never
costs more than one stage. Nothing here invents numbers: the JSON files are
the only thing that may be quoted in the paper.
"""

import glob
import json
import os
import platform
import subprocess
import sys
import time

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Configuration -- every value here must be reported in the paper.
# --------------------------------------------------------------------------
# The defaults are what the paper reports. SAMPLE_FRAC and OUT_DIR can be
# overridden from the environment so the same protocol can be re-run at full
# scale into a separate directory as a robustness check, without touching the
# reported results.
SAMPLE_FRAC = float(os.environ.get("SAMPLE_FRAC", "0.20"))
TOP_K = 20                  # features kept by the selector
SEEDS_HOLDOUT = [int(x) for x in
                 os.environ.get("SEEDS_HOLDOUT", "42,1,2,3,4").split(",")]
SEEDS_DAY = [int(x) for x in os.environ.get("SEEDS_DAY", "42,1,2").split(",")]
TEST_SIZE = 0.30
OUT_DIR = os.environ.get("OUT_DIR", "results_v3")
STAGES = os.environ.get("STAGES", "S1,S2,S3,S4,S5,S6,S7,S8").split(",")

CICIDS_REPO = "c01dsnap/CIC-IDS2017"
UNSW_REPO = "Mouwiya/UNSW-NB15"

os.makedirs(OUT_DIR, exist_ok=True)


def save(stage, obj):
    path = os.path.join(OUT_DIR, f"{stage}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=float)
    print(f"[saved] {path}")


def load(stage):
    path = os.path.join(OUT_DIR, f"{stage}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


# --------------------------------------------------------------------------
# Models -- hyperparameters are fixed here so the paper can report them in
# full (reviewer 1, concern 5). No tuning is performed; this is deliberate
# and stated as a limitation.
# --------------------------------------------------------------------------
def build_models(seed):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neural_network import MLPClassifier
    from xgboost import XGBClassifier

    return {
        "Logistic Regression": LogisticRegression(
            penalty="l2", C=1.0, solver="lbfgs", max_iter=1000,
            random_state=seed, n_jobs=-1),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=None, min_samples_split=2,
            min_samples_leaf=1, max_features="sqrt", criterion="gini",
            n_jobs=-1, random_state=seed),
        "XGBoost": XGBClassifier(
            n_estimators=300, max_depth=8, learning_rate=0.3,
            subsample=1.0, colsample_bytree=1.0, reg_lambda=1.0,
            tree_method="hist", eval_metric="logloss", n_jobs=-1,
            random_state=seed),
        "MLP": MLPClassifier(
            hidden_layer_sizes=(128, 64), activation="relu", solver="adam",
            alpha=1e-4, batch_size=200, learning_rate_init=1e-3,
            max_iter=50, early_stopping=True, n_iter_no_change=5,
            validation_fraction=0.1, random_state=seed),
    }


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
DAY_OF = {
    "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed",
    "thursday": "Thu", "friday": "Fri",
}


def day_from_filename(name):
    low = os.path.basename(name).lower()
    for key, day in DAY_OF.items():
        if low.startswith(key):
            return day
    return "Unknown"


def fetch_cicids():
    """Load the 8 MachineLearningCVE CSVs, tagging each flow with its capture
    day and keeping the original multi-class label."""
    from huggingface_hub import list_repo_files, hf_hub_download

    files = [f for f in list_repo_files(CICIDS_REPO, repo_type="dataset")
             if f.lower().endswith(".csv")]
    print(f"CICIDS2017: {len(files)} CSV files on the hub")

    frames = []
    for f in sorted(files):
        local = hf_hub_download(CICIDS_REPO, f, repo_type="dataset")
        part = pd.read_csv(local, low_memory=False)
        part.columns = part.columns.str.strip()
        label_col = "Label" if "Label" in part.columns else part.columns[-1]
        part = part.rename(columns={label_col: "Label"})
        if SAMPLE_FRAC < 1.0:
            part = part.sample(frac=SAMPLE_FRAC, random_state=42)
        part["day"] = day_from_filename(f)
        frames.append(part)
        print(f"  {os.path.basename(f)[:52]:52s} {part.shape} day={part['day'].iloc[0]}")

    df = pd.concat(frames, ignore_index=True)
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    df = df.drop_duplicates()

    y = (df["Label"].astype(str).str.upper().str.strip() != "BENIGN").astype(int)
    family = df["Label"].astype(str).str.strip()
    day = df["day"].astype(str)
    X = (df.drop(columns=["Label", "day"])
           .select_dtypes(include=[np.number])
           .replace([np.inf, -np.inf], np.nan)
           .fillna(0.0))
    print(f"CICIDS2017 final: {X.shape}, attack ratio {y.mean():.4f}")
    print(day.value_counts().to_string())
    return X.reset_index(drop=True), y.reset_index(drop=True), \
        family.reset_index(drop=True), day.reset_index(drop=True)


def fetch_unsw():
    from huggingface_hub import list_repo_files, hf_hub_download

    files = list_repo_files(UNSW_REPO, repo_type="dataset")
    train = [f for f in files if "train" in f.lower() and f.lower().endswith(".csv")]
    target = sorted(train or [f for f in files if f.lower().endswith(".csv")])[0]
    local = hf_hub_download(UNSW_REPO, target, repo_type="dataset")
    df = pd.read_csv(local, low_memory=False)
    df.columns = df.columns.str.strip()

    label_col = "label" if "label" in df.columns else df.columns[-1]
    y = df[label_col].astype(int)
    family = (df["attack_cat"].astype(str).str.strip()
              if "attack_cat" in df.columns else pd.Series(["?"] * len(df)))
    drop = [c for c in [label_col, "attack_cat", "id"] if c in df.columns]
    X_raw = df.drop(columns=drop)
    X = pd.get_dummies(X_raw, columns=[c for c in X_raw.columns
                                       if X_raw[c].dtype == object],
                       drop_first=True)
    X = X.select_dtypes(include=[np.number]).replace(
        [np.inf, -np.inf], np.nan).fillna(0.0)
    print(f"UNSW-NB15: {X.shape}, attack ratio {y.mean():.4f}")
    return X.reset_index(drop=True), y.reset_index(drop=True), \
        family.reset_index(drop=True)


# --------------------------------------------------------------------------
# Pipeline: selection + scaling + SMOTE, all fitted on the training half only
# and re-fitted for every split (reviewer 1, concern 5).
# --------------------------------------------------------------------------
def fit_pipeline(X_tr, y_tr, X_te, seed, top_k=TOP_K):
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier

    scaler = StandardScaler().fit(X_tr)
    X_tr_s, X_te_s = scaler.transform(X_tr), scaler.transform(X_te)

    selector = RandomForestClassifier(
        n_estimators=100, n_jobs=-1, random_state=seed).fit(X_tr_s, y_tr)
    order = np.argsort(selector.feature_importances_)[::-1][:top_k]
    names = [X_tr.columns[i] for i in order]

    from imblearn.over_sampling import SMOTE
    X_bal, y_bal = SMOTE(random_state=seed).fit_resample(X_tr_s[:, order], y_tr)
    return X_bal, y_bal, X_te_s[:, order], names


def evaluate(y_true, y_pred, y_score):
    """Full operational metric set (reviewer 1, concern 7)."""
    from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                                 f1_score, roc_auc_score, average_precision_score,
                                 matthews_corrcoef, balanced_accuracy_score,
                                 confusion_matrix)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_attack": precision_score(y_true, y_pred, zero_division=0),
        "recall_attack": recall_score(y_true, y_pred, zero_division=0),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "roc_auc": roc_auc_score(y_true, y_score) if len(set(y_true)) > 1 else float("nan"),
        "pr_auc": average_precision_score(y_true, y_score) if len(set(y_true)) > 1 else float("nan"),
        "mcc": matthews_corrcoef(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "fpr": fp / (fp + tn) if (fp + tn) else float("nan"),
        "fnr": fn / (fn + tp) if (fn + tp) else float("nan"),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def timed_fit_predict(clf, X_tr, y_tr, X_te, timing_repeats=5):
    """Train once, then measure inference with a warm-up pass and repeats
    (reviewer 1, concern 8; reviewer 2, concern 2)."""
    t0 = time.perf_counter()
    clf.fit(X_tr, y_tr)
    train_s = time.perf_counter() - t0

    clf.predict(X_te[:1000])                       # warm-up, discarded
    durations = []
    for _ in range(timing_repeats):
        t0 = time.perf_counter()
        y_pred = clf.predict(X_te)
        durations.append(time.perf_counter() - t0)
    batch_s = float(np.mean(durations))
    y_score = (clf.predict_proba(X_te)[:, 1] if hasattr(clf, "predict_proba")
               else clf.decision_function(X_te))
    return y_pred, y_score, {
        "train_s": train_s,
        "batch_infer_s_mean": batch_s,
        "batch_infer_s_std": float(np.std(durations)),
        "n_test": int(len(X_te)),
        "per_sample_ms": 1000.0 * batch_s / len(X_te),
        "batch_throughput_per_s": len(X_te) / batch_s,
        "timing_repeats": timing_repeats,
    }


# --------------------------------------------------------------------------
# S1 -- repeated stratified holdout, all models, all seeds
# --------------------------------------------------------------------------
def stage1(X, y):
    from sklearn.model_selection import train_test_split

    runs = []
    for seed in SEEDS_HOLDOUT:
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=TEST_SIZE, stratify=y, random_state=seed)
        X_bal, y_bal, X_te_k, feats = fit_pipeline(X_tr, y_tr, X_te, seed)
        print(f"[S1] seed={seed} train={X_bal.shape} test={X_te_k.shape}")
        for name, clf in build_models(seed).items():
            y_pred, y_score, cost = timed_fit_predict(clf, X_bal, y_bal, X_te_k)
            row = {"seed": seed, "model": name, "features": feats}
            row.update(evaluate(y_te.values, y_pred, y_score))
            row.update(cost)
            runs.append(row)
            print(f"    {name:22s} F1={row['macro_f1']:.4f} "
                  f"FPR={row['fpr']:.5f} train={cost['train_s']:.1f}s")

    summary = _summarise(runs)
    stats = _paired_tests(runs)
    save("S1_holdout", {"runs": runs, "summary": summary, "paired_tests": stats,
                        "config": {"seeds": SEEDS_HOLDOUT, "test_size": TEST_SIZE,
                                   "top_k": TOP_K, "sample_frac": SAMPLE_FRAC}})
    return runs


def _summarise(runs):
    df = pd.DataFrame(runs)
    keep = ["accuracy", "precision_attack", "recall_attack", "macro_f1",
            "roc_auc", "pr_auc", "mcc", "balanced_accuracy", "fpr", "fnr",
            "train_s", "per_sample_ms"]
    out = {}
    for model, grp in df.groupby("model"):
        entry = {}
        for col in keep:
            vals = grp[col].astype(float).values
            mean, std, n = vals.mean(), vals.std(ddof=1) if len(vals) > 1 else 0.0, len(vals)
            half = 1.96 * std / np.sqrt(n) if n > 1 else 0.0
            entry[col] = {"mean": mean, "std": std, "n": n,
                          "ci95_low": mean - half, "ci95_high": mean + half}
        out[model] = entry
    return out


def _paired_tests(runs):
    """Paired comparison of macro-F1 across the shared seeds -- the reviewer
    asked whether XGBoost is *significantly* better than Random Forest."""
    from scipy import stats as sps

    df = pd.DataFrame(runs)
    pivot = df.pivot_table(index="seed", columns="model", values="macro_f1")
    out = {}
    models = list(pivot.columns)
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            d = (pivot[a] - pivot[b]).dropna().values
            if len(d) < 2:
                continue
            t, p = sps.ttest_rel(pivot[a].values, pivot[b].values)
            try:
                _, p_w = sps.wilcoxon(pivot[a].values, pivot[b].values)
            except ValueError:
                p_w = float("nan")
            out[f"{a} vs {b}"] = {
                "mean_diff_macro_f1": float(d.mean()),
                "std_diff": float(d.std(ddof=1)),
                "t_stat": float(t), "p_value_paired_t": float(p),
                "p_value_wilcoxon": float(p_w), "n_seeds": int(len(d)),
            }
    return out


# --------------------------------------------------------------------------
# S2 -- day-disjoint evaluation
# --------------------------------------------------------------------------
TRAIN_DAYS = ["Mon", "Tue", "Wed"]
TEST_DAYS = ["Thu", "Fri"]


def stage2(X, y, family, day):
    tr_mask = day.isin(TRAIN_DAYS).values
    te_mask = day.isin(TEST_DAYS).values
    X_tr, y_tr = X[tr_mask], y[tr_mask]
    X_te, y_te = X[te_mask], y[te_mask]
    print(f"[S2] day-disjoint: train {X_tr.shape} ({sorted(set(family[tr_mask]))})")
    print(f"[S2]               test  {X_te.shape} ({sorted(set(family[te_mask]))})")

    runs = []
    for seed in SEEDS_DAY:
        X_bal, y_bal, X_te_k, feats = fit_pipeline(X_tr, y_tr, X_te, seed)
        for name, clf in build_models(seed).items():
            y_pred, y_score, cost = timed_fit_predict(clf, X_bal, y_bal, X_te_k)
            row = {"seed": seed, "model": name, "features": feats}
            row.update(evaluate(y_te.values, y_pred, y_score))
            row.update(cost)
            runs.append(row)
            print(f"    seed={seed} {name:22s} F1={row['macro_f1']:.4f} "
                  f"recall={row['recall_attack']:.4f} FPR={row['fpr']:.5f}")

    save("S2_day_disjoint", {
        "runs": runs, "summary": _summarise(runs),
        "train_days": TRAIN_DAYS, "test_days": TEST_DAYS,
        "train_families": sorted(set(family[tr_mask])),
        "test_families": sorted(set(family[te_mask])),
        "note": ("On CICIDS2017 each attack family is confined to one capture "
                 "day, so a day-disjoint split is necessarily also "
                 "family-disjoint: the test attacks are unseen types."),
    })
    return runs


# --------------------------------------------------------------------------
# S3 -- per-family recall and leave-one-family-out
# --------------------------------------------------------------------------
def stage3(X, y, family):
    from sklearn.model_selection import train_test_split

    seed = 42
    idx = np.arange(len(X))
    i_tr, i_te = train_test_split(idx, test_size=TEST_SIZE, stratify=y,
                                  random_state=seed)
    X_tr, X_te = X.iloc[i_tr], X.iloc[i_te]
    y_tr, y_te = y.iloc[i_tr], y.iloc[i_te]
    fam_te = family.iloc[i_te]
    X_bal, y_bal, X_te_k, _ = fit_pipeline(X_tr, y_tr, X_te, seed)

    per_family = {}
    for name, clf in build_models(seed).items():
        clf.fit(X_bal, y_bal)
        pred = clf.predict(X_te_k)
        stats = {}
        for fam in sorted(fam_te.unique()):
            m = (fam_te == fam).values
            if fam.upper() == "BENIGN":
                stats[fam] = {"n": int(m.sum()),
                              "false_positive_rate": float((pred[m] == 1).mean())}
            else:
                stats[fam] = {"n": int(m.sum()),
                              "recall": float((pred[m] == 1).mean())}
        per_family[name] = stats
        worst = sorted(((v.get("recall", 1.0), k) for k, v in stats.items()
                        if "recall" in v))[:3]
        print(f"[S3] {name:22s} weakest families: {worst}")

    # Leave-one-family-out: can the detector flag an attack type it never saw?
    loo = {}
    families = [f for f in family.unique() if f.upper() != "BENIGN"]
    for held in families:
        keep = ~((family == held).values)
        X_tr2, y_tr2 = X[keep], y[keep]
        X_ho = X[(family == held).values]
        if len(X_ho) < 50:
            continue
        i_tr2, i_te2 = train_test_split(np.arange(len(X_tr2)), test_size=TEST_SIZE,
                                        stratify=y_tr2, random_state=42)
        X_bal2, y_bal2, X_ho_k, _ = fit_pipeline(
            X_tr2.iloc[i_tr2], y_tr2.iloc[i_tr2], X_ho, 42)
        clf = build_models(42)["XGBoost"]
        clf.fit(X_bal2, y_bal2)
        loo[held] = {"n_heldout": int(len(X_ho)),
                     "unseen_recall": float((clf.predict(X_ho_k) == 1).mean())}
        print(f"[S3] leave-out {held:28s} unseen recall={loo[held]['unseen_recall']:.4f}")

    save("S3_per_family", {"per_family_random_split": per_family,
                           "leave_one_family_out_xgboost": loo})
    return per_family, loo


# --------------------------------------------------------------------------
# S4 -- feature-selection stability and alternative importance criteria
# --------------------------------------------------------------------------
def stage4(X, y):
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_selection import mutual_info_classif
    from sklearn.inspection import permutation_importance

    per_seed = {}
    for seed in SEEDS_HOLDOUT:
        X_tr, _, y_tr, _ = train_test_split(X, y, test_size=TEST_SIZE,
                                            stratify=y, random_state=seed)
        scaler = StandardScaler().fit(X_tr)
        rf = RandomForestClassifier(n_estimators=100, n_jobs=-1,
                                    random_state=seed).fit(scaler.transform(X_tr), y_tr)
        order = np.argsort(rf.feature_importances_)[::-1][:TOP_K]
        per_seed[seed] = [X.columns[i] for i in order]

    keys = list(per_seed)
    jac = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            sa, sb = set(per_seed[a]), set(per_seed[b])
            jac.append(len(sa & sb) / len(sa | sb))
    core = set(per_seed[keys[0]])
    for k in keys[1:]:
        core &= set(per_seed[k])
    print(f"[S4] mean pairwise Jaccard = {np.mean(jac):.3f}, "
          f"{len(core)}/{TOP_K} features selected by every seed")

    # Alternative criteria on a subsample (permutation importance is costly).
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=TEST_SIZE,
                                              stratify=y, random_state=42)
    sub = min(60000, len(X_tr))
    Xs = StandardScaler().fit_transform(X_tr.iloc[:sub])
    ys = y_tr.iloc[:sub]
    mi = mutual_info_classif(Xs, ys, random_state=42)
    mi_top = [X.columns[i] for i in np.argsort(mi)[::-1][:TOP_K]]

    rf = RandomForestClassifier(n_estimators=100, n_jobs=-1,
                                random_state=42).fit(Xs, ys)
    perm = permutation_importance(rf, Xs[:20000], ys.iloc[:20000],
                                  n_repeats=5, random_state=42, n_jobs=-1)
    perm_top = [X.columns[i] for i in np.argsort(perm.importances_mean)[::-1][:TOP_K]]

    imp_top = per_seed[42]
    agree = {
        "impurity_vs_permutation": len(set(imp_top) & set(perm_top)) / TOP_K,
        "impurity_vs_mutual_info": len(set(imp_top) & set(mi_top)) / TOP_K,
        "permutation_vs_mutual_info": len(set(perm_top) & set(mi_top)) / TOP_K,
    }
    print(f"[S4] top-{TOP_K} overlap between criteria: {agree}")

    save("S4_feature_stability", {
        "top_k_per_seed": {str(k): v for k, v in per_seed.items()},
        "mean_pairwise_jaccard": float(np.mean(jac)),
        "always_selected": sorted(core),
        "impurity_top": imp_top, "permutation_top": perm_top,
        "mutual_info_top": mi_top, "criterion_overlap": agree,
        "permutation_subsample": int(sub),
    })


# --------------------------------------------------------------------------
# S5 -- UNSW-NB15 independent-dataset replication (NOT transfer)
# --------------------------------------------------------------------------
def stage5():
    from sklearn.model_selection import train_test_split

    Xu, yu, _ = fetch_unsw()
    runs = []
    for seed in SEEDS_HOLDOUT:
        X_tr, X_te, y_tr, y_te = train_test_split(
            Xu, yu, test_size=TEST_SIZE, stratify=yu, random_state=seed)
        X_bal, y_bal, X_te_k, feats = fit_pipeline(X_tr, y_tr, X_te, seed)
        for name, clf in build_models(seed).items():
            y_pred, y_score, cost = timed_fit_predict(clf, X_bal, y_bal, X_te_k)
            row = {"seed": seed, "model": name, "features": feats}
            row.update(evaluate(y_te.values, y_pred, y_score))
            row.update(cost)
            runs.append(row)
            print(f"[S5] seed={seed} {name:22s} F1={row['macro_f1']:.4f}")

    save("S5_unsw_replication", {
        "runs": runs, "summary": _summarise(runs),
        "paired_tests": _paired_tests(runs),
        "note": ("Models are trained and tested within UNSW-NB15. This is an "
                 "independent-dataset replication of the ranking, not a "
                 "transfer experiment."),
    })
    return runs


# --------------------------------------------------------------------------
# S6 -- true cross-dataset transfer on an aligned feature space
# --------------------------------------------------------------------------
# Documented alignment. CICIDS2017 'Flow Duration' is microseconds, UNSW
# 'dur' is seconds, so the CICIDS column is divided by 1e6.
ALIGN = [
    ("Flow Duration", "dur", 1e-6),
    ("Total Fwd Packets", "spkts", 1.0),
    ("Total Backward Packets", "dpkts", 1.0),
    ("Total Length of Fwd Packets", "sbytes", 1.0),
    ("Total Length of Bwd Packets", "dbytes", 1.0),
    ("Fwd Packet Length Mean", "smean", 1.0),
    ("Bwd Packet Length Mean", "dmean", 1.0),
]


def stage6(Xc, yc):
    from sklearn.preprocessing import StandardScaler
    from imblearn.over_sampling import SMOTE

    Xu_raw, yu, _ = fetch_unsw()
    c_cols = [c for c, _, _ in ALIGN if c in Xc.columns]
    u_cols = [u for c, u, _ in ALIGN if c in Xc.columns and u in Xu_raw.columns]
    pairs = [(c, u, s) for c, u, s in ALIGN
             if c in Xc.columns and u in Xu_raw.columns]
    if len(pairs) < 4:
        save("S6_transfer", {"error": "insufficient aligned features",
                             "cicids_available": c_cols,
                             "unsw_available": list(Xu_raw.columns)})
        return
    print(f"[S6] aligned feature space ({len(pairs)}): "
          f"{[(c, u) for c, u, _ in pairs]}")

    A = pd.DataFrame({u: Xc[c].astype(float) * s for c, u, s in pairs})
    B = Xu_raw[[u for _, u, _ in pairs]].astype(float)

    results = {}
    for tag, (Xs, ys, Xt, yt) in {
        "cicids2017 -> unsw-nb15": (A, yc, B, yu),
        "unsw-nb15 -> cicids2017": (B, yu, A, yc),
    }.items():
        scaler = StandardScaler().fit(Xs)
        Xs_s, Xt_s = scaler.transform(Xs), scaler.transform(Xt)
        Xb, yb = SMOTE(random_state=42).fit_resample(Xs_s, ys)
        row = {}
        for name, clf in build_models(42).items():
            clf.fit(Xb, yb)
            pred = clf.predict(Xt_s)
            score = (clf.predict_proba(Xt_s)[:, 1] if hasattr(clf, "predict_proba")
                     else clf.decision_function(Xt_s))
            row[name] = evaluate(np.asarray(yt), pred, score)
            print(f"[S6] {tag} {name:22s} F1={row[name]['macro_f1']:.4f} "
                  f"recall={row[name]['recall_attack']:.4f}")
        results[tag] = row

    save("S6_transfer", {
        "aligned_features": [{"cicids": c, "unsw": u, "scale": s}
                             for c, u, s in pairs],
        "results": results,
        "note": ("Train on one dataset, test on the other, using only the "
                 "aligned feature subset. This is the transfer experiment the "
                 "earlier version claimed but did not perform."),
    })


# --------------------------------------------------------------------------
# S7 -- operational analysis at realistic prevalence
# --------------------------------------------------------------------------
def stage7():
    """Benchmark prevalence is far above operational reality. Given a measured
    TPR/FPR, precision at prevalence pi is pi*TPR / (pi*TPR + (1-pi)*FPR)."""
    out = {}
    for stage in ("S1_holdout", "S2_day_disjoint", "S5_unsw_replication"):
        blob = load(stage)
        if not blob:
            continue
        per_model = {}
        for model, s in blob["summary"].items():
            tpr = s["recall_attack"]["mean"]
            fpr = s["fpr"]["mean"]
            curve = {}
            for pi in (0.1, 0.01, 0.001, 0.0001):
                denom = pi * tpr + (1 - pi) * fpr
                curve[str(pi)] = {
                    "ppv": (pi * tpr / denom) if denom else float("nan"),
                    "false_alerts_per_million_flows": (1 - pi) * fpr * 1e6,
                    "true_alerts_per_million_flows": pi * tpr * 1e6,
                }
            per_model[model] = {"tpr": tpr, "fpr": fpr, "ppv_by_prevalence": curve}
        out[stage] = per_model
        for model, v in per_model.items():
            p = v["ppv_by_prevalence"]["0.001"]["ppv"]
            print(f"[S7] {stage:20s} {model:22s} PPV@0.1%prev = {p:.4f}")
    save("S7_operational", out)


# --------------------------------------------------------------------------
# S8 -- environment capture
# --------------------------------------------------------------------------
def stage8():
    import sklearn
    info = {
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "numpy": np.__version__, "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
    }
    try:
        import xgboost
        info["xgboost"] = xgboost.__version__
    except Exception:
        pass
    try:
        import imblearn
        info["imbalanced_learn"] = imblearn.__version__
    except Exception:
        pass
    if os.name == "nt":
        info["cpu_model"] = os.environ.get("PROCESSOR_IDENTIFIER")
        try:
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = _MS()
            st.dwLength = ctypes.sizeof(_MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            info["memory"] = f"{st.ullTotalPhys / 2**30:.1f} GiB total"
        except Exception:
            info["memory"] = None
    else:
        for cmd, key in ((["cat", "/proc/cpuinfo"], "cpu_model"),
                         (["free", "-h"], "memory")):
            try:
                txt = subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=10).stdout
                if key == "cpu_model":
                    line = [l for l in txt.splitlines() if "model name" in l]
                    info[key] = line[0].split(":", 1)[1].strip() if line else None
                else:
                    info[key] = txt.strip().splitlines()[1] if txt else None
            except Exception:
                info[key] = None
    print(json.dumps(info, indent=2))
    save("S8_environment", info)


# --------------------------------------------------------------------------
def main():
    print(f"Stages to run: {STAGES}")
    stage8() if "S8" in STAGES else None

    need_cicids = any(s in STAGES for s in ("S1", "S2", "S3", "S4", "S6"))
    if need_cicids:
        X, y, family, day = fetch_cicids()
        save("S0_dataset", {
            "n_rows": int(len(X)), "n_features": int(X.shape[1]),
            "attack_ratio": float(y.mean()),
            "sample_frac": SAMPLE_FRAC,
            "family_counts": family.value_counts().to_dict(),
            "day_counts": day.value_counts().to_dict(),
        })
        if "S1" in STAGES:
            stage1(X, y)
        if "S2" in STAGES:
            stage2(X, y, family, day)
        if "S3" in STAGES:
            stage3(X, y, family)
        if "S4" in STAGES:
            stage4(X, y)
        if "S6" in STAGES:
            stage6(X, y)
    if "S5" in STAGES:
        stage5()
    if "S7" in STAGES:
        stage7()
    print("\nDone. JSON results in", os.path.abspath(OUT_DIR))


if __name__ == "__main__":
    main()
