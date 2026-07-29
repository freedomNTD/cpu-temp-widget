# -*- coding: utf-8 -*-
"""诊断脚本：以管理员身份运行，打印 LHM 读到的所有 CPU 传感器，并写文件。

用法（管理员 PowerShell）:
    python diagnose.py
会在当前目录生成 _diag.txt。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_diag.txt")


def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def main():
    lines = []
    lines.append(f"管理员权限: {is_admin()}")
    lines.append(f"Python: {sys.version}")
    lines.append("")

    try:
        import clr
        dll = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "LibreHardwareMonitor", "LibreHardwareMonitorLib.dll",
        )
        lines.append(f"LHM dll 存在: {os.path.exists(dll)} -> {dll}")
        clr.AddReference(dll)
        from LibreHardwareMonitor.Hardware import Computer

        c = Computer()
        c.IsCpuEnabled = True
        c.IsGpuEnabled = True
        c.IsMemoryEnabled = True
        c.IsMotherboardEnabled = False
        c.IsStorageEnabled = False
        c.IsBatteryEnabled = False
        c.IsNetworkEnabled = False
        c.IsControllerEnabled = False
        c.IsPsuEnabled = False
        c.Open()
        # 探测两次让值稳定
        for _ in range(2):
            for hw in c.Hardware:
                hw.Update()
            time.sleep(0.5)

        lines.append(f"检测到硬件数: {len(list(c.Hardware))}")
        for hw in c.Hardware:
            lines.append(f"=== {hw.Name}  [{hw.HardwareType}] ===")
            for s in hw.Sensors:
                lines.append(f"  {str(s.Name):35s} {str(s.SensorType):14s} = {s.Value}")
            for sub in hw.SubHardware:
                sub.Update()
                lines.append(f"  --- sub: {sub.Name} [{sub.HardwareType}] ---")
                for s in sub.Sensors:
                    lines.append(f"      {str(s.Name):31s} {str(s.SensorType):14s} = {s.Value}")
        c.Close()
    except Exception as e:
        import traceback
        lines.append(f"ERROR {e}")
        lines.append(traceback.format_exc())

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("done ->", out)


if __name__ == "__main__":
    main()
