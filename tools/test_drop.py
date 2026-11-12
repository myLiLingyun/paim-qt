# SPDX-License-Identifier: GPL-3.0-or-later
"""File drag-and-drop entry point tests."""
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
from PyQt6.QtGui import QPainter, QColor

app = QApplication([])

import mspaint.app as app_module
from mspaint.app import PaintWindow
from mspaint.document import Document

results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


class FakeMessage:
    def __init__(self, *args, **kwargs):
        pass

    def present(self):
        pass


def main():
    win = PaintWindow()
    win.show()
    app.processEvents()
    try:
        folder = tempfile.mkdtemp()
        image = Document(40, 30)
        p = QPainter(image.surface)
        p.fillRect(0, 0, 40, 30, QColor(0, 128, 0))
        p.end()
        path = os.path.join(folder, 'dropped.png')
        image.save(path)
        note = os.path.join(folder, 'notes.txt')
        with open(note, 'w') as fh:
            fh.write('not an image')

        check('open dropped image', win._open_dropped_files([path]) is True)
        app.processEvents()
        check('dropped image loaded', win.doc.width == 40 and win.doc.height == 30,
              (win.doc.width, win.doc.height))
        check('dropped image recent', os.path.abspath(path) in win.recent_files)

        # Invalid files show a message instead of raising; avoid a modal box.
        original = app_module.MessageDialog
        app_module.MessageDialog = FakeMessage
        try:
            result = win._open_dropped_files([note])
            check('invalid drop rejected', result is False)
        finally:
            app_module.MessageDialog = original

        # Multiple URLs: the image wins over the text file.
        win.doc.dirty = False
        check('multiple files picks image',
              win._open_dropped_files([note, path]) is True)

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
