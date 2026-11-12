# SPDX-License-Identifier: GPL-3.0-or-later
"""Application-level feature tests (preferences, clipboard, QAT, actions)."""
import os
import sys
import tempfile
import traceback

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
config = tempfile.mkdtemp()
data = tempfile.mkdtemp()
os.environ['XDG_CONFIG_HOME'] = config
os.environ['XDG_DATA_HOME'] = data
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QKeySequence
from PyQt6.QtTest import QTest

app = QApplication([])

from mspaint.app import PaintWindow
from mspaint.document import Selection
from mspaint import dialogs as dialogs_module

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
        # Actions / shortcuts
        for name in ('new', 'open', 'save', 'save-as', 'print', 'undo', 'redo',
                     'cut', 'copy', 'paste', 'select-all', 'crop', 'resize',
                     'properties', 'invert-colors', 'clear-image', 'zoom-in',
                     'zoom-out', 'fullscreen', 'help', 'grid', 'ruler', 'bold',
                     'italic', 'font-underline'):
            check('action ' + name, name in win.actions)
        check('save shortcut', win.actions['save'].shortcut() == QKeySequence('Ctrl+S'),
              win.actions['save'].shortcut().toString())
        check('save-as shortcut', win.actions['save-as'].shortcut() == QKeySequence('F12'),
              win.actions['save-as'].shortcut().toString())

        # No two actions may share a shortcut: Qt would make it ambiguous and
        # silently stop firing (this used to break Ctrl+E).
        duplicate_shortcuts = []
        seen = {}
        for action in win.findChildren(QAction):
            text = action.shortcut().toString()
            if not text:
                continue
            if text in seen:
                duplicate_shortcuts.append((text, seen[text], action.text()))
            seen[text] = action.text()
        check('no duplicate shortcuts', not duplicate_shortcuts, duplicate_shortcuts)

        # Keyboard commands fire through the window actions
        win.activateWindow()
        win.canvas.setFocus()
        app.processEvents()
        QTest.keyClick(win.canvas, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        prop_dialogs = [x for x in QApplication.topLevelWidgets()
                        if isinstance(x, dialogs_module.AttributesDialog)]
        check('Ctrl+E opens properties', len(prop_dialogs) == 1, len(prop_dialogs))
        for dialog in prop_dialogs:
            dialog.close()
        win.activateWindow()
        win.canvas.setFocus()
        app.processEvents()
        QTest.keyClick(win.canvas, Qt.Key.Key_PageUp, Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        check('Ctrl+PgUp zooms in', win.canvas.zoom == 2.0, win.canvas.zoom)
        QTest.keyClick(win.canvas, Qt.Key.Key_PageDown, Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        check('Ctrl+PgDown zooms out', win.canvas.zoom == 1.0, win.canvas.zoom)
        win.activateWindow()
        win.canvas.setFocus()
        app.processEvents()
        grid_before = win.cb_grid.isChecked()
        QTest.keyClick(win.canvas, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        check('Ctrl+G toggles grid', win.cb_grid.isChecked() != grid_before)
        win.cb_grid.setChecked(grid_before)

        # Colours and palette
        win._palette_left('#ED1C24')
        check('palette colour 1', win.canvas.color1 == (237, 28, 36), win.canvas.color1)
        win._palette_right('#00A2E8')
        check('palette colour 2', win.canvas.color2 == (0, 162, 232), win.canvas.color2)

        # Zoom slider
        win.zoom_scale.setValue(250)
        app.processEvents()
        check('zoom slider', abs(win.canvas.zoom - 2.5) < 1e-6, win.canvas.zoom)
        win.canvas.set_zoom(1.0)

        # Text style state survives to rendering
        win._set_tool('text')
        win.canvas.text_bold = True
        win.canvas.text_italic = True
        win.canvas.text_underline = True
        win.canvas.text_size = 24
        win.canvas._begin_text(10, 10)
        if win.canvas._text_editor is not None:
            win.canvas._text_editor.setPlainText('Style')
            win.canvas._commit_text()
        check('text style commit', win.doc.can_undo())

        # Clipboard round trip
        win.canvas.select_all()
        win._copy_clicked()
        win.canvas.delete_selection()
        win._paste_clicked()
        app.processEvents()
        check('clipboard paste creates selection',
              win.doc.selection is not None and win.doc.selection.w == win.doc.width,
              win.doc.selection.rect if win.doc.selection else None)
        win.canvas.commit_floating()

        # Save to path via application helper and add recent
        path = os.path.join(tempfile.mkdtemp(), 'features.png')
        win._save_to_path(path, fmt='png')
        check('application save', os.path.exists(path) and not win.doc.dirty)
        check('recent file recorded', path in win.recent_files, win.recent_files[:2])

        # Preferences: QAT + theme persist into a second window
        win._set_theme_mode('dark')
        win._toggle_qat_pin('new', True)
        app.processEvents()
        win._force_close = True
        win.close()

        second = PaintWindow()
        check('theme preference persisted', second.theme_mode == 'dark', second.theme_mode)
        check('qat preference persisted', 'new' in second.qat_pinned, second.qat_pinned)
        check('recent persisted', path in second.recent_files, second.recent_files[:2])
        second.show()
        app.processEvents()

        # View toggles and status bar
        second._toggle_status(False)
        check('status hidden', not second.statusbar.isVisible())
        second._toggle_status(True)
        check('status visible', second.statusbar.isVisible())
        second._toggle_thumbnail()
        check('thumbnail panel visible', second.thumb_panel.isVisible())
        second._toggle_thumbnail()
        second._switch_ribbon('view')
        check('view ribbon switched', second.view_ribbon.isVisible()
              and not second.home_ribbon.isVisible())
        second._switch_ribbon('home')
        check('home ribbon switched', second.home_ribbon.isVisible())

        # Rotate / invert / clear / undo
        second._rotate('right')
        check('rotate image dims', (second.doc.width, second.doc.height) == (432, 768),
              (second.doc.width, second.doc.height))
        second._invert_colors()
        check('invert colours undoable', second.doc.can_undo())
        second._clear_image()
        check('clear image white',
              pix(second.doc.surface, 5, 5) == (255, 255, 255, 255),
              pix(second.doc.surface, 5, 5))
        second._undo()
        second._undo()
        second._undo()
        check('multi undo', second.doc.can_redo())

        # Resize and skew through document helpers used by the dialog
        second.doc.resize(200, 100)
        check('resize document', (second.doc.width, second.doc.height) == (200, 100))
        second.doc.skew(5, 0)
        check('skew document', second.doc.width > 200)

        # Every QAT menu kind constructs
        for kind in ('rotate', 'shapes', 'outline', 'fill', 'size', 'colors', 'theme'):
            menu = second._make_qat_menu(kind)
            check('qat menu ' + kind, menu is not None and len(menu.actions()) > 0,
                  len(menu.actions()) if menu else 0)

        # All registry commands can be pinned and unpinned
        keys = ['rotate', 'shapes', 'outline', 'fill-style', 'size', 'colors',
                'zoom-100', 'ruler', 'grid', 'statusbar', 'thumbnail', 'theme']
        for key in keys:
            second._toggle_qat_pin(key, True)
        app.processEvents()
        check('extended QAT commands pinned',
              all(k in second.qat_buttons for k in keys), second.qat_pinned)
        for key in keys:
            second._toggle_qat_pin(key, False)
        app.processEvents()
        check('extended QAT commands unpinned',
              all(k not in second.qat_pinned for k in keys), second.qat_pinned)

        # After switching from dark to light, icon-only controls must not keep
        # light icons (they used to blend into the light toolbar).
        win2 = PaintWindow()
        win2.show()
        app.processEvents()
        win2._set_theme_mode('dark')
        app.processEvents()
        win2._set_theme_mode('light')
        app.processEvents()

        def icon_luminance(button):
            image = button.icon().pixmap(32, 32).toImage()
            values = []
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    if color.alpha() > 20:
                        values.append((color.red() + color.green() + color.blue()) / 3)
            return sum(values) / len(values) if values else 255

        status_buttons = [b for b in win2.statusbar.findChildren(
            __import__('PyQt6.QtWidgets', fromlist=['QToolButton']).QToolButton)
            if b.icon().isNull() is False]
        arrow_buttons = [b for b in win2.findChildren(
            __import__('PyQt6.QtWidgets', fromlist=['QToolButton']).QToolButton)
            if b.property('paint_icon') in ('chevron_up', 'chevron_down', 'dropdown')]
        check('status zoom icons darken for light theme',
              all(icon_luminance(b) < 180 for b in status_buttons),
              [round(icon_luminance(b)) for b in status_buttons])
        check('navigation icons darken for light theme',
              all(icon_luminance(b) < 180 for b in arrow_buttons),
              [round(icon_luminance(b)) for b in arrow_buttons])
        check('light palette uses dark text',
              win2.palette().color(win2.palette().ColorRole.WindowText).lightness() < 128,
              win2.palette().color(win2.palette().ColorRole.WindowText).name())
        win2._force_close = True
        win2.close()
        app.processEvents()

        # Follow-system theme mode reacts to GTK_THEME changes
        second._set_theme_mode('auto')
        old_gtk = os.environ.get('GTK_THEME')
        os.environ['GTK_THEME'] = 'Adwaita-dark'
        second._poll_system_theme()
        app.processEvents()
        check('auto theme follows dark', second.dark_mode)
        os.environ['GTK_THEME'] = 'Adwaita'
        second._poll_system_theme()
        app.processEvents()
        check('auto theme follows light', not second.dark_mode)
        if old_gtk is None:
            os.environ.pop('GTK_THEME', None)
        else:
            os.environ['GTK_THEME'] = old_gtk

        # Printing to PDF exercises the page renderer without a print dialog
        from PyQt6.QtPrintSupport import QPrinter
        pdf = os.path.join(tempfile.mkdtemp(), 'print.pdf')
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(pdf)
        second._draw_print_page(printer)
        check('print to PDF', os.path.exists(pdf) and os.path.getsize(pdf) > 0,
              os.path.getsize(pdf) if os.path.exists(pdf) else 0)

        second._force_close = True
        second.close()
        print('RESULTS', sum(1 for _, ok, _ in results if ok), '/', len(results))
        fails = [n for n, ok, _ in results if not ok]
        print('FAILED', fails)
        return 0 if not fails else 1
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
