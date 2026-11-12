# SPDX-License-Identifier: GPL-3.0-or-later
"""Localisation tests."""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mspaint import i18n

results = []
_saved = {k: os.environ.get(k) for k in ('PAIM_LANG', 'LANGUAGE', 'LC_ALL',
                                         'LC_MESSAGES', 'LANG')}


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


def restore():
    for key, value in _saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    i18n.set_language(None)


def main():
    try:
        for key in _saved:
            os.environ.pop(key, None)
        i18n.set_language('zh')
        check('forced zh', i18n.language_is_zh() and i18n.tr('中文', 'English') == '中文')
        i18n.set_language('en')
        check('forced en', not i18n.language_is_zh()
              and i18n.tr('中文', 'English') == 'English')
        i18n.set_language(None)
        os.environ.pop('LANGUAGE', None)
        os.environ['LANG'] = 'zh_CN.UTF-8'
        check('env zh', i18n.language_is_zh())
        os.environ['LANG'] = 'en_US.UTF-8'
        check('env en', not i18n.language_is_zh())
        os.environ['PAIM_LANG'] = 'zh'
        check('paim_lang override', i18n.language_is_zh())
        os.environ['PAIM_LANG'] = 'en'
        check('paim_lang override en', not i18n.language_is_zh())
        os.environ.pop('PAIM_LANG', None)
        os.environ['LANGUAGE'] = 'zh_CN:en_US'
        check('language list', i18n.language_is_zh())
        print('RESULTS', sum(1 for _, ok, _ in results if ok), '/', len(results))
        fails = [n for n, ok, _ in results if not ok]
        print('FAILED', fails)
        return 0 if not fails else 1
    finally:
        restore()


if __name__ == '__main__':
    sys.exit(main())
