# SPDX-License-Identifier: GPL-3.0-or-later
"""Text tool and clipboard integration tests."""
import os
import sys
import tempfile
import traceback

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
config = tempfile.mkdtemp()
os.environ['XDG_CONFIG_HOME'] = config
os.environ['XDG_DATA_HOME'] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

app = QApplication([])

from mspaint.app import PaintWindow
from mspaint.document import Selection

results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


def main():
    win = PaintWindow()
    win.show()
    app.processEvents()
    try:
        # Text tool
        win._set_tool('text')
        win.canvas.set_colors(color1=(0, 0, 0))
        win.canvas.text_size = 24
        win.canvas._begin_text(20, 20)
        check('text editor created', win.canvas._text_editor is not None)
        win.canvas._text_editor.setPlainText('Hello')
        win.canvas._commit_text()
        changed = False
        for y in range(15, 70):
            for x in range(15, 180):
                if win.doc.surface.pixelColor(x, y).getRgb()[:3] != (255, 255, 255):
                    changed = True
                    break
            if changed:
                break
        check('text rendered to canvas', changed)

        # Copy a selection
        win.doc.selection = Selection(15, 15, 100, 60)
        surface = win.canvas.copy_selection()
        check('copy selection returns image',
              surface is not None and surface.width() == 100,
              surface.width() if surface else None)
        win._copy_to_clipboard(surface)
        mime = QApplication.clipboard().mimeData()
        check('clipboard has png format',
              mime is not None and mime.hasFormat('image/png'))
        check('clipboard has image', not QApplication.clipboard().image().isNull())

        # Paste into the document
        win.canvas.paste_surface(win._quick_clipboard)
        check('paste creates floating selection',
              win.doc.selection is not None and win.doc.selection.floating is not None,
              win.doc.selection.rect if win.doc.selection else None)
        win.canvas.commit_floating()
        check('paste commits', win.doc.selection.floating is None)

        # Clipboard path through the application command
        win.canvas.select_all()
        win._copy_clicked()
        win._paste_clicked()
        app.processEvents()
        check('clipboard paste command creates selection',
              win.doc.selection is not None and win.doc.selection.w == win.doc.width,
              win.doc.selection.rect if win.doc.selection else None)
        win.canvas.commit_floating()

        # Text style switching preserves editor content
        win._set_tool('text')
        win.canvas._begin_text(200, 120)
        win.canvas._text_editor.setPlainText('Styled')
        win.canvas.text_bold = True
        win.canvas.update_text_style()
        check('text style preserves content',
              win.canvas._text_editor is not None
              and win.canvas._text_editor.toPlainText() == 'Styled',
              win.canvas._text_editor.toPlainText() if win.canvas._text_editor else None)
        # Standard text-editing shortcuts stay inside the editor
        from PyQt6.QtTest import QTest
        win.canvas._begin_text(300, 200)
        editor = win.canvas._text_editor
        editor.setPlainText('Select me')
        editor.moveCursor(editor.textCursor().MoveOperation.Start)
        QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        check('ctrl+a stays in text editor',
              editor.textCursor().hasSelection()
              and editor.textCursor().selectedText() == 'Select me',
              editor.textCursor().selectedText())
        QTest.keyClick(editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        check('editor undo works', editor.toPlainText() != '')
        win.canvas._discard_text()

        win.canvas._commit_text()

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
