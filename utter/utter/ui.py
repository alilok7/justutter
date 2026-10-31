"""Midnight Glass UI (PySide6): floating bar, dashboard, tray icon and learn dialog."""

from __future__ import annotations

import ctypes
import logging
import math
import os
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utter import APP_NAME

if TYPE_CHECKING:
    from utter.app import UtterApp
    from utter.personal import CorrectionProposal

log = logging.getLogger(__name__)

BG = "#101216"
PANEL = "#15171C"
CARD = "#1C1F26"
TEXT = "#F4F5F7"
MUTED = "#A7ADB8"
FAINT = "#6F7682"
ACCENT = "#3EE6B5"
WARN = "#FFB547"
DANGER = "#FF6B6B"
MODE_COLORS = {"email": "#7FD3FF", "chat": "#B3A9FF", "dev": ACCENT, "default": MUTED}


def ui_font() -> str:
    families = set(QFontDatabase.families())
    return next((f for f in ("Inter", "Segoe UI Variable Text", "Segoe UI") if f in families),
                "Sans Serif")


def make_app() -> QApplication:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont(ui_font(), 10))
    app.setWindowIcon(logo_icon())
    return app


def logo_pixmap(size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 40
    p.setPen(QPen(QColor(255, 255, 255, 36), 1))
    p.setBrush(QColor("#0B0C0F"))
    p.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), 12 * s, 12 * s)
    pen = QPen(QColor(ACCENT), 3 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(QPointF(12 * s, 14 * s))
    path.lineTo(12 * s, 20 * s)
    path.arcTo(QRectF(12 * s, 12 * s, 16 * s, 16 * s), 180, 180)
    path.lineTo(28 * s, 14 * s)
    p.drawPath(path)
    p.drawLine(QPointF(20 * s, 17 * s), QPointF(20 * s, 23 * s))
    p.end()
    return pm


def logo_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        icon.addPixmap(logo_pixmap(size))
    return icon


# --- Floating bar ---------------------------------------------------------------------------

class FloatingBar(QWidget):
    """Hidden while idle; fades in at bottom-centre; never activates or takes input."""

    HEIGHT = 44  # design units; the whole bar is drawn at `scale` of this size
    MARGIN = 10  # room for the glow ring and shadow
    MIN_TEXT_PT = 7.0  # text never shrinks below this, so it stays readable

    def __init__(self, level_source: Callable[[], float] = lambda: 0.0,
                 scale: float = 1.0, minimal: bool = True) -> None:
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.WindowDoesNotAcceptFocus
                            | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.level_source = level_source
        self.state = "ready"
        self.text = ""
        self.detail = ""
        self._levels = [0.0] * 5
        self._phase = 0.0
        self._started = time.monotonic()
        self.scale = scale
        self.minimal = minimal
        # Fonts are sized in design units (the painter is scaled), so divide by the scale to
        # get the on-screen size, floored for legibility.
        self._font = QFont(ui_font())
        self._font.setPointSizeF(max(self.MIN_TEXT_PT, 10 * scale) / scale)
        self._font.setWeight(QFont.Weight.Medium)
        self._detail_font = QFont(ui_font())
        self._detail_font.setPointSizeF(max(self.MIN_TEXT_PT - 0.5, 9 * scale) / scale)
        self._anim = QTimer(self)
        self._anim.setInterval(33)
        self._anim.timeout.connect(self._step)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(lambda: self.set("ready", ""))
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._fade_done)

    # public API ------------------------------------------------------------------------------
    def set(self, state: str, text: str, detail: str = "", revert_ms: int | None = None) -> None:
        self._hide_timer.stop()
        if state == "ready":
            self._fade_to(0.0, 260)
            return
        if state != self.state and state in ("listening", "handsfree", "working"):
            self._started = time.monotonic()
        if self.minimal:  # icons speak for themselves; results get one short word
            detail = ""
            if state in ("listening", "working"):
                text = ""
        self.state, self.text, self.detail = state, text, detail
        self._relayout()
        if not self.isVisible() or self._fade.endValue() == 0.0:
            self._show_faded()
        self.update()
        if revert_ms:
            self._hide_timer.start(revert_ms)

    @property
    def shown(self) -> bool:
        return self.isVisible() and self.state != "ready"

    # layout & animation ----------------------------------------------------------------------
    def _content_width(self) -> int:
        fm, dfm = QFontMetrics(self._font), QFontMetrics(self._detail_font)
        icon = 27 if self.state in ("listening", "handsfree") else 22
        if self.state == "handsfree":
            icon += 21
        width = 14 + icon + 14
        if self.text:
            width += fm.horizontalAdvance(self.text) + 14
        if self.detail:
            width += 10 + dfm.horizontalAdvance(self.detail)
        return width

    def _relayout(self) -> None:
        w = math.ceil((self._content_width() + 2 * self.MARGIN) * self.scale)
        h = math.ceil((self.HEIGHT + 2 * self.MARGIN) * self.scale)
        screen = QApplication.primaryScreen()
        area = screen.availableGeometry() if screen else None
        self.resize(w, h)
        if area is not None:
            self.move(area.x() + (area.width() - w) // 2, area.y() + area.height() - h - 16)

    def _show_faded(self) -> None:
        self.setWindowOpacity(0.0)
        self.show()
        self._make_non_activating()
        self._anim.start()
        self._fade_to(1.0, 120)

    def _fade_to(self, value: float, ms: int) -> None:
        self._fade.stop()
        self._fade.setDuration(ms)
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(value)
        self._fade.start()

    def _fade_done(self) -> None:
        if self._fade.endValue() == 0.0:
            self.hide()
            self._anim.stop()
            self.state = "ready"

    def _make_non_activating(self) -> None:
        if os.name != "nt":
            return
        user32 = ctypes.windll.user32
        hwnd = int(self.winId())
        style = user32.GetWindowLongW(hwnd, -20)
        user32.SetWindowLongW(hwnd, -20, style | 0x08000000 | 0x00000080 | 0x00000020)

    def _step(self) -> None:
        self._phase += 0.33
        if self.state in ("listening", "handsfree"):
            level = min(1.0, max(0.0, self.level_source() * 9.0))
            self._levels = self._levels[1:] + [level]
            if self.state == "handsfree":
                elapsed = int(time.monotonic() - self._started)
                text = f"{elapsed // 60}:{elapsed % 60:02d}"
                if text != self.text:
                    self.text = text
                    self._relayout()
        self.update()

    # painting --------------------------------------------------------------------------------
    def paintEvent(self, _event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.scale(self.scale, self.scale)
        m = self.MARGIN
        rect = QRectF(m, m, self.width() / self.scale - 2 * m, self.HEIGHT)
        radius = self.HEIGHT / 2
        if self.state in ("listening", "handsfree"):
            glow = QColor(ACCENT)
            glow.setAlpha(46)
            p.setPen(QPen(glow, 6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), radius + 2, radius + 2)
        border = QColor(WARN if self.state == "warn" else DANGER if self.state == "error"
                        else "#FFFFFF")
        border.setAlpha(110 if self.state in ("warn", "error") else 26)
        p.setPen(QPen(border, 1))
        p.setBrush(QColor(11, 12, 15, 225))
        p.drawRoundedRect(rect, radius, radius)

        x = rect.left() + 14
        cy = rect.center().y()
        if self.state == "handsfree":
            dot = QColor(DANGER)
            dot.setAlphaF(0.55 + 0.45 * (0.5 + 0.5 * math.sin(self._phase)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(dot)
            p.drawEllipse(QPointF(x + 4.5, cy), 4.5, 4.5)
            x += 21
        if self.state in ("listening", "handsfree"):
            x = self._paint_wave(p, x, cy)
        elif self.state == "working":
            x = self._paint_spinner(p, x, cy)
        else:
            x = self._paint_badge(p, x, cy)
        x += 14
        p.setPen(QColor(TEXT))
        p.setFont(self._font)
        fm = QFontMetrics(self._font)
        p.drawText(QPointF(x, cy + fm.ascent() / 2 - 1), self.text)
        if self.detail:
            x += fm.horizontalAdvance(self.text) + 10
            p.setPen(QColor(MUTED))
            p.setFont(self._detail_font)
            dfm = QFontMetrics(self._detail_font)
            p.drawText(QPointF(x, cy + dfm.ascent() / 2 - 1), self.detail)
        p.end()

    def _paint_wave(self, p: QPainter, x: float, cy: float) -> float:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ACCENT))
        for i, level in enumerate(self._levels):
            idle = 0.18 + 0.08 * math.sin(self._phase + i * 1.3)
            h = 4 + 14 * max(idle, level)
            p.drawRoundedRect(QRectF(x + i * 6, cy - h / 2, 3, h), 1.5, 1.5)
        return x + 27

    def _paint_spinner(self, p: QPainter, x: float, cy: float) -> float:
        box = QRectF(x + 3, cy - 8, 16, 16)
        p.setPen(QPen(QColor(255, 255, 255, 46), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(box)
        p.setPen(QPen(QColor(ACCENT), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(box, int(-self._phase * 57.3 * 16 * 1.6) % (360 * 16), 90 * 16)
        return x + 22

    def _paint_badge(self, p: QPainter, x: float, cy: float) -> float:
        c = QPointF(x + 11, cy)
        if self.state == "done":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawEllipse(c, 11, 11)
            pen = QPen(QColor("#0B0C0F"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            path = QPainterPath(QPointF(c.x() - 4.5, c.y() + 0.2))
            path.lineTo(c.x() - 1.5, c.y() + 3.2)
            path.lineTo(c.x() + 4.5, c.y() - 3.4)
            p.drawPath(path)
        elif self.state in ("warn", "error", "paused"):
            color = QColor(DANGER if self.state == "error" else WARN if self.state == "warn"
                           else MUTED)
            p.setPen(QPen(color, 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, 8, 8)
            if self.state == "paused":
                p.drawLine(QPointF(c.x() - 2, c.y() - 3.5), QPointF(c.x() - 2, c.y() + 3.5))
                p.drawLine(QPointF(c.x() + 2, c.y() - 3.5), QPointF(c.x() + 2, c.y() + 3.5))
            else:
                p.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(c.x(), c.y() - 4), QPointF(c.x(), c.y() + 0.8))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                p.drawEllipse(QPointF(c.x(), c.y() + 3.6), 1, 1)
        else:  # cancelled
            p.setPen(QPen(QColor(MUTED), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(c.x() - 4, c.y() - 4), QPointF(c.x() + 4, c.y() + 4))
            p.drawLine(QPointF(c.x() + 4, c.y() - 4), QPointF(c.x() - 4, c.y() + 4))
        return x + 22


# --- Small widgets ----------------------------------------------------------------------------

class Toggle(QAbstractButton):
    def __init__(self, checked: bool, on_change: Callable[[bool], None]) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(on_change)

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    def paintEvent(self, _event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ACCENT if on else "#3A3F4A"))
        p.drawRoundedRect(QRectF(0, 0, 40, 22), 11, 11)
        p.setBrush(QColor("#0B0C0F" if on else TEXT))
        p.drawEllipse(QPointF(29 if on else 11, 11), 8, 8)
        p.end()


def label(text: str, color: str = TEXT, size: int = 10, weight: int = 400,
          wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(f"color: {color}; font-size: {size}pt; font-weight: {weight};"
                      "background: transparent;")
    lab.setWordWrap(wrap)
    return lab


def card(layout: QVBoxLayout | QHBoxLayout | QGridLayout) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setLayout(layout)
    return frame


def stat_card(title: str) -> tuple[QFrame, QLabel, QLabel]:
    lay = QVBoxLayout()
    lay.setContentsMargins(18, 14, 18, 14)
    lay.setSpacing(4)
    lay.addWidget(label(title, MUTED, 9))
    value, note = label("-", TEXT, 19, 700), label("", WARN, 9)
    lay.addWidget(value)
    lay.addWidget(note)
    return card(lay), value, note


def relative(at: datetime) -> str:
    secs = int((datetime.now() - at).total_seconds())
    if secs < 60:
        return "now"
    if secs < 3600:
        return f"{secs // 60}m"
    return f"{secs // 3600}h"


STYLE = f"""
QWidget#root {{ background: {BG}; }}
QWidget {{ color: {TEXT}; }}
QFrame#card {{ background: {CARD}; border-radius: 14px; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid rgba(255,255,255,0.08);
               border-radius: 16px; }}
QListWidget#nav {{ background: transparent; border: none; outline: none; font-size: 10.5pt; }}
QListWidget#nav::item {{ height: 38px; padding-left: 12px; border-radius: 10px; color: #D5D9E0; }}
QListWidget#nav::item:selected {{ background: rgba(62,230,181,0.12); color: {ACCENT};
                                  font-weight: 600; }}
QListWidget#nav::item:hover:!selected {{ background: rgba(255,255,255,0.04); }}
QListWidget#list {{ background: {CARD}; border: none; border-radius: 12px; padding: 6px; }}
QListWidget#list::item {{ padding: 8px; border-radius: 8px; }}
QListWidget#list::item:selected {{ background: rgba(62,230,181,0.12); color: {TEXT}; }}
QTextEdit, QLineEdit {{ background: #0F1115; border: 1px solid rgba(255,255,255,0.10);
                        border-radius: 10px; padding: 6px 8px; color: {TEXT};
                        selection-background-color: rgba(62,230,181,0.35); }}
QLineEdit:focus, QTextEdit:focus {{ border-color: {ACCENT}; }}
QPushButton {{ background: transparent; border: 1px solid rgba(255,255,255,0.14);
               border-radius: 10px; padding: 8px 14px; color: {TEXT}; }}
QPushButton:hover {{ background: rgba(255,255,255,0.06); }}
QPushButton#primary {{ background: {ACCENT}; color: #0B0C0F; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #5CF0C6; }}
QTableWidget {{ background: {CARD}; border: none; border-radius: 12px; gridline-color: transparent;
                selection-background-color: rgba(62,230,181,0.14); selection-color: {TEXT}; }}
QHeaderView::section {{ background: {CARD}; color: {MUTED}; border: none; padding: 8px;
                        font-weight: 600; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.14); border-radius: 4px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QMenu {{ background: rgba(21,23,28,0.98); border: 1px solid rgba(255,255,255,0.10);
         border-radius: 12px; padding: 6px; color: {TEXT}; }}
QMenu::item {{ padding: 8px 14px; border-radius: 8px; }}
QMenu::item:selected {{ background: rgba(255,255,255,0.06); }}
QMenu::item:disabled {{ color: {ACCENT}; font-weight: 600; }}
QMenu::separator {{ height: 1px; background: rgba(255,255,255,0.06); margin: 4px 8px; }}
QDialog, QMessageBox {{ background: {PANEL}; }}
"""


# --- Dashboard --------------------------------------------------------------------------------

class Dashboard(QWidget):
    PAGES = ("Home", "History", "Dictionary", "Snippets", "Memory", "Settings")

    def __init__(self, app: UtterApp) -> None:
        super().__init__(None)
        self.app = app
        self.setObjectName("root")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(logo_icon())
        self.resize(1080, 700)
        self.setStyleSheet(STYLE)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)

        side = QVBoxLayout()
        side.setSpacing(14)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(logo_pixmap(36))
        brand.addWidget(logo)
        brand.addWidget(label(APP_NAME, TEXT, 13, 700))
        brand.addStretch(1)
        side.addLayout(brand)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(190)
        for name in self.PAGES:
            self.nav.addItem(QListWidgetItem(name))
        side.addWidget(self.nav, 1)
        quit_btn = QPushButton(f"Quit {APP_NAME}")
        quit_btn.clicked.connect(app.quit)
        side.addWidget(quit_btn)
        outer.addLayout(side)

        self.stack = QStackedWidget()
        panel_lay = QVBoxLayout()
        panel_lay.setContentsMargins(28, 24, 28, 24)
        panel_lay.addWidget(self.stack)
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setLayout(panel_lay)
        outer.addWidget(panel, 1)
        self.stack.addWidget(self._build_home())
        self.stack.addWidget(self._build_history())
        self.stack.addWidget(self._build_dictionary())
        self.stack.addWidget(self._build_snippets())
        self.stack.addWidget(self._build_memory())
        self.stack.addWidget(self._build_settings())
        self.nav.currentRowChanged.connect(self._go)
        self.nav.setCurrentRow(0)

    def _go(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        self.refresh()

    # Home --------------------------------------------------------------------------------------
    def _build_home(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)
        head = QHBoxLayout()
        self.greeting = label("", TEXT, 17, 600)
        head.addWidget(self.greeting)
        head.addStretch(1)
        self.badge = label("", ACCENT, 9, 600)
        self.badge.setStyleSheet(f"color: {ACCENT}; background: rgba(62,230,181,0.12);"
                                 "border-radius: 14px; padding: 6px 12px; font-weight: 600;")
        head.addWidget(self.badge)
        lay.addLayout(head)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        c1, self.saved_value, self.saved_note = stat_card("Saved vs Wispr Pro")
        c2, self.words_value, self.words_note = stat_card("Words this week")
        c3, self.latency_value, self.latency_note = stat_card("Median release-to-text")
        for c in (c1, c2, c3):
            stats.addWidget(c)
        lay.addLayout(stats)

        toggles = QHBoxLayout()
        toggles.setSpacing(12)
        self.polish_toggle = Toggle(self.app.settings.polish_enabled, self.app.set_polish)
        self.learn_toggle = Toggle(self.app.settings.learn_enabled, self.app.set_learning)
        for text, toggle in (("AI polish (local)", self.polish_toggle),
                             ("Learn from me", self.learn_toggle)):
            row = QHBoxLayout()
            row.setContentsMargins(16, 12, 16, 12)
            row.addWidget(label(text, TEXT, 10))
            row.addStretch(1)
            row.addWidget(toggle)
            toggles.addWidget(card(row))
        lay.addLayout(toggles)

        lay.addWidget(label("RECENT", MUTED, 8, 600))
        self.recent = QVBoxLayout()
        self.recent.setSpacing(8)
        lay.addLayout(self.recent)
        lay.addStretch(1)
        self.engine_line = label("", FAINT, 9)
        lay.addWidget(self.engine_line)
        return page

    def refresh_home(self) -> None:
        a, s, cfg = self.app, self.app.stats, self.app.settings
        hour = datetime.now().hour
        self.greeting.setText("Good morning" if hour < 12 else "Good afternoon" if hour < 18
                              else "Good evening")
        blocked = a.guard.blocked_count
        self.badge.setText(f"●  On-device · Network requests: {blocked}")
        price = cfg.wispr_pro_monthly_usd
        self.saved_value.setText(f"${price * 12:.0f} / year")
        self.saved_note.setText(f"Wispr Pro is ${price:.0f}/month · {APP_NAME} is $0")
        self.saved_note.setStyleSheet(f"color: {MUTED}; background: transparent;")
        self.words_value.setText(f"{s.words_week:,}")
        over = s.words_over_free_cap(cfg.wispr_free_weekly_words)
        self.words_note.setText(f"{over:,} over Wispr's free cap" if over else
                                f"Wispr's free cap is {cfg.wispr_free_weekly_words:,}/week")
        median = s.median_latency()
        self.latency_value.setText(f"{median:.1f}s" if median is not None else "-")
        count = s.dictations_total
        self.latency_note.setText(f"{count:,} dictation{'' if count == 1 else 's'}")
        self.latency_note.setStyleSheet(f"color: {MUTED}; background: transparent;")
        polish = (a.polisher.model if a.polisher_ready else "starting") if cfg.polish_enabled \
            else "off"
        self.engine_line.setText(f"Whisper {a.model_name} on CPU · AI polish: {polish} · "
                                 "audio is never saved")
        while self.recent.count():
            item = self.recent.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        items = a.history.items()[:5]
        if not items:
            self.recent.addWidget(label("Hold Ctrl+Win anywhere and speak. Your dictations "
                                        "show up here.", MUTED, 10))
        for d in items:
            row = QHBoxLayout()
            row.setContentsMargins(14, 10, 14, 10)
            color = MODE_COLORS.get(d.mode.value, MUTED)
            chip = QLabel(d.mode.value)
            chip.setStyleSheet(f"color: {color}; background: rgba(255,255,255,0.06);"
                               "border-radius: 6px; padding: 3px 8px; font-size: 8pt;"
                               "font-weight: 600;")
            row.addWidget(chip)
            text = label(d.clean.replace("\n", " ")[:90], "#D5D9E0", 10)
            row.addWidget(text, 1)
            row.addWidget(label(relative(d.at), FAINT, 9))
            self.recent.addWidget(card(row))

    # History -----------------------------------------------------------------------------------
    def _build_history(self) -> QWidget:
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        self.hist = QListWidget()
        self.hist.setObjectName("list")
        self.hist.setFixedWidth(300)
        self.hist.currentRowChanged.connect(self._show_item)
        lay.addWidget(self.hist)
        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(label("Raw transcript (select a misheard word, then Learn correction)",
                              MUTED, 9))
        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        right.addWidget(self.raw_text)
        right.addWidget(label("Inserted text", MUTED, 9))
        self.clean_text = QTextEdit()
        self.clean_text.setReadOnly(True)
        right.addWidget(self.clean_text)
        self.rules = label("", MUTED, 9, wrap=True)
        right.addWidget(self.rules)
        buttons = QHBoxLayout()
        for text, fn in (("Copy raw", lambda: self._copy(self.raw_text)),
                         ("Copy inserted", lambda: self._copy(self.clean_text))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            buttons.addWidget(b)
        learn = QPushButton("Learn correction…")
        learn.setObjectName("primary")
        learn.clicked.connect(self._learn)
        buttons.addWidget(learn)
        buttons.addStretch(1)
        right.addLayout(buttons)
        lay.addLayout(right, 1)
        return page

    def refresh_history(self) -> None:
        current = self.hist.currentRow()
        self.hist.blockSignals(True)
        self.hist.clear()
        for d in self.app.history.items():
            preview = d.clean.replace("\n", " ")[:34]
            self.hist.addItem(f"{d.at:%H:%M}  {d.mode.value:<7}  {preview}")
        self.hist.blockSignals(False)
        if self.hist.count():
            self.hist.setCurrentRow(max(0, min(current, self.hist.count() - 1)))
            self._show_item(self.hist.currentRow())

    def _show_item(self, row: int) -> None:
        items = self.app.history.items()
        if not 0 <= row < len(items):
            return
        d = items[row]
        self.raw_text.setPlainText(d.raw)
        self.clean_text.setPlainText(d.clean)
        changes = "; ".join(d.rules) or "no changes"
        self.rules.setText(f"{d.app or '?'} · {d.mode.value} · {d.action} · {d.latency_s:.2f}s\n"
                           f"Changes: {changes}")

    def _copy(self, widget: QTextEdit) -> None:
        clip = QApplication.clipboard()
        clip.setText(widget.toPlainText())

    def _learn(self) -> None:
        heard = self.raw_text.textCursor().selectedText().strip()
        dialog = GlossaryDialog(self, heard)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.heard and dialog.written:
            self.app.add_glossary(dialog.heard, dialog.written)
            self.refresh()

    # Dictionary ----------------------------------------------------------------------------
    def _build_dictionary(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(label("Dictionary", TEXT, 15, 600))
        lay.addWidget(label("Words Utter should always get right. Stored locally in config.json.",
                            MUTED, 10))
        self.gloss = QTableWidget(0, 2)
        self.gloss.setHorizontalHeaderLabels(["When I hear", "Write"])
        self.gloss.horizontalHeader().setStretchLastSection(True)
        self.gloss.horizontalHeader().setDefaultSectionSize(280)
        self.gloss.verticalHeader().setVisible(False)
        self.gloss.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.gloss.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self.gloss, 1)
        row = QHBoxLayout()
        self.heard_in, self.written_in = QLineEdit(), QLineEdit()
        self.heard_in.setPlaceholderText("When I hear…  (e.g. mera lion)")
        self.written_in.setPlaceholderText("Write…  (e.g. MERaLiON)")
        add = QPushButton("Add")
        add.setObjectName("primary")
        add.clicked.connect(self._add_gloss)
        delete = QPushButton("Delete selected")
        delete.clicked.connect(self._delete_gloss)
        for w in (self.heard_in, self.written_in, add, delete):
            row.addWidget(w)
        lay.addLayout(row)
        return page

    def refresh_dictionary(self) -> None:
        entries = self.app.settings.glossary
        self.gloss.setRowCount(len(entries))
        for i, g in enumerate(entries):
            self.gloss.setItem(i, 0, QTableWidgetItem(g.heard))
            self.gloss.setItem(i, 1, QTableWidgetItem(g.written))

    def _add_gloss(self) -> None:
        heard, written = self.heard_in.text().strip(), self.written_in.text().strip()
        if heard and written:
            self.app.add_glossary(heard, written)
            self.heard_in.clear()
            self.written_in.clear()
            self.refresh_dictionary()

    def _delete_gloss(self) -> None:
        rows = sorted({i.row() for i in self.gloss.selectedIndexes()}, reverse=True)
        for r in rows:
            self.app.remove_glossary(r)
        self.refresh_dictionary()

    # Snippets ------------------------------------------------------------------------------
    def _build_snippets(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(label("Snippets", TEXT, 15, 600))
        lay.addWidget(label("Say the phrase to insert the text. Static text only, never executed. "
                            "Edit them in config.json.", MUTED, 10, wrap=True))
        self.snips = QTableWidget(0, 2)
        self.snips.setHorizontalHeaderLabels(["Say", "Inserts"])
        self.snips.horizontalHeader().setStretchLastSection(True)
        self.snips.horizontalHeader().setDefaultSectionSize(280)
        self.snips.verticalHeader().setVisible(False)
        self.snips.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.snips, 1)
        open_btn = QPushButton("Open config folder")
        open_btn.clicked.connect(lambda: os.startfile(self.app.config_dir))
        lay.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignLeft)
        return page

    def refresh_snippets(self) -> None:
        snippets = self.app.settings.snippets
        self.snips.setRowCount(len(snippets))
        for i, s in enumerate(snippets):
            self.snips.setItem(i, 0, QTableWidgetItem(s.trigger))
            self.snips.setItem(i, 1, QTableWidgetItem(s.text.replace("\n", " ⏎ ")))

    # Memory --------------------------------------------------------------------------------
    def _build_memory(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(label("Personal memory", TEXT, 15, 600))
        lay.addWidget(label("Utter learns your words and style from what you dictate and fix "
                            "(Ctrl+Alt+L). Everything stays in personal.json on this PC.",
                            MUTED, 10, wrap=True))
        row = QHBoxLayout()
        row.setContentsMargins(16, 12, 16, 12)
        row.addWidget(label("Learn from my dictations and corrections", TEXT, 10))
        row.addStretch(1)
        self.learn_toggle2 = Toggle(self.app.settings.learn_enabled, self.app.set_learning)
        row.addWidget(self.learn_toggle2)
        lay.addWidget(card(row))
        self.memory_terms = label("", "#D5D9E0", 10, wrap=True)
        self.memory_stats = label("", MUTED, 9)
        box = QVBoxLayout()
        box.setContentsMargins(16, 14, 16, 14)
        box.addWidget(label("WORDS IT IS LEARNING", MUTED, 8, 600))
        box.addWidget(self.memory_terms)
        box.addWidget(self.memory_stats)
        lay.addWidget(card(box))
        forget = QPushButton("Forget everything")
        forget.clicked.connect(self._forget)
        lay.addWidget(forget, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addStretch(1)
        return page

    def refresh_memory(self) -> None:
        m = self.app.memory
        top = sorted(m.vocab.items(), key=lambda kv: -kv[1])[:24]
        self.memory_terms.setText("  ·  ".join(f"{t} ×{n}" for t, n in top) or
                                  "Nothing yet. Keep dictating.")
        self.memory_stats.setText(f"Corrections learned: {m.corrections_learned} · "
                                  f"Style examples: {len(m.style_examples)}")

    def _forget(self) -> None:
        answer = QMessageBox.question(self, APP_NAME,
                                      "Delete all learned words and style examples?")
        if answer == QMessageBox.StandardButton.Yes:
            self.app.forget_memory()
            self.refresh_memory()

    # Settings ------------------------------------------------------------------------------
    def _build_settings(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(label("Settings", TEXT, 15, 600))
        self.settings_box = QVBoxLayout()
        self.settings_box.setContentsMargins(18, 14, 18, 14)
        self.settings_box.setSpacing(10)
        lay.addWidget(card(self.settings_box))
        buttons = QHBoxLayout()
        open_btn = QPushButton("Open config folder")
        open_btn.clicked.connect(lambda: os.startfile(self.app.config_dir))
        buttons.addWidget(open_btn)
        buttons.addStretch(1)
        lay.addLayout(buttons)
        lay.addWidget(label("Advanced settings live in config.json (validated on load). "
                            "Restart Utter after editing it.", FAINT, 9, wrap=True))
        lay.addStretch(1)
        return page

    def refresh_settings(self) -> None:
        cfg = self.app.settings
        while self.settings_box.count():
            item = self.settings_box.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        chord = "+".join(k.title() for k in cfg.hotkey).replace("Windows", "Win")
        rows = [
            ("Push-to-talk", f"Hold {chord}"),
            ("Hands-free", f"{chord}+Space · finish with {chord} · Esc cancels"),
            ("Undo AI edit", cfg.undo_hotkey.title()),
            ("Learn correction", cfg.correction_hotkey.title()),
            ("Dashboard", cfg.dashboard_hotkey.title()),
            ("Speech model", f"Whisper {cfg.model} (CPU, offline)"),
            ("AI polish model", f"{cfg.polish_model} via Ollama on 127.0.0.1"),
            ("Max recording", f"{cfg.max_recording_s / 60:.0f} minutes"),
        ]
        for name, value in rows:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(label(name, MUTED, 10))
            h.addStretch(1)
            h.addWidget(label(value, TEXT, 10))
            self.settings_box.addWidget(row)

    # visibility ------------------------------------------------------------------------------
    def refresh(self) -> None:
        if not self.isVisible():
            return
        page = self.stack.currentIndex()
        [self.refresh_home, self.refresh_history, self.refresh_dictionary,
         self.refresh_snippets, self.refresh_memory, self.refresh_settings][page]()

    def toggle(self) -> None:
        if self.isVisible() and self.isActiveWindow():
            self.hide()
            return
        self.show()
        self.raise_()
        self.activateWindow()
        self.refresh()

    def tick(self) -> None:
        if self.isVisible() and self.stack.currentIndex() == 0:
            self.refresh_home()


# --- Dialogs ------------------------------------------------------------------------------------

class GlossaryDialog(QDialog):
    def __init__(self, parent: QWidget, heard: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setStyleSheet(STYLE)
        self.heard = ""
        self.written = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        lay.addWidget(label("Teach a correction", TEXT, 12, 600))
        self.heard_in, self.written_in = QLineEdit(heard), QLineEdit()
        self.heard_in.setPlaceholderText("What it heard")
        self.written_in.setPlaceholderText("What it should write")
        lay.addWidget(self.heard_in)
        lay.addWidget(self.written_in)
        lay.addLayout(_buttons(self, "Cancel", "Learn"))
        self.resize(420, 0)

    def accept(self) -> None:
        self.heard, self.written = self.heard_in.text().strip(), self.written_in.text().strip()
        super().accept()


class LearnDialog(QDialog):
    def __init__(self, pairs: Sequence[tuple[str, str]], style_example: bool) -> None:
        super().__init__(None)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(logo_icon())
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)
        lay.addWidget(label("Learn these corrections?" if pairs else "Remember this rewrite?",
                            TEXT, 12, 600))
        for heard, written in pairs:
            row = QLabel(f"{heard}  →  {written}")
            row.setStyleSheet("font-family: 'JetBrains Mono', Consolas, monospace;"
                              "color: #D5D9E0; background: transparent;")
            lay.addWidget(row)
        if style_example:
            lay.addWidget(label("Your rewrite will also be kept as a style example for AI "
                                "polish.", MUTED, 9, wrap=True))
        lay.addLayout(_buttons(self, "Not now", "Learn"))
        self.resize(440, 0)


def _buttons(dialog: QDialog, cancel: str, ok: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.addStretch(1)
    no = QPushButton(cancel)
    no.clicked.connect(dialog.reject)
    yes = QPushButton(ok)
    yes.setObjectName("primary")
    yes.setDefault(True)
    yes.clicked.connect(dialog.accept)
    row.addWidget(no)
    row.addWidget(yes)
    return row


def confirm_learn(proposal: CorrectionProposal) -> bool:
    dialog = LearnDialog(proposal.pairs, proposal.style_example is not None)
    dialog.activateWindow()
    return dialog.exec() == QDialog.DialogCode.Accepted


def error_box(text: str) -> None:
    make_app()
    box = QMessageBox(QMessageBox.Icon.Critical, APP_NAME, text)
    box.setStyleSheet(STYLE)
    box.exec()


# --- Tray ---------------------------------------------------------------------------------------

class Tray(QSystemTrayIcon):
    def __init__(self, app: UtterApp) -> None:
        super().__init__(logo_icon())
        self.app = app
        self.setToolTip(f"{APP_NAME}: hold Ctrl+Win to dictate")
        menu = QMenu()
        menu.setStyleSheet(STYLE)
        self.status = QAction(f"{APP_NAME} is ready", menu)
        self.status.setEnabled(False)
        menu.addAction(self.status)
        menu.addSeparator()
        open_action = QAction("Open dashboard", menu)
        open_action.triggered.connect(app.toggle_dashboard)
        menu.addAction(open_action)
        self.pause_action = QAction("Pause dictation", menu)
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self._pause)
        menu.addAction(self.pause_action)
        self.polish_action = QAction("AI polish", menu)
        self.polish_action.setCheckable(True)
        self.polish_action.setChecked(app.settings.polish_enabled)
        self.polish_action.toggled.connect(app.set_polish)
        menu.addAction(self.polish_action)
        menu.addSeparator()
        quit_action = QAction(f"Quit {APP_NAME}", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(quit_action)
        self._menu = menu
        self.setContextMenu(menu)
        self.activated.connect(self._activated)

    def _pause(self, paused: bool) -> None:
        self.app.set_paused(paused)
        self.status.setText(f"{APP_NAME} is paused" if paused else f"{APP_NAME} is ready")

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.app.toggle_dashboard()
