# Hướng dẫn chạy thí nghiệm trên Google Colab (lấy số cho bài báo)

Mục tiêu: chạy `experiments/ids_cicids2017.ipynb` → ra **2 bảng số thật** + hình
confusion matrix/ROC → dán vào `main.tex` thay các chỗ `TODO`.

## Bước 1 — Mở notebook trên Colab
1. Vào https://colab.research.google.com → **File → Open notebook → GitHub**.
2. Dán: `HThanh-how/nids-cicids2017` → chọn `experiments/ids_cicids2017.ipynb`.
   (Repo private thì: **File → Upload notebook**, kéo file `.ipynb` từ máy lên.)
3. **Runtime → Change runtime type → T4 GPU** (miễn phí; không bắt buộc nhưng nhanh hơn).

## Bước 2 — Lấy dữ liệu CICIDS2017 (cách Kaggle, nhanh nhất)
Tạo **1 cell mới ở đầu** notebook, dán đoạn này rồi chạy:

```python
# (a) Lấy API token Kaggle: kaggle.com -> ảnh đại diện -> Settings -> API -> Create New Token
#     -> tải kaggle.json về máy.
from google.colab import files
files.upload()                      # chọn kaggle.json vừa tải
!mkdir -p ~/.kaggle && cp kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json
!pip -q install kaggle

# (b) Tải bộ CSV gốc (MachineLearningCVE) và giải nén
!kaggle datasets download -d cicdataset/cicids2017 -p /content/cicids_raw --unzip

# (c) Tự tìm thư mục chứa 8 file CSV và set DATA_DIR cho notebook
import glob, os
hits = glob.glob('/content/**/*.csv', recursive=True)
DATA_DIR = os.path.dirname(sorted(hits, key=len)[0]) if hits else None
print('DATA_DIR =', DATA_DIR, '| CSV files:', len(hits))
```

> Lưu ý: cell "## 1. Lấy dữ liệu" có sẵn trong notebook đặt `DATA_DIR = '/content/cicids2017'`.
> **Sửa dòng đó** thành `DATA_DIR` mà đoạn (c) in ra (vd. `/content/cicids_raw/MachineLearningCSV/MachineLearningCVE`).

**Cách thay thế (không dùng Kaggle):** tải 8 file CSV về Google Drive, rồi trong Colab:
```python
from google.colab import drive; drive.mount('/content/drive')
DATA_DIR = '/content/drive/MyDrive/<thư-mục-bạn-để-CSV>'
```

## Bước 3 — Chạy hết
**Runtime → Run all.** Notebook sẽ: nạp → làm sạch → chọn đặc trưng → SMOTE →
train 4 model → in **2 bảng** + lưu `confusion_matrix.pdf`, `roc_curve.pdf`.

## Bước 4 — Lấy kết quả về bài báo
- Cell "## 7. Xuất ra LaTeX" in sẵn 2 khối `\begin{tabular}...`. **Copy** chúng,
  gửi cho tôi (hoặc tự thay vào 2 bảng `tab:results`, `tab:cost` trong `main.tex`).
- Tải `confusion_matrix.pdf`, `roc_curve.pdf` → bỏ vào thư mục `figures/`.
- Gửi tôi 2 bảng số → tôi viết lại đoạn Results + điền câu kết quả ở Abstract/Conclusion
  cho khớp số thật (thay hết `\textbf{TODO}`).

## Thời gian ước tính
Tải data ~2–5 phút; train 4 model trên vài trăm nghìn dòng ~5–15 phút (CPU) hoặc nhanh hơn với GPU.

> Nếu bộ đầy đủ quá nặng/Colab hết RAM: trong cell nạp dữ liệu, lấy mẫu bớt
> (`df = df.sample(frac=0.3, random_state=42)`) — ghi rõ tỉ lệ mẫu này vào paper.
