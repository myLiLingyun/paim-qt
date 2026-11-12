# SPDX-License-Identifier: GPL-3.0-or-later
"""The interactive canvas widget for the Paint clone (PyQt6)."""
from __future__ import annotations

import math

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import (QBrush, QColor, QFont, QImage, QKeyEvent, QMouseEvent,
                         QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
                         QWheelEvent)
from PyQt6.QtWidgets import QTextEdit, QWidget

from .document import (Document, Selection, _buffer, _copy_image, _qcolor,
                       png_bytes_to_surface, surface_to_png_bytes)
from .raster import (BRUSH_ORDER, DEFAULT_PALETTE, bucket_fill, draw_curve,
                     draw_eraser, draw_freehand, draw_pixel_line, fill_shape,
                     pick_color, stroke_segment)
from .shapes import SHAPE_ORDER, build_shape_path
from .text import draw_text

PAD = 12

_CHECKER_CACHE: dict[tuple[bool, int], QBrush] = {}


def checker_brush(dark: bool = False, cell: int = 8) -> QBrush:
    """A repeating checkerboard brush used behind transparent pixels."""
    key = (bool(dark), int(cell))
    brush = _CHECKER_CACHE.get(key)
    if brush is None:
        cell = max(2, int(cell))
        tile = QPixmap(cell * 2, cell * 2)
        tile.fill(QColor(255, 255, 255) if not dark else QColor(77, 79, 87))
        p = QPainter(tile)
        shade = (QColor(209, 209, 209) if not dark else QColor(56, 59, 66))
        p.fillRect(QRect(0, 0, cell, cell), shade)
        p.fillRect(QRect(cell, cell, cell, cell), shade)
        p.end()
        brush = QBrush(tile)
        _CHECKER_CACHE[key] = brush
    return brush


def _scale_image(image: QImage, w, h) -> QImage:
    w = max(1, int(round(w)))
    h = max(1, int(round(h)))
    return image.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)


class PaintCanvas(QWidget):
    """Canvas, input handling, selection overlay and text editing."""

    def __init__(self, document: Document, *, language='zh', parent=None):
        super().__init__(parent)
        self.doc = document
        self.language = language
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(),
                           self.sizePolicy().verticalPolicy())

        self.zoom = 1.0
        self.dark = False
        self.grid = False
        self.rulers = False
        self.thumbnail = False
        self.tool = 'pencil'
        self.previous_tool = 'pencil'
        self.brush = 'brush'
        self.line_width = 1
        self.outline_style = 'solid'
        self.fill_style = 'solid'
        self.opaque_selection = True
        self.color1 = (0, 0, 0)
        self.color2 = (255, 255, 255)
        self.palette = list(DEFAULT_PALETTE)
        self.text_family = 'Sans'
        self.text_size = 12
        self.text_bold = False
        self.text_italic = False
        self.text_underline = False
        self.text_opaque = False

        # callbacks
        self.on_status = None
        self.on_zoom_changed = None
        self.on_selection_changed = None
        self.on_modified = None
        self.on_pointer = None
        self.on_color_picked = None

        # input state
        self._button = 1
        self._start = (0.0, 0.0)
        self._last = (0.0, 0.0)
        self._points = []
        self._mode = None
        self._preview = None
        self._action_undo_pushed = False
        self._move_origin = None
        self._move_start = None
        self._resize_handle = None
        self._resize_rect0 = None
        self._resize_start = None
        self._resize_base = None
        self._new_selection = None
        self._free_points = []
        self._curve = None
        self._sel_start = (0, 0)
        self._text_editor = None
        self._text_pos = None

        self.setMinimumSize(32, 32)
        self._update_size()
        self.reset_document(document)

    # ------------------------------------------------------------------
    # Setup / sizing
    def reset_document(self, document: Document):
        if self._text_editor is not None:
            self._discard_text()
        self.doc = document
        self._preview = None
        self._mode = None
        self._points = []
        self._curve = None
        self._update_size()
        self.update()
        self._notify_modified()

    def _update_size(self):
        w = self.doc.width * self.zoom + PAD * 2
        h = self.doc.height * self.zoom + PAD * 2
        self.setFixedSize(max(32, int(math.ceil(w))), max(32, int(math.ceil(h))))
        self._sync_text_editor_geometry()
        self.update()

    # ------------------------------------------------------------------
    # Geometry helpers
    def image_origin(self):
        return PAD, PAD

    def view_to_image(self, vx, vy):
        ox, oy = self.image_origin()
        return (vx - ox) / self.zoom, (vy - oy) / self.zoom

    def image_to_view(self, ix, iy):
        ox, oy = self.image_origin()
        return ox + ix * self.zoom, oy + iy * self.zoom

    def _clamp_point(self, x, y):
        return (max(0, min(self.doc.width - 1e-6, x)),
                max(0, min(self.doc.height - 1e-6, y)))

    # ------------------------------------------------------------------
    # Public state
    def set_tool(self, tool):
        if self._text_editor is not None and tool != 'text':
            self._commit_text()
        self.commit_floating()
        self.previous_tool = self.tool
        self.tool = tool
        self._preview = None
        self.update()
        self._update_status()

    def set_brush(self, brush):
        self.brush = brush
        self.set_tool('brush')

    def set_zoom(self, zoom, anchor=None):
        zoom = max(0.1, min(8.0, zoom))
        if abs(zoom - self.zoom) < 1e-9:
            return
        self.zoom = zoom
        self._update_size()
        if self.on_zoom_changed:
            self.on_zoom_changed(zoom)
        self._update_status()

    def zoom_in(self):
        levels = [0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0]
        for z in levels:
            if z > self.zoom + 1e-6:
                self.set_zoom(z)
                return
        self.set_zoom(8.0)

    def zoom_out(self):
        levels = [0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0]
        for z in reversed(levels):
            if z < self.zoom - 1e-6:
                self.set_zoom(z)
                return
        self.set_zoom(0.1)

    def set_colors(self, color1=None, color2=None):
        if color1 is not None:
            c = _qcolor(color1)
            self.color1 = (c.red(), c.green(), c.blue())
        if color2 is not None:
            c = _qcolor(color2)
            self.color2 = (c.red(), c.green(), c.blue())
        self.update()
        if self.on_color_picked:
            self.on_color_picked(self.color1, self.color2)

    def set_palette(self, palette):
        self.palette = list(palette)
        self.update()

    # ------------------------------------------------------------------
    # Status / notifications
    def _update_status(self, vx=None, vy=None):
        if self.on_status is None:
            return
        pos = None
        if vx is not None and vy is not None:
            ix, iy = self.view_to_image(vx, vy)
            if 0 <= ix < self.doc.width and 0 <= iy < self.doc.height:
                pos = (int(ix), int(iy))
        sel = self.doc.selection
        sel_info = None
        if sel and not sel.empty:
            sel_info = sel.rect
        self.on_status(pos, sel_info, self.doc.width, self.doc.height, self.zoom)

    def _emit_pointer(self, point):
        if self.on_pointer:
            self.on_pointer(point)

    def _notify_modified(self):
        if self.on_modified:
            self.on_modified()

    def _notify_selection(self):
        if self.on_selection_changed:
            self.on_selection_changed(self.doc.selection)

    # ------------------------------------------------------------------
    # Painting
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # workspace
        p.fillRect(self.rect(), QColor(24, 27, 32) if self.dark else QColor(168, 184, 204))
        ox, oy = self.image_origin()
        z = self.zoom
        iw = self.doc.width * z
        ih = self.doc.height * z
        # drop shadow / border around the canvas
        p.fillRect(QRectF(ox + 2, oy + 2, iw, ih),
                   QColor(0, 0, 0, 115) if self.dark else QColor(0, 0, 0, 51))
        p.save()
        p.setClipRect(QRectF(ox, oy, iw, ih))
        # checkerboard
        p.fillRect(QRectF(ox, oy, iw, ih), checker_brush(self.dark))
        # image
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, z < 2.0)
        p.drawImage(QRectF(ox, oy, iw, ih), self.doc.surface)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        # floating selection
        sel = self.doc.selection
        if sel and sel.floating is not None and sel.floating_origin is not None:
            fx, fy = sel.floating_origin
            floating = sel.floating
            if not self.opaque_selection:
                floating = self._apply_transparent_selection(floating)
            p.save()
            if sel.polygon:
                path = QPainterPath()
                pts = sel.polygon
                if pts:
                    path.moveTo(QPointF(pts[0][0] - sel.x + fx, pts[0][1] - sel.y + fy))
                    for pt in pts[1:]:
                        path.lineTo(QPointF(pt[0] - sel.x + fx, pt[1] - sel.y + fy))
                    path.closeSubpath()
                    p.setClipPath(path)
            p.drawImage(QRectF(ox + fx * z, oy + fy * z,
                               floating.width() * z, floating.height() * z), floating)
            p.restore()
        p.restore()

        # grid
        if self.grid:
            p.save()
            p.setClipRect(QRectF(ox, oy, iw, ih))
            step = 1 if z >= 4 else (5 if z >= 2 else 10)
            p.setPen(QPen(QColor(166, 184, 209, 71) if self.dark
                          else QColor(51, 77, 115, 64), 0.7))
            x = 0
            while x <= self.doc.width:
                px = ox + x * z
                p.drawLine(QPointF(px + 0.5, oy), QPointF(px + 0.5, oy + ih))
                x += step
            y = 0
            while y <= self.doc.height:
                py = oy + y * z
                p.drawLine(QPointF(ox, py + 0.5), QPointF(ox + iw, py + 0.5))
                y += step
            p.restore()

        # selection outline / handles
        if sel and not sel.empty:
            p.save()
            self._draw_selection(p, sel)
            p.restore()

        # live preview
        if self._preview:
            p.save()
            p.translate(ox, oy)
            p.scale(z, z)
            self._draw_preview(p)
            p.restore()

        # canvas border
        p.setPen(QPen(QColor(140, 153, 173, 166) if self.dark
                      else QColor(26, 31, 41, 140), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(ox + 0.5, oy + 0.5, iw - 1, ih - 1))

        # text editor selection border
        if self._text_editor is not None and self._text_pos:
            tx, ty = self._text_pos
            p.save()
            pen = QPen(QColor(38, 89, 191, 204), 1)
            pen.setDashPattern([4, 3])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(ox + tx * z - 1, oy + ty * z - 1,
                              self._text_editor.width() + 2,
                              self._text_editor.height() + 2))
            p.restore()
        p.end()

    def _draw_selection(self, p: QPainter, sel: Selection):
        ox, oy = self.image_origin()
        z = self.zoom
        x, y, w, h = sel.rect
        if sel.floating is not None and sel.floating_origin is not None:
            x, y = sel.floating_origin
            w, h = sel.floating.width(), sel.floating.height()
        if sel.polygon:
            pts = sel.polygon
            if len(pts) > 1:
                path = QPainterPath()
                path.moveTo(QPointF(ox + pts[0][0] * z, oy + pts[0][1] * z))
                for px, py in pts[1:]:
                    path.lineTo(QPointF(ox + px * z, oy + py * z))
                path.closeSubpath()
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(0, 0, 0, 217), 1, Qt.PenStyle.DashLine))
                p.drawPath(path)
                p.setPen(QPen(QColor(255, 255, 255, 230), 1, Qt.PenStyle.DashLine))
                p.drawPath(path)
                return
        rect = QRectF(ox + x * z - 0.5, oy + y * z - 0.5, w * z + 1, h * z + 1)
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(0, 0, 0, 217), 1)
        pen.setDashPattern([4, 4])
        p.setPen(pen)
        p.drawRect(rect)
        pen = QPen(QColor(255, 255, 255, 230), 1)
        pen.setDashPattern([4, 4])
        pen.setDashOffset(4)
        p.setPen(pen)
        p.drawRect(rect)
        if not sel.polygon and not sel.inverted:
            hs = 5
            corners = [(x, y), (x + w / 2, y), (x + w, y),
                       (x, y + h / 2), (x + w, y + h / 2),
                       (x, y + h), (x + w / 2, y + h), (x + w, y + h)]
            for cx, cy in corners:
                px, py = ox + cx * z, oy + cy * z
                p.fillRect(QRectF(px - hs, py - hs, hs * 2, hs * 2), QColor(255, 255, 255))
                p.setPen(QPen(QColor(38, 38, 38), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(px - hs, py - hs, hs * 2, hs * 2))

    def _draw_preview(self, p: QPainter):
        preview = self._preview
        if not preview:
            return
        kind = preview.get('kind')
        if kind == 'rect_selection':
            x, y, w, h = preview['rect']
            pen = QPen(QColor(0, 0, 0, 204), 1 / self.zoom)
            pen.setDashPattern([4, 3])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(x, y, w, h))
        elif kind == 'free_selection':
            pts = preview['points']
            if len(pts) > 1:
                pen = QPen(QColor(0, 0, 0, 204), 1 / self.zoom)
                pen.setDashPattern([4, 3])
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath(QPointF(*pts[0]))
                for q in pts[1:]:
                    path.lineTo(QPointF(*q))
                p.drawPath(path)
        elif kind == 'shape':
            self._render_shape(p, preview['shape'], preview['x'], preview['y'],
                               preview['w'], preview['h'], preview=True)
        elif kind == 'line':
            p.setPen(QPen(self._stroke_color(), max(0.8, self.line_width),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(*preview['p0']), QPointF(*preview['p1']))
        elif kind == 'curve':
            p0, p1, c1, c2 = preview['p0'], preview['p1'], preview['c1'], preview['c2']
            p.setPen(QPen(self._stroke_color(), max(0.8, self.line_width),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            path = QPainterPath(QPointF(*p0))
            path.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*p1))
            p.drawPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(51, 102, 230, 204))
            for c in (c1, c2):
                p.drawEllipse(QPointF(*c), 3 / self.zoom, 3 / self.zoom)

    def _render_shape(self, p: QPainter, shape, x, y, w, h, preview=False):
        if w == 0 or h == 0:
            return
        fill_shape(p, shape, x, y, w, h, self.fill_style, self._fill_color(),
                   self.outline_style, self._stroke_color(), self.line_width,
                   alpha=0.85 if preview else 1.0)

    def _stroke_color(self):
        return QColor(*self.color1)

    def _fill_color(self):
        return QColor(*self.color2)

    # ------------------------------------------------------------------
    # Mouse / keyboard events
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            super().mousePressEvent(event)
            return
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if self.tool in ('select', 'free_select'):
                self.doc.select_all()
                self._notify_selection()
                self.update()
                return
        pos = event.position()
        self._drag_begin(pos.x(), pos.y(), event.button())
        if self._text_editor is None:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        if self._mode:
            self._drag_update(pos.x(), pos.y())
        ix, iy = self.view_to_image(pos.x(), pos.y())
        self._emit_pointer((int(ix), int(iy)))
        self._update_status(pos.x(), pos.y())
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            pos = event.position()
            self._drag_end(pos.x(), pos.y())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._emit_pointer(None)
        self._update_status()
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta < 0:
                self.zoom_in()
            elif delta > 0:
                self.zoom_out()
            event.accept()
            return
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent):
        if self._handle_key(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def _handle_key(self, event: QKeyEvent) -> bool:
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if key == Qt.Key.Key_Escape:
            if self._text_editor is not None:
                self._discard_text()
            elif self._curve is not None:
                self._curve = None
                self._preview = None
                self.update()
            elif self.doc.selection is not None:
                self.doc.selection = None
                self._notify_selection()
                self.update()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._curve is not None:
                self.finish_curve()
                return True
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.doc.selection is not None:
                self.doc.delete_selection(self._delete_background())
                self._notify_selection()
                self._notify_modified()
                self.update()
                return True
        if (self.doc.selection and self.doc.selection.floating is not None
                and key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down)):
            step = 10 if shift else 1
            sel = self.doc.selection
            ox, oy = sel.floating_origin or (0, 0)
            if key == Qt.Key.Key_Left:
                ox -= step
            if key == Qt.Key.Key_Right:
                ox += step
            if key == Qt.Key.Key_Up:
                oy -= step
            if key == Qt.Key.Key_Down:
                oy += step
            sel.floating_origin = (ox, oy)
            self.update()
            return True
        return False

    def _button_number(self, button):
        return 3 if button == Qt.MouseButton.RightButton else 1

    # ------------------------------------------------------------------
    # Drag handling
    def _drag_begin(self, start_x, start_y, button=Qt.MouseButton.LeftButton):
        self._start = (start_x, start_y)
        self._last = (start_x, start_y)
        self._button = self._button_number(button)
        self._points = []
        self._free_points = []
        self._preview = None
        self._action_undo_pushed = False
        self._new_selection = None
        if self._text_editor is not None and self.tool != 'text':
            self._commit_text()
        ix, iy = self.view_to_image(start_x, start_y)
        if not (0 <= ix <= self.doc.width and 0 <= iy <= self.doc.height):
            self._mode = None
            return
        ix, iy = self._clamp_point(ix, iy)
        sel = self.doc.selection
        if sel and sel.floating is not None:
            inside = sel.contains(ix, iy)
            if not inside or self.tool not in ('select', 'free_select'):
                self.commit_floating()
        self._mode = None
        if self.tool == 'select':
            self._begin_select(ix, iy, freeform=False)
        elif self.tool == 'free_select':
            self._begin_select(ix, iy, freeform=True)
        elif self.tool == 'text':
            self._begin_text(ix, iy)
        elif self.tool == 'magnifier':
            if self._button == 3:
                self.zoom_out()
            else:
                self.zoom_in()
        elif self.tool == 'picker':
            self._pick(ix, iy)
        elif self.tool == 'fill':
            self._do_fill(ix, iy)
        elif self.tool in ('eraser', 'pencil', 'brush'):
            self._begin_stroke(ix, iy)
        elif self.tool in SHAPE_ORDER:
            if self.tool == 'line':
                self._mode = 'line'
                self.doc.push_undo('直线')
                self._preview = {'kind': 'line', 'p0': (ix, iy), 'p1': (ix, iy)}
            elif self.tool == 'curve':
                if self._curve is None:
                    self._mode = 'curve_draw'
                    self.doc.push_undo('曲线')
                    self._preview = {'kind': 'line', 'p0': (ix, iy), 'p1': (ix, iy)}
                else:
                    self._mode = 'curve_adjust'
                    self._curve_adjust_start(ix, iy)
            else:
                self._mode = 'shape'
                self.doc.push_undo(self.tool)
                self._preview = {'kind': 'shape', 'shape': self.tool,
                                 'x': ix, 'y': iy, 'w': 0, 'h': 0}
        self._update_status(start_x, start_y)
        self.update()

    def _drag_update(self, x, y):
        if not self._mode:
            return
        ix, iy = self.view_to_image(x, y)
        ix, iy = self._clamp_point(ix, iy)
        self._last = (x, y)
        if self._mode == 'stroke':
            self._continue_stroke(ix, iy)
        elif self._mode == 'move':
            if self._move_origin is not None:
                dx = ix - self._move_start[0]
                dy = iy - self._move_start[1]
                self.doc.selection.floating_origin = (
                    int(round(self._move_origin[0] + dx)),
                    int(round(self._move_origin[1] + dy)))
                self.update()
        elif self._mode == 'resize_selection':
            self._resize_selection_update(ix, iy)
            self.update()
        elif self._mode == 'select_rect':
            x0, y0 = self._sel_start
            nx, ny = min(x0, ix), min(y0, iy)
            nw, nh = abs(ix - x0), abs(iy - y0)
            self._preview = {'kind': 'rect_selection', 'rect': (nx, ny, nw, nh)}
            self._new_selection = (nx, ny, nw, nh)
            self.update()
        elif self._mode == 'select_free':
            if (not self._free_points or math.hypot(ix - self._free_points[-1][0],
                                                    iy - self._free_points[-1][1]) >= 1.0 / self.zoom):
                self._free_points.append((ix, iy))
            self._preview = {'kind': 'free_selection', 'points': self._free_points}
            self.update()
        elif self._mode in ('line', 'curve_draw'):
            self._preview = {'kind': 'line', 'p0': self._preview['p0'], 'p1': (ix, iy)}
            self.update()
        elif self._mode == 'curve_adjust':
            self._curve_drag(ix, iy)
            self.update()
        elif self._mode == 'shape':
            preview = self._preview
            nx, ny = min(preview['x'], ix), min(preview['y'], iy)
            nw, nh = abs(ix - preview['x']), abs(iy - preview['y'])
            self._preview = {'kind': 'shape', 'shape': preview['shape'],
                             'x': nx, 'y': ny, 'w': nw, 'h': nh}
            self.update()
        self._update_status(x, y)

    def _drag_end(self, x, y):
        mode = self._mode
        sx, sy = self._start
        self._mode = None
        if mode == 'stroke':
            self._commit_stroke()
        elif mode == 'line':
            if self._preview:
                p0, p1 = self._preview['p0'], self._preview['p1']
                if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) >= 0.5:
                    painter = QPainter(self.doc.surface)
                    painter.setPen(QPen(self._stroke_color(), max(0.8, self.line_width),
                                        Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    painter.drawLine(QPointF(*p0), QPointF(*p1))
                    painter.end()
            self._preview = None
            self._notify_modified()
        elif mode == 'curve_draw':
            if self._preview:
                p0, p1 = self._preview['p0'], self._preview['p1']
                if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) >= 1:
                    c1 = (p0[0] + (p1[0] - p0[0]) / 3, p0[1] + (p1[1] - p0[1]) / 3)
                    c2 = (p0[0] + (p1[0] - p0[0]) * 2 / 3, p0[1] + (p1[1] - p0[1]) * 2 / 3)
                    self._curve = {'p0': p0, 'p1': p1, 'c1': c1, 'c2': c2, 'steps': 0}
                    self._preview = {'kind': 'curve', 'p0': p0, 'p1': p1, 'c1': c1, 'c2': c2}
                else:
                    self._preview = None
        elif mode == 'shape':
            if self._preview:
                preview = self._preview
                if preview['w'] >= 0.5 and preview['h'] >= 0.5:
                    painter = QPainter(self.doc.surface)
                    self._render_shape(painter, preview['shape'], preview['x'],
                                       preview['y'], preview['w'], preview['h'])
                    painter.end()
                    self._notify_modified()
                self._preview = None
        elif mode == 'select_rect':
            if self._new_selection:
                x, y, w, h = self._new_selection
                if w < 1 or h < 1:
                    self.doc.selection = None
                else:
                    self.doc.selection = Selection(int(x), int(y), int(round(w)), int(round(h)))
                    if self.on_selection_changed:
                        self.on_selection_changed(self.doc.selection)
            else:
                self.doc.selection = None
            self._preview = None
            self._new_selection = None
            self._notify_selection()
        elif mode == 'select_free':
            if self._free_points and len(self._free_points) >= 3:
                xs = [pt[0] for pt in self._free_points]
                ys = [pt[1] for pt in self._free_points]
                x, y = min(xs), min(ys)
                w, h = max(xs) - x, max(ys) - y
                if w >= 1 and h >= 1:
                    self.doc.selection = Selection(int(x), int(y), int(math.ceil(w)),
                                                   int(math.ceil(h)),
                                                   polygon=list(self._free_points))
            else:
                self.doc.selection = None
            self._preview = None
            self._free_points = []
            self._notify_selection()
        elif mode == 'move':
            self._move_origin = None
            self._move_start = None
            self._notify_selection()
            self._notify_modified()
        elif mode == 'resize_selection':
            self._resize_handle = None
            self._notify_selection()
            self._notify_modified()
        self.update()
        self._update_status(x, y)

    # ------------------------------------------------------------------
    # Stroke drawing
    def _begin_stroke(self, ix, iy):
        self._mode = 'stroke'
        self.doc.push_undo('绘图')
        self._action_undo_pushed = True
        self._points = [(ix, iy)]
        button = self.color2 if self._button == 3 else self.color1
        color = QColor(*button)
        if self.tool == 'pencil' and self.line_width <= 1:
            draw_pixel_line(self.doc.surface, ix, iy, ix, iy, color)
        else:
            painter = QPainter(self.doc.surface)
            if self.tool == 'eraser':
                size = max(4, self.line_width * 2)
                draw_eraser(painter, ix, iy, size, QColor(*self.color2),
                            clear=self.doc.transparent)
            elif self.tool == 'pencil':
                painter.setPen(QPen(color, max(1, self.line_width * 0.5),
                                    Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                radius = max(0.5, self.line_width * 0.25)
                painter.drawEllipse(QPointF(ix, iy), radius, radius)
            elif self.tool == 'brush':
                stroke_segment(painter, (ix, iy), (ix + 0.01, iy + 0.01), color,
                               self.line_width, self.brush, seed=1)
            painter.end()
        self._notify_modified()
        self.update()

    def _continue_stroke(self, ix, iy):
        last = self._points[-1]
        if abs(ix - last[0]) < 0.1 and abs(iy - last[1]) < 0.1 and self.tool != 'brush':
            return
        button = self.color2 if self._button == 3 else self.color1
        color = QColor(*button)
        if self.tool == 'pencil' and self.line_width <= 1:
            draw_pixel_line(self.doc.surface, last[0], last[1], ix, iy, color)
        else:
            painter = QPainter(self.doc.surface)
            if self.tool == 'eraser':
                size = max(4, self.line_width * 2)
                dist = math.hypot(ix - last[0], iy - last[1])
                steps = max(1, int(dist / max(1, size * 0.35)))
                for i in range(1, steps + 1):
                    t = i / steps
                    draw_eraser(painter, last[0] + (ix - last[0]) * t,
                                last[1] + (iy - last[1]) * t, size,
                                QColor(*self.color2), clear=self.doc.transparent)
            elif self.tool == 'pencil':
                painter.setPen(QPen(color, max(1, self.line_width * 0.5),
                                    Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(QPointF(*last), QPointF(ix, iy))
            elif self.tool == 'brush':
                stroke_segment(painter, last, (ix, iy), color, self.line_width,
                               self.brush, seed=len(self._points))
            painter.end()
        self._points.append((ix, iy))
        self._update_status(*self.image_to_view(ix, iy))
        self.update()

    def _commit_stroke(self):
        if self._points:
            self._notify_modified()
        self._points = []

    def _delete_background(self):
        if self.doc.transparent:
            return QColor(255, 255, 255, 0)
        return QColor(*self.color2)

    def _do_fill(self, ix, iy):
        self.doc.push_undo('用颜色填充')
        color = QColor(*(self.color2 if self._button == 3 else self.color1))
        bucket_fill(self.doc.surface, int(ix), int(iy), color)
        self._notify_modified()
        self.update()

    def _pick(self, ix, iy):
        color = pick_color(self.doc.surface, int(ix), int(iy))
        if color:
            if self._button == 3:
                self.set_colors(color2=color[:3])
            else:
                self.set_colors(color1=color[:3])
            self._update_status(*self.image_to_view(ix, iy))

    # ------------------------------------------------------------------
    # Selection
    def _begin_select(self, ix, iy, freeform=False):
        sel = self.doc.selection
        handle = self._selection_handle_at(ix, iy) if sel and not freeform else None
        if handle:
            if sel.floating is None:
                self.doc.lift_selection()
                self._transparentize_floating()
            self._mode = 'resize_selection'
            self._resize_handle = handle
            self._resize_rect0 = (sel.x, sel.y, sel.w, sel.h)
            self._resize_start = (ix, iy)
            self._resize_base = _copy_image(sel.floating) if sel.floating else None
            self._notify_selection()
            return
        if sel and not sel.empty and sel.contains(ix, iy):
            if sel.floating is None:
                self.doc.lift_selection()
                self._transparentize_floating()
            self._mode = 'move'
            self._move_origin = sel.floating_origin or sel.rect[:2]
            self._move_start = (ix, iy)
            self._notify_selection()
            return
        self.doc.selection = None
        self._sel_start = (ix, iy)
        self._free_points = [(ix, iy)] if freeform else []
        self._mode = 'select_free' if freeform else 'select_rect'
        self._preview = ({'kind': 'free_selection', 'points': self._free_points}
                         if freeform else {'kind': 'rect_selection', 'rect': (ix, iy, 0, 0)})
        self._notify_selection()
        self.update()

    def _selection_handle_at(self, ix, iy):
        sel = self.doc.selection
        if not sel or sel.empty or sel.polygon or sel.inverted:
            return None
        x, y, w, h = sel.rect
        if sel.floating is not None and sel.floating_origin is not None:
            x, y = sel.floating_origin
            w, h = sel.floating.width(), sel.floating.height()
        tol = max(5.0, 7.0 / self.zoom)
        points = {
            'nw': (x, y), 'n': (x + w / 2, y), 'ne': (x + w, y),
            'w': (x, y + h / 2), 'e': (x + w, y + h / 2),
            'sw': (x, y + h), 's': (x + w / 2, y + h), 'se': (x + w, y + h),
        }
        for name, (px, py) in points.items():
            if abs(ix - px) <= tol and abs(iy - py) <= tol:
                return name
        return None

    def _resize_selection_update(self, ix, iy):
        sel = self.doc.selection
        if not sel or self._resize_base is None or self._resize_rect0 is None:
            return
        x0, y0, w0, h0 = self._resize_rect0
        dx = ix - self._resize_start[0]
        dy = iy - self._resize_start[1]
        x, y, w, h = x0, y0, w0, h0
        handle = self._resize_handle or 'se'
        if 'w' in handle:
            x = x0 + dx
            w = w0 - dx
        if 'e' in handle:
            w = w0 + dx
        if 'n' in handle:
            y = y0 + dy
            h = h0 - dy
        if 's' in handle:
            h = h0 + dy
        if w < 1:
            if 'w' in handle:
                x = x0 + w0 - 1
            w = 1
        if h < 1:
            if 'n' in handle:
                y = y0 + h0 - 1
            h = 1
        nw, nh = max(1, int(round(w))), max(1, int(round(h)))
        scaled = _scale_image(self._resize_base, nw, nh)
        sel.floating = scaled
        sel.floating_origin = (int(round(x)), int(round(y)))
        sel.x, sel.y, sel.w, sel.h = int(round(x)), int(round(y)), nw, nh

    # ------------------------------------------------------------------
    # Curve tool
    def _curve_adjust_start(self, ix, iy):
        curve = self._curve
        if not curve:
            return
        d1 = math.hypot(ix - curve['c1'][0], iy - curve['c1'][1])
        d2 = math.hypot(ix - curve['c2'][0], iy - curve['c2'][1])
        curve['active'] = 'c1' if d1 <= d2 else 'c2'
        curve['offset'] = (ix - curve[curve['active']][0], iy - curve[curve['active']][1])
        self._preview = {'kind': 'curve', 'p0': curve['p0'], 'p1': curve['p1'],
                         'c1': curve['c1'], 'c2': curve['c2']}

    def _curve_drag(self, ix, iy):
        curve = self._curve
        if not curve:
            return
        key = curve.get('active', 'c1')
        ox, oy = curve.get('offset', (0, 0))
        curve[key] = (ix - ox, iy - oy)
        self._preview = {'kind': 'curve', 'p0': curve['p0'], 'p1': curve['p1'],
                         'c1': curve['c1'], 'c2': curve['c2']}

    def finish_curve(self):
        if not self._curve:
            return
        curve = self._curve
        painter = QPainter(self.doc.surface)
        draw_curve(painter, curve['p0'], curve['p1'], curve['c1'], curve['c2'],
                   self._stroke_color(), self.line_width, self.outline_style)
        painter.end()
        self._curve = None
        self._preview = None
        if not self.doc.can_undo():
            self.doc.push_undo('曲线')
        self._notify_modified()
        self.update()

    # ------------------------------------------------------------------
    # Text tool
    def _begin_text(self, ix, iy):
        if self._text_editor is not None:
            self._commit_text()
        self._text_pos = (ix, iy)
        self._create_text_editor(ix, iy)

    def _editor_font(self) -> QFont:
        font = QFont(self.text_family or 'Sans')
        px = max(6, int(round(self.text_size * 96 / 72 * self.zoom)))
        font.setPixelSize(px)
        font.setBold(self.text_bold)
        font.setItalic(self.text_italic)
        font.setUnderline(self.text_underline)
        return font

    def _create_text_editor(self, ix, iy):
        if self._text_editor is not None:
            self._remove_text_editor()
        editor = QTextEdit(self)
        editor.setAcceptRichText(False)
        editor.setTabChangesFocus(True)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        editor.setFont(self._editor_font())
        editor.resize(max(120, int(220 * self.zoom)), max(40, int(70 * self.zoom)))
        color = QColor(*self.color1).name()
        bg = QColor(*self.color2).name() if self.text_opaque else 'transparent'
        editor.setStyleSheet(
            f"QTextEdit {{ background-color: {bg}; color: {color}; "
            f"padding: 0px; border: 1px solid #4a90e2; }}")
        px, py = self.image_to_view(ix, iy)
        editor.move(int(px), int(py))
        editor.installEventFilter(self)
        editor.show()
        editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self._text_editor = editor
        self.update()

    def _remove_text_editor(self):
        editor = self._text_editor
        self._text_editor = None
        if editor is not None:
            editor.removeEventFilter(self)
            editor.hide()
            editor.deleteLater()

    def _sync_text_editor_geometry(self):
        if self._text_editor is None or self._text_pos is None:
            return
        ix, iy = self._text_pos
        px, py = self.image_to_view(ix, iy)
        self._text_editor.move(int(px), int(py))
        self._text_editor.setFont(self._editor_font())

    def eventFilter(self, obj, event):
        if obj is self._text_editor:
            if event.type() == QEvent.Type.ShortcutOverride:
                # Let the text editor own the standard editing shortcuts;
                # otherwise the window-level actions would steal Ctrl+A/C/V/X/Z/Y.
                key = event.key()
                ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                if ctrl and key in (Qt.Key.Key_A, Qt.Key.Key_C, Qt.Key.Key_V,
                                    Qt.Key.Key_X, Qt.Key.Key_Z, Qt.Key.Key_Y):
                    event.accept()
                    return True
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                if key == Qt.Key.Key_Escape:
                    self._discard_text()
                    return True
                if ctrl and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._commit_text()
                    return True
            elif event.type() == QEvent.Type.FocusOut:
                QTimer.singleShot(0, lambda e=obj: self._deferred_text_commit(e))
        return super().eventFilter(obj, event)

    def _deferred_text_commit(self, editor=None):
        # A style change rebuilds the editor; the stale FocusOut must not
        # commit the newly created editor.
        if editor is not None and editor is not self._text_editor:
            return
        if self._text_editor is not None:
            self._commit_text()

    def _commit_text(self):
        editor = self._text_editor
        if editor is None:
            return
        text = editor.toPlainText()
        pos = self._text_pos
        self._remove_text_editor()
        self._text_pos = None
        if text.strip() and pos:
            self.doc.push_undo('文本')
            painter = QPainter(self.doc.surface)
            draw_text(painter, text, pos[0], pos[1], self.text_family, self.text_size,
                      self.text_bold, self.text_italic, self.text_underline,
                      QColor(*self.color1), QColor(*self.color2), self.text_opaque)
            painter.end()
            self._notify_modified()
        self.update()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _discard_text(self):
        self._remove_text_editor()
        self._text_pos = None
        self.update()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def update_text_style(self):
        if self._text_editor is not None and self._text_pos:
            ix, iy = self._text_pos
            text = self._text_editor.toPlainText()
            cursor = self._text_editor.textCursor().position()
            self._remove_text_editor()
            self._text_pos = (ix, iy)
            self._create_text_editor(ix, iy)
            self._text_editor.setPlainText(text)
            cursor_obj = self._text_editor.textCursor()
            cursor_obj.setPosition(min(cursor, len(text)))
            self._text_editor.setTextCursor(cursor_obj)
            self._text_editor.setFocus(Qt.FocusReason.OtherFocusReason)

    # ------------------------------------------------------------------
    # Clipboard / selection API
    def _apply_transparent_selection(self, surface: QImage):
        """Drop Colour 2 pixels when Paint's transparent-selection mode is on."""
        if surface is None or self.opaque_selection:
            return surface
        out = _copy_image(surface)
        _replace_color_alpha(out, self.color2)
        return out

    def _transparentize_floating(self):
        sel = self.doc.selection
        if sel and sel.floating is not None and not self.opaque_selection:
            sel.floating = self._apply_transparent_selection(sel.floating)

    def get_clipboard_surface(self):
        if self.doc.selection:
            if self.doc.selection.floating is not None:
                out = _copy_image(self.doc.selection.floating)
                return self._apply_transparent_selection(out)
            return self._apply_transparent_selection(self.doc.get_selection_surface())
        return None

    def paste_surface(self, surface: QImage, *, origin=(0, 0)):
        self.set_tool('select')
        surface = _copy_image(surface)
        surface = self._apply_transparent_selection(surface)
        self.doc.push_undo('粘贴')
        self.doc.selection = Selection(int(origin[0]), int(origin[1]),
                                       surface.width(), surface.height(),
                                       floating=surface,
                                       floating_origin=(int(origin[0]), int(origin[1])))
        self._notify_selection()
        self._notify_modified()
        self._update_size()
        self.update()

    def paste_png_bytes(self, data: bytes):
        self.paste_surface(png_bytes_to_surface(data))

    def commit_floating(self):
        sel = self.doc.selection
        if sel and sel.floating is not None:
            self._transparentize_floating()
            self.doc.flatten_selection()
            self.doc.dirty = True
            self._notify_modified()
            self.update()

    def copy_selection(self):
        self.commit_floating()
        return self.get_clipboard_surface()

    def cut_selection(self):
        surface = self.copy_selection()
        if surface is not None:
            self.doc.delete_selection(self._delete_background())
            self._notify_selection()
            self._notify_modified()
            self.update()
        return surface

    def delete_selection(self):
        if self.doc.selection is not None:
            self.doc.delete_selection(self._delete_background())
            self._notify_selection()
            self._notify_modified()
            self.update()
            return True
        return False

    def select_all(self):
        self.commit_floating()
        self.doc.select_all()
        self._notify_selection()
        self.update()

    def crop(self):
        self.commit_floating()
        if self.doc.crop():
            self._notify_selection()
            self._notify_modified()
            self._update_size()
            return True
        return False

    def update_after_image_change(self):
        self._update_size()
        self.update()
        self._notify_modified()
        self._notify_selection()
        self._update_status()

    def png_for_clipboard(self):
        surface = self.get_clipboard_surface()
        return surface_to_png_bytes(surface, with_alpha=True) if surface else None


# ----------------------------------------------------------------------
# Pixel helpers
def _replace_color_alpha(surface: QImage, bg_rgb, tolerance=18):
    """Make pixels matching the Paint background colour transparent."""
    c = _qcolor(bg_rgb)
    br, bg, bb = c.red(), c.green(), c.blue()
    data, stride = _buffer(surface)
    for y in range(surface.height()):
        off = y * stride
        end = off + surface.width() * 4
        while off < end:
            b, g, r, a = data[off], data[off + 1], data[off + 2], data[off + 3]
            if a and abs(r - br) <= tolerance and abs(g - bg) <= tolerance and abs(b - bb) <= tolerance:
                data[off] = data[off + 1] = data[off + 2] = data[off + 3] = 0
            off += 4
