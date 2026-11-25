#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Keeps the site loadable on low-memory devices and old browsers.

    tools/check-site.py SITE                every .html of a made site (tools/build-site.sh's _site)
    tools/check-site.py [FILE.html...]      every .html of the repository when none is named (not book/, the
                                            book's sources, nor tests/)
    tools/check-site.py --drop SITE         as SITE, then a part of the site with a page that fails (a manual's
                                            folder, manual/snx, manual/cs-book) is put out of it, a page in its
                                            place saying why (tools/stand-in.py): the exit status is 3 when one
                                            is, and 1 when a page of no such part fails (the main page)

A page fails on JavaScript (a <script>, an on... attribute, a javascript: link), on CSS (a <style>, a style
attribute, a stylesheet <link>), on a size over 16 KB (a second to load at 128 kbit/s), and on an element an old
browser does not draw (canvas, video, audio, picture, iframe, an inline svg). Each failure is printed as
FILE:LINE: what; the exit status is 1 when there is one.

The ISA manuals (manual/, tools/gen-manual.py) have the one exception: its pages may link its stylesheet and load
scripts from files (<script src>: its search and the search's data), which they read without. Nothing inline there
either, and the stylesheet and the search stay small (MANUAL_CAPS).

The math book (manual/cs-book/) goes further, as its formulas and figures need it: pages up to 64 KB, inline
svg figures, its own stylesheet (book.css) and MathJax, which typesets the TeX of its formulas and is loaded from
BOOK_MATHJAX alone. Its pages read without them too: the TeX is plain text.
"""
import glob
import html.parser
import os
import sys

MAX_BYTES = 16 * 1024
NEW_ELEMENTS = {'canvas', 'video', 'audio', 'picture', 'iframe', 'svg'}
MANUAL = 'manual/'
MANUAL_CAPS = {'manual/manual.css': 4 * 1024, 'manual/search.js': 8 * 1024, 'manual/cs-book/book.css': 4 * 1024}
BOOK = 'manual/cs-book/'
BOOK_MAX_BYTES = 64 * 1024
BOOK_MATHJAX = 'https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js'


class Page(html.parser.HTMLParser):
    def __init__(self, path, manual=False, book=False):
        super().__init__(convert_charrefs=True)
        self.path, self.failures, self.manual, self.book, self.in_script = path, [], manual, book, False

    def fail(self, what):
        self.failures.append(f'{self.path}:{self.getpos()[0]}: {what}')

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            src = dict(attrs).get('src') or ''
            if not self.manual or not src:
                self.fail('a <script>: the site has no JavaScript' if not self.manual else
                          'an inline <script>: the manual loads its scripts from files')
            elif '://' in src and not (self.book and src == BOOK_MATHJAX):
                self.fail(f'a script from {src}: the manual\'s scripts are its own (the book: and MathJax)')
            self.in_script = True
        if tag == 'style':
            self.fail('a <style>: the site has no CSS')
        if tag in NEW_ELEMENTS and not (self.book and tag == 'svg'):
            self.fail(f'a <{tag}>, which an old browser does not draw')
        for name, value in attrs:
            value = (value or '').strip().lower()
            if name.startswith('on'):
                self.fail(f'an {name} attribute: the site has no JavaScript')
            elif name == 'style':
                self.fail('a style attribute: the site has no CSS')
            elif name in ('href', 'src', 'action') and value.startswith('javascript:'):
                self.fail('a javascript: link: the site has no JavaScript')
        if tag == 'link' and 'stylesheet' in (dict(attrs).get('rel') or '').lower():
            href = dict(attrs).get('href') or ''
            if not self.manual or not (href.endswith('manual.css') if not self.book else href == 'book.css'):
                self.fail('a stylesheet: the site has no CSS' if not self.manual else
                          'a stylesheet other than ' + ('book.css' if self.book else 'manual.css'))

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False

    def handle_data(self, data):
        if self.in_script and data.strip():
            self.fail('an inline <script>: the manual loads its scripts from files')


def check(path, root):
    data = open(path, 'rb').read()
    rel = os.path.relpath(os.path.abspath(path), root).replace(os.sep, '/')
    book = ('/' + rel).find('/' + BOOK) >= 0
    page = Page(path, ('/' + rel).find('/' + MANUAL) >= 0, book)
    cap = BOOK_MAX_BYTES if book else MAX_BYTES
    if len(data) > cap:
        page.failures.append(f'{path}:1: {len(data)} bytes, over {cap}')
    page.feed(data.decode('utf-8', 'replace'))
    page.close()
    return page.failures


def part_of(rel):
    """The part of the site a page is of: manual/X for a page in a manual's folder, manual for the manuals' index
    (manual/index.html), None for the site's own pages, which no generator makes"""
    bits = rel.split('/')
    if bits[0] != 'manual' or len(bits) < 2:
        return None
    return 'manual' if len(bits) == 2 else 'manual/' + bits[1]


def drop(site):
    import importlib.util
    sys.dont_write_bytecode = True  # no __pycache__ in tools/
    spec = importlib.util.spec_from_file_location('stand_in', os.path.join(os.path.dirname(__file__), 'stand-in.py'))
    stand_in = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stand_in)
    root = os.path.abspath(site)
    files = sorted(glob.glob(os.path.join(root, '**', '*.html'), recursive=True))
    bad, fatal = {}, []
    for path in files:
        failures = check(path, root)
        if not failures:
            continue
        part = part_of(os.path.relpath(path, root).replace(os.sep, '/'))
        if part is None:
            fatal += failures
        else:
            bad.setdefault(part, []).extend(failures)
    for part, failures in sorted(bad.items(), key=lambda kv: kv[0] == 'manual'):  # the manuals' index last
        print('\n'.join(failures))
        print(f'check-site: {part}/ is put out of the site: {len(failures)} failure(s)')
        stand_in.stand_in(root, part, f'{len(failures)} of its pages failed tools/check-site.py, the first: '
                                      f'{os.path.relpath(failures[0], root)}')
    if fatal:
        print('\n'.join(fatal))
        return 1
    return 3 if bad else 0


def main(argv):
    if argv[:1] == ['--drop'] and len(argv) == 2:
        return drop(argv[1])
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    site = len(argv) == 1 and os.path.isdir(argv[0])
    if site:
        root = os.path.abspath(argv[0])
        files = sorted(glob.glob(os.path.join(root, '**', '*.html'), recursive=True))
    else:
        skip = [os.path.join(root, d) + os.sep for d in ('tests', 'book', '_site')]
        files = argv or sorted(f for f in glob.glob(os.path.join(root, '**', '*.html'), recursive=True)
                               if not any(f.startswith(d) for d in skip))
    failures = [f for path in files for f in check(path, root)]
    for rel, cap in MANUAL_CAPS.items():
        path = os.path.join(root, rel)
        if (site or not argv) and os.path.exists(path) and os.path.getsize(path) > cap:
            failures.append(f'{path}:1: {os.path.getsize(path)} bytes, over {cap}: the manual\'s {rel[len(MANUAL):]} stays small')
    print('\n'.join(failures) if failures else f'{len(files)} page(s): no JavaScript, no CSS (the manual: its own, from files), small, drawn by old browsers')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
