# WRITING GUIDE — prompt pack + checklist

Mục đích: bạn (hoặc model giá rẻ) dùng các **prompt sẵn** dưới đây để viết từng mục của
`main.tex`, còn **checklist** giữ chất lượng đúng chuẩn. Đây là "đường ray" — sinh chữ
bằng token nào cũng được, nhưng phải vượt checklist mới coi là xong.

## Luật chung (dán kèm MỌI prompt)

```
You are writing a section of an academic conference paper in the Springer LNCS
format (target venue: ICTA/FDSE 2026, Scopus-indexed). Rules:
- Output LaTeX body text only (no \documentclass, no preamble).
- Formal academic English, third person, present tense for general facts.
- DO NOT fabricate numbers, citations, or results. If a number is unknown,
  leave a literal "TODO" placeholder — never invent data.
- Cite only keys that exist in references.bib (sharafaldin2018cicids,
  tavallaee2009nslkdd, moustafa2015unswnb15, chen2016xgboost,
  breiman2001random, chawla2002smote, buczak2016survey). Use \cite{key}.
- Keep within the length budget given for the section.
- Match the existing structure and \label{} names in main.tex.
```

Ngân sách độ dài (paper Springer ~ 12–14 trang LNCS hoặc 6 trang đôi cột tuỳ template):
Abstract ~180 từ · Intro ~1 trang · Related Work ~0.75 trang · Dataset ~1 trang ·
Method ~1 trang · Results ~1.5 trang · Deployment ~1 trang · Conclusion ~0.5 trang.

---

## 1. Abstract
**Prompt:**
```
Write the Abstract (~180 words) for a paper titled "Network Intrusion Detection on
CICIDS2017: A Comparative Study of Machine Learning and Deep Learning Models with a
Cloud-Native Deployment Design". Cover: problem & motivation; the comparative study
(Logistic Regression, Random Forest, XGBoost, a deep model) on CICIDS2017; unified
metrics (precision/recall/macro-F1/ROC-AUC) plus computational cost; the cloud-native
deployment contribution. Leave the single results sentence as a TODO placeholder.
End with no citations.
```
**Checklist:** [ ] ≤200 từ  [ ] nêu đủ 3 đóng góp  [ ] không có số bịa  [ ] không \cite.

## 2. Introduction
**Prompt:**
```
Write the Introduction (~1 page). Structure: (1) context — rising attack volume in
enterprise/telecom networks motivating learning-based IDS; (2) the gap — most works
report offline accuracy but neglect fair cross-model comparison under one protocol AND
the path to scalable deployment; (3) a bulleted \begin{itemize} of the three
contributions already listed in main.tex; (4) a short paragraph organization map
referencing \ref{sec:related}..\ref{sec:conclusion}. Cite buczak2016survey once for the
general ML-for-IDS claim.
```
**Checklist:** [ ] có problem statement rõ  [ ] 3 contributions trùng main.tex  [ ] có đoạn "organization"  [ ] chỉ 1–2 cite hợp lệ.

## 3. Related Work
**Prompt:**
```
Write Related Work (~0.75 page) in 3 short paragraphs: (a) ML/DL approaches to IDS
broadly (cite buczak2016survey); (b) benchmark datasets — limitations of NSL-KDD
(tavallaee2009nslkdd) and UNSW-NB15 (moustafa2015unswnb15), motivating CICIDS2017
(sharafaldin2018cicids); (c) the research gap this paper fills (cost-aware comparison +
deployment). Add a literal "% TODO: add 3-5 recent (2022-2025) venue-domain refs" line.
```
**Checklist:** [ ] 3 đoạn  [ ] cite đúng key  [ ] nêu rõ gap  [ ] có dòng TODO refs mới.

## 4. Dataset and Preprocessing
**Prompt:**
```
Write Section 3 "Dataset and Preprocessing" (~1 page) with the existing subsections
(Cleaning and Encoding; Feature Selection; Class Imbalance). Describe CICIDS2017
(sharafaldin2018cicids): ~5 days of flows, benign + multiple attack families, 80+
flow features. Explain cleaning (drop NaN/Inf, strip column-name whitespace, dedup),
label encoding (binary benign/attack), standardization, feature selection (RF
importance / mutual information -> top-k, leave k as TODO), and imbalance handling
(SMOTE chawla2002smote or class weights). Leave concrete counts as TODO.
```
**Checklist:** [ ] mô tả dataset có cite  [ ] đủ 3 subsection  [ ] số liệu cụ thể = TODO  [ ] cite SMOTE.

## 5. Methodology
**Prompt:**
```
Write Section 4 "Methodology" (~1 page) with subsections Models, Experimental Setup,
Evaluation Metrics. Models: Logistic Regression (baseline), Random Forest
(breiman2001random), XGBoost (chen2016xgboost), a deep model (MLP or 1D-CNN). Setup:
Google Colab free tier; scikit-learn / XGBoost / PyTorch; 5-fold stratified CV; fixed
seed for reproducibility. Metrics: define Accuracy, Precision, Recall, macro-F1,
ROC-AUC briefly, plus training/inference time. No invented results.
```
**Checklist:** [ ] 3 subsection  [ ] cite RF + XGBoost  [ ] nêu reproducibility (seed, CV)  [ ] định nghĩa metric.

## 6. Experiments and Results
**Prompt:**
```
Write Section 5 "Experiments and Results" (~1.5 pages) DISCUSSION TEXT ONLY around the
two existing tables (\ref{tab:results}, \ref{tab:cost}). Do NOT fill the tables with
numbers — keep them as the author will paste real results. Write: a sentence
introducing each table; a paragraph template comparing models on macro-F1 vs cost with
"TODO" where specific numbers go; a paragraph on per-attack-class behavior and confusion
matrix highlights (TODO); a short error-analysis paragraph. Frame claims conditionally
("the best-performing model ... achieves a macro-F1 of TODO").
```
**Checklist:** [ ] KHÔNG điền số vào bảng  [ ] mọi số = TODO  [ ] có so sánh F1↔cost  [ ] tham chiếu \ref{tab:*}.

## 7. Cloud-Native Deployment Design
**Prompt:**
```
Write Section 6 "Cloud-Native Deployment Design" (~1 page). Describe exporting the
selected model and serving it as a REST microservice (FastAPI), containerized with
Docker, deployable on Kubernetes, with a CI/CD pipeline (build->test->deploy). Reference
\ref{fig:arch}. Discuss observed throughput (requests/s) and median/p95 latency as TODO
placeholders from a load test. Keep it concrete and engineering-oriented.
```
**Checklist:** [ ] FastAPI+Docker+K8s+CI/CD  [ ] ref \ref{fig:arch}  [ ] latency/throughput = TODO.

## 8. Conclusion and Future Work
**Prompt:**
```
Write Section 7 "Conclusion and Future Work" (~0.5 page). Summarize the comparative
findings (conditionally, numbers as TODO) and the deployment contribution. Then give a
forward-looking paragraph tying future work to a PhD research direction: online/continual
learning for concept drift, explainable IDS, graph-based detection, or federated
detection across telecom nodes.
```
**Checklist:** [ ] tóm tắt đủ ý  [ ] future work nối hướng NCS  [ ] số = TODO.

---

## Vòng lặp kiểm soát (control loop)
1. **Generate** từng mục bằng model rẻ (hoặc Claude qua proxy) với prompt ở trên.
2. **Self-check** ngay với checklist của mục đó — fail thì sửa/regenerate.
3. **Compile**: push lên GitHub → Actions build PDF (xem lỗi LaTeX ở Artifacts/log).
4. **Hard review**: các mục nặng (Results, Method, Abstract) mang về Opus soát logic/claim.
5. **Numbers**: chỉ điền số THẬT từ notebook (`experiments/`) vào bảng — không bao giờ bịa.

> Nguyên tắc vàng: model nào viết cũng được, nhưng **mọi con số phải đến từ thí nghiệm
> thật**, và mọi `\cite` phải có trong `references.bib`. Đó là ranh giới không vượt.
