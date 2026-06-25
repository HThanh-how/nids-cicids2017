# Experiment results (real run)

Run on Google Colab (free tier), data pulled directly from the public
HuggingFace mirror `c01dsnap/CIC-IDS2017` (8 MachineLearningCVE CSVs), no auth.

**Config:** 20% stratified sample per file, seed=42, top-k=20 features
(Random Forest importance), StandardScaler, SMOTE on train, 70/30 stratified
train/test split.

**Dataset after cleaning:** 530,222 flows · 78 numeric features · attack ratio 17.85%.

## Detection performance (test set)

| Model | Accuracy | Precision | Recall | macro-F1 | ROC-AUC |
|---|---|---|---|---|---|
| Logistic Regression | 0.9186 | 0.7324 | 0.8571 | 0.8697 | 0.9629 |
| Random Forest | 0.9935 | 0.9719 | **0.9924** | 0.9890 | 0.9983 |
| **XGBoost** | **0.9952** | **0.9811** | 0.9921 | **0.9918** | **0.9998** |
| Deep model (MLP) | 0.9763 | 0.8911 | 0.9882 | 0.9613 | 0.9989 |

## Computational cost

| Model | Train time (s) | Inference (ms/sample) |
|---|---|---|
| Logistic Regression | 10.55 | 0.0001 |
| Random Forest | 185.76 | 0.0090 |
| XGBoost | 18.58 | 0.0057 |
| Deep model (MLP) | 675.54 | 0.0232 |

**Takeaway:** XGBoost is the best accuracy-to-cost trade-off — top macro-F1
(0.9918) and ROC-AUC (0.9998) with fast training (18.58 s) and low inference
(0.0057 ms/sample). Random Forest matches accuracy but trains ~10x slower;
MLP is slowest and less accurate.

## Robustness checks

**5-fold stratified CV (XGBoost, CICIDS2017):** macro-F1 = **0.9918 ± 0.0004**
(folds: 0.9910, 0.9917, 0.9921, 0.9919, 0.9923) — confirms the single-split
result is stable.

**Confusion matrix (XGBoost, CICIDS2017 test):** TN=130129, FP=542, FN=224,
TP=28172 (≈159k flows).

## Cross-dataset validation — UNSW-NB15 (175,341 flows, 42 features, attack ratio 68%)

| Model | Accuracy | Precision | Recall | macro-F1 | ROC-AUC |
|---|---|---|---|---|---|
| Logistic Regression | 0.8879 | 0.9108 | 0.9260 | 0.8698 | 0.9331 |
| Random Forest | 0.9554 | 0.9678 | 0.9666 | 0.9487 | 0.9925 |
| **XGBoost** | **0.9563** | 0.9667 | **0.9692** | **0.9497** | **0.9930** |
| Deep model (MLP) | 0.9361 | **0.9757** | 0.9293 | 0.9284 | 0.9893 |

Same pipeline + stratified 70/30 split. **XGBoost wins again** (macro-F1 0.9497,
ROC-AUC 0.9930); model ranking (XGBoost ≳ RF > MLP > LR) is preserved across
both datasets → the cost-aware conclusion generalizes, not a single-benchmark
artifact. Data: HF `Mouwiya/UNSW-NB15` (public, no auth).

> Reproduce: paste a single base64 one-liner (or run `ids_cicids2017.ipynb`)
> in Colab; ~18 min end-to-end on the free CPU tier.
