# SPDX-License-Identifier: GPL-3.0-or-later
"""Transparency and alpha-channel tests."""
import os
import sys
import tempfile
import traceback

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['XDG_CONFIG_HOME'] = tempfile.mkdtemp()
os.environ['XDG_DATA_HOME'] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QPainter

app = QApplication([])

from mspaint.app import PaintWindow
from mspaint.document import Document, Selection, image_has_transparency

results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


def pix(image, x, y):
    c = image.pixelColor(x, y)
    return (c.red(), c.green(), c.blue(), c.alpha())


def main():
    win = PaintWindow()
    win.show()
    app.processEvents()
    try:
        # Start with a fresh transparent document
        win.doc = Document(200, 150, transparent=True)
        win._bind_document()
        check('transparent document', win.doc.transparent)
        check('transparent pixels', pix(win.doc.surface, 10, 10)[3] == 0,
              pix(win.doc.surface, 10, 10))

        # Drawing keeps the rest transparent
        win._set_tool('brush')
        win.canvas.set_colors(color1=(255, 0, 0))
        win.canvas.line_width = 8
        win.canvas._drag_begin(30, 30)
        win.canvas._drag_update(100, 100)
        win.canvas._drag_end(100, 100)
        check('brush on transparent image', pix(win.doc.surface, 30, 30)[3] > 0
              and pix(win.doc.surface, 180, 130)[3] == 0,
              (pix(win.doc.surface, 30, 30), pix(win.doc.surface, 180, 130)))

        # Eraser clears to transparent
        win._set_tool('eraser')
        win.canvas.line_width = 20
        win.canvas._drag_begin(30, 30)
        win.canvas._drag_update(100, 100)
        win.canvas._drag_end(100, 100)
        check('eraser clears to transparent', pix(win.doc.surface, 30, 30)[3] == 0,
              pix(win.doc.surface, 30, 30))

        # Delete selection clears to transparent
        win.doc.clear_image()
        p = QPainter(win.doc.surface)
        p.fillRect(20, 20, 50, 50, QColor(0, 0, 255, 255))
        p.end()
        win.doc.selection = Selection(20, 20, 50, 50)
        win.canvas.delete_selection()
        check('delete selection transparent', pix(win.doc.surface, 30, 30)[3] == 0,
              pix(win.doc.surface, 30, 30))

        # Moving a selection leaves transparent pixels behind
        win.doc.clear_image()
        p = QPainter(win.doc.surface)
        p.fillRect(20, 20, 50, 50, QColor(0, 255, 0, 255))
        p.end()
        win.doc.selection = Selection(20, 20, 50, 50)
        win._set_tool('select')
        win.canvas._drag_begin(40, 40)
        win.canvas._drag_update(90, 80)
        win.canvas._drag_end(90, 80)
        check('move leaves transparency', pix(win.doc.surface, 30, 30)[3] == 0,
              pix(win.doc.surface, 30, 30))
        win.canvas.commit_floating()
        check('moved pixels opaque', pix(win.doc.surface, 90, 90)[3] == 255,
              pix(win.doc.surface, 90, 90))

        # Alpha-preserving PNG and GIF round trips
        png = os.path.join(tempfile.mkdtemp(), 'alpha.png')
        win.doc.save(png, fmt='png')
        opened = Document.open(png)
        check('png alpha saved', image_has_transparency(opened.surface)
              and pix(opened.surface, 20, 20)[3] == 0, pix(opened.surface, 20, 20))
        gif = os.path.join(tempfile.mkdtemp(), 'alpha.gif')
        win.doc.save(gif, fmt='gif')
        opened_gif = Document.open(gif)
        check('gif alpha saved', image_has_transparency(opened_gif.surface),
              pix(opened_gif.surface, 20, 20))
        webp = os.path.join(tempfile.mkdtemp(), 'alpha.webp')
        win.doc.save(webp, fmt='webp')
        opened_webp = Document.open(webp)
        check('webp alpha saved', image_has_transparency(opened_webp.surface),
              pix(opened_webp.surface, 20, 20))
        tiff = os.path.join(tempfile.mkdtemp(), 'alpha.tiff')
        win.doc.save(tiff, fmt='tiff')
        opened_tiff = Document.open(tiff)
        check('tiff alpha saved', image_has_transparency(opened_tiff.surface),
              pix(opened_tiff.surface, 20, 20))

        # Transparency via image properties: punching out the background colour
        opaque = Document(60, 40)
        p = QPainter(opaque.surface)
        p.fillRect(10, 10, 20, 20, QColor(0, 0, 0))
        p.end()
        opaque.set_transparency(True)
        check('background punched out', pix(opaque.surface, 50, 30)[3] == 0,
              pix(opaque.surface, 50, 30))
        check('black content preserved', pix(opaque.surface, 20, 20)[3] == 255,
              pix(opaque.surface, 20, 20))
        opaque.set_transparency(False)
        check('alpha flattened', pix(opaque.surface, 50, 30)[3] == 255,
              pix(opaque.surface, 50, 30))

        # Inverted selections clear everything outside the rectangle
        inv = Document(60, 40)
        p = QPainter(inv.surface)
        p.fillRect(10, 10, 20, 20, QColor(0, 0, 255))
        p.end()
        inv.selection = Selection(10, 10, 20, 20, inverted=True)
        inv.delete_selection(QColor(255, 255, 255, 0))
        check('inverted selection clears outside',
              pix(inv.surface, 2, 2)[3] == 0 and pix(inv.surface, 20, 20)[3] == 255,
              (pix(inv.surface, 2, 2), pix(inv.surface, 20, 20)))

        # Transparent-selection mode removes colour 2 from floating content
        win.doc = Document(100, 80)
        win._bind_document()
        p = QPainter(win.doc.surface)
        p.fillRect(0, 0, 50, 50, QColor(255, 255, 255))
        p.fillRect(0, 0, 10, 10, QColor(10, 20, 30))
        p.end()
        win.canvas.select_all()
        win.canvas.opaque_selection = False
        win.canvas.set_colors(color2=(255, 255, 255))
        sliced = win.canvas.get_clipboard_surface()
        check('transparent selection removes background',
              sliced is not None and pix(sliced, 30, 30)[3] == 0
              and pix(sliced, 5, 5)[3] == 255,
              (pix(sliced, 30, 30) if sliced else None,
               pix(sliced, 5, 5) if sliced else None))
        win.canvas.opaque_selection = True


        # Checkerboard shows through transparent pixels
        win.doc = Document(120, 90, transparent=True)
        win._bind_document()
        win.canvas.dark = False
        win.canvas.update()
        app.processEvents()
        shot = win.canvas.grab().toImage()
        shades = set()
        for x in range(15, 45):
            c = shot.pixelColor(x, 20)
            shades.add((c.red(), c.green(), c.blue()))
        check('checkerboard visible through alpha', len(shades) > 1, sorted(shades)[:4])

        # Polygon selection delete / lift keeps the alpha channel
        poly_doc = Document(60, 60, transparent=True)
        p = QPainter(poly_doc.surface)
        p.fillRect(0, 0, 60, 60, QColor(0, 0, 255, 255))
        p.end()
        poly_doc.selection = Selection(5, 5, 30, 30,
                                       polygon=[(10, 10), (30, 10), (30, 30), (10, 30)])
        poly_doc.delete_selection(QColor(255, 255, 255, 0))
        check('polygon delete clears alpha',
              pix(poly_doc.surface, 20, 20)[3] == 0, pix(poly_doc.surface, 20, 20))
        check('polygon delete keeps outside',
              pix(poly_doc.surface, 50, 50)[3] == 255, pix(poly_doc.surface, 50, 50))
        poly_doc.selection = Selection(5, 5, 30, 30,
                                       polygon=[(10, 10), (30, 10), (30, 30), (10, 30)])
        poly_doc.lift_selection()
        check('polygon lift leaves transparency',
              pix(poly_doc.surface, 20, 20)[3] == 0, pix(poly_doc.surface, 20, 20))

        # Resize canvas fills with a transparent background
        grow = Document(20, 20, transparent=True)
        grow.resize_canvas(40, 40)
        check('resize canvas keeps transparency',
              pix(grow.surface, 35, 35)[3] == 0, pix(grow.surface, 35, 35))

        # UI eraser and save preserve alpha
        win.doc = Document(80, 60, transparent=True)
        win._bind_document()
        p = QPainter(win.doc.surface)
        p.fillRect(0, 0, 80, 60, QColor(255, 0, 0, 255))
        p.end()
        win._set_tool('eraser')
        win.canvas.line_width = 8
        win.canvas._drag_begin(win.canvas.image_to_view(20, 20)[0],
                               win.canvas.image_to_view(20, 20)[1])
        win.canvas._drag_update(win.canvas.image_to_view(50, 40)[0],
                                win.canvas.image_to_view(50, 40)[1])
        win.canvas._drag_end(win.canvas.image_to_view(50, 40)[0],
                             win.canvas.image_to_view(50, 40)[1])
        check('UI eraser clears alpha', pix(win.doc.surface, 20, 20)[3] == 0,
              pix(win.doc.surface, 20, 20))
        ui_png = os.path.join(tempfile.mkdtemp(), 'ui-alpha.png')
        win._save_to_path(ui_png, fmt='png')
        ui_opened = Document.open(ui_png)
        check('UI save preserves alpha', image_has_transparency(ui_opened.surface),
              pix(ui_opened.surface, 20, 20))

        print('RESULTS', sum(1 for _, ok, _ in results if ok), '/', len(results))
        fails = [n for n, ok, _ in results if not ok]
        print('FAILED', fails)
        return 0 if not fails else 1
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        win._force_close = True
        win.close()


if __name__ == '__main__':
    sys.exit(main())
