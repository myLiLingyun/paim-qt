# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometry for all shapes offered by the Paint shape gallery.

The original GTK/Cairo implementation appended to a Cairo context.  This
Qt port returns a ``QPainterPath`` instead, which keeps the rest of the
drawing code simple and lets the same geometry be used for clipping,
masking and hit testing.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainterPath, QPolygonF

SHAPE_ORDER = [
    'line', 'curve',
    'ellipse', 'rectangle', 'rounded_rectangle', 'triangle', 'right_triangle',
    'diamond', 'pentagon', 'hexagon',
    'arrow_right', 'arrow_left', 'arrow_up', 'arrow_down',
    'star4', 'star5', 'star6',
    'rounded_callout', 'oval_callout', 'cloud_callout',
    'heart', 'lightning',
]

SHAPE_LABELS_ZH = {
    'line': '直线', 'curve': '曲线', 'ellipse': '椭圆形', 'rectangle': '矩形',
    'rounded_rectangle': '圆角矩形', 'triangle': '三角形', 'right_triangle': '直角三角形',
    'diamond': '菱形', 'pentagon': '五边形', 'hexagon': '六边形',
    'arrow_right': '向右的箭头', 'arrow_left': '向左的箭头',
    'arrow_up': '向上的箭头', 'arrow_down': '向下的箭头',
    'star4': '四角星形', 'star5': '五角星形', 'star6': '六角星形',
    'rounded_callout': '圆角矩形标注', 'oval_callout': '椭圆形插图编号',
    'cloud_callout': '云形插图编号', 'heart': '心形', 'lightning': '闪电形',
}
SHAPE_LABELS_EN = {
    'line': 'Line', 'curve': 'Curve', 'ellipse': 'Ellipse', 'rectangle': 'Rectangle',
    'rounded_rectangle': 'Rounded rectangle', 'triangle': 'Triangle', 'right_triangle': 'Right triangle',
    'diamond': 'Diamond', 'pentagon': 'Pentagon', 'hexagon': 'Hexagon',
    'arrow_right': 'Right arrow', 'arrow_left': 'Left arrow',
    'arrow_up': 'Up arrow', 'arrow_down': 'Down arrow',
    'star4': 'Four-point star', 'star5': 'Five-point star', 'star6': 'Six-point star',
    'rounded_callout': 'Rounded rectangular callout', 'oval_callout': 'Oval callout',
    'cloud_callout': 'Cloud callout', 'heart': 'Heart', 'lightning': 'Lightning',
}

# Gallery positions: the reference ribbon has three rows of six slots.
GALLERY_ROWS = [
    ['line', 'curve', 'ellipse', 'rectangle', 'rounded_rectangle', 'triangle'],
    ['right_triangle', 'diamond', 'pentagon', 'hexagon', 'arrow_right', 'arrow_left'],
    ['arrow_up', 'arrow_down', 'star4', 'star5', 'star6', 'rounded_callout'],
    ['oval_callout', 'cloud_callout', 'heart', 'lightning'],
]


def _polygon_path(points, close=True) -> QPainterPath:
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(QPointF(*points[0]))
    for p in points[1:]:
        path.lineTo(QPointF(*p))
    if close:
        path.closeSubpath()
    return path


def _regular_polygon(cx, cy, rx, ry, n, start=-math.pi / 2, rotate=0.0):
    pts = []
    for i in range(n):
        a = start + rotate + i * 2 * math.pi / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def _star(cx, cy, rx, ry, n, inner=0.38):
    pts = []
    for i in range(n * 2):
        a = -math.pi / 2 + i * math.pi / n
        r = 1.0 if i % 2 == 0 else inner
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    return pts


def _rounded_rect_path(x, y, w, h, r) -> QPainterPath:
    path = QPainterPath()
    if r <= 0:
        path.addRect(QRectF(x, y, w, h))
        return path
    path.addRoundedRect(QRectF(x, y, w, h), r, r)
    return path


def _cloud_path(x, y, w, h) -> QPainterPath:
    # A simple Paint-like cloud from overlapping circles.  All circles are
    # subpaths so a single fill/stroke handles the union sensibly.
    circles = [
        (x + w * 0.20, y + h * 0.62, w * 0.18, h * 0.28),
        (x + w * 0.33, y + h * 0.34, w * 0.20, h * 0.30),
        (x + w * 0.53, y + h * 0.23, w * 0.22, h * 0.33),
        (x + w * 0.73, y + h * 0.38, w * 0.19, h * 0.30),
        (x + w * 0.80, y + h * 0.63, w * 0.18, h * 0.27),
        (x + w * 0.50, y + h * 0.66, w * 0.30, h * 0.31),
    ]
    path = QPainterPath()
    for cx, cy, rx, ry in circles:
        path.addEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))
    return path


def build_shape_path(shape: str, x: float, y: float, w: float, h: float,
                     *, corner_radius: float | None = None) -> QPainterPath:
    """Return the geometry of *shape* inside the given bounds."""
    x, y, w, h = float(x), float(y), float(w), float(h)
    path = QPainterPath()
    if w == 0 or h == 0:
        return path
    if w < 0:
        x += w
        w = -w
    if h < 0:
        y += h
        h = -h
    cx, cy = x + w / 2, y + h / 2
    if shape == 'ellipse':
        path.addEllipse(QRectF(x, y, w, h))
    elif shape == 'rectangle':
        path.addRect(QRectF(x, y, w, h))
    elif shape == 'rounded_rectangle':
        r = min(corner_radius if corner_radius is not None else min(w, h) * 0.18,
                w / 2, h / 2)
        path = _rounded_rect_path(x, y, w, h, r)
    elif shape == 'triangle':
        path = _polygon_path([(cx, y), (x + w, y + h), (x, y + h)])
    elif shape == 'right_triangle':
        path = _polygon_path([(x, y), (x, y + h), (x + w, y + h)])
    elif shape == 'diamond':
        path = _polygon_path([(cx, y), (x + w, cy), (cx, y + h), (x, cy)])
    elif shape == 'pentagon':
        path = _polygon_path(_regular_polygon(cx, cy, w / 2, h / 2, 5))
    elif shape == 'hexagon':
        path = _polygon_path([(x + w * 0.25, y), (x + w * 0.75, y), (x + w, cy),
                              (x + w * 0.75, y + h), (x + w * 0.25, y + h), (x, cy)])
    elif shape in ('arrow_right', 'arrow_left', 'arrow_up', 'arrow_down'):
        if shape in ('arrow_right', 'arrow_left'):
            shaft = h * 0.28
            head_len = min(w * 0.38, h * 0.75)
            if shape == 'arrow_right':
                pts = [(x, cy - shaft), (x + w - head_len, cy - shaft),
                       (x + w - head_len, y), (x + w, cy),
                       (x + w - head_len, y + h), (x + w - head_len, cy + shaft),
                       (x, cy + shaft)]
            else:
                pts = [(x + w, cy - shaft), (x + head_len, cy - shaft),
                       (x + head_len, y), (x, cy), (x + head_len, y + h),
                       (x + head_len, cy + shaft), (x + w, cy + shaft)]
        else:
            shaft = w * 0.28
            head_len = min(h * 0.38, w * 0.75)
            if shape == 'arrow_down':
                pts = [(cx - shaft, y), (cx - shaft, y + h - head_len),
                       (x, y + h - head_len), (cx, y + h),
                       (x + w, y + h - head_len), (cx + shaft, y + h - head_len),
                       (cx + shaft, y)]
            else:
                pts = [(cx - shaft, y + h), (cx - shaft, y + head_len),
                       (x, y + head_len), (cx, y), (x + w, y + head_len),
                       (cx + shaft, y + head_len), (cx + shaft, y + h)]
        path = _polygon_path(pts)
    elif shape in ('star4', 'star5', 'star6'):
        n = {'star4': 4, 'star5': 5, 'star6': 6}[shape]
        inner = {'star4': 0.32, 'star5': 0.38, 'star6': 0.52}[shape]
        path = _polygon_path(_star(cx, cy, w / 2, h / 2, n, inner))
    elif shape == 'rounded_callout':
        bw = w * 0.78
        bh = h * 0.76
        path = _rounded_rect_path(x + w * 0.22, y, bw, bh, min(bw, bh) * 0.18)
        path.moveTo(x + w * 0.30, y + bh * 0.88)
        path.lineTo(x + w * 0.06, y + h)
        path.lineTo(x + w * 0.44, y + bh * 0.92)
        path.closeSubpath()
    elif shape == 'oval_callout':
        bw, bh = w * 0.78, h * 0.76
        path.addEllipse(QRectF(x + w * 0.22, y, bw, bh))
        path.moveTo(x + w * 0.30, y + bh * 0.88)
        path.lineTo(x + w * 0.06, y + h)
        path.lineTo(x + w * 0.46, y + bh * 0.92)
        path.closeSubpath()
    elif shape == 'cloud_callout':
        bw, bh = w * 0.78, h * 0.76
        path = _cloud_path(x + w * 0.22, y, bw, bh)
        path.moveTo(x + w * 0.34, y + bh * 0.80)
        path.lineTo(x + w * 0.06, y + h)
        path.lineTo(x + w * 0.48, y + bh * 0.84)
        path.closeSubpath()
    elif shape == 'heart':
        path.moveTo(cx, y + h * 0.30)
        path.cubicTo(cx + w * 0.12, y, x + w, y + h * 0.12, x + w * 0.82, y + h * 0.48)
        path.cubicTo(x + w * 0.68, y + h * 0.72, cx + w * 0.18, y + h * 0.82, cx, y + h)
        path.cubicTo(cx - w * 0.18, y + h * 0.82, x + w * 0.32, y + h * 0.72, x + w * 0.18, y + h * 0.48)
        path.cubicTo(x, y + h * 0.12, cx - w * 0.12, y, cx, y + h * 0.30)
        path.closeSubpath()
    elif shape == 'lightning':
        path = _polygon_path([
            (x + w * 0.56, y), (x + w * 0.12, y + h * 0.58),
            (x + w * 0.45, y + h * 0.58), (x + w * 0.30, y + h),
            (x + w * 0.90, y + h * 0.36), (x + w * 0.55, y + h * 0.36),
            (x + w * 0.78, y),
        ])
    else:
        path.addRect(QRectF(x, y, w, h))
    return path


def shape_polygon(shape: str, x: float, y: float, w: float, h: float) -> QPolygonF:
    """Return a polygon approximation, handy for masks and hit testing."""
    return build_shape_path(shape, x, y, w, h).toFillPolygon()


def shape_bounds(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def star_points(cx, cy, r, n=5, start=-math.pi / 2):
    return _star(cx, cy, r, r, n, 0.38)
