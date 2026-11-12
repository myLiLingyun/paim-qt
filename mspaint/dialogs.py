# SPDX-License-Identifier: GPL-3.0-or-later
"""Dialogs used by paim (PyQt6)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QColorDialog, QComboBox,
                             QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton,
                             QRadioButton, QSpinBox, QVBoxLayout, QWidget)

from .i18n import tr
from .raster import DEFAULT_PALETTE


def label(text, xalign=0.0, css=None, wrap=False):
    w = QLabel(text)
    w.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    if wrap:
        w.setWordWrap(True)
    if css:
        w.setStyleSheet(css)
    return w


class BaseDialog(QDialog):
    def __init__(self, parent, title, width=360):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)
        self._outer = QVBoxLayout(self)
        self.content = QVBoxLayout()
        self._outer.addLayout(self.content, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                        QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr('确定', 'OK'))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('取消', 'Cancel'))
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        self._outer.addWidget(self.buttons)

    def _on_accept(self):
        self.apply()
        self.accept()

    def apply(self):
        pass

    def present(self):
        self.show()
        self.raise_()
        self.activateWindow()


class ResizeDialog(BaseDialog):
    def __init__(self, parent, width, height, callback):
        super().__init__(parent, tr('调整大小和扭曲', 'Resize and skew'), 420)
        self.src_w, self.src_h = width, height
        self.callback = callback
        self.mode = 'percent'
        self._updating = False

        head = QHBoxLayout()
        head.addWidget(label(tr('调整大小', 'Resize'), css='font-weight: bold;'))
        head.addSpacing(16)
        head.addWidget(label(tr('倾斜', 'Skew'), css='font-weight: bold;'))
        head.addStretch(1)
        self.content.addLayout(head)

        grid = QGridLayout()
        grid.addWidget(label(tr('单位:', 'Units:')), 0, 0)
        self.unit_pct = QRadioButton(tr('百分比', 'Percentage'))
        self.unit_px = QRadioButton(tr('像素', 'Pixels'))
        self.unit_pct.setChecked(True)
        unit_group = QButtonGroup(self)
        unit_group.addButton(self.unit_pct)
        unit_group.addButton(self.unit_px)
        units = QHBoxLayout()
        units.addWidget(self.unit_pct)
        units.addWidget(self.unit_px)
        grid.addLayout(units, 0, 1, 1, 2)
        grid.addWidget(label(tr('水平:', 'Horizontal:')), 1, 0)
        self.hspin = QSpinBox()
        self.hspin.setRange(1, 10000)
        self.hspin.setValue(100)
        grid.addWidget(self.hspin, 1, 1, 1, 2)
        grid.addWidget(label(tr('垂直:', 'Vertical:')), 2, 0)
        self.vspin = QSpinBox()
        self.vspin.setRange(1, 10000)
        self.vspin.setValue(100)
        grid.addWidget(self.vspin, 2, 1, 1, 2)
        self.ratio = QCheckBox(tr('保持纵横比', 'Maintain aspect ratio'))
        self.ratio.setChecked(True)
        grid.addWidget(self.ratio, 3, 0, 1, 3)
        self.content.addLayout(grid)
        self.content.addWidget(self._separator())

        skew = QGridLayout()
        skew.addWidget(label(tr('水平:', 'Horizontal:')), 0, 0)
        self.skew_h = QSpinBox()
        self.skew_h.setRange(-89, 89)
        skew.addWidget(self.skew_h, 0, 1)
        skew.addWidget(label(tr('度', 'degrees')), 0, 2)
        skew.addWidget(label(tr('垂直:', 'Vertical:')), 1, 0)
        self.skew_v = QSpinBox()
        self.skew_v.setRange(-89, 89)
        skew.addWidget(self.skew_v, 1, 1)
        skew.addWidget(label(tr('度', 'degrees')), 1, 2)
        self.content.addLayout(skew)

        self.unit_pct.toggled.connect(self._mode_changed)
        self.hspin.valueChanged.connect(self._h_changed)
        self.vspin.valueChanged.connect(self._v_changed)

    @staticmethod
    def _separator():
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet('background: #c8c8c8;')
        return line

    def _mode_changed(self, _checked=False):
        if self._updating:
            return
        self._updating = True
        if self.unit_px.isChecked():
            self.mode = 'pixel'
            self.hspin.setRange(1, 100000)
            self.vspin.setRange(1, 100000)
            self.hspin.setValue(self.src_w)
            self.vspin.setValue(self.src_h)
        else:
            self.mode = 'percent'
            self.hspin.setRange(1, 10000)
            self.vspin.setRange(1, 10000)
            self.hspin.setValue(100)
            self.vspin.setValue(100)
        self._updating = False

    def _h_changed(self, value):
        if self._updating or not self.ratio.isChecked():
            return
        self._updating = True
        if self.mode == 'percent':
            self.vspin.setValue(value)
        else:
            self.vspin.setValue(max(1, round(value * self.src_h / self.src_w)))
        self._updating = False

    def _v_changed(self, value):
        if self._updating or not self.ratio.isChecked():
            return
        self._updating = True
        if self.mode == 'percent':
            self.hspin.setValue(value)
        else:
            self.hspin.setValue(max(1, round(value * self.src_w / self.src_h)))
        self._updating = False

    def apply(self):
        if self.mode == 'percent':
            w = self.src_w * self.hspin.value() / 100.0
            h = self.src_h * self.vspin.value() / 100.0
        else:
            w = self.hspin.value()
            h = self.vspin.value()
        self.callback(int(round(w)), int(round(h)), self.skew_h.value(),
                      self.skew_v.value())


class AttributesDialog(BaseDialog):
    def __init__(self, parent, doc, callback):
        super().__init__(parent, tr('映像属性', 'Image properties'), 380)
        self.doc = doc
        self.callback = callback
        grid = QGridLayout()
        grid.addWidget(label(tr('宽度:', 'Width:')), 0, 0)
        self.wspin = QSpinBox()
        self.wspin.setRange(1, 100000)
        self.wspin.setValue(doc.width)
        grid.addWidget(self.wspin, 0, 1)
        grid.addWidget(label(tr('高度:', 'Height:')), 1, 0)
        self.hspin = QSpinBox()
        self.hspin.setRange(1, 100000)
        self.hspin.setValue(doc.height)
        grid.addWidget(self.hspin, 1, 1)
        grid.addWidget(label(tr('单位:', 'Units:')), 2, 0)
        self.units = QComboBox()
        self.units.addItems([tr('像素', 'Pixels'), tr('英寸', 'Inches'),
                             tr('厘米', 'Centimeters')])
        grid.addWidget(self.units, 2, 1)
        grid.addWidget(label(tr('颜色:', 'Colors:')), 3, 0)
        self.color = QRadioButton(tr('彩色', 'Color'))
        self.bw = QRadioButton(tr('黑白', 'Black and white'))
        self.color.setChecked(True)
        color_group = QButtonGroup(self)
        color_group.addButton(self.color)
        color_group.addButton(self.bw)
        colors = QHBoxLayout()
        colors.addWidget(self.color)
        colors.addWidget(self.bw)
        grid.addLayout(colors, 3, 1)
        self.transparent = QCheckBox(tr('透明', 'Transparent'))
        self.transparent.setToolTip(tr('透明背景（保留 Alpha 通道）',
                                       'Transparent background (preserve the alpha channel)'))
        self.transparent.setChecked(bool(getattr(doc, 'transparent', False)))
        grid.addWidget(self.transparent, 4, 0, 1, 2)
        self.content.addLayout(grid)
        self.content.addWidget(label(
            tr('透明背景会保留 PNG、GIF 和 WebP 文件的透明通道。',
               'A transparent background is preserved in PNG, GIF and WebP files.'),
            css='color: #666;', wrap=True))
        self.content.addWidget(label(
            tr('注意：将图像转换为黑白后无法撤销。',
               'Note: converting the image to black and white cannot be undone.'),
            css='color: #666;', wrap=True))

    def apply(self):
        factor = 1.0
        if self.units.currentIndex() == 1:
            factor = 96.0
        elif self.units.currentIndex() == 2:
            factor = 96.0 / 2.54
        w = int(round(self.wspin.value() * factor))
        h = int(round(self.hspin.value() * factor))
        self.callback(w, h, not self.bw.isChecked(), self.transparent.isChecked())


class ColorDialog:
    """A thin wrapper around Qt's full-featured colour chooser."""

    def __init__(self, parent, initial, callback, title=None):
        self.parent = parent
        self.initial = initial
        self.callback = callback
        self.title = title or tr('编辑颜色', 'Edit colors')

    def present(self):
        initial = QColor(int(self.initial[0]), int(self.initial[1]), int(self.initial[2]))
        dialog = QColorDialog(initial, self.parent)
        dialog.setWindowTitle(self.title)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        for i, color in enumerate(DEFAULT_PALETTE[:20]):
            dialog.setCustomColor(i, QColor(color))
        if dialog.exec():
            color = dialog.currentColor()
            self.callback((color.red(), color.green(), color.blue()))

    def apply(self):
        pass


class SaveOptionsDialog(BaseDialog):
    def __init__(self, parent, fmt, callback):
        super().__init__(parent, tr('保存选项', 'Save options'), 340)
        self.fmt = fmt
        self.callback = callback
        self.content.addWidget(label(tr('选择保存格式：', 'Choose a format:'),
                                     css='font-weight: bold;'))
        self.formats = QComboBox()
        self.formats.addItems([tr('PNG 图片', 'PNG picture'), tr('JPEG 图片', 'JPEG picture'),
                               tr('BMP 图片', 'BMP picture'), tr('GIF 图片', 'GIF picture')])
        mapping = {'png': 0, 'jpg': 1, 'jpeg': 1, 'bmp': 2, 'dib': 2, 'gif': 3}
        self.formats.setCurrentIndex(mapping.get(fmt, 0))
        self.content.addWidget(self.formats)
        self.depth_label = label(tr('BMP 位深度：', 'BMP bit depth:'))
        self.depths = QComboBox()
        self.depths.addItems([tr('单色位图 (1 位)', 'Monochrome bitmap (1-bit)'),
                              tr('16 色位图 (4 位)', '16-color bitmap (4-bit)'),
                              tr('256 色位图 (8 位)', '256-color bitmap (8-bit)'),
                              tr('24 位位图', '24-bit bitmap')])
        self.depths.setCurrentIndex(3)
        self.content.addWidget(self.depth_label)
        self.content.addWidget(self.depths)
        self.formats.currentIndexChanged.connect(self._update_depth)
        self._update_depth()

    def _update_depth(self, *_args):
        enabled = self.formats.currentIndex() == 2
        self.depth_label.setEnabled(enabled)
        self.depths.setEnabled(enabled)

    def apply(self):
        fmt = ['png', 'jpg', 'bmp', 'gif'][self.formats.currentIndex()]
        bits = [1, 4, 8, 24][self.depths.currentIndex()]
        self.callback(fmt, bits)


class PageSetupDialog(BaseDialog):
    def __init__(self, parent, settings, callback):
        super().__init__(parent, tr('页面设置', 'Page setup'), 400)
        self.settings = settings
        self.callback = callback
        grid = QGridLayout()
        grid.addWidget(label(tr('方向:', 'Orientation:')), 0, 0)
        self.portrait = QRadioButton(tr('纵向', 'Portrait'))
        self.landscape = QRadioButton(tr('横向', 'Landscape'))
        self.portrait.setChecked(not settings.get('landscape'))
        self.landscape.setChecked(settings.get('landscape', False))
        orient = QHBoxLayout()
        orient.addWidget(self.portrait)
        orient.addWidget(self.landscape)
        grid.addLayout(orient, 0, 1)
        grid.addWidget(label(tr('缩放:', 'Scale:')), 1, 0)
        self.scale = QSpinBox()
        self.scale.setRange(10, 400)
        self.scale.setValue(int(settings.get('scale', 100)))
        scale_row = QHBoxLayout()
        scale_row.addWidget(self.scale)
        scale_row.addWidget(label('%'))
        grid.addLayout(scale_row, 1, 1)
        grid.addWidget(label(tr('左边距:', 'Left margin:')), 2, 0)
        self.left = QDoubleSpinBox()
        self.left.setRange(0, 100)
        self.left.setSingleStep(0.1)
        self.left.setValue(settings.get('left', 0.5))
        left_row = QHBoxLayout()
        left_row.addWidget(self.left)
        left_row.addWidget(label(tr('英寸', 'inches')))
        grid.addLayout(left_row, 2, 1)
        grid.addWidget(label(tr('上边距:', 'Top margin:')), 3, 0)
        self.top = QDoubleSpinBox()
        self.top.setRange(0, 100)
        self.top.setSingleStep(0.1)
        self.top.setValue(settings.get('top', 0.5))
        top_row = QHBoxLayout()
        top_row.addWidget(self.top)
        top_row.addWidget(label(tr('英寸', 'inches')))
        grid.addLayout(top_row, 3, 1)
        self.center = QCheckBox(tr('居中', 'Center'))
        self.center.setChecked(settings.get('center', True))
        self.content.addLayout(grid)
        self.content.addWidget(self.center)

    def apply(self):
        self.callback({
            'landscape': self.landscape.isChecked(),
            'scale': self.scale.value(),
            'left': self.left.value(),
            'top': self.top.value(),
            'center': self.center.isChecked(),
        })


class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr('关于 paim', 'About paim'))
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = QLabel('paim')
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        layout.addWidget(title)
        layout.addWidget(QLabel('paim (paintImproved) 2.0.0'))
        comments = tr(
            'paim (paintImproved)\n一款轻快的 Linux Qt6 绘图应用\n'
            '支持绘图工具、选区、文本、图像调整和多种文件格式。',
            'paim (paintImproved)\nA lightweight Qt6 drawing application for Linux.\n'
            'Tools, selections, text, image adjustments and many file formats.')
        text = QLabel(comments)
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addWidget(QLabel('https://github.com/myLiLingyun/paim-qt'))
        layout.addWidget(QLabel('GNU GPL v3 or later\nCopyright (C) 2026 paim contributors'))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)

    def present(self):
        self.show()
        self.raise_()
        self.activateWindow()


class MessageDialog:
    """A modal message box with the same call shape as the GTK version."""

    def __init__(self, parent, text, secondary=None, kind=None, buttons=None,
                 callback=None):
        self.parent = parent
        self.text = text
        self.secondary = secondary
        self.kind = kind
        self.callback = callback

    def present(self):
        box = QMessageBox(self.parent)
        box.setWindowTitle('paim')
        box.setText(self.text)
        if self.secondary:
            box.setInformativeText(self.secondary)
        if self.kind in ('error', 'ERROR', 3):
            box.setIcon(QMessageBox.Icon.Critical)
        elif self.kind in ('warning', 'WARNING', 1):
            box.setIcon(QMessageBox.Icon.Warning)
        else:
            box.setIcon(QMessageBox.Icon.Information)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
        if self.callback:
            self.callback(0)
