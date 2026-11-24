#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Makes ScarletNX's documentation (its docs/, Markdown) into pages of the site.

    tools/gen-docs.py DOCS [OUT] [--commit SHA]     OUT is _site/manual/snx beside tools/ when not named

Each DOCS/x/y.md is the page x/y.html; DOCS/README.md, the documents' index, is index.html. A page stays under the
site's 16 KB: a document too long for one is cut at its sections (## headings) into a page each, x/y/SECTION.html,
and x/y.html keeps what comes before its first section with a list of them; a section still too long is cut again
at its ### headings, and then between its blocks (a table repeats its header). Links between the documents, to
their headings (as GitHub names them), go to the page that has that heading; links out of docs/ go to the file in
ScarletNX's repository at the commit the documents are from (DOCS's checkout, or --commit).

The Markdown is what the documents use: ATX headings, paragraphs, lists (nested, numbered), fenced code, GitHub's
tables, links, `code`, **strong**, *emphasis*, ~~struck~~, <https://...> and bare https:// links, and HTML
comments (dropped). Any other HTML in them is text. Pages link the manuals' stylesheet (manual.css) and have no
script.
"""
import html
import os
import re
import subprocess
import sys

REPO = 'https://github.com/scarletnx/ScarletNX'
LIMIT = 14 * 1024          # a page's own text; the head, the lines to other pages and the foot fit in the rest
TITLE = 'ScarletNX documentation'


def fail(what):
    sys.exit(f'gen-docs: {what}')


# --- Markdown blocks -------------------------------------------------------------------------------------------

FENCE = re.compile(r'^( {0,3})(`{3,}|~{3,})\s*([^`\s]*)')
HEADING = re.compile(r'^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$')
HR = re.compile(r'^ {0,3}([-*_])(?:\s*\1){2,}\s*$')
ITEM = re.compile(r'^( *)([-*+]|\d{1,9}[.)])( +|$)(.*)$')
DELIM = re.compile(r'^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$')


def starts_block(line):
    return bool(FENCE.match(line) or HEADING.match(line) or ITEM.match(line) and ITEM.match(line).group(4).strip())


def cells(line):
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|') and not line.endswith('\\|'):
        line = line[:-1]
    out, cur, code = [], '', False
    i = 0
    while i < len(line):
        c = line[i]
        if c == '\\' and i + 1 < len(line) and line[i + 1] == '|':
            cur += '|'
            i += 2
            continue
        if c == '`':
            code = not code
        if c == '|' and not code:
            out.append(cur.strip())
            cur = ''
        else:
            cur += c
        i += 1
    out.append(cur.strip())
    return out


def blocks(lines):
    """[(kind, data)]: ('h', (level, text)), ('p', text), ('code', (lang, text)), ('hr', None),
    ('table', (aligns, head, rows)), ('list', (ordered, start, loose, [item blocks]))"""
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = FENCE.match(line)
        if m:
            indent, fence, lang = len(m.group(1)), m.group(2), m.group(3)
            body, i = [], i + 1
            while i < n and not re.match(r'^ {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*$', lines[i]):
                body.append(lines[i][indent:] if lines[i][:indent].strip() == '' else lines[i].lstrip())
                i += 1
            out.append(('code', (lang, '\n'.join(body))))
            i += 1
            continue
        m = HEADING.match(line)
        if m:
            out.append(('h', (len(m.group(1)), m.group(2))))
            i += 1
            continue
        if HR.match(line):
            out.append(('hr', None))
            i += 1
            continue
        if '|' in line and i + 1 < n and DELIM.match(lines[i + 1]) and '-' in lines[i + 1]:
            head = cells(line)
            aligns = []
            for c in cells(lines[i + 1]):
                c = c.strip()
                aligns.append('center' if c.startswith(':') and c.endswith(':') else
                              'right' if c.endswith(':') else 'left' if c.startswith(':') else '')
            rows, i = [], i + 2
            while i < n and lines[i].strip() and '|' in lines[i]:
                rows.append(cells(lines[i]))
                i += 1
            out.append(('table', (aligns, head, rows)))
            continue
        m = ITEM.match(line)
        if m and (m.group(4).strip() or (i + 1 < n and lines[i + 1].strip())):
            i = list_block(lines, i, out)
            continue
        para = [line.strip()]
        i += 1
        while i < n and lines[i].strip() and not starts_block(lines[i]) and not HR.match(lines[i]) and not (
                '|' in lines[i] and i + 1 < n and DELIM.match(lines[i + 1])):
            para.append(lines[i].strip() if not lines[i].endswith('  ') else lines[i].strip() + '  ')
            i += 1
        out.append(('p', '\n'.join(para)))
    return out


def list_block(lines, i, out):
    first = ITEM.match(lines[i])
    base = len(first.group(1))
    ordered = first.group(2)[0].isdigit()
    start = int(first.group(2)[:-1]) if ordered else 1
    items, loose, n = [], False, len(lines)
    while i < n:
        m = ITEM.match(lines[i])
        if not m or len(m.group(1)) > base + 3 or len(m.group(1)) < base or m.group(2)[0].isdigit() != ordered:
            break
        offset = len(m.group(1)) + len(m.group(2)) + max(1, min(len(m.group(3)), 4))
        body, i, blank = [m.group(4)], i + 1, False
        while i < n:
            line = lines[i]
            if not line.strip():
                body.append('')
                blank = True
                i += 1
                continue
            ind = len(line) - len(line.lstrip(' '))
            if ind >= offset:
                body.append(line[offset:])
            elif not blank and not starts_block(line) and not HR.match(line):
                body.append(line.strip())                       # a lazy continuation of its paragraph
            else:
                break
            blank = False
            i += 1
        while body and not body[-1].strip():
            body.pop()
        if blank and i < n and ITEM.match(lines[i]) and len(ITEM.match(lines[i]).group(1)) == len(m.group(1)):
            loose = True
        sub = blocks(body)
        if any(not b.strip() for b in body) and sum(1 for k, _ in sub if k == 'p') > 1:
            loose = True
        items.append(sub)
    out.append(('list', (ordered, start, loose, items)))
    return i


# --- inline ----------------------------------------------------------------------------------------------------

def slug(text):
    """GitHub's id for a heading: its text, lower case, without punctuation, spaces as hyphens"""
    t = re.sub(r'<[^>]+>', '', inline(text, lambda u: u))
    t = html.unescape(t).lower()
    t = re.sub(r'[^\w\- ]', '', t)
    return t.replace(' ', '-')


def inline(text, link):
    """text's HTML; link(url) gives a link's href"""
    keep = []

    def hold(s):
        keep.append(s)
        return f'\x00{len(keep) - 1}\x00'

    text = re.sub(r'(`+)(.+?)(?<!`)\1(?!`)', lambda m: hold('<code>' + html.escape(m.group(2).strip(), quote=False) + '</code>'),
                  text, flags=re.S)
    text = re.sub(r'\\([\\`*_{}\[\]()#+\-.!|~<>])', lambda m: hold(html.escape(m.group(1), quote=False)), text)
    text = re.sub(r'<(https?://[^>\s]+)>', lambda m: hold(f'<a href="{html.escape(m.group(1))}">{html.escape(m.group(1), quote=False)}</a>'), text)

    def a(m):
        label, url = m.group(1), m.group(2)
        return hold(f'<a href="{html.escape(link(url))}">') + label + hold('</a>')
    for _ in range(2):
        text = re.sub(r'\[((?:[^\[\]\x00]|\x00\d+\x00|\[[^\[\]]*\])*)\]\(<?([^)\s>]+)>?(?:\s+"[^"]*")?\)', a, text)
    text = re.sub(r'(?<![\w/"=])(https?://[^\s<>()\x00]*[^\s<>().,;:!?\x00\'"])',
                  lambda m: hold(f'<a href="{html.escape(m.group(1))}">{html.escape(m.group(1), quote=False)}</a>'), text)
    text = html.escape(text, quote=False)
    text = re.sub(r'\*\*(?=\S)(.+?)(?<=\S)\*\*', r'<strong>\1</strong>', text, flags=re.S)
    text = re.sub(r'(?<![\w])__(?=\S)(.+?)(?<=\S)__(?![\w])', r'<strong>\1</strong>', text, flags=re.S)
    text = re.sub(r'(?<![*\w])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![*\w])', r'<em>\1</em>', text, flags=re.S)
    text = re.sub(r'(?<![\w])_(?=\S)(.+?)(?<=\S)_(?![\w])', r'<em>\1</em>', text, flags=re.S)
    text = re.sub(r'~~(?=\S)(.+?)(?<=\S)~~', r'<del>\1</del>', text, flags=re.S)
    text = re.sub(r' {2,}\n', '<br>\n', text)
    while '\x00' in text:
        text = re.sub(r'\x00(\d+)\x00', lambda m: keep[int(m.group(1))], text)
    return text


# --- HTML ------------------------------------------------------------------------------------------------------

def render(bs, link, ids, tight=False):
    out = []
    for kind, d in bs:
        if kind == 'h':
            level, text = d
            out.append(f'<h{level} id="{ids.pop(0)}">{inline(text, link)}</h{level}>')
        elif kind == 'p':
            out.append(inline(d, link) if tight else f'<p>{inline(d, link)}</p>')
        elif kind == 'code':
            lang, text = d
            out.append(f'<pre><code>{html.escape(text, quote=False)}</code></pre>')
        elif kind == 'hr':
            out.append('<hr>')
        elif kind == 'table':
            out.append(table(d, link))
        elif kind == 'list':
            ordered, start, loose, items = d
            tag = 'ol' if ordered else 'ul'
            attr = f' start="{start}"' if ordered and start != 1 else ''
            lis = [f'<li>{render(item, link, ids, not loose)}</li>' for item in items]
            out.append(f'<{tag}{attr}>\n' + '\n'.join(lis) + f'\n</{tag}>')
    return '\n'.join(out)


def table(d, link, rows=None):
    aligns, head, all_rows = d
    rows = all_rows if rows is None else rows

    def row(cs, tag):
        cs = (cs + [''] * len(head))[:len(head)]
        return '<tr>' + ''.join(f'<{tag}{" align=" + chr(34) + a + chr(34) if a else ""}>{inline(c, link)}</{tag}>'
                                for c, a in zip(cs, aligns + [''] * len(head))) + '</tr>'
    return ('<table class="fields">\n' + row(head, 'th') + '\n' + '\n'.join(row(r, 'td') for r in rows) +
            '\n</table>')


# --- the documents ---------------------------------------------------------------------------------------------

def strip_comments(text):
    return re.sub(r'<!--.*?-->\n?', '', text, flags=re.S)


class Doc:
    def __init__(self, rel, text):
        self.rel = rel                                   # 'user/usage.md'
        self.page = 'index' if rel == 'README.md' else rel[:-3]
        self.blocks = blocks(strip_comments(text).split('\n'))
        heads = [d for k, d in self.blocks if k == 'h']
        self.title = re.sub(r'<[^>]+>', '', inline(heads[0][1], lambda u: u)) if heads else rel
        self.ids, seen = [], {}
        for level, text in self.heading_list():
            s = slug(text)
            k = seen.get(s, 0)
            seen[s] = k + 1
            self.ids.append(s if not k else f'{s}-{k}')

    def heading_list(self):
        found = []

        def walk(bs):
            for k, d in bs:
                if k == 'h':
                    found.append(d)
                elif k == 'list':
                    for item in d[3]:
                        walk(item)
        walk(self.blocks)
        return found


def size(bs, doc):
    ids = list(doc.ids) + ['x'] * 1000
    return len(render(bs, lambda u: 'x' * 40, ids).encode())


def heading_count(bs):
    n = 0
    for k, d in bs:
        if k == 'h':
            n += 1
        elif k == 'list':
            n += sum(heading_count(item) for item in d[3])
    return n


def split_blocks(bs, doc, limit):
    """bs cut between blocks into runs under limit; a table, a list or code too big alone is cut too"""
    parts, cur, cur_size = [], [], 0
    for b in bs:
        s = size([b], doc)
        if s > limit:
            for piece in cut_block(b, doc, limit):
                ps = size([piece], doc)
                if cur and cur_size + ps > limit:
                    parts.append(cur)
                    cur, cur_size = [], 0
                cur.append(piece)
                cur_size += ps
            continue
        if cur and cur_size + s > limit:
            parts.append(cur)
            cur, cur_size = [], 0
        cur.append(b)
        cur_size += s
    if cur:
        parts.append(cur)
    return parts


def cut_block(b, doc, limit):
    kind, d = b
    if kind == 'table':
        aligns, head, rows = d
        out, cur = [], []
        for r in rows:
            if cur and size([('table', (aligns, head, cur + [r]))], doc) > limit:
                out.append(('table', (aligns, head, cur)))
                cur = []
            cur.append(r)
        return out + [('table', (aligns, head, cur))]
    if kind == 'code':
        lang, text = d
        out, cur = [], []
        for line in text.split('\n'):
            if cur and len(html.escape('\n'.join(cur + [line])).encode()) > limit - 100:
                out.append(('code', (lang, '\n'.join(cur))))
                cur = []
            cur.append(line)
        return out + [('code', (lang, '\n'.join(cur)))]
    if kind == 'list':
        ordered, start, loose, items = d
        out, cur, first = [], [], start
        for item in items:
            if size([('list', (ordered, first, loose, [item]))], doc) > limit:
                if cur:                                      # an item too long alone: cut what it holds
                    out.append(('list', (ordered, first, loose, cur)))
                    first += len(cur)
                    cur = []
                for piece in split_blocks(item, doc, limit - 200):
                    out.append(('list', (ordered, first, loose, [piece])))
                first += 1
                continue
            if cur and size([('list', (ordered, first, loose, cur + [item]))], doc) > limit:
                out.append(('list', (ordered, first, loose, cur)))
                first += len(cur)
                cur = []
            cur.append(item)
        return out + ([('list', (ordered, first, loose, cur))] if cur else [])
    return [b]


def sections(bs, level):
    """bs as (lead, [(heading block, body)]) at headings of this level"""
    lead, secs = [], []
    for b in bs:
        if b[0] == 'h' and b[1][0] == level:
            secs.append((b, []))
        elif secs:
            secs[-1][1].append(b)
        else:
            lead.append(b)
    return lead, secs


def pages_of(doc):
    """[(page name, title, blocks, heading ids)] for one document"""
    bs = doc.blocks
    ids = list(doc.ids)
    if size(bs, doc) <= LIMIT:
        return [(doc.page, doc.title, bs, ids)]
    out = []
    lead, secs = sections(bs, 2)
    nlead = heading_count(lead)
    lead_ids, ids = ids[:nlead], ids[nlead:]
    toc = []
    if size(lead, doc) > LIMIT - 2048:                     # too long before its first section: pages of it
        chunks = split_blocks(lead, doc, LIMIT - 2048)
        lead = chunks[0]
        n = heading_count(lead)
        rest_ids, lead_ids = lead_ids[n:], lead_ids[:n]
        for j, chunk in enumerate(chunks[1:]):
            n = heading_count(chunk)
            out.append((f'{doc.page}/{j + 2}',
                        f'{doc.title} ({j + 2})', chunk, rest_ids[:n]))
            toc.append((out[-1][0], out[-1][1]))
            rest_ids = rest_ids[n:]
    used = set()
    for head, body in secs:
        name = ids[0]
        k, base = 1, (name if name != 'index' else 'index-section') or 'section'
        name = base
        while name in used:
            k += 1
            name = f'{base}-{k}'
        used.add(name)
        n = 1 + heading_count(body)
        sec_ids, ids = ids[:n], ids[n:]
        title = re.sub(r'<[^>]+>', '', inline(head[1][1], lambda u: u))
        page = f'{doc.page}/{name}'                       # README's: index/NAME, beside no document
        whole = [head] + body
        if size(whole, doc) <= LIMIT:
            chunks = [whole]
        else:
            sub_lead, subs = sections(body, 3)
            groups = [[head] + sub_lead] + [[h] + b for h, b in subs]
            chunks, cur = [], []
            for g in groups:
                if size(g, doc) > LIMIT:
                    if cur:
                        chunks.append(cur)
                        cur = []
                    chunks.extend(split_blocks(g, doc, LIMIT))
                elif cur and size(cur + g, doc) > LIMIT:
                    chunks.append(cur)
                    cur = list(g)
                else:
                    cur += g
            if cur:
                chunks.append(cur)
        for j, chunk in enumerate(chunks):
            n = heading_count(chunk)
            out.append((page if j == 0 else f'{page}-{j + 1}', title + (f' ({j + 1})' if j else ''),
                        chunk, sec_ids[:n]))
            sec_ids = sec_ids[n:]
        toc.append((page, title))
    first = lead + [('toc', toc)]
    out.insert(0, (doc.page, doc.title, first, lead_ids))
    return out


def relative(src_page, dst_page):
    src_dir = os.path.dirname(src_page)
    return os.path.relpath(dst_page + '.html', src_dir or '.').replace(os.sep, '/')


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    commit = None
    if '--commit' in argv:
        k = argv.index('--commit')
        commit = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]
    if not argv:
        fail('usage: tools/gen-docs.py DOCS [OUT] [--commit SHA]')
    docs = os.path.abspath(argv[0])
    out = argv[1] if len(argv) > 1 else os.path.join(root, '_site', 'manual', 'snx')
    if commit is None:
        r = subprocess.run(['git', '-C', docs, 'rev-parse', 'HEAD'], capture_output=True, text=True)
        commit = r.stdout.strip() if r.returncode == 0 else 'main'
    r = subprocess.run(['git', '-C', docs, 'rev-parse', '--show-prefix'], capture_output=True, text=True)
    prefix = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else 'docs/'
    files = sorted(os.path.relpath(os.path.join(d, f), docs).replace(os.sep, '/')
                   for d, _, fs in os.walk(docs) for f in fs)
    mds = [f for f in files if f.endswith('.md')]
    if 'README.md' not in mds:
        fail(f'{docs} has no README.md, the documents\' index')
    documents = {f: Doc(f, open(os.path.join(docs, f), encoding='utf-8').read()) for f in mds}

    # every page, and the page each heading is on
    pages, where = [], {}
    for f, doc in documents.items():
        for name, title, bs, ids in pages_of(doc):
            pages.append((doc, name, title, bs, ids))
            for i in ids:
                where.setdefault((f, i), name)

    def linker(doc, page):
        def link(url):
            if re.match(r'^[a-z][a-z0-9+.-]*:', url):
                return url
            path, _, frag = url.partition('#')
            if not path:
                target = doc.rel
            else:
                target = os.path.normpath(os.path.join(os.path.dirname(doc.rel), path)).replace(os.sep, '/')
            if target in documents:
                dst = where.get((target, frag), documents[target].page) if frag else documents[target].page
                return relative(page, dst) + (f'#{frag}' if frag and (target, frag) in where else '')
            git = os.path.normpath(os.path.join(prefix, target)).replace(os.sep, '/')
            if git.startswith('../'):
                return url
            kind = 'tree' if path.endswith('/') or ('.' not in os.path.basename(git)) else 'blob'
            return f'{REPO}/{kind}/{commit}/{git}' + (f'#{frag}' if frag else '')
        return link

    short = commit[:12] if re.fullmatch(r'[0-9a-f]{40}', commit) else commit
    for doc, name, title, bs, ids in pages:
        link = linker(doc, name)
        up = relative(name, 'index').rsplit('index.html', 1)[0] or './'
        css = os.path.relpath('manual.css', os.path.join('snx', os.path.dirname(name))).replace(os.sep, '/')
        body = []
        for k, d in bs:
            if k == 'toc':
                body.append('<ul>\n' + '\n'.join(f'<li><a href="{relative(name, p)}">{html.escape(t, quote=False)}</a></li>'
                                                 for p, t in d) + '\n</ul>')
            else:
                body.append(render([(k, d)], link, ids))
        crumbs = [f'<a href="{up}../../">ScarletNX</a>', f'<a href="{up}">{TITLE}</a>' if name != 'index' else TITLE]
        if name != doc.page:
            crumbs.append(f'<a href="{relative(name, doc.page)}">{html.escape(doc.title, quote=False)}</a>')
        siblings = [p for d2, p, *_ in pages if d2 is doc]
        k = siblings.index(name)
        nav = []
        if len(siblings) > 1:
            if k:
                nav.append(f'<a rel="prev" href="{relative(name, siblings[k - 1])}">&larr; previous</a>')
            if k + 1 < len(siblings):
                nav.append(f'<a rel="next" href="{relative(name, siblings[k + 1])}">next &rarr;</a>')
        heading = '' if bs and bs[0][0] == 'h' else f'<h1>{html.escape(title, quote=False)}</h1>\n'
        page = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                '<meta name="color-scheme" content="light dark">\n'
                f'<title>{html.escape(title, quote=False)} - {TITLE}</title>\n<link rel="stylesheet" href="{css}">\n'
                '</head>\n<body>\n'
                f'<p class="nav">{" / ".join(crumbs)}' + (' &middot; ' + ' &middot; '.join(nav) if nav else '') + '</p>\n'
                + heading + '\n'.join(body) + '\n<hr>\n'
                + (f'<p class="nav">{" &middot; ".join(nav)}</p>\n' if nav else '')
                + f'<p class="foot">Made from <a href="{REPO}/blob/{commit}/{prefix}{doc.rel}">{prefix}{doc.rel}</a> '
                f'at <a href="{REPO}/tree/{commit}">{short}</a>. GPL-3.0-or-later.</p>\n</body>\n</html>\n')
        path = os.path.join(out, name + '.html')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'w', encoding='utf-8').write(page)
    print(f'{len(documents)} document(s), {len(pages)} page(s): {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
