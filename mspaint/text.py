# SPDX-License-Identifier: GPL-3.0-or-later
"""Text-tool rendering built on QPainter/QFont."""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen

from .document import _qcolor


def make_font(family, size_pt, bold=False, italic=False, underline=False) -> QFont:
    font = QFont(family or 'Sans')
    try:
        font.setPointSizeF(max(1.0, float(size_pt)))
    except Exception:
        font.setPointSizeF(12.0)
    font.setBold(bool(bold))
    font.setItalic(bool(italic))
    font.setUnderline(bool(underline))
    return font


def _lines(text):
    text = text or ' '
    return text.replace('\t', '    ').split('\n')


def text_extents(text, family, size_pt, bold=False, italic=False, underline=False):
    """Return (width, height) in device-independent pixels."""
    font = make_font(family, size_pt, bold, italic, underline)
    fm = QFontMetricsF(font)
    lines = _lines(text)
    width = max([fm.horizontalAdvance(line) for line in lines] + [1.0])
    height = max(1.0, fm.lineSpacing() * len(lines))
    return int(math.ceil(width)), int(math.ceil(height))


def draw_text(painter: QPainter, text, x, y, family, size_pt, bold=False,
              italic=False, underline=False, color=(0, 0, 0), background=None,
              opaque=False, alignment='left'):
    """Render text; returns (width, height) in pixels.

    The caller has already positioned the painter in image coordinates.
    """
    font = make_font(family, size_pt, bold, italic, underline)
    fm = QFontMetricsF(font)
    lines = _lines(text)
    widths = [fm.horizontalAdvance(line) for line in lines]
    w = max(1, int(math.ceil(max(widths + [1.0]))))
    h = max(1, int(math.ceil(fm.lineSpacing() * len(lines))))
    if opaque and background is not None:
        painter.save()
        painter.fillRect(QRectF(x, y, w, h), _qcolor(background))
        painter.restore()
    painter.save()
    painter.setFont(font)
    painter.setPen(QPen(_qcolor(color)))
    ascent = fm.ascent()
    line_spacing = fm.lineSpacing()
    for i, line in enumerate(lines):
        lw = fm.horizontalAdvance(line)
        if alignment == 'center':
            lx = x + (w - lw) / 2
        elif alignment == 'right':
            lx = x + (w - lw)
        else:
            lx = x
        painter.drawText(QPointF(lx, y + ascent + i * line_spacing), line)
    painter.restore()
    return w, h
