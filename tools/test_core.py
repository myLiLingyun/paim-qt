# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless tests for the Qt document, raster and file behaviour."""
import os
import sys
import tempfile
import traceback

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QPainter

app = QApplication([])

from mspaint.document import (Document, Selection, image_has_transparency,
                              surface_to_png_bytes, png_bytes_to_surface)
from mspaint.raster import (bucket_fill, draw_curve, draw_freehand, fill_shape,
                            pick_color, draw_pixel_line)
from mspaint.shapes import SHAPE_ORDER
from mspaint.text import draw_text

results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


def pix(image, x, y):
    c = image.pixelColor(x, y)
    return (c.red(), c.green(), c.blue(), c.alpha())


def main():
    d = Document(320, 240)
    check('new document white', pix(d.surface, 0, 0) == (255, 255, 255, 255),
          pix(d.surface, 0, 0))
    d.push_undo('pencil')
    p = QPainter(d.surface)
    p.setPen(QColor(0, 0, 0))
    p.drawLine(10, 10, 100, 100)
    p.end()
    d.dirty = True
    check('draw pixel', pix(d.surface, 10, 10)[:3] != (255, 255, 255),
          pix(d.surface, 10, 10))
    check('undo stack', d.can_undo())
    check('undo restores', (d.undo() and pix(d.surface, 10, 10) == (255, 255, 255, 255)),
          pix(d.surface, 10, 10))
    check('redo restores', (d.redo() and pix(d.surface, 10, 10)[:3] != (255, 255, 255)),
          pix(d.surface, 10, 10))
    d.undo()

    for brush in ['brush', 'calligraphy1', 'calligraphy2', 'airbrush', 'paintbrush',
                  'crayon', 'marker', 'pencil', 'watercolor']:
        d2 = Document(160, 120)
        try:
            p = QPainter(d2.surface)
            draw_freehand(p, [(10, 10), (30, 40), (80, 80), (120, 30)],
                          QColor(0, 0, 0), 8, brush, seed=1)
            p.end()
            check('brush ' + brush, True)
        except Exception as exc:
            check('brush ' + brush, False, repr(exc))

    from mspaint.raster import SHAPE_FILL_STYLES, SHAPE_OUTLINE_STYLES
    for fill_style in SHAPE_FILL_STYLES:
        d_style = Document(220, 180)
        try:
            p = QPainter(d_style.surface)
            fill_shape(p, 'rounded_rectangle', 20, 20, 180, 140, fill_style,
                       QColor(60, 120, 220), 'solid', QColor(0, 0, 0), 2)
            p.end()
            check('fill style ' + fill_style, True)
        except Exception as exc:
            check('fill style ' + fill_style, False, repr(exc))
    for outline_style in SHAPE_OUTLINE_STYLES:
        d_style = Document(220, 180)
        try:
            p = QPainter(d_style.surface)
            fill_shape(p, 'ellipse', 20, 20, 180, 140, 'none', QColor(255, 255, 255),
                       outline_style, QColor(0, 0, 0), 4)
            p.end()
            check('outline style ' + outline_style, True)
        except Exception as exc:
            check('outline style ' + outline_style, False, repr(exc))

    for shape in SHAPE_ORDER:
        d2 = Document(200, 160)
        try:
            p = QPainter(d2.surface)
            if shape == 'curve':
                draw_curve(p, (10, 10), (180, 140), (50, 120), (140, 20),
                           QColor(0, 0, 0), 2)
            else:
                fill_shape(p, shape, 10, 10, 170, 130, 'solid', QColor(255, 0, 0),
                           'solid', QColor(0, 0, 0), 2)
            p.end()
            check('shape ' + shape, True)
        except Exception as exc:
            check('shape ' + shape, False, repr(exc))

    d2 = Document(80, 80)
    bucket_fill(d2.surface, 20, 20, QColor(255, 0, 0))
    check('flood fill', pix(d2.surface, 40, 40) == (255, 0, 0, 255),
          pix(d2.surface, 40, 40))
    check('picker', pick_color(d2.surface, 40, 40) == (255, 0, 0, 255),
          pick_color(d2.surface, 40, 40))
    draw_pixel_line(d2.surface, 1, 1, 5, 5, QColor(0, 255, 0))
    check('pixel line', pix(d2.surface, 3, 3) == (0, 255, 0, 255),
          pix(d2.surface, 3, 3))

    d2 = Document(120, 90)
    p = QPainter(d2.surface)
    p.fillRect(10, 10, 30, 20, QColor(0, 0, 255))
    p.end()
    d2.selection = Selection(10, 10, 30, 20)
    d2.rotate('right')
    check('rotate selection dims', (d2.width, d2.height) == (120, 90),
          (d2.width, d2.height))
    check('selection rotated', d2.selection.rect == (10, 10, 20, 30),
          d2.selection.rect)
    d2.undo()
    d2.selection = Selection(10, 10, 30, 20)
    surface = d2.get_selection_surface()
    check('selection surface', surface is not None and surface.width() == 30)
    d2.delete_selection(QColor(255, 255, 255))
    check('delete selection white', pix(d2.surface, 20, 20) == (255, 255, 255, 255),
          pix(d2.surface, 20, 20))
    d2.selection = Selection(0, 0, d2.width, d2.height)
    d2.crop()
    check('crop', (d2.width, d2.height) == (120, 90))
    d2.resize(240, 180)
    check('resize', (d2.width, d2.height) == (240, 180), (d2.width, d2.height))
    d2.skew(10, 5)
    check('skew', d2.width > 240 and d2.height > 180, (d2.width, d2.height))

    d3 = Document(64, 48)
    p = QPainter(d3.surface)
    p.fillRect(0, 0, 32, 48, QColor(255, 0, 0))
    p.end()
    tmp = tempfile.mkdtemp()
    for fmt, ext in [('png', 'png'), ('jpg', 'jpg'), ('bmp', 'bmp'), ('gif', 'gif'),
                     ('dib', 'dib'), ('webp', 'webp'), ('tiff', 'tiff')]:
        path = os.path.join(tmp, 'test.' + ext)
        try:
            d3.save(path, fmt=fmt)
            opened = Document.open(path)
            check('format ' + fmt,
                  opened.width == 64 and opened.height == 48,
                  f'{opened.width}x{opened.height}')
            r, g, b, a = pix(opened.surface, 8, 8)
            check('format pixel ' + fmt, r > 200 and g < 80, (r, g, b, a))
        except Exception as exc:
            check('format ' + fmt, False, repr(exc))
    for bits in (1, 4, 8, 24):
        path = os.path.join(tmp, f'test{bits}.bmp')
        try:
            d3.save(path, fmt='bmp', bits=bits)
            check(f'bmp {bits}bit', os.path.getsize(path) > 0, os.path.getsize(path))
        except Exception as exc:
            check(f'bmp {bits}bit', False, repr(exc))

    d4 = Document(300, 100)
    try:
        p = QPainter(d4.surface)
        w, h = draw_text(p, 'Hello 你好', 10, 10, 'Sans', 16, True, False, False,
                         QColor(0, 0, 0), QColor(255, 255, 255), True)
        p.end()
        check('text extents', w > 10 and h > 5, (w, h))
    except Exception as exc:
        check('text render', False, repr(exc))

    d5 = Document(100, 100)
    d5.selection = Selection(0, 0, 20, 20)
    p = QPainter(d5.surface)
    p.fillRect(0, 0, 20, 20, QColor(0, 255, 0))
    p.end()
    d5.get_selection_surface()
    d5.lift_selection()
    check('lift selection', d5.selection.floating is not None)
    d5.selection.floating_origin = (30, 40)
    d5.flatten_selection()
    check('flatten at origin', pix(d5.surface, 35, 45)[:3] == (0, 255, 0),
          pix(d5.surface, 35, 45))
    check('flatten geometry', (d5.selection.x, d5.selection.y) == (30, 40),
          d5.selection.rect)

    # Transparency
    t = Document(50, 50, transparent=True)
    check('transparent document', image_has_transparency(t.surface) and t.transparent)
    p = QPainter(t.surface)
    p.fillRect(0, 0, 25, 50, QColor(0, 255, 0, 255))
    p.end()
    png = surface_to_png_bytes(t.surface, with_alpha=True)
    reopened = png_bytes_to_surface(png)
    check('png alpha round trip', pix(reopened, 5, 5)[3] == 255
          and pix(reopened, 40, 5)[3] == 0, (pix(reopened, 5, 5), pix(reopened, 40, 5)))
    t.set_transparency(False)
    check('transparency disabled', not t.transparent
          and pix(t.surface, 40, 5)[3] == 255, pix(t.surface, 40, 5))

    print('RESULTS', sum(1 for _, ok, _ in results if ok), '/', len(results))
    fails = [n for n, ok, _ in results if not ok]
    print('FAILED', fails)
    return 0 if not fails else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
