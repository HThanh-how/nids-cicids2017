# IDS on CICIDS2017 — Springer LNCS paper (auto-built on GitHub, free)

Bài báo hội nghị (target: **ICTA 2026 / FDSE 2026**, Springer LNCS/CCIS, Scopus)
được biên dịch **miễn phí** bằng GitHub Actions — không cần Overleaf trả phí,
không cần cài TeX trên máy.

## Cách hoạt động (rẻ = $0)

GitHub-hosted runner (`ubuntu-latest`) compile LaTeX bằng
[`xu-cheng/latex-action`](https://github.com/xu-cheng/latex-action) trên image
TeX Live đầy đủ. **Public repo → CI hoàn toàn miễn phí**; private repo có 2000
phút/tháng free (mỗi build chỉ ~1–2 phút).

| Workflow | Kích hoạt | Kết quả |
|---|---|---|
| `.github/workflows/build.yml` | mỗi push / PR / chạy tay | PDF ở tab **Actions → Artifacts**, và tự tạo **Release** kèm PDF khi push lên `main` |
| `.github/workflows/pages.yml` | mỗi push lên `main` | đăng PDF lên **GitHub Pages** → link công khai để gửi thầy hướng dẫn |

## Dùng thế nào

```bash
cd intrusion-detection-cicids2017
git init && git add . && git commit -m "init paper scaffold"
git branch -M main
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```

Sau đó vào tab **Actions** xem build; tải PDF ở **Artifacts** hoặc **Releases**.
Bật Pages: **Settings → Pages → Source: GitHub Actions** để có link đọc online.

## Biên dịch tại máy (tùy chọn, nếu có TeX Live/MiKTeX)

```bash
latexmk -pdf main.tex      # llncs class + splncs04.bst, bibtex tự chạy
```

## Cấu trúc

```
intrusion-detection-cicids2017/
├── main.tex            # bài báo (Springer LNCS) — đã có sẵn outline đầy đủ
├── references.bib      # tài liệu tham khảo (CICIDS2017, XGBoost, ...)
├── figures/            # hình (kiến trúc, ROC, confusion matrix)
├── .github/workflows/  # build.yml + pages.yml
├── .gitignore
└── README.md
```

## Việc còn lại
- [ ] Điền số liệu vào 2 bảng trong Mục 5 (chạy thí nghiệm trên Colab — **notebook khung sẽ làm ở bước sau**).
- [ ] Thay tên tác giả thật (bạn = tác giả chính; GV HCMUT = corresponding).
- [ ] Thêm 3–5 tài liệu tham khảo mới (2022–2025) đúng domain của venue.
- [ ] Thêm hình kiến trúc cloud-native + biểu đồ ROC.
- [ ] Đổi `\documentclass{llncs}` sang template chính thức của ICTA/FDSE nếu BTC yêu cầu bản riêng.

> Lưu ý: ICTA/FDSE dùng **Springer LNCS/CCIS** nên `llncs` là đúng hệ. `llncs.cls`
> và `splncs04.bst` đều có sẵn trong TeX Live đầy đủ mà `latex-action` dùng, nên
> build chạy ngay không cần cài thêm.
