"""CPU/GPU 温度桌面悬浮图标（Windows / PyQt5，基于嵌入式 LibreHardwareMonitor）。

显示：
  CPU  温度 / 占用率 / 功率
  GPU  温度 / 占用率 / 功率
  内存 占用率

特性：
- 无边框圆角半透明悬浮窗，始终置顶
- 鼠标拖动移动位置；右键菜单切换「鼠标穿透」
- 数值按阈值变色（温度：绿/黄/红）
- 系统托盘：显示/隐藏、退出
- 每 2 秒刷新
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt5.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QLinearGradient,
    QIcon,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QWidget,
)

from temp_source import Stats, get_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("cpu_temp_widget")

# 日志也写到文件，便于排查（写到 exe/脚本所在目录）
try:
    import os as _os
    import sys as _sys
    # 打包后：写到 exe 旁边；普通运行：写到脚本旁边
    _log_dir = _os.path.dirname(_os.path.abspath(_sys.executable)) \
        if getattr(_sys, "frozen", False) \
        else _os.path.dirname(_os.path.abspath(__file__))
    _fh = logging.FileHandler(
        _os.path.join(_log_dir, "run.log"),
        encoding="utf-8",
    )
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(_fh)
except Exception:
    pass

# ---- 配置 ----
REFRESH_INTERVAL_MS = 2000

# 温度阈值（℃）
CPU_WARN, CPU_HOT = 70.0, 85.0
GPU_WARN, GPU_HOT = 65.0, 80.0

# ---- 配色 ----
COL_BG_TOP = QColor(28, 30, 40, 225)
COL_BG_BOT = QColor(14, 16, 24, 225)
COL_BORDER = QColor(255, 255, 255, 45)
COL_LABEL = QColor(150, 158, 175)
COL_VAL_OK = QColor(220, 226, 235)
COL_NONE = QColor(120, 128, 140)


def temp_color(temp: Optional[float], warn: float, hot: float) -> QColor:
    if temp is None:
        return COL_NONE
    if temp >= hot:
        return QColor(244, 67, 54)
    if temp >= warn:
        return QColor(255, 193, 7)
    return QColor(76, 200, 120)


def load_color(load: Optional[float]) -> QColor:
    if load is None:
        return COL_NONE
    if load >= 90:
        return QColor(244, 67, 54)
    if load >= 60:
        return QColor(255, 193, 7)
    return QColor(76, 200, 120)


@dataclass
class Row:
    label: str
    value: Optional[float]
    suffix: str = ""
    fmt: str = "{:.0f}"
    color: QColor = COL_VAL_OK


class TempWidget(QWidget):
    """圆角半透明悬浮窗，显示 CPU/GPU/内存多行信息。"""

    def __init__(self) -> None:
        super().__init__()
        self._stats: Stats = Stats()
        self._drag_offset: Optional[QPoint] = None
        self._click_through = False

        self._init_window()

    # ---- 初始化 ----
    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.setFixedSize(220, 205)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - 240, screen.top() + 20)

    # ---- 数据 ----
    def set_stats(self, stats: Stats) -> None:
        self._stats = stats
        self.update()

    # ---- 鼠标穿透 ----
    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        if enabled:
            self.setWindowFlags(self.windowFlags() | Qt.WindowTransparentForInput)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowTransparentForInput)
        self.show()

    def toggle_click_through(self) -> None:
        self.set_click_through(not self._click_through)

    # ---- 拖动 ----
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        event.accept()

    # ---- 绘制 ----
    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        w, h = self.width(), self.height()
        radius = 16.0

        # 背景
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, COL_BG_TOP)
        grad.setColorAt(1.0, COL_BG_BOT)
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), radius, radius)

        # 边框
        p.setBrush(Qt.NoBrush)
        p.setPen(COL_BORDER)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), radius, radius)

        # 标题
        title_font = QFont("Segoe UI", 12, QFont.Bold)
        p.setFont(title_font)
        p.setPen(QColor(200, 206, 220))
        p.drawText(QRectF(16, 8, w - 32, 22), Qt.AlignLeft, "硬件监控")

        s = self._stats

        # 三组行：CPU / GPU / 内存
        def fmt(val, kind, warn, hot=0, suffix=""):
            if val is None:
                return ("--", COL_NONE)
            if kind == "temp":
                return (f"{val:.0f}{suffix}", temp_color(val, warn, hot))
            if kind == "load":
                return (f"{val:.0f}{suffix}", load_color(val))
            # power / 其他：默认色
            return (f"{val:.0f}{suffix}", COL_VAL_OK)

        rows = [
            # CPU
            ("CPU", [
                fmt(s.cpu_temp, "temp", CPU_WARN, CPU_HOT, "°"),
                fmt(s.cpu_load, "load", 0, 0, "%"),
                fmt(s.cpu_power, "power", 0, 0, "W"),
            ]),
            # GPU
            ("GPU", [
                fmt(s.gpu_temp, "temp", GPU_WARN, GPU_HOT, "°"),
                fmt(s.gpu_load, "load", 0, 0, "%"),
                fmt(s.gpu_power, "power", 0, 0, "W"),
            ]),
            # 内存
            ("MEM", [
                fmt(s.mem_load, "load", 0, 0, "%"),
            ]),
        ]

        label_font = QFont("Segoe UI", 12, QFont.Bold)
        val_font = QFont("Segoe UI", 12)

        top_y = 36
        row_h = 32
        for group_name, items in rows:
            # 组标签
            p.setFont(label_font)
            p.setPen(QColor(110, 200, 255))
            p.drawText(QRectF(16, top_y, 50, 22), Qt.AlignLeft | Qt.AlignVCenter, group_name)
            # 三个数值
            n = len(items)
            slot_w = (w - 70) / max(n, 1)
            for i, (text, color) in enumerate(items):
                p.setFont(val_font)
                p.setPen(color)
                x = 64 + i * slot_w
                p.drawText(QRectF(x, top_y, slot_w, 22), Qt.AlignRight | Qt.AlignVCenter, text)
            top_y += row_h


def make_tray_icon(app: QApplication, widget: TempWidget) -> QSystemTrayIcon:
    """系统托盘图标及菜单。"""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QColor(76, 200, 120))
    painter.setPen(QColor(255, 255, 255, 60))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor(255, 255, 255))
    painter.setFont(QFont("Segoe UI", 22, QFont.Bold))
    painter.drawText(pix.rect(), Qt.AlignCenter, "H")
    painter.end()

    tray = QSystemTrayIcon(QIcon(pix), app)
    tray.setToolTip("硬件监控悬浮窗")

    menu = QMenu()
    toggle_vis = QAction("显示/隐藏", menu)
    toggle_vis.triggered.connect(
        lambda: widget.hide() if widget.isVisible() else widget.show()
    )
    menu.addAction(toggle_vis)

    toggle_click = QAction("切换鼠标穿透", menu)
    toggle_click.triggered.connect(widget.toggle_click_through)
    menu.addAction(toggle_click)

    menu.addSeparator()

    quit_action = QAction("退出", menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: (
            widget.hide() if widget.isVisible() else widget.show()
        )
        if reason == QSystemTrayIcon.DoubleClick
        else None
    )
    return tray


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    widget = TempWidget()
    widget.show()

    tray = make_tray_icon(app, widget)
    tray.show()

    _warned_no_data = {"v": False}

    def refresh() -> None:
        stats = get_stats()
        widget.set_stats(stats)
        if stats.cpu_temp is not None or stats.gpu_temp is not None:
            tip = f"CPU {stats.cpu_temp or '--'}°C | GPU {stats.gpu_temp or '--'}°C"
            tray.setToolTip(tip)
        else:
            tray.setToolTip("读取失败：请以管理员身份运行（UAC 点“是”）")
            if not _warned_no_data["v"]:
                _warned_no_data["v"] = True
                log.warning("读不到硬件数据。请以管理员身份启动本程序。")

    refresh()
    timer = QTimer()
    timer.timeout.connect(refresh)
    timer.start(REFRESH_INTERVAL_MS)

    log.info("硬件监控悬浮窗已启动")
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
