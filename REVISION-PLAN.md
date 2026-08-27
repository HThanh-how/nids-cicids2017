# Kế hoạch sửa bài sau khi ICTA 2026 từ chối (submission 153)

**Bến đỗ mới: SOICT 2026** — abstract 09/09/2026, full paper **16/09/2026**,
notification 12/10, hội nghị 04–05/12 tại **TP.HCM**, Springer **CCIS** (Scopus + EI).
Review **single-blind** (để tên thật, `\anonfalse`), giới hạn **12 trang chưa tính references**
(ICTA chỉ cho 8 → nay dư chỗ cho toàn bộ thí nghiệm mới).

Điểm số ICTA: R1 = −2 (reject), R2 = −1 (weak reject). Không reviewer nào nói bài **sai**;
cả hai nói bài **chưa đủ bằng chứng cho những gì nó tuyên bố**. R1 viết sẵn danh sách
"làm xong những cái này thì đăng được" — đây là bản đồ đường đi, ta bám sát từng dòng.

## Định vị lại đóng góp

Bài cũ tự nhận là "IDS framework triển khai được" nhưng bằng chứng chỉ là so sánh model
+ hình kiến trúc. Cả hai reviewer đều đánh vào chỗ đó. Bài mới đổi thành **hai đóng góp
đo được** mà bài cũ *không* có:

1. **Khoảng hụt lạc quan của benchmark** — cùng một pipeline, đánh giá bằng chia ngẫu nhiên
   so với chia tách theo ngày thu thập (day-disjoint). Chênh lệch chính là kết quả.
   Trên CICIDS2017 mỗi họ tấn công chỉ xuất hiện đúng một ngày, nên tách theo ngày
   *đồng thời* là tách theo họ tấn công: tập test toàn tấn công chưa từng thấy.
2. **Serving cloud-native đo thật, không phải hình vẽ** — dựng FastAPI + Docker + K8s rồi
   đo p50/p95/p99, throughput theo mức đồng thời, CPU/RAM, hành vi autoscale, thời gian khởi động.
   Đây là phần R1 (ý 9) chê nặng nhất, mà cũng là **nghề chính của tác giả** → biến điểm yếu
   nhất thành điểm khác biệt mạnh nhất so với các bài ML thuần.

Tiêu đề đề xuất (chọn 1 khi viết xong):
- *How Optimistic Is Your IDS Benchmark? Leakage-Resistant Evaluation and Measured
  Cloud-Native Serving for Network Intrusion Detection*
- *From Benchmark Scores to Serving Latency: A Cost-Aware, Leakage-Resistant Study of
  Network Intrusion Detection*

## Đối chiếu từng ý reviewer

| # | Reviewer nói | Việc phải làm | Ở đâu |
|---|---|---|---|
| R1.1 | Không có gì mới về phương pháp | Định vị lại thành **benchmark thực nghiệm có kiểm soát**, bỏ mọi chữ "framework" | viết lại Intro/Conclusion |
| R1.2, R2.3 | "cross-dataset" là gọi sai tên | Đổi tên thành *independent-dataset replication* **và** làm transfer thật (train CICIDS → test UNSW và ngược lại) trên không gian đặc trưng đã căn chỉnh | ✅ đã đổi tên trong `main.tex`; số liệu ← `run_v3.py` S5 + S6 |
| R1.3 | Chia ngẫu nhiên → rò rỉ, điểm ảo | Thêm giao thức **day-disjoint**, báo cáo song song với chia ngẫu nhiên | S2 |
| R1.4 | Chỉ 1 seed; CV chỉ chạy cho model đã chọn | 5 seed, **tất cả** model, mean ± std + khoảng tin cậy 95%, kiểm định t bắt cặp + Wilcoxon (XGB vs RF) | S1 |
| R1.5 | Thiếu siêu tham số, chọn đặc trưng có thể rò rỉ | Bảng siêu tham số đầy đủ; chọn đặc trưng + SMOTE + scaler **fit lại trong từng tập train** | S1 (`fit_pipeline`) + bảng mới |
| R1.6 | Gộp nhị phân che họ tấn công yếu | Recall theo từng họ + **leave-one-family-out** (khả năng bắt tấn công chưa từng thấy) | S3 |
| R1.7 | Thiếu chỉ số vận hành | FPR, FNR, MCC, balanced accuracy, PR-AUC, và **PPV theo tỉ lệ tấn công thực tế** (0,01%–10%) | S7 |
| R1.8 | So sánh chi phí không kiểm soát | Warm-up + đo lặp 5 lần, ghi CPU/RAM/phiên bản thư viện/số luồng | S8 + `timed_fit_predict` |
| R1.9 | Deployment mới là bản vẽ | **Dựng thật + đo tải** (xem mục dưới) | cần máy |
| R1.10 | Chọn đặc trưng chưa được kiểm chứng | Liệt kê đủ top-20, độ ổn định Jaccard giữa các seed, đối chiếu impurity vs permutation vs mutual information | S4 |
| R1.11 | Dataset cũ | Thu hẹp phát biểu về phạm vi benchmark, ghi rõ trong Limitations | viết |
| R1.12 | Related work mỏng | **Bảng so sánh** với các bài gần đây theo: dataset, cách chia, độ mịn nhãn, kiểm định thống kê, có đo triển khai thật không | viết + tra cứu |
| R2.2 | 0,0057 ms/mẫu mâu thuẫn với "10⁵ dự đoán/giây" | Bỏ hẳn phép quy đổi ra throughput; nói rõ đây là chi phí model khi khấu hao trên cả lô, **không phải** throughput dịch vụ | ✅ đã sửa trong `main.tex` |
| R2.4 | Không tìm thấy artifact tái lập | Công khai repo + `run_v3.py` + JSON kết quả + Dockerfile + manifest K8s, ghi link vào bài | repo |

## Thí nghiệm — `experiments/run_v3.py`

Một script tự chứa, chạy theo từng chặng, mỗi chặng ghi checkpoint ra
`results_v3/<stage>.json` để Colab có hết giờ cũng chỉ mất một chặng.

```bash
pip -q install xgboost imbalanced-learn scikit-learn pandas numpy scipy huggingface_hub
STAGES=S1,S2 python run_v3.py     # chạy từng nhóm chặng cho khỏi timeout
```

Gợi ý chia mẻ trên Colab free: `S8,S1` → `S2,S3` → `S4,S6` → `S5,S7`.
Nặng nhất là S1 (5 seed × 4 model) và S3 (leave-one-family-out).

**Nguyên tắc bất di bất dịch: chỉ số nào có trong JSON mới được đưa vào bài.**

## Đo triển khai thật (phần chưa có máy)

Cần một môi trường **tách khỏi production** và ghi lại được cấu hình:
VM data-lab (20.20.20.200) hoặc k3s/kind trên máy cá nhân. **Không đụng cụm 39/41/204.**

Cần đo và báo cáo:
- Độ trễ end-to-end p50/p95/p99 theo mức đồng thời (1, 8, 32, 128 client) — dùng k6 hoặc locust
- Throughput bão hoà, và điểm gãy khi tăng tải
- CPU/RAM lúc nghỉ và lúc bão hoà, so với resource limit đã đặt
- Thời gian khởi động nguội (cold start) của pod, thời gian nạp model
- Hành vi HPA: ngưỡng kích hoạt, độ trễ scale-up, throughput sau khi scale
- Ứng xử khi lỗi: giết pod giữa lúc tải, đo thời gian phục hồi và số request hỏng
- So sánh dự đoán từng bản ghi với dự đoán theo lô

Kèm vào artifact: `Dockerfile`, manifest K8s (Deployment/Service/HPA + resource limits),
hợp đồng API, kịch bản k6.

## Trình tự 20 ngày

1. Chạy `run_v3.py` trên Colab, thu đủ JSON — **việc chặn đường mọi thứ khác, làm trước**
2. Dựng service + đo tải, xuất CSV/JSON kết quả
3. Viết lại bài theo khung 12 trang (thêm: giao thức đánh giá, per-family, transfer,
   phân tích vận hành, kết quả triển khai đo được, bảng so sánh related work, limitations mở rộng)
4. Đổi `\anonfalse` (SOICT single-blind), đổi template LNCS → **CCIS**
5. Nộp abstract trước 09/09, full paper trước 16/09

## Ghi chú

- Bản nộp ICTA và toàn bộ review được giữ lại làm mốc so sánh.
- Đừng vá vặt bài cũ rồi nộp lại: R1 nói thẳng khối lượng cần làm **vượt quá** một lần
  chỉnh sửa camera-ready. Bài phải mạnh lên thật thì mới qua được SOICT.
