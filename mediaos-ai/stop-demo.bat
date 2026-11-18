@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo MEDIA OS AI dayandirilir (melumatlar ve yuklenmis model saxlanilir)...
docker compose -f docker-compose.yml -f docker-compose.gpu.yml stop
echo Dayandirildi.
pause
