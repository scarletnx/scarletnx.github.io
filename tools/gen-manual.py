#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Makes the ISA manuals (manual/) from ScarletNX's Sail: ARM's (A64 and AArch32), Maxwell's (SM53) and Ampere's (SM86).

    tools/gen-manual.py SCARLETNX [OUT]     OUT is manual/ beside tools/ when not named
        --commit HASH       the ScarletNX commit the Sail is from, for the links to it (else asked of git, else main)

SCARLETNX is a checkout of ScarletNX; it reads src/common/cpu/aarch64/sail, src/common/cpu/arm/sail and
src/nx/gpu/shader (the GPU manuals are left out when it has none). Every instruction is a page laid out as Arm's
reference lays one out:
  ARM (manual/a64, manual/a32): made only from the Sail. Each class an encoding diagram (the fixed bits, the fields,
    under them the names of the fields the encoding fixes), its decode and the operation.
  Maxwell and Ampere (manual/sm53, manual/sm86): the opcode from the encodings' file (sm53.decode, sm86.decode), the
    fields the decoder gives and those the Sail reads (Field(lo, n), through the Sail's calls), the file's notes,
    and the operation in the Sail (the function the .roots file runs for it, and its fusions).
Every name the Sail defines is a page of the shared pseudocode, which the instructions link to. Pages stay under the
site's 16 KB: the indexes and a long definition split over pages, an instruction's links shrink to first uses.
The output is the same for the same Sail: no date, nothing random.
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
    m = re.match(r'function \w+\s*(\([^)]*\))?[^=]*?=\s*', text)  # one expression: it alone
    if m and not text.startswith('function clause'):
        rest = text[m.end():]
        return '\n'.join(l[4:] if l.startswith('    ') else l for l in rest.split('\n'))
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

    def page(self, rel, title, body_html, depth, search=None, manual=None):
        """A page depth folders under manual/; manual: the GPU manual's (name, folder, footer) it is of"""
        up = '../' * depth
        home = up or './'
        name = 'ARM ISA'
        foot = (f'sail-arm\'s definitions are Arm\'s ASL in Sail (BSD 3-Clause Clear, '
                f'<a href="{up}LICENSE-sail-arm.txt">license</a>); ScarletNX\'s fixups are GPL-3.0-or-later.')
        if manual:
            name, folder, foot = manual
            home = up + folder + '/'
        scripts = ''
        if search:
            scripts = ''.join(f'<script src="{up}{s}/data.js"></script>' for s in search)
            scripts += f'<script src="{up}search.js"></script>'
        return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                f'<meta name="color-scheme" content="light dark">\n<title>{html.escape(title)} - ScarletNX {name}</title>\n'
                f'<link rel="stylesheet" href="{up}manual.css">\n</head>\n<body>\n'
                f'<p class="nav"><a href="{up}../">ScarletNX</a> / <a href="{home}">{name}</a></p>\n'
                f'{body_html}\n<hr>\n<p class="foot">Made from ScarletNX\'s Sail at '
                f'<a href="https://github.com/scarletnx/ScarletNX/tree/{self.commit}">{self.commit[:12]}</a>. '
                f'{foot}</p>\n'
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
    """Arm's register diagram of an encoding: the bit numbers, the bits (fields boxed), the names of fixed fields;
    a word wider than 32 bits in rows of 32, its high bits first"""
    field_at = {}
    for name, lo, w in c.fields:
        for b in range(lo, lo + w):
            field_at.setdefault(b, (name, lo, w))
    rows = []
    for row_hi in range(c.width - 1, -1, -32):
        row_lo = max(0, row_hi - 31)
        first, second = [], []
        b = row_hi
        while b >= row_lo:
            if b in field_at:
                name, lo, w = field_at[b]
                end = max(lo, row_lo)
                span = range(b, end - 1, -1)
                fixed = [c.bits.get(k) for k in span]
                if all(v is None for v in fixed) and not any(k in c.should for k in span):
                    first.append(f'<td colspan="{len(span)}" class="lr">{name}</td>' if len(span) > 1 else
                                 f'<td class="lr">{name}</td>')
                    second.append((len(span), ''))
                else:
                    for k, v in zip(span, fixed):
                        cls = 'lr' if len(span) == 1 else 'l' if k == span[0] else 'r' if k == end else ''
                        v = v or (f'({c.should[k]})' if k in c.should else 'x')
                        first.append(f'<td class="{cls}">{v}</td>' if cls else f'<td>{v}</td>')
                    second.append((len(span), name))
                b = end - 1
                continue
            run = []
            while b >= row_lo and b not in field_at:
                run.append(b)
                b -= 1
            for k in run:
                cls = 'lr' if len(run) == 1 else 'l' if k == run[0] else 'r' if k == run[-1] else ''
                v = c.bits.get(k) or (f'({c.should[k]})' if k in c.should else '')
                first.append(f'<td class="{cls}">{v}</td>' if cls else f'<td>{v}</td>')
            second.append((len(run), ''))
        row2 = []
        for n, name in second:
            if not name and row2 and not row2[-1][1]:
                row2[-1] = (row2[-1][0] + n, '')
            else:
                row2.append((n, name))
        nums = ''.join(f'<td>{k}</td>' for k in range(row_hi, row_lo - 1, -1))
        cells2 = ''.join((f'<td colspan="{n}" class="droppedname">{name}</td>' if name else
                          (f'<td colspan="{n}"></td>' if n > 1 else '<td></td>')) for n, name in row2)
        rows.append(f'<tr class="nums">{nums}</tr><tr class="firstrow">{"".join(first)}</tr>'
                    f'<tr class="secondrow">{cells2}</tr>')
    return f'<table class="regdiagram" border="1" cellspacing="0">{"".join(rows)}</table>'


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


# ---- the GPU manuals: Maxwell (SM53) and Ampere (SM86) ----

GPUS = [
    {
        'id': 'sm53', 'name': 'Maxwell ISA', 'title': 'Maxwell (SM53)', 'set': 'SM53', 'width': 64, 'op_lo': 48,
        'decode': 'sm53.decode', 'ops': 'translator.h', 'prefix': 'O_', 'roots': 'sail/sm53.roots',
        'sails': ['sail/gpu.sail', 'sail/lut3.sail', 'sail/sm53.sail'],
        'about': 'the instructions of the Switch\'s GPU (the Tegra X1\'s Maxwell, SM53) that ScarletNX\'s shader translator takes',
        'word': 'a 64-bit instruction word in hex (<code>0x5c58000000270004</code>): its opcode is bits 63:48',
        'encodings': 'Eden\'s <code>maxwell.inc</code> (GPL-2.0-or-later)',
    },
    {
        'id': 'sm86', 'name': 'Ampere ISA', 'title': 'Ampere (SM86)', 'set': 'SM86', 'width': 128, 'op_lo': 0,
        'decode': 'sm86.decode', 'ops': 'sm86.h', 'prefix': 'SM86_', 'roots': 'sail/sm86.roots',
        'sails': ['sail/gpu.sail', 'sail/lut3.sail', 'sail/sm86.sail'],
        'about': 'the SM86 instructions (Volta to Ada\'s 128-bit encoding, Ampere\'s) that ScarletNX\'s shader translator takes',
        'word': 'a 128-bit instruction in hex, its high 64 bits first (<code>0x000fe20007ffe0ff_0000000000007210</code>), '
                'or its low 64 bits: its opcode is bits 15:0',
        'encodings': 'Mesa\'s NAK (<code>sm70_encode.rs</code>, MIT) and CuAssembler\'s sm_86 records',
    },
]
GPU_DIR = 'src/nx/gpu/shader'

# What the shader Sail's state functions read (sm53.sail's comments: d at 0, a at 8, b at 20; the constant buffer word
# bank at 34, offset at 20; the immediate of 19 bits and its sign at 56), and the guard predicate every instruction has
SM53_ALWAYS = [('pred', 16, 3), ('pred.not', 19, 1)]
SM53_USES = {'Dst': [('Rd', 0, 8)], 'RegA': [('Ra', 8, 8)], 'RegB': [('Rb', 20, 8)]}
SM53_RIGHT = {'R': [('Rb', 20, 8)], 'RC': [('Rb', 20, 8)], 'C': [('cbuf.offset', 20, 14), ('cbuf.bank', 34, 5)],
              'CR': [('cbuf.offset', 20, 14), ('cbuf.bank', 34, 5)], 'I': [('imm', 20, 19), ('imm.sign', 56, 1)]}
# SM86's decoder (sm86_decode.c, the inverse of NAK's encoder): the form, the guard predicate, the destination, the
# scheduling controls, and an ALU instruction's a and, by the form, b and c
SM86_ALWAYS = [('form', 9, 3), ('pred', 12, 3), ('pred.not', 15, 1), ('stall', 105, 4), ('yield', 109, 1),
               ('wr_bar', 110, 3), ('rd_bar', 113, 3), ('wait', 116, 6), ('reuse', 122, 4)]
SM86_FORMS = {
    'ALU': {1: ('Rb at 32', 'Rc at 64'), 2: ('Rb at 64', 'immediate at 32'),
            3: ('Rb at 64', 'constant buffer: offset at 38, bank at 54'), 4: ('immediate at 32', 'Rc at 64'),
            5: ('constant buffer: offset at 38, bank at 54', 'Rc at 64'), 6: ('URb at 32', 'Rc at 64'),
            7: ('Rb at 64', 'URc at 32')},
    'UALU': {1: ('URb at 32', 'URc at 64'), 2: ('URb at 64', 'immediate at 32'), 4: ('immediate at 32', 'URc at 64'),
             6: ('URb at 32', 'URc at 64')},
}


class Encoding:
    """A pattern of a .decode file as a word: its fixed bits, and the fields the page shows"""

    def __init__(self, width, bits, fields):
        self.width, self.bits, self.fields, self.should = width, bits, fields, {}


def parse_decode(path):
    """The patterns of a decodetree file in order: name, bits (left bit first), its section, the note before it"""
    pats, block, section, note, seen = [], [], None, None, False  # seen: the file's header is behind
    for line in open(path, encoding='utf-8').read().split('\n') + ['']:
        if line.startswith('#'):
            block.append(line[1:].strip())
            continue
        if block and seen and len(block) == 1 and block[0][:1].islower():  # a section's heading
            section, note, block = block[0].split(':')[0], None, []
        if not line.strip():
            if block and not seen:
                seen = True
            elif block:
                if len(block) == 1 and block[0][:1].islower():
                    section, note = block[0].split(':')[0], None
                else:
                    note = ' '.join(block)
            elif seen and pats and pats[-1]['note'] == note:
                note = None  # a note is the patterns' up to the blank line after them
            block = []
            continue
        if line.strip() in ('{', '}'):
            continue
        if block:
            note = ' '.join(block)
            block = []
        parts = line.split()
        seen = True
        pats.append({'name': parts[0], 'bits': ''.join(parts[1:]), 'section': section, 'note': note,
                     'order': len(pats)})
    return pats


def parse_roots(base, rel, title=None):
    """op lines (opcode -> the function, its place in the line), fuse lines, and each opcode's family"""
    ops, fuses, family = {}, [], {}
    lines = open(os.path.join(base, rel), encoding='utf-8').read().split('\n')
    comments = [l[1:].strip() for l in lines if l.startswith('#') and 'SPDX' not in l and 'Copyright' not in l]
    if title is None and comments:
        title = re.sub(r'^SM\d+\'s ', '', comments[0]).split(' (')[0]
        title = title[0].upper() + title[1:]
    files = []
    for line in lines:
        w = line.split()
        if not w or w[0].startswith('#'):
            continue
        if w[0] == 'include':
            sub = parse_roots(base, os.path.join(os.path.dirname(rel), w[1]))
            ops.update(sub[0]); fuses += sub[1]; family.update(sub[2]); files += sub[3]
            files.append(os.path.join(os.path.dirname(rel), w[1]).replace('.roots', '.sail'))
        elif w[0] == 'op':
            for k, opc in enumerate(w[2:]):
                ops.setdefault(opc, (w[1], k))
                family.setdefault(opc, title)
        elif w[0] == 'fuse':
            fuses.append((w[1], w[2:]))
    return ops, fuses, family, files


def gpu_fields(defs, fn, env=None, depth=0, via=None, out=None, uses=None):
    """The fields a function reads with literal places (Field(lo, n)), following the Sail's calls with the literal
    arguments put in for the parameters; and every name it calls"""
    out = [] if out is None else out
    uses = set() if uses is None else uses
    entry = defs.get(fn)
    if not entry or depth > 4:
        return out, uses
    d = (entry['snx'] or entry['arm'])[-1]
    text = d.text[d.text.find('function'):] if 'function' in d.text else ''
    env = env or {}

    def ev(expr):
        e = IDENT.sub(lambda m: str(env[m.group(0)]) if m.group(0) in env else m.group(0), expr)
        return eval(e) if re.fullmatch(r'[\d\s+\-*()]+', e) else None  # digits and arithmetic alone

    for line in text.split('\n'):
        for m in re.finditer(r'\bField\(([^,()]+),\s*([^,()]+)\)', line):
            lo, n = ev(m.group(1)), ev(m.group(2))
            if lo is None or n is None:
                continue
            let = re.search(r'\blet (\w+)\b[^=]*=[^=]', line[:m.start()])
            name = let.group(1) if let else via or (f'[{lo + n - 1}:{lo}]' if n > 1 else f'[{lo}]')
            out.append((name, lo, n, via or fn))
    uses.update(re.findall(r'\b([A-Za-z_]\w*)\(', text))
    followed = set()
    for m in re.finditer(r'\b([A-Za-z_]\w*)\(([^()]*)\)', text):
        callee = m.group(1)
        if callee == fn or callee not in defs:
            continue
        cd = (defs[callee]['snx'] or defs[callee]['arm'])[-1]
        pm = re.search(r'^function \w+\s*\(([^)]*)\)', cd.text, re.M)
        params = [p.split(':')[0].strip() for p in pm.group(1).split(',')] if pm and pm.group(1).strip() else []
        args = [a.strip() for a in m.group(2).split(',')] if m.group(2).strip() else []
        sub = {p: ev(a) for p, a in zip(params, args) if ev(a) is not None}
        followed.add(callee)
        if sub or depth < 2:
            gpu_fields(defs, callee, sub, depth + 1, via or (f'{callee}({m.group(2)})' if sub else None), out, uses)
    if depth < 2:  # the calls whose arguments are calls: followed with none known
        for callee in sorted(set(re.findall(r'\b([A-Za-z_]\w*)\(', text)) - followed - {fn}):
            if callee in defs:
                gpu_fields(defs, callee, {}, depth + 1, via, out, uses)
    return out, uses


def build_gpu(site, root, g, out_rows):
    gid, base = g['id'], os.path.join(root, GPU_DIR)
    manual = (g['name'], gid, f'The Sail and the encodings\' file are ScarletNX\'s (GPL-3.0-or-later); its encodings '
                              f'are from {g["encodings"]}.')
    pats = parse_decode(os.path.join(base, g['decode']))
    header = open(os.path.join(base, g['ops']), encoding='utf-8').read()
    info = {}
    for m in re.finditer(r'X\((\w+), (?:(\w+), )?"([^"]*)"\)', header):
        info[m.group(1)] = (m.group(2), m.group(3))
    ops, fuses, family, files = parse_roots(base, g['roots'])
    defs = {}
    for rel in g['sails'] + [f for f in files if f not in g['sails']]:
        if not os.path.exists(os.path.join(base, rel)):
            continue
        for d in parse(os.path.join(base, rel), ('snx', f'{GPU_DIR}/{rel}')):
            if d.kind == 'clause':
                continue
            entry = defs.setdefault(d.name, {'arm': [], 'snx': []})
            last = entry['snx'][-1] if entry['snx'] else None
            if last and last.kind == 'val' and d.kind == 'function':
                last.text += '\n\n' + d.text
                last.kind = 'function'
                last.comment = ' '.join(c for c in (last.comment, d.comment) if c)
            else:
                entry['snx'].append(d)

    def fn_of(opc):
        return ops.get(g['prefix'] + opc)

    # the pages: SM53's by mnemonic, each form a class; SM86's by opcode, its forms one diagram
    pages = {}
    for p in pats:
        kind, display = info.get(p['name'], (None, p['name']))
        if gid == 'sm53':
            key, heading = display.split(' ')[0], display
        else:
            key, heading = p['name'], display
        fam = family.get(g['prefix'] + p['name']) if fn_of(p['name']) else 'Without Sail'
        group = fam if gid == 'sm53' else (p['section'] or 'Other')
        group = group[0].upper() + group[1:]
        page = pages.setdefault(re.sub(r'[^A-Za-z0-9_]', '_', key),
                                {'title': key if gid == 'sm53' else display, 'pats': [], 'groups': [], 'kind': kind,
                                 'sail': False})
        page['pats'].append((heading, p))
        page['sail'] |= bool(fn_of(p['name']))
        if group not in page['groups']:
            page['groups'].append(group)
    groups = []
    for page in pages.values():
        for grp in page['groups']:
            if grp not in groups:
                groups.append(grp)
    if 'Without Sail' in groups:
        groups.remove('Without Sail')
        groups.append('Without Sail')
    def slug(text):
        words, out = re.sub(r'[^a-z0-9]+', ' ', text.lower()).split(), ''
        for w in words:
            if out and len(out) + 1 + len(w) > 32:
                break
            out = f'{out}-{w}' if out else w
        return out

    gslug = {grp: slug(grp) for grp in groups}

    executes = {}
    for key, page in pages.items():
        for heading, p in page['pats']:
            f = fn_of(p['name'])
            if f:
                executes.setdefault('execute_' + f[0], key)
    fused = {}
    for fn, opcs in fuses:
        for opc in opcs:
            fused.setdefault(opc[len(g['prefix']):], []).append(fn)
    helpers = sorted(n for n in defs if n not in executes)
    enum_members = {}
    for n in helpers:
        for d in defs[n]['snx']:
            if d.kind == 'enum':
                for m in IDENT.findall(d.text.split('=', 1)[1]):
                    enum_members.setdefault(m, n)

    def links(up):
        table = {n: f'{up}fn/{n}.html' for n in helpers}
        table.update({m: f'{up}fn/{e}.html' for m, e in enum_members.items()})
        table.update({n: f'{up}{k}.html' for n, k in executes.items()})
        return table

    top_links = links('')
    used_by = {}
    for n, entry in defs.items():
        for d in entry['snx']:
            for ref in set(IDENT.findall(d.text)) - {n}:
                ref = enum_members.get(ref, ref)
                if ref in defs:
                    used_by.setdefault(ref, set()).add(n)

    op_hi = g['op_lo'] + 15
    for key, page in sorted(pages.items()):
        rel = f'{gid}/{key}.html'
        fns = []
        for heading, p in page['pats']:
            f = fn_of(p['name'])
            if f and f[0] not in fns:
                fns.append(f[0])
        # the fields: the decoder's, then the Sail's of every function the page's opcodes run
        sail_fields, uses, by_form = [], set(), False
        for f in fns:
            fl, us = gpu_fields(defs, 'execute_' + f)
            sail_fields += fl
            uses |= us
            by_form |= gid == 'sm53' and 'Form' in us and sum(1 for v in ops.values() if v[0] == f) > 1
        for heading, p in page['pats']:
            for fn in fused.get(p['name'], []):
                for part in (fn + '_ok', fn):
                    fl, us = gpu_fields(defs, part)
                    sail_fields += fl
                    uses |= us

        def fields_for(p):
            got = []
            if gid == 'sm53':
                got += [(n, lo, w, 'the decoder') for n, lo, w in SM53_ALWAYS]
                form = p['name'].rsplit('_', 1)[1] if '_' in p['name'] else ''
                for use, fl in SM53_USES.items():
                    if use in uses and (use != 'RegB' or form in ('R', 'RC')):  # b's place holds the others' operand
                        got += [(n, lo, w, f'{use}()') for n, lo, w in fl]
                if uses & {'Right', 'RightOf', 'CbufWord'}:
                    got += [(n, lo, w, 'the right operand') for n, lo, w in SM53_RIGHT.get(form, [])]
            else:
                got += [(n, lo, w, 'the decoder') for n, lo, w in SM86_ALWAYS if not (n == 'form' and page['kind'] not in SM86_FORMS)]
                uniform = page['kind'] == 'UALU'
                if uses & {'Dst', 'D_write', 'D_writeAt'}:
                    got.append(('URd' if uniform else 'Rd', 16, 6 if uniform else 8, 'the decoder'))
                if page['kind'] in SM86_FORMS:
                    got.append(('URa' if uniform else 'Ra', 24, 6 if uniform else 8, 'the decoder'))
            got += [(n, lo, w, src) for n, lo, w, src in sail_fields]
            seen, table = set(), []
            for n, lo, w, src in got:
                if (lo, w) not in seen:
                    seen.add((lo, w))
                    table.append((n, lo, w, src))
            return table

        def enc_for(pats_here, fields):
            fixed = {}
            for k in range(16):
                vals = {p['bits'][k] for p in pats_here}
                if len(vals) == 1 and vals != {'-'}:
                    fixed[op_hi - k] = vals.pop()
            shown, taken = [], set()
            for n, lo, w, src in fields:
                if by_form and src not in ('the decoder', 'the right operand') and not src.endswith('()'):
                    continue  # the Sail reads it in some forms: the table says which function
                span = set(range(lo, lo + w))
                if span & taken or any(b in fixed for b in span if n != 'form'):
                    continue
                if n == 'form' and all(b in fixed for b in span):
                    continue
                taken |= span
                shown.append((n, lo, w))
            return Encoding(g['width'], fixed, shown)

        def field_table(fields):
            rows = ''.join(f'<tr><td>{html.escape(n)}</td><td>{lo + w - 1}:{lo}</td><td>{html.escape(src)}</td></tr>'
                           if w > 1 else f'<tr><td>{html.escape(n)}</td><td>{lo}</td><td>{html.escape(src)}</td></tr>'
                           for n, lo, w, src in sorted(fields, key=lambda f: (-f[1] - f[2], f[0])))
            return f'<table class="fields"><tr><th>Field</th><th>Bits</th><th>From</th></tr>{rows}</table>'

        def note(p):
            return f'<p class="note">{html.escape(p["note"])}</p>' if p['note'] else ''

        def opbits(p):
            return f'<p class="bits">bits {op_hi}:{g["op_lo"]}: {" ".join(p["bits"][i:i + 4] for i in range(0, 16, 4))}</p>'

        def runs(p):
            f = fn_of(p['name'])
            if not f:
                return '<p>ScarletNX\'s Sail has no operation for it: the translator\'s own code takes it, or refuses it.</p>'
            if gid != 'sm53':  # SM86's Form() is the decoder's form (bits 11:9), not the place in the roots line
                return f'<p>Runs <a href="#execute_{f[0]}">execute_{f[0]}</a>.</p>'
            return f'<p>Runs <a href="#execute_{f[0]}">execute_{f[0]}</a> with <code>Form()</code> {f[1]}.</p>'

        by_form_note = ('<p>The operation reads some of these fields in some forms alone (it chooses by <code>Form()</code>), '
                        'so the diagrams show only the decoder\'s.</p>' if by_form else '')
        for with_links, linked in ((True, None), (True, set()), (False, None)):
            parts = [f'<h1>{html.escape(page["title"])}</h1>',
                     '<p class="groups">' + ' / '.join(f'<a href="{gslug[grp]}.html">{html.escape(grp)}</a>'
                                                       for grp in page['groups']) + '</p>']
            if gid == 'sm53':
                for heading, p in page['pats']:
                    fields = fields_for(p)
                    parts.append(f'<h2 class="classheading" id="{p["name"]}">{html.escape(heading)}</h2>')
                    parts.append(diagram(enc_for([p], fields)))
                    parts.append(opbits(p) + note(p) + runs(p))
                fields = fields_for(page['pats'][0][1])
                parts.append('<h3>Fields</h3>' + by_form_note + field_table(fields))
            else:
                ps = [p for h, p in page['pats']]
                fields = fields_for(ps[0])
                parts.append(f'<h2 class="classheading" id="{ps[0]["name"]}">Encoding</h2>')
                parts.append(diagram(enc_for(ps, fields)))
                parts.append('<p class="bits">' + '<br>'.join(opbits(p)[len('<p class="bits">'):-4] for p in ps) + '</p>')
                forms = SM86_FORMS.get(page['kind'])
                if forms:
                    rows = ''.join(f'<tr><td>{int(p["bits"][4:7], 2)} ({p["bits"][4:7]})</td>'
                                   f'<td>{forms.get(int(p["bits"][4:7], 2), ("?", "?"))[0]}</td>'
                                   f'<td>{forms.get(int(p["bits"][4:7], 2), ("?", "?"))[1]}</td></tr>' for p in ps)
                    parts.append(f'<h3>Forms</h3><table class="fields"><tr><th>Form (bits 11:9)</th><th>b</th>'
                                 f'<th>c</th></tr>{rows}</table>')
                notes = []
                for p in ps:
                    if p['note'] and p['note'] not in notes:
                        notes.append(p['note'])
                parts += [f'<p class="note">{html.escape(n_)}</p>' for n_ in notes]
                parts.append(runs(ps[0]))
                parts.append('<h3>Fields</h3>' + by_form_note + field_table(fields))
            for f in fns:
                ex = defs.get('execute_' + f)
                if not ex:
                    continue
                d = ex['snx'][-1]
                parts.append(f'<h2 class="pseudocode" id="execute_{f}">Operation <a class="src" '
                             f'href="{site.source_link(d)}">Sail</a></h2>')
                if d.comment:
                    parts.append(f'<p>{html.escape(d.comment)}</p>')
                parts.append(code(body(d), top_links, f'{key}.html', with_links, linked))
            fdone = []
            for heading, p in page['pats']:
                for fn in fused.get(p['name'], []):
                    if fn in fdone or fn not in defs:
                        continue
                    fdone.append(fn)
                    d = defs[fn]['snx'][-1]
                    parts.append(f'<h2 class="pseudocode">Fusion {fn} <a class="src" href="{site.source_link(d)}">Sail</a></h2>')
                    if d.comment:
                        parts.append(f'<p>{html.escape(d.comment)}</p>')
                    for part in (fn + '_ok', fn):
                        if part in defs:
                            parts.append(code(defs[part]['snx'][-1].text, top_links, f'{key}.html', with_links, linked))
            text = site.page(key, page['title'], '\n'.join(parts), 1, manual=manual)
            if len(text.encode()) <= MAX_BYTES or not with_links:
                break
        site.write(rel, text)
        for heading, p in page['pats']:
            mask = sum(1 << (15 - k) for k, c in enumerate(p['bits']) if c != '-')
            value = sum(1 << (15 - k) for k, c in enumerate(p['bits']) if c == '1')
            if gid != 'sm53' and page['kind'] in SM86_FORMS:
                heading = f'form {int(p["bits"][4:7], 2)}'
            out_rows.append([page['title'], f'{rel}#{p["name"] if gid == "sm53" else page["pats"][0][1]["name"]}',
                             g['set'], heading, f'{mask:x}', f'{value:x}', '0', '0', str(p['order'])])

    # the shared pseudocode: a page per name, a long one over several
    fn_links = links('../')
    for n in helpers:
        d0 = defs[n]['snx'][-1]
        users = sorted(used_by.get(n, ()), key=lambda u: (u not in executes, u.lower()))
        items, seen = [], set()
        for u in users:
            if u in executes:
                if executes[u] not in seen:
                    seen.add(executes[u])
                    items.append(f'<li><a href="../{executes[u]}.html">{html.escape(pages[executes[u]]["title"])}</a></li>')
            elif u in helpers:
                items.append(f'<li><a href="{u}.html">{html.escape(u)}</a></li>')
        used = '<h2>Used by</h2><ul class="cols">' + ''.join(items) + '</ul>' if items else ''
        head = (f'<h1>{html.escape(n)}</h1><p><a class="src" href="{site.source_link(d0)}">'
                f'{d0.source[1].rsplit("/", 1)[1]}</a></p>' + (f'<p>{html.escape(d0.comment)}</p>' if d0.comment else ''))
        text_all = '\n\n'.join(d.text for d in defs[n]['snx'])
        lines = text_all.split('\n')
        chunks, cur = [], []
        for line in lines:
            cur.append(line)
            if len('\n'.join(cur).encode()) > 9000:
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        for k, chunk in enumerate(chunks, 1):
            nav = '' if len(chunks) == 1 else '<p>Part ' + ' '.join(
                (f'<a href="{n}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                for j in range(1, len(chunks) + 1)) + '</p>'
            pagehtml = head + nav + code('\n'.join(chunk), fn_links, f'../fn/{n}.html') + nav + (used if k == len(chunks) else '')
            text = site.page(n, n, pagehtml, 2, manual=manual)
            if len(text.encode()) > MAX_BYTES:
                text = site.page(n, n, head + nav + code('\n'.join(chunk), {}, '') + nav + (used if k == len(chunks) else ''), 2, manual=manual)
            site.write(f'{gid}/fn/{n}{"" if k == 1 else f"-{k}"}.html', text)

    # the indexes
    for grp in groups:
        rows = sorted(((p['title'], k) for k, p in pages.items() if grp in p['groups']), key=lambda r: (r[0].lower(), r[1]))
        slug = gslug[grp]

        def render(chunk, k, n, grp=grp, slug=slug):
            nav = '' if n == 1 else '<p>Page ' + ' '.join(
                (f'<a href="{slug}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                for j in range(1, n + 1)) + '</p>'
            return site.page(grp, grp, f'<h1>{html.escape(grp)}</h1>{nav}<ul class="cols">' + ''.join(
                f'<li><a href="{key}.html">{html.escape(t)}</a></li>' for t, key in chunk) + f'</ul>{nav}', 1, manual=manual)

        split = split_pages(rows, render, f'{gid}/{slug}.html')
        for k, (rel, chunk) in enumerate(split, 1):
            site.write(rel, render(chunk, k, len(split)))

    def render_shared(chunk, k, n):
        nav = '' if n == 1 else '<p>Page ' + ' '.join(
            (f'<a href="shared{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
            for j in range(1, n + 1)) + '</p>'
        return site.page('Shared pseudocode', 'Shared pseudocode', f'<h1>{g["title"]}: shared pseudocode</h1>{nav}'
                         '<ul class="cols">' + ''.join(f'<li><a href="fn/{n_}.html">{html.escape(n_)}</a></li>'
                                                      for n_ in chunk) + f'</ul>{nav}', 1, manual=manual)

    split = split_pages(helpers, render_shared, f'{gid}/shared.html')
    for k, (rel, chunk) in enumerate(split, 1):
        site.write(rel, render_shared(chunk, k, len(split)))
    with_sail = sum(1 for p in pages.values() if p['sail'])
    glist = ''.join(f'<li><a href="{gslug[grp]}.html">{html.escape(grp)}</a> '
                    f'({sum(1 for p in pages.values() if grp in p["groups"])})</li>' for grp in groups)
    site.write(f'{gid}/index.html', site.page(g['name'], g['name'],
               f'<h1>{g["name"]}: {g["title"][g["title"].index("(") + 1:-1]}</h1><p>{g["about"][0].upper() + g["about"][1:]}, laid out as Arm\'s reference lays an instruction '
               f'out: each encoding\'s diagram (its opcode from <code>{g["decode"]}</code>, the fields the decoder and '
               f'the Sail read) and the operation in ScarletNX\'s Sail. {len(pages)} instructions, {len(pats)} encodings; '
               f'{with_sail} with Sail.</p><div id="search" data-root="../"></div>'
               f'<p>The search takes a name (the nearest when none is the same) or {g["word"]}.</p>'
               f'<h2>Instructions</h2><ul>{glist}</ul><h2>Shared pseudocode</h2>'
               f'<p><a href="shared.html">Every function and type the instructions use</a> ({len(helpers)})</p>'
               f'<p>The <a href="../">ARM ISA</a>, and the '
               + ' and '.join(f'<a href="../{o["id"]}/">{o["name"]}</a>' for o in GPUS if o is not g) + '.</p>',
               1, search=[gid], manual=manual))
    return len(pages), len(pats)


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
    commit = commit or find_commit(root, [a['dir'] for a in ARCHES] + [GPU_DIR])
    here = os.path.dirname(os.path.abspath(__file__))

    # the manual is made whole each time: what the Sail no longer has goes
    for a in ARCHES + GPUS:
        shutil.rmtree(os.path.join(out, a['id']), ignore_errors=True)
    site = Site(out, commit)
    summary = []
    for a in ARCHES:
        rows = []
        n_pages, n_clauses = build_arch(site, root, a, rows)
        site.write(f'{a["id"]}/data.js', '// The search\'s data (tools/gen-manual.py): title, page, instruction set, '
                   'class, mask, value, the bits that must not be a value (mask, value), and the order the decoder tries it in\n'
                   'var ARM = (window.ARM || []).concat([\n' + ',\n'.join(
                       '[' + ','.join('"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"' for v in r) + ']'
                       for r in rows) + '\n]);\nwindow.ARM = ARM;\n')
        summary.append(f'<li><a href="{a["id"]}/">{a["title"]}</a>: {a["about"]} ({n_pages} instructions, {n_clauses} encodings)</li>')
    gpus = []
    for g in GPUS:
        if not os.path.exists(os.path.join(root, GPU_DIR, g['decode'])):
            continue
        rows = []
        n_pages, n_pats = build_gpu(site, root, g, rows)
        site.write(f'{g["id"]}/data.js', '// The search\'s data (tools/gen-manual.py): title, page, instruction set, '
                   'class, mask, value (of the 16-bit opcode), none, and the order of the encodings\' file\n'
                   'var ARM = (window.ARM || []).concat([\n' + ',\n'.join(
                       '[' + ','.join('"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"' for v in r) + ']'
                       for r in rows) + '\n]);\nwindow.ARM = ARM;\n')
        gpus.append(f'<li><a href="{g["id"]}/">{g["name"]}</a>: {g["title"]} ({n_pages} instructions, {n_pats} encodings)</li>')
    for name in ('manual.css', 'search.js'):
        shutil.copyfile(os.path.join(here, 'manual', name), os.path.join(out, name))
    shutil.copyfile(os.path.join(root, ARCHES[0]['dir'], 'LICENSE'), os.path.join(out, 'LICENSE-sail-arm.txt'))
    site.write('index.html', site.page('ARM ISA', 'ARM ISA',
               '<h1>ARM ISA</h1><p>The instructions ScarletNX recompiles, laid out as Arm\'s reference lays them out '
               'and made from the Sail it recompiles them from: <a href="https://github.com/rems-project/sail-arm">'
               'sail-arm</a>\'s model of Armv9.4-A, and ScarletNX\'s fixups of it. Each instruction has its encodings, '
               'their decode and its operation; every name they use is a page of the shared pseudocode.</p>'
               '<div id="search" data-root=""></div>'
               f'<ul>{"".join(summary)}</ul>'
               '<p>The search takes a name (the nearest when none is the same) or an instruction word in hex '
               '(<code>0x1a020020</code>, or a Thumb halfword <code>0x4148</code>): it lists every encoding it '
               'matches.</p>' + (f'<h2>The GPUs\' instructions</h2><ul>{"".join(gpus)}</ul>' if gpus else ''),
               0, search=[a['id'] for a in ARCHES]))
    print(f'{len(site.written)} files in {out} (ScarletNX {commit[:12]})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
