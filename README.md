# CPU/GPU 温度桌面悬浮图标

一个轻量的 Windows 桌面悬浮窗，实时显示硬件监控信息。

## 显示内容

```
┌─────────────────────────┐
│ 硬件监控                 │
│ CPU    40°   8%   41W    │   温度 / 占用率 / 功率
│ GPU    40°  31%   27W    │   温度 / 占用率 / 功率
│ MEM    21%               │   内存占用率
└─────────────────────────┘
```

- **温度**按阈值变色：绿（正常）/ 黄（警告）/ 红（过热）
- 占用率颜色随高低变化
- 无边框圆角半透明，置顶，可拖动
- 右键菜单切换「鼠标穿透」；系统托盘可显示/隐藏、退出
- 每 2 秒刷新

## 工作原理

内置 `LibreHardwareMonitorLib.dll`（在 `LibreHardwareMonitor/` 目录），通过 pythonnet
直接调用读取 CPU/GPU/内存传感器。

**重要：读取硬件传感器需要管理员权限**，因此启动时会弹 UAC，请点「是」。
只有管理员身份运行才能读到真实数据（否则显示 `--`）。

实测数据示例（i7-14700KF + RTX 3080）：
```
CPU  40°C / 8.5% / 41.5W
GPU  40°C / 31%  / 27.0W
MEM  20.6%
```

## 使用

### 桌面快捷方式（推荐）

桌面双击 **「CPU 温度悬浮窗」** 图标 → UAC 点「是」→ 悬浮窗以管理员身份启动。

### 命令行

```bash
cd cpu_temp_widget
# 提权启动（PowerShell，能读到数据）：
Start-Process pythonw -ArgumentList '"cpu_temp_widget.py"' -Verb RunAs
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `cpu_temp_widget.py` | 主程序：悬浮窗 + 系统托盘 (PyQt5) |
| `temp_source.py` | 数据层：嵌入式 LHM 库读取 CPU/GPU/内存 |
| `app.ico` | 自动生成的图标 |
| `run.log` | 运行日志（排查用） |
| `LibreHardwareMonitor/` | 内置 LHM 库文件 (v0.9.6) |

## 配置

`cpu_temp_widget.py` 顶部：

- `REFRESH_INTERVAL_MS = 2000`  刷新间隔
- `CPU_WARN / CPU_HOT`  CPU 温度黄/红阈值（默认 70 / 85℃）
- `GPU_WARN / GPU_HOT`  GPU 温度黄/红阈值（默认 65 / 80℃）

## 依赖

```bash
pip install -r requirements.txt
```

PyQt5、WMI、psutil、pythonnet。

## 打包成 exe

已提供 `cpu_temp_widget.spec`，可打包成单文件 exe（内置 LHM 库，自动请求管理员权限）：

```bash
pip install pyinstaller
pyinstaller cpu_temp_widget.spec --noconfirm --clean
```

产物在 `dist/CPU温度悬浮窗.exe`（约 46 MB，单文件，无需 Python 环境即可运行）。

- 双击即弹 UAC，点「是」后以管理员身份运行，自动读取 CPU/GPU/内存数据
- 可单独拷贝到其它 Windows 10/11 机器运行（仍是单文件，无需安装）
- `run.log` 会生成在 exe 旁边，便于排查

## 兜底说明

若嵌入式 LHM 库不可用（如移动到其它机器未带 `LibreHardwareMonitor/` 目录），
程序会自动降级：WMI（需单独运行 LHM/OHM 并发布）→ psutil（仅内存/CPU 占用）。

