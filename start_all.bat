@echo off
REM 一键启动：以管理员启动 LibreHardwareMonitor，再启动 CPU 温度悬浮窗
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo [1/2] 以管理员身份启动 LibreHardwareMonitor（请允许 UAC 弹窗）...
if exist "LibreHardwareMonitor\LibreHardwareMonitor.exe" (
    powershell -NoProfile -Command "Start-Process -FilePath '%CD%\LibreHardwareMonitor\LibreHardwareMonitor.exe' -Verb RunAs"
) else (
    echo     未找到 LibreHardwareMonitor，跳过此步。
)

echo [2/2] 启动 CPU 温度悬浮窗...
start "" "%~dp0cpu_temp_widget.py"

echo 完成。悬浮窗将在几秒内显示温度。
timeout /t 2 >nul
