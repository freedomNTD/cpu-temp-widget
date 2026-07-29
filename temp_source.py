"""硬件监控数据源（基于嵌入式 LibreHardwareMonitor 库）。

通过 pythonnet 直接调用 LibreHardwareMonitorLib.dll 读取 CPU/GPU/内存传感器。
需要本进程以管理员身份运行，否则传感器 Value 为 None。

WMI / psutil 作为兜底（仅 CPU 温度）。
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


def _resource_dir() -> str:
    """返回资源根目录。

    - PyInstaller 单文件打包后：资源解压到 sys._MEIPASS
    - 普通 Python 运行：使用本文件所在目录
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    return os.path.dirname(os.path.abspath(__file__))


_LHM_DIR = os.path.join(_resource_dir(), "LibreHardwareMonitor")
_LHM_DLL = os.path.join(_LHM_DIR, "LibreHardwareMonitorLib.dll")

_computer = None
_computer_tried = False


@dataclass
class Stats:
    """一行刷新采集到的全部指标。None 表示该项未取到。"""
    cpu_temp: Optional[float] = None     # CPU Package 温度 ℃
    cpu_load: Optional[float] = None     # CPU 总占用率 %
    cpu_power: Optional[float] = None    # CPU Package 功率 W
    gpu_temp: Optional[float] = None     # GPU Core 温度 ℃
    gpu_load: Optional[float] = None     # GPU Core 占用率 %
    gpu_power: Optional[float] = None    # GPU 功率 W
    mem_load: Optional[float] = None     # 内存占用率 %


def _get_computer():
    """初始化并返回嵌入的 LHM Computer 实例。失败返回 None。"""
    global _computer, _computer_tried
    if _computer_tried:
        return _computer
    _computer_tried = True

    if not os.path.exists(_LHM_DLL):
        log.warning("LHM 库不存在: %s", _LHM_DLL)
        return None

    try:
        import clr  # type: ignore
        clr.AddReference(_LHM_DLL)
        from LibreHardwareMonitor.Hardware import Computer  # type: ignore

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
        _computer = c
        # 预热：LHM 部分传感器首次 Update 后值仍为 None，需要几次刷新才稳定
        try:
            import time as _time
            for _ in range(2):
                for hw in c.Hardware:
                    hw.Update()
                _time.sleep(0.3)
        except Exception:
            pass
        log.info("已加载嵌入式 LibreHardwareMonitor 库")
        return c
    except Exception as e:
        log.warning("加载 LibreHardwareMonitor 库失败: %s", e)
        return None


def _stype(s) -> str:
    return str(s.SensorType)


def _read_embedded() -> Stats:
    """从嵌入的 LHM 库一次性读取所有指标。

    采用「按硬件类型分组 + 启发式选值」的通用策略，不依赖具体型号命名，
    自动兼容 Intel/AMD、独显/核显/APU、桌面/笔记本等不同配置：
      CPU 温度: 收集所有核心/封装温度（排除 distance to tjmax）取最大值
                （≈ CPU Package；AMD Tctl 本身即最高核心，逻辑一致）
      CPU 功率: 取所有 CPU 功率读数中的最大值
      CPU 占用: 优先 "total"，否则所有核心占用的平均
      GPU: 支持多块 GPU，取温度最高的那块；每项优先 "core/package"，否则取该 GPU 最高读数
      内存: 认 Memory 类型硬件，排除虚拟内存组
    """
    st = Stats()
    c = _get_computer()
    if c is None:
        return st

    # 各硬件类型分组的传感器值
    cpu_temps = []          # CPU 温度候选
    cpu_loads = []          # CPU 各核心占用
    cpu_total_load = None   # CPU Total 占用
    cpu_powers = []         # CPU 功率候选

    gpu_list = []           # 每块 GPU: dict(temp_cands=[], load=None, power_cands=[])

    try:
        for hw in c.Hardware:
            hw.Update()
            for sub in hw.SubHardware:
                sub.Update()
            htype = str(hw.HardwareType)

            is_cpu = "Cpu" in htype
            is_gpu = "Gpu" in htype
            is_mem = "Memory" in htype and "Virtual" not in htype and "Total" not in htype

            sensors = list(hw.Sensors)
            if is_gpu:
                for sub in hw.SubHardware:
                    sensors.extend(sub.Sensors)

            # GPU 分组容器
            ginfo = None
            if is_gpu:
                ginfo = {"temp_cands": [], "load": None, "power_cands": []}
                gpu_list.append(ginfo)

            for s in sensors:
                t = _stype(s)
                val = s.Value
                if val is None:
                    continue
                name = str(s.Name or "")
                lname = name.lower()
                fval = float(val)

                if is_cpu:
                    if t == "Temperature":
                        # 排除 "Distance to TjMax"（不是真实温度）
                        if "distance" in lname:
                            continue
                        cpu_temps.append(fval)
                    elif t == "Load":
                        if "total" in lname:
                            cpu_total_load = fval
                        else:
                            cpu_loads.append(fval)
                    elif t == "Power":
                        cpu_powers.append(fval)
                elif is_gpu and ginfo is not None:
                    if t == "Temperature":
                        ginfo["temp_cands"].append(fval)
                    elif t == "Load" and ginfo["load"] is None:
                        # 优先 "GPU Core" 占用
                        if "core" in lname:
                            ginfo["load"] = fval
                        elif ginfo["load"] is None:
                            ginfo["load"] = fval
                    elif t == "Power":
                        ginfo["power_cands"].append(fval)
                elif is_mem:
                    if t == "Load" and "memory" in lname:
                        st.mem_load = fval

        # ---- CPU 汇总 ----
        if cpu_temps:
            st.cpu_temp = round(max(cpu_temps), 1)
        if cpu_total_load is not None:
            st.cpu_load = round(cpu_total_load, 1)
        elif cpu_loads:
            st.cpu_load = round(sum(cpu_loads) / len(cpu_loads), 1)
        if cpu_powers:
            st.cpu_power = round(max(cpu_powers), 1)

        # ---- GPU 汇总（多 GPU 取温度最高者显示）----
        best_gpu_temp = None
        best_gpu_load = None
        best_gpu_power = None
        for g in gpu_list:
            # 该 GPU 温度：优先最高（hot spot 或 core 都涵盖）
            g_temp = max(g["temp_cands"]) if g["temp_cands"] else None
            if g_temp is not None and (best_gpu_temp is None or g_temp > best_gpu_temp):
                best_gpu_temp = g_temp
                best_gpu_load = g["load"]
                best_gpu_power = max(g["power_cands"]) if g["power_cands"] else None
        if best_gpu_temp is not None:
            st.gpu_temp = round(best_gpu_temp, 1)
        if best_gpu_load is not None:
            st.gpu_load = round(best_gpu_load, 1)
        if best_gpu_power is not None:
            st.gpu_power = round(best_gpu_power, 1)

    except Exception as e:
        log.warning("嵌入式 LHM 读取异常: %s", e)
    return st


# -------- 兜底：WMI / psutil（仅 CPU 温度） --------

def _via_wmi_cpu_temp() -> Optional[float]:
    try:
        import wmi  # type: ignore
    except Exception:
        return None
    for ns in (r"ROOT\Hardware", r"ROOT\LibreHardwareMonitor", r"ROOT\OpenHardwareMonitor", r"ROOT\HWiNFO"):
        try:
            c = wmi.WMI(namespace=ns)
            sensors = c.Sensor(Type="Temperature")
        except Exception:
            continue
        if not sensors:
            continue
        cpu = []
        for s in sensors:
            name = (s.Name or "").lower()
            parent = (s.Parent or "").lower()
            value = getattr(s, "Value", None)
            if value is None:
                continue
            if "package" in name or "cpu" in name or "cpu" in parent or "/amd" in parent or "/intelcpu" in parent:
                cpu.append(float(value))
        if cpu:
            return round(sum(cpu) / len(cpu), 1)
    return None


def _via_psutil() -> Stats:
    """psutil 兜底：CPU 温度读不到时尝试，内存占用率总能读到。"""
    st = Stats()
    try:
        import psutil  # type: ignore
    except Exception:
        return st
    # 内存
    try:
        st.mem_load = round(psutil.virtual_memory().percent, 1)
    except Exception:
        pass
    # CPU 占用
    try:
        st.cpu_load = round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        pass
    # CPU 温度（Windows 上基本读不到）
    try:
        temps = psutil.sensors_temperatures()  # type: ignore[attr-defined]
    except Exception:
        temps = None
    if temps:
        for name, entries in temps.items():
            if ("cpu" in name.lower() or "core" in name.lower()) and entries:
                st.cpu_temp = round(float(entries[0].current), 1)
                break
    return st


def get_stats() -> Stats:
    """返回当前全部硬件指标。优先嵌入式 LHM，兜底 WMI/psutil。"""
    st = _read_embedded()
    # 若 LHM 没读到 CPU 温度，兜底
    if st.cpu_temp is None:
        st.cpu_temp = _via_wmi_cpu_temp()
    # 若 LHM 整体不可用（全是 None），用 psutil 补内存/CPU 占用
    if all(v is None for v in (
        st.cpu_temp, st.cpu_load, st.cpu_power,
        st.gpu_temp, st.gpu_load, st.gpu_power, st.mem_load,
    )):
        st = _via_psutil()
    return st


# 向后兼容：旧接口只返回 CPU 温度
def get_cpu_temp() -> Optional[float]:
    return get_stats().cpu_temp


if __name__ == "__main__":
    s = get_stats()
    print(s)
