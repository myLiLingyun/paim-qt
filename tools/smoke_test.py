# SPDX-License-Identifier: GPL-3.0-or-later
"""Programmatic UI smoke test for the Qt Paint clone (no mouse automation)."""
import os
import sys
import tempfile
import traceback

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['XDG_CONFIG_HOME'] = tempfile.mkdtemp()
os.environ['XDG_DATA_HOME'] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QColor, QPainter

app = QApplication([])

from mspaint.app import PaintWindow
from mspaint.document import Selection

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
        check('window visible', win.isVisible())
        check('file menu exists', win.file_tab.menu() is not None)
        check('home ribbon visible', win.home_ribbon.isVisible())
        check('shape gallery', len(win.shape_buttons) >= 15, len(win.shape_buttons))
        check('default document', (win.doc.width, win.doc.height) == (768, 432),
              (win.doc.width, win.doc.height))

        # File menu entries
        texts = [a.text() for a in win.file_tab.menu().actions()]
        check('file menu has save', any('保存' in t or 'Save' in t for t in texts), texts[:6])

        # Draw and mark dirty
        win.canvas.set_colors(color1=(0, 0, 0))
        win.canvas.set_tool('pencil')
        win.canvas._drag_begin(20, 20)
        win.canvas._drag_update(120, 120)
        win.canvas._drag_end(120, 120)
        win.doc.dirty = True
        win._update_title()
        check('title has dirty star', '*' in win.windowTitle(), win.windowTitle())

        path = os.path.join(tempfile.mkdtemp(), 'paim-smoke.png')
        win._save_to_path(path, fmt='png')
        check('save clears dirty', not win.doc.dirty, f'dirty={win.doc.dirty}')
        check('save clears title star', '*' not in win.windowTitle(), win.windowTitle())
        check('save file exists', os.path.exists(path), path)

        # Delete key clears selection to background
        win.canvas.select_all()
        QTest.keyClick(win.canvas, Qt.Key.Key_Delete)
        app.processEvents()
        check('delete key handled', win.doc.selection is None)
        check('delete fills white', pix(win.doc.surface, 0, 0) == (255, 255, 255, 255),
              pix(win.doc.surface, 0, 0))

        # Floating selection follows origin and commits
        win.canvas.select_all()
        win.doc.lift_selection()
        win.doc.selection.floating_origin = (123, 77)
        check('floating origin moved', win.doc.selection.floating_origin == (123, 77))
        win.canvas.commit_floating()
        check('selection geometry updated after move',
              (win.doc.selection.x, win.doc.selection.y) == (123, 77),
              win.doc.selection.rect)

        # Zoom / status
        win.canvas.set_zoom(2.0)
        app.processEvents()
        check('zoom updates canvas size', win.canvas.width() > 768, win.canvas.width())
        check('zoom label', win.zoom_label.text() == '200%', win.zoom_label.text())
        win.canvas.set_zoom(1.0)

        # Recent files
        win._add_recent(path)
        check('recent refresh', any(path == p for p in win.recent_files), win.recent_files)

        # Quick access pin/unpin
        before = list(win.qat_pinned)
        win._toggle_qat_pin('new', True)
        app.processEvents()
        check('qat pin', 'new' in win.qat_pinned)
        win._toggle_qat_pin('new', False)
        app.processEvents()
        check('qat unpin', win.qat_pinned == before)

        # Theme switching
        win._set_theme_mode('dark')
        app.processEvents()
        check('dark theme', win.dark_mode)
        win._set_theme_mode('light')
        app.processEvents()
        check('light theme', not win.dark_mode)

        # Dialogs construct without errors
        from mspaint import dialogs
        d = dialogs.ResizeDialog(win, 768, 432, lambda *a: None)
        d.deleteLater()
        d = dialogs.AttributesDialog(win, win.doc, lambda *a: None)
        d.deleteLater()
        d = dialogs.SaveOptionsDialog(win, 'bmp', lambda *a: None)
        d.deleteLater()
        d = dialogs.PageSetupDialog(win, win.page_settings, lambda *a: None)
        d.deleteLater()
        check('dialogs construct', True)

        # Open saved file
        win.load_path(path)
        check('open saved file', win.doc.width == 768, win.doc.width)

        # View toggles
        win._toggle_thumbnail()
        check('thumbnail visible', win.thumb_panel.isVisible())
        win._toggle_thumbnail()
        check('thumbnail hidden', not win.thumb_panel.isVisible())
        win.cb_ruler.setChecked(True)
        check('rulers visible', win.hruler.isVisible())
        win.cb_ruler.setChecked(False)

        # Fullscreen toggle does not raise
        try:
            win._toggle_fullscreen()
            app.processEvents()
            win._toggle_fullscreen()
            app.processEvents()
            check('fullscreen callable', True)
        except Exception as exc:
            check('fullscreen callable', False, repr(exc))

        # Close without prompt
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
