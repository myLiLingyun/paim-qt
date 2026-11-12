# SPDX-License-Identifier: GPL-3.0-or-later
"""Raster drawing primitives, brushes, fills and shape rendering (Qt)."""
from __future__ import annotations

import math
import random
from collections import deque

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QImage, QPainter, QPainterPath, QPen,
                         QRadialGradient)

from .document import _buffer, _qcolor
from .shapes import build_shape_path


# Palette used by ms-paint (20 colours, two rows of 10).
DEFAULT_PALETTE = [
    '#000000', '#7F7F7F', '#880015', '#ED1C24', '#FF7F27',
    '#FFF200', '#22B14C', '#00A2E8', '#3F48CC', '#A349A4',
    '#FFFFFF', '#C3C3C3', '#B97A57', '#FFAEC9', '#FFC90E',
    '#EFE4B0', '#B5E61D', '#99D9EA', '#7092BE', '#C8BFE7',
]

BRUSH_LABELS = {
    'brush': ('刷子', 'Brush'),
    'calligraphy1': ('书法笔刷 1', 'Calligraphy brush 1'),
    'calligraphy2': ('书法笔刷 2', 'Calligraphy brush 2'),
    'airbrush': ('喷枪', 'Airbrush'),
    'paintbrush': ('颜料刷', 'Paintbrush'),
    'crayon': ('蜡笔', 'Crayon'),
    'marker': ('记号笔', 'Marker'),
    'pencil': ('普通铅笔', 'Regular pencil'),
    'watercolor': ('水彩笔刷', 'Watercolor brush'),
}
BRUSH_ORDER = list(BRUSH_LABELS)
LINE_WIDTHS = [1, 2, 3, 4, 5, 6, 8, 10, 16, 24, 30, 40]
SHAPE_OUTLINE_STYLES = {
    'none': ('无轮廓', 'No outline'),
    'solid': ('实线', 'Solid color'),
    'crayon': ('蜡笔', 'Crayon'),
    'marker': ('记号笔', 'Marker'),
    'oil': ('油画笔', 'Oil'),
    'pencil': ('普通铅笔', 'Natural pencil'),
    'watercolor': ('水彩', 'Watercolor'),
}
SHAPE_FILL_STYLES = {
    'none': ('无填充', 'No fill'),
    'solid': ('纯色', 'Solid color'),
    'crayon': ('蜡笔', 'Crayon'),
    'marker': ('记号笔', 'Marker'),
    'oil': ('油画笔', 'Oil'),
    'pencil': ('普通铅笔', 'Natural pencil'),
    'watercolor': ('水彩', 'Watercolor'),
}


def rgb(rgb_tuple, alpha=1.0):
    c = _qcolor(rgb_tuple)
    c.setAlphaF(alpha)
    return c


def _color(color, alpha=1.0) -> QColor:
    c = _qcolor(color)
    c.setAlphaF(max(0.0, min(1.0, c.alphaF() * float(alpha))))
    return c


def _lerp(a, b, t):
    return a + (b - a) * t


def _pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, max(0.01, float(width)))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def stroke_segment(painter: QPainter, p0, p1, color, width, brush='brush', *, seed=0,
                   alpha=1.0):
    """Draw one brush segment.  The caller has already configured the painter."""
    x0, y0 = p0
    x1, y1 = p1
    rng = random.Random((seed * 1315423911) ^ (int(x0) * 73856093) ^ (int(y0) * 19349663))
    w = max(0.5, float(width))
    painter.save()
    if brush == 'pencil':
        painter.setPen(_pen(_color(color, alpha), max(0.7, w * 0.25)))
        painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    elif brush == 'calligraphy1':
        _stamp_rotated(painter, p0, p1, color, w, -math.pi / 4, alpha)
    elif brush == 'calligraphy2':
        _stamp_rotated(painter, p0, p1, color, w, math.pi / 4, alpha)
    elif brush == 'airbrush':
        dist = max(1.0, math.hypot(x1 - x0, y1 - y0))
        n = max(3, int(dist * (w / 3.0)) + 2)
        painter.setPen(Qt.PenStyle.NoPen)
        for _ in range(n):
            t = rng.random()
            cx = _lerp(x0, x1, t) + rng.uniform(-1, 1) * w * 0.7
            cy = _lerp(y0, y1, t) + rng.uniform(-1, 1) * w * 0.7
            rr = rng.uniform(0.35, max(0.7, w * 0.18))
            painter.setBrush(_color(color, alpha * rng.uniform(0.25, 0.8)))
            painter.drawEllipse(QPointF(cx, cy), rr, rr)
    elif brush == 'paintbrush':
        strokes = max(3, int(w / 2.5))
        nx, ny = (-(y1 - y0), x1 - x0)
        ln = math.hypot(nx, ny) or 1
        for i in range(strokes):
            off = (i - (strokes - 1) / 2) * (w / max(4, strokes))
            jx = nx / ln * off + rng.uniform(-0.7, 0.7)
            jy = ny / ln * off + rng.uniform(-0.7, 0.7)
            painter.setPen(_pen(_color(color, alpha * rng.uniform(0.55, 1.0)),
                                max(0.6, rng.uniform(0.55, 1.25))))
            painter.drawLine(QPointF(x0 + jx, y0 + jy), QPointF(x1 + jx, y1 + jy))
    elif brush == 'crayon':
        n = max(2, int(w / 2))
        nx, ny = (-(y1 - y0), x1 - x0)
        ln = math.hypot(nx, ny) or 1
        for _ in range(n):
            j = rng.uniform(-w / 2, w / 2)
            painter.setPen(_pen(_color(color, alpha * rng.uniform(0.35, 0.8)),
                                max(0.5, w * 0.16)))
            painter.drawLine(QPointF(x0 + nx / ln * j, y0 + ny / ln * j),
                             QPointF(x1 + nx / ln * j + rng.uniform(-1, 1),
                                     y1 + ny / ln * j + rng.uniform(-1, 1)))
    elif brush == 'marker':
        painter.setPen(_pen(_color(color, alpha * 0.62), w))
        painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        painter.setPen(_pen(_color(color, alpha * 0.55), max(1.0, w * 0.65)))
        painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    elif brush == 'watercolor':
        painter.setPen(_pen(_color(color, alpha * 0.16), w * 1.5))
        painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        painter.setPen(Qt.PenStyle.NoPen)
        for _ in range(2):
            painter.setBrush(_color(color, alpha * 0.10))
            ox = rng.uniform(-w * 0.35, w * 0.35)
            oy = rng.uniform(-w * 0.35, w * 0.35)
            radius = rng.uniform(w * 0.35, w * 0.8)
            painter.drawEllipse(QPointF(_lerp(x0, x1, 0.5) + ox,
                                       _lerp(y0, y1, 0.5) + oy), radius, radius)
    else:  # standard round brush
        painter.setPen(_pen(_color(color, alpha), w))
        painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        if w >= 4:
            painter.setPen(_pen(_color(color, alpha * 0.35), max(1.0, w * 0.42)))
            painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    painter.restore()


def _stamp_rotated(painter, p0, p1, color, width, angle, alpha):
    painter.save()
    painter.setPen(_pen(_color(color, alpha), max(0.7, width * 0.35)))
    painter.drawLine(QPointF(*p0), QPointF(*p1))
    dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    steps = max(1, int(dist / max(1.0, width * 0.35)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color(color, alpha))
    for i in range(steps + 1):
        t = i / steps
        cx = _lerp(p0[0], p1[0], t)
        cy = _lerp(p0[1], p1[1], t)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(math.degrees(angle))
        painter.scale(width * 0.52, width * 0.22)
        painter.drawEllipse(QRectF(-1, -1, 2, 2))
        painter.restore()
    painter.restore()


def draw_freehand(painter, points, color, width, brush='brush', seed=0):
    if len(points) == 1:
        points = [points[0], (points[0][0] + 0.01, points[0][1] + 0.01)]
    for i in range(len(points) - 1):
        stroke_segment(painter, points[i], points[i + 1], color, width, brush, seed=seed + i)


def draw_pixel_line(surface: QImage, x0, y0, x1, y1, color_rgb):
    """Draw a crisp one-pixel Bresenham line directly into an ARGB32 image.

    Used by the pencil at 1 px so a click changes exactly the pixel under the
    pointer and a drag has no anti-aliased fringe.
    """
    w, h = surface.width(), surface.height()
    x0, y0 = int(math.floor(x0)), int(math.floor(y0))
    x1, y1 = int(math.floor(x1)), int(math.floor(y1))
    c = _qcolor(color_rgb)
    c.setAlpha(255)
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < w and 0 <= y0 < h:
            surface.setPixelColor(x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def bucket_fill(surface: QImage, x: int, y: int, color_rgb, tolerance=0,
                alpha=1.0):
    """Scanline flood fill with exact / tolerance matching on ARGB32."""
    w, h = surface.width(), surface.height()
    if x < 0 or y < 0 or x >= w or y >= h:
        return False
    data, stride = _buffer(surface)
    off = int(y) * stride + int(x) * 4
    target = bytes(data[off:off + 4])
    c = _qcolor(color_rgb)
    a = max(0, min(255, int(round(c.alphaF() * 255 * alpha))))
    new = bytes((c.blue(), c.green(), c.red(), a))
    if target == new:
        return False

    def matches(off):
        return (abs(data[off] - target[0]) <= tolerance
                and abs(data[off + 1] - target[1]) <= tolerance
                and abs(data[off + 2] - target[2]) <= tolerance
                and abs(data[off + 3] - target[3]) <= tolerance)

    seen = bytearray(w * h)
    stack = deque([(int(x), int(y))])
    while stack:
        cx, cy = stack.pop()
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            continue
        idx = cy * w + cx
        if seen[idx]:
            continue
        off = cy * stride + cx * 4
        if not matches(off):
            continue
        left = cx
        while left > 0:
            o = cy * stride + (left - 1) * 4
            if seen[cy * w + left - 1] or not matches(o):
                break
            left -= 1
        right = cx
        while right < w - 1:
            o = cy * stride + (right + 1) * 4
            if seen[cy * w + right + 1] or not matches(o):
                break
            right += 1
        for px in range(left, right + 1):
            seen[cy * w + px] = 1
            o = cy * stride + px * 4
            data[o:o + 4] = new
            if cy > 0:
                oo = (cy - 1) * stride + px * 4
                if not seen[(cy - 1) * w + px] and matches(oo):
                    stack.append((px, cy - 1))
            if cy < h - 1:
                oo = (cy + 1) * stride + px * 4
                if not seen[(cy + 1) * w + px] and matches(oo):
                    stack.append((px, cy + 1))
    return True


def fill_shape(painter: QPainter, shape, x, y, w, h, fill_style, fill_color,
               outline_style, outline_color, line_width, *, alpha=1.0,
               corner_radius=None):
    """Render a shape with Paint's outline/fill styles."""
    path = build_shape_path(shape, x, y, w, h, corner_radius=corner_radius)
    if path.isEmpty():
        return
    if fill_style != 'none':
        painter.save()
        if fill_style == 'solid':
            painter.fillPath(path, _color(fill_color, alpha))
        else:
            painter.setClipPath(path)
            _style_fill(painter, path, fill_style, fill_color, alpha)
        painter.restore()
    if outline_style != 'none':
        painter.save()
        if outline_style == 'solid':
            painter.setPen(_pen(_color(outline_color, alpha), max(0.8, line_width)))
            painter.drawPath(path)
        else:
            _style_stroke_path(painter, path, outline_style, outline_color,
                               line_width, alpha)
        painter.restore()


def _style_fill(painter, path: QPainterPath, style, color, alpha):
    x, y, w, h = (path.boundingRect().x(), path.boundingRect().y(),
                  path.boundingRect().width(), path.boundingRect().height())
    painter.setPen(Qt.PenStyle.NoPen)
    if style == 'watercolor':
        rng = random.Random(int(x + y * 3 + w * 7 + h * 11))
        for _ in range(30):
            cx = x + rng.random() * w
            cy = y + rng.random() * h
            r = rng.uniform(4, max(8, min(w, h) * 0.22))
            grad = QRadialGradient(QPointF(cx, cy), r)
            c0 = _color(color, alpha * 0.18)
            c1 = _color(color, 0)
            grad.setColorAt(0, c0)
            grad.setColorAt(1, c1)
            painter.setBrush(grad)
            painter.drawEllipse(QPointF(cx, cy), r, r)
    elif style == 'crayon':
        rng = random.Random(int(x * 5 + y * 13 + w + h * 3))
        for _ in range(140):
            px, py = x + rng.random() * w, y + rng.random() * h
            painter.setBrush(_color(color, alpha * rng.uniform(0.15, 0.55)))
            radius = rng.uniform(0.5, 1.4)
            painter.drawEllipse(QPointF(px, py), radius, radius)
    elif style == 'marker':
        painter.fillRect(path.boundingRect(), _color(color, alpha * 0.35))
    elif style == 'pencil':
        rng = random.Random(int(x + y * 2 + w * 3))
        for _ in range(100):
            px = x + rng.random() * w
            py = y + rng.random() * h
            painter.fillRect(QRectF(px, py, rng.uniform(0.6, 1.6), 1),
                             _color(color, alpha * rng.uniform(0.2, 0.65)))
    elif style == 'oil':
        rng = random.Random(int(x * 2 + y * 7 + w))
        for _ in range(60):
            px, py = x + rng.random() * w, y + rng.random() * h
            painter.save()
            painter.translate(px, py)
            painter.rotate(rng.random() * 180)
            painter.scale(rng.uniform(2, 8), rng.uniform(0.6, 1.8))
            painter.setBrush(_color(color, alpha * rng.uniform(0.2, 0.5)))
            painter.drawEllipse(QRectF(-1, -1, 2, 2))
            painter.restore()
    else:
        painter.fillRect(path.boundingRect(), _color(color, alpha * 0.5))


def _style_stroke_path(painter, path: QPainterPath, style, color, width, alpha):
    width = max(0.8, width)
    if style == 'marker':
        painter.setPen(_pen(_color(color, alpha * 0.5), width))
        painter.drawPath(path)
        painter.setPen(_pen(_color(color, alpha * 0.8), max(1, width * 0.5)))
        painter.drawPath(path)
    elif style == 'watercolor':
        for i in range(3):
            painter.setPen(_pen(_color(color, alpha * (0.18 + i * 0.07)),
                                max(1, width * (1 + i * 0.45))))
            painter.drawPath(path)
    elif style in ('crayon', 'pencil'):
        pen = _pen(_color(color, alpha * 0.7), width)
        pen.setDashPattern([1.5, 1.8])
        painter.setPen(pen)
        painter.drawPath(path)
    elif style == 'oil':
        painter.setPen(_pen(_color(color, alpha * 0.75), max(1, width * 1.2)))
        painter.drawPath(path)
    else:
        painter.setPen(_pen(_color(color, alpha), width))
        painter.drawPath(path)


def draw_curve(painter: QPainter, p0, p1, c1, c2, color, width,
               outline_style='solid', alpha=1.0):
    path = QPainterPath(QPointF(*p0))
    path.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*p1))
    painter.save()
    if outline_style == 'solid':
        painter.setPen(_pen(_color(color, alpha), max(0.8, width)))
        painter.drawPath(path)
    else:
        _style_stroke_path(painter, path, outline_style, color, width, alpha)
    painter.restore()


def draw_eraser(painter: QPainter, x, y, size, color, clear=False):
    painter.save()
    rgba = _qcolor(color)
    if clear or rgba.alpha() <= 0:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 0))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(rgba)
    painter.drawRect(QRectF(round(x - size / 2), round(y - size / 2), size, size))
    painter.restore()


def pick_color(surface: QImage, x, y):
    w, h = surface.width(), surface.height()
    if not (0 <= x < w and 0 <= y < h):
        return None
    c = surface.pixelColor(int(x), int(y))
    return (c.red(), c.green(), c.blue(), c.alpha())
