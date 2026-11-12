# SPDX-License-Identifier: GPL-3.0-or-later
"""Dialog behaviour tests."""
import os
import sys
import tempfile
import traceback

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['XDG_CONFIG_HOME'] = tempfile.mkdtemp()
os.environ['XDG_DATA_HOME'] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QDialogButtonBox

app = QApplication([])

from mspaint.app import PaintWindow
from mspaint import dialogs
from mspaint.document import Document

results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


def main():
    win = PaintWindow()
    try:
        # Resize dialog percent
        got = {}
        d = dialogs.ResizeDialog(win, 200, 100, lambda *a: got.update(args=a))
        d.hspin.setValue(50)
        d.apply()
        check('resize percent', got['args'][:2] == (100, 50), got)
        d.deleteLater()

        # Resize dialog pixels + aspect ratio
        got = {}
        d = dialogs.ResizeDialog(win, 200, 100, lambda *a: got.update(args=a))
        d.unit_px.setChecked(True)
        d.hspin.setValue(300)
        check('resize aspect ratio keeps ratio', d.vspin.value() == 150, d.vspin.value())
        d.skew_h.setValue(10)
        d.apply()
        check('resize pixel + skew', got['args'] == (300, 150, 10, 0), got)
        d.deleteLater()

        # Attributes dialog
        got = {}
        d = dialogs.AttributesDialog(win, win.doc, lambda *a: got.update(args=a))
        d.wspin.setValue(100)
        d.hspin.setValue(80)
        d.units.setCurrentIndex(1)
        d.bw.setChecked(True)
        d.transparent.setChecked(True)
        d.apply()
        check('attributes dialog', got['args'] == (9600, 7680, False, True), got)
        d.deleteLater()

        # Save options
        got = {}
        d = dialogs.SaveOptionsDialog(win, 'bmp', lambda *a: got.update(args=a))
        d.formats.setCurrentIndex(2)
        d.depths.setCurrentIndex(0)
        d.apply()
        check('save options', got['args'] == ('bmp', 1), got)
        d.deleteLater()

        # Page setup
        got = {}
        d = dialogs.PageSetupDialog(win, win.page_settings, lambda *a: got.update(args=a))
        d.landscape.setChecked(True)
        d.scale.setValue(150)
        d.center.setChecked(False)
        d.apply()
        settings = got['args'][0]
        check('page setup', settings['landscape'] and settings['scale'] == 150
              and not settings['center'], settings)
        d.deleteLater()

        # About dialog
        d = dialogs.AboutDialog(win)
        check('about dialog', d.windowTitle() != '')
        d.deleteLater()

        # BaseDialog buttons are localised and connected
        d = dialogs.BaseDialog(win, 'x')
        box = d.findChild(QDialogButtonBox)
        check('base dialog buttons', box is not None and
              box.button(QDialogButtonBox.StandardButton.Ok).text() in ('确定', 'OK'))
        d.deleteLater()

        # Message dialog builds a QMessageBox without exec'ing
        msg = dialogs.MessageDialog(win, 'hello', 'world')
        check('message dialog object', msg.text == 'hello')
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
