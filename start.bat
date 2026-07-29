@echo off
REM 启动 CPU 温度悬浮窗
cd /d "%~dp0"
python cpu_temp_widget.py
if errorlevel 1 (
    echo.
    echo 运行失败,请先安装依赖: pip install -r requirements.txt
    pause
)
