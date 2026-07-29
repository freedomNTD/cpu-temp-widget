# -*- coding: utf-8 -*-
"""下载并解压 LibreHardwareMonitor 库到 ./LibreHardwareMonitor 目录。

因为 LHM 是第三方二进制（体积大），未纳入 git 版本管理。
首次使用前请运行此脚本获取 LHM 库，否则程序读不到硬件数据。

用法:
    python download_lhm.py
"""
import io
import os
import sys
import zipfile
import urllib.request

LHM_VERSION = "v0.9.6"
LHM_URL = (
    "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/"
    f"releases/download/{LHM_VERSION}/LibreHardwareMonitor.zip"
)
DEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LibreHardwareMonitor")


def main() -> int:
    if os.path.exists(os.path.join(DEST_DIR, "LibreHardwareMonitorLib.dll")):
        print(f"已存在: {DEST_DIR}，跳过下载。")
        return 0

    print(f"下载 LibreHardwareMonitor {LHM_VERSION} ...")
    print(LHM_URL)
    req = urllib.request.Request(LHM_URL, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=120).read()
    print(f"下载完成: {len(data)} 字节")

    print(f"解压到: {DEST_DIR}")
    os.makedirs(DEST_DIR, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(DEST_DIR)

    dll = os.path.join(DEST_DIR, "LibreHardwareMonitorLib.dll")
    if os.path.exists(dll):
        print("完成！现在可以运行 cpu_temp_widget.py 或执行打包。")
        return 0
    print("错误：解压后未找到 LibreHardwareMonitorLib.dll", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
