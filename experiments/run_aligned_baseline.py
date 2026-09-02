"""
S6b: in-domain baseline on the aligned seven-feature space.

The transfer experiment (S6) restricts both corpora to the seven flow-level
quantities they share. That restriction is a confound: some of the observed
degradation could come from using seven features instead of twenty rather
than from the domain shift. This stage measures the confound directly by
running an ordinary in-domain stratified holdout on exactly those seven
features, in each corpus separately.

If in-domain performance on seven features stays close to the twenty-feature
result, then the transfer collapse cannot be attributed to the feature space.

    python run_aligned_baseline.py      # writes results_v3/S6b_aligned.json
"""

import numpy as np
import pandas as pd

import run_v3 as exp

SEED = 42


def in_domain(X, y, name):
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from imblearn.over_sampling import SMOTE

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=exp.TEST_SIZE, stratify=y, random_state=SEED)
    scaler = StandardScaler().fit(X_tr)
    X_tr_s, X_te_s = scaler.transform(X_tr), scaler.transform(X_te)
    X_bal, y_bal = SMOTE(random_state=SEED).fit_resample(X_tr_s, y_tr)

    out = {}
    for model, clf in exp.build_models(SEED).items():
        clf.fit(X_bal, y_bal)
        pred = clf.predict(X_te_s)
        score = (clf.predict_proba(X_te_s)[:, 1]
                 if hasattr(clf, "predict_proba")
                 else clf.decision_function(X_te_s))
        out[model] = exp.evaluate(np.asarray(y_te), pred, score)
        print(f"[S6b] {name:12s} {model:22s} "
              f"F1={out[model]['macro_f1']:.4f} "
              f"recall={out[model]['recall_attack']:.4f}")
    return out


def main():
    Xc, yc, _, _ = exp.fetch_cicids()
    Xu, yu, _ = exp.fetch_unsw()

    pairs = [(c, u, s) for c, u, s in exp.ALIGN
             if c in Xc.columns and u in Xu.columns]
    print(f"[S6b] aligned features ({len(pairs)}): "
          f"{[c for c, _, _ in pairs]}")

    A = pd.DataFrame({u: Xc[c].astype(float) * s for c, u, s in pairs})
    B = Xu[[u for _, u, _ in pairs]].astype(float)

    result = {
        "n_aligned_features": len(pairs),
        "aligned_features": [{"cicids": c, "unsw": u, "scale": s}
                             for c, u, s in pairs],
        "cicids2017_in_domain": in_domain(A, yc, "CICIDS2017"),
        "unsw_nb15_in_domain": in_domain(B, yu, "UNSW-NB15"),
        "note": ("Ordinary in-domain stratified holdout restricted to the "
                 "seven features used for transfer. Compare against the "
                 "twenty-feature in-domain results (S1, S5) to separate the "
                 "cost of the reduced feature space from the domain shift "
                 "measured in S6."),
    }
    exp.save("S6b_aligned_indomain", result)


if __name__ == "__main__":
    main()
