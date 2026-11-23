#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Makes the ARM manual (manual/) from ScarletNX's Sail of the A64 and AArch32 instructions.

    tools/gen-arm-manual.py SCARLETNX [OUT]     OUT is manual/ beside tools/ when not named
        --commit HASH       the ScarletNX commit the Sail is from, for the links to it (else asked of git, else main)

SCARLETNX is a checkout of ScarletNX (src/common/cpu/aarch64/sail and src/common/cpu/arm/sail are all it reads).
Every instruction there is a page laid out as Arm's reference lays one out, made only from the Sail: each class an
encoding diagram (the fixed bits, the fields, under them the names of the fields the encoding fixes), its decode and
the operation. Every name the Sail defines (sail-arm's v8_base, or ScarletNX's fixup of it) is a page of the shared
pseudocode, which the instructions link to. Pages stay under the site's 16 KB; the index pages split when they would
not. The output is the same for the same Sail: no date, nothing random.
"""
import html
import os
import re
import shutil
import subprocess
import sys

MAX_BYTES = 16 * 1024
GITHUB = 'https://github.com/scarletnx/ScarletNX/blob'

ARCHES = [
    {
        'id': 'a64', 'title': 'A64', 'dir': 'src/common/cpu/aarch64/sail',
        'arm': 'a64.sail', 'snx': 'nx.sail', 'about': 'the AArch64 instruction set, as a Switch program runs it',
        'groups': {
            '__DecodeA64_BranchExcSys': 'Branches, exception generating and system instructions',
            '__DecodeA64_DataProcImm': 'Data processing (immediate)',
            '__DecodeA64_DataProcReg': 'Data processing (register)',
            '__DecodeA64_DataProcFPSIMD': 'Data processing (scalar floating-point and Advanced SIMD)',
            '__DecodeA64_LoadStore': 'Loads and stores',
        },
    },
    {
        'id': 'a32', 'title': 'A32 and T32', 'dir': 'src/common/cpu/arm/sail',
        'arm': 'a32.sail', 'snx': 'arm.sail', 'about': 'the AArch32 instruction sets, from the ARM7TDMI to the Cortex-A57',
        'groups': {
            '__DecodeA32_DataProMisc': 'A32: data processing and miscellaneous instructions',
            '__DecodeA32_BranchBlock': 'A32: branch, branch with link, and block data transfer',
            '__DecodeT16': 'T32: 16-bit instructions',
        },
    },
]

TOP = re.compile(r'^(val|function|enum|struct|register|type|let|overload|bitfield|union|mapping)\b')
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
SLICE = re.compile(r"let (\w+) = Slice\(__opcode, (\d+), (\d+)\);")
GUARD = re.compile(r'Slice\(__opcode, (\d+), (\d+)\) != 0b([01]+)')

# What sail-arm's name of an A64 instruction adds to its mnemonic, as Arm's titles have it
A64_FORMS = {
    'addsub_shift': 'shifted register', 'addsub_imm': 'immediate', 'addsub_ext': 'extended register',
    'log_imm': 'immediate', 'log_shift': 'shifted register', 'reg': 'register', 'imm': 'immediate',
    'imm_gen': 'immediate', 'reg_gen': 'register', 'lit_gen': 'literal', 'lit': 'literal', 'gen': '', 'int': '',
    'advsimd': 'vector', 'advsimd_reg': 'register', 'advsimd_vec': 'vector', 'float': 'scalar',
    'float_fix': 'scalar, fixed-point', 'float_int': 'scalar, integer', 'float_gen': 'general',
    'float_imm': 'scalar, immediate',
}
A64_NAMES = {'b_cond': 'B.cond', 'bc_cond': 'BC.cond'}
A32_FORMS = {'i': 'immediate', 'r': 'register', 'rr': 'register-shifted register', 'l': 'literal',
             'SP_i': 'SP plus immediate', 'SP_r': 'SP plus register'}


class Def:
    """A top-level definition of one Sail file: its text, the line it starts on, the comment before it"""

    def __init__(self, kind, name, text, line, comment, source):
        self.kind, self.name, self.text, self.line, self.comment, self.source = kind, name, text, line, comment, source


def parse(path, source):
    """The top-level definitions of a Sail file, in order; a comment at the start of a line belongs to the next"""
    lines = open(path, encoding='utf-8').read().split('\n')
    items, comment, i = [], [], 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('/*'):
            j = i
            while '*/' not in lines[j]:
                j += 1
            comment = lines[i:j + 1] if 'SPDX' not in line and 'sailgen --extract' not in line else []
            i = j + 1
            continue
        if line.startswith('//'):
            comment.append(line)
            i += 1
            continue
        m = TOP.match(line)
        if not m:
            if line.strip() == '':
                comment = [] if comment and i + 1 < len(lines) and lines[i + 1].strip() == '' else comment
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not TOP.match(lines[j]) and not lines[j].startswith(('//', '/*')):
            j += 1
        text = '\n'.join(lines[i:j]).rstrip()
        kind = m.group(1)
        words = line.split()
        if kind == 'function' and words[1] == 'clause':
            name = words[2]
            kind = 'clause'
        else:
            name = IDENT.match(words[1]).group(0)
        items.append(Def(kind, name, text, i + 1, clean_comment(comment), source))
        comment = []
        i = j
    return items


def clean_comment(lines):
    text = []
    for line in lines:
        line = line.strip()
        for mark in ('/*', '*/', '//'):
            line = line.replace(mark, '')
        text.append(line.strip())
    return ' '.join(t for t in text if t)


class Clause:
    """An encoding: a clause of a decoder, the bits it fixes and the fields it gives the decode function"""

    def __init__(self, d):
        self.decoder = d.name
        head = d.text.split('\n', 1)[0]
        m = re.search(r'\(\[(.*?)\] as __opcode\)', head)
        if m:
            bits = m.group(1).split(', ')
        else:  # every bit fixed: a literal
            bits = [{'0': 'bitzero', '1': 'bitone'}[b] for b in re.search(r'\(0b([01]+) as __opcode\)', head).group(1)]
        self.width = len(bits)
        self.bits = {self.width - 1 - k: {'bitzero': '0', 'bitone': '1'}.get(b) for k, b in enumerate(bits)}
        self.fields = [(n, int(lo), int(w)) for n, lo, w in SLICE.findall(d.text)]
        self.guards = [(int(lo), int(w), v) for lo, w, v in GUARD.findall(head)]
        text = d.text.split('\n', 1)[1]
        call = list(re.finditer(r'\b(decode_\w+)\(', text))[-1]
        depth, k = 1, call.end()
        while depth:
            depth += {'(': 1, ')': -1}.get(text[k], 0)
            k += 1
        self.decode, self.args = call.group(1), text[call.end():k - 1]
        # the bits that should be a value (Arm's (0) and (1)): another is CONSTRAINED UNPREDICTABLE
        self.should = {int(b): v for b, v in re.findall(r'\[__opcode\[(\d+)\]\] != 0b([01])', text)}
        # what else decides it: the guard but SEE's order and the fields' values
        guard = re.search(r'\bif (.*)\) = \{$', head)
        rest = [g.strip() for g in guard.group(1).split('&')] if guard else []
        self.condition = [g for g in rest if not g.startswith('SEE <') and not GUARD.fullmatch(g)]
        self.source = d.source[0]
        self.mask = sum(1 << b for b, v in self.bits.items() if v is not None)
        self.value = sum(1 << b for b, v in self.bits.items() if v == '1')
        self.pattern = ''.join(self.bits[b] or ('(' + self.should[b] + ')' if b in self.should else 'x')
                               for b in range(self.width - 1, -1, -1))


def load(root, arch, commit):
    base = os.path.join(root, arch['dir'])
    defs, clauses = {}, []
    for fname, who in ((arch['arm'], 'arm'), (arch['snx'], 'snx')):
        for d in parse(os.path.join(base, fname), (who, arch['dir'] + '/' + fname)):
            if d.kind == 'clause':
                if d.name in arch['groups']:
                    clauses.append(Clause(d))
                continue
            entry = defs.setdefault(d.name, {'arm': [], 'snx': []})
            last = entry[who][-1] if entry[who] else None
            if last and last.kind == 'val' and d.kind == 'function' and d.line - last.line - last.text.count('\n') <= 3:
                # a val and its function are one definition, as the pages show it
                last.text += '\n\n' + d.text
                last.kind = 'function'
                last.comment = ' '.join(c for c in (last.comment, d.comment) if c)
            else:
                entry[who].append(d)
    for c in clauses:  # a field given straight to the decode function: the name of its parameter
        d = (defs[c.decode]['snx'] or defs[c.decode]['arm'])[-1]
        m = re.match(r'function \w+ \(?([\w, ]*)\)? =', d.text)
        params = [p.strip() for p in m.group(1).split(',')] if m and m.group(1).strip() else []
        args = [a.strip() for a in re.split(r',(?![^(]*\))', c.args)] if c.args.strip() else []
        for p, a in zip(params, args):
            sl = re.fullmatch(r'Slice\(__opcode, (\d+), (\d+)\)', a)
            if sl:
                c.fields.append((p, int(sl.group(1)), int(sl.group(2))))
    return defs, clauses


WORDS = {'idx': 'index', 'imm': 'immediate', 'reg': 'register', 'regoff': 'register offset', 'simd': 'SIMD',
         'sisd': 'scalar', 'fp': 'FP', 'pac': 'PAC', 'crc': 'CRC', 'dp': 'data processing', 'fpsimd': 'FP&SIMD', 'gen': 'general', 'advsimd': 'Advanced SIMD',
         'extendedreg': 'extended register', 'shiftedreg': 'shifted register', 'pc': 'PC', 'rel': 'relative',
         '1src': '1 source', '2src': '2 sources', 'uncond': 'unconditional', 'nzcv': 'NZCV', 'sw': 'SW', 'cfinv': 'CFINV', 'dit': 'DIT', 'ld': 'load', 'st': 'store'}


def words(cls):
    """sail-arm's name of an instruction class as Arm's headings write one"""
    text = ' '.join(WORDS.get(w, w) for w in cls.split('_'))
    text = text.replace('post index', 'post-index').replace('pre index', 'pre-index')
    return text[0].upper() + text[1:]


def instruction_key(arch, decode):
    """The page an encoding's decode function is on, the page's title, and the class's heading"""
    name = decode[len('decode_'):]
    if arch == 'a64':
        mn, cls = name.split('_aarch64_instrs_')
        first, _, rest = mn.partition('_')
        title = A64_NAMES.get(mn)
        if not title:
            form = A64_FORMS.get(rest, rest.replace('_', ' '))
            title = first.upper() + (f' ({form})' if form else '')
        return mn, title, words(cls)
    if not name.startswith('aarch32_instrs_'):  # a clause of ScarletNX's own (arm.sail)
        name = name[len('aarch32_'):]
        if name.startswith('legacy_'):
            return name[len('legacy_'):], name[len('legacy_'):], 'ScarletNX: ' + name.replace('_', ' ')
        stem = re.sub(r'_T\d$', '', name)
        return stem, stem.replace('_', ' ').capitalize() + ' (ScarletNX)', 'ScarletNX: ' + name.replace('_', ' ')
    name = name[len('aarch32_instrs_'):]
    name = re.sub(r'_A[S]?_txt$', '', name)
    stem, enc = name.rsplit('_', 1)
    first, _, rest = stem.partition('_')
    form = A32_FORMS.get(rest, rest.replace('_', ' '))
    return stem, first + (f' ({form})' if form else ''), enc.replace('enc', '')


def body(d):
    """A function's statements, as Arm's reference shows an instruction's pseudocode: no signature, no braces"""
    text = d.text
    m = re.search(r'^function ', text, re.M)
    if m:
        text = text[m.start():]
    lines = text.split('\n')
    if len(lines) >= 3 and lines[0].endswith('{') and lines[-1] == '}':
        return '\n'.join(l[4:] if l.startswith('    ') else l for l in lines[1:-1])
    return text


class Site:
    def __init__(self, out, commit):
        self.out, self.commit, self.written = out, commit, []

    def write(self, rel, content):
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = content.encode('utf-8')
        if rel.endswith('.html') and len(data) > MAX_BYTES:
            raise SystemExit(f'{rel}: {len(data)} bytes, over {MAX_BYTES}')
        with open(path, 'wb') as f:
            f.write(data)
        self.written.append(rel)

    def page(self, rel, title, body_html, depth, search=None):
        up = '../' * depth
        home = up or './'
        scripts = ''
        if search:
            scripts = ''.join(f'<script src="{up}{s}/data.js"></script>' for s in search)
            scripts += f'<script src="{up}search.js"></script>'
        return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                f'<meta name="color-scheme" content="light dark">\n<title>{html.escape(title)} - ScarletNX ARM manual</title>\n'
                f'<link rel="stylesheet" href="{up}manual.css">\n</head>\n<body>\n'
                f'<p class="nav"><a href="{up}../">ScarletNX</a> / <a href="{home}">ARM manual</a></p>\n'
                f'{body_html}\n<hr>\n<p class="foot">Made from ScarletNX\'s Sail at '
                f'<a href="https://github.com/scarletnx/ScarletNX/tree/{self.commit}">{self.commit[:12]}</a>. '
                f'sail-arm\'s definitions are Arm\'s ASL in Sail (BSD 3-Clause Clear, '
                f'<a href="{up}LICENSE-sail-arm.txt">license</a>); ScarletNX\'s fixups are GPL-3.0-or-later.</p>\n'
                f'{scripts}</body>\n</html>\n')

    def source_link(self, d):
        return f'{GITHUB}/{self.commit}/{d.source[1]}#L{d.line}'


def code(text, links, here, with_links=True, linked=None):
    """Sail as HTML, every name with a page a link to it; with linked (a set), only a name not linked before"""
    out, last = [], 0
    for m in IDENT.finditer(text):
        name = m.group(0)
        out.append(html.escape(text[last:m.start()]))
        href = links.get(name) if with_links and (linked is None or name not in linked) else None
        if href and href != here:
            if linked is not None:
                linked.add(name)
            out.append(f'<a href="{href}">{name}</a>')
        else:
            out.append(name)
        last = m.end()
    out.append(html.escape(text[last:]))
    return '<pre>' + ''.join(out) + '</pre>'


def diagram(c):
    """Arm's register diagram of an encoding: the bit numbers, the bits (fields boxed), the names of fixed fields"""
    field_at = {}
    for name, lo, w in c.fields:
        for b in range(lo, lo + w):
            field_at.setdefault(b, (name, lo, w))
    first, second = [], []
    b = c.width - 1
    while b >= 0:
        if b in field_at:
            name, lo, w = field_at[b]
            hi = lo + w - 1
            span = range(min(hi, b), lo - 1, -1)
            fixed = [c.bits[k] for k in span]
            if all(v is None for v in fixed) and not any(k in c.should for k in span):
                first.append(f'<td colspan="{len(span)}" class="lr">{name}</td>')
                second.append((len(span), ''))
            else:
                for k, v in zip(span, fixed):
                    cls = 'lr' if len(span) == 1 else 'l' if k == span[0] else 'r' if k == lo else ''
                    v = v or (f'({c.should[k]})' if k in c.should else 'x')
                    first.append(f'<td class="{cls}">{v}</td>' if cls else f'<td>{v}</td>')
                second.append((len(span), name))
            b = lo - 1
            continue
        run = []
        while b >= 0 and b not in field_at:
            run.append(b)
            b -= 1
        for k in run:
            cls = 'lr' if len(run) == 1 else 'l' if k == run[0] else 'r' if k == run[-1] else ''
            v = c.bits[k] or (f'({c.should[k]})' if k in c.should else '')
            first.append(f'<td class="{cls}">{v}</td>' if cls else f'<td>{v}</td>')
        second.append((len(run), ''))
    row2 = []
    for n, name in second:
        if not name and row2 and not row2[-1][1]:
            row2[-1] = (row2[-1][0] + n, '')
        else:
            row2.append((n, name))
    nums = ''.join(f'<td>{k}</td>' for k in range(c.width - 1, -1, -1))
    cells2 = ''.join((f'<td colspan="{n}" class="droppedname">{name}</td>' if name else
                      (f'<td colspan="{n}"></td>' if n > 1 else '<td></td>')) for n, name in row2)
    return (f'<table class="regdiagram" border="1" cellspacing="0"><thead><tr>{nums}</tr></thead>'
            f'<tbody><tr class="firstrow">{"".join(first)}</tr><tr class="secondrow">{cells2}</tr></tbody></table>')


def guard_text(c):
    out = list(c.condition)
    for lo, w, v in c.guards:
        named = [n for n, flo, fw in c.fields if flo == lo and fw == w]
        out.append(f'{named[0] if named else f"bits {lo + w - 1}:{lo}"} != {v}')
    return out


def split_pages(rows, render, first_rel):
    """Rows over as many pages as keep each under the limit: first_rel, then -2, -3, ..."""
    chunks, start = [], 0
    while start < len(rows):
        end = len(rows)
        while end > start + 1 and len(render(rows[start:end], 1, 2).encode()) > MAX_BYTES - 1024:
            end = start + max(1, (end - start) * 3 // 4)
        chunks.append(rows[start:end])
        start = end
    stem = first_rel[:-len('.html')]
    rels = [first_rel] + [f'{stem}-{k}.html' for k in range(2, len(chunks) + 1)]
    return list(zip(rels, chunks))


def build_arch(site, root, arch, out_rows):
    aid = arch['id']
    defs, clauses = load(root, arch, site.commit)

    # instruction pages: every encoding by the page of its decode function
    pages = {}
    for c in clauses:
        key, title, heading = instruction_key(aid, c.decode)
        page = pages.setdefault(key, {'title': title, 'classes': [], 'groups': set()})
        page['classes'].append((heading, c))
        page['groups'].add(c.decoder)

    inst_names = {}  # decode_/execute_ names -> their instruction page
    for key, page in pages.items():
        for heading, c in page['classes']:
            inst_names[c.decode] = f'{key}.html'
            for d in defs[c.decode]['arm'] + defs[c.decode]['snx']:
                for e in re.findall(r'\b(execute_\w+)\(', d.text):
                    inst_names.setdefault(e, f'{key}.html')

    helpers = sorted(n for n in defs if n not in inst_names and not n.startswith(('decode_', 'execute_')))
    enum_members = {}
    for n in helpers:
        for d in defs[n]['arm'] + defs[n]['snx']:
            if d.kind == 'enum':
                for m in IDENT.findall(d.text.split('=', 1)[1]):
                    enum_members.setdefault(m, n)

    def links(depth):
        up = '../' * depth
        table = {n: f'{up}fn/{n}.html' for n in helpers}
        table.update({m: f'{up}fn/{e}.html' for m, e in enum_members.items()})
        table.update({n: f'{up}{p}' for n, p in inst_names.items()})
        return table

    # who uses what: a helper's page lists the instructions and the definitions that name it
    used_by = {}
    for n, entry in defs.items():
        for d in entry['arm'] + entry['snx']:
            for ref in set(IDENT.findall(d.text)) - {n}:
                ref = enum_members.get(ref, ref)
                if ref in defs:
                    used_by.setdefault(ref, set()).add(n)

    top_links = links(0)
    fallbacks = []
    for key, page in sorted(pages.items()):
        rel = f'{aid}/{key}.html'
        for with_links, linked in ((True, None), (True, set()), (False, None)):
            parts = [f'<h1>{html.escape(page["title"])}</h1>',
                     '<p class="groups">' + ' / '.join(
                         f'<a href="{g[len("__Decode"):]}.html">{html.escape(arch["groups"][g])}</a>'
                         for g in sorted(page['groups'])) + '</p>']
            executes = []
            for heading, c in page['classes']:
                anchor = re.sub(r'\W+', '_', heading)
                parts.append(f'<h2 class="classheading" id="{anchor}">{html.escape(heading)}</h2>')
                parts.append(diagram(c))
                extra = guard_text(c)
                parts.append(f'<p class="bits">{c.pattern}'
                             + (''.join(f'<br>{html.escape(g)}' for g in extra)) + '</p>')
                dec = (defs[c.decode]['snx'] or defs[c.decode]['arm'])[0]
                parts.append(f'<h3>Decode <a class="src" href="{site.source_link(dec)}">Sail</a></h3>')
                if dec.source[0] == 'snx':
                    parts.append(f'<p>ScarletNX\'s fixup{" (it takes the place of sail-arm&#39;s)" if defs[c.decode]["arm"] else ""}'
                                 f'{": " + html.escape(dec.comment) if dec.comment else ""}</p>')
                parts.append(code(body(dec), top_links, f'{key}.html', with_links, linked))
                for e in re.findall(r'\b(execute_\w+)\(', dec.text):
                    if e not in executes and e in defs:
                        executes.append(e)
            for e in executes:
                ex = (defs[e]['snx'] or defs[e]['arm'])[0]
                parts.append(f'<h2 class="pseudocode">Operation <a class="src" href="{site.source_link(ex)}">Sail</a></h2>')
                parts.append(code(body(ex), top_links, f'{key}.html', with_links, linked))
            text = site.page(f'{page["title"]}', page['title'], '\n'.join(parts), 1)
            if len(text.encode()) <= MAX_BYTES or not with_links:
                break
            fallbacks.append((rel, 'first uses' if linked is None else 'none'))
        site.write(rel, text)
        for heading, c in page['classes']:
            anchor = re.sub(r'\W+', '_', heading)
            ex = [(lo, w, v) for lo, w, v in c.guards]
            exmask = sum(((1 << w) - 1) << lo for lo, w, v in ex) if len(ex) == 1 else 0
            exval = int(ex[0][2], 2) << ex[0][0] if len(ex) == 1 else 0
            out_rows.append([page['title'], f'{aid}/{key}.html#{anchor}', 'T16' if c.width == 16 else
                             ('A64' if aid == 'a64' else 'A32'), heading, f'{c.mask:x}', f'{c.value:x}',
                             f'{exmask:x}', f'{exval:x}', str(clauses.index(c))])

    # shared pseudocode: a page per name
    fn_links = links(1)
    for n in helpers:
        rel = f'{aid}/fn/{n}.html'
        entry = defs[n]
        parts = [f'<h1>{html.escape(n)}</h1>']
        for d in entry['snx']:
            parts.append(f'<h2>ScarletNX\'s fixup <a class="src" href="{site.source_link(d)}">{d.source[1].rsplit("/", 1)[1]}</a></h2>')
            if d.comment:
                parts.append(f'<p>{html.escape(d.comment)}</p>')
            parts.append(code(d.text, fn_links, f'../fn/{n}.html'))
        for d in entry['arm']:
            what = 'sail-arm\'s definition' + (', which the fixup replaces' if entry['snx'] else '')
            parts.append(f'<h2>{what} <a class="src" href="{site.source_link(d)}">{d.source[1].rsplit("/", 1)[1]}</a></h2>')
            parts.append(code(d.text, fn_links, f'../fn/{n}.html'))
        users = sorted(used_by.get(n, ()), key=lambda u: (u not in inst_names, pages[inst_names[u][:-5]]['title'].lower() if u in inst_names else u.lower()))
        if users:
            items, seen = [], set()
            for u in users:
                if u in inst_names:
                    if inst_names[u] not in seen:
                        seen.add(inst_names[u])
                        items.append(f'<li><a href="../{inst_names[u]}">{html.escape(pages[inst_names[u][:-5]]["title"])}</a></li>')
                elif u in helpers:
                    items.append(f'<li><a href="{u}.html">{html.escape(u)}</a></li>')
            parts.append('<h2>Used by</h2><ul class="cols">' + ''.join(items) + '</ul>')
        text = site.page(n, n, '\n'.join(parts), 2)
        if len(text.encode()) > MAX_BYTES:
            text = site.page(n, n, '\n'.join(p if not p.startswith('<pre>') else
                                              code(html.unescape(re.sub(r'<[^>]+>', '', p)), {}, '') for p in parts), 2)
        site.write(rel, text)

    # the indexes: the instruction groups, each split over pages when it must be, and the shared pseudocode
    for g, gtitle in arch['groups'].items():
        rows = sorted(((p['title'], k) for k, p in pages.items() if g in p['groups']), key=lambda r: (r[0].lower(), r[1]))
        gname = g[len('__Decode'):]

        def render(chunk, k, n, gtitle=gtitle, gname=gname):
            nav = '' if n == 1 else '<p>Page ' + ' '.join(
                (f'<a href="{gname}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                for j in range(1, n + 1)) + '</p>'
            return site.page(gtitle, gtitle, f'<h1>{html.escape(gtitle)}</h1>{nav}<ul class="cols">' + ''.join(
                f'<li><a href="{key}.html">{html.escape(t)}</a></li>' for t, key in chunk) + f'</ul>{nav}', 1)

        split = split_pages(rows, render, f'{aid}/{gname}.html')
        for k, (rel, chunk) in enumerate(split, 1):
            site.write(rel, render(chunk, k, len(split)))
    hrows = helpers

    def render_shared(chunk, k, n):
        nav = '' if n == 1 else '<p>Page ' + ' '.join(
            (f'<a href="shared{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
            for j in range(1, n + 1)) + '</p>'
        return site.page('Shared pseudocode', 'Shared pseudocode', f'<h1>{arch["title"]}: shared pseudocode</h1>{nav}'
                         '<ul class="cols">' + ''.join(f'<li><a href="fn/{n_}.html">{html.escape(n_)}</a></li>'
                                                      for n_ in chunk) + f'</ul>{nav}', 1)

    split = split_pages(hrows, render_shared, f'{aid}/shared.html')
    for k, (rel, chunk) in enumerate(split, 1):
        site.write(rel, render_shared(chunk, k, len(split)))

    groups = ''.join(
        f'<li><a href="{g[len("__Decode"):]}.html">{html.escape(t)}</a> '
        f'({sum(1 for p in pages.values() if g in p["groups"])})</li>' for g, t in arch['groups'].items())
    site.write(f'{aid}/index.html', site.page(arch['title'], arch['title'],
               f'<h1>{arch["title"]}</h1><p>The instructions ScarletNX\'s recompiler takes from the Sail of '
               f'{arch["about"]}: {len(pages)} instructions, {len(clauses)} encodings.</p>'
               '<div id="search" data-root="../"></div>'
               f'<h2>Instructions</h2><ul>{groups}</ul><h2>Shared pseudocode</h2>'
               f'<p><a href="shared.html">Every function, type and register the instructions use</a> ({len(helpers)})</p>',
               1, search=[aid]))
    for rel, what in fallbacks:
        print(f'{rel}: over {MAX_BYTES} bytes with every link, so links {what}', file=sys.stderr)
    return len(pages), len(clauses)


def find_commit(root, dirs):
    try:
        return subprocess.run(['git', '-C', root, 'log', '-1', '--format=%H', '--'] + dirs, capture_output=True,
                              text=True, check=True).stdout.strip() or 'main'
    except (OSError, subprocess.CalledProcessError):
        return 'main'


def main(argv):
    commit = None
    if '--commit' in argv:
        k = argv.index('--commit')
        commit = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]
    if not 1 <= len(argv) <= 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    root = argv[0]
    out = argv[1] if len(argv) == 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'manual')
    commit = commit or find_commit(root, [a['dir'] for a in ARCHES])
    here = os.path.dirname(os.path.abspath(__file__))

    # the manual is made whole each time: what the Sail no longer has goes
    for a in ARCHES:
        shutil.rmtree(os.path.join(out, a['id']), ignore_errors=True)
    site = Site(out, commit)
    summary = []
    for a in ARCHES:
        rows = []
        n_pages, n_clauses = build_arch(site, root, a, rows)
        site.write(f'{a["id"]}/data.js', '// The search\'s data (tools/gen-arm-manual.py): title, page, instruction set, '
                   'class, mask, value, the bits that must not be a value (mask, value), and the order the decoder tries it in\n'
                   'var ARM = (window.ARM || []).concat([\n' + ',\n'.join(
                       '[' + ','.join('"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"' for v in r) + ']'
                       for r in rows) + '\n]);\nwindow.ARM = ARM;\n')
        summary.append(f'<li><a href="{a["id"]}/">{a["title"]}</a>: {a["about"]} ({n_pages} instructions, {n_clauses} encodings)</li>')
    for name in ('manual.css', 'search.js'):
        shutil.copyfile(os.path.join(here, 'manual', name), os.path.join(out, name))
    shutil.copyfile(os.path.join(root, ARCHES[0]['dir'], 'LICENSE'), os.path.join(out, 'LICENSE-sail-arm.txt'))
    site.write('index.html', site.page('ARM manual', 'ARM manual',
               '<h1>ARM manual</h1><p>The instructions ScarletNX recompiles, laid out as Arm\'s reference lays them out '
               'and made from the Sail it recompiles them from: <a href="https://github.com/rems-project/sail-arm">'
               'sail-arm</a>\'s model of Armv9.4-A, and ScarletNX\'s fixups of it. Each instruction has its encodings, '
               'their decode and its operation; every name they use is a page of the shared pseudocode.</p>'
               '<div id="search" data-root=""></div>'
               f'<ul>{"".join(summary)}</ul>'
               '<p>The search takes a name (the nearest when none is the same) or an instruction word in hex '
               '(<code>0x1a020020</code>, or a Thumb halfword <code>0x4148</code>): it lists every encoding it '
               'matches.</p>', 0, search=[a['id'] for a in ARCHES]))
    print(f'{len(site.written)} files in {out} (ScarletNX {commit[:12]})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
