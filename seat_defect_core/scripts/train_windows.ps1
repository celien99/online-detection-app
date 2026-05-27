# ============================================================
# seat_defect_core Windows GPU 训练脚本
# 用法:
#   1. 将此文件所在目录（seat_defect_core/）拷贝到 Windows 机器
#   2. 组织训练数据: D:\training_data\<camera_id>\good\*.jpg
#   3. 运行: powershell -File scripts\train_windows.ps1
# ============================================================

param(
    [string]$GoodImagesRoot = "D:\training_data",
    [string]$OutputRoot = "D:\models\seat_model_a",
    [string]$Config = ".\config.best.json",
    [string]$Cameras = "",           # 留空=全部，指定用逗号分隔如 "cam_back,cam_front"
    [string]$MlflowUri = "",         # MLflow 地址，留空则跳过
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

# 1. 检查 conda 环境
Write-Host "=== 检查 Python 环境 ===" -ForegroundColor Cyan
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: 未找到 Python，请先安装 miniconda 并创建环境:" -ForegroundColor Red
    Write-Host ""
    Write-Host "  conda create -n seat_train python=3.11 -y" -ForegroundColor Yellow
    Write-Host "  conda activate seat_train" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  # PyTorch (CUDA 12.1)" -ForegroundColor Yellow
    Write-Host "  pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  # 检测核心依赖" -ForegroundColor Yellow
    Write-Host "  pip install anomalib>=1.0.0 opencv-python>=4.9.0 ultralytics>=8.2.0 numpy>=1.26.0 requests>=2.31.0" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  # 可选: MLflow 追踪" -ForegroundColor Yellow
    Write-Host "  pip install mlflow" -ForegroundColor Yellow
    exit 1
}
Write-Host "  OK: $pythonVersion" -ForegroundColor Green

# 2. 检查 CUDA
Write-Host "=== 检查 CUDA ===" -ForegroundColor Cyan
$cudaCheck = python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  警告: torch 未安装或不可用，请先安装 PyTorch" -ForegroundColor Yellow
} else {
    Write-Host "  $cudaCheck" -ForegroundColor Green
}

# 3. 检查训练数据
Write-Host "=== 检查训练数据 ===" -ForegroundColor Cyan
if (-not (Test-Path $GoodImagesRoot)) {
    Write-Host "  错误: 训练数据目录不存在: $GoodImagesRoot" -ForegroundColor Red
    Write-Host "  期望结构: $GoodImagesRoot\<camera_id>\good\*.jpg" -ForegroundColor Yellow
    Write-Host "  例如: $GoodImagesRoot\cam_back\good\0001.jpg" -ForegroundColor Yellow
    exit 1
}

$cameraDirs = Get-ChildItem -Path $GoodImagesRoot -Directory
foreach ($dir in $cameraDirs) {
    $goodDir = Join-Path $dir.FullName "good"
    $count = 0
    if (Test-Path $goodDir) {
        $count = (Get-ChildItem -Path $goodDir -Filter "*.jpg" -File).Count + (Get-ChildItem -Path $goodDir -Filter "*.png" -File).Count
    }
    Write-Host "  $($dir.Name): $count 张图像" -ForegroundColor $(if ($count -ge 50) { "Green" } else { "Yellow" })
}

# 4. 构建命令
$cmdArgs = @(
    "-m", "seat_defect_core", "batch-train",
    "--config", $Config,
    "--good-images-root", $GoodImagesRoot,
    "--output-root", $OutputRoot
)

if ($Cameras) {
    $cmdArgs += "--cameras"
    $cmdArgs += $Cameras
}
if ($MlflowUri) {
    $cmdArgs += "--mlflow-uri"
    $cmdArgs += $MlflowUri
}
if ($DryRun) {
    $cmdArgs += "--dry-run"
}

Write-Host "=== 开始训练 ===" -ForegroundColor Cyan
Write-Host "  命令: python $($cmdArgs -join ' ')" -ForegroundColor White
Write-Host ""

python @cmdArgs

Write-Host ""
Write-Host "=== 训练完成 ===" -ForegroundColor Cyan
Write-Host "  模型输出: $OutputRoot" -ForegroundColor Green
if (-not $DryRun) {
    Write-Host ""
    Write-Host "  生成文件:" -ForegroundColor White
    Get-ChildItem -Path $OutputRoot -Filter "*.pt" | ForEach-Object { Write-Host "    $($_.Name)" }
    Get-ChildItem -Path $OutputRoot -Filter "*.meta.json" | ForEach-Object { Write-Host "    $($_.Name)" }
}
