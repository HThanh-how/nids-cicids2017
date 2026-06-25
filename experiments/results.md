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

> Reproduce: paste a single base64 one-liner (or run `ids_cicids2017.ipynb`)
> in Colab; ~18 min end-to-end on the free CPU tier.
