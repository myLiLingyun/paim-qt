# SPDX-License-Identifier: GPL-3.0-or-later
"""Small vector icon set used by the Paint ribbon (QPainter)."""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QIcon, QPainter, QPainterPath, QPen,
                         QPixmap)

from .shapes import build_shape_path

BLUE = QColor(46, 107, 179)
DARK = QColor(46, 46, 51)
ORANGE = QColor(224, 107, 31)
RED = QColor(204, 46, 46)
GREEN = QColor(51, 148, 77)
YELLOW = QColor(242, 184, 31)
GREY = QColor(115, 122, 133)
WHITE = QColor(255, 255, 255)

# Light theme palette (module globals are updated by set_dark_theme()).
_LIGHT_COLORS = {
    'DARK': QColor(46, 46, 51),
    'BLUE': QColor(46, 107, 179),
    'GREY': QColor(115, 122, 133),
}
_DARK_COLORS = {
    'DARK': QColor(224, 227, 232),
    'BLUE': QColor(112, 179, 250),
    'GREY': QColor(173, 181, 194),
}
_THEME_DARK = False


def set_dark_theme(dark: bool):
    """Switch icon stroke colours."""
    global _THEME_DARK, DARK, BLUE, GREY
    _THEME_DARK = bool(dark)
    values = _DARK_COLORS if _THEME_DARK else _LIGHT_COLORS
    DARK = QColor(values['DARK'])
    BLUE = QColor(values['BLUE'])
    GREY = QColor(values['GREY'])


def is_dark_theme():
    return _THEME_DARK


def _sp(points, close=False) -> QPainterPath:
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(QPointF(*points[0]))
    for p in points[1:]:
        path.lineTo(QPointF(*p))
    if close:
        path.closeSubpath()
    return path


def _base_pen(width=1.8, color=None) -> QPen:
    pen = QPen(color or DARK, width)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def draw_icon(painter: QPainter, name, size):
    """Draw a 32x32 logical icon, scaled to *size*."""
    s = size / 32.0
    painter.save()
    painter.scale(s, s)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(_base_pen(1.8, DARK))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    n = name

    def fill_rect(x, y, w, h, color):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRect(QRectF(x, y, w, h))

    def stroke_rect(x, y, w, h, color=None, width=1.8):
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = _base_pen(width, color or DARK)
        painter.setPen(pen)
        painter.drawRect(QRectF(x, y, w, h))

    def arc(cx, cy, r, start, sweep, color=None, width=1.8):
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(_base_pen(width, color or DARK))
        path = QPainterPath()
        path.arcMoveTo(QRectF(cx - r, cy - r, r * 2, r * 2), start)
        path.arcTo(QRectF(cx - r, cy - r, r * 2, r * 2), start, sweep)
        painter.drawPath(path)

    if n == 'save':
        fill_rect(5, 3, 22, 26, BLUE)
        fill_rect(9, 5, 14, 8, WHITE)
        fill_rect(9, 18, 14, 9, QColor(217, 230, 242))
        stroke_rect(9, 18, 14, 9, DARK)
    elif n in ('undo', 'redo'):
        painter.setPen(_base_pen(2.6, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if n == 'undo':
            arc(17, 18, 8, 0, 180, BLUE, 2.6)
            path = _sp([(5, 16), (8, 21), (13, 17)], True)
        else:
            arc(15, 18, 8, 180, 180, BLUE, 2.6)
            path = _sp([(27, 16), (24, 21), (19, 17)], True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BLUE)
        painter.drawPath(path)
    elif n == 'paste':
        fill_rect(8, 6, 17, 23, QColor(204, 163, 89))
        fill_rect(10, 10, 13, 16, QColor(242, 230, 199))
        stroke_rect(8, 6, 17, 23, DARK)
        fill_rect(12, 3, 9, 6, QColor(153, 158, 166))
        stroke_rect(12, 3, 9, 6, DARK)
    elif n == 'cut':
        painter.setPen(_base_pen(2, GREY))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(10, 5), QPointF(21, 20))
        painter.drawLine(QPointF(22, 5), QPointF(11, 20))
        painter.setPen(_base_pen(1.5, BLUE))
        painter.drawEllipse(QPointF(9, 24), 4, 4)
        painter.drawEllipse(QPointF(23, 24), 4, 4)
    elif n == 'copy':
        painter.setPen(_base_pen(1.5, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(5, 8, 16, 19))
        fill_rect(10, 4, 17, 20, WHITE)
        stroke_rect(10, 4, 17, 20, BLUE, 1.5)
    elif n in ('select_rect', 'crop'):
        if n == 'select_rect':
            pen = _base_pen(1.4, DARK)
            pen.setDashPattern([3, 2])
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(4, 4, 24, 24))
        else:
            painter.setPen(_base_pen(1.4, BLUE))
            pen = _base_pen(1.4, BLUE)
            pen.setDashPattern([3, 2])
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(8, 8, 16, 16))
            painter.setPen(_base_pen(1.8, DARK))
            painter.drawLine(QPointF(4, 4), QPointF(11, 4))
            painter.drawLine(QPointF(4, 4), QPointF(4, 11))
            painter.drawLine(QPointF(28, 28), QPointF(21, 28))
            painter.drawLine(QPointF(28, 28), QPointF(28, 21))
    elif n == 'select_free':
        pen = _base_pen(1.4, BLUE)
        pen.setDashPattern([3, 2])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(_sp([(6, 22), (8, 10), (16, 5), (26, 9), (25, 19), (17, 27), (8, 25)], True))
    elif n == 'resize':
        painter.setPen(_base_pen(1.8, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(4, 18, 11, 10))
        painter.drawRect(QRectF(17, 4, 11, 11))
        painter.drawLine(QPointF(15, 17), QPointF(22, 10))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BLUE)
        painter.drawPath(_sp([(22, 8), (24, 12), (19, 12)], True))
    elif n == 'rotate':
        arc(16, 16, 9, 160, 280, BLUE, 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BLUE)
        painter.drawPath(_sp([(22, 3), (28, 8), (21, 10)], True))
    elif n == 'pencil':
        path = _sp([(5, 26), (9, 15), (21, 3), (29, 10), (17, 22)], True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(242, 184, 26))
        painter.drawPath(path)
        painter.setPen(_base_pen(1.8, DARK))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(230, 191, 140))
        painter.drawPath(_sp([(5, 26), (9, 15), (13, 19)], True))
        painter.setBrush(QColor(51, 51, 51))
        painter.drawPath(_sp([(5, 26), (7, 21), (10, 24)], True))
    elif n == 'fill':
        painter.setPen(_base_pen(1.8, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(_sp([(5, 6), (18, 18), (23, 13), (10, 4), (5, 6)], False))
        path = QPainterPath()
        path.moveTo(8, 27)
        path.quadTo(18, 8, 28, 24)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(51, 115, 191, 90))
        painter.drawEllipse(QPointF(24, 9), 4, 4)
    elif n == 'text':
        fill_rect(4, 4, 24, 24, BLUE)
        painter.setPen(WHITE)
        painter.setFont(QFont('Sans', 21, QFont.Weight.Bold))
        painter.drawText(QPointF(9, 24), 'A')
    elif n == 'eraser':
        path = _sp([(5, 22), (17, 6), (27, 14), (15, 28)], True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(240, 179, 179))
        painter.drawPath(path)
        painter.setPen(_base_pen(1.8, DARK))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        fill_rect(4, 24, 24, 5, QColor(102, 173, 230))
    elif n == 'picker':
        painter.setPen(_base_pen(2, DARK))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(6, 26), QPointF(21, 10))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BLUE)
        painter.drawPath(_sp([(18, 5), (29, 5), (29, 16), (25, 13), (18, 5)], True))
        painter.setBrush(QColor(242, 191, 51))
        painter.drawEllipse(QPointF(5, 27), 3, 3)
    elif n == 'magnifier':
        painter.setPen(_base_pen(3, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(13, 13), 8, 8)
        painter.setPen(_base_pen(4, BLUE))
        painter.drawLine(QPointF(19, 19), QPointF(28, 28))
        painter.setPen(_base_pen(1, QColor(255, 255, 255, 204)))
        painter.drawEllipse(QPointF(11, 11), 3, 3)
    elif n == 'brush':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(209, 143, 77))
        painter.drawPath(_sp([(6, 26), (14, 16), (22, 8), (27, 12), (18, 23), (9, 29)], True))
        painter.setBrush(QColor(173, 107, 51))
        painter.drawPath(_sp([(6, 26), (14, 16), (17, 20), (9, 29)], True))
        painter.setPen(_base_pen(4, QColor(64, 64, 64)))
        painter.drawLine(QPointF(21, 4), QPointF(29, 12))
    elif n == 'line':
        painter.setPen(_base_pen(2, BLUE))
        painter.drawLine(QPointF(5, 26), QPointF(27, 6))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(DARK)
        painter.drawEllipse(QPointF(5, 26), 2, 2)
        painter.drawEllipse(QPointF(27, 6), 2, 2)
    elif n == 'curve':
        painter.setPen(_base_pen(2, BLUE))
        path = QPainterPath(QPointF(4, 25))
        path.cubicTo(QPointF(12, 2), QPointF(22, 30), QPointF(28, 7))
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(DARK)
        painter.drawEllipse(QPointF(4, 25), 2, 2)
        painter.drawEllipse(QPointF(28, 7), 2, 2)
    elif n == 'shapes':
        painter.setPen(_base_pen(1.8, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(4, 5, 15, 12))
        painter.drawEllipse(QPointF(22, 22), 7, 7)
        painter.drawPath(_sp([(4, 29), (11, 17), (18, 29)], True))
    elif n == 'outline':
        painter.setPen(_base_pen(1.5, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(4, 6, 24, 20))
    elif n == 'fill_style':
        painter.setPen(_base_pen(1.5, BLUE))
        painter.setBrush(BLUE)
        painter.drawRect(QRectF(4, 6, 24, 20))
        fill_rect(8, 10, 8, 6, QColor(255, 255, 255, 115))
    elif n == 'color1':
        fill_rect(4, 4, 24, 24, QColor(0, 0, 0))
        stroke_rect(4.5, 4.5, 23, 23, QColor(179, 179, 179), 1)
    elif n == 'color2':
        fill_rect(4, 4, 24, 24, QColor(255, 255, 255))
        stroke_rect(4.5, 4.5, 23, 23, QColor(140, 140, 140), 1)
    elif n == 'edit_colors':
        painter.setPen(Qt.PenStyle.NoPen)
        for i, c in enumerate([RED, ORANGE, YELLOW, GREEN, BLUE, QColor(140, 64, 179)]):
            painter.setBrush(c)
            painter.drawRect(QRectF(3 + (i % 3) * 9, 7 + (i // 3) * 10, 8, 8))
    elif n == 'paint3d':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(64, 140, 217))
        painter.drawEllipse(QPointF(16, 16), 10, 10)
        painter.setPen(_base_pen(1.5, WHITE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(16, 16), 5, 5)
    elif n in ('plus', 'minus'):
        painter.setPen(_base_pen(2, DARK))
        painter.drawLine(QPointF(8, 16), QPointF(24, 16))
        if n == 'plus':
            painter.drawLine(QPointF(16, 8), QPointF(16, 24))
    elif n == 'new':
        fill_rect(6, 5, 20, 23, WHITE)
        stroke_rect(6, 5, 20, 23, GREY)
        painter.setPen(_base_pen(2, BLUE))
        painter.drawLine(QPointF(16, 10), QPointF(16, 22))
        painter.drawLine(QPointF(10, 16), QPointF(22, 16))
    elif n == 'open':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(242, 199, 77))
        painter.drawPath(_sp([(3, 9), (13, 9), (16, 13), (29, 13), (26, 27), (5, 27)], True))
        painter.setPen(_base_pen(1.5, DARK))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(_sp([(3, 9), (13, 9), (16, 13), (29, 13), (26, 27), (5, 27)], True))
    elif n == 'print':
        fill_rect(7, 12, 18, 10, GREY)
        fill_rect(9, 4, 14, 9, WHITE)
        stroke_rect(9, 4, 14, 9, DARK)
        fill_rect(9, 22, 14, 6, WHITE)
        stroke_rect(9, 22, 14, 6, DARK)
    elif n == 'home':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BLUE)
        painter.drawPath(_sp([(3, 15), (16, 3), (29, 15), (25, 15), (25, 29), (7, 29), (7, 15)], True))
        fill_rect(13, 19, 6, 10, WHITE)
    elif n == 'theme':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BLUE)
        painter.drawEllipse(QPointF(16, 16), 9, 9)
        painter.setBrush(QColor(28, 31, 36))
        painter.drawEllipse(QPointF(21, 11), 8, 8)
        painter.setPen(_base_pen(1.2, BLUE))
        for i in range(8):
            a = i * math.pi / 4
            painter.drawLine(QPointF(16 + 12 * math.cos(a), 16 + 12 * math.sin(a)),
                             QPointF(16 + 15 * math.cos(a), 16 + 15 * math.sin(a)))
    elif n == 'grid':
        painter.setPen(_base_pen(1.2, BLUE))
        for i in range(4):
            v = 5 + i * 7.3
            painter.drawLine(QPointF(v, 5), QPointF(v, 27))
            painter.drawLine(QPointF(5, v), QPointF(27, v))
    elif n == 'ruler':
        fill_rect(3, 11, 26, 10, QColor(242, 217, 115))
        stroke_rect(3, 11, 26, 10, DARK)
        painter.setPen(_base_pen(1, DARK))
        for i in range(1, 6):
            painter.drawLine(QPointF(3 + i * 4, 11),
                             QPointF(3 + i * 4, 11 + (5 if i % 2 else 8)))
    elif n == 'statusbar':
        fill_rect(3, 22, 26, 5, GREY)
        stroke_rect(3, 22, 26, 5, DARK)
    elif n == 'fullscreen':
        painter.setPen(_base_pen(2, DARK))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for pts in ([(4, 12), (4, 4), (12, 4)], [(20, 4), (28, 4), (28, 12)],
                    [(28, 20), (28, 28), (20, 28)], [(12, 28), (4, 28), (4, 20)]):
            painter.drawPath(_sp(pts, False))
    elif n == 'thumbnail':
        painter.setPen(_base_pen(1.5, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(4, 4, 24, 24))
        painter.drawRect(QRectF(7, 7, 18, 18))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(46, 107, 179, 64))
        painter.drawRect(QRectF(7, 7, 18, 18))
    elif n in ('zoomin', 'zoomout'):
        painter.setPen(_base_pen(2.5, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(13, 13), 7, 7)
        painter.setPen(_base_pen(3, BLUE))
        painter.drawLine(QPointF(18, 18), QPointF(27, 27))
        painter.setPen(_base_pen(1.8, DARK))
        painter.drawLine(QPointF(9, 13), QPointF(17, 13))
        if n == 'zoomin':
            painter.drawLine(QPointF(13, 9), QPointF(13, 17))
    elif n == 'shape_more':
        painter.setPen(_base_pen(1.5, DARK))
        painter.drawPath(_sp([(11, 6), (21, 16), (11, 26)], False))
    elif n == 'chevron_up':
        painter.setPen(_base_pen(1.6, DARK))
        painter.drawPath(_sp([(8, 20), (16, 11), (24, 20)], False))
    elif n == 'chevron_down':
        painter.setPen(_base_pen(1.6, DARK))
        painter.drawPath(_sp([(8, 12), (16, 21), (24, 12)], False))
    elif n == 'dropdown':
        painter.setPen(_base_pen(1.4, DARK))
        painter.drawPath(_sp([(11, 13), (16, 19), (21, 13)], False))
    elif n == 'app':
        fill_rect(3, 3, 26, 26, WHITE)
        fill_rect(4, 4, 24, 24, QColor(166, 204, 242, 204))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BLUE)
        painter.drawEllipse(QPointF(18, 11), 4, 4)
        painter.setPen(_base_pen(3, BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(QPointF(8, 27))
        path.cubicTo(QPointF(8, 18), QPointF(28, 18), QPointF(28, 27))
        painter.drawPath(path)
        painter.setPen(_base_pen(2, QColor(102, 140, 191)))
        painter.drawLine(QPointF(5, 25), QPointF(26, 25))
    else:
        painter.setPen(_base_pen(1.8, DARK))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(6, 6, 20, 20))
    painter.restore()


def paint_icon(name, size=24) -> QPixmap:
    pixmap = QPixmap(int(size), int(size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    draw_icon(painter, name, size)
    painter.end()
    return pixmap


def icon(name, size=24) -> QIcon:
    return QIcon(paint_icon(name, size))


def image(name, size=16) -> QIcon:
    return icon(name, size)


def shape_icon(shape, size=24) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(_base_pen(1.3, BLUE))
    p.setBrush(Qt.BrushStyle.NoBrush)
    margin = 2.5
    w = size - 2 * margin
    h = size - 2 * margin
    if shape == 'line':
        p.drawLine(QPointF(margin, margin + h), QPointF(margin + w, margin))
    elif shape == 'curve':
        path = QPainterPath(QPointF(margin, margin + h))
        path.cubicTo(QPointF(margin + w * 0.25, margin - h * 0.25),
                     QPointF(margin + w * 0.75, margin + h * 1.25),
                     QPointF(margin + w, margin))
        p.drawPath(path)
    else:
        p.drawPath(build_shape_path(shape, margin, margin, w, h))
    p.end()
    return QIcon(pixmap)


def brush_icon(brush, size=36) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    orange = QColor(219, 120, 41)
    p.setPen(QPen(orange, 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(orange)
    if brush == 'calligraphy1':
        p.drawLine(QPointF(6, 26), QPointF(29, 9))
    elif brush == 'calligraphy2':
        p.drawLine(QPointF(6, 8), QPointF(29, 26))
    elif brush == 'airbrush':
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(30):
            import random
            r = random.Random(i)
            p.drawEllipse(QPointF(9 + r.random() * 21, 9 + r.random() * 19), 0.8, 0.8)
    elif brush == 'crayon':
        for i in range(5):
            p.setPen(QPen(orange, 1.3))
            p.drawLine(QPointF(7 + i, 26 - i), QPointF(17 + i, 17 - i))
    elif brush == 'marker':
        p.setPen(QPen(QColor(204, 102, 31, 153), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(8, 24), QPointF(28, 12))
    elif brush == 'watercolor':
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(204, 102, 31, 71))
        for i in range(5):
            p.drawEllipse(QPointF(12 + i * 3, 20 - i * 2), 6, 6)
    else:
        p.drawLine(QPointF(8, 26), QPointF(28, 10))
    p.setPen(QPen(QColor(194, 179, 158) if not _THEME_DARK else QColor(71, 46, 26),
                  3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(25, 8), QPointF(30, 13))
    p.end()
    return QIcon(pixmap)
