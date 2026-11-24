#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Makes the book From Derivatives to Attention (book/) into its pages.

    tools/gen-book.py [BOOK] [OUT] [--cc CC]       book/ and _site/manual/cs-book by default

A page's source is its body: book/index.html, book/refs.html and a chapter book/NN-name.html each. The head (its
title from the <h1>, book.css, MathJax when the page has TeX) and a chapter's lines to the contents, the chapter
before and the one after are made here, the same for every page.

A program a chapter shows is a marker in its body, <!--prog NAME.c-->, its source book/NN-name/NAME.c beside the
output it printed, NAME.out. Each is compiled (CC, C99, -Wall -Wextra -Werror) and run in its directory, and what
it prints must be NAME.out, or the book is not made: the text quotes those numbers. <!--prog NAME.c recorded-->
is a program whose output depends on the machine (a timing, rand(), a C library's last digits): it is compiled
but not run, its NAME.out is what it printed where RECORDED says, and the page says so. "freebsd" after it is a
program of FreeBSD's API (fpsetprec), compiled only there. <!--out NAME.c ...--> shows only what the program
prints, the program staying beside the page. OTHER.out after the name is its output when it is not NAME.out (the
same program built otherwise, recorded).
"""
import glob
import html
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile

BOOK_TITLE = 'From Derivatives to Attention'
MATHJAX = 'https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js'
RECORDED = 'FreeBSD 15.1 on amd64 (Core i5-9400), clang 19'
CFLAGS = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-O2']
PROG = re.compile(r'<!--(prog|out) ([\w.-]+\.c)((?: [\w.-]+)*)-->')


def fail(what):
    sys.exit(f'gen-book: {what}')


def text(fragment):
    return html.unescape(re.sub(r'<[^>]+>', '', fragment)).strip()


def head(title, body):
    math = '\\(' in body or '\\[' in body
    return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<meta name="color-scheme" content="light dark">\n'
            f'<title>{html.escape(title, quote=False)}</title>\n<link rel="stylesheet" href="book.css">\n'
            + (f'<script src="{MATHJAX}" async></script>\n' if math else '') + '</head>\n<body>\n')


def program(book, chapter, kind, name, flags, cc, work):
    src = os.path.join(book, chapter, name)
    outs = [f for f in flags if f.endswith('.out')]
    flags = [f for f in flags if not f.endswith('.out')]
    out = os.path.join(book, chapter, outs[0]) if outs else src[:-2] + '.out'
    if not os.path.isfile(src) or not os.path.isfile(out):
        fail(f'{chapter}.html shows {name}: {chapter}/{name} and {os.path.basename(out)} must both be there')
    code, printed = open(src).read(), open(out).read()
    unknown = set(flags) - {'recorded', 'freebsd'}
    if unknown:
        fail(f'{chapter}.html: <!--prog {name}--> has {", ".join(sorted(unknown))}, not recorded or freebsd')
    if 'freebsd' not in flags or platform.system() == 'FreeBSD':
        exe = os.path.join(work, chapter + '-' + name[:-2])
        r = subprocess.run([cc] + CFLAGS + ['-o', exe, src, '-lm'], capture_output=True, text=True)
        if r.returncode:
            fail(f'{chapter}/{name} does not compile without warnings:\n{r.stderr}')
        if 'recorded' not in flags:
            r = subprocess.run([exe], cwd=os.path.dirname(src), capture_output=True, text=True, timeout=600)
            if r.returncode or r.stdout.rstrip('\n') != printed.rstrip('\n'):
                fail(f'{chapter}/{name} (status {r.returncode}) printed\n{r.stdout}{r.stderr}\nnot its .out:\n'
                     f'{printed}\n(the text quotes it: make the two agree, or mark the program recorded if what '
                     'it prints depends on the machine)')
    page = f'<pre class="out">{html.escape(printed.rstrip(chr(10)), quote=False)}</pre>'
    if kind == 'prog':
        page = f'<pre><code>{html.escape(code.rstrip(chr(10)), quote=False)}</code></pre>\n' + page
    if 'recorded' in flags:
        page += (f'\n<p class="rec">Printed on {RECORDED}. It depends on the machine: elsewhere the timings, '
                 'the random numbers or the last digits differ.</p>')
    return page


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cc = 'cc'
    if '--cc' in argv:
        i = argv.index('--cc')
        cc = argv[i + 1]
        del argv[i:i + 2]
    book = argv[0] if argv else os.path.join(root, 'book')
    out = argv[1] if len(argv) > 1 else os.path.join(root, '_site', 'manual', 'cs-book')
    chapters = sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(book, '[0-9][0-9]-*.html')))
    bodies = {c: open(os.path.join(book, c + '.html')).read() for c in chapters + ['index', 'refs']}
    titles = {}
    for c in chapters + ['refs']:
        m = re.search(r'<h1>(.*?)</h1>', bodies[c], re.S)
        if not m:
            fail(f'{c}.html has no <h1>')
        titles[c] = text(m.group(1))
    os.makedirs(out, exist_ok=True)
    shutil.copyfile(os.path.join(book, 'book.css'), os.path.join(out, 'book.css'))
    crumbs = f'<a href="../../">ScarletNX</a> / '
    with tempfile.TemporaryDirectory() as work:
        for c in chapters + ['index', 'refs']:
            body = PROG.sub(lambda m: program(book, c, m.group(1), m.group(2), m.group(3).split(), cc, work),
                            bodies[c])
            if c == 'index':
                page = head(f'{BOOK_TITLE}: mathematics for programmers', body)
                page += f'<p class="nav">{crumbs}{BOOK_TITLE}</p>\n' + body
            elif c == 'refs':
                page = head(f'References - {BOOK_TITLE}', body)
                page += f'<p class="nav">{crumbs}<a href="./">{BOOK_TITLE}</a> / References</p>\n' + body
            else:
                k = chapters.index(c)
                prev = (f'<a rel="prev" href="{chapters[k - 1]}.html">&larr; {html.escape(titles[chapters[k - 1]], quote=False)}</a>'
                        if k else '')
                nxt = chapters[k + 1] if k + 1 < len(chapters) else 'refs'
                nxt = f'<a rel="next" href="{nxt}.html">{html.escape(titles[nxt], quote=False)} &rarr;</a>'
                links = ' &middot; '.join(x for x in (prev, nxt) if x)
                page = head(f'{titles[c]} - {BOOK_TITLE}', body)
                page += (f'<p class="nav">{crumbs}<a href="./">{BOOK_TITLE}</a> / Chapter {k + 1} &middot; {links}</p>\n'
                         + body + f'<hr>\n<p class="nav"><a href="./">Contents</a> &middot; {links}</p>\n')
            page += '</body>\n</html>\n'
            open(os.path.join(out, c + '.html'), 'w').write(page)
    print(f'{len(chapters)} chapter(s), the contents and the references: {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
