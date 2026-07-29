@echo off
REM 以管理员身份启动 LibreHardwareMonitor（必须提权才能读取 CPU 温度传感器）
chcp 65001 >nul
setlocal
cd /d "%~dp0LibreHardwareMonitor"
if not exist LibreHardwareMonitor.exe (
    echo 找不到 LibreHardwareMonitor.exe
    echo 请确认 cpu_temp_widget\LibreHardwareMonitor 目录存在。
    pause
    exit /b 1
)
echo 正在以管理员身份启动 LibreHardwareMonitor...
powershell -NoProfile -Command "Start-Process -FilePath '%CD%\LibreHardwareMonitor.exe' -Verb RunAs"
echo.
echo 已请求启动（如弹出 UAC，请点“是”）。
echo LibreHardwareMonitor 启动后，CPU 温度悬浮窗即可读到温度。
timeout /t 3 >nul
