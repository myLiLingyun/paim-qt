# SPDX-License-Identifier: GPL-3.0-or-later
"""Document, selection, history and raster file I/O for the Paint clone.

The GTK original used Cairo image surfaces.  This Qt port stores every
surface as a straight-alpha ``QImage`` (``Format_ARGB32``) so pixel access
is endian-independent and drawings composite exactly like Paint's.
"""
from __future__ import annotations

import copy
import io
import math
import os
from dataclasses import dataclass

from PyQt6.QtCore import QBuffer, QIODevice, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import (QColor, QImage, QImageReader, QImageWriter, QPainter,
                         QPainterPath, QPolygonF)

ARGB = QImage.Format.Format_ARGB32


# ----------------------------------------------------------------------
# Colour helpers
def _qcolor(color) -> QColor:
    """Accept QColor, '#rrggbb' or an RGB/RGBA tuple (ints 0-255 or floats 0-1)."""
    if isinstance(color, QColor):
        return QColor(color)
    if isinstance(color, str):
        return QColor(color)
    if color is None:
        return QColor(0, 0, 0, 255)
    values = list(color)
    if len(values) < 3:
        return QColor(0, 0, 0, 255)
    rgb = [float(v) for v in values[:3]]
    if max(rgb) <= 1.0:
        rgb = [round(v * 255) for v in rgb]
    rgb = [max(0, min(255, int(round(v)))) for v in rgb]
    if len(values) >= 4:
        alpha = values[3]
        if isinstance(alpha, float) and alpha <= 1.0:
            alpha = round(alpha * 255)
        alpha = max(0, min(255, int(round(float(alpha)))))
    else:
        alpha = 255
    return QColor(rgb[0], rgb[1], rgb[2], alpha)


def normalize_rgba(color):
    """Return an RGBA tuple with float components in the 0..1 range."""
    c = _qcolor(color)
    return (c.redF(), c.greenF(), c.blueF(), c.alphaF())


def is_transparent_color(color) -> bool:
    return _qcolor(color).alpha() <= 0


def rgb_to_float(rgb):
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def rgba_to_hex(rgba) -> str:
    c = _qcolor(rgba)
    return "#%02X%02X%02X" % (c.red(), c.green(), c.blue())


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    c = QColor(value.strip())
    if not c.isValid():
        value = value.strip().lstrip('#')
        if len(value) == 3:
            value = ''.join(ch * 2 for ch in value)
        if len(value) != 6:
            raise ValueError(value)
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    return (c.red(), c.green(), c.blue())


# ----------------------------------------------------------------------
# Image helpers
def _copy_image(image: QImage) -> QImage:
    return image.copy()


def new_image(width: int, height: int, color=QColor(255, 255, 255, 255)) -> QImage:
    image = QImage(max(1, int(width)), max(1, int(height)), ARGB)
    image.fill(_qcolor(color))
    return image


# Compatibility alias: the old code called these "surfaces".
new_surface = new_image
_copy_surface = _copy_image


def clear_image(image: QImage, color=QColor(255, 255, 255, 255)) -> None:
    image.fill(_qcolor(color))


clear_surface = clear_image


def _bytes_per_line(image: QImage) -> int:
    return image.bytesPerLine()


def _buffer(image: QImage):
    """Return a writable memoryview over *image* plus its bytes-per-line."""
    ptr = image.bits()
    ptr.setsize(image.sizeInBytes())
    return memoryview(ptr), image.bytesPerLine()


def image_has_transparency(image: QImage, threshold: int = 254) -> bool:
    """Return True when any pixel in *image* has alpha below *threshold*."""
    if not image.hasAlphaChannel():
        return False
    if image.format() != ARGB:
        image = image.convertToFormat(ARGB)
    data, stride = _buffer(image)
    width, height = image.width(), image.height()
    if stride == width * 4:
        any_low = any(data[i] <= threshold for i in range(3, len(data), 4))
        return any_low
    for y in range(height):
        off = y * stride + 3
        end = off + width * 4
        while off < end:
            if data[off] <= threshold:
                return True
            off += 4
    return False


surface_has_transparency = image_has_transparency
surface_has_alpha = image_has_transparency


def pil_has_transparency(im) -> bool:
    """Return True if a Pillow image has an alpha channel/key with real alpha."""
    if im.mode in ('RGBA', 'LA', 'PA') or 'A' in im.getbands():
        try:
            alpha = im.getchannel('A')
            low, _high = alpha.getextrema()
            return low < 255
        except Exception:
            return True
    info = getattr(im, 'info', {}) or {}
    if info.get('transparency') is not None:
        return im.mode in ('P', 'L', 'RGB', '1')
    return False


def _flatten_image(image: QImage, color=QColor(255, 255, 255)) -> QImage:
    """Composite *image* over an opaque colour and return an opaque image."""
    color = QColor(color)
    color.setAlpha(255)
    out = QImage(image.width(), image.height(), ARGB)
    out.fill(color)
    p = QPainter(out)
    p.drawImage(0, 0, image)
    p.end()
    return out


def _to_pil(image: QImage, *, with_alpha=False):
    """Convert a QImage to a Pillow RGBA/RGB image."""
    from PIL import Image as PILImage
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = rgba.constBits()
    ptr.setsize(rgba.sizeInBytes())
    raw = bytes(ptr)
    im = PILImage.frombuffer('RGBA', (rgba.width(), rgba.height()), raw, 'raw',
                             'RGBA', rgba.bytesPerLine(), 1).copy()
    if with_alpha:
        return im
    background = PILImage.new('RGBA', im.size, (255, 255, 255, 255))
    return PILImage.alpha_composite(background, im).convert('RGB')


def _from_pil(im) -> QImage:
    from PIL import Image as PILImage
    im = im.convert('RGBA')
    raw = im.tobytes()
    image = QImage(raw, im.width, im.height, QImage.Format.Format_RGBA8888).copy()
    return image.convertToFormat(ARGB)


def surface_to_pil(image: QImage, *, with_alpha=False):
    return _to_pil(image, with_alpha=with_alpha)


def pil_to_surface(im) -> QImage:
    return _from_pil(im)


def png_bytes_to_surface(data: bytes) -> QImage:
    image = QImage.fromData(data)
    if image.isNull():
        raise ValueError('unrecognised image data')
    return image.convertToFormat(ARGB)


def surface_to_png_bytes(image: QImage, with_alpha=True) -> bytes:
    img = image if with_alpha else _flatten_image(image, QColor(255, 255, 255))
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    data = bytes(buf.data())
    buf.close()
    return data


def _mask_from_path(width: int, height: int, path: QPainterPath,
                    inverted: bool = False) -> QImage:
    mask = QImage(max(1, int(width)), max(1, int(height)), ARGB)
    mask.fill(QColor(0, 0, 0, 0))
    p = QPainter(mask)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 255))
    p.drawPath(path)
    p.end()
    if inverted:
        data, stride = _buffer(mask)
        for y in range(mask.height()):
            off = y * stride
            end = off + mask.width() * 4
            while off < end:
                data[off] = 255
                data[off + 1] = 255
                data[off + 2] = 255
                data[off + 3] = 255 - data[off + 3]
                off += 4
    return mask


@dataclass
class Selection:
    """A selection region in image coordinates.

    Rectangular selections use *rect* only.  Free-form selections carry a
    polygon path.  ``inverted`` means the selected region is the image minus
    the shape.  ``floating`` is true while the selected pixels are lifted.
    """
    x: int
    y: int
    w: int
    h: int
    polygon: list[tuple[float, float]] | None = None
    inverted: bool = False
    mask: QImage | None = None
    floating: QImage | None = None
    floating_origin: tuple[int, int] | None = None

    @property
    def rect(self):
        return (int(self.x), int(self.y), int(self.w), int(self.h))

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h

    @property
    def empty(self):
        return self.w <= 0 or self.h <= 0

    def contains(self, x: float, y: float) -> bool:
        x, y = float(x), float(y)
        if self.floating is not None and self.floating_origin is not None:
            bx, by = self.floating_origin
            bw, bh = self.floating.width(), self.floating.height()
        else:
            bx, by = self.x, self.y
            bw, bh = self.w, self.h
        in_bounds = bx <= x < bx + bw and by <= y < by + bh
        if self.polygon:
            if self.floating is not None and self.floating_origin is not None:
                dx, dy = bx - self.x, by - self.y
                poly = [(px + dx, py + dy) for px, py in self.polygon]
            else:
                poly = self.polygon
            inside_shape = _point_in_polygon(x, y, poly) and in_bounds
        else:
            inside_shape = in_bounds
        if not self.inverted and not in_bounds:
            return False
        return (not inside_shape) if self.inverted else inside_shape

    def clone(self) -> 'Selection':
        return copy.copy(self)

    def mask_surface(self, width: int, height: int) -> QImage:
        """Return an ARGB mask covering the whole image."""
        path = QPainterPath()
        if self.polygon:
            pts = [QPointF(px, py) for px, py in self.polygon]
            if pts:
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                path.closeSubpath()
        else:
            path.addRect(QRectF(self.x, self.y, self.w, self.h))
        return _mask_from_path(width, height, path, self.inverted)

    # New Qt-flavoured name.
    mask_image = mask_surface


def _point_in_polygon(x, y, points):
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


@dataclass
class Snapshot:
    surface: QImage
    width: int
    height: int
    selection: Selection | None
    label: str = ''
    background: QColor = None


class Document:
    """A Paint document with undo/redo and selection operations."""

    def __init__(self, width=768, height=432, *, background=QColor(255, 255, 255, 255),
                 dpi=96, transparent=False):
        self.width = int(width)
        self.height = int(height)
        self.dpi = dpi
        self.background = _qcolor(background)
        if transparent:
            self.background.setAlpha(0)
        self.surface = new_image(self.width, self.height, self.background)
        self.filename: str | None = None
        self.format: str | None = None
        self.dirty = False
        self.selection: Selection | None = None
        self.undo_stack: list[Snapshot] = []
        self.redo_stack: list[Snapshot] = []
        self.max_undo = 50
        self.metadata: dict = {'transparent': self.transparent}
        self.palette: list[str] = []

    # ------------------------------------------------------------------
    # Transparency state
    @property
    def transparent(self) -> bool:
        """Whether new/cleared pixels use a transparent background."""
        return self.background.alpha() <= 0

    @transparent.setter
    def transparent(self, value: bool) -> None:
        value = bool(value)
        if hasattr(self, 'surface'):
            if value != self.transparent:
                self.set_transparency(value)
            return
        self.background.setAlpha(0 if value else 255)

    @property
    def is_transparent(self) -> bool:
        return self.transparent

    @is_transparent.setter
    def is_transparent(self, value: bool) -> None:
        self.transparent = value

    @property
    def transparent_background(self) -> bool:
        return self.transparent

    @transparent_background.setter
    def transparent_background(self, value: bool) -> None:
        self.transparent = value

    @property
    def has_alpha(self) -> bool:
        return self.transparent or image_has_transparency(self.surface)

    @property
    def has_transparency(self) -> bool:
        return self.has_alpha

    # ------------------------------------------------------------------
    # History
    def snapshot(self, label='') -> Snapshot:
        return Snapshot(_copy_image(self.surface), self.width, self.height,
                        self.selection.clone() if self.selection else None, label,
                        QColor(self.background))

    def push_undo(self, label='') -> None:
        self.undo_stack.append(self.snapshot(label))
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.dirty = True

    def can_undo(self):
        return bool(self.undo_stack)

    def can_redo(self):
        return bool(self.redo_stack)

    def undo(self):
        if not self.undo_stack:
            return False
        current = self.snapshot('redo')
        snap = self.undo_stack.pop()
        self._restore(snap)
        self.redo_stack.append(current)
        self.dirty = True
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        current = self.snapshot('undo')
        snap = self.redo_stack.pop()
        self._restore(snap)
        self.undo_stack.append(current)
        self.dirty = True
        return True

    def _restore(self, snap: Snapshot):
        self.surface = _copy_image(snap.surface)
        self.width, self.height = snap.width, snap.height
        self.selection = snap.selection.clone() if snap.selection else None
        self.background = QColor(snap.background)
        self.metadata['transparent'] = self.transparent

    # ------------------------------------------------------------------
    # Transparency operations
    def _make_color_transparent(self, color, tolerance: int = 0) -> None:
        """Turn opaque pixels matching *color* into fully transparent pixels."""
        target = _qcolor(color)
        tr, tg, tb = target.red(), target.green(), target.blue()
        data, stride = _buffer(self.surface)
        for y in range(self.height):
            off = y * stride
            end = off + self.width * 4
            while off < end:
                if data[off + 3] > 0:
                    r, g, b = data[off + 2], data[off + 1], data[off]
                    if (abs(r - tr) <= tolerance and abs(g - tg) <= tolerance
                            and abs(b - tb) <= tolerance):
                        data[off] = data[off + 1] = data[off + 2] = data[off + 3] = 0
                off += 4

    def flatten_alpha(self, color=None) -> None:
        """Composite the image over an opaque background colour."""
        if color is None:
            color = QColor(self.background)
        color = _qcolor(color)
        if color.alpha() <= 0:
            return
        color.setAlpha(255)
        out = QImage(self.width, self.height, ARGB)
        out.fill(color)
        p = QPainter(out)
        p.drawImage(0, 0, self.surface)
        p.end()
        self.surface = out
        self.dirty = True

    def set_transparency(self, enabled: bool, *, background=None, clear=True,
                         label='透明背景') -> bool:
        enabled = bool(enabled)
        if enabled == self.transparent:
            return False
        self.push_undo(label)
        if enabled:
            old = QColor(self.background)
            old.setAlpha(255)
            self.background = QColor(old.red(), old.green(), old.blue(), 0)
            if clear:
                self._make_color_transparent(old)
        else:
            self.background.setAlpha(255)
            if background is not None:
                self.background = _qcolor(background)
                self.background.setAlpha(255)
            self.flatten_alpha(self.background)
        self.metadata['transparent'] = self.transparent
        self.dirty = True
        return True

    # ------------------------------------------------------------------
    # Geometry and whole-image operations
    def replace_surface(self, surface: QImage, *, push=True, label=''):
        if push:
            self.push_undo(label or '替换图像')
        self.surface = surface.convertToFormat(ARGB)
        self.width = self.surface.width()
        self.height = self.surface.height()
        self.dirty = True

    def resize(self, width, height, *, interpolation='good', label='调整大小'):
        width, height = max(1, int(round(width))), max(1, int(round(height)))
        if width == self.width and height == self.height:
            return False
        self.push_undo(label)
        if self.selection:
            self._resize_selection(width, height, interpolation)
        else:
            mode = (Qt.TransformationMode.FastTransformation if interpolation == 'nearest'
                    else Qt.TransformationMode.SmoothTransformation)
            self.surface = self.surface.scaled(width, height,
                                               Qt.AspectRatioMode.IgnoreAspectRatio, mode)
            self.width, self.height = width, height
        self.dirty = True
        return True

    def _resize_selection(self, new_w, new_h, interpolation):
        sel = self.selection
        if not sel:
            return
        sx, sy, sw, sh = sel.rect
        if sw <= 0 or sh <= 0:
            return
        full = new_image(new_w, new_h, self.background)
        p = QPainter(full)
        p.drawImage(0, 0, self.surface)
        piece = self._selected_piece(sel)
        p.setClipRect(QRect(sx, sy, max(1, int(new_w)), max(1, int(new_h))))
        p.fillRect(QRect(sx, sy, sw, sh), self.background)
        mode = (Qt.TransformationMode.FastTransformation if interpolation == 'nearest'
                else Qt.TransformationMode.SmoothTransformation)
        scaled = piece.scaled(max(1, int(new_w)), max(1, int(new_h)),
                              Qt.AspectRatioMode.IgnoreAspectRatio, mode)
        p.drawImage(sx, sy, scaled)
        p.end()
        self.surface = full
        self.width, self.height = new_w, new_h
        self.selection = Selection(sx, sy, max(1, int(new_w)), max(1, int(new_h)))

    def _selected_piece(self, sel: Selection) -> QImage:
        x, y, w, h = sel.rect
        x = max(0, x)
        y = max(0, y)
        w = min(w, self.width - x)
        h = min(h, self.height - y)
        piece = self.surface.copy(x, y, max(1, w), max(1, h))
        if sel.polygon or sel.inverted:
            mask = sel.mask_image(self.width, self.height).copy(x, y, piece.width(), piece.height())
            p = QPainter(piece)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            p.drawImage(0, 0, mask)
            p.end()
        return piece

    def resize_canvas(self, width, height, *, label='属性'):
        width, height = max(1, int(width)), max(1, int(height))
        if width == self.width and height == self.height:
            return False
        self.push_undo(label)
        out = new_image(width, height, self.background)
        p = QPainter(out)
        p.drawImage(0, 0, self.surface)
        p.end()
        self.surface = out
        self.width, self.height = width, height
        self.selection = None
        self.dirty = True
        return True

    def crop(self):
        sel = self.selection
        if not sel or sel.empty:
            return False
        x, y, w, h = sel.rect
        x = max(0, x)
        y = max(0, y)
        w = min(w, self.width - x)
        h = min(h, self.height - y)
        if w <= 0 or h <= 0:
            return False
        self.push_undo('裁剪')
        self.surface = self.surface.copy(x, y, w, h)
        self.width, self.height = w, h
        self.selection = None
        self.dirty = True
        return True

    def rotate(self, mode: str):
        """mode: right, left, 180, flip_v, flip_h. Applies to selection if present."""
        if mode not in ('right', 'left', '180', 'flip_v', 'flip_h'):
            raise ValueError(mode)
        self.push_undo('旋转或翻转')
        if self.selection and not self.selection.empty:
            sel = self.selection
            x, y, w, h = sel.rect
            x, y = max(0, x), max(0, y)
            w, h = min(w, self.width - x), min(h, self.height - y)
            # Keep the GTK behaviour: a free-form / inverted selection is
            # rotated through its mask, not as its whole bounding rectangle.
            piece = self._selected_piece(sel)
            transformed = self._transform_image(piece, mode)
            p = QPainter(self.surface)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(QRect(x, y, w, h), self.background)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.drawImage(x, y, transformed)
            p.end()
            self.selection = Selection(x, y, transformed.width(), transformed.height())
        else:
            self.surface = self._transform_image(self.surface, mode)
            self.width, self.height = self.surface.width(), self.surface.height()
            self.selection = None
        self.dirty = True

    @staticmethod
    def _transform_image(src: QImage, mode: str) -> QImage:
        transform = __import__('PyQt6.QtGui', fromlist=['QTransform']).QTransform()
        if mode == 'right':
            transform.rotate(90)
        elif mode == 'left':
            transform.rotate(-90)
        elif mode == '180':
            transform.rotate(180)
        elif mode == 'flip_v':
            transform.scale(1, -1)
        elif mode == 'flip_h':
            transform.scale(-1, 1)
        return src.transformed(transform, Qt.TransformationMode.SmoothTransformation)

    def skew(self, horizontal=0.0, vertical=0.0, *, label='倾斜'):
        if abs(horizontal) < 1e-9 and abs(vertical) < 1e-9:
            return False
        self.push_undo(label)
        from PyQt6.QtGui import QTransform
        hx = math.tan(math.radians(horizontal))
        vy = math.tan(math.radians(vertical))
        extra_w = abs(hx) * self.height
        extra_h = abs(vy) * self.width
        nw = int(math.ceil(self.width + extra_w))
        nh = int(math.ceil(self.height + extra_h))
        out = new_image(nw, nh, self.background if not self.transparent
                        else QColor(0, 0, 0, 0))
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if hx >= 0:
            p.translate(0, extra_h if vy >= 0 else 0)
        else:
            p.translate(extra_w, extra_h if vy >= 0 else 0)
        p.setTransform(QTransform(1, vy, hx, 1, 0, 0), True)
        p.drawImage(0, 0, self.surface)
        p.end()
        self.surface = out
        self.width, self.height = nw, nh
        self.selection = None
        self.dirty = True
        return True

    def invert_colors(self):
        self.push_undo('反色')
        data, stride = _buffer(self.surface)
        for y in range(self.height):
            off = y * stride
            end = off + self.width * 4
            while off < end:
                data[off] = 255 - data[off]
                data[off + 1] = 255 - data[off + 1]
                data[off + 2] = 255 - data[off + 2]
                off += 4
        self.dirty = True

    def clear_image(self, color=None):
        self.push_undo('清除图像')
        self.surface.fill(_qcolor(self.background if color is None else color))
        self.selection = None
        self.dirty = True

    def flatten_selection(self):
        """Commit a floating selection into the image."""
        sel = self.selection
        if not sel or sel.floating is None or sel.floating_origin is None:
            return
        x, y = sel.floating_origin
        p = QPainter(self.surface)
        if sel.polygon or sel.inverted:
            layer = QImage(self.surface.size(), ARGB)
            layer.fill(QColor(0, 0, 0, 0))
            lp = QPainter(layer)
            lp.drawImage(x, y, sel.floating)
            lp.end()
            mask = sel.mask_image(self.width, self.height)
            lp = QPainter(layer)
            lp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            lp.drawImage(0, 0, mask)
            lp.end()
            p.drawImage(0, 0, layer)
        else:
            p.drawImage(x, y, sel.floating)
        p.end()
        sel.x, sel.y = int(round(x)), int(round(y))
        sel.w, sel.h = sel.floating.width(), sel.floating.height()
        sel.floating = None
        sel.floating_origin = None

    def get_selection_surface(self, include_alpha=True):
        sel = self.selection
        if not sel or sel.empty:
            return None
        x, y, w, h = sel.rect
        x = max(0, x)
        y = max(0, y)
        w = min(w, self.width - x)
        h = min(h, self.height - y)
        if w <= 0 or h <= 0:
            return None
        piece = self.surface.copy(x, y, w, h)
        if sel.inverted or sel.polygon:
            mask = sel.mask_image(self.width, self.height).copy(x, y, w, h)
            p = QPainter(piece)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            p.drawImage(0, 0, mask)
            p.end()
        return piece

    def delete_selection(self, background=None):
        sel = self.selection
        if not sel:
            return False
        if sel.floating is not None:
            sel.floating = None
            sel.floating_origin = None
            self.selection = None
            self.dirty = True
            return True
        if background is None:
            background = self.background
        background = _qcolor(background)
        self.push_undo('删除')
        p = QPainter(self.surface)
        if sel.inverted or sel.polygon:
            mask = sel.mask_image(self.width, self.height)
            if background.alpha() <= 0:
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
                p.drawImage(0, 0, mask)
            else:
                layer = QImage(self.width, self.height, ARGB)
                layer.fill(background)
                lp = QPainter(layer)
                lp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                lp.drawImage(0, 0, mask)
                lp.end()
                p.drawImage(0, 0, layer)
        else:
            x, y, w, h = sel.rect
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(QRect(x, y, w, h), background)
        p.end()
        self.selection = None
        self.dirty = True
        return True

    def select_all(self):
        self.flatten_selection()
        self.selection = Selection(0, 0, self.width, self.height)
        return self.selection

    def invert_selection(self):
        if not self.selection:
            self.select_all()
            return
        self.selection.inverted = not self.selection.inverted

    def lift_selection(self):
        """Lift selected pixels into a floating surface and clear the source."""
        sel = self.selection
        if not sel or sel.empty:
            return None
        if sel.floating is not None:
            return sel.floating
        x, y, w, h = sel.rect
        x, y = max(0, x), max(0, y)
        w, h = min(w, self.width - x), min(h, self.height - y)
        if w <= 0 or h <= 0:
            return None
        surface = self.get_selection_surface()
        if surface is None:
            return None
        self.push_undo('移动选区')
        p = QPainter(self.surface)
        if sel.inverted or sel.polygon:
            mask = sel.mask_image(self.width, self.height)
            if self.background.alpha() <= 0:
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
                p.drawImage(0, 0, mask)
            else:
                layer = QImage(self.width, self.height, ARGB)
                layer.fill(self.background)
                lp = QPainter(layer)
                lp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                lp.drawImage(0, 0, mask)
                lp.end()
                p.drawImage(0, 0, layer)
        else:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(QRect(x, y, w, h), self.background)
        p.end()
        sel.floating = surface
        sel.floating_origin = (x, y)
        return surface

    # ------------------------------------------------------------------
    # File I/O
    @classmethod
    def open(cls, path: str) -> 'Document':
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        image = reader.read()
        dpi = 96
        if image.isNull():
            image = _open_with_pillow(path)
            if image is None:
                raise ValueError(reader.errorString() or f'cannot open {path}')
        image = image.convertToFormat(ARGB)
        transparent = image_has_transparency(image)
        background = QColor(255, 255, 255, 0 if transparent else 255)
        doc = cls(image.width(), image.height(), background=background)
        doc.surface = image
        doc.filename = path
        doc.format = os.path.splitext(path)[1].lower().lstrip('.')
        doc.dirty = False
        doc.selection = None
        doc.undo_stack.clear()
        doc.redo_stack.clear()
        try:
            dpi = image.dotsPerMeterX() * 0.0254
        except Exception:
            dpi = 96
        if not dpi or dpi <= 1:
            dpi = 96
        doc.metadata['dpi'] = dpi
        doc.metadata['transparent'] = transparent
        doc.dpi = int(round(dpi))
        return doc

    def to_pil(self, *, with_alpha=False):
        return _to_pil(self.surface, with_alpha=with_alpha)

    def save(self, path: str | None = None, fmt: str | None = None, **options) -> str:
        path = path or self.filename
        if not path:
            raise ValueError('没有文件名')
        fmt = (fmt or os.path.splitext(path)[1].lstrip('.') or self.format or 'png').lower()
        if fmt == 'jpeg':
            fmt = 'jpg'
        alpha_formats = ('png', 'gif', 'webp', 'tif', 'tiff')
        with_alpha = bool(options.get('with_alpha', fmt in alpha_formats))
        quality = int(options.get('quality', 92))
        if fmt in ('bmp', 'dib', 'gif', 'webp') or (fmt == 'jpg' and self.has_alpha):
            _save_with_pillow(self, path, fmt, options)
        else:
            image = self.surface
            if not with_alpha:
                image = _flatten_image(image, options.get('background', QColor(255, 255, 255)))
            if fmt == 'png':
                out = image.copy()
                dots = int(round(self.dpi / 0.0254))
                out.setDotsPerMeterX(dots)
                out.setDotsPerMeterY(dots)
            else:
                out = image
            writer = QImageWriter(path)
            writer.setFormat(fmt.encode())
            if fmt in ('jpg', 'webp'):
                writer.setQuality(quality)
            if not writer.write(out):
                _save_with_pillow(self, path, fmt, options)
        self.filename = path
        self.format = fmt
        self.dirty = False
        return path

    def duplicate(self) -> 'Document':
        doc = Document(self.width, self.height, background=self.background)
        doc.surface = _copy_image(self.surface)
        doc.filename = self.filename
        doc.format = self.format
        doc.dirty = self.dirty
        doc.selection = self.selection.clone() if self.selection else None
        doc.dpi = self.dpi
        return doc


# ----------------------------------------------------------------------
# File format helpers
def _open_with_pillow(path):
    try:
        from PIL import Image, ImageOps
        with Image.open(path) as im:
            im.load()
            im = ImageOps.exif_transpose(im)
            return _from_pil(im)
    except Exception:
        return None


def _save_with_pillow(doc: Document, path: str, fmt: str, options: dict) -> None:
    """Pillow fallback for GIF, DIB and sub-24-bit BMP files."""
    from PIL import Image, ImageOps

    with_alpha = bool(options.get('with_alpha', fmt in ('png', 'gif', 'webp', 'tif', 'tiff')))
    img = _to_pil(doc.surface, with_alpha=True)
    background = options.get('background', (255, 255, 255))
    if not with_alpha and img.mode == 'RGBA':
        bg = _qcolor(background)
        bg.setAlpha(255)
        canvas = Image.new('RGBA', img.size, (bg.red(), bg.green(), bg.blue(), 255))
        img = Image.alpha_composite(canvas, img).convert('RGB')
    if fmt == 'jpg':
        if img.mode == 'RGBA':
            bg = _qcolor(background)
            bg.setAlpha(255)
            canvas = Image.new('RGBA', img.size, (bg.red(), bg.green(), bg.blue(), 255))
            img = Image.alpha_composite(canvas, img).convert('RGB')
        img.save(path, 'JPEG', quality=options.get('quality', 92))
    elif fmt in ('bmp', 'dib'):
        bits = int(options.get('bits', 24))
        if img.mode == 'RGBA':
            bg = _qcolor(background)
            bg.setAlpha(255)
            canvas = Image.new('RGBA', img.size, (bg.red(), bg.green(), bg.blue(), 255))
            img = Image.alpha_composite(canvas, img).convert('RGB')
        if bits == 1:
            img = img.convert('1')
        elif bits == 4:
            img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=16)
        elif bits == 8:
            img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)
        else:
            img = img.convert('RGB')
        img.save(path, 'BMP')
    elif fmt == 'gif':
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        _save_gif_with_alpha(img, path)
    elif fmt == 'png':
        if not with_alpha and img.mode == 'RGBA':
            img = img.convert('RGB')
        img.save(path, 'PNG', dpi=(doc.dpi, doc.dpi))
    elif fmt == 'webp':
        img.save(path, 'WEBP', lossless=bool(options.get('lossless', True)),
                 quality=options.get('quality', 95))
    elif fmt in ('tif', 'tiff'):
        img.save(path, 'TIFF')
    else:
        img.save(path)


def _save_gif_with_alpha(im, path: str) -> None:
    """Save an RGBA image as a GIF, preserving binary transparency."""
    from PIL import Image
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    alpha = im.getchannel('A')
    rgb = im.convert('RGB')
    palette = rgb.convert('P', palette=Image.Palette.ADAPTIVE, colors=255)
    transparent_mask = alpha.point(lambda a: 255 if a < 128 else 0)
    if transparent_mask.getbbox() is None:
        palette.save(path, 'GIF')
        return
    palette.paste(255, mask=transparent_mask)
    palette.info['transparency'] = 255
    palette.save(path, 'GIF', transparency=255)
