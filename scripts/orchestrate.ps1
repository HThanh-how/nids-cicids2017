# =====================================================================
#  orchestrate.ps1 — chạy các sub-agent Claude Code (headless) trên PROXY
#  công ty để soạn/sửa bài. "Bộ não" (danh sách task + prompt) do orchestrator
#  soạn sẵn; bạn chỉ chạy script này → token tính vào proxy công ty.
#
#  DÙNG:
#    1) Đặt key cho phiên (KHÔNG hardcode vào file):
#         $env:ANTHROPIC_API_KEY = "fe_oa_..."
#    2) cd vào repo:  cd D:\Phd\BCKH\intrusion-detection-cicids2017
#    3) Chạy:         .\scripts\orchestrate.ps1
#
#  Mỗi task là 1 sub-agent độc lập (không nhớ ngữ cảnh chat) — nên prompt phải
#  tự đủ. Sub-agent tự sửa file trong repo và commit.
# =====================================================================
$ErrorActionPreference = "Stop"

if (-not $env:ANTHROPIC_API_KEY) {
  throw "Chưa set `$env:ANTHROPIC_API_KEY (key proxy công ty). Set rồi chạy lại."
}

# --- cấu hình proxy cho riêng phiên này ---
$env:ANTHROPIC_BASE_URL          = "https://cc.freemodel.dev"
$env:ANTHROPIC_MODEL             = "opus"    # alias -> tự lên đời, không ghim version
$env:ANTHROPIC_SMALL_FAST_MODEL  = "haiku"

function Invoke-SubAgent($name, $prompt) {
  Write-Host "`n=== SUB-AGENT: $name ===" -ForegroundColor Cyan
  # --permission-mode acceptEdits: tự duyệt sửa file (không hỏi từng lần)
  claude -p $prompt --permission-mode acceptEdits
  if ($LASTEXITCODE -ne 0) { Write-Warning "Task '$name' exit $LASTEXITCODE" }
}

# ---------------------------------------------------------------------
# DANH SÁCH TASK — orchestrator điền sẵn. Thêm/bớt tuỳ ý.
# LƯU Ý: task cần SỰ THẬT/trích dẫn (tìm paper, tra số) thì KHÔNG giao cho
# sub-agent proxy (thường KHÔNG có Web Search -> dễ bịa). Để orchestrator làm.
# Sub-agent proxy hợp với: viết lại/trau chuốt prose tự-đủ, refactor, format.
# ---------------------------------------------------------------------
$tasks = @(
  @{ name = "polish-intro"; prompt = @"
Read main.tex in the current repository. Improve ONLY the Introduction section
(Section 1) for clarity and academic tone, keeping Springer LNCS style, the same
\cite{} keys, the three-item contributions list, and the organization paragraph.
Do not touch other sections. Do not add or invent any numbers or citations.
Then commit just main.tex with message: 'Polish introduction'.
"@ }

  @{ name = "polish-method"; prompt = @"
Read main.tex. Improve ONLY Section 4 (Methodology) prose for precision and flow,
keeping the equations, subsections (Models, Experimental Setup, Evaluation Metrics),
and \cite{} keys intact. No invented numbers. Commit main.tex with message:
'Polish methodology'.
"@ }
)

foreach ($t in $tasks) { Invoke-SubAgent $t.name $t.prompt }

Write-Host "`nXong. Xem thay đổi:" -ForegroundColor Green
Write-Host "  git log --oneline -n $($tasks.Count)" -ForegroundColor Green
Write-Host "  git diff HEAD~$($tasks.Count)" -ForegroundColor Green
Write-Host "Push khi ưng:  git push" -ForegroundColor Green
