"""
Control experiments added for the SOICT 2026 camera-ready, in answer to the
reviewers. They reuse run_v3.py unchanged -- same data loading, same 20 %
sample, same models, same in-split preprocessing (fit_pipeline) -- so every
difference from the reported protocols is the control itself.

  R0  Family partition: label x capture-day counts, which families are
      present in the random-split test set, which enter leave-one-family-out.
      No training.                                               (Review 7)
  R1  P2 (day-disjoint) re-run keeping the scores: threshold-free metrics,
      recall at a matched false-positive rate, per-family recall on the
      test days. Seeds 42,1,2 reproduce S2; 3,4 extend it.  (R6-Q1, R5)
  R2  Temporal decomposition: train on 70 % of Mon-Wed, then measure
      (a) a held-out 30 % of Mon-Wed  -- same days, seen families;
      (b) Thu-Fri benign flows          -- temporal shift, no new family;
      (c) Thu-Fri attack flows          -- unseen families (plus shift).
                                                     (R2-R7: confounding)
  R3  Near-duplicate control: a random split grouped so that no two flows
      agreeing on all 78 features to two significant figures fall on
      opposite sides; plus the near-duplicate exposure of each protocol.
  R4  Cross-dataset transfer (S6) re-run keeping the scores, then
      re-thresholded on the target with target labels: an ORACLE diagnostic
      that bounds what threshold recalibration alone could recover.
                                                              (Review 7)

    STAGES=R0,R1,R2,R3,R4 python run_revision.py

Results go to results_v3/<stage>.json next to the reported ones.
"""

import json
import os
import time

import numpy as np
import pandas as pd

import run_v3 as v3

STAGES = os.environ.get("REV_STAGES", "R0,R1,R2,R3,R4").split(",")
SEEDS_R1 = [int(s) for s in os.environ.get("SEEDS_R1", "42,1,2,3,4").split(",")]
SEEDS_R2 = [int(s) for s in os.environ.get("SEEDS_R2", "42,1,2").split(",")]
SEEDS_R3 = [int(s) for s in os.environ.get("SEEDS_R3", "42,1,2,3,4").split(",")]
LOFO_MIN = 50          # run_v3.stage3 skips families with fewer held-out flows


def _scores(clf, X):
    return (clf.predict_proba(X)[:, 1] if hasattr(clf, "predict_proba")
            else clf.decision_function(X))


def recall_at_fpr(y, s, target_fpr):
    """Recall when the threshold is set so that the false-positive rate on
    the benign flows does not exceed target_fpr (decision: score > t)."""
    y = np.asarray(y)
    neg = np.sort(s[y == 0])
    pos = s[y == 1]
    k = int(np.floor(target_fpr * len(neg)))       # benign flows allowed above t
    t = neg[len(neg) - k - 1] if k < len(neg) else -np.inf
    return {"target_fpr": float(target_fpr), "threshold": float(t),
            "fpr": float((neg > t).mean()), "recall": float((pos > t).mean())}


def per_family(pred, fam):
    out = {}
    for f in sorted(fam.unique()):
        m = (fam == f).values
        key = "false_positive_rate" if f.upper() == "BENIGN" else "recall"
        out[f] = {"n": int(m.sum()), key: float((pred[m] == 1).mean())}
    return out


def summarise(runs):
    """run_v3._summarise without the cost columns, which these controls do
    not time."""
    df = pd.DataFrame(runs)
    keep = [k for k in ("accuracy", "precision_attack", "recall_attack",
                        "macro_f1", "roc_auc", "pr_auc", "mcc",
                        "balanced_accuracy", "fpr", "fnr") if k in df]
    out = {}
    for model, grp in df.groupby("model"):
        entry = {}
        for col in keep:
            vals = grp[col].astype(float).values
            n = len(vals)
            sd = vals.std(ddof=1) if n > 1 else 0.0
            half = 1.96 * sd / np.sqrt(n) if n > 1 else 0.0
            entry[col] = {"mean": float(vals.mean()), "std": float(sd), "n": n,
                          "ci95_low": float(vals.mean() - half),
                          "ci95_high": float(vals.mean() + half)}
        out[model] = entry
    return out


def save(stage, obj, t0):
    obj["runtime_s"] = time.perf_counter() - t0
    v3.save(stage, obj)


# --------------------------------------------------------------------------
def r0(X, y, family, day):
    t0 = time.perf_counter()
    ct = pd.crosstab(family, day)
    s3 = v3.load("S3_per_family") or {}
    in_test = set(s3.get("per_family_random_split", {}).get("XGBoost", {}))
    in_lofo = set(s3.get("leave_one_family_out_xgboost", {}))
    rows = {}
    for f in ct.index:
        days = [d for d in ct.columns if ct.loc[f, d] > 0]
        rows[f] = {
            "n": int(ct.loc[f].sum()),
            "days": days,
            "in_random_split_test": f in in_test,
            "in_lofo": f in in_lofo,
            "side_p2": ("train" if set(days) <= set(v3.TRAIN_DAYS) else
                        "test" if set(days) <= set(v3.TEST_DAYS) else "both"),
        }
    attacks = [f for f in rows if f.upper() != "BENIGN"]
    save("R0_partition", {
        "labels": rows,
        "n_attack_labels": len(attacks),
        "n_attack_labels_in_random_test": sum(rows[f]["in_random_split_test"]
                                              for f in attacks),
        "n_attack_labels_in_lofo": sum(rows[f]["in_lofo"] for f in attacks),
        "lofo_min_flows": LOFO_MIN,
        "attack_labels_spanning_days": [f for f in attacks
                                        if len(rows[f]["days"]) > 1],
        "prevalence": {
            "all": float(y.mean()),
            "p2_train": float(y[day.isin(v3.TRAIN_DAYS)].mean()),
            "p2_test": float(y[day.isin(v3.TEST_DAYS)].mean()),
        },
    }, t0)


# --------------------------------------------------------------------------
def r1(X, y, family, day):
    t0 = time.perf_counter()
    tr, te = day.isin(v3.TRAIN_DAYS).values, day.isin(v3.TEST_DAYS).values
    X_tr, y_tr, X_te, y_te = X[tr], y[tr], X[te], y[te].values
    fam_te = family[te].reset_index(drop=True)
    runs = []
    for seed in SEEDS_R1:
        X_bal, y_bal, X_te_k, feats = v3.fit_pipeline(X_tr, y_tr, X_te, seed)
        scores, preds = {}, {}
        for name, clf in v3.build_models(seed).items():
            clf.fit(X_bal, y_bal)
            preds[name] = clf.predict(X_te_k)
            scores[name] = _scores(clf, X_te_k)
        default_fpr = {m: float((preds[m][y_te == 0] == 1).mean()) for m in preds}
        for name in preds:
            row = {"seed": seed, "model": name}
            row.update(v3.evaluate(y_te, preds[name], scores[name]))
            row["per_family"] = per_family(preds[name], fam_te)
            # recall of this model when held to another model's alert rate
            row["recall_at_fpr_of"] = {
                ref: recall_at_fpr(y_te, scores[name], default_fpr[ref])
                for ref in preds}
            runs.append(row)
            print(f"[R1] seed={seed} {name:20s} rec={row['recall_attack']:.4f} "
                  f"fpr={row['fpr']:.4f} auc={row['roc_auc']:.4f} "
                  f"rec@LRfpr={row['recall_at_fpr_of']['Logistic Regression']['recall']:.4f}")
    summary = summarise(runs)
    matched = {}
    for name in summary:
        rr = [r for r in runs if r["model"] == name]
        matched[name] = {ref: {
            "recall_mean": float(np.mean([r["recall_at_fpr_of"][ref]["recall"] for r in rr])),
            "fpr_mean": float(np.mean([r["recall_at_fpr_of"][ref]["fpr"] for r in rr])),
        } for ref in rr[0]["recall_at_fpr_of"]}
    fam_mean = {}
    for name in summary:
        rr = [r for r in runs if r["model"] == name]
        fam_mean[name] = {f: float(np.mean([r["per_family"][f].get(
            "recall", r["per_family"][f].get("false_positive_rate")) for r in rr]))
            for f in rr[0]["per_family"]}
    save("R1_p2_thresholds", {
        "seeds": SEEDS_R1, "runs": runs, "summary": summary,
        "matched_fpr_summary": matched, "per_family_mean": fam_mean,
        "test_prevalence": float(y_te.mean()), "n_test": int(len(y_te)),
    }, t0)


# --------------------------------------------------------------------------
def r2(X, y, family, day):
    from sklearn.model_selection import train_test_split

    t0 = time.perf_counter()
    pool = day.isin(v3.TRAIN_DAYS).values
    cross = day.isin(v3.TEST_DAYS).values
    Xp, yp = X[pool].reset_index(drop=True), y[pool].reset_index(drop=True)
    Xc, yc = X[cross].reset_index(drop=True), y[cross].reset_index(drop=True).values
    fam_c = family[cross].reset_index(drop=True)
    runs = []
    for seed in SEEDS_R2:
        i_tr, i_ho = train_test_split(np.arange(len(Xp)), test_size=v3.TEST_SIZE,
                                      stratify=yp, random_state=seed)
        X_eval = pd.concat([Xp.iloc[i_ho], Xc], ignore_index=True)
        X_bal, y_bal, X_eval_k, _ = v3.fit_pipeline(
            Xp.iloc[i_tr], yp.iloc[i_tr], X_eval, seed)
        n_ho = len(i_ho)
        y_ho = yp.iloc[i_ho].values
        for name, clf in v3.build_models(seed).items():
            clf.fit(X_bal, y_bal)
            p = clf.predict(X_eval_k)
            s = _scores(clf, X_eval_k)
            p_ho, p_c, s_c = p[:n_ho], p[n_ho:], s[n_ho:]
            row = {
                "seed": seed, "model": name,
                "in_period": v3.evaluate(y_ho, p_ho, s[:n_ho]),
                "cross_period_all": v3.evaluate(yc, p_c, s_c),
                "cross_period_benign_fpr": float((p_c[yc == 0] == 1).mean()),
                "cross_period_attack_recall": float((p_c[yc == 1] == 1).mean()),
                "cross_period_per_family": per_family(p_c, fam_c),
            }
            runs.append(row)
            print(f"[R2] seed={seed} {name:20s} "
                  f"in: rec={row['in_period']['recall_attack']:.4f} "
                  f"fpr={row['in_period']['fpr']:.4f} | cross: "
                  f"benignFPR={row['cross_period_benign_fpr']:.4f} "
                  f"rec={row['cross_period_attack_recall']:.4f}")
    summ = {}
    for name in {r["model"] for r in runs}:
        rr = [r for r in runs if r["model"] == name]

        def ms(vals):
            a = np.asarray(vals, dtype=float)
            sd = a.std(ddof=1) if len(a) > 1 else 0.0
            return {"mean": float(a.mean()), "std": float(sd),
                    "ci95_half": float(1.96 * sd / np.sqrt(len(a))), "n": len(a)}
        summ[name] = {
            "in_period_recall": ms([r["in_period"]["recall_attack"] for r in rr]),
            "in_period_fpr": ms([r["in_period"]["fpr"] for r in rr]),
            "in_period_macro_f1": ms([r["in_period"]["macro_f1"] for r in rr]),
            "cross_benign_fpr": ms([r["cross_period_benign_fpr"] for r in rr]),
            "cross_attack_recall": ms([r["cross_period_attack_recall"] for r in rr]),
            "cross_macro_f1": ms([r["cross_period_all"]["macro_f1"] for r in rr]),
        }
    save("R2_temporal_decomposition", {
        "seeds": SEEDS_R2, "runs": runs, "summary": summ,
        "n_in_period_test": int(round(len(Xp) * v3.TEST_SIZE)),
        "n_cross_benign": int((yc == 0).sum()), "n_cross_attack": int((yc == 1).sum()),
        "in_period_prevalence": float(yp.mean()),
        "cross_prevalence": float(yc.mean()),
    }, t0)


# --------------------------------------------------------------------------
def near_dup_key(X, sig=2):
    """Hash of the feature vector with every value rounded to `sig`
    significant figures: flows sharing a key are near-duplicates."""
    A = X.to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        mag = np.where(A == 0, 0, np.floor(np.log10(np.abs(A))))
        step = 10.0 ** (mag - (sig - 1))
        Q = np.where(A == 0, 0.0, np.round(A / step) * step)
    return pd.util.hash_pandas_object(pd.DataFrame(Q), index=False).values


def r3(X, y, family, day):
    from sklearn.model_selection import GroupShuffleSplit, train_test_split

    t0 = time.perf_counter()
    exact = pd.util.hash_pandas_object(X, index=False).values
    near = near_dup_key(X, 2)
    yv = y.values

    def exposure(tr, te, key):
        seen = set(key[tr])
        hit = np.fromiter((k in seen for k in key[te]), bool, count=int(te.sum()))
        yt = yv[te]
        return {"all": float(hit.mean()), "attack": float(hit[yt == 1].mean()),
                "benign": float(hit[yt == 0].mean())}

    # near-duplicate exposure: share of test flows with a twin in training
    idx = np.arange(len(X))
    i_tr, i_te = train_test_split(idx, test_size=v3.TEST_SIZE, stratify=y,
                                  random_state=42)
    m_tr = np.zeros(len(X), bool); m_tr[i_tr] = True
    p1 = {"exact": exposure(m_tr, ~m_tr, exact), "sf2": exposure(m_tr, ~m_tr, near)}
    tr2, te2 = day.isin(v3.TRAIN_DAYS).values, day.isin(v3.TEST_DAYS).values
    p2 = {"exact": exposure(tr2, te2, exact), "sf2": exposure(tr2, te2, near)}
    sizes = pd.Series(near).value_counts()
    in_multi = pd.Series(near).map(sizes).values > 1
    print(f"[R3] exposure P1={p1}  P2={p2}")

    runs, splits = [], []
    for seed in SEEDS_R3:
        gss = GroupShuffleSplit(n_splits=1, test_size=v3.TEST_SIZE, random_state=seed)
        g_tr, g_te = next(gss.split(X, y, groups=near))
        m = np.zeros(len(X), bool); m[g_tr] = True
        splits.append({"seed": seed, "n_train": int(len(g_tr)), "n_test": int(len(g_te)),
                       "test_prevalence": float(yv[g_te].mean()),
                       "exposure_sf2": exposure(m, ~m, near)["all"]})
        X_bal, y_bal, X_te_k, _ = v3.fit_pipeline(X.iloc[g_tr], y.iloc[g_tr],
                                                  X.iloc[g_te], seed)
        fam_te = family.iloc[g_te].reset_index(drop=True)
        for name, clf in v3.build_models(seed).items():
            clf.fit(X_bal, y_bal)
            p = clf.predict(X_te_k)
            row = {"seed": seed, "model": name}
            row.update(v3.evaluate(yv[g_te], p, _scores(clf, X_te_k)))
            row["per_family"] = per_family(p, fam_te)
            runs.append(row)
            print(f"[R3] seed={seed} {name:20s} F1={row['macro_f1']:.4f} "
                  f"rec={row['recall_attack']:.4f} fpr={row['fpr']:.4f}")
    save("R3_grouped_split", {
        "definition": ("groups = flows whose 78 features agree to two "
                       "significant figures; GroupShuffleSplit 70/30"),
        "n_flows": int(len(X)), "n_groups_sf2": int(len(sizes)),
        "share_in_multi_member_groups": float(in_multi.mean()),
        "share_attack_in_multi_member_groups": float(in_multi[yv == 1].mean()),
        "largest_group": int(sizes.iloc[0]),
        "exposure_p1_seed42": p1, "exposure_p2": p2,
        "splits": splits, "runs": runs, "summary": summarise(runs),
    }, t0)


# --------------------------------------------------------------------------
def _at(y, s, t):
    p = (s > t).astype(int)
    e = v3.evaluate(y, p, s)
    e["threshold"] = float(t)
    e["predicted_positive_rate"] = float(p.mean())
    return e


def _best_f1_threshold(y, s, cand):
    """Macro-F1 at every candidate threshold (decision: score > t), by
    counting with sorted scores instead of re-evaluating each one."""
    pos, neg = np.sort(s[y == 1]), np.sort(s[y == 0])
    P, N = len(pos), len(neg)
    tp = P - np.searchsorted(pos, cand, side="right")
    fp = N - np.searchsorted(neg, cand, side="right")
    fn, tn = P - tp, N - fp
    with np.errstate(divide="ignore", invalid="ignore"):
        f1p = np.where(2 * tp + fp + fn > 0, 2 * tp / (2 * tp + fp + fn), 0.0)
        f1n = np.where(2 * tn + fn + fp > 0, 2 * tn / (2 * tn + fn + fp), 0.0)
    return float(cand[int(np.argmax((f1p + f1n) / 2))])


def r4(Xc, yc):
    from sklearn.preprocessing import StandardScaler
    from imblearn.over_sampling import SMOTE

    t0 = time.perf_counter()
    Xu, yu, _ = v3.fetch_unsw()
    pairs = [(c, u, s) for c, u, s in v3.ALIGN if c in Xc.columns and u in Xu.columns]
    A = pd.DataFrame({u: Xc[c].astype(float) * s for c, u, s in pairs})
    B = Xu[[u for _, u, _ in pairs]].astype(float)
    out = {}
    for tag, (Xs, ys, Xt, yt) in {
            "cicids2017 -> unsw-nb15": (A, yc, B, yu),
            "unsw-nb15 -> cicids2017": (B, yu, A, yc)}.items():
        yt = np.asarray(yt)
        sc = StandardScaler().fit(Xs)
        Xb, yb = SMOTE(random_state=42).fit_resample(sc.transform(Xs), ys)
        Xt_s = sc.transform(Xt)
        prev = float(yt.mean())
        row = {}
        for name, clf in v3.build_models(42).items():
            clf.fit(Xb, yb)
            pred = clf.predict(Xt_s)
            s = _scores(clf, Xt_s)
            default = v3.evaluate(yt, pred, s)
            # (a) prevalence-matched: flag the top pi_target share of flows
            t_prev = float(np.quantile(s, 1 - prev))
            # (b) best macro-F1 over 2001 score quantiles
            cand = np.unique(np.concatenate([np.quantile(s, np.linspace(0, 1, 2001)),
                                             [-np.inf]]))
            best = _at(yt, s, _best_f1_threshold(yt, s, cand))
            row[name] = {"default": default,
                         "prevalence_matched": _at(yt, s, t_prev),
                         "best_macro_f1": best}
            print(f"[R4] {tag} {name:20s} F1 default={default['macro_f1']:.4f} "
                  f"prev-matched={row[name]['prevalence_matched']['macro_f1']:.4f} "
                  f"best={best['macro_f1']:.4f} auc={default['roc_auc']:.4f}")
        out[tag] = {"target_prevalence": prev, "source_prevalence": float(np.mean(ys)),
                    "models": row}
    save("R4_transfer_rethreshold", {
        "note": ("ORACLE diagnostic: thresholds (b) and the prevalence in (a) "
                 "use target labels and are not available in deployment; "
                 "they bound what recalibration alone could recover."),
        "results": out}, t0)


# --------------------------------------------------------------------------
def main():
    t0 = time.perf_counter()
    X, y, family, day = v3.fetch_cicids()
    print(f"[load] {time.perf_counter() - t0:.1f}s")
    for st, fn in (("R0", r0), ("R1", r1), ("R2", r2), ("R3", r3)):
        if st in STAGES:
            fn(X, y, family, day)
    if "R4" in STAGES:
        r4(X, y)
    print(f"done in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
