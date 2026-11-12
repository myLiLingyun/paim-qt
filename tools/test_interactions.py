# SPDX-License-Identifier: GPL-3.0-or-later
"""Mouse/keyboard interaction tests for the Qt canvas."""
import os
import sys
import tempfile
import traceback

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['XDG_CONFIG_HOME'] = tempfile.mkdtemp()
os.environ['XDG_DATA_HOME'] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtTest import QTest

app = QApplication([])

from mspaint.app import PaintWindow

results = []
PAD = 12


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


def view(x, y, zoom=1.0):
    return QPoint(int(PAD + x * zoom), int(PAD + y * zoom))


def drag(canvas, start, end, button=Qt.MouseButton.LeftButton):
    p0 = view(*start)
    p1 = view(*end)
    QTest.mousePress(canvas, button, Qt.KeyboardModifier.NoModifier, p0)
    QTest.mouseMove(canvas, QPoint((p0.x() + p1.x()) // 2, (p0.y() + p1.y()) // 2))
    QTest.mouseMove(canvas, p1)
    QTest.mouseRelease(canvas, button, Qt.KeyboardModifier.NoModifier, p1)
    app.processEvents()


def click(canvas, x, y, button=Qt.MouseButton.LeftButton):
    p = view(x, y)
    QTest.mouseClick(canvas, button, Qt.KeyboardModifier.NoModifier, p)
    app.processEvents()


def pix(image, x, y):
    c = image.pixelColor(x, y)
    return (c.red(), c.green(), c.blue(), c.alpha())


def main():
    win = PaintWindow()
    win.show()
    app.processEvents()
    win.canvas.setFocus()
    try:
        # Pencil
        win._set_tool('pencil')
        win.canvas.set_colors(color1=(0, 0, 0))
        drag(win.canvas, (50, 50), (150, 150))
        check('pencil mouse stroke', pix(win.doc.surface, 100, 100)[:3] == (0, 0, 0),
              pix(win.doc.surface, 100, 100))
        win._undo()

        # Right-button stroke uses colour 2
        win.canvas.set_colors(color2=(0, 0, 255))
        win._set_tool('pencil')
        drag(win.canvas, (40, 160), (140, 160), button=Qt.MouseButton.RightButton)
        check('right button stroke', pix(win.doc.surface, 90, 160)[:3] == (0, 0, 255),
              pix(win.doc.surface, 90, 160))
        win._undo()

        # Line tool
        win._set_tool('line')
        win.canvas.set_colors(color1=(0, 0, 0))
        drag(win.canvas, (20, 20), (120, 20))
        check('line preview commits', pix(win.doc.surface, 70, 20)[:3] == (0, 0, 0),
              pix(win.doc.surface, 70, 20))

        # Rectangle selection + move
        win._set_tool('select')
        drag(win.canvas, (30, 30), (130, 100))
        check('rect selection created', win.doc.selection is not None,
              win.doc.selection.rect if win.doc.selection else None)
        check('rect selection geometry',
              win.doc.selection is not None and win.doc.selection.rect == (30, 30, 100, 70),
              win.doc.selection.rect if win.doc.selection else None)
        drag(win.canvas, (80, 60), (120, 90))
        check('selection lifted and moved',
              win.doc.selection is not None and win.doc.selection.floating is not None,
              win.doc.selection.floating_origin if win.doc.selection else None)
        check('floating origin shifted',
              win.doc.selection.floating_origin == (70, 60),
              win.doc.selection.floating_origin if win.doc.selection else None)
        win.canvas.commit_floating()
        check('floating committed',
              (win.doc.selection.x, win.doc.selection.y) == (70, 60), win.doc.selection.rect)

        # Escape clears selection
        QTest.keyClick(win.canvas, Qt.Key.Key_Escape)
        app.processEvents()
        check('escape clears selection', win.doc.selection is None)

        # Free-form selection
        win._set_tool('free_select')
        p0 = view(250, 260)
        QTest.mousePress(win.canvas, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, p0)
        for x, y in ((300, 240), (340, 290), (300, 330), (250, 300)):
            QTest.mouseMove(win.canvas, view(x, y))
        QTest.mouseRelease(win.canvas, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier, view(250, 300))
        app.processEvents()
        check('free-form selection',
              win.doc.selection is not None and win.doc.selection.polygon is not None,
              win.doc.selection.polygon if win.doc.selection else None)
        QTest.keyClick(win.canvas, Qt.Key.Key_Escape)
        app.processEvents()

        # Resize a rectangular selection with its south-east handle
        win._set_tool('select')
        drag(win.canvas, (30, 30), (130, 100))
        before = win.doc.selection.rect if win.doc.selection else None
        win._set_tool('select')
        drag(win.canvas, (130, 100), (160, 130))
        after = win.doc.selection.rect if win.doc.selection else None
        check('selection handle resizes',
              before == (30, 30, 100, 70) and after is not None
              and after[2] >= 120 and after[3] >= 90, (before, after))
        QTest.keyClick(win.canvas, Qt.Key.Key_Escape)
        app.processEvents()

        # Fill tool
        win._set_tool('fill')
        win.canvas.set_colors(color1=(255, 0, 0))
        click(win.canvas, 300, 200)
        check('bucket fill mouse', pix(win.doc.surface, 300, 200) == (255, 0, 0, 255),
              pix(win.doc.surface, 300, 200))

        # Picker
        win.canvas.set_colors(color1=(0, 0, 0))
        win._set_tool('picker')
        click(win.canvas, 300, 200)
        check('picker updates colour 1', win.canvas.color1 == (255, 0, 0),
              win.canvas.color1)

        # Shape tool commits a rectangle
        win._set_tool('rectangle')
        win.canvas.set_colors(color1=(0, 0, 0))
        win.canvas.line_width = 4
        drag(win.canvas, (200, 250), (300, 320))
        check('rectangle shape committed',
              pix(win.doc.surface, 250, 250)[:3] != (255, 255, 255),
              pix(win.doc.surface, 250, 250))

        # Text tool on a blank area
        win._clear_image()
        win.canvas.set_colors(color1=(0, 0, 0))
        win._set_tool('text')
        click(win.canvas, 20, 150)
        check('text editor opened', win.canvas._text_editor is not None)
        if win.canvas._text_editor is not None:
            win.canvas._text_editor.setPlainText('Qt 文本')
            QTest.keyClick(win.canvas._text_editor, Qt.Key.Key_Return,
                           Qt.KeyboardModifier.ControlModifier)
            app.processEvents()
            check('text editor closed', win.canvas._text_editor is None)
            region = [pix(win.doc.surface, x, y) for x in range(20, 150, 2)
                      for y in range(150, 190, 2)]
            check('text committed to image',
                  any(c[0] < 100 and c[3] > 0 for c in region), region[:5])

        # Eraser paints colour 2 on an opaque document
        win._set_tool('eraser')
        win.canvas.set_colors(color2=(255, 255, 255))
        win.canvas.line_width = 8
        drag(win.canvas, (300, 200), (340, 200))
        check('eraser clears with colour 2',
              pix(win.doc.surface, 320, 200) == (255, 255, 255, 255),
              pix(win.doc.surface, 320, 200))

        # Zoom with magnifier
        zoom_before = win.canvas.zoom
        win._set_tool('magnifier')
        click(win.canvas, 100, 100)
        check('magnifier zooms in', win.canvas.zoom > zoom_before,
              (zoom_before, win.canvas.zoom))
        win.canvas.set_zoom(1.0)

        # Keyboard zoom shortcuts via actions
        win.actions['zoom-in'].trigger()
        app.processEvents()
        check('zoom action', win.canvas.zoom == 2.0, win.canvas.zoom)
        win.canvas.set_zoom(1.0)

        # Undo with Ctrl+Z through the action
        win.actions['undo'].trigger()
        app.processEvents()
        check('undo action', win.doc.can_redo())

        # Delete with Delete key
        win.canvas.select_all()
        QTest.keyClick(win.canvas, Qt.Key.Key_Delete)
        app.processEvents()
        check('delete key', win.doc.selection is None)
        win._force_close = True
        win.close()

        print('RESULTS', sum(1 for _, ok, _ in results if ok), '/', len(results))
        fails = [n for n, ok, _ in results if not ok]
        print('FAILED', fails)
        return 0 if not fails else 1
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
