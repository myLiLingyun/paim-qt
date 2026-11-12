# SPDX-License-Identifier: GPL-3.0-or-later
"""Main Qt6 application window for the Paint clone."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import (QBuffer, QByteArray, QIODevice, QPoint, QPointF, QRect,
                          QRectF, QSize, Qt, QTimer)
from PyQt6.QtGui import (QAction, QActionGroup, QColor, QFont, QFontDatabase,
                         QGuiApplication, QIcon, QImage, QImageReader, QKeySequence,
                         QPainter, QPalette, QPen, QPixmap, QPolygonF)
from PyQt6.QtWidgets import (QApplication, QCheckBox, QColorDialog,
                             QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                             QFontComboBox, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
                             QScrollArea, QSizePolicy, QSlider, QSpinBox,
                             QStatusBar, QStyle, QToolButton, QVBoxLayout,
                             QWidget)
from PyQt6.QtPrintSupport import (QPrintDialog, QPrintPreviewDialog, QPrinter,
                                  QPrinterInfo)

from . import __version__, icons as icon_module
from .dialogs import (AboutDialog, AttributesDialog, ColorDialog, MessageDialog,
                      PageSetupDialog, ResizeDialog, SaveOptionsDialog)
from .document import (Document, Selection, _buffer, _copy_image, _qcolor,
                       hex_to_rgb, rgba_to_hex, surface_to_png_bytes, _to_pil)
from .i18n import language_is_zh
from .raster import (BRUSH_LABELS, BRUSH_ORDER, DEFAULT_PALETTE, LINE_WIDTHS,
                     SHAPE_FILL_STYLES, SHAPE_OUTLINE_STYLES)
from .shapes import (GALLERY_ROWS, SHAPE_LABELS_EN, SHAPE_LABELS_ZH,
                     SHAPE_ORDER)
from .text import text_extents
from .view import PaintCanvas, checker_brush
from . import dialogs


APP_ID = 'io.github.paim.PaintImproved'
APP_NAME = 'paim'


def _system_dark() -> bool:
    env = os.environ.get('GTK_THEME', '').lower()
    if env:
        return 'dark' in env
    # On GNOME the desktop-wide appearance toggle is authoritative.  Ask it
    # first, because Qt can report Light while the session is dark.
    try:
        result = subprocess.run(
            ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
            capture_output=True, text=True, timeout=1.0, check=False)
        value = (result.stdout or '').strip().strip("'").lower()
        if value == 'prefer-dark':
            return True
        if value == 'prefer-light':
            return False
    except Exception:
        pass
    try:
        hints = QGuiApplication.styleHints()
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    return False


def _stylesheet(dark: bool) -> str:
    if not dark:
        return """
        QMainWindow, QWidget#central { background: #f0f0f0; color: #1d1d1d; }
        QWidget#qatBar { background: #f7f7f7; border-bottom: 1px solid #c8c8c8; }
        QWidget#tabBar { background: #f4f4f4; border-bottom: 1px solid #b9b9b9; }
        QToolButton#fileTab { background: #1f6fb2; color: white; border: none;
            border-radius: 3px; padding: 4px 18px; font-size: 13px; }
        QToolButton#fileTab:hover { background: #2b83c9; }
        QToolButton#ribbonTab { border: 1px solid transparent; border-radius: 3px 3px 0 0;
            padding: 4px 16px; background: transparent; font-size: 13px; }
        QToolButton#ribbonTab:hover { background: #e7f1fa; border-color: #b8d3ea; }
        QToolButton#ribbonTab:checked { background: #ffffff; border-color: #b9b9b9;
            border-bottom-color: #ffffff; }
        QWidget#ribbon { background: #fafafa; border-bottom: 1px solid #bfbfbf; }
        QFrame#ribbonGroup { border-right: 1px solid #d7d7d7; }
        QLabel#ribbonCaption { font-size: 10px; color: #444444; }
        QToolButton#ribbonBig { border: 1px solid transparent; border-radius: 3px;
            background: transparent; padding: 2px 3px; font-size: 10px; color: #1d1d1d; }
        QToolButton#ribbonBig:hover { background: #e6f1fb; border-color: #a9c9e7; }
        QToolButton#ribbonBig:checked { background: #d5e9f8; border-color: #82b1dd; }
        QToolButton#ribbonSmall { border: 1px solid transparent; border-radius: 3px;
            background: transparent; padding: 1px 3px; font-size: 11px; color: #1d1d1d; }
        QToolButton#ribbonSmall:hover { background: #e6f1fb; border-color: #a9c9e7; }
        QToolButton#ribbonSmall:checked { background: #d5e9f8; border-color: #82b1dd; }
        QToolButton#quick { border: 1px solid transparent; border-radius: 3px;
            background: transparent; padding: 2px; }
        QToolButton#quick:hover { background: #e3f0fb; border-color: #9dc4e8; }
        QToolButton#paletteSwatch { border: 1px solid #8a8a8a; border-radius: 0; }
        QToolButton#paletteSwatch:hover { border: 1px solid #1a5fa0; }
        QWidget#textBar { background: #fbfbfb; border-bottom: 1px solid #c8c8c8; }
        QLabel#hint { color: #666666; font-size: 11px; }
        QScrollArea { background: #a6b8cc; border: none; }
        QScrollArea > QWidget > QWidget { background: #a6b8cc; }
        QScrollBar:vertical { background: #cfd6e0; width: 14px; }
        QScrollBar:horizontal { background: #cfd6e0; height: 14px; }
        QScrollBar::handle { background: #97a4b5; border-radius: 4px; min-height: 24px; }
        QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
        QSlider::groove:horizontal { height: 4px; background: #cfcfcf; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #2b83c9; border-radius: 2px; }
        QSlider::handle:horizontal { width: 12px; margin: -5px 0; border-radius: 6px;
            background: #f7f7f7; border: 1px solid #8a8a8a; }
        QStatusBar { background: #f5f5f5; border-top: 1px solid #c4c4c4; }
        QStatusBar::item { border: none; }
        QLabel#statusLabel { color: #333333; font-size: 11px; padding: 0 7px; }
        QMenu { background: #fbfbfb; color: #1d1d1d; border: 1px solid #b6b6b6; }
        QMenu::item:selected { background: #d5e9f8; }
        QMenu::item:disabled { color: #999999; }
        QCheckBox, QRadioButton, QLabel { color: #1d1d1d; }
        QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QFontComboBox {
            background: #ffffff; color: #1d1d1d; border: 1px solid #b8b8b8;
            border-radius: 3px; padding: 2px; }
        QDialog { background: #f4f4f4; }
        QTextEdit { background: transparent; }
        """
    return """
        QMainWindow, QWidget#central { background: #1f2023; color: #e9e9ec; }
        QWidget#qatBar { background: #292a2e; border-bottom: 1px solid #3b3c41; }
        QWidget#tabBar { background: #25262a; border-bottom: 1px solid #3a3b40; }
        QToolButton#fileTab { background: #2b6fa9; color: white; border: none;
            border-radius: 3px; padding: 4px 18px; font-size: 13px; }
        QToolButton#fileTab:hover { background: #357fbe; }
        QToolButton#ribbonTab { border: 1px solid transparent; border-radius: 3px 3px 0 0;
            padding: 4px 16px; background: transparent; font-size: 13px; color: #e4e4e7; }
        QToolButton#ribbonTab:hover { background: #343a44; border-color: #4d5b69; }
        QToolButton#ribbonTab:checked { background: #303136; border-color: #4c4d52;
            border-bottom-color: #303136; color: #ffffff; }
        QWidget#ribbon { background: #292a2d; border-bottom: 1px solid #3a3b3f; }
        QFrame#ribbonGroup { border-right: 1px solid #3b3c40; }
        QLabel#ribbonCaption { font-size: 10px; color: #a9abb0; }
        QToolButton#ribbonBig { border: 1px solid transparent; border-radius: 3px;
            background: transparent; padding: 2px 3px; font-size: 10px; color: #e9e9ec; }
        QToolButton#ribbonBig:hover { background: #37414c; border-color: #526271; }
        QToolButton#ribbonBig:checked { background: #31465c; border-color: #5b86b2; }
        QToolButton#ribbonSmall { border: 1px solid transparent; border-radius: 3px;
            background: transparent; padding: 1px 3px; font-size: 11px; color: #e9e9ec; }
        QToolButton#ribbonSmall:hover { background: #37414c; border-color: #526271; }
        QToolButton#ribbonSmall:checked { background: #31465c; border-color: #5b86b2; }
        QToolButton#quick { border: 1px solid transparent; border-radius: 3px;
            background: transparent; padding: 2px; }
        QToolButton#quick:hover { background: #37414c; border-color: #526271; }
        QToolButton#paletteSwatch { border: 1px solid #6d6e72; border-radius: 0; }
        QToolButton#paletteSwatch:hover { border: 1px solid #8fc0ef; }
        QWidget#textBar { background: #292a2d; border-bottom: 1px solid #3a3b3f; }
        QLabel#hint { color: #a1a3a9; font-size: 11px; }
        QScrollArea { background: #181b20; border: none; }
        QScrollArea > QWidget > QWidget { background: #181b20; }
        QScrollBar:vertical { background: #2b2d32; width: 14px; }
        QScrollBar:horizontal { background: #2b2d32; height: 14px; }
        QScrollBar::handle { background: #555a63; border-radius: 4px; min-height: 24px; }
        QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
        QSlider::groove:horizontal { height: 4px; background: #47484c; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #2b83c9; border-radius: 2px; }
        QSlider::handle:horizontal { width: 12px; margin: -5px 0; border-radius: 6px;
            background: #d8d9dc; border: 1px solid #6a6b70; }
        QStatusBar { background: #27282b; border-top: 1px solid #3a3b3f; }
        QStatusBar::item { border: none; }
        QLabel#statusLabel { color: #d2d3d6; font-size: 11px; padding: 0 7px; }
        QMenu { background: #292a2d; color: #e9e9ec; border: 1px solid #4a4b50; }
        QMenu::item:selected { background: #37414c; }
        QMenu::item:disabled { color: #77797f; }
        QMenu::separator { background: #3d3e42; height: 1px; }
        QCheckBox, QRadioButton, QLabel { color: #e9e9ec; }
        QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QFontComboBox {
            background: #202124; color: #e9e9ec; border: 1px solid #47484c;
            border-radius: 3px; padding: 2px; }
        QDialog { background: #242528; }
        QTextEdit { background: transparent; }
        QToolTip { background: #3a3b3f; color: #f4f4f6; }
        """


def _app_palette(dark: bool) -> QPalette:
    """A complete palette so widgets not covered by the stylesheet stay legible."""
    role = QPalette.ColorRole
    group = QPalette.ColorGroup
    palette = QPalette()
    if dark:
        window, window_text = QColor('#1f2023'), QColor('#e9e9ec')
        base, text = QColor('#202124'), QColor('#e9e9ec')
        button, button_text = QColor('#292a2d'), QColor('#e9e9ec')
        disabled = QColor('#77797f')
        tooltip_base, tooltip_text = QColor('#3a3b3f'), QColor('#f4f4f6')
        highlight, highlighted_text = QColor('#2b6fa9'), QColor('#ffffff')
    else:
        window, window_text = QColor('#f0f0f0'), QColor('#1d1d1d')
        base, text = QColor('#ffffff'), QColor('#1d1d1d')
        button, button_text = QColor('#f0f0f0'), QColor('#1d1d1d')
        disabled = QColor('#999999')
        tooltip_base, tooltip_text = QColor('#ffffff'), QColor('#1d1d1d')
        highlight, highlighted_text = QColor('#308cc6'), QColor('#ffffff')
    palette.setColor(role.Window, window)
    palette.setColor(role.WindowText, window_text)
    palette.setColor(role.Base, base)
    palette.setColor(role.AlternateBase, window)
    palette.setColor(role.Text, text)
    palette.setColor(role.Button, button)
    palette.setColor(role.ButtonText, button_text)
    palette.setColor(role.ToolTipBase, tooltip_base)
    palette.setColor(role.ToolTipText, tooltip_text)
    palette.setColor(role.Highlight, highlight)
    palette.setColor(role.HighlightedText, highlighted_text)
    palette.setColor(role.PlaceholderText, disabled)
    palette.setColor(role.BrightText, QColor('#ff5555'))
    for r in (role.WindowText, role.Text, role.ButtonText):
        palette.setColor(group.Disabled, r, disabled)
    return palette


class ColorSwatch(QToolButton):
    """A palette button that distinguishes left and right clicks."""

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color_value = color
        self.setFixedSize(18, 18)
        self.setObjectName('paletteSwatch')
        self.setToolTip(color)
        self.setStyleSheet(
            f'QToolButton {{ background-color: {color}; border: 1px solid #8a8a8a; }}'
            f'QToolButton:hover {{ border: 1px solid #1a5fa0; }}')
        self.clicked.connect(self._left_clicked)
        self.right_clicked = None

    def _left_clicked(self):
        if self._left_handler:
            self._left_handler(self.color_value)

    _left_handler = None

    def set_handlers(self, left, right):
        self._left_handler = left
        self.right_clicked = right
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.right_clicked:
            self.right_clicked(self.color_value)
            event.accept()
            return
        super().mousePressEvent(event)


class RulerWidget(QWidget):
    def __init__(self, canvas, horizontal=True, offset_getter=None, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.horizontal = horizontal
        self.offset_getter = offset_getter or (lambda: 0)
        if horizontal:
            self.setFixedHeight(18)
        else:
            self.setFixedWidth(20)

    def paintEvent(self, event):
        p = QPainter(self)
        dark = getattr(self.canvas, 'dark', False)
        if dark:
            p.fillRect(self.rect(), QColor(41, 42, 45))
            p.setPen(QColor(158, 163, 173))
        else:
            p.fillRect(self.rect(), QColor(239, 239, 239))
            p.setPen(QColor(140, 140, 140))
        z = self.canvas.zoom
        # The scroll area centres the canvas when it fits; map the widget into
        # the viewport so the ruler origin follows both centring and scrolling.
        viewport = self.canvas.parentWidget()
        if viewport is None:
            viewport = self.canvas
        pos = self.canvas.mapTo(viewport, QPoint(0, 0))
        origin = pos.x() if self.horizontal else pos.y()
        width, height = self.width(), self.height()
        length = width if self.horizontal else height
        start_img = max(0, int((-origin - 12) / z) - 50)
        end_img = start_img + int(length / z) + 100
        step = 10
        if z < 0.5:
            step = 50
        elif z < 1:
            step = 20
        for val in range(max(0, (start_img // step) * step), end_img + step, step):
            tick_pos = origin + 12 + val * z
            if tick_pos < -20 or tick_pos > length + 20:
                continue
            major = val % (step * 5) == 0
            tick = 5 if major else 2
            if self.horizontal:
                p.drawLine(QPointF(tick_pos + 0.5, height), QPointF(tick_pos + 0.5, height - tick))
            else:
                p.drawLine(QPointF(width, tick_pos + 0.5), QPointF(width - tick, tick_pos + 0.5))
            if major:
                p.setFont(QFont('Sans', 7))
                if self.horizontal:
                    p.drawText(QPointF(tick_pos + 2, 9), str(val))
                else:
                    p.save()
                    p.translate(9, tick_pos + 2)
                    p.rotate(-90)
                    p.drawText(QPointF(0, 0), str(val))
                    p.restore()
        p.setPen(QPen(QColor(176, 176, 176) if not dark else QColor(71, 72, 76), 1))
        if self.horizontal:
            p.drawLine(QPointF(0, height - 0.5), QPointF(width, height - 0.5))
        else:
            p.drawLine(QPointF(width - 0.5, 0), QPointF(width - 0.5, height))
        p.end()


class ThumbnailWidget(QWidget):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setMinimumSize(158, 120)

    def paintEvent(self, event):
        doc = self.canvas.doc
        if doc.width <= 0 or doc.height <= 0:
            return
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(255, 255, 255))
        w, h = doc.width, doc.height
        scale = min((self.width() - 4) / w, (self.height() - 4) / h)
        x = (self.width() - w * scale) / 2
        y = (self.height() - h * scale) / 2
        p.save()
        p.setClipRect(QRectF(x, y, w * scale, h * scale))
        p.fillRect(QRectF(x, y, w * scale, h * scale), checker_brush(self.canvas.dark, 6))
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawImage(QRectF(x, y, w * scale, h * scale), doc.surface)
        p.restore()
        p.setPen(QPen(QColor(51, 51, 51, 153), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(x, y, w * scale, h * scale))
        p.end()


class PaintWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.lang_zh = language_is_zh()
        self._load_preferences()
        self.qat_registry = {}
        self.qat_buttons = {}
        self._init_qat_registry()
        self.dark_mode = self._resolve_dark()
        self._applying_theme = False
        self._updating_theme_menu = False
        icon_module.set_dark_theme(self.dark_mode)

        self.resize(1500, 900)
        icon_path = Path(__file__).resolve().parent.parent / 'assets' / 'paim.png'
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.doc = Document(768, 432)
        self.recent_files = []
        self.zoom = 1.0
        self.status_visible = True
        self.thumbnail_visible = False
        self._is_fullscreen = False
        self.page_settings = {'landscape': False, 'scale': 100, 'left': 0.5,
                              'top': 0.5, 'center': True}
        self._save_after = None
        self._quick_clipboard = None
        self._force_close = False
        self.actions = {}
        self._load_recent()

        self._build_ui()
        self._build_actions()
        self._build_file_menu()
        self._update_title()
        self._update_action_sensitivity()
        self._sync_palette()
        self._apply_runtime_theme(self.dark_mode, force=True)
        self.setAcceptDrops(True)

        try:
            hints = QGuiApplication.styleHints()
            hints.colorSchemeChanged.connect(self._on_system_theme_changed)
        except Exception:
            pass
        # GNOME does not emit a Qt colour-scheme change on all platforms, so
        # poll cheaply while the theme mode is "follow system".
        self._theme_timer = QTimer(self)
        self._theme_timer.setInterval(4000)
        self._theme_timer.timeout.connect(self._poll_system_theme)
        self._theme_timer.start()

    # ------------------------------------------------------------------
    # Preferences
    def _settings_path(self):
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        return base / 'paim' / 'settings.json'

    def _load_preferences(self):
        self.theme_mode = 'auto'
        self.qat_pinned = ['save', 'undo', 'redo']
        try:
            path = self._settings_path()
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                mode = data.get('theme_mode', 'auto')
                if mode in ('auto', 'light', 'dark'):
                    self.theme_mode = mode
                qat = data.get('qat')
                if isinstance(qat, list):
                    self.qat_pinned = [str(x) for x in qat if isinstance(x, str)]
        except Exception:
            pass
        seen = set()
        self.qat_pinned = [x for x in self.qat_pinned
                           if not (x in seen or seen.add(x))]

    def _save_preferences(self):
        try:
            path = self._settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'theme_mode': self.theme_mode,
                                       'qat': self.qat_pinned},
                                      ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(tmp, path)
        except Exception:
            pass

    def _resolve_dark(self):
        if self.theme_mode == 'dark':
            return True
        if self.theme_mode == 'light':
            return False
        return _system_dark()

    def tr(self, zh, en):
        return zh if self.lang_zh else en

    # ------------------------------------------------------------------
    # UI construction
    def _build_ui(self):
        self.canvas = PaintCanvas(self.doc, language='zh' if self.lang_zh else 'en')
        self.central = QWidget()
        self.central.setObjectName('central')
        self.setCentralWidget(self.central)
        root = QVBoxLayout(self.central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # quick access toolbar
        self.qat_bar = QWidget()
        self.qat_bar.setObjectName('qatBar')
        self.qat_layout = QHBoxLayout(self.qat_bar)
        self.qat_layout.setContentsMargins(4, 1, 4, 1)
        self.qat_layout.setSpacing(1)
        root.addWidget(self.qat_bar)

        # tab bar
        tabbar = QWidget()
        tabbar.setObjectName('tabBar')
        tab_layout = QHBoxLayout(tabbar)
        tab_layout.setContentsMargins(5, 0, 5, 0)
        tab_layout.setSpacing(2)
        self.file_tab = QToolButton()
        self.file_tab.setObjectName('fileTab')
        self.file_tab.setText(self.tr('文件', 'File'))
        self.file_tab.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.file_tab.setToolTip(self.tr('文件', 'File'))
        tab_layout.addWidget(self.file_tab)
        self.home_tab = QToolButton()
        self.home_tab.setObjectName('ribbonTab')
        self.home_tab.setText(self.tr('主页', 'Home'))
        self.home_tab.setCheckable(True)
        self.home_tab.setChecked(True)
        self.home_tab.clicked.connect(lambda: self._switch_ribbon('home'))
        tab_layout.addWidget(self.home_tab)
        self.view_tab = QToolButton()
        self.view_tab.setObjectName('ribbonTab')
        self.view_tab.setText(self.tr('查看', 'View'))
        self.view_tab.setCheckable(True)
        self.view_tab.clicked.connect(lambda: self._switch_ribbon('view'))
        tab_layout.addWidget(self.view_tab)
        tab_layout.addStretch(1)
        help_btn = QToolButton()
        help_btn.setObjectName('ribbonTab')
        help_btn.setText('?')
        help_btn.setToolTip(self.tr('paim 帮助 (F1)', 'paim help (F1)'))
        help_btn.clicked.connect(self._help)
        tab_layout.addWidget(help_btn)
        root.addWidget(tabbar)

        # ribbons
        self.ribbon_stack = QWidget()
        self.ribbon_layout = QVBoxLayout(self.ribbon_stack)
        self.ribbon_layout.setContentsMargins(0, 0, 0, 0)
        self.ribbon_layout.setSpacing(0)
        self.home_ribbon = self._build_home_ribbon()
        self.view_ribbon = self._build_view_ribbon()
        self.ribbon_layout.addWidget(self.home_ribbon)
        self.ribbon_layout.addWidget(self.view_ribbon)
        self.view_ribbon.setVisible(False)
        self.ribbon_stack.setFixedHeight(126)
        root.addWidget(self.ribbon_stack)

        # text toolbar
        self.textbar = self._build_text_bar()
        self.textbar.setVisible(False)
        root.addWidget(self.textbar)

        # central canvas
        center = QWidget()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self.ruler_corner = QWidget()
        self.ruler_corner.setFixedSize(20, 18)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hruler = RulerWidget(self.canvas, True,
                                  lambda: self.scroll.horizontalScrollBar().value())
        self.vruler = RulerWidget(self.canvas, False,
                                  lambda: self.scroll.verticalScrollBar().value())
        grid.addWidget(self.ruler_corner, 0, 0)
        grid.addWidget(self.hruler, 0, 1)
        grid.addWidget(self.vruler, 1, 0)
        grid.addWidget(self.scroll, 1, 1)
        center_layout.addWidget(grid_host, 1)
        self._set_rulers_visible(False)

        # thumbnail panel
        self.thumb_panel = QWidget()
        thumb_layout = QVBoxLayout(self.thumb_panel)
        thumb_layout.setContentsMargins(6, 8, 6, 8)
        thumb_layout.setSpacing(4)
        thumb_label = QLabel(self.tr('缩略图', 'Thumbnail'))
        thumb_label.setObjectName('ribbonCaption')
        thumb_label.setStyleSheet('font-weight: bold;')
        thumb_layout.addWidget(thumb_label)
        self.thumb_area = ThumbnailWidget(self.canvas)
        thumb_layout.addWidget(self.thumb_area)
        thumb_layout.addStretch(1)
        self.thumb_panel.setFixedWidth(180)
        self.thumb_panel.setVisible(False)
        center_layout.addWidget(self.thumb_panel)
        root.addWidget(center, 1)

        # status bar
        self.statusbar = QStatusBar()
        self.statusbar.setSizeGripEnabled(True)
        self.setStatusBar(self.statusbar)
        self.pos_label = QLabel('')
        self.pos_label.setObjectName('statusLabel')
        self.sel_label = QLabel('')
        self.sel_label.setObjectName('statusLabel')
        self.size_label = QLabel('')
        self.size_label.setObjectName('statusLabel')
        self.statusbar.addWidget(self.pos_label)
        self.statusbar.addWidget(self.sel_label)
        self.statusbar.addWidget(self.size_label, 1)
        self.zoom_label = QLabel('100%')
        self.zoom_label.setObjectName('statusLabel')
        zoom_out = QToolButton()
        zoom_out.setObjectName('quick')
        zoom_out.setIcon(icon_module.icon('minus', 13))
        zoom_out.setIconSize(QSize(13, 13))
        zoom_out.setProperty('paint_icon', 'minus')
        zoom_out.setProperty('paint_icon_size', 13)
        zoom_out.setToolTip(self.tr('缩小', 'Zoom out'))
        zoom_out.clicked.connect(self.canvas.zoom_out)
        zoom_in = QToolButton()
        zoom_in.setObjectName('quick')
        zoom_in.setIcon(icon_module.icon('plus', 13))
        zoom_in.setIconSize(QSize(13, 13))
        zoom_in.setProperty('paint_icon', 'plus')
        zoom_in.setProperty('paint_icon_size', 13)
        zoom_in.setToolTip(self.tr('放大', 'Zoom in'))
        zoom_in.clicked.connect(self.canvas.zoom_in)
        self.zoom_scale = QSlider(Qt.Orientation.Horizontal)
        self.zoom_scale.setRange(10, 800)
        self.zoom_scale.setFixedWidth(130)
        self.zoom_scale.valueChanged.connect(self._on_zoom_scale)
        self.statusbar.addPermanentWidget(self.zoom_label)
        self.statusbar.addPermanentWidget(zoom_out)
        self.statusbar.addPermanentWidget(self.zoom_scale)
        self.statusbar.addPermanentWidget(zoom_in)

        # callbacks
        self.canvas.on_status = self._on_canvas_status
        self.canvas.on_zoom_changed = self._on_canvas_zoom
        self.canvas.on_selection_changed = lambda sel: self._update_action_sensitivity()
        self.canvas.on_modified = self._on_canvas_modified
        self.canvas.on_pointer = self._on_canvas_pointer
        self.canvas.on_color_picked = self._on_colors_changed

        self.scroll.horizontalScrollBar().valueChanged.connect(self.hruler.update)
        self.scroll.verticalScrollBar().valueChanged.connect(self.vruler.update)
        self.scroll.verticalScrollBar().valueChanged.connect(self._update_rulers)

        # drag hint overlay
        self.drop_hint = QLabel(self.tr('松开以打开图片', 'Drop to open the image'), self.central)
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.drop_hint.setStyleSheet(
            'background: rgba(10, 14, 20, 180); border: 3px dashed #62a9ef;'
            'border-radius: 10px; color: white; font-size: 24px; font-weight: bold;')
        self.drop_hint.setVisible(False)

        self._rebuild_qat()
        self._sync_zoom_controls()
        self._update_theme_menu()

    # ------------------------------------------------------------------
    # Ribbon helpers
    def _ribbon_group(self, title, child, min_width=None):
        group = QFrame()
        group.setObjectName('ribbonGroup')
        box = QVBoxLayout(group)
        box.setContentsMargins(6, 2, 6, 0)
        box.setSpacing(0)
        box.addWidget(child, 1)
        caption = QLabel(title)
        caption.setObjectName('ribbonCaption')
        caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        box.addWidget(caption)
        if min_width:
            group.setMinimumWidth(min_width)
        return group

    def _big_button(self, icon_name, label_text, tooltip, callback, *, toggle=False,
                    menu=None):
        button = QToolButton()
        button.setObjectName('ribbonBig')
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIcon(icon_module.icon(icon_name, 30))
        button.setIconSize(QSize(30, 30))
        button.setText(label_text)
        button.setToolTip(tooltip)
        button.setCheckable(toggle)
        button.setFixedWidth(64)
        button.setMinimumHeight(64)
        button.setProperty('paint_icon', icon_name)
        button.setProperty('paint_icon_size', 30)
        button.clicked.connect(callback)
        if menu is not None:
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        return button

    def _small_button(self, icon_name, label_text, tooltip, callback, *, toggle=False,
                      menu=None):
        button = QToolButton()
        button.setObjectName('ribbonSmall')
        button.setIcon(icon_module.icon(icon_name, 18))
        button.setIconSize(QSize(18, 18))
        if label_text:
            button.setText(label_text)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        else:
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setToolTip(tooltip)
        button.setCheckable(toggle)
        button.setProperty('paint_icon', icon_name)
        button.setProperty('paint_icon_size', 18)
        button.clicked.connect(callback)
        if menu is not None:
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        return button

    def _stacked_button(self, icon_name, label_text, tooltip, callback):
        button = QToolButton()
        button.setObjectName('ribbonSmall')
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIcon(icon_module.icon(icon_name, 17))
        button.setIconSize(QSize(17, 17))
        button.setText(label_text)
        button.setToolTip(tooltip)
        button.setFixedWidth(58)
        button.setProperty('paint_icon', icon_name)
        button.setProperty('paint_icon_size', 17)
        button.clicked.connect(callback)
        return button

    def _tool_button(self, icon_name, tool, tooltip, toggle=True):
        button = QToolButton()
        button.setObjectName('ribbonSmall')
        button.setIcon(icon_module.icon(icon_name, 18))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tooltip)
        button.setCheckable(toggle)
        button.setProperty('paint_icon', icon_name)
        button.setProperty('paint_icon_size', 18)
        button.clicked.connect(lambda checked, t=tool: self._on_tool_clicked(t, checked))
        self.tool_buttons[tool] = button
        return button

    def _build_home_ribbon(self):
        ribbon = QWidget()
        ribbon.setObjectName('ribbon')
        layout = QHBoxLayout(ribbon)
        layout.setContentsMargins(4, 3, 4, 1)
        layout.setSpacing(0)
        self.tool_buttons = {}

        # Clipboard
        clip = QWidget()
        clip_layout = QHBoxLayout(clip)
        clip_layout.setContentsMargins(4, 0, 4, 0)
        clip_layout.setSpacing(4)
        self.paste_btn = self._big_button(
            'paste', self.tr('粘贴', 'Paste'),
            self.tr('粘贴剪贴板的内容。', 'Paste the clipboard contents.'),
            self._paste_clicked, menu=self._make_paste_menu())
        cut_btn = self._big_button('cut', self.tr('剪切', 'Cut'),
                                   self.tr('从画布中剪切选定内容。', 'Cut the selection.'),
                                   self._cut_clicked)
        copy_btn = self._big_button('copy', self.tr('复制', 'Copy'),
                                    self.tr('复制选定内容。', 'Copy the selection.'),
                                    self._copy_clicked)
        for b, key in ((self.paste_btn, 'paste'), (cut_btn, 'cut'), (copy_btn, 'copy')):
            self._attach_qat(b, key)
        clip_layout.addWidget(self.paste_btn)
        clip_layout.addWidget(cut_btn)
        clip_layout.addWidget(copy_btn)
        layout.addWidget(self._ribbon_group(self.tr('剪贴板', 'Clipboard'), clip))

        # Image
        image = QWidget()
        image_layout = QHBoxLayout(image)
        image_layout.setContentsMargins(4, 0, 4, 0)
        image_layout.setSpacing(4)
        sel_col = QVBoxLayout()
        sel_col.setSpacing(0)
        self.select_btn = self._big_button(
            'select_rect', self.tr('选择', 'Select'),
            self.tr('选择图片的一部分。', 'Select part of the picture.'),
            lambda: self._set_tool('select'), toggle=True,
            menu=self._make_select_menu())
        self.tool_buttons['select'] = self.select_btn
        self._attach_qat(self.select_btn, 'select')
        sel_col.addWidget(self.select_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        image_layout.addLayout(sel_col)
        grid = QGridLayout()
        grid.setSpacing(2)
        crop = self._stacked_button('crop', self.tr('裁剪', 'Crop'),
                                    self.tr('裁剪 (Ctrl+Shift+X)', 'Crop (Ctrl+Shift+X)'),
                                    self._crop)
        invert = self._stacked_button('edit_colors', self.tr('反色', 'Invert'),
                                      self.tr('反色 (Ctrl+Shift+I)', 'Invert colors (Ctrl+Shift+I)'),
                                      self._invert_colors)
        resize = self._stacked_button('resize', self.tr('调整大小', 'Resize'),
                                      self.tr('调整大小 (Ctrl+W)', 'Resize (Ctrl+W)'),
                                      self._resize_dialog)
        rotate = self._stacked_button('rotate', self.tr('旋转', 'Rotate'),
                                      self.tr('旋转或翻转', 'Rotate or flip'),
                                      lambda: self._make_rotate_menu().exec(
                                          self.cursor().pos()))
        self._attach_qat(crop, 'crop')
        self._attach_qat(invert, 'invert')
        self._attach_qat(resize, 'resize')
        grid.addWidget(crop, 0, 0)
        grid.addWidget(invert, 1, 0)
        grid.addWidget(resize, 0, 1)
        grid.addWidget(rotate, 1, 1)
        image_layout.addLayout(grid)
        layout.addWidget(self._ribbon_group(self.tr('图像', 'Image'), image))

        # Tools
        tools = QWidget()
        tools_grid = QGridLayout(tools)
        tools_grid.setContentsMargins(4, 0, 4, 0)
        tools_grid.setSpacing(1)
        tool_defs = [
            ('pencil', 'pencil', self.tr('铅笔', 'Pencil')),
            ('fill', 'fill', self.tr('用颜色填充', 'Fill with color')),
            ('text', 'text', self.tr('文本', 'Text')),
            ('eraser', 'eraser', self.tr('橡皮擦', 'Eraser')),
            ('picker', 'picker', self.tr('颜色选取器', 'Color picker')),
            ('magnifier', 'magnifier', self.tr('放大镜', 'Magnifier')),
        ]
        for i, (icon_name, tool, label) in enumerate(tool_defs):
            button = self._tool_button(icon_name, tool, label)
            self._attach_qat(button, tool)
            tools_grid.addWidget(button, i // 3, i % 3)
        layout.addWidget(self._ribbon_group(self.tr('工具', 'Tools'), tools))

        # Brushes
        brush_box = QWidget()
        brush_layout = QHBoxLayout(brush_box)
        brush_layout.setContentsMargins(4, 0, 4, 0)
        brush_layout.setSpacing(2)
        self.brush_btn = self._big_button(
            'brush', self.tr('刷子', 'Brushes'),
            self.tr('用不同种类的刷子绘画。', 'Paint with different brushes.'),
            lambda: self._set_tool('brush'), toggle=True,
            menu=self._make_brush_menu())
        self.tool_buttons['brush'] = self.brush_btn
        self._attach_qat(self.brush_btn, 'brush')
        brush_layout.addWidget(self.brush_btn)
        layout.addWidget(self._ribbon_group(self.tr('刷子', 'Brushes'), brush_box))

        # Shapes gallery
        shapes = QWidget()
        shapes_layout = QHBoxLayout(shapes)
        shapes_layout.setContentsMargins(2, 0, 2, 0)
        shapes_layout.setSpacing(1)
        self.shapes_grid_host = QWidget()
        self.shapes_grid = QGridLayout(self.shapes_grid_host)
        self.shapes_grid.setContentsMargins(0, 0, 0, 0)
        self.shapes_grid.setSpacing(1)
        self.shape_buttons = {}
        self.shape_page = 0
        self._fill_shape_gallery()
        shapes_layout.addWidget(self.shapes_grid_host)
        arrows = QVBoxLayout()
        arrows.setSpacing(0)
        up = QToolButton()
        up.setObjectName('ribbonSmall')
        up.setIcon(icon_module.icon('chevron_up', 14))
        up.setProperty('paint_icon', 'chevron_up')
        up.setProperty('paint_icon_size', 14)
        up.setToolTip(self.tr('上一页形状', 'Previous shapes'))
        up.clicked.connect(lambda: self._shape_page(-1))
        down = QToolButton()
        down.setObjectName('ribbonSmall')
        down.setIcon(icon_module.icon('chevron_down', 14))
        down.setProperty('paint_icon', 'chevron_down')
        down.setProperty('paint_icon_size', 14)
        down.setToolTip(self.tr('下一页形状', 'More shapes'))
        down.clicked.connect(lambda: self._shape_page(1))
        arrows.addWidget(up)
        arrows.addWidget(down)
        shapes_layout.addLayout(arrows)
        layout.addWidget(self._ribbon_group(self.tr('形状', 'Shapes'), shapes))

        # Outline / fill
        styles = QWidget()
        styles_layout = QVBoxLayout(styles)
        styles_layout.setContentsMargins(4, 0, 4, 0)
        styles_layout.setSpacing(4)
        outline_menu = self._make_style_menu('outline', SHAPE_OUTLINE_STYLES)
        fill_menu = self._make_style_menu('fill', SHAPE_FILL_STYLES)
        self.outline_btn = self._small_button('outline', self.tr('轮廓', 'Outline'),
                                              self.tr('轮廓样式', 'Outline style'),
                                              lambda: None, menu=outline_menu)
        self.fill_btn = self._small_button('fill_style', self.tr('填充', 'Fill'),
                                           self.tr('填充样式', 'Fill style'),
                                           lambda: None, menu=fill_menu)
        self._attach_qat(self.outline_btn, 'outline')
        self._attach_qat(self.fill_btn, 'fill-style')
        styles_layout.addWidget(self.outline_btn)
        styles_layout.addWidget(self.fill_btn)
        layout.addWidget(self._ribbon_group('', styles, min_width=82))

        # Size
        size_box = QWidget()
        size_layout = QVBoxLayout(size_box)
        size_layout.setContentsMargins(4, 0, 4, 0)
        size_layout.setSpacing(0)
        self.size_btn = QToolButton()
        self.size_btn.setObjectName('ribbonBig')
        self.size_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.size_btn.setIcon(icon_module.icon('outline', 30))
        self.size_btn.setText(self.tr('粗细', 'Size'))
        self.size_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.size_btn.setMenu(self._make_size_menu())
        self.size_btn.setProperty('paint_icon', 'outline')
        self.size_btn.setProperty('paint_icon_size', 30)
        self._attach_qat(self.size_btn, 'size')
        size_layout.addWidget(self.size_btn)
        layout.addWidget(self._ribbon_group('', size_box, min_width=60))

        # Colors
        colors = QWidget()
        colors_layout = QHBoxLayout(colors)
        colors_layout.setContentsMargins(4, 0, 4, 0)
        colors_layout.setSpacing(5)
        chips = QVBoxLayout()
        chips.setSpacing(1)
        row1 = QHBoxLayout()
        row1.setSpacing(2)
        self.color1_btn = QToolButton()
        self.color1_btn.setFixedSize(30, 26)
        self.color1_btn.setToolTip(self.tr('颜色 1 (前景色)', 'Color 1 (foreground)'))
        self.color1_btn.clicked.connect(lambda: self._edit_color(1))
        row1.addWidget(self.color1_btn)
        row1.addWidget(QLabel(self.tr('颜色 1', 'Color 1')))
        row2 = QHBoxLayout()
        row2.setSpacing(2)
        self.color2_btn = QToolButton()
        self.color2_btn.setFixedSize(30, 26)
        self.color2_btn.setToolTip(self.tr('颜色 2 (背景色)', 'Color 2 (background)'))
        self.color2_btn.clicked.connect(lambda: self._edit_color(2))
        row2.addWidget(self.color2_btn)
        row2.addWidget(QLabel(self.tr('颜色 2', 'Color 2')))
        chips.addLayout(row1)
        chips.addLayout(row2)
        colors_layout.addLayout(chips)
        palette_host = QWidget()
        self.palette_grid = QGridLayout(palette_host)
        self.palette_grid.setContentsMargins(0, 0, 0, 0)
        self.palette_grid.setSpacing(1)
        colors_layout.addWidget(palette_host)
        edit_colors = self._big_button(
            'edit_colors', self.tr('编辑\n颜色', 'Edit\ncolors'),
            self.tr('编辑颜色', 'Edit colors'), lambda: self._edit_color(1))
        colors_layout.addWidget(edit_colors)
        self._attach_qat(self.color1_btn, 'colors')
        self._attach_qat(self.color2_btn, 'colors')
        layout.addWidget(self._ribbon_group(self.tr('颜色', 'Colors'), colors))
        self._build_palette()
        layout.addStretch(1)
        return ribbon

    def _build_view_ribbon(self):
        ribbon = QWidget()
        ribbon.setObjectName('ribbon')
        layout = QHBoxLayout(ribbon)
        layout.setContentsMargins(4, 3, 4, 1)
        layout.setSpacing(0)

        zoom = QWidget()
        zoom_layout = QHBoxLayout(zoom)
        zoom_layout.setContentsMargins(4, 0, 4, 0)
        zoom_layout.setSpacing(4)
        zin = self._big_button('zoomin', self.tr('放大', 'Zoom in'),
                               self.tr('放大当前图片。 (Ctrl+PgUp)', 'Zoom in (Ctrl+PgUp)'),
                               self.canvas.zoom_in)
        zout = self._big_button('zoomout', self.tr('缩小', 'Zoom out'),
                                self.tr('缩小当前图片。 (Ctrl+PgDn)', 'Zoom out (Ctrl+PgDn)'),
                                self.canvas.zoom_out)
        z100 = self._big_button('magnifier', '100%', self.tr('缩放到 100%', 'Zoom to 100%'),
                                lambda: self.canvas.set_zoom(1.0))
        for b, key in ((zin, 'zoom-in'), (zout, 'zoom-out'), (z100, 'zoom-100')):
            self._attach_qat(b, key)
            zoom_layout.addWidget(b)
        layout.addWidget(self._ribbon_group(self.tr('缩放', 'Zoom'), zoom))

        show = QWidget()
        show_layout = QVBoxLayout(show)
        show_layout.setContentsMargins(10, 2, 10, 2)
        show_layout.setSpacing(4)
        self.cb_ruler = QCheckBox(self.tr('标尺 (Ctrl+R)', 'Rulers (Ctrl+R)'))
        self.cb_grid = QCheckBox(self.tr('网格线 (Ctrl+G)', 'Gridlines (Ctrl+G)'))
        self.cb_status = QCheckBox(self.tr('状态栏', 'Status bar'))
        self.cb_ruler.toggled.connect(self._toggle_rulers)
        self.cb_grid.toggled.connect(self._toggle_grid)
        self.cb_status.setChecked(True)
        self.cb_status.toggled.connect(self._toggle_status)
        for widget, key in ((self.cb_ruler, 'ruler'), (self.cb_grid, 'grid'),
                            (self.cb_status, 'statusbar')):
            self._attach_qat(widget, key)
            show_layout.addWidget(widget)
        layout.addWidget(self._ribbon_group(self.tr('显示或隐藏', 'Show or hide'), show))

        display = QWidget()
        display_layout = QHBoxLayout(display)
        display_layout.setContentsMargins(4, 0, 4, 0)
        display_layout.setSpacing(4)
        fs_btn = self._big_button('fullscreen', self.tr('全屏', 'Full screen'),
                                  self.tr('全屏查看图片。 (F11)', 'View full screen (F11)'),
                                  self._toggle_fullscreen)
        self.thumb_btn = self._big_button('thumbnail', self.tr('缩略图', 'Thumbnail'),
                                          self.tr('显示或隐藏缩略图。', 'Show or hide the thumbnail'),
                                          self._toggle_thumbnail)
        self._attach_qat(fs_btn, 'fullscreen')
        self._attach_qat(self.thumb_btn, 'thumbnail')
        display_layout.addWidget(fs_btn)
        display_layout.addWidget(self.thumb_btn)
        layout.addWidget(self._ribbon_group(self.tr('显示', 'Display'), display))

        theme = QWidget()
        theme_layout = QVBoxLayout(theme)
        theme_layout.setContentsMargins(10, 2, 10, 2)
        theme_layout.setSpacing(2)
        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName('ribbonSmall')
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.theme_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.theme_btn.setText(self.tr('主题：跟随系统', 'Theme: System'))
        self.theme_btn.setMenu(self._make_theme_menu())
        self._attach_qat(self.theme_btn, 'theme')
        theme_layout.addWidget(self.theme_btn)
        layout.addWidget(self._ribbon_group(self.tr('主题', 'Theme'), theme))
        layout.addStretch(1)
        return ribbon

    def _build_text_bar(self):
        bar = QWidget()
        bar.setObjectName('textBar')
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(8)
        title = QLabel(self.tr('文本工具', 'Text tools'))
        title.setStyleSheet('font-weight: bold;')
        layout.addWidget(title)
        layout.addWidget(QLabel(self.tr('字体:', 'Font:')))
        self.font_combo = QFontComboBox()
        self.font_combo.setMaximumWidth(220)
        self.font_combo.currentFontChanged.connect(self._font_changed)
        layout.addWidget(self.font_combo)
        layout.addWidget(QLabel(self.tr('大小:', 'Size:')))
        self.font_size = QSpinBox()
        self.font_size.setRange(4, 200)
        self.font_size.setValue(12)
        self.font_size.setFixedWidth(70)
        self.font_size.valueChanged.connect(self._font_size_changed)
        layout.addWidget(self.font_size)
        self.btn_bold = QToolButton()
        self.btn_bold.setText('B')
        self.btn_bold.setCheckable(True)
        self.btn_bold.setToolTip(self.tr('加粗', 'Bold'))
        self.btn_bold.toggled.connect(lambda v: self._set_text_style('bold', v))
        self.btn_italic = QToolButton()
        self.btn_italic.setText('I')
        self.btn_italic.setCheckable(True)
        self.btn_italic.setToolTip(self.tr('斜体', 'Italic'))
        self.btn_italic.toggled.connect(lambda v: self._set_text_style('italic', v))
        self.btn_under = QToolButton()
        self.btn_under.setText('U')
        self.btn_under.setCheckable(True)
        self.btn_under.setToolTip(self.tr('下划线', 'Underline'))
        self.btn_under.toggled.connect(lambda v: self._set_text_style('underline', v))
        for b in (self.btn_bold, self.btn_italic, self.btn_under):
            b.setObjectName('ribbonSmall')
            b.setAutoRaise(True)
            b.setFixedSize(26, 24)
            layout.addWidget(b)
        layout.addWidget(QLabel(self.tr('背景:', 'Background:')))
        self.btn_opaque = QToolButton()
        self.btn_opaque.setText(self.tr('不透明', 'Opaque'))
        self.btn_opaque.setObjectName('ribbonSmall')
        self.btn_opaque.setAutoRaise(True)
        self.btn_opaque.setCheckable(True)
        self.btn_opaque.toggled.connect(lambda v: self._set_text_opaque(v))
        self.btn_transparent = QToolButton()
        self.btn_transparent.setObjectName('ribbonSmall')
        self.btn_transparent.setAutoRaise(True)
        self.btn_transparent.setText(self.tr('透明', 'Transparent'))
        self.btn_transparent.setCheckable(True)
        self.btn_transparent.setChecked(True)
        self.btn_transparent.toggled.connect(
            lambda v: self._set_text_opaque(False) if v else None)
        layout.addWidget(self.btn_opaque)
        layout.addWidget(self.btn_transparent)
        layout.addStretch(1)
        self.canvas.text_family = self.font_combo.currentFont().family()
        return bar

    # ------------------------------------------------------------------
    # Menus
    def _make_paste_menu(self):
        menu = QMenu(self)
        menu.addAction(self.tr('粘贴 (Ctrl+V)', 'Paste (Ctrl+V)'), self._paste_clicked)
        menu.addAction(self.tr('粘贴来源...', 'Paste from...'), self._paste_from_file)
        return menu

    def _make_select_menu(self):
        menu = QMenu(self)
        menu.addAction(self.tr('矩形选择', 'Rectangular selection'),
                       lambda: self._set_tool('select'))
        menu.addAction(self.tr('自由图形选择', 'Free-form selection'),
                       lambda: self._set_tool('free_select'))
        menu.addSeparator()
        menu.addAction(self.tr('全选 (Ctrl+A)', 'Select all (Ctrl+A)'), self._select_all)
        menu.addAction(self.tr('反向选择', 'Invert selection'), self._invert_selection)
        menu.addAction(self.tr('删除选定内容', 'Delete selection'), self._delete)
        menu.addAction(self.tr('裁剪 (Ctrl+Shift+X)', 'Crop (Ctrl+Shift+X)'), self._crop)
        menu.addSeparator()
        self.trans_action = menu.addAction(self.tr('透明选择', 'Transparent selection'))
        self.trans_action.setCheckable(True)
        self.trans_action.toggled.connect(lambda v: self._set_opaque_selection(not v))
        return menu

    def _make_rotate_menu(self):
        menu = QMenu(self)
        for text, mode in [(self.tr('向右旋转 90 度', 'Rotate right 90°'), 'right'),
                           (self.tr('向左旋转 90 度', 'Rotate left 90°'), 'left'),
                           (self.tr('旋转 180 度', 'Rotate 180°'), '180'),
                           (self.tr('垂直翻转', 'Flip vertical'), 'flip_v'),
                           (self.tr('水平翻转', 'Flip horizontal'), 'flip_h')]:
            menu.addAction(text, lambda _=False, m=mode: self._rotate(m))
        return menu

    def _make_brush_menu(self):
        menu = QMenu(self)
        for brush in BRUSH_ORDER:
            menu.addAction(icon_module.brush_icon(brush, 36),
                           BRUSH_LABELS[brush][0 if self.lang_zh else 1],
                           lambda _=False, b=brush: self._set_brush(b))
        return menu

    def _make_style_menu(self, kind, styles):
        menu = QMenu(self)
        for key, (zh, en) in styles.items():
            menu.addAction(zh if self.lang_zh else en,
                           lambda _=False, k=key: self._set_style(kind, k))
        return menu

    def _make_size_menu(self):
        menu = QMenu(self)
        for width in LINE_WIDTHS:
            menu.addAction(f'{width} px',
                           lambda _=False, w=width: self._set_line_width(w))
        return menu

    def _make_theme_menu(self, register=True):
        menu = QMenu(self)
        group = QActionGroup(menu)
        group.setExclusive(True)
        actions = {}
        for mode, text in (('auto', self.tr('跟随系统', 'Follow system')),
                           ('light', self.tr('浅色', 'Light')),
                           ('dark', self.tr('深色', 'Dark'))):
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(mode == self.theme_mode)
            action.triggered.connect(lambda _=False, m=mode: self._set_theme_mode(m))
            group.addAction(action)
            actions[mode] = action
        if register:
            self.theme_actions = actions
        return menu

    def _make_qat_menu(self, kind):
        if kind == 'shapes':
            menu = QMenu(self)
            for shape in SHAPE_ORDER:
                text = SHAPE_LABELS_ZH.get(shape, shape) if self.lang_zh else SHAPE_LABELS_EN.get(shape, shape)
                menu.addAction(icon_module.shape_icon(shape, 24), text,
                               lambda _=False, s=shape: self._choose_shape(s))
            return menu
        if kind == 'rotate':
            return self._make_rotate_menu()
        if kind == 'outline':
            return self._make_style_menu('outline', SHAPE_OUTLINE_STYLES)
        if kind == 'fill':
            return self._make_style_menu('fill', SHAPE_FILL_STYLES)
        if kind == 'size':
            return self._make_size_menu()
        if kind == 'colors':
            menu = QMenu(self)
            for color in DEFAULT_PALETTE:
                swatch = QPixmap(16, 16)
                swatch.fill(QColor(color))
                menu.addAction(QIcon(swatch), color,
                               lambda _=False, c=color: self._palette_left(c))
            menu.addSeparator()
            menu.addAction(self.tr('编辑颜色...', 'Edit colors...'),
                           lambda: self._edit_color(1))
            return menu
        if kind == 'theme':
            return self._make_theme_menu(register=False)
        return QMenu(self)

    def _build_file_menu(self):
        menu = QMenu(self)
        # Reuse the window-level actions so their shortcuts are not registered
        # twice (duplicate shortcuts become ambiguous and silently stop working).
        menu.addAction(self.actions['new'])
        menu.addAction(self.actions['open'])
        menu.addSeparator()
        menu.addAction(self.actions['save'])
        menu.addAction(self.actions['save-as'])
        menu.addAction(self.actions['print'])
        menu.addAction(self.tr('打印预览', 'Print preview'), self._print_preview)
        menu.addAction(self.tr('页面设置', 'Page setup'), self._page_setup)
        menu.addSeparator()
        menu.addAction(self.actions['properties'])
        menu.addAction(self.tr('从扫描仪或照相机...', 'From scanner or camera...'),
                       self._scanner_unavailable)
        menu.addAction(self.tr('在电子邮件中发送', 'Send in e-mail'), self._send_email)
        menu.addAction(self.tr('设置为桌面背景', 'Set as desktop background'), self._set_wallpaper)
        self.recent_menu = menu.addMenu(self.tr('最近查看的图片', 'Recently viewed pictures'))
        menu.addSeparator()
        menu.addAction(self.tr('关于 paim', 'About paim'), self._about)
        menu.addAction(self.actions['exit'])
        self.file_tab.setMenu(menu)
        self._refresh_recent()

    # ------------------------------------------------------------------
    # Quick access toolbar
    def _init_qat_registry(self):
        def reg(key, zh, en, icon_name, callback, menu=None):
            self.qat_registry[key] = {'zh': zh, 'en': en, 'icon': icon_name,
                                      'callback': callback, 'menu': menu}
        reg('save', '保存', 'Save', 'save', self._save_clicked)
        reg('undo', '撤消', 'Undo', 'undo', self._undo)
        reg('redo', '重做', 'Redo', 'redo', self._redo)
        reg('new', '新建', 'New', 'new', self._new_clicked)
        reg('open', '打开', 'Open', 'open', self._open_clicked)
        reg('print', '打印', 'Print', 'print', lambda: self._print())
        reg('cut', '剪切', 'Cut', 'cut', self._cut_clicked)
        reg('copy', '复制', 'Copy', 'copy', self._copy_clicked)
        reg('paste', '粘贴', 'Paste', 'paste', self._paste_clicked)
        reg('select', '选择', 'Select', 'select_rect', lambda: self._set_tool('select'))
        reg('crop', '裁剪', 'Crop', 'crop', self._crop)
        reg('resize', '调整大小', 'Resize', 'resize', self._resize_dialog)
        reg('invert', '反色', 'Invert colors', 'edit_colors', self._invert_colors)
        reg('pencil', '铅笔', 'Pencil', 'pencil', lambda: self._set_tool('pencil'))
        reg('fill', '用颜色填充', 'Fill with color', 'fill', lambda: self._set_tool('fill'))
        reg('text', '文本', 'Text', 'text', lambda: self._set_tool('text'))
        reg('eraser', '橡皮擦', 'Eraser', 'eraser', lambda: self._set_tool('eraser'))
        reg('picker', '颜色选取器', 'Color picker', 'picker', lambda: self._set_tool('picker'))
        reg('magnifier', '放大镜', 'Magnifier', 'magnifier', lambda: self._set_tool('magnifier'))
        reg('brush', '刷子', 'Brushes', 'brush', lambda: self._set_tool('brush'))
        reg('zoom-in', '放大', 'Zoom in', 'zoomin', lambda: self.canvas.zoom_in())
        reg('zoom-out', '缩小', 'Zoom out', 'zoomout', lambda: self.canvas.zoom_out())
        reg('zoom-100', '100%', '100%', 'magnifier', lambda: self.canvas.set_zoom(1.0))
        reg('fullscreen', '全屏', 'Full screen', 'fullscreen', self._toggle_fullscreen)
        reg('rotate', '旋转', 'Rotate', 'rotate', None, menu='rotate')
        reg('shapes', '形状', 'Shapes', 'shapes', None, menu='shapes')
        reg('outline', '轮廓', 'Outline', 'outline', None, menu='outline')
        reg('fill-style', '填充', 'Fill', 'fill_style', None, menu='fill')
        reg('size', '粗细', 'Size', 'outline', None, menu='size')
        reg('colors', '颜色', 'Colors', 'edit_colors', None, menu='colors')
        reg('ruler', '标尺', 'Rulers', 'ruler',
            lambda: self.cb_ruler.setChecked(not self.cb_ruler.isChecked()))
        reg('grid', '网格线', 'Gridlines', 'grid',
            lambda: self.cb_grid.setChecked(not self.cb_grid.isChecked()))
        reg('statusbar', '状态栏', 'Status bar', 'statusbar',
            lambda: self.cb_status.setChecked(not self.cb_status.isChecked()))
        reg('thumbnail', '缩略图', 'Thumbnail', 'thumbnail', self._toggle_thumbnail)
        reg('theme', '主题', 'Theme', 'theme', None, menu='theme')

    def _qat_label(self, spec):
        return spec['zh'] if self.lang_zh else spec['en']

    def _rebuild_qat(self):
        while self.qat_layout.count():
            item = self.qat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.qat_buttons = {}
        for key in list(self.qat_pinned):
            spec = self.qat_registry.get(key)
            if spec is None:
                continue
            button = QToolButton()
            button.setObjectName('quick')
            button.setIcon(icon_module.icon(spec['icon'], 18))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(self._qat_label(spec))
            button.setProperty('paint_icon', spec['icon'])
            button.setProperty('paint_icon_size', 18)
            if spec.get('menu'):
                button.setMenu(self._make_qat_menu(spec['menu']))
                button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            else:
                button.clicked.connect(spec['callback'])
            self._attach_qat(button, key)
            self.qat_layout.addWidget(button)
            self.qat_buttons[key] = button
        customize = QToolButton()
        customize.setObjectName('quick')
        customize.setIcon(icon_module.icon('dropdown', 16))
        customize.setIconSize(QSize(16, 16))
        customize.setProperty('paint_icon', 'dropdown')
        customize.setProperty('paint_icon_size', 16)
        customize.setToolTip(self.tr('自定义快速访问工具栏', 'Customize Quick Access Toolbar'))
        customize.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        customize.setMenu(self._build_qat_customize_menu())
        self.qat_layout.addWidget(customize)
        self.qat_layout.addStretch(1)
        self._update_quick_access()

    def _build_qat_customize_menu(self):
        menu = QMenu(self)
        title = menu.addAction(self.tr('快速访问工具栏', 'Quick Access Toolbar'))
        title.setEnabled(False)
        menu.addSeparator()
        for key, spec in self.qat_registry.items():
            action = menu.addAction(self._qat_label(spec))
            action.setCheckable(True)
            action.setChecked(key in self.qat_pinned)
            action.toggled.connect(lambda checked, k=key: self._toggle_qat_pin(k, checked))
        return menu

    def _attach_qat(self, widget, key):
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda pos, w=widget, k=key: self._show_qat_context(w, k, pos))

    def _show_qat_context(self, widget, key, pos):
        spec = self.qat_registry.get(key)
        if spec is None:
            return
        menu = QMenu(self)
        title = menu.addAction(self._qat_label(spec))
        title.setEnabled(False)
        menu.addSeparator()
        pinned = key in self.qat_pinned
        menu.addAction(
            self.tr('从快速访问工具栏删除', 'Remove from Quick Access Toolbar') if pinned
            else self.tr('添加到快速访问工具栏', 'Add to Quick Access Toolbar'),
            lambda: self._toggle_qat_pin(key, not pinned))
        menu.exec(widget.mapToGlobal(pos))

    def _toggle_qat_pin(self, key, pin):
        if pin:
            if key not in self.qat_pinned:
                self.qat_pinned.append(key)
        else:
            if key in self.qat_pinned:
                self.qat_pinned.remove(key)
        self._save_preferences()
        QTimer.singleShot(0, self._rebuild_qat)

    # ------------------------------------------------------------------
    # Palette / color UI
    def _build_palette(self):
        while self.palette_grid.count():
            item = self.palette_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for i, color in enumerate(DEFAULT_PALETTE[:40]):
            swatch = ColorSwatch(color)
            swatch.set_handlers(self._palette_left, self._palette_right)
            self.palette_grid.addWidget(swatch, i // 10, i % 10)
        self._sync_palette()

    def _sync_palette(self):
        if not hasattr(self, 'color1_btn') or not hasattr(self, 'canvas'):
            return
        for button, rgb in ((self.color1_btn, self.canvas.color1),
                            (self.color2_btn, self.canvas.color2)):
            color = QColor(*rgb).name()
            button.setStyleSheet(
                f'QToolButton {{ background-color: {color}; border: 1px solid #555555; }}')

    def _palette_left(self, color):
        self.canvas.set_colors(color1=hex_to_rgb(color))
        self._sync_palette()

    def _palette_right(self, color):
        self.canvas.set_colors(color2=hex_to_rgb(color))
        self._sync_palette()

    def _on_colors_changed(self, c1, c2):
        self._sync_palette()

    def _edit_color(self, which):
        initial = self.canvas.color1 if which == 1 else self.canvas.color2

        def apply(rgb):
            if which == 1:
                self.canvas.set_colors(color1=rgb)
            else:
                self.canvas.set_colors(color2=rgb)
            self._sync_palette()

        ColorDialog(self, initial, apply).present()

    # ------------------------------------------------------------------
    # Shapes / tool state
    def _fill_shape_gallery(self):
        while self.shapes_grid.count():
            item = self.shapes_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        page_size = 15
        items = SHAPE_ORDER[:page_size] if self.shape_page == 0 else SHAPE_ORDER[page_size:]
        for i, shape in enumerate(items):
            button = QToolButton()
            button.setObjectName('ribbonSmall')
            button.setIcon(icon_module.shape_icon(shape, 24))
            button.setIconSize(QSize(24, 24))
            label = SHAPE_LABELS_ZH.get(shape, shape) if self.lang_zh else SHAPE_LABELS_EN.get(shape, shape)
            button.setToolTip(label)
            button.setCheckable(True)
            button.setProperty('paint_shape', shape)
            button.clicked.connect(lambda checked, s=shape: self._choose_shape(s))
            self._attach_qat(button, 'shapes')
            self.shapes_grid.addWidget(button, i // 5, i % 5)
            self.shape_buttons[shape] = button
        self._update_shape_active()

    def _shape_page(self, delta):
        self.shape_page = (self.shape_page + delta) % 2
        self._fill_shape_gallery()

    def _choose_shape(self, shape):
        self._commit_current_text()
        self.canvas.set_tool(shape)
        self._set_tool_button_state(shape)
        self._update_shape_active()

    def _update_shape_active(self):
        if not hasattr(self, 'canvas'):
            return
        for shape, button in getattr(self, 'shape_buttons', {}).items():
            button.blockSignals(True)
            button.setChecked(shape == self.canvas.tool)
            button.blockSignals(False)

    def _set_opaque_selection(self, opaque):
        self.canvas.opaque_selection = bool(opaque)
        if hasattr(self, 'trans_action'):
            self.trans_action.blockSignals(True)
            self.trans_action.setChecked(not opaque)
            self.trans_action.blockSignals(False)
        self.canvas.update()

    def _set_brush(self, brush):
        self.canvas.brush = brush
        self._set_tool('brush')
        self._set_tool_button_state('brush')

    def _set_line_width(self, width):
        self.canvas.line_width = width
        self.size_btn.setToolTip(f'{self.tr("粗细", "Size")}: {width}px')
        self.canvas.update()
        self._update_status_labels()

    def _set_style(self, kind, key):
        if kind == 'outline':
            self.canvas.outline_style = key
        else:
            self.canvas.fill_style = key
        self.canvas.update()

    def _on_tool_clicked(self, tool, checked):
        if not checked:
            # Tools are modal: clicking the active tool must not deactivate it.
            if self.canvas.tool == tool:
                button = self.tool_buttons.get(tool)
                if button is not None:
                    button.blockSignals(True)
                    button.setChecked(True)
                    button.blockSignals(False)
            return
        self._set_tool(tool)

    def _set_tool(self, tool):
        self._commit_current_text()
        self.canvas.set_tool(tool)
        self._set_tool_button_state(tool)
        self.textbar.setVisible(tool == 'text')
        self._update_action_sensitivity()

    def _set_tool_button_state(self, tool):
        for name, button in getattr(self, 'tool_buttons', {}).items():
            button.blockSignals(True)
            button.setChecked(name == tool)
            button.blockSignals(False)
        self._update_shape_active()
        if hasattr(self, 'textbar'):
            self.textbar.setVisible(tool == 'text')

    def _update_quick_access(self):
        if not hasattr(self, 'qat_buttons'):
            return
        for key, button in self.qat_buttons.items():
            if key == 'undo':
                button.setEnabled(self.doc.can_undo())
            elif key == 'redo':
                button.setEnabled(self.doc.can_redo())
            elif key in ('cut', 'copy', 'crop'):
                button.setEnabled(self.doc.selection is not None)
            else:
                button.setEnabled(True)

    # ------------------------------------------------------------------
    # Status / title
    def _on_canvas_status(self, pos, sel, width, height, zoom):
        self._update_status_labels(pos, sel, width, height, zoom)

    def _update_status_labels(self, pos=None, sel=None, width=None, height=None,
                              zoom=None):
        if width is None:
            width, height = self.doc.width, self.doc.height
        if zoom is None:
            zoom = self.canvas.zoom
        self.pos_label.setText(f'{pos[0]}, {pos[1]} px' if pos else '')
        self.sel_label.setText(f'{sel[2]} × {sel[3]}' if sel else '')
        self.size_label.setText(f'{width} × {height} px')
        self.zoom_label.setText(f'{int(round(zoom * 100))}%')
        self._sync_zoom_controls(zoom)
        if hasattr(self, 'thumb_area'):
            self.thumb_area.update()

    def _sync_zoom_controls(self, zoom=None):
        if not hasattr(self, 'zoom_scale'):
            return
        if zoom is None:
            zoom = self.canvas.zoom
        self.zoom_scale.blockSignals(True)
        self.zoom_scale.setValue(int(round(zoom * 100)))
        self.zoom_scale.blockSignals(False)
        self.zoom_label.setText(f'{int(round(zoom * 100))}%')

    def _on_zoom_scale(self, value):
        zoom = value / 100.0
        if abs(zoom - self.canvas.zoom) > 1e-4:
            self.canvas.set_zoom(zoom)
        self.zoom_label.setText(f'{int(round(zoom * 100))}%')

    def _on_canvas_zoom(self, zoom):
        self.zoom = zoom
        self._sync_zoom_controls(zoom)
        self._update_status_labels()
        self._update_title()
        self._update_rulers()

    def _on_canvas_pointer(self, point):
        pass

    def _on_canvas_modified(self):
        self._update_title()
        self._update_action_sensitivity()
        self._update_quick_access()
        if hasattr(self, 'thumb_area'):
            self.thumb_area.update()

    def _update_title(self):
        name = os.path.basename(self.doc.filename) if self.doc.filename else self.tr('无标题', 'Untitled')
        mark = ' *' if self.doc.dirty else ''
        self.setWindowTitle(f'{name}{mark} - paim')

    # ------------------------------------------------------------------
    # Actions and shortcuts
    def _build_actions(self):
        def add(name, text, slot, shortcut=None):
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
                action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.triggered.connect(lambda _=False, s=slot: s())
            self.addAction(action)
            self.actions[name] = action
            return action
        add('new', self.tr('新建', 'New'), self._new_clicked, 'Ctrl+N')
        add('open', self.tr('打开', 'Open'), self._open_clicked, 'Ctrl+O')
        add('save', self.tr('保存', 'Save'), self._save_clicked, 'Ctrl+S')
        add('save-as', self.tr('另存为', 'Save as'), self._save_as_clicked, 'F12')
        add('print', self.tr('打印', 'Print'), self._print, 'Ctrl+P')
        add('undo', self.tr('撤消', 'Undo'), self._undo, 'Ctrl+Z')
        add('redo', self.tr('重做', 'Redo'), self._redo, 'Ctrl+Y')
        add('cut', self.tr('剪切', 'Cut'), self._cut_clicked, 'Ctrl+X')
        add('copy', self.tr('复制', 'Copy'), self._copy_clicked, 'Ctrl+C')
        add('paste', self.tr('粘贴', 'Paste'), self._paste_clicked, 'Ctrl+V')
        add('select-all', self.tr('全选', 'Select all'), self._select_all, 'Ctrl+A')
        add('crop', self.tr('裁剪', 'Crop'), self._crop, 'Ctrl+Shift+X')
        add('resize', self.tr('调整大小', 'Resize'), self._resize_dialog, 'Ctrl+W')
        add('properties', self.tr('属性', 'Properties'), self._properties, 'Ctrl+E')
        add('invert-colors', self.tr('反色', 'Invert colors'), self._invert_colors,
            'Ctrl+Shift+I')
        add('clear-image', self.tr('清除图像', 'Clear image'), self._clear_image,
            'Ctrl+Shift+N')
        add('zoom-in', self.tr('放大', 'Zoom in'), self.canvas.zoom_in, 'Ctrl+PgUp')
        add('zoom-out', self.tr('缩小', 'Zoom out'), self.canvas.zoom_out, 'Ctrl+PgDown')
        add('fullscreen', self.tr('全屏', 'Full screen'), self._toggle_fullscreen, 'F11')
        add('help', self.tr('帮助', 'Help'), self._help, 'F1')
        add('grid', self.tr('网格线', 'Gridlines'),
            lambda: self.cb_grid.setChecked(not self.cb_grid.isChecked()), 'Ctrl+G')
        add('ruler', self.tr('标尺', 'Rulers'),
            lambda: self.cb_ruler.setChecked(not self.cb_ruler.isChecked()), 'Ctrl+R')
        add('bold', self.tr('加粗', 'Bold'),
            lambda: self.btn_bold.setChecked(not self.btn_bold.isChecked()), 'Ctrl+B')
        add('italic', self.tr('斜体', 'Italic'),
            lambda: self.btn_italic.setChecked(not self.btn_italic.isChecked()), 'Ctrl+I')
        add('font-underline', self.tr('下划线', 'Underline'),
            lambda: self.btn_under.setChecked(not self.btn_under.isChecked()), 'Ctrl+U')
        add('delete', self.tr('删除', 'Delete'), self._delete)
        add('invert-selection', self.tr('反向选择', 'Invert selection'),
            self._invert_selection)
        add('rotate-right', self.tr('向右旋转', 'Rotate right'),
            lambda: self._rotate('right'))
        add('rotate-left', self.tr('向左旋转', 'Rotate left'),
            lambda: self._rotate('left'))
        add('exit', self.tr('退出', 'Exit'), self.close)

    # ------------------------------------------------------------------
    # Document lifecycle and file dialogs
    def _confirm_save(self, callback):
        self._commit_current_text()
        if not self.doc.dirty:
            callback()
            return
        name = os.path.basename(self.doc.filename) if self.doc.filename else self.tr('无标题', 'Untitled')
        box = QMessageBox(self)
        box.setWindowTitle('paim')
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(self.tr(f'你想将更改保存到 {name} 吗?', 'Do you want to save changes?'))
        save = box.addButton(self.tr('保存', 'Save'), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(self.tr('不保存', "Don't save"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(self.tr('取消', 'Cancel'), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            self._save(on_done=callback)
        elif clicked is discard:
            callback()

    def _new_clicked(self):
        def go():
            width, height = self.doc.width, self.doc.height
            self.doc = Document(width, height)
            self._bind_document()
        self._confirm_save(go)

    def _bind_document(self):
        self.canvas.reset_document(self.doc)
        self.canvas.doc = self.doc
        self._update_title()
        self._update_status_labels()
        self._update_action_sensitivity()
        self._update_quick_access()
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def _open_clicked(self):
        def choose():
            filters = self.tr(
                '所有图片文件 (*.png *.jpg *.jpeg *.bmp *.dib *.gif *.tif *.tiff *.webp);;'
                '所有文件 (*)',
                'All picture files (*.png *.jpg *.jpeg *.bmp *.dib *.gif *.tif *.tiff *.webp);;'
                'All files (*)')
            path, _ = QFileDialog.getOpenFileName(self, self.tr('打开', 'Open'), '', filters)
            if path:
                self.load_path(path)
        self._confirm_save(choose)

    def load_path(self, path):
        try:
            doc = Document.open(path)
        except Exception as exc:
            MessageDialog(self, self.tr('paim 无法打开该文件。', 'paim cannot open this file.'),
                          str(exc)).present()
            return
        self.doc = doc
        self._bind_document()
        self._add_recent(path)
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def _save_clicked(self):
        self._save()

    def _save(self, on_done=None):
        self._commit_current_text()
        self.canvas.commit_floating()
        if self.doc.filename:
            self._save_to_path(self.doc.filename, on_done=on_done)
        else:
            self._save_as_clicked(on_done=on_done)

    def _save_as_clicked(self, checked=False, on_done=None):
        self._commit_current_text()
        self.canvas.commit_floating()
        self._save_after = on_done
        filters = self.tr(
            'PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;BMP 图片 (*.bmp *.dib);;'
            'GIF 图片 (*.gif);;WebP 图片 (*.webp);;TIFF 图片 (*.tif *.tiff);;'
            '所有图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff)',
            'PNG picture (*.png);;JPEG picture (*.jpg *.jpeg);;BMP picture (*.bmp *.dib);;'
            'GIF picture (*.gif);;WebP picture (*.webp);;TIFF picture (*.tif *.tiff);;'
            'All picture files (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff)')
        base = os.path.basename(self.doc.filename) if self.doc.filename else (self.tr('无标题', 'Untitled') + '.png')
        path, selected = QFileDialog.getSaveFileName(self, self.tr('另存为', 'Save As'),
                                                     base, filters)
        if not path:
            return
        root, ext = os.path.splitext(path)
        if not ext:
            ext = '.png'
            path += ext
        ext = ext.lower().lstrip('.')
        if ext in ('bmp', 'dib'):
            def done(fmt, bits):
                self._save_to_path(path, fmt=fmt, bits=bits)
            SaveOptionsDialog(self, ext, done).present()
        else:
            self._save_to_path(path, fmt=ext)

    def _save_to_path(self, path, fmt=None, bits=24, on_done=None):
        try:
            self.doc.save(path, fmt=fmt, bits=bits)
            self.doc.dirty = False
        except Exception as exc:
            MessageDialog(self, self.tr('paim 不能存储该文件。', 'paim cannot save this file.'),
                          str(exc)).present()
            return
        try:
            self._add_recent(path)
        except Exception:
            pass
        self._update_title()
        self._update_action_sensitivity()
        self._update_quick_access()
        callback = on_done if on_done is not None else self._save_after
        self._save_after = None
        if callback:
            callback()

    def _recent_path(self):
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
        return base / 'mspaint-linux' / 'recent.json'

    def _add_recent(self, path):
        path = os.path.abspath(path)
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]
        self._save_recent()
        self._refresh_recent()

    def _load_recent(self):
        try:
            path = self._recent_path()
            if path.exists():
                self.recent_files = json.loads(path.read_text()) or []
        except Exception:
            self.recent_files = []

    def _save_recent(self):
        try:
            path = self._recent_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.recent_files))
        except Exception:
            pass

    def _refresh_recent(self):
        if not hasattr(self, 'recent_menu'):
            return
        self.recent_menu.clear()
        valid = [p for p in self.recent_files if os.path.exists(p)]
        self.recent_files = valid
        if not valid:
            action = self.recent_menu.addAction(self.tr('（没有最近使用的文件）', '(No recent files)'))
            action.setEnabled(False)
            return
        for path in valid[:8]:
            self.recent_menu.addAction(os.path.basename(path),
                                       lambda _=False, p=path: self._load_recent_file(p))

    def _load_recent_file(self, path):
        def go():
            self.load_path(path)
        self._confirm_save(go)

    # ------------------------------------------------------------------
    # Clipboard
    def _copy_to_clipboard(self, surface):
        if surface is None:
            return False
        self._quick_clipboard = _copy_image(surface)
        clipboard = QApplication.clipboard()
        mime = __import__('PyQt6.QtCore', fromlist=['QMimeData']).QMimeData()
        png = surface_to_png_bytes(surface, with_alpha=True)
        mime.setData('image/png', QByteArray(png))
        mime.setImageData(surface.convertToFormat(QImage.Format.Format_ARGB32))
        clipboard.setMimeData(mime)
        return True

    def _copy_clicked(self):
        surface = self.canvas.copy_selection()
        if surface is None:
            MessageDialog(self, self.tr('没有要复制的内容。', 'Nothing is selected.')).present()
            return
        self._copy_to_clipboard(surface)
        self._update_action_sensitivity()

    def _cut_clicked(self):
        surface = self.canvas.copy_selection()
        if surface is None:
            return
        self._copy_to_clipboard(surface)
        self.canvas.delete_selection()
        self._update_action_sensitivity()

    def _paste_clicked(self):
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            mime = clipboard.mimeData()
            if mime is not None and mime.hasImage():
                data = mime.imageData()
                if isinstance(data, QImage):
                    image = data
        if image.isNull():
            mime = clipboard.mimeData()
            if mime is not None and mime.hasFormat('image/png'):
                image = QImage.fromData(bytes(mime.data('image/png')))
        if not image.isNull():
            self.canvas.paste_surface(image.convertToFormat(QImage.Format.Format_ARGB32))
            return
        if self._quick_clipboard is not None:
            self.canvas.paste_surface(_copy_image(self._quick_clipboard))
            return
        MessageDialog(self, self.tr('剪贴板中没有图像。', 'There is no image on the clipboard.')).present()

    def _paste_from_file(self):
        filters = self.tr('所有图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)',
                          'All picture files (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)')
        path, _ = QFileDialog.getOpenFileName(self, self.tr('粘贴来源', 'Paste from'), '', filters)
        if not path:
            return
        try:
            doc = Document.open(path)
        except Exception as exc:
            MessageDialog(self, self.tr('无法打开该文件。', 'Cannot open file.'), str(exc)).present()
            return
        self.canvas.paste_surface(doc.surface)

    # ------------------------------------------------------------------
    # Commands
    def _undo(self):
        self._commit_current_text()
        self.canvas.commit_floating()
        if self.doc.undo():
            self.canvas.update_after_image_change()
            self._update_title()
            self._update_action_sensitivity()
            self._update_quick_access()

    def _redo(self):
        self._commit_current_text()
        self.canvas.commit_floating()
        if self.doc.redo():
            self.canvas.update_after_image_change()
            self._update_title()
            self._update_action_sensitivity()
            self._update_quick_access()

    def _delete(self):
        self.canvas.delete_selection()
        self._update_action_sensitivity()

    def _select_all(self):
        self.canvas.select_all()
        self._update_action_sensitivity()

    def _invert_selection(self):
        if self.doc.selection is None:
            self.canvas.select_all()
        else:
            self.canvas.commit_floating()
            self.doc.invert_selection()
        self.canvas.update()
        self._update_action_sensitivity()

    def _crop(self):
        if self.canvas.crop():
            self._update_status_labels()
            self._update_action_sensitivity()
            self._update_title()

    def _resize_dialog(self):
        self._commit_current_text()

        def apply(width, height, skew_h, skew_v):
            if self.doc.selection:
                surface = self.canvas.get_clipboard_surface()
                if surface is None:
                    return
                self.canvas.commit_floating()
                self.doc.push_undo('调整大小')
                sel = self.doc.selection
                if sel:
                    x, y, sw, sh = sel.rect
                    scaled = surface.scaled(width, height,
                                            Qt.AspectRatioMode.IgnoreAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                    p = QPainter(self.doc.surface)
                    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                    p.fillRect(QRect(x, y, sw, sh), self.doc.background)
                    p.end()
                    self.doc.selection = Selection(x, y, scaled.width(), scaled.height(),
                                                   floating=scaled, floating_origin=(x, y))
                    self.doc.dirty = True
                    self.canvas.update_after_image_change()
            else:
                if self.doc.resize(width, height):
                    self.canvas.update_after_image_change()
                if (skew_h or skew_v) and self.doc.skew(skew_h, skew_v):
                    self.canvas.update_after_image_change()
            self._update_title()
            self._update_action_sensitivity()

        ResizeDialog(self, self.doc.width, self.doc.height, apply).present()

    def _rotate(self, mode):
        self._commit_current_text()
        self.canvas.commit_floating()
        self.doc.rotate(mode)
        self.canvas.update_after_image_change()
        self._update_title()

    def _invert_colors(self):
        self._commit_current_text()
        self.canvas.commit_floating()
        self.doc.invert_colors()
        self.canvas.update_after_image_change()
        self._update_title()

    def _clear_image(self):
        self._commit_current_text()
        self.canvas.commit_floating()
        self.doc.clear_image()
        self.canvas.update_after_image_change()
        self._update_title()

    def _properties(self):
        def apply(width, height, color, transparent):
            self._commit_current_text()
            self.canvas.commit_floating()
            if width != self.doc.width or height != self.doc.height:
                self.doc.resize_canvas(width, height)
            if not color:
                self._to_black_white()
            if transparent != self.doc.transparent:
                self.doc.set_transparency(transparent)
            self.canvas.update_after_image_change()
            self._update_title()
            self._update_action_sensitivity()

        AttributesDialog(self, self.doc, apply).present()

    def _to_black_white(self):
        image = self.doc.surface.copy()
        if image.format() != QImage.Format.Format_ARGB32:
            image = image.convertToFormat(QImage.Format.Format_ARGB32)
        data, stride = _buffer(image)
        for y in range(image.height()):
            off = y * stride
            end = off + image.width() * 4
            while off < end:
                b, g, r = data[off], data[off + 1], data[off + 2]
                gray = min(255, int(0.299 * r + 0.587 * g + 0.114 * b))
                data[off] = data[off + 1] = data[off + 2] = gray
                off += 4
        self.doc.push_undo('转换为黑白')
        self.doc.surface = image
        self.doc.dirty = True

    # ------------------------------------------------------------------
    # Text
    def _commit_current_text(self):
        self.canvas._commit_text()

    def _font_changed(self, font):
        self.canvas.text_family = font.family()
        self.canvas.update_text_style()

    def _font_size_changed(self, value):
        self.canvas.text_size = value
        self.canvas.update_text_style()

    def _set_text_style(self, attr, value):
        setattr(self.canvas, 'text_' + attr, value)
        self.canvas.update_text_style()

    def _set_text_opaque(self, value):
        self.canvas.text_opaque = value
        if value:
            self.btn_opaque.setChecked(True)
            self.btn_transparent.setChecked(False)
        else:
            self.btn_opaque.setChecked(False)
            self.btn_transparent.setChecked(True)
        self.canvas.update_text_style()

    # ------------------------------------------------------------------
    # View
    def _switch_ribbon(self, name):
        if name == 'home':
            self.home_tab.setChecked(True)
            self.view_tab.setChecked(False)
        else:
            self.home_tab.setChecked(False)
            self.view_tab.setChecked(True)
        self.home_ribbon.setVisible(name == 'home')
        self.view_ribbon.setVisible(name == 'view')

    def _set_rulers_visible(self, visible):
        self.ruler_corner.setVisible(visible)
        self.hruler.setVisible(visible)
        self.vruler.setVisible(visible)
        self.canvas.rulers = visible
        if visible:
            self._update_rulers()

    def _update_rulers(self):
        if hasattr(self, 'hruler'):
            self.hruler.update()
            self.vruler.update()

    def _toggle_rulers(self, active):
        self._set_rulers_visible(active)
        if self.cb_ruler.isChecked() != active:
            self.cb_ruler.blockSignals(True)
            self.cb_ruler.setChecked(active)
            self.cb_ruler.blockSignals(False)

    def _toggle_grid(self, active):
        self.canvas.grid = active
        if self.cb_grid.isChecked() != active:
            self.cb_grid.blockSignals(True)
            self.cb_grid.setChecked(active)
            self.cb_grid.blockSignals(False)
        self.canvas.update()

    def _toggle_status(self, active):
        self.statusbar.setVisible(active)
        self.status_visible = active

    def _toggle_thumbnail(self):
        self.thumbnail_visible = not self.thumbnail_visible
        self.thumb_panel.setVisible(self.thumbnail_visible)
        self.thumb_btn.setChecked(self.thumbnail_visible)
        self.thumb_area.update()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ------------------------------------------------------------------
    # Printing / page setup
    def _print(self, preview=False):
        self._commit_current_text()
        self.canvas.commit_floating()
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPrinter.PageOrientation.Landscape
                                   if self.page_settings['landscape']
                                   else QPrinter.PageOrientation.Portrait)
        try:
            if preview:
                dialog = QPrintPreviewDialog(printer, self)
                dialog.paintRequested.connect(self._draw_print_page)
                dialog.exec()
            else:
                dialog = QPrintDialog(printer, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self._draw_print_page(printer)
        except Exception as exc:
            MessageDialog(self, self.tr('paim 无法打印你的文档。', 'paim could not print the document.'),
                          str(exc)).present()

    def _draw_print_page(self, printer):
        painter = QPainter(printer)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        page_w, page_h = rect.width(), rect.height()
        scale = min(page_w / self.doc.width, page_h / self.doc.height)
        scale *= self.page_settings['scale'] / 100.0
        w = self.doc.width * scale
        h = self.doc.height * scale
        x = (page_w - w) / 2 if self.page_settings['center'] else 0
        y = (page_h - h) / 2 if self.page_settings['center'] else 0
        painter.fillRect(QRectF(0, 0, page_w, page_h), QColor(255, 255, 255))
        painter.drawImage(QRectF(x, y, w, h), self.doc.surface)
        painter.end()

    def _print_preview(self):
        self._print(preview=True)

    def _page_setup(self):
        def apply(settings):
            self.page_settings.update(settings)
            MessageDialog(self, self.tr('页面设置已更新。', 'Page setup updated.')).present()
        PageSetupDialog(self, self.page_settings, apply).present()

    # ------------------------------------------------------------------
    # Misc commands
    def _set_wallpaper(self):
        if not self.doc.filename:
            MessageDialog(self, self.tr('在将它选为桌面背景前必须保存该文件。',
                                        'The file must be saved before setting it as the desktop background.')).present()
            return
        try:
            base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
            path = base / 'mspaint-linux' / 'wallpaper.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            self.doc.duplicate().save(str(path), fmt='png', with_alpha=False)
            uri = path.as_uri()
            for key in ('picture-uri', 'picture-uri-dark'):
                subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', key, uri],
                               check=False, timeout=5)
            MessageDialog(self, self.tr('已将图片设置为桌面背景。',
                                        'The picture was set as the desktop background.')).present()
        except Exception as exc:
            MessageDialog(self, self.tr('无法设置桌面背景。', 'Could not set the desktop background.'),
                          str(exc)).present()

    def _send_email(self):
        if not self.doc.filename:
            MessageDialog(self, self.tr('请先保存文件。', 'Please save the file first.')).present()
            return
        try:
            subprocess.Popen(['xdg-email', '--attach', self.doc.filename])
        except Exception as exc:
            MessageDialog(self, str(exc)).present()

    def _scanner_unavailable(self):
        MessageDialog(self,
                      self.tr('未找到扫描仪或照相机，或该设备不受支持。',
                              'No scanner or camera was found, or the device is not supported.'),
                      self.tr('paim 通过文件打开或粘贴来导入图像。',
                              'paim imports pictures from files or the clipboard.')).present()

    def _help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr('paim 帮助', 'paim help'))
        dialog.resize(560, 500)
        layout = QVBoxLayout(dialog)
        title = QLabel('paim')
        title.setStyleSheet('font-size: 20px; font-weight: bold;')
        layout.addWidget(title)
        text = self.tr(
            'paim 是一款在 Linux 上使用 Qt6 构建的轻量绘图应用。\n\n'
            '键盘快捷键:\n'
            '  Ctrl+N  新建\n  Ctrl+O  打开\n  Ctrl+S  保存\n  F12  另存为\n'
            '  Ctrl+Z  撤消\n  Ctrl+Y  重做\n  Ctrl+X/C/V  剪切/复制/粘贴\n'
            '  Ctrl+A  全选\n  Ctrl+W  调整大小和扭曲\n  Ctrl+E  属性\n'
            '  Ctrl+Shift+X  裁剪\n  Ctrl+Shift+I  反色\n  Ctrl+Shift+N  清除图像\n'
            '  Ctrl+PgUp/Ctrl+PgDn  放大/缩小\n  F11  全屏\n  F1  帮助\n'
            '  Delete  删除选定内容\n  Esc  取消选择或文本编辑\n\n'
            '主题：查看 → 主题，可跟随系统或手动选浅色/深色。\n'
            '快速访问：右键功能区命令即可添加到标题栏。',
            'paim is a lightweight drawing app for Linux built with Qt6.\n\n'
            'Keyboard shortcuts:\n'
            '  Ctrl+N  New\n  Ctrl+O  Open\n  Ctrl+S  Save\n  F12  Save as\n'
            '  Ctrl+Z  Undo\n  Ctrl+Y  Redo\n  Ctrl+X/C/V  Cut/Copy/Paste\n'
            '  Ctrl+A  Select all\n  Ctrl+W  Resize and skew\n  Ctrl+E  Properties\n'
            '  Ctrl+Shift+X  Crop\n  Ctrl+Shift+I  Invert colours\n  Ctrl+Shift+N  Clear image\n'
            '  Ctrl+PgUp/Ctrl+PgDn  Zoom in/out\n  F11  Full screen\n  F1  Help\n'
            '  Delete  Delete selection\n  Esc  Cancel selection or text editing\n\n'
            'Theme: View → Theme, follow the system or choose Light/Dark.\n'
            'Quick Access: right-click a ribbon command to pin it to the title bar.')
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.clicked.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _about(self):
        AboutDialog(self).present()

    def _update_action_sensitivity(self):
        has_selection = self.doc.selection is not None
        for name in ('cut', 'copy', 'delete', 'invert-selection', 'crop'):
            action = self.actions.get(name)
            if action is not None:
                action.setEnabled(has_selection)
        for name in ('undo', 'redo'):
            action = self.actions.get(name)
            if action is not None:
                action.setEnabled(self.doc.can_undo() if name == 'undo' else self.doc.can_redo())
        self._update_quick_access()

    # ------------------------------------------------------------------
    # Drag and drop
    def _show_drop_hint(self, visible):
        self.drop_hint.setGeometry(self.central.rect())
        self.drop_hint.setVisible(visible)
        if visible:
            self.drop_hint.raise_()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._show_drop_hint(True)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._show_drop_hint(False)

    def dropEvent(self, event):
        self._show_drop_hint(False)
        if not event.mimeData().hasUrls():
            return
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self._open_dropped_files(paths)
        event.acceptProposedAction()

    def _open_dropped_files(self, paths):
        candidates = [p for p in paths if p and os.path.isfile(p)]
        if not candidates:
            MessageDialog(self, self.tr('没有可打开的文件。', 'No file to open.')).present()
            return False
        candidates.sort(key=lambda p: 0 if p.lower().endswith(
            ('.png', '.jpg', '.jpeg', '.bmp', '.dib', '.gif', '.tif', '.tiff',
             '.webp', '.ico', '.ppm', '.pgm', '.tga')) else 1)
        chosen = None
        last_error = None
        for candidate in candidates:
            reader = QImageReader(candidate)
            if reader.canRead():
                chosen = candidate
                break
        if chosen is None:
            try:
                Document.open(candidates[0])
                chosen = candidates[0]
            except Exception as exc:
                last_error = exc
        if chosen is None:
            MessageDialog(self, self.tr('paim 无法打开该文件。', 'paim cannot open this file.'),
                          str(last_error or '')).present()
            return False

        def go():
            self.load_path(chosen)
        self._confirm_save(go)
        return True

    # ------------------------------------------------------------------
    # Theme
    def _apply_runtime_theme(self, dark, *, force=False):
        if self._applying_theme:
            return
        if not force and dark == self.dark_mode:
            return
        self._applying_theme = True
        try:
            self.dark_mode = dark
            icon_module.set_dark_theme(dark)
            self.canvas.dark = dark
            app = QApplication.instance()
            if app is not None:
                app.setPalette(_app_palette(dark))
                app.setStyleSheet(_stylesheet(dark))
            self._refresh_icons()
            if hasattr(self, 'brush_btn'):
                self.brush_btn.setMenu(self._make_brush_menu())
            # Rebuild the quick-access buttons and their menus after the
            # currently open menu (if any) has closed.
            QTimer.singleShot(0, self._rebuild_qat)
            self.canvas.update()
            if hasattr(self, 'hruler'):
                self.hruler.update()
                self.vruler.update()
            if hasattr(self, 'thumb_area'):
                self.thumb_area.update()
            self._update_theme_menu()
        finally:
            self._applying_theme = False

    def _refresh_icons(self):
        for button in self.findChildren(QToolButton):
            name = button.property('paint_icon')
            if name:
                size = int(button.property('paint_icon_size') or 18)
                button.setIcon(icon_module.icon(name, size))
            shape = button.property('paint_shape')
            if shape:
                button.setIcon(icon_module.shape_icon(shape, 24))
            brush = button.property('paint_brush')
            if brush:
                button.setIcon(icon_module.brush_icon(brush, 36))

    def _on_system_theme_changed(self, *args):
        if self._applying_theme or self.theme_mode != 'auto':
            return
        self._apply_runtime_theme(_system_dark())

    def _poll_system_theme(self):
        if self._applying_theme or self.theme_mode != 'auto':
            return
        dark = _system_dark()
        if dark != self.dark_mode:
            self._apply_runtime_theme(dark)

    def _set_theme_mode(self, mode):
        if mode not in ('auto', 'light', 'dark'):
            return
        self.theme_mode = mode
        self._save_preferences()
        self._apply_runtime_theme(self._resolve_dark(), force=True)
        self._update_theme_menu()

    def _update_theme_menu(self):
        if not hasattr(self, 'theme_btn'):
            return
        labels = {
            'auto': self.tr('主题：跟随系统', 'Theme: System'),
            'light': self.tr('主题：浅色', 'Theme: Light'),
            'dark': self.tr('主题：深色', 'Theme: Dark'),
        }
        self.theme_btn.setText(labels.get(self.theme_mode, labels['auto']))
        self._updating_theme_menu = True
        try:
            for mode, action in getattr(self, 'theme_actions', {}).items():
                action.setChecked(mode == self.theme_mode)
        finally:
            self._updating_theme_menu = False

    def _on_theme_mode_toggled(self, checked, mode):
        if self._updating_theme_menu or not checked:
            return
        self._set_theme_mode(mode)

    # ------------------------------------------------------------------
    # Window events
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'drop_hint'):
            self.drop_hint.setGeometry(self.central.rect())
        self._update_rulers()

    def closeEvent(self, event):
        self._commit_current_text()
        if self._force_close or not self.doc.dirty:
            event.accept()
            return

        def go():
            self._force_close = True
            self.close()

        self._confirm_save(go)
        event.ignore()


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName('paim')
    app.setOrganizationName('paim')
    app.setDesktopFileName('paim')
    app.setStyle('Fusion')
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent.parent / 'assets' / 'paim.png')))
    window = PaintWindow()
    window.show()
    for path in argv[1:]:
        if os.path.isfile(path):
            window.load_path(path)
    return app.exec()
