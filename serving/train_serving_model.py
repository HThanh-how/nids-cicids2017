"""
Train and freeze the model that the serving benchmark actually runs.

The point of this script is traceability: the artefact loaded by the API is
produced here, by the *same* pipeline used in the offline evaluation
(experiments/run_v3.py) -- scaler, RF-importance top-k selection and SMOTE all
fitted on the training split only. The reported serving latency therefore
belongs to a model whose accuracy is reported in the same paper, which is what
reviewer 1 (concern 9) and reviewer 2 (concern 2) asked for.

Outputs (serving/artifacts/):
  model.joblib      fitted XGBoost classifier
  scaler.joblib     fitted StandardScaler (all input features)
  metadata.json     feature order, offline metrics, build environment

Usage:
    python train_serving_model.py
"""

import json
import os
import sys
import time

import numpy as np
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "experiments"))

import run_v3 as exp  # noqa: E402  (path set above)

ART = os.path.join(HERE, "artifacts")
SEED = 42


def main():
    os.makedirs(ART, exist_ok=True)
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
    from imblearn.over_sampling import SMOTE

    X, y, family, day = exp.fetch_cicids()
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=exp.TEST_SIZE, stratify=y, random_state=SEED)

    # Same pipeline as the offline study, fitted on the training half only.
    scaler = StandardScaler().fit(X_tr)
    X_tr_s, X_te_s = scaler.transform(X_tr), scaler.transform(X_te)
    selector = RandomForestClassifier(
        n_estimators=100, n_jobs=-1, random_state=SEED).fit(X_tr_s, y_tr)
    order = np.argsort(selector.feature_importances_)[::-1][:exp.TOP_K]
    feature_names = [X_tr.columns[i] for i in order]
    X_bal, y_bal = SMOTE(random_state=SEED).fit_resample(X_tr_s[:, order], y_tr)

    clf = exp.build_models(SEED)["XGBoost"]
    t0 = time.perf_counter()
    clf.fit(X_bal, y_bal)
    train_s = time.perf_counter() - t0

    pred = clf.predict(X_te_s[:, order])
    score = clf.predict_proba(X_te_s[:, order])[:, 1]
    metrics = exp.evaluate(y_te.values, pred, score)
    print(json.dumps(metrics, indent=2, default=float))

    joblib.dump(clf, os.path.join(ART, "model.joblib"))
    joblib.dump(scaler, os.path.join(ART, "scaler.joblib"))
    meta = {
        "model": "XGBoost",
        "hyperparameters": clf.get_params(),
        "all_input_features": list(X.columns),
        "selected_features": feature_names,
        "selected_indices": [int(i) for i in order],
        # StandardScaler is per-column, so serving only needs the mean/scale of
        # the selected columns -- the API can then accept 20 numbers instead of
        # the full feature vector, with numerically identical results.
        "selected_mean": [float(v) for v in scaler.mean_[order]],
        "selected_scale": [float(v) for v in scaler.scale_[order]],
        "top_k": exp.TOP_K,
        "seed": SEED,
        "sample_frac": exp.SAMPLE_FRAC,
        "test_size": exp.TEST_SIZE,
        "train_seconds": train_s,
        "offline_metrics_random_split": metrics,
        "n_train_after_smote": int(len(y_bal)),
        "n_test": int(len(y_te)),
    }
    with open(os.path.join(ART, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=float)

    # A small held-out sample the load generator replays, so the benchmark
    # sends real flows rather than synthetic noise.
    sample = X_te.iloc[:2000][feature_names]
    sample.to_json(os.path.join(ART, "sample_flows.json"),
                   orient="records")
    print(f"[ok] artefacts written to {ART}")


if __name__ == "__main__":
    main()
