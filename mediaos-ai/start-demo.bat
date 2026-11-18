@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title MEDIA OS AI - DEMO

echo ============================================
echo   MEDIA OS AI - DGK Demo (lokal model)
echo ============================================
echo.

docker version >nul 2>&1
if errorlevel 1 (
  echo [XETA] Docker Desktop islemir.
  echo Docker Desktop-u acin ^(ve ya qurasdirin: https://www.docker.com/products/docker-desktop/^), sonra bu fayli yeniden acin.
  pause
  exit /b 1
)

if not exist backend\.env copy backend\.env.example backend\.env >nul

set "FILES=-f docker-compose.yml"
nvidia-smi >nul 2>&1
if errorlevel 1 (
  echo [i] NVIDIA GPU tapilmadi - model CPU-da isleyecek, kicik model secilir ^(qwen2.5:3b-instruct^).
  set "MEDIAOS_OLLAMA_MODEL=qwen2.5:3b-instruct"
) else (
  echo [i] NVIDIA GPU tapildi - qwen2.5:7b-instruct GPU-da isleyecek.
  set "FILES=-f docker-compose.yml -f docker-compose.gpu.yml"
  set "MEDIAOS_OLLAMA_MODEL=qwen2.5:7b-instruct"
)

echo.
echo [1/4] Servisler qurulur ve ise salinir (ilk defe 5-15 deqiqe ceke biler)...
docker compose %FILES% up -d --build
if errorlevel 1 (
  echo [XETA] docker compose ugursuz oldu. Yuxaridaki mesaji Claude-a gonderin.
  pause
  exit /b 1
)

echo [2/4] Lokal model yuklenir (ilk defe ~2-5 GB, internet suretinden asilidir)...
docker compose %FILES% logs -f ollama-pull
docker compose %FILES% wait ollama-pull >nul 2>&1

echo [3/4] Demo melumatlari yuklenir (yalniz baza bosdursa)...
docker compose %FILES% exec -T api python -m scripts.seed

echo [4/4] Hazirdir. Brauzer acilir: http://localhost:8000
echo Giris tokenleri: mos_dev_admin_token / mos_dev_analyst_token / mos_dev_viewer_token
start "" http://localhost:8000
echo.
echo Dayandirmaq ucun: stop-demo.bat
pause
