#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Makes the ISA manuals (manual/) from ScarletNX's Sail: ARM's (A64 and AArch32), Maxwell's (SM53), Ampere's (SM86),
the PICA200's (the 3DS's GPU) and the USSE's (the Vita's GPU); and the NVN API (manual/nvn) from nvn.hook and nvn.h.

    tools/gen-manual.py SCARLETNX [OUT]     OUT is _site/manual beside tools/ when not named

The exit status is 0, or 3 when the site is made in part: each manual is made alone, and a page or a source file
that fails is left out of its manual, so ScarletNX's sources changing breaks only what reads them. A page in the
place of what failed says why, and stderr lists each (a warning of the run in GitHub's Actions).
        --commit HASH       the ScarletNX commit the Sail is from, for the links to it (else asked of git, else main)

SCARLETNX is a checkout of ScarletNX; it reads src/common/cpu/aarch64/sail, src/common/cpu/arm/sail,
src/nx/gpu/shader, src/3ds/gpu, src/vita/gpu, src/3ds/services, src/android/framework and src/nx/gpu/nvn (a GPU manual is left out when its files aren't there). Every instruction is a page laid out as Arm's
reference lays one out:
  ARM (manual/a64, manual/a32): made only from the Sail. Each class an encoding diagram (the fixed bits, the fields,
    under them the names of the fields the encoding fixes), its decode and the operation.
  Maxwell and Ampere (manual/sm53, manual/sm86): the opcode from the encodings' file (sm53.decode, sm86.decode), the
    fields the decoder gives and those the Sail reads (Field(lo, n), through the Sail's calls), the file's notes,
    and the operation in the Sail (the function the .roots file runs for it, and its fusions).
  PICA200 and USSE (manual/pica, manual/usse): the encodings' file (pica.decode, usse.decode) names every bit of the
    word, so each pattern's diagram is the file's, its format's and fields'; the fields' table says which of the
    Sail's functions read each, and the operation is the Sail's, as for Maxwell's.
  3DS IPC (manual/3ds-ipc): the commands of src/3ds/services/*.swipc, each request's and response's words as
    swipc --ctr's dispatcher reads and writes them, and the handler.
  Android (manual/android): the Java side of src/android/framework as javadoc reads it: each public and protected
    type and member, its declaration, its doc comment (/** */), the source's groups of members (// ---- name ----).
  nn (manual/nn): the hooks of src/nx/hle/hook/hooks.hook and src/nx/nn/*.hook by family and by namespace, each C++
    symbol demangled (an Itanium demangler of the names the hooks use), and the SVCs of src/nx/hle/svc/hos.svc in a
    table by number with their registers in both ABIs, laid out as tools/svcgen lays them out.
  Driver bugs (manual/driver-bugs): src/common/gpu/vk/extension_bans.txt as one table, which sort.js sorts by a
    column; its page may be 128 KB.
  NVN (manual/nvn): each function's signature, its doc comment (nvn.hook's ## @brief, @param, @return) and handler.
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
import traceback

MAX_BYTES = 16 * 1024


class GenError(Exception):
    """A page or a manual this can't make: a page over the size, sources it doesn't read"""


def report(what):
    """A failure, on stderr; in GitHub's Actions an annotation of the run too"""
    print(f'gen-manual: {what}', file=sys.stderr)
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print(f'::warning title=gen-manual::{what}', file=sys.stderr)
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
        if c.decode not in defs:  # the extract (sailgen --extract) left it out: no root reaches it
            continue
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
        self.out, self.commit, self.written, self.failures, self.root = out, commit, [], [], '\0'

    def failed(self, what, e):
        """A page or a source file that failed: the rest goes on"""
        reason = f'{type(e).__name__}: {e}'.replace(self.root, '')  # the checkout's paths, not the machine's
        report(f'{what}: {reason}')
        self.failures.append((what, reason))
        return reason

    def failed_page(self, rel, title, depth, manual, e):
        """A page that failed: one in its place says why, so the links to it still lead somewhere"""
        reason = self.failed(rel, e)
        self.write(rel, self.page(title, title, f'<h1>{html.escape(title)}</h1><p>This page could not be made from '
                                                f'ScarletNX at {self.commit[:12]}: <code>{html.escape(reason)}</code>.</p>',
                                  depth, manual=manual))

    def write(self, rel, content, limit=MAX_BYTES):
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = content.encode('utf-8')
        if rel.endswith('.html') and len(data) > limit:
            raise GenError(f'{rel}: {len(data)} bytes, over {limit}')
        with open(path, 'wb') as f:
            f.write(data)
        self.written.append(rel)

    def page(self, rel, title, body_html, depth, search=None, manual=None, scripts=()):
        """A page depth folders under manual/; manual: the GPU manual's (name, folder, footer) it is of"""
        up = '../' * depth
        home = up or './'
        name = 'ARM ISA'
        foot = (f'sail-arm\'s definitions are Arm\'s ASL in Sail (BSD 3-Clause Clear, '
                f'<a href="{up}LICENSE-sail-arm.txt">license</a>); ScarletNX\'s fixups are GPL-3.0-or-later.')
        if manual:
            name, folder, foot = manual
            home = up + folder + '/'
        if search:  # search.js loads the data when the box is first used
            body_html = body_html.replace('<div id="search" ', '<div id="search" data-load="' + ' '.join(
                f'{up}{s}/data.js' for s in search) + '" ', 1)
            scripts = (f'<script src="{up}search.js"></script>',) + tuple(scripts)
        scripts = ''.join(x if x.startswith('<') else f'<script src="{up}{x}"></script>' for x in scripts)
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


# What a diagram's cell is, for its colour (manual.css, and LEGEND): a fixed bit, a field, a bit of a field the
# encoding fixes, a bit that should be a value
LEGEND = ('<p class="legend"><span class="b">fixed bit</span> <span class="f">field</span> '
          '<span class="x">field the encoding fixes</span> <span class="s">should be</span></p>')


def cell(text, box, kind, span=1):
    cls = ' '.join(c for c in (box, kind) if c)
    return (f'<td colspan="{span}"' if span > 1 else '<td') + (f' class="{cls}">' if cls else '>') + f'{text}</td>'


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
                    first.append(cell(name, 'lr', 'f', len(span)))
                    second.append((len(span), ''))
                else:
                    for k, v in zip(span, fixed):
                        cls = 'lr' if len(span) == 1 else 'l' if k == span[0] else 'r' if k == end else ''
                        kind = 's' if not v and k in c.should else 'x'
                        v = v or (f'({c.should[k]})' if k in c.should else 'x')
                        first.append(cell(v, cls, kind))
                    second.append((len(span), name))
                b = end - 1
                continue
            run = []
            while b >= row_lo and b not in field_at:
                run.append(b)
                b -= 1
            for k in run:
                cls = 'lr' if len(run) == 1 else 'l' if k == run[0] else 'r' if k == run[-1] else ''
                kind = 'b' if c.bits.get(k) else 's' if k in c.should else ''
                v = c.bits.get(k) or (f'({c.should[k]})' if k in c.should else '')
                first.append(cell(v, cls, kind))
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
            for d in (defs[c.decode]['arm'] + defs[c.decode]['snx'] if c.decode in defs else []):
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
        try:
            rel = f'{aid}/{key}.html'
            for with_links, linked in ((True, None), (True, set()), (False, None)):
                parts = [f'<h1>{html.escape(page["title"])}</h1>',
                         '<p class="groups">' + ' / '.join(
                             f'<a href="{g[len("__Decode"):]}.html">{html.escape(arch["groups"][g])}</a>'
                             for g in sorted(page['groups'])) + '</p>', LEGEND]
                executes = []
                for heading, c in page['classes']:
                    anchor = re.sub(r'\W+', '_', heading)
                    parts.append(f'<h2 class="classheading" id="{anchor}">{html.escape(heading)}</h2>')
                    parts.append(diagram(c))
                    extra = guard_text(c)
                    parts.append(f'<p class="bits">{c.pattern}'
                                 + (''.join(f'<br>{html.escape(g)}' for g in extra)) + '</p>')
                    if c.decode not in defs:
                        parts.append(f'<h3>Decode</h3><p>The Sail has no <code>{c.decode}</code>: ScarletNX\'s extract of '
                                     f'sail-arm keeps what its roots reach, and none reaches it.</p>')
                        continue
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
        except Exception as e:  # its sources changed in a way this doesn't read: this page alone fails
            site.failed_page(f'{aid}/{key}.html', page['title'], 1, None, e)

    # shared pseudocode: a page per name
    fn_links = links(1)
    for n in helpers:
        try:
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
        except Exception as e:  # its sources changed in a way this doesn't read: this page alone fails
            site.failed_page(f'{aid}/fn/{n}.html', n, 2, None, e)

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
BUILT = set()  # the GPU manuals this run makes (their Sail is there), which the indexes link to

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
        title = re.sub(r'^(SM\d+|The \w+)\'s ', '', comments[0]).split(' (')[0]
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


def load_gpu_sail(base, dir_rel, rels):
    """The definitions of a GPU's Sail files, by name; a val and the function after it one definition. Each knows
    the section of its file it is in (a /* ---- name ---- */ line before it)"""
    defs = {}
    for rel in rels:
        path = os.path.join(base, rel)
        if not os.path.exists(path):
            continue
        sections = [(n, m.group(1)) for n, line in enumerate(open(path, encoding='utf-8'), 1)
                    for m in [re.match(r'/\* ---- (.+?) ---- \*/$', line.strip())] if m]
        for d in parse(path, ('snx', f'{dir_rel}/{rel}')):
            if d.kind == 'clause':
                continue
            d.section = ([t for n, t in sections if n < d.line] or [None])[-1]
            entry = defs.setdefault(d.name, {'arm': [], 'snx': []})
            last = entry['snx'][-1] if entry['snx'] else None
            if last and last.kind == 'val' and d.kind == 'function':
                last.text += '\n\n' + d.text
                last.kind = 'function'
                last.comment = ' '.join(c for c in (last.comment, d.comment) if c)
            else:
                entry['snx'].append(d)
    return defs


def gpu_used_by(defs, enum_members):
    """Who names what: a definition's users"""
    used_by = {}
    for n, entry in defs.items():
        for d in entry['snx']:
            for ref in set(IDENT.findall(d.text)) - {n}:
                ref = enum_members.get(ref, ref)
                if ref in defs:
                    used_by.setdefault(ref, set()).add(n)
    return used_by


def other_manuals(g):
    """The links of a manual's index to the other manuals made"""
    names = ['the <a href="../">ARM ISA</a>'] + [f'the <a href="../{o["id"]}/">{o["name"]}</a>' for o in GPUS + DECODED
                                                if o is not g and o['id'] in BUILT]
    names += [f'the <a href="../{i}/">{n}</a>' for i, n in (('nvn', 'NVN API'), ('nn', 'nn API'), ('3ds-ipc', '3DS IPC'),
                                                           ('android', 'Android API'), ('driver-bugs', 'Driver bugs'))
              if i != g['id'] and i in BUILT]
    text = ', '.join(names[:-1]) + ' and ' + names[-1] if len(names) > 1 else names[0]
    return f'<p>{text[0].upper() + text[1:]}.</p>'


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
    defs = load_gpu_sail(base, GPU_DIR, g['sails'] + [f for f in files if f not in g['sails']])

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
    used_by = gpu_used_by(defs, enum_members)

    op_hi = g['op_lo'] + 15
    for key, page in sorted(pages.items()):
        try:
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
                                                           for grp in page['groups']) + '</p>', LEGEND]
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
        except Exception as e:  # its sources changed in a way this doesn't read: this page alone fails
            site.failed_page(f'{gid}/{key}.html', page['title'], 1, manual, e)

    with_sail = sum(1 for p in pages.values() if p['sail'])
    gpu_pages(site, g, manual, defs, helpers, used_by, executes, pages, groups, gslug, links,
              f'laid out as Arm\'s reference lays an instruction out: each encoding\'s diagram (its opcode from '
              f'<code>{g["decode"]}</code>, the fields the decoder and the Sail read) and the operation in ScarletNX\'s '
              f'Sail. {len(pages)} instructions, {len(pats)} encodings; {with_sail} with Sail.')
    return len(pages), len(pats)


def gpu_pages(site, g, manual, defs, helpers, used_by, executes, pages, groups, gslug, links, intro):
    """A GPU manual's shared pseudocode (a page per name, a long one over several), its groups' indexes, the shared
    pseudocode's index and the manual's index, whose paragraph goes on with intro"""
    gid = g['id']
    # the shared pseudocode: a page per name, a long one over several
    fn_links = links('../')
    for n in helpers:
        try:
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
        except Exception as e:  # its sources changed in a way this doesn't read: this page alone fails
            site.failed_page(f'{gid}/fn/{n}.html', n, 2, manual, e)

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
    glist = ''.join(f'<li><a href="{gslug[grp]}.html">{html.escape(grp)}</a> '
                    f'({sum(1 for p in pages.values() if grp in p["groups"])})</li>' for grp in groups)
    site.write(f'{gid}/index.html', site.page(g['name'], g['name'],
               f'<h1>{g["name"]}: {g["title"][g["title"].index("(") + 1:-1]}</h1><p>{g["about"][0].upper() + g["about"][1:]}, '
               f'{intro}</p><div id="search" data-root="../"></div>'
               f'<p>The search takes a name (the nearest when none is the same) or {g["word"]}.</p>'
               f'<h2>Instructions</h2><ul>{glist}</ul><h2>Shared pseudocode</h2>'
               f'<p><a href="shared.html">Every function and type the instructions use</a> ({len(helpers)})</p>'
               + other_manuals(g),
               1, search=[gid], manual=manual))


# ---- the 3DS's and the Vita's GPUs (PICA200, USSE): their encodings' files name every field of the word ----

DECODED = [
    {
        'id': 'pica', 'name': 'PICA200 ISA', 'title': 'PICA200 (3DS)', 'set': 'PICA', 'width': 32, 'dir': 'src/3ds/gpu',
        'decode': 'pica.decode', 'prefix': 'P_', 'roots': 'sail/pica.roots', 'sails': ['sail/pica.sail'],
        'about': 'the vertex shader instructions of the 3DS\'s GPU (the PICA200) that ScarletNX\'s shader decompiler '
                 '(<code>vk/vsgen.c</code>) takes',
        'word': 'a 32-bit instruction word in hex (<code>0x4c000000</code>)',
        'encodings': 'nihstro\'s <code>shader_bytecode.h</code> (BSD-3-Clause), as Azahar reads them',
    },
    {
        'id': 'usse', 'name': 'USSE ISA', 'title': 'USSE (SGX543)', 'set': 'USSE', 'width': 64, 'dir': 'src/vita/gpu',
        'decode': 'usse.decode', 'prefix': 'U_', 'roots': 'sail/usse.roots', 'sails': ['sail/usse.sail'],
        'about': 'the shader instructions of the Vita\'s GPU (the SGX543\'s USSE) that ScarletNX\'s shader translator '
                 '(<code>usse.c</code>) takes',
        'word': 'a 64-bit instruction word in hex (<code>0x3800000000000000</code>)',
        'encodings': 'Vita3K\'s <code>usse_translator_entry.cpp</code> (GPL-2.0-or-later)',
    },
]


def parse_decodetree(path, width):
    """The patterns of a decodetree file whose patterns are whole words, in order, each with its format's bits and
    fields put in: name, bits (left bit first: '0', '1', '-' ignored, 'f' a field's), fields (name and its segments
    (lo, n), the most significant first), the format's name and its note, the note before the pattern, and the { }
    group it is in (the decoder tries a group's patterns in order: the first that matches wins)"""
    lines, cont = [], ''
    for line in open(path, encoding='utf-8').read().split('\n'):
        if line.rstrip().endswith('\\'):
            cont += line.rstrip()[:-1] + ' '
            continue
        lines.append(cont + line)
        cont = ''
    fields, formats, pats, groups = {}, {}, [], []
    block, blank_before, fmt_note, depth = [], True, None, 0

    def layout(tokens, what):
        bits, flds = [], []
        for t in tokens:
            if t[0] in '&@':
                continue
            m = re.fullmatch(r'([A-Za-z_]\w*):s?(\d+)', t)
            if m:
                n = int(m.group(2))
                flds.append((m.group(1), [(width - len(bits) - n, n)]))
                bits += ['f'] * n
                continue
            m = re.fullmatch(r'(?:([A-Za-z_]\w*)=)?%(\w+)', t)
            if m:
                flds.append((m.group(1) or m.group(2), fields[m.group(2)]))
                continue
            if re.fullmatch(r'[A-Za-z_]\w*=\w+', t):  # a constant argument: no bits
                continue
            if not re.fullmatch(r'[01.\-]+', t):
                raise GenError(f'{path}: {what}: no bits {t!r}')
            bits += list(t)
        if len(bits) != width:
            raise GenError(f'{path}: {what}: {len(bits)} bits, not {width}')
        return bits, flds

    for line in lines:
        s = line.strip()
        if s.startswith('#'):
            block.append(s[1:].strip())
            continue
        if not s:
            if block and blank_before and len(block) == 1 and block[0][:1].islower():
                pass  # a section's heading over the patterns after it
            block, blank_before, fmt_note = [], True, None
            continue
        note = ' '.join(b for b in block if b) or None
        before, block, blank_before = blank_before, [], False
        if s == '{':
            depth += 1
            groups.append([])
            continue
        if s == '}':
            depth -= 1
            continue
        w = s.split()
        if w[0].startswith('%'):
            fields[w[0][1:]] = [(int(lo), int(n.lstrip('s'))) for lo, n in (seg.split(':') for seg in w[1:])]
        elif w[0].startswith('&'):
            pass
        elif w[0].startswith('@'):
            fmt_note = note or fmt_note
            formats[w[0][1:]] = layout(w[1:], w[0]) + (fmt_note,)
        else:
            bits, flds = layout(w[1:], w[0])
            fmt = next((t[1:] for t in w[1:] if t.startswith('@')), None)
            if fmt:
                fbits, fflds, _ = formats[fmt]
                bits = [f if b == '.' else b for b, f in zip(bits, fbits)]
                flds = fflds + flds
            for _, segs in flds:  # the bits of a field put together from several places
                for lo, n in segs:
                    for b in range(lo, lo + n):
                        if bits[width - 1 - b] == '.':
                            bits[width - 1 - b] = 'f'
            bits = ['-' if b == '.' else b for b in bits]
            if note and before and len(note.split()) <= 12 and note[:1].islower() and '(' not in note:
                note = None  # a section's heading, not the pattern's note
            pat = {'name': w[0], 'bits': bits, 'fields': flds, 'format': fmt,
                   'format_note': formats[fmt][2] if fmt else None, 'note': note, 'order': len(pats),
                   'group': groups[-1] if depth else None}
            if depth:
                groups[-1].append(w[0])
            pats.append(pat)
    return pats


def field_bits(segs):
    """A field's bits as the tables write them: 31:26, or 53:52, 50, 35:34 for one put together"""
    return ', '.join(f'{lo + n - 1}:{lo}' if n > 1 else f'{lo}' for lo, n in segs)


def build_decoded(site, root, g, out_rows):
    gid, base = g['id'], os.path.join(root, g['dir'])
    width = g['width']
    manual = (g['name'], gid, f'The Sail and the encodings\' file are ScarletNX\'s (GPL-3.0-or-later); its encodings '
                              f'are from {g["encodings"]}.')
    pats = parse_decodetree(os.path.join(base, g['decode']), width)
    ops, fuses, family, files = parse_roots(base, g['roots'])
    defs = load_gpu_sail(base, g['dir'], g['sails'] + [f for f in files if f not in g['sails']])

    def fn_of(name):
        return ops.get(g['prefix'] + name)

    # a page per pattern; its group the roots' family (a roots file each), else the Sail's section of its operation
    pages = {}
    for p in pats:
        f = fn_of(p['name'])
        if not f:
            grp = 'Without Sail'
        elif files:
            grp = family[g['prefix'] + p['name']]
        else:
            d = defs.get('execute_' + f[0])
            grp = (d and d['snx'][-1].section) or family[g['prefix'] + p['name']]
        grp = grp[0].upper() + grp[1:]
        pages[p['name']] = {'title': p['name'], 'pat': p, 'groups': [grp], 'sail': bool(f)}
    groups = []
    for page in pages.values():
        if page['groups'][0] not in groups:
            groups.append(page['groups'][0])
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
    for key in sorted((k for k in pages if fn_of(k)), key=lambda k: fn_of(k)[1]):  # the page of the roots' first
        f = fn_of(key)
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
    used_by = gpu_used_by(defs, enum_members)
    shared_fn = {}  # an operation several opcodes run: how many
    for f, _ in ops.values():
        shared_fn[f] = shared_fn.get(f, 0) + 1

    for key, page in sorted(pages.items()):
        try:
            p = page['pat']
            rel = f'{gid}/{key}.html'
            f = fn_of(key)
            sail_fields = []
            if f:
                sail_fields, _ = gpu_fields(defs, 'execute_' + f[0])
            for fn in fused.get(key, []):
                for part in (fn + '_ok', fn):
                    sail_fields += gpu_fields(defs, part)[0]

            # the encoding: the fixed bits, and every field of the file (one put together from several places, each
            # place a field of its own, named by the bits of the field's value it holds)
            enc_fields = []
            for name, segs in p['fields']:
                if len(segs) == 1:
                    enc_fields.append((name, segs[0][0], segs[0][1]))
                    continue
                top = sum(n for _, n in segs)
                for lo, n in segs:
                    enc_fields.append((f'{name}[{top - 1}:{top - n}]' if n > 1 else f'{name}[{top - 1}]', lo, n))
                    top -= n
            fixed = {width - 1 - k: b for k, b in enumerate(p['bits']) if b in '01'}
            enc = Encoding(width, {b: fixed.get(b) for b in range(width)}, enc_fields)

            # the fields' table: each field of the file, and which of the Sail's functions read it (or bits of it); then
            # what the Sail reads outside them
            readers, outside = {name: [] for name, _ in p['fields']}, []
            spans = {name: set(b for lo, n in segs for b in range(lo, lo + n)) for name, segs in p['fields']}
            for name, lo, n, src in sail_fields:
                bits_read = set(range(lo, lo + n))
                whole = next((fn for fn, segs in p['fields'] if (lo, n) in segs), None)  # it, or a piece of it
                if whole:
                    what = src
                else:
                    whole = next((fn for fn in spans if bits_read <= spans[fn]), None)
                    what = f'{src} ({lo + n - 1}:{lo})' if n > 1 else f'{src} ({lo})'
                if whole:
                    if what not in readers[whole]:
                        readers[whole].append(what)
                elif (name, lo, n, src) not in outside:
                    outside.append((name, lo, n, src))
            rows = [(name, segs[0][0] + segs[0][1], f'<tr><td>{html.escape(name)}</td><td>{field_bits(segs)}</td>'
                           f'<td>{html.escape(", ".join(readers[name]))}</td></tr>') for name, segs in p['fields']]
            rows += [(name, lo + n, f'<tr><td>{html.escape(name)}</td><td>{field_bits([(lo, n)])}</td>'
                                    f'<td>{html.escape(src)} (not a field of the file)</td></tr>')
                     for name, lo, n, src in outside]
            rows.sort(key=lambda r: -r[1])
            table = ('<table class="fields"><tr><th>Field</th><th>Bits</th><th>The Sail reads it in</th></tr>'
                     + ''.join(r[2] for r in rows) + '</table>')
            shared_note = (f'<p>Its operation is {shared_fn[f[0]]} opcodes\' (<code>Form()</code> tells them apart), so '
                           f'it may read the fields of their layouts too.</p>' if f and shared_fn[f[0]] > 1 else '')

            pattern = ''.join('x' if b == 'f' else b for b in p['bits'])
            pattern = ' '.join(pattern[i:i + 4] for i in range(0, width, 4))
            if not f:
                runs = '<p>ScarletNX\'s Sail has no operation for it: the translator\'s own code takes it, or refuses it.</p>'
            else:
                runs = f'<p>Runs <a href="#execute_{f[0]}">execute_{f[0]}</a> with <code>Form()</code> {f[1]}.</p>'
            info = ''
            if p['note']:
                info += f'<p class="note">{html.escape(p["note"])}</p>'
            if p['format']:
                info += (f'<p>Its format is <code>@{p["format"]}</code>' + (f': {html.escape(p["format_note"])}'
                                                                            if p['format_note'] else '') + '.</p>')
            if p['group'] and len(p['group']) > 1:
                info += ('<p>It is in a group of patterns that may match the same word: the decoder tries them in this '
                         'order, and the first that matches decodes it: ' + ', '.join(n if n == key else f'<a href="{n}.html">{n}</a>'
                                                                   for n in p['group']) + '.</p>')
            for with_links, linked in ((True, None), (True, set()), (False, None)):
                parts = [f'<h1>{html.escape(page["title"])}</h1>',
                         '<p class="groups">' + ' / '.join(f'<a href="{gslug[grp]}.html">{html.escape(grp)}</a>'
                                                           for grp in page['groups']) + '</p>', LEGEND,
                         f'<h2 class="classheading" id="{key}">Encoding</h2>', diagram(enc),
                         f'<p class="bits">bits {width - 1}:0: {pattern}</p>', info, runs,
                         '<h3>Fields</h3>' + shared_note + table]
                if f and 'execute_' + f[0] in defs:
                    d = defs['execute_' + f[0]]['snx'][-1]
                    parts.append(f'<h2 class="pseudocode" id="execute_{f[0]}">Operation <a class="src" '
                                 f'href="{site.source_link(d)}">Sail</a></h2>')
                    if d.comment:
                        parts.append(f'<p>{html.escape(d.comment)}</p>')
                    parts.append(code(body(d), top_links, f'{key}.html', with_links, linked))
                for fn in fused.get(key, []):
                    if fn not in defs:
                        continue
                    d = defs[fn]['snx'][-1]
                    parts.append(f'<h2 class="pseudocode">Fusion {fn} <a class="src" href="{site.source_link(d)}">Sail</a></h2>')
                    if d.comment:
                        parts.append(f'<p>{html.escape(d.comment)}</p>')
                    for part in (fn + '_ok', fn):
                        if part in defs:
                            parts.append(code(defs[part]['snx'][-1].text, top_links, f'{key}.html', with_links, linked))
                text = site.page(key, page['title'], '\n'.join(x for x in parts if x), 1, manual=manual)
                if len(text.encode()) <= MAX_BYTES or not with_links:
                    break
            site.write(rel, text)
            mask = sum(1 << (width - 1 - k) for k, b in enumerate(p['bits']) if b in '01')
            value = sum(1 << (width - 1 - k) for k, b in enumerate(p['bits']) if b == '1')
            out_rows.append([key, f'{rel}#{key}', g['set'], page['groups'][0], f'{mask:x}', f'{value:x}', '0', '0',
                             str(p['order'])])
        except Exception as e:  # its sources changed in a way this doesn't read: this page alone fails
            site.failed_page(f'{gid}/{key}.html', page['title'], 1, manual, e)

    with_sail = sum(1 for p in pages.values() if p['sail'])
    gpu_pages(site, g, manual, defs, helpers, used_by, executes, pages, groups, gslug, links,
              f'laid out as Arm\'s reference lays an instruction out: each encoding\'s diagram (its bits and fields '
              f'from <code>{g["decode"]}</code>, and which the Sail reads) and the operation in ScarletNX\'s Sail. '
              f'{len(pages)} instructions; {with_sail} with Sail.')
    return len(pages), len(pats)


# ---- the 3DS IPC manual: the services' schemas (src/3ds/services/*.swipc), as swipc --ctr lays out their words ----

CTR_DIR = 'src/3ds/services'
CTR_MANUAL = ('3DS IPC', '3ds-ipc', 'The schemas and the handlers are ScarletNX\'s (GPL-3.0-or-later).')


def parse_swipc(path):
    """A .swipc file's types (name -> what it stands for) and interfaces: name, ports, line, comment over it, and
    commands (id, name, arguments (type, name, out), decorators, line, comment over it). A comment over a definition
    is the # or // lines right over it; ## lines are doxygen's commands (parse_doc)"""
    raw = open(path, encoding='utf-8').read()
    comments, text, i, line = {}, [], 0, 1
    while i < len(raw):  # the text without its comments, its lines kept; each line's comment
        if raw[i] == '#' or raw.startswith('//', i):
            j = raw.find('\n', i)
            j = len(raw) if j < 0 else j
            comments[line] = raw[i:j]
            text.append(' ' * (j - i))
            i = j
        elif raw.startswith('/*', i):
            j = raw.index('*/', i) + 2
            text.append(re.sub(r'[^\n]', ' ', raw[i:j]))
            line += raw.count('\n', i, j)
            i = j
        else:
            if raw[i] == '\n':
                line += 1
            text.append(raw[i])
            i += 1
    text = ''.join(text)

    def line_of(pos):
        return text.count('\n', 0, pos) + 1

    def comment_over(n):
        lines = []
        while n - 1 in comments and not comments[n - 1].lstrip('#/ ').startswith(('SPDX', 'Copyright')):
            n -= 1
            lines.insert(0, comments[n])
        doc = [l.lstrip()[2:].strip() for l in lines if l.lstrip().startswith(('##', '///'))]
        plain = ' '.join(re.sub(r'^(#|//)\s?', '', l.strip()) for l in lines
                         if not l.lstrip().startswith(('##', '///')))
        return plain.strip() or None, parse_doc(doc) if doc else None

    def split_args(body):
        out, depth, cur = [], 0, ''
        for ch in body:
            depth += {'<': 1, '>': -1, '(': 1, ')': -1}.get(ch, 0)
            if ch == ',' and depth == 0:
                out.append(cur)
                cur = ''
            else:
                cur += ch
        out.append(cur)
        result = []
        for a in (x.strip() for x in out):
            if a:
                m = re.match(r'(.+?)\s+(\w+)$', a, re.S)
                result.append((re.sub(r'\s+', ' ', m.group(1)) if m else a, m.group(2) if m else ''))
        return result

    types, ifaces, iface = {}, [], None
    pat = re.compile(r'\btype\s+(\w+)\s*=\s*([^;]+);'
                     r'|\binterface\s+([\w:]+)(?:\s+is\s+([^{]+?))?\s*\{'
                     r'|((?:@\w+(?:\([^)]*\))?\s*)*)\[\s*(\w+)\s*\]\s*(\w+)\s*\(([^)]*)\)\s*(?:->\s*(\([^)]*\)|[^;]+?))?\s*;'
                     r'|(\})', re.S)
    for m in pat.finditer(text):
        if m.group(1):
            types[m.group(1)] = re.sub(r'\s+', ' ', m.group(2).strip())
        elif m.group(3):
            n = line_of(m.start())
            comment, doc = comment_over(n)
            iface = {'name': m.group(3), 'ports': [x.strip() for x in (m.group(4) or '').split(',') if x.strip()],
                     'line': n, 'comment': comment, 'doc': doc, 'cmds': []}
            ifaces.append(iface)
        elif m.group(6) and iface is not None:
            n = line_of(m.start(6))
            comment, doc = comment_over(n)
            outs = m.group(9)
            if outs and outs.startswith('('):
                outs = split_args(outs[1:-1])
            elif outs:
                outs = split_args(outs)
            args = [(t, a, False) for t, a in split_args(m.group(8))] + [(t, a, True) for t, a in (outs or [])]
            iface['cmds'].append({'id': int(m.group(6), 0), 'name': m.group(7), 'args': args,
                                  'decorators': re.findall(r'@\w+', m.group(5) or ''), 'line': n,
                                  'comment': comment, 'doc': doc})
        elif m.group(10):
            iface = None
    return types, ifaces


def ctr_wire(cmd, types):
    """A command's words as swipc --ctr's dispatcher reads and writes them (tools/swipc/ctr.inc): the request's and the
    response's header and their words (index, what), and the handler's C prototype's parameters"""
    def resolve(t):
        seen = set()
        while t in types and t not in seen:
            seen.add(t)
            t = types[t]
        return t

    normal, pid, req, resp, params, runs = [0, 0], False, [], [], [], []
    for t, name, out in cmd['args']:
        r = resolve(t)
        hm = re.fullmatch(r'handle<\s*(copy|move)\b[^>]*>', r)
        bm = re.fullmatch(r'bytes<\s*(\w+)\s*>', r)
        im = re.fullmatch(r'u(32|64)', r)
        shown = t if t == r else f'{t} ({r})'
        if r == 'pid' and not out:
            pid = True
            params.append(f'uint32_t a_{name}')
        elif hm and out:
            move = hm.group(1) == 'move'
            if not runs or runs[-1][0] != move:
                runs.append([move, []])
            runs[-1][1].append((name, shown))
            params.append(f'uint32_t* a_{name}')
        elif im or (bm and int(bm.group(1), 0) % 4 == 0):
            words = int(im.group(1)) // 32 if im else int(bm.group(1), 0) // 4
            at = normal[out] + (2 if out else 1)
            for k in range(words):
                what = name if words == 1 else (f'{name}, low word' if im and k == 0 else f'{name}, high word' if im
                                                 else f'{name}, bytes {4 * k}-{4 * k + 3}')
                (resp if out else req).append((at + k, f'<code>{html.escape(name)}</code>: {html.escape(shown)}'
                                               if words == 1 else f'<code>{html.escape(what)}</code>: {html.escape(shown)}'))
            normal[out] += words
            params.append(f'{"" if out else "const "}uint8_t* a_{name}' if bm else
                          f'uint{im.group(1)}_t{"*" if out else ""} a_{name}')
        else:
            req.append((None, f'<code>{html.escape(name)}</code>: {html.escape(shown)}, a type swipc --ctr refuses'))
    if pid:
        req.append((normal[0] + 1, '0x20: the calling process\'s ID follows'))
        req.append((normal[0] + 2, '<code>{}</code>: the caller\'s process ID, which the kernel writes over the '
                                   'client\'s word'.format(html.escape(next(n for t, n, o in cmd['args']
                                                                            if resolve(t) == 'pid' and not o)))))
    at = normal[1] + 2
    for move, hs in runs:
        resp.append((at, f'0x{((len(hs) - 1) << 26) | (16 if move else 0):x}: {"moved" if move else "copied"} '
                         f'handle{"s" if len(hs) > 1 else ""}, {len(hs)}'))
        at += 1
        for name, shown in hs:
            resp.append((at, f'<code>{html.escape(name)}</code>: {html.escape(shown)}'))
            at += 1
    translated = at - normal[1] - 2
    req_header = cmd['id'] << 16 | normal[0] << 6 | (2 if pid else 0)
    resp_header = cmd['id'] << 16 | (normal[1] + 1) << 6 | translated
    req.insert(0, (0, f'header 0x{req_header:08x}: command 0x{cmd["id"]:x}, {normal[0]} normal word'
                      f'{"" if normal[0] == 1 else "s"}, {2 if pid else 0} translated'))
    resp.insert(0, (0, f'header 0x{resp_header:08x}: command 0x{cmd["id"]:x}, {normal[1] + 1} normal word'
                       f'{"" if normal[1] == 0 else "s"}, {translated} translated'))
    resp.insert(1, (1, 'the result: 0 for success. A failed command\'s response is the header and the result alone'))
    return req_header, resp_header, req, resp, params


def build_ctr_ipc(site, root, rows):
    base = os.path.join(root, CTR_DIR)
    schemas = sorted(f for f in os.listdir(base) if f.endswith('.swipc'))
    # the handlers' definitions in the services' C: file and line
    defined = {}
    for fname in sorted(os.listdir(base)):
        if fname.endswith('.c'):
            for n, line in enumerate(open(os.path.join(base, fname), encoding='utf-8'), 1):
                m = re.match(r'(?:static\s+)?uint32_t\s+(\w+)\(SnxCtrIpc\*', line)
                if m and not line.rstrip().endswith(';'):
                    defined.setdefault(m.group(1), (f'{CTR_DIR}/{fname}', n))
    ifaces, types = [], {}
    for f in schemas:
        try:
            t, fs = parse_swipc(os.path.join(base, f))
        except Exception as e:  # a schema this doesn't read: its interfaces are left out
            site.failed(f'{CTR_DIR}/{f}', e)
            continue
        types.update(t)
        for i in fs:
            i['schema'] = f
            ifaces.append(i)

    def page_of(i):
        name = i['ports'][0] if i['ports'] else i['name'].split('::')[-1]
        return re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_') or 'interface'

    def title_of(i):
        return ', '.join(i['ports']) if i['ports'] else i['name'].split('::')[-1]

    def page(rel, title, body, depth, search=False):
        site.write(f'3ds-ipc/{rel}', site.page(title, title, body, depth, search=['3ds-ipc'] if search else None,
                                               manual=CTR_MANUAL))

    def doc_parts(doc):
        if not doc:
            return []
        parts = [f'<p>{html.escape(doc["brief"])}</p>'] if doc['brief'] else []
        if doc['params']:
            parts.append('<table class="fields"><tr><th>Argument</th><th>Description</th></tr>' + ''.join(
                f'<tr><td><code>{html.escape(n)}</code></td><td>{html.escape(t)}</td></tr>' for n, t in doc['params'])
                + '</table>')
        if doc['return']:
            parts.append(f'<p>Returns: {html.escape(doc["return"])}</p>')
        parts += [f'<p>{html.escape(tag.capitalize())}: {html.escape(t)}</p>' for tag, t in doc['other']]
        return parts

    def words_table(words):
        return ('<table class="fields"><tr><th>Word</th><th>Contents</th></tr>' + ''.join(
            f'<tr><td>{"" if k is None else k}</td><td>{what}</td></tr>' for k, what in words) + '</table>')

    for i in ifaces:
        try:
            key = page_of(i)
            mangled = i['name'].replace('::', '_')
            src = f'{GITHUB}/{site.commit}/{CTR_DIR}/{i["schema"]}'
            blocks = []
            for c in i['cmds']:
                req_h, resp_h, req, resp, params = ctr_wire(c, types)
                handler = f'{mangled}_{c["name"]}'
                h = defined.get(handler)
                block = [f'<h2 id="{c["name"]}">{html.escape(c["name"])} <a class="src" href="{src}#L{c["line"]}">'
                         f'{i["schema"]}</a></h2>',
                         f'<p class="bits">command 0x{c["id"]:x}: request 0x{req_h:08x}, response 0x{resp_h:08x}</p>']
                if c['comment']:
                    block.append(f'<p>{html.escape(c["comment"])}</p>')
                block += doc_parts(c['doc'])
                if c['decorators']:
                    block.append(f'<p>Marked {", ".join(c["decorators"])}.</p>')
                block.append('<h3>Request</h3>' + words_table(req))
                block.append('<h3>Response</h3>' + words_table(resp))
                block.append(f'<h3>Handler</h3><pre class="sig">uint32_t {handler}(SnxCtrIpc* c'
                             + ''.join(f', {html.escape(x)}' for x in params) + ')</pre>'
                             + (f'<p><a href="{GITHUB}/{site.commit}/{h[0]}#L{h[1]}">{h[0].rsplit("/", 1)[1]}, line '
                                f'{h[1]}</a></p>' if h else ''))
                blocks.append('\n'.join(block))
                rows.append([c['name'], f'3ds-ipc/{key}.html#{c["name"]}', '3DS', f'{title_of(i)} 0x{c["id"]:x}',
                             'ffff0000', f'{c["id"] << 16:x}', '0', '0', str(c['id'])])
            head = [f'<h1>{html.escape(title_of(i))}</h1>',
                    f'<p>The interface <code>{html.escape(i["name"])}</code> of <a href="{src}#L{i["line"]}">'
                    f'{i["schema"]}</a>' + (f', the service{"s" if len(i["ports"]) > 1 else ""} '
                                           + ', '.join(f'<code>{html.escape(x)}</code>' for x in i['ports'])
                                           if i['ports'] else ', a session a service opens (no port of its own)')
                    + f'. {len(i["cmds"])} command{"" if len(i["cmds"]) == 1 else "s"}; the handlers are in '
                      f'<code>{CTR_DIR}</code>.</p>']
            if i['comment']:
                head.append(f'<p>{html.escape(i["comment"])}</p>')
            head += doc_parts(i['doc'])
            toc = '<ul class="cols">' + ''.join(f'<li><a href="#{c["name"]}">{html.escape(c["name"])}</a> (0x{c["id"]:x})</li>'
                                               for c in i['cmds']) + '</ul>'

            def render(chunk, k, n, key=key, head=head, toc=toc, i=i):
                nav = '' if n == 1 else '<p>Page ' + ' '.join(
                    (f'<a href="{key}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                    for j in range(1, n + 1)) + '</p>'
                return site.page(title_of(i), title_of(i), '\n'.join(head) + (toc if n == 1 else '') + nav
                                 + '\n'.join(chunk) + nav, 1, manual=CTR_MANUAL)

            for k, (rel, chunk) in enumerate(split_pages(blocks, render, f'3ds-ipc/{key}.html'), 1):
                n = len(split_pages(blocks, render, f'3ds-ipc/{key}.html'))
                site.write(rel, render(chunk, k, n))
        except Exception as e:  # its sources changed in a way this doesn't read: this page alone fails
            site.failed_page(f'3ds-ipc/{page_of(i)}.html', title_of(i), 1, CTR_MANUAL, e)

    ncmds = sum(len(i['cmds']) for i in ifaces)
    table = ('<table class="fields"><tr><th>Service</th><th>Interface</th><th>Commands</th><th>Schema</th></tr>'
             + ''.join(f'<tr><td><a href="{page_of(i)}.html">{html.escape(title_of(i))}</a></td>'
                       f'<td><code>{html.escape(i["name"])}</code></td><td>{len(i["cmds"])}</td>'
                       f'<td><a href="{GITHUB}/{site.commit}/{CTR_DIR}/{i["schema"]}">{i["schema"]}</a></td></tr>'
                       for i in sorted(ifaces, key=lambda i: title_of(i).lower())) + '</table>')
    page('index.html', '3DS IPC',
         '<h1>3DS IPC</h1><p>The 3DS services\' commands that ScarletNX\'s schemas declare '
         f'(<code>{CTR_DIR}/*.swipc</code>), each laid out word by word as the dispatcher <code>swipc --ctr</code> '
         'makes of the schema reads the request and writes the response, with the handler that answers it. '
         f'{len(ifaces)} interfaces, {ncmds} commands.</p>'
         '<div id="search" data-root="../" data-placeholder="Search: a command, or a header word in hex"></div>'
         '<p>The search takes a command\'s name (the nearest when none is the same) or a header word in hex '
         '(<code>0x00050100</code>): its bits 31:16 are the command.</p>'
         '<h2>The words</h2><p>A command is up to 64 words at the thread\'s TLS + 0x80. Its header is the command in '
         'bits 31:16, then the count of normal words (bits 11:6) and of translated words (bits 5:0); the normal '
         'words follow in the schema\'s order (u32 a word, u64 two, its low word first, bytes&lt;N&gt; N / 4), then '
         'the translated: descriptors, each followed by what it describes. A request\'s pid is descriptor 0x20 and '
         'the word the kernel writes the caller\'s process ID over; a response\'s handles of one kind in a row '
         'share a descriptor, 0x0 copied, 0x10 moved, with the count less one in bits 31:26. A response\'s first '
         'normal word is the result.</p>'
         '<h2>Services</h2>' + table +
         '<p>The services\' other commands are answered by their C (each service\'s own dispatch), before its '
         'schema\'s dispatcher, and are not here.</p>' + other_manuals({'id': '3ds-ipc'}),
         1, search=True)
    return len(ifaces), ncmds


# ---- the Android API: the Java side of ScarletNX's Android framework, as javadoc reads it ----

JAVA_TOKEN = re.compile(r'''
    (?P<sect>//[ \t]*-{3,}[^\n]*?-{3,}[ \t]*(?=\n)|/\*[ \t]*-{3,}[^\n]*?-{3,}[ \t]*\*/)
  | (?P<doc>/\*\*(?!/).*?\*/)
  | (?P<block>/\*.*?\*/)
  | (?P<line>//[^\n]*)
  | (?P<text>"""(?:.|\n)*?""")
  | (?P<str>"(?:\\.|[^"\\\n])*")
  | (?P<chr>'(?:\\.|[^'\\\n])+')
  | (?P<num>\.?\d(?:[\w.]|[eEpP][+-])*)
  | (?P<id>[A-Za-z_$][\w$]*)
  | (?P<ws>\s+)
  | (?P<op>>>>=|<<=|>>=|\.\.\.|->|::|\+\+|--|&&|\|\||[-+*/%&|^!=<>]=|.)
''', re.S | re.X)
JAVA_MODIFIERS = {'public', 'protected', 'private', 'static', 'final', 'abstract', 'native', 'synchronized',
                  'transient', 'volatile', 'strictfp', 'default', 'sealed', 'non-sealed'}
JAVA_KINDS = {'class', 'interface', 'enum', 'record'}


class JTok:
    __slots__ = ('kind', 'text', 'line')

    def __init__(self, kind, text, line):
        self.kind, self.text, self.line = kind, text, line


def java_tokens(src):
    """The file's tokens but whitespace and plain comments; a doc comment is a token ('doc')"""
    out, line = [], 1
    for m in JAVA_TOKEN.finditer(src):
        k, t = m.lastgroup, m.group(0)
        if k not in ('ws', 'block', 'line'):
            out.append(JTok(k, t, line))
        line += t.count('\n')
    return out


def javadoc_text(raw):
    """A doc comment's text: the stars and the margin gone, its lines joined"""
    body = raw[3:-2]
    lines = [re.sub(r'^\s*\*(?!/) ?', '', l) for l in body.split('\n')]
    return re.sub(r'[ \t]*\n[ \t]*', '\n', '\n'.join(lines)).strip()


class JMember:
    def __init__(self, kind, name, sig, mods, doc, line, **extra):
        self.kind, self.name, self.sig, self.mods, self.doc, self.line = kind, name, sig, mods, doc, line
        self.section = None
        self.__dict__.update(extra)


class JType:
    def __init__(self, kind, name, fqn, pkg, mods, doc, line, path, outer):
        self.kind, self.name, self.fqn, self.pkg, self.mods, self.doc, self.line = kind, name, fqn, pkg, mods, doc, line
        self.path, self.outer = path, outer
        self.extends, self.implements, self.tparams, self.members, self.nested = [], [], '', [], []
        self.imports = None


def java_join(toks):
    """Tokens as source text, spaced as one writes Java"""
    out = ''
    for t in toks:
        s = t.text
        if not out:
            out = s
        elif s in (',', ';', ')', ']', '.', '...', '::') or out[-1] in '(.[@' or out.endswith('::'):
            out += s
        elif s in ('(', '[') and (out[-1].isalnum() or out[-1] in '_$>]'):
            out += s
        elif s == '<' and (out[-1].isalnum() or out[-1] in '_$'):
            out += s
        elif s == '>' or out[-1] == '<':
            out += s
        elif s == '?' and out[-1] == '<':
            out += s
        else:
            out += ' ' + s
    return out


def java_parse(path, rel):
    """A Java file's package, imports and types (each with its nested ones): the declarations javadoc sees"""
    toks = java_tokens(open(path, encoding='utf-8').read())
    pkg, imports, i = '', [], 0
    types = []

    def skip_balanced(i, open_, close):
        depth = 0
        while i < len(toks):
            t = toks[i].text if toks[i].kind == 'op' else None
            if t == open_:
                depth += 1
            elif t == close:
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return i

    def skip_annotation(i):  # at '@': the annotation and its arguments
        i += 1
        if i < len(toks) and toks[i].text == 'interface':
            return i
        while i < len(toks) and toks[i].kind == 'id':
            i += 1
            if i < len(toks) and toks[i].text == '.':
                i += 1
            else:
                break
        if i < len(toks) and toks[i].text == '(':
            i = skip_balanced(i, '(', ')')
        return i

    def angle_end(i):  # at '<': past the matching '>' of type arguments
        depth = 0
        while i < len(toks):
            t = toks[i].text
            if t == '<':
                depth += 1
            elif t == '>':
                depth -= 1
            elif t == '>>':
                depth -= 2
            elif t == '>>>':
                depth -= 3
            elif t in (';', '{', '(', ')', '='):
                return i
            i += 1
            if depth <= 0:
                return i
        return i

    def type_end(i):  # past a type: a name, its type arguments, its array brackets
        while i < len(toks):
            if toks[i].kind != 'id':
                return i
            i += 1
            if i < len(toks) and toks[i].text == '<':
                i = angle_end(i)
            while i < len(toks) and toks[i].text == '@':
                i = skip_annotation(i)
            if i < len(toks) and toks[i].text == '.':
                i += 1
                continue
            break
        while i + 1 < len(toks) and toks[i].text == '[' and toks[i + 1].text == ']':
            i += 2
        if i < len(toks) and toks[i].text == '...':
            i += 1
        return i

    def split_top(seq, sep=','):
        parts, cur, depth = [], [], 0
        for t in seq:
            if t.text in ('(', '[', '{', '<'):
                depth += 1
            elif t.text in (')', ']', '}', '>'):
                depth -= 1
            elif t.text == '>>':
                depth -= 2
            elif t.text == '>>>':
                depth -= 3
            if t.text == sep and depth == 0:
                parts.append(cur)
                cur = []
            else:
                cur.append(t)
        if cur:
            parts.append(cur)
        return parts

    def params_of(seq):
        out = []
        for p in split_top(seq):
            p = [t for t in p if t.text != 'final']
            k = 0
            while k < len(p) and p[k].text == '@':
                j = k + 1
                while j < len(p) and (p[j].kind == 'id' or p[j].text == '.'):
                    j += 1
                if j < len(p) and p[j].text == '(':
                    d = 0
                    while j < len(p):
                        d += {'(': 1, ')': -1}.get(p[j].text, 0)
                        j += 1
                        if d == 0:
                            break
                k = j
            p = p[k:]
            if p:
                out.append((java_join(p[:-1]), p[-1].text))
        return out

    def body(i, owner):
        """A class body from just past its '{': its members and nested types; returns past its '}'"""
        enum_consts = owner.kind == 'enum'
        doc, section, first = None, None, len(owner.members)
        while i < len(toks):
            t = toks[i]
            for m in owner.members[first:]:  # the members read since: the group they are in
                m.section = section
            first = len(owner.members)
            if t.kind == 'sect':  # // ---- a group of members ----
                section = t.text.strip('/* \t-') or None
                i += 1
                continue
            if t.text == '}' and t.kind == 'op':
                return i + 1
            if t.kind == 'doc':
                doc = (javadoc_text(t.text), t.line)
                i += 1
                continue
            if enum_consts:  # the constants: names, their arguments, their bodies, up to ';' or '}'
                if t.text == ';':
                    enum_consts = False
                    i += 1
                    continue
                if t.text == ',':
                    i += 1
                    continue
                if t.text == '@':
                    i = skip_annotation(i)
                    continue
                if t.kind == 'id':
                    m = JMember('constant', t.text, t.text, {'public', 'static', 'final'}, doc and doc[0], t.line)
                    i += 1
                    if i < len(toks) and toks[i].text == '(':
                        j = skip_balanced(i, '(', ')')
                        m.sig += java_join(toks[i:j])
                        i = j
                    if i < len(toks) and toks[i].text == '{':
                        i = skip_balanced(i, '{', '}')
                    owner.members.append(m)
                    doc = None
                    continue
                enum_consts = False
            if t.text == ';':
                i += 1
                doc = None
                continue
            start = i
            mods, deprecated = set(), False
            while i < len(toks):
                if toks[i].text == '@' and (i + 1 >= len(toks) or toks[i + 1].text != 'interface'):
                    deprecated |= i + 1 < len(toks) and toks[i + 1].text == 'Deprecated'
                    i = skip_annotation(i)
                elif toks[i].kind == 'id' and toks[i].text in JAVA_MODIFIERS:
                    mods.add(toks[i].text)
                    i += 1
                else:
                    break
            if i < len(toks) and toks[i].text == '{':  # an initializer
                i = skip_balanced(i, '{', '}')
                doc = None
                continue
            kind = toks[i].text if i < len(toks) else ''
            if kind == '@' and i + 1 < len(toks) and toks[i + 1].text == 'interface':
                kind = '@interface'
                i += 1
            if kind in JAVA_KINDS or kind == '@interface':
                if owner.kind in ('interface', '@interface'):
                    mods |= {'public', 'static'}
                i = type_decl(i + 1, kind, mods, doc, owner.pkg, owner, owner.path, deprecated)
                doc = None
                continue
            # a member: type parameters, a type, a name; or a constructor's name
            tparams = ''
            if i < len(toks) and toks[i].text == '<':
                j = angle_end(i)
                tparams = java_join(toks[i:j])
                i = j
            if i < len(toks) and toks[i].kind == 'id' and toks[i].text == owner.name and i + 1 < len(toks) \
                    and toks[i + 1].text in ('(', '{'):
                name_at, type_toks = i, []
            else:
                j = type_end(i)
                type_toks = toks[i:j]
                name_at = j
            if name_at >= len(toks) or toks[name_at].kind != 'id' or not type_toks and toks[name_at].text != owner.name:
                # not a declaration this reads: skip to the statement's end
                while i < len(toks) and toks[i].text not in (';', '{', '}'):
                    i += 1
                if i < len(toks) and toks[i].text == '{':
                    i = skip_balanced(i, '{', '}')
                elif i < len(toks) and toks[i].text == ';':
                    i += 1
                doc = None
                continue
            name = toks[name_at].text
            line = toks[start].line
            if owner.kind in ('interface', '@interface'):
                mods.add('public')
            nxt = toks[name_at + 1].text if name_at + 1 < len(toks) else ''
            if nxt == '(' or (nxt == '{' and owner.kind == 'record' and not type_toks):
                if nxt == '(':
                    j = skip_balanced(name_at + 1, '(', ')')
                    params = params_of(toks[name_at + 2:j - 1])
                else:
                    j, params = name_at + 1, None  # a record's compact constructor
                k = j
                while k < len(toks) and toks[k].text not in ('{', ';'):
                    k += 1
                throws = ''
                tail = toks[j:k]
                if tail and tail[0].text == 'throws':
                    throws = java_join(tail[1:])
                default = java_join(tail[1:]) if tail and tail[0].text == 'default' else ''
                behaviour = None
                if k < len(toks) and toks[k].text == '{':
                    end = skip_balanced(k, '{', '}')
                    inner = toks[k + 1:end - 1]
                    if not inner:
                        behaviour = 'empty'
                    elif inner[0].text == 'throw' and len(inner) > 2 and inner[2].text == 'UnsupportedOperationException':
                        behaviour = 'unsupported'
                    k = end
                else:
                    if 'abstract' not in mods and 'native' not in mods and owner.kind in ('interface', '@interface'):
                        mods.add('abstract')
                    k += 1
                ret = java_join(type_toks)
                kindm = 'constructor' if not type_toks else 'method'
                owner.members.append(JMember(kindm, name, '', mods, doc and doc[0], line, ret=ret, params=params or [],
                                             throws=throws, tparams=tparams, behaviour=behaviour, default=default,
                                             deprecated=deprecated))
                i = k
                doc = None
                continue
            # fields: declarators to ';' (an initializer's braces, brackets and parentheses skipped)
            ftype = java_join(type_toks)
            k = name_at
            decls = []
            while k < len(toks):
                nm = toks[k].text
                k += 1
                dims = ''
                while k + 1 < len(toks) and toks[k].text == '[' and toks[k + 1].text == ']':
                    dims += '[]'
                    k += 2
                init = []
                if k < len(toks) and toks[k].text == '=':
                    k += 1
                    depth = 0
                    while k < len(toks):
                        x = toks[k].text if toks[k].kind == 'op' else None
                        if x in ('(', '[', '{'):
                            depth += 1
                        elif x in (')', ']', '}'):
                            depth -= 1
                        elif x in (',', ';') and depth == 0:
                            if x == ';' or (k + 1 < len(toks) and toks[k + 1].kind == 'id' and k + 2 < len(toks)
                                            and toks[k + 2].text in ('=', ',', ';', '[')):
                                break
                        init.append(toks[k])
                        k += 1
                decls.append((nm, dims, init))
                if k < len(toks) and toks[k].text == ',':
                    k += 1
                    continue
                break
            k += 1  # the ';'
            for nm, dims, init in decls:
                value = None
                if init and {'static', 'final'} <= mods and len(init) <= 6 and all(
                        x.kind in ('num', 'str', 'chr', 'id', 'op') for x in init) and not any(
                        x.text in ('new', '{', '(') for x in init):
                    value = re.sub(r'^([-~!]) ', r'\1', java_join(init))
                owner.members.append(JMember('field', nm, '', mods, doc and doc[0], line, type=ftype + dims,
                                             value=value, deprecated=deprecated))
            i = k
            doc = None
        return i

    def type_decl(i, kind, mods, doc, pkg, outer, rel, deprecated=False):
        name = toks[i].text
        line = toks[i].line
        fqn = (outer.fqn + '.' if outer else (pkg + '.' if pkg else '')) + name
        t = JType(kind, name, fqn, pkg, mods, doc and doc[0], line, rel, outer)
        t.deprecated = deprecated
        i += 1
        if i < len(toks) and toks[i].text == '<':
            j = angle_end(i)
            t.tparams = java_join(toks[i:j])
            i = j
        if kind == 'record' and i < len(toks) and toks[i].text == '(':
            j = skip_balanced(i, '(', ')')
            t.components = params_of(toks[i + 1:j - 1])
            i = j
        while i < len(toks) and toks[i].text != '{':
            w = toks[i].text
            if w in ('extends', 'implements', 'permits'):
                j = i + 1
                while j < len(toks) and toks[j].text not in ('{', 'implements', 'extends', 'permits'):
                    j += 1
                names = [java_join(p) for p in split_top(toks[i + 1:j])]
                if w == 'extends' and kind not in ('interface', '@interface'):
                    t.extends = names
                elif w != 'permits':
                    (t.implements if w == 'implements' else t.extends).extend(names)
                i = j
            else:
                i += 1
        i = body(i + 1, t)
        (outer.nested if outer else types).append(t)
        return i

    while i < len(toks):
        t = toks[i]
        if t.kind == 'sect':
            i += 1
            continue
        if t.text == 'package':
            j = i + 1
            while toks[j].text != ';':
                j += 1
            pkg = ''.join(x.text for x in toks[i + 1:j])
            i = j + 1
            continue
        if t.text == 'import':
            j = i + 1
            while toks[j].text != ';':
                j += 1
            imports.append(''.join(x.text for x in toks[i + 1:j]))
            i = j + 1
            continue
        doc = None
        if t.kind == 'doc':
            doc = (javadoc_text(t.text), t.line)
            i += 1
        mods, deprecated = set(), False
        while i < len(toks) and (toks[i].text in JAVA_MODIFIERS or
                                 toks[i].text == '@' and toks[i + 1].text != 'interface'):
            if toks[i].text == '@':
                deprecated |= toks[i + 1].text == 'Deprecated'
                i = skip_annotation(i)
            else:
                mods.add(toks[i].text)
                i += 1
        if i < len(toks) and toks[i].kind == 'doc':
            continue
        kind = toks[i].text if i < len(toks) else ''
        if kind == '@':
            kind = '@interface'
            i += 1
        if kind in JAVA_KINDS or kind == '@interface':
            i = type_decl(i + 1, kind, mods, doc, pkg, None, rel, deprecated)
        else:
            i += 1
    for t in types:
        t.imports = imports
    return pkg, imports, types
ANDROID_DIR = 'src/android/framework'
ANDROID_MANUAL = ('Android API', 'android', 'The framework is ScarletNX\'s (GPL-3.0-or-later); the parts that follow '
                                           'the Android Open Source Project\'s sources (Apache-2.0) say so in their '
                                           'files.')
ANDROID_REFERENCE = 'https://developer.android.com/reference/'
# the packages Android's reference documents (its own, and the libraries it ships)
ANDROID_DOCUMENTED = ('android.', 'org.json', 'org.xmlpull.v1', 'javax.microedition.khronos', 'dalvik.system')


def java_first_sentence(doc):
    text = re.sub(r'\s+', ' ', re.sub(r'\{@\w+\s+([^}]*)\}', r'\1', doc or '')).strip()
    m = re.match(r'(.+?[.:;!?])(\s|$)', text)
    return (m.group(1) if m else text)[:300]


def build_android(site, root, rows):
    base = os.path.join(root, ANDROID_DIR)
    types, by_fqn = [], {}
    for d, dirs, files in os.walk(base):
        dirs.sort()
        for f in sorted(files):
            if f.endswith('.java'):
                rel = os.path.relpath(os.path.join(d, f), root)
                try:
                    _, _, ts = java_parse(os.path.join(d, f), rel)
                except Exception as e:  # a file this doesn't read: its types are left out
                    site.failed(rel, e)
                    continue
                stack = list(ts)
                while stack:
                    t = stack.pop(0)
                    types.append(t)
                    stack = t.nested + stack
    # the API: public and protected types whose enclosing types are too, and their public and protected members
    def visible(t):
        while t:
            if not t.mods & {'public', 'protected'}:
                return False
            t = t.outer
        return True

    api = [t for t in types if visible(t)]
    by_fqn = {t.fqn: t for t in api}
    packages = {}
    for t in api:
        packages.setdefault(t.pkg, []).append(t)

    def page_of(t):
        return f'c/{t.fqn}.html'

    def resolve(name, ctx):
        """A type's name, as ctx's file writes it, to the API's type, or None"""
        name = name.strip()
        if name in by_fqn:
            return by_fqn[name]
        first, _, rest = name.partition('.')
        top = None
        c = ctx
        while c and not top:  # nested in ctx or in its outer types, or ctx's own
            if c.name == first:
                top = c
            top = top or next((n for n in c.nested if n.name == first), None)
            c = c.outer
        if not top:
            for imp in ctx.imports or []:
                if imp.endswith('.' + first) and imp in by_fqn:
                    top = by_fqn[imp]
                    break
        if not top and (f'{ctx.pkg}.{first}' if ctx.pkg else first) in by_fqn:
            top = by_fqn[f'{ctx.pkg}.{first}' if ctx.pkg else first]
        if not top:
            for imp in ctx.imports or []:
                if imp.endswith('.*') and f'{imp[:-2]}.{first}' in by_fqn:
                    top = by_fqn[f'{imp[:-2]}.{first}']
                    break
        if not top:
            return None
        for part in rest.split('.') if rest else []:
            top = next((n for n in top.nested if n.name == part and n.fqn in by_fqn), None)
            if not top:
                return None
        return top

    def type_html(text, ctx, up):
        """A type as the source writes it, each name of the API a link to its page"""
        out, last = [], 0
        for m in re.finditer(r'[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*', text):
            out.append(html.escape(text[last:m.start()]))
            t = resolve(m.group(0), ctx)
            out.append(f'<a href="{up}{page_of(t)}">{m.group(0)}</a>' if t else html.escape(m.group(0)))
            last = m.end()
        out.append(html.escape(text[last:]))
        return ''.join(out)

    def doc_html(doc, ctx, up):
        """A doc comment as HTML: its paragraphs, {@code} and {@link}; its @ tags as a table"""
        if not doc:
            return ''
        body, tags = [], []
        for part in re.split(r'\n(?=\s*@\w)', doc):
            m = re.match(r'\s*@(\w+)\s*(.*)', part, re.S)
            if m and body:
                tags.append((m.group(1), m.group(2)))
            elif m and not body and part.lstrip().startswith('@'):
                tags.append((m.group(1), m.group(2)))
            else:
                body.append(part)

        def inline(text):
            out, last = [], 0
            for m in re.finditer(r'\{@(\w+)\s*([^}]*)\}', text):
                out.append(html.escape(text[last:m.start()]))
                what, arg = m.group(1), m.group(2).strip()
                if what in ('link', 'linkplain'):
                    target, _, label = arg.partition(' ')
                    cls, _, member = target.partition('#')
                    t = resolve(cls, ctx) if cls else ctx
                    shown = html.escape(label or (target.replace('#', '.') if cls else member))
                    out.append(f'<a href="{up}{page_of(t)}">{shown}</a>' if t and t.fqn in by_fqn
                               else f'<code>{shown}</code>')
                else:
                    out.append(f'<code>{html.escape(arg)}</code>')
                last = m.end()
            out.append(html.escape(text[last:]))
            return ' '.join(''.join(out).split())

        paras = [p for p in re.split(r'\n\s*\n|<p>', '\n'.join(body)) if p.strip()]
        out = ''.join(f'<p>{inline(p)}</p>' for p in paras)
        if tags:
            out += '<table class="fields">' + ''.join(
                f'<tr><th>{html.escape(t)}</th><td>{inline(v)}</td></tr>' for t, v in tags) + '</table>'
        return out

    def anchor(m):
        if m.kind in ('method', 'constructor'):
            erased = [re.sub(r'<.*>', '', t).split('.')[-1].replace('[]', '_').replace('...', '_')
                      for t, _ in m.params]
            return re.sub(r'[^\w-]', '', '-'.join([m.name] + erased))
        return m.name

    def badges(m):
        out = []
        if 'native' in m.mods:
            out.append('native')
        if getattr(m, 'behaviour', None) == 'empty':
            out.append('empty body')
        if getattr(m, 'behaviour', None) == 'unsupported':
            out.append('throws UnsupportedOperationException')
        if getattr(m, 'deprecated', False):
            out.append('deprecated')
        return ''.join(f' <span class="tag">{b}</span>' for b in out)

    def decl(t, up):
        mods = [x for x in ('public', 'protected', 'abstract', 'static', 'final', 'sealed') if x in t.mods]
        kind = {'@interface': '@interface'}.get(t.kind, t.kind)
        text = ' '.join(mods + [kind]) + f' {html.escape(t.name)}{html.escape(t.tparams)}'
        if getattr(t, 'components', None):
            text += '(' + ', '.join(f'{type_html(a, t, up)} {html.escape(b)}' for a, b in t.components) + ')'
        if t.extends:
            text += ' extends ' + ', '.join(type_html(x, t.outer or t, up) for x in t.extends)
        if t.implements:
            text += ' implements ' + ', '.join(type_html(x, t.outer or t, up) for x in t.implements)
        return f'<pre class="sig">{text}</pre>'

    def member_html(m, t, up):
        mods = ' '.join(x for x in ('public', 'protected', 'abstract', 'static', 'final', 'native', 'synchronized',
                                    'default') if x in m.mods)
        if m.kind in ('method', 'constructor'):
            sig = (f'{mods} ' + (f'{html.escape(m.tparams)} ' if m.tparams else '')
                   + (f'{type_html(m.ret, t, up)} ' if m.kind == 'method' else '') + f'{html.escape(m.name)}('
                   + ', '.join(f'{type_html(a, t, up)} {html.escape(b)}' for a, b in m.params) + ')'
                   + (f' throws {type_html(m.throws, t, up)}' if m.throws else '')
                   + (f' default {html.escape(m.default)}' if m.default else ''))
        elif m.kind == 'constant':
            sig = html.escape(m.sig)
        else:
            sig = f'{mods} {type_html(m.type, t, up)} {html.escape(m.name)}' + (
                f' = {html.escape(m.value)}' if m.value else '')
        return (f'<dt id="{anchor(m)}"><code>{sig.strip()}</code>{badges(m)} <a class="src" '
                f'href="{source}/{t.path}#L{m.line}">source</a></dt>'
                + (f'<dd>{doc_html(m.doc, t, up)}</dd>' if m.doc else ''))

    subclasses = {}
    for t in api:
        for x in t.extends + t.implements:
            s_ = resolve(x, t.outer or t)
            if s_:
                subclasses.setdefault(s_.fqn, []).append(t)

    def kind_name(t):
        return {'class': 'Class', 'interface': 'Interface', 'enum': 'Enum', 'record': 'Record',
                '@interface': 'Annotation'}[t.kind]

    source = f'{GITHUB}/{site.commit[:12]}'  # a member's link: the commit short, as there are thousands
    n_members = 0
    for t in api:
        try:
            members = [m for m in t.members if m.mods & {'public', 'protected'} or m.kind == 'constant']
            n_members += len(members)
            up = '../'
            head = [f'<h1>{html.escape(t.name)}' + (' <span class="tag">deprecated</span>' if getattr(t, 'deprecated', False)
                                                     else '') + '</h1>',
                    f'<p class="groups">{kind_name(t)} of <a href="../p/{t.pkg}.html">{html.escape(t.pkg)}</a>'
                    + (f', in <a href="../{page_of(t.outer)}">{html.escape(t.outer.name)}</a>' if t.outer else '')
                    + f' &middot; <a class="src" href="{GITHUB}/{site.commit}/{t.path}#L{t.line}">{t.path.rsplit("/", 1)[1]}</a>'
                    + (f' &middot; <a href="{ANDROID_REFERENCE}{t.pkg.replace(".", "/")}/{t.fqn[len(t.pkg) + 1:]}">Android\'s '
                       f'reference</a>' if t.fqn.startswith(ANDROID_DOCUMENTED) and 'public' in t.mods else '') + '</p>',
                    decl(t, up)]
            chain, s_ = [], resolve(t.extends[0], t.outer or t) if t.extends and t.kind == 'class' else None
            while s_ and s_ not in chain and len(chain) < 12:
                chain.append(s_)
                s_ = resolve(s_.extends[0], s_.outer or s_) if s_.extends else None
            if chain:
                head.append('<p>' + ' &larr; '.join([html.escape(t.name)] + [f'<a href="../{page_of(c)}">{html.escape(c.name)}</a>'
                                                                            for c in chain]) + '</p>')
            head.append(doc_html(t.doc, t, up) or '')
            nested = [n for n in t.nested if n.fqn in by_fqn]
            if nested:
                head.append('<h2>Nested types</h2><ul class="cols">' + ''.join(
                    f'<li><a href="../{page_of(n)}">{html.escape(n.name)}</a> ({n.kind})</li>' for n in nested) + '</ul>')
            subs = sorted(subclasses.get(t.fqn, []), key=lambda x: x.name.lower())
            if subs:
                head.append(f'<h2>{"Implemented" if t.kind == "interface" else "Extended"} in the framework by</h2>'
                            '<ul class="cols">' + ''.join(f'<li><a href="../{page_of(x)}">{html.escape(x.name)}</a></li>'
                                                          for x in subs[:120]) + '</ul>'
                            + (f'<p>and {len(subs) - 120} more</p>' if len(subs) > 120 else ''))
            # the members: by the source's groups (// ---- name ----) when it has them, else by kind, in source order
            blocks, groups = [], []
            if any(m.section for m in members):
                for m in members:
                    g = m.section or 'Members'
                    if not groups or groups[-1][0] != g:
                        groups.append((g, []))
                    groups[-1][1].append(m)
            else:
                for title, kinds in (('Enum constants', ('constant',)), ('Fields', ('field',)),
                                     ('Constructors', ('constructor',)), ('Methods', ('method',))):
                    ms = [m for m in members if m.kind in kinds]
                    if ms:
                        groups.append((title, ms))
            for g, ms in groups:
                first = True
                for m in ms:
                    blocks.append((g if first else None, member_html(m, t, up), m))
                    first = False
            rows.append([t.name, f'android/{page_of(t)}', 'Java', f'{t.kind} {t.pkg}'])
            rel = f'android/{page_of(t)}'
            stem = t.fqn

            def render(chunk, k, n, head=head, stem=stem, t=t):
                nav = '' if n == 1 else '<p>Page ' + ' '.join(
                    (f'<a href="{stem}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                    for j in range(1, n + 1)) + '</p>'
                body, open_ = [], False
                for g, b, _ in chunk:
                    if g is not None or not open_:
                        if open_:
                            body.append('</dl>')
                        body.append(f'<h2>{html.escape(g[0].upper() + g[1:])}</h2>' if g else '')
                        body.append('<dl>')
                        open_ = True
                    body.append(b)
                if open_:
                    body.append('</dl>')
                return site.page(t.name, t.fqn, ('\n'.join(head) if k == 1 else f'<h1>{html.escape(t.name)}</h1>')
                                 + nav + '\n'.join(body) + nav, 2, manual=ANDROID_MANUAL)

            split = split_pages(blocks, render, rel) if blocks else [(rel, [])]
            searched = set()
            for k, (r, chunk) in enumerate(split, 1):
                site.write(r, render(chunk, k, len(split)))
                for _, _, m in chunk:  # the search names each member once, an overload by the first
                    if m.name not in searched:
                        searched.add(m.name)
                        rows.append([m.name, f'{r}#{anchor(m)}', 'Java', f'{m.kind} of {t.name}'])
        except Exception as e:  # its sources changed in a way this doesn't read: this page alone fails
            site.failed_page(f'android/{page_of(t)}', t.name, 2, ANDROID_MANUAL, e)

    # the packages
    def group_of(pkg):
        return ('ScarletNX\'s runtime' if pkg.startswith('snx.') else 'Android' if pkg.startswith('android.')
                else 'The libraries Android ships')

    for pkg, ts in packages.items():
        items = []
        for kind, title in (('interface', 'Interfaces'), ('class', 'Classes'), ('enum', 'Enums'),
                            ('record', 'Records'), ('@interface', 'Annotations')):
            for x in sorted((x for x in ts if x.kind == kind), key=lambda x: x.fqn.lower()):
                items.append((title, f'<tr><td><a href="../{page_of(x)}">{html.escape(x.fqn[len(pkg) + 1:])}</a></td>'
                                     f'<td>{html.escape(java_first_sentence(x.doc))}</td></tr>'))

        def render(chunk, k, n, pkg=pkg):
            nav = '' if n == 1 else '<p>Page ' + ' '.join(
                (f'<a href="{pkg}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                for j in range(1, n + 1)) + '</p>'
            body, last = [], None
            for title, row in chunk:
                if title != last:
                    if last:
                        body.append('</table>')
                    body.append(f'<h2>{title}</h2><table class="fields">')
                    last = title
                body.append(row)
            if last:
                body.append('</table>')
            return site.page(pkg, pkg, f'<h1>{html.escape(pkg)}</h1><p class="groups">{group_of(pkg)}</p>{nav}'
                             + ''.join(body) + nav, 1, manual=ANDROID_MANUAL)

        for k, (r, chunk) in enumerate(split_pages(items, render, f'android/p/{pkg}.html'), 1):
            site.write(r, render(chunk, k, len(split_pages(items, render, f'android/p/{pkg}.html'))))
        rows.append([pkg, f'android/p/{pkg}.html', 'Java', 'package'])

    lists = ''
    for g in ('Android', 'The libraries Android ships', 'ScarletNX\'s runtime'):
        pk = sorted(p for p in packages if group_of(p) == g)
        if pk:
            lists += f'<h2>{g}</h2><ul class="cols">' + ''.join(
                f'<li><a href="p/{p}.html">{html.escape(p)}</a> ({len(packages[p])})</li>' for p in pk) + '</ul>'
    natives = sum(1 for t in api for m in t.members if 'native' in m.mods and m.mods & {'public', 'protected'})
    site.write('android/index.html', site.page('Android API', 'Android API',
        '<h1>Android API</h1><p>The Java side of the Android framework ScarletNX gives an Android app '
        f'(<code>{ANDROID_DIR}</code>), as javadoc reads it: every public and protected type and member, its '
        'declaration, the doc comment over it, the groups its source puts the members in, and where it is. '
        f'{len(api)} types in {len(packages)} packages, {n_members} members, {natives} of them native (their '
        'bodies are ScarletNX\'s C). A member whose body is empty, or only throws UnsupportedOperationException, is '
        'marked so. Each type of Android\'s own packages links to Android\'s reference.</p>'
        '<div id="search" data-root="../" data-placeholder="Search: a package, type or member"></div>'
        + lists + other_manuals({'id': 'android'}), 1, search=['android'], manual=ANDROID_MANUAL))
    return len(api), len(packages), n_members

# ---- the nn API: the hooks (tools/hookgen's declarations) and the SVCs (hos.svc) ----

def strip_template_args(text):
    out, depth = '', 0
    for ch in text:
        if ch == '<':
            depth += 1
        elif ch == '>':
            depth -= 1
        elif depth == 0:
            out += ch
    return out


class Demangler:
    """The Itanium C++ ABI's mangled names, as far as the hooks' symbols use them: nested and unscoped names,
    constructors and destructors, operators, template arguments, substitutions (S_, St...), template parameters,
    the builtin types, pointers, references, cv-qualifiers, function and array types, local names. A name outside
    that raises ValueError. The result is spelled as c++filt spells it"""

    BUILTIN = {'v': 'void', 'w': 'wchar_t', 'b': 'bool', 'c': 'char', 'a': 'signed char', 'h': 'unsigned char',
               's': 'short', 't': 'unsigned short', 'i': 'int', 'j': 'unsigned int', 'l': 'long',
               'm': 'unsigned long', 'x': 'long long', 'y': 'unsigned long long', 'n': '__int128',
               'o': 'unsigned __int128', 'f': 'float', 'd': 'double', 'e': 'long double', 'g': '__float128',
               'z': '...'}
    BUILTIN_D = {'n': 'std::nullptr_t', 's': 'char16_t', 'i': 'char32_t', 'u': 'char8_t', 'h': 'half', 'a': 'auto',
                 'c': 'decltype(auto)'}
    OPERATORS = {'nw': 'new', 'na': 'new[]', 'dl': 'delete', 'da': 'delete[]', 'ps': '+', 'ng': '-', 'ad': '&',
                 'de': '*', 'co': '~', 'pl': '+', 'mi': '-', 'ml': '*', 'dv': '/', 'rm': '%', 'an': '&', 'or': '|',
                 'eo': '^', 'aS': '=', 'pL': '+=', 'mI': '-=', 'mL': '*=', 'dV': '/=', 'rM': '%=', 'aN': '&=',
                 'oR': '|=', 'eO': '^=', 'ls': '<<', 'rs': '>>', 'lS': '<<=', 'rS': '>>=', 'eq': '==', 'ne': '!=',
                 'lt': '<', 'gt': '>', 'le': '<=', 'ge': '>=', 'ss': '<=>', 'nt': '!', 'aa': '&&', 'oo': '||',
                 'pp': '++', 'mm': '--', 'cm': ',', 'pm': '->*', 'pt': '->', 'cl': '()', 'ix': '[]'}
    STD = {'t': 'std', 'a': 'std::allocator', 'b': 'std::basic_string',
           's': 'std::string', 'i': 'std::istream', 'o': 'std::ostream', 'd': 'std::iostream'}

    def __init__(self, s):
        self.s, self.i, self.subs, self.tparams, self.kind = s, 0, [], [], 'name'

    def peek(self, n=1):
        return self.s[self.i:self.i + n]

    def take(self, what):
        if not self.s.startswith(what, self.i):
            raise ValueError(f'{what} expected at {self.i}')
        self.i += len(what)

    def number(self):
        j = self.i
        while j < len(self.s) and self.s[j].isdigit():
            j += 1
        if j == self.i:
            raise ValueError(f'a number expected at {self.i}')
        n, self.i = int(self.s[self.i:j]), j
        return n

    def seq_id(self):  # S_ is 0, S0_ 1, ..., base 36
        if self.peek() == '_':
            self.i += 1
            return 0
        j = self.i
        while self.s[j] != '_':
            j += 1
        n = int(self.s[self.i:j], 36) + 1
        self.i = j + 1
        return n

    # ---- the types, as trees: ('name', text), ('ptr' | 'ref' | 'rref' | 'const' | 'volatile', t),
    # ('func', ret, params, quals), ('array', n, t) ----
    def show(self, t, d=''):
        k = t[0]
        if k == 'name':
            return t[1] + d
        if k in ('ptr', 'ref', 'rref'):
            mark = {'ptr': '*', 'ref': '&', 'rref': '&&'}[k]
            if t[1][0] in ('func', 'array'):
                return self.show(t[1], '(' + mark + d + ')')
            return self.show(t[1], mark + d)
        if k in ('const', 'volatile'):
            if t[1][0] == 'func':
                return self.show(t[1], d)
            return self.show(t[1], ' ' + k + d)
        if k == 'func':
            params = ', '.join(self.show(p) for p in t[2] if p != ('name', 'void') or len(t[2]) > 1)
            return self.show(t[1]) + ' ' + d + '(' + params + ')' + t[3]
        if k == 'array':
            return self.show(t[2], (' (' + d + ')' if d else ' ') + f'[{t[1]}]')
        raise ValueError(k)

    def type(self):
        c = self.peek()
        if not c:
            raise ValueError('the name ends in a type')
        if c == '*':  # a hook pattern's run of any characters, read as one type, as the patterns use it
            self.i += 1
            t = ('name', '*')
            self.subs.append(t)
            return t
        if c in self.BUILTIN:
            self.i += 1
            return ('name', self.BUILTIN[c])
        if c == 'D' and self.peek(2)[1:] in self.BUILTIN_D:
            self.i += 2
            return ('name', self.BUILTIN_D[self.s[self.i - 1]])
        if c in 'PROKVr':
            self.i += 1
            if c == 'r':
                return self.type()
            inner = self.type()
            t = ({'P': 'ptr', 'R': 'ref', 'O': 'rref', 'K': 'const', 'V': 'volatile'}[c], inner)
            self.subs.append(t)
            return t
        if c == 'F':
            self.i += 1
            if self.peek() == 'Y':
                self.i += 1
            ret = self.type()
            params = []
            while self.peek() not in ('E', 'R', 'O') or self.peek(2) in ('RK', 'RV') and False:
                if self.peek() in ('R', 'O') and self.peek(2)[1:] == 'E':
                    break
                params.append(self.type())
            quals = ''
            if self.peek() in ('R', 'O'):
                quals = ' &' if self.peek() == 'R' else ' &&'
                self.i += 1
            self.take('E')
            t = ('func', ret, params, quals)
            self.subs.append(t)
            return t
        if c == 'A':
            self.i += 1
            n = self.number() if self.peek().isdigit() else ''
            self.take('_')
            t = ('array', n, self.type())
            self.subs.append(t)
            return t
        if c == 'S':
            if self.peek(2)[1:] in self.STD and self.peek(2) != 'St':
                name = self.name_prefix_sub()
                if self.peek() == 'I':
                    name = name + self.template_args()
                    t = ('name', name)
                    self.subs.append(t)
                    return t
                return ('name', name)
            if self.peek(2) == 'St':
                t = ('name', self.unscoped())
                if self.peek() == 'I':
                    self.subs.append(t)
                    t = ('name', t[1] + self.template_args())
                self.subs.append(t)
                return t
            self.i += 1
            n = self.seq_id()
            if n >= len(self.subs) and '*' in self.s:  # past what a pattern's * stands for: unknowable here
                return ('name', '?')
            t = self.subs[n]
            if self.peek() == 'I':  # a substituted template's arguments
                t = ('name', self.show(t) + self.template_args())
                self.subs.append(t)
            return t
        if c == 'T':
            self.i += 1
            n = self.seq_id()
            t = self.tparams[n] if n < len(self.tparams) else ('name', f'T{n}')
            self.subs.append(t)
            if self.peek() == 'I':
                t = ('name', self.show(t) + self.template_args())
                self.subs.append(t)
            return t
        if c == 'N' or c.isdigit() or c == 'Z':
            name, _ = self.name(as_type=True)
            t = ('name', name)
            return t
        if c == 'M':
            self.i += 1
            cls = self.type()
            member = self.type()
            t = ('name', self.show(member, ' ' + self.show(cls) + '::*'))
            self.subs.append(t)
            return t
        raise ValueError(f'type {c!r} at {self.i}')

    def name_prefix_sub(self):
        """St, Sa, Sb, Ss... as a prefix"""
        self.i += 1
        c = self.s[self.i]
        self.i += 1
        return self.STD[c]

    def source_name(self):
        n = self.number()
        name = self.s[self.i:self.i + n]
        self.i += n
        return '(anonymous namespace)' if name.startswith('_GLOBAL__N') else name

    def unqualified(self, prefix):
        """A name's last part: a source name, a constructor or destructor (of prefix's last part), an operator"""
        c = self.peek()
        self.kind = 'name'
        if c.isdigit():
            name = self.source_name()
        elif c == 'C' and self.peek(2)[1:] and self.peek(2)[1:] in '1235I':
            self.i += 2
            if self.s[self.i - 1] == 'I':
                self.i += 1
                self.type()
            name = strip_template_args(prefix).split('::')[-1]
            self.kind = 'ctor'
        elif c == 'D' and self.peek(2)[1:] and self.peek(2)[1:] in '0124':
            self.i += 2
            name = '~' + strip_template_args(prefix).split('::')[-1]
            self.kind = 'ctor'
        elif c == 'L':  # an internal name
            self.i += 1
            name = self.source_name()
        elif c.islower() or c == 'c':
            code = self.peek(2)
            if code == 'cv':
                self.i += 2
                name = 'operator ' + self.show(self.type())
                self.kind = 'ctor'  # a conversion: no return type either
            elif code in self.OPERATORS:
                self.i += 2
                op = self.OPERATORS[code]
                name = 'operator' + (' ' + op if op[0].isalpha() else op)
            elif code == 'li':
                self.i += 2
                name = 'operator"" ' + self.source_name()
            else:
                raise ValueError(f'operator {code!r}')
        else:
            raise ValueError(f'name {c!r} at {self.i}')
        while self.peek() == 'B':  # an ABI tag
            self.i += 1
            name += f'[abi:{self.source_name()}]'
        return name

    def template_args(self):
        self.take('I')
        args = []
        while self.peek() != 'E':
            if self.peek() == 'L':
                self.i += 1
                if self.peek() == '_' and self.peek(2) == '_Z':
                    self.i += 2
                    args.append(('name', self.encoding()))
                else:
                    t = self.type()
                    j = self.s.index('E', self.i)
                    v = self.s[self.i:j].replace('n', '-', 1) if self.s[self.i:j].startswith('n') else self.s[self.i:j]
                    self.i = j
                    args.append(('name', self.literal(t, v)))
                self.take('E')
            elif self.peek() == 'J':
                self.i += 1
                pack = []
                while self.peek() != 'E':
                    pack.append(self.type())
                self.i += 1
                args.append(('name', ', '.join(self.show(p) for p in pack)))
            elif self.peek() == 'X':
                self.i += 1
                args.append(('name', self.expression()))
                self.take('E')
            else:
                args.append(self.type())
        self.i += 1
        self.tparams = args
        return '<' + ', '.join(self.show(a) for a in args) + '>'

    SUFFIX = {'int': '', 'unsigned int': 'u', 'long': 'l', 'unsigned long': 'ul', 'long long': 'll',
              'unsigned long long': 'ull'}

    def literal(self, t, v):
        if t == ('name', 'bool'):
            return {'0': 'false', '1': 'true'}.get(v, v)
        if t[0] == 'name' and t[1] in self.SUFFIX:
            return v + self.SUFFIX[t[1]]
        return f'({self.show(t)}){v}'

    def expression(self):
        """The expressions of template arguments the hooks' symbols have: names (sr), literals, template
        parameters, binary operators"""
        code = self.peek(2)
        if code == 'sr':
            self.i += 2
            if self.peek().isdigit():  # qualifiers, E, then the name
                levels = []
                while self.peek() != 'E':
                    level = self.source_name()
                    if self.peek() == 'I':
                        level += self.template_args()
                    levels.append(level)
                self.i += 1
                scope = '::'.join(levels)
            else:
                scope = self.show(self.type())
            name = self.source_name()
            if self.peek() == 'I':
                name += self.template_args()
            return f'{scope}::{name}'
        if self.peek() == 'L':
            self.i += 1
            t = self.type()
            j = self.s.index('E', self.i)
            v = self.s[self.i:j]
            v = '-' + v[1:] if v.startswith('n') else v
            self.i = j + 1
            return self.literal(t, v)
        if self.peek() == 'T':
            return self.show(self.type())
        if code in self.OPERATORS and code not in ('nw', 'na', 'dl', 'da', 'cl', 'ix'):
            self.i += 2
            if code in ('ps', 'ng', 'ad', 'de', 'co', 'nt'):
                return self.OPERATORS[code] + self.expression()
            left = self.expression()
            right = self.expression()
            return f'{left} {self.OPERATORS[code]} {right}'
        raise ValueError(f'expression {code!r}')

    def unscoped(self):
        if self.peek(2) == 'St':
            self.i += 2
            return 'std::' + self.unqualified('std')
        return self.unqualified('')

    def name(self, as_type=False):
        """A name and whether it ends in template arguments (whose function encodes its return type); a name as a
        type is a substitution too"""
        c = self.peek()
        if c == 'N':
            self.i += 1
            quals = ''
            while self.peek() in ('r', 'V', 'K'):
                quals = {'r': ' restrict', 'V': ' volatile', 'K': ' const'}[self.s[self.i]] + quals
                self.i += 1
            ref = ''
            if self.peek() in ('R', 'O'):
                ref = ' &' if self.peek() == 'R' else ' &&'
                self.i += 1
            prefix, templated, parts, last_kind = '', False, 0, 'name'
            while self.peek() != 'E':
                c = self.peek()
                if c == 'S' and not (self.peek(2)[1:] in self.STD and self.peek(2) != 'St'):
                    if self.peek(2) == 'St':
                        self.i += 2
                        prefix = 'std'
                        continue
                    self.i += 1
                    prefix = self.show(self.subs[self.seq_id()])
                    templated = False
                    continue  # a substitution is in the table already
                elif c == 'S':
                    prefix = self.name_prefix_sub()
                    templated = False
                    continue
                elif c == 'T':
                    self.i += 1
                    prefix = self.show(self.tparams[self.seq_id()])
                    self.subs.append(('name', prefix))
                    templated = False
                    continue
                elif c == 'I':
                    prefix += self.template_args()
                    templated = True
                else:
                    part = self.unqualified(prefix)
                    last_kind = self.kind
                    prefix = prefix + '::' + part if prefix else part
                    templated = False
                parts += 1
                if self.peek() != 'E' or as_type:
                    self.subs.append(('name', prefix))
            self.i += 1
            self.quals = quals + ref
            self.kind = last_kind  # the last part's, not a template argument's
            return prefix, templated
        if c == 'Z':
            self.i += 1
            outer = self.encoding()
            self.take('E')
            if self.peek() == 's':
                self.i += 1
                name = outer + '::string literal'
            else:
                inner, templated = self.name(as_type)
                name = outer + '::' + inner
            if self.peek() == '_':
                self.i += 1
                self.number() if self.peek().isdigit() else None
            return name, False
        name = self.unscoped()
        self.quals = ''
        last_kind = self.kind
        if self.peek() == 'I':
            self.subs.append(('name', name))
            name += self.template_args()
            self.kind = last_kind
            if as_type:
                self.subs.append(('name', name))
            return name, True
        if self.peek() == 'I':
            self.subs.append(('name', name))
            name += self.template_args()
            if as_type:
                self.subs.append(('name', name))
            return name, True
        if as_type:
            self.subs.append(('name', name))
        return name, False

    def encoding(self):
        name, templated = self.name()
        quals = self.quals
        if self.i >= len(self.s) or self.peek() in ('E', '.'):
            return name
        if templated and self.kind != 'ctor':  # a template function's name: its return type first
            ret = self.type()
        else:
            ret = None
        params = []
        while self.i < len(self.s) and self.peek() not in ('E', '.'):
            params.append(self.type())
        shown = ', '.join(self.show(p) for p in params if not (p == ('name', 'void') and len(params) == 1))
        return (self.show(ret) + ' ' if ret else '') + f'{name}({shown}){quals}'


def demangle(symbol):
    """A symbol as c++filt spells it, or None for one not mangled or not read here"""
    if not symbol.startswith('_Z') or symbol.count('*') > 4:
        return None
    try:
        d = Demangler(symbol)
        d.i = 2
        text = d.encoding()
        if d.i < len(symbol):
            clone = symbol[d.i:]
            if not clone.startswith('.'):
                return None
            text += ' [clone ' + clone + ']'
        return text
    except (ValueError, IndexError, KeyError):
        return None


NN_HOOKS = ['src/nx/hle/hook/hooks.hook']  # and every src/nx/nn/*.hook
NN_DIR = 'src/nx/nn'
NN_SVC = 'src/nx/hle/svc/hos.svc'
NN_HANDLER_DIRS = ['src/nx/hle/hook', 'src/nx/nn', 'src/nx/hle/svc']
NN_MANUAL = ('nn API', 'nn', 'The hooks\' and the SVCs\' declarations and their handlers are ScarletNX\'s '
                             '(GPL-3.0-or-later); the SVCs\' declarations are Eden\'s, as hos.svc says.')


def parse_hookspec(path):
    """A file of tools/hookgen's language (hle/hook/hooks.hook's): its families, routes, structs and hooks, in order,
    each with the comment over it (a # comment may be over a run of declarations) and its ## doc comment"""
    items, family, block, block_id, doc, pending = [], None, None, 0, None, []
    lines = open(path, encoding='utf-8').read().split('\n')
    i = 0
    while i < len(lines):
        line, n = lines[i], i + 1
        s = line.strip()
        i += 1
        if s.startswith('##'):
            doc = (doc or []) + [s[2:].strip()]
            continue
        if s.startswith('#'):
            if block is None or block[1]:  # a comment after declarations starts anew
                block_id += 1
                block = [[], False, block_id]
            if not re.match(r'#\s*(SPDX-|Copyright )', s):  # the file's license, not a comment of its declarations
                block[0].append(s[1:].strip())
            continue
        if not s:
            block, doc = None, None
            continue
        if block is not None:
            block[1] = True
        comment = ' '.join(x for x in block[0] if x) if block else None
        cid = block[2] if block else None
        if s.startswith('struct') or s.startswith('@version') and ' struct ' in s and not ' hook ' in s:
            text = s
            while '}' not in text and i < len(lines):  # a struct over lines: a field a line
                text += '\n' + lines[i].strip()
                i += 1
            if not re.search(r'\}\s*size\s+\w+', text) and i < len(lines):
                text += ' ' + lines[i].strip()
                i += 1
            m = re.match(r'((?:@version\([^)]*\)\s*)*)struct\s+([\w:]+)\s*((?:@version\([^)]*\)\s*)*)\{(.*)\}\s*size\s+(\w+)',
                         text, re.S)
            if m:
                fields = []
                for f in re.split(r'[;\n]', m.group(4)):
                    fm = re.match(r'\s*(.+?)\s+(\w+)\s*@\s*(\w+)\s*$', f)
                    if fm:
                        fields.append((fm.group(1), fm.group(2), fm.group(3)))
                versions = pending + re.findall(r'@version\(([^)]*)\)', m.group(1) + m.group(3))
                items.append({'kind': 'struct', 'name': m.group(2), 'fields': fields, 'size': m.group(5),
                              'versions': versions, 'line': n, 'family': family, 'comment': comment, 'cid': cid})
            pending, doc = [], None
            continue
        m = re.fullmatch(r'@version\(([^)]*)\)', s)
        if m:  # a @version line alone: the next declaration's
            pending.append(m.group(1))
            continue
        w = s.split()
        if w[0] == 'family':
            family = w[1]
            items.append({'kind': 'family', 'name': w[1], 'line': n, 'comment': comment, 'cid': cid})
            block, doc = None, None
            continue
        if w[0] == 'route':
            items.append({'kind': 'route', 'symbol': w[1], 'line': n, 'comment': comment, 'cid': cid,
                          'family': family})
            continue
        if w[0] == 'include':
            continue
        address = re.match(r'\[([0-9A-Fa-f]+):(0x[0-9A-Fa-f]+|\d+)\]\s*', s)  # a function of one build of a game
        if address:
            s = s[address.end():]
        m = re.match(r'((?:(?:@version\([^)]*\)|a32)\s+)*)hook\s+(\S+?)\((.*?)\)\s*(?:->\s*(.+?))?\s*'
                     r'((?:=|uses|pure|a32|check|@version).*)?$', s)
        if not m:
            raise GenError(f'{path}:{n}: a line this does not read: {s[:80]}')
        args = []
        depth, cur = 0, ''
        for ch in m.group(3) + ',':
            depth += {'[': 1, ']': -1}.get(ch, 0)
            if ch == ',' and depth == 0:
                if cur.strip():
                    am = re.match(r'(.+?)\s*\b(\w+)(?:\s+(in|out|inout)\[([^\]]*)\])?$', cur.strip())
                    args.append((am.group(1).strip(), am.group(2), am.group(3), am.group(4)) if am else
                                (cur.strip(), '', None, None))
                cur = ''
            else:
                cur += ch
        rest = m.group(5) or ''
        handler = re.search(r'=\s*(\w+)', rest)
        uses = re.search(r'\buses\s+([\w:]+(?:\s*,\s*[\w:]+)*)', rest)
        symbol = m.group(2)
        default = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', symbol, count=1)
        check = re.search(r'\bcheck\s+(\w+)', rest)
        if address:
            default = symbol
        items.append({'kind': 'hook', 'symbol': symbol, 'args': args, 'ret': (m.group(4) or 'void').strip(),
                      'handler': handler.group(1) if handler else default,
                      'check': check.group(1) if check else None,
                      'address': (address.group(1), address.group(2)) if address else None,
                      'uses': [u.strip() for u in uses.group(1).split(',')] if uses else [],
                      'pure': bool(re.search(r'\bpure\b', rest)),
                      'a32': bool(re.search(r'\ba32\b', m.group(1) + ' ' + rest)),
                      'versions': pending + re.findall(r'@version\(([^)]*)\)', m.group(1) + ' ' + rest),
                      'line': n, 'family': family, 'comment': comment, 'cid': cid,
                      'doc': parse_doc(doc) if doc else None})
        pending, doc = [], None
    return items


def parse_svcs(path):
    """hos.svc: the types (name, 32-bit size, 64-bit size, the handler's C type) and the SVCs (number, flags, return
    type, name, arguments), each with its registers in each ABI, as tools/svcgen lays them out (Eden's register
    allocator: AAPCS64's eight 8-byte registers, all parameters; AAPCS32's eight 4-byte ones, four parameters)"""
    types, svcs = {}, []
    for n, line in enumerate(open(path, encoding='utf-8'), 1):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('type '):
            name, s32, s64, ctype = s.split()[1:5]
            types[name] = {'size': (int(s32), int(s64)), 'ctype': ctype}
            continue
        m = re.match(r'(0x[0-9A-Fa-f]+|\d+)\s+((?:(?:stub|quiet|nowarn)\s+)*)(\w+)\s+(\w+)\((.*)\)\s*;$', s)
        if not m:
            raise GenError(f'{path}:{n}: a line this does not read: {s[:80]}')
        args = []
        for a in [x.strip() for x in m.group(5).split(',') if x.strip()]:
            am = re.match(r'(\w+)\s*(\*?)\s*(\w+)$', a)
            star, name = am.group(2) == '*', am.group(3)
            output = name == 'out' or 'out_' in name
            args.append({'type': am.group(1), 'name': name, 'star': star, 'output': output and star,
                         'regs': [None, None]})
        svc = {'number': int(m.group(1), 0), 'flags': m.group(2).split(), 'ret': m.group(3), 'name': m.group(4),
               'args': args, 'line': n, 'ret_regs': [[], []]}
        for abi in (0, 1):  # 0: AAPCS32, 1: AAPCS64
            bytes_, params = (4, 4) if abi == 0 else (8, 8)

            def allocator():
                return {'used': [False] * 8}

            def single(al, ngrn):
                if ngrn < params:
                    if al['used'][ngrn]:
                        raise GenError(f'{path}:{n}: register {ngrn} allocated twice')
                    al['used'][ngrn] = True
                    return ngrn, 1
                for r in range(8):
                    if not al['used'][r]:
                        al['used'][r] = True
                        return r, 0
                raise GenError(f'{path}:{n}: no registers left')

            def add(al, ngrn, size, align):
                if size <= bytes_:
                    r, inc = single(al, ngrn)
                    return [r], inc
                inc, regs, left = (ngrn % 2 if align else 0), [], size
                while left > 0:
                    r, step = single(al, ngrn + inc)
                    regs.append(r)
                    inc += step
                    left -= bytes_
                return regs, inc

            ins, outs, ngrn = allocator(), allocator(), 0
            for a in args:
                if a['output']:
                    ngrn += 1
                    continue
                a['regs'][abi], inc = add(ins, ngrn, types[a['type']]['size'][abi], 1)
                ngrn += inc
            ngrn = 0
            if types[svc['ret']]['size'][abi]:
                svc['ret_regs'][abi], inc = add(outs, ngrn, types[svc['ret']]['size'][abi], 0)
                ngrn += inc
            for a in args:
                if a['output']:
                    a['regs'][abi], inc = add(outs, ngrn, types[a['type']]['size'][abi], 0)
                    ngrn += inc
        svcs.append(svc)
    return types, svcs


def build_nn(site, root, rows):
    files = [f for f in NN_HOOKS if os.path.exists(os.path.join(root, f))]
    nn_dir = os.path.join(root, NN_DIR)
    if os.path.isdir(nn_dir):
        files += sorted(f'{NN_DIR}/{f}' for f in os.listdir(nn_dir) if f.endswith('.hook'))
    handlers = {}
    for d in NN_HANDLER_DIRS:
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        for fname in sorted(os.listdir(full)):
            if not fname.endswith('.c'):
                continue
            lines = open(os.path.join(full, fname), encoding='utf-8', errors='replace').read().split('\n')
            macros = {}  # #define M(name, ...) ... prefix##name##suffix(CPU* ...: the handlers M(x) defines
            for k, line in enumerate(lines):
                dm = re.match(r'#define\s+(\w+)\((\w+)[^)]*\)', line)
                if dm:
                    text, j = line, k
                    while text.rstrip().endswith('\\') and j + 1 < len(lines):
                        j += 1
                        text += lines[j]
                    hm = re.search(r'\b(\w*)##\s*' + dm.group(2) + r'\s*(?:##\s*(\w+))?\s*\((?:CPU|SnxArmCPU)\b', text)
                    if hm:
                        macros[dm.group(1)] = (hm.group(1), hm.group(2) or '')
            for k, line in enumerate(lines, 1):
                # a function's definition at the start of a line: a handler, an SVC's, a pattern's check
                m = re.match(r'(?:static\s+|inline\s+)*[A-Za-z_][\w]*[\s\*]+(?:[\w\s\*]*?[\s\*])?(\w+)\(', line)
                if m and not line.rstrip().endswith(';') and m.group(1) not in ('if', 'while', 'for', 'switch', 'return'):
                    handlers.setdefault(m.group(1), (f'{d}/{fname}', k))
                mm = re.match(r'\s*(\w+)\((\w+)', line)
                if mm and mm.group(1) in macros and not line.startswith('#'):
                    pre, post = macros[mm.group(1)]
                    handlers.setdefault(pre + mm.group(2) + post, (f'{d}/{fname}', k))
    src = f'{GITHUB}/{site.commit[:12]}'

    def handler_html(name):
        h = handlers.get(name)
        return (f'<a href="{src}/{h[0]}#L{h[1]}"><code>{name}</code></a> ({h[0].rsplit("/", 1)[1]})' if h
                else f'<code>{name}</code>')

    families, structs, routes = {}, {}, []
    for f in files:
        try:
            items = parse_hookspec(os.path.join(root, f))
        except Exception as e:  # a file this doesn't read: its families are left out
            site.failed(f, e)
            continue
        for it in items:
            it['file'] = f
            if it['kind'] == 'family':
                families.setdefault(it['name'], {'name': it['name'], 'file': f, 'line': it['line'], 'items': [],
                                                 'comment': it['comment']})
            elif it['kind'] == 'route':
                routes.append(it)
            elif it['family']:
                families[it['family']]['items'].append(it)
            if it['kind'] == 'struct':
                structs.setdefault(it['name'], []).append(it)

    def version_text(v):
        key = re.match(r'\s*(sdk|nvn|movie)\b', v)
        name = {'sdk': 'SDK', 'nvn': 'NVN', 'movie': 'movie'}[key.group(1)] if key else 'SDK'
        return name + ' ' + (v[key.end():] if key else v).strip()

    def tags(it):
        out = [version_text(v) for v in it.get('versions', [])]
        if it.get('a32'):
            out.append('32-bit')
        if it.get('pure'):
            out.append('pure')
        if '*' in it.get('symbol', ''):
            out.append('pattern')
        return ''.join(f' <span class="tag">{html.escape(t)}</span>' for t in out)

    def display(symbol):
        d = demangle(symbol)
        return d, (strip_template_args(d.split('(')[0]) if d else symbol)

    # the families' pages: their hooks by the comments over them, their structs
    struct_at, anchors, seen = {}, {}, {}
    for fam in families.values():
        for it in fam['items']:
            base = it['symbol'] if it['kind'] == 'hook' else 'struct-' + it['name'].replace('::', '-')
            k = seen.get(base, 0)  # one declared for several versions: an anchor each
            seen[base] = k + 1
            it['anchor'] = base if not k else f'{base}-{k + 1}'

    def item_html(it, fam_rel):
        if it['kind'] == 'struct':
            rows_ = ''.join(f'<tr><td>{html.escape(f[1])}</td><td>{html.escape(f[0])}</td><td>{html.escape(f[2])}</td></tr>'
                            for f in it['fields'])
            return (f'<dt id="{it["anchor"]}"><code>struct {html.escape(it["name"])}</code>{tags(it)} '
                    f'<a class="src" href="{src}/{it["file"]}#L{it["line"]}">source</a></dt><dd><table class="fields">'
                    f'<tr><th>Field</th><th>Type</th><th>Offset</th></tr>{rows_}</table><p>Size {html.escape(it["size"])}'
                    f'.</p></dd>')
        d, short = display(it['symbol'])
        args = ', '.join(html.escape(f'{t} {n}' + (f' {b}[{l}]' if b else '')) for t, n, b, l in it['args'])
        lines = []
        if d:
            lines.append(f'<code>{html.escape(it["symbol"])}</code>' + (
                ': a pattern, whose * matches any run of characters, so one handler takes every instance of the '
                'template that compiles to the same code' if '*' in it['symbol'] else ''))
        lines.append(f'As C: <code>{html.escape(it["ret"])} ({args})</code>')
        lines.append(f'Handler: {handler_html(it["handler"])}')
        if it['check']:
            lines.append(f'Check: {handler_html(it["check"])}, which says whether a function the pattern matches '
                         'is one the handler takes')
        if it['address']:
            lines.append(f'Address: the module of build ID <code>{html.escape(it["address"][0])}</code>, at offset '
                         f'<code>{html.escape(it["address"][1])}</code> (a function of one build of a game, which no '
                         'symbol names)')
        if it['uses']:
            lines.append('Uses: ' + ', '.join(
                f'<a href="{struct_at[u]}">{html.escape(u)}</a>' if u in struct_at else html.escape(u)
                for u in it['uses']))
        if it['pure']:
            lines.append('Pure: the hooks_verify setting checks it against the game\'s own code on every call')
        doc = ''
        if it['doc']:
            dd = it['doc']
            doc = (f'<p>{html.escape(dd["brief"])}</p>' if dd['brief'] else '') + ''.join(
                f'<p><code>{html.escape(n)}</code>: {html.escape(t)}</p>' for n, t in dd['params']) + (
                f'<p>Returns: {html.escape(dd["return"])}</p>' if dd['return'] else '')
        return (f'<dt id="{it["anchor"]}"><code>{html.escape(d or it["symbol"])}</code>{tags(it)} '
                f'<a class="src" href="{src}/{it["file"]}#L{it["line"]}">source</a></dt><dd>{doc}<p>'
                + '<br>'.join(lines) + '</p></dd>')

    # the structs' places first (a hook links its struct): each family's page split as its items are
    family_pages = {}
    for fam in families.values():
        rel = f'nn/f/{fam["name"]}.html'
        for it in fam['items']:
            if it['kind'] == 'struct':
                struct_at.setdefault(it['name'], f'{fam["name"]}.html#{it["anchor"]}')
    for fam in families.values():
        rel = f'nn/f/{fam["name"]}.html'
        blocks, last = [], None
        for it in fam['items']:
            intro = it['comment'] if it['cid'] != last and it['comment'] else None
            last = it['cid']
            blocks.append((intro, item_html(it, rel), it))
        moving = fam['file'] in NN_HOOKS

        def render(chunk, k, n, fam=fam, moving=moving):
            nav = '' if n == 1 else '<p>Page ' + ' '.join(
                (f'<a href="{fam["name"]}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                for j in range(1, n + 1)) + '</p>'
            body, open_ = [], False
            for intro, b, _ in chunk:
                if intro or not open_:
                    if open_:
                        body.append('</dl>')
                    if intro:
                        body.append(f'<p class="note">{html.escape(intro)}</p>')
                    body.append('<dl>')
                    open_ = True
                body.append(b)
            if open_:
                body.append('</dl>')
            head = (f'<h1>{html.escape(fam["name"])}</h1><p class="groups">Family of <a href="{src}/{fam["file"]}#L'
                    f'{fam["line"]}">{fam["file"]}</a>' + (' (to move to src/nx/nn)' if moving else '') +
                    '. The hooks_off setting turns a family off by its name.</p>'
                    + (f'<p>{html.escape(fam["comment"])}</p>' if fam['comment'] and k == 1 else ''))
            return site.page(fam['name'], fam['name'], head + nav + '\n'.join(body) + nav, 2, manual=NN_MANUAL)

        try:
            split = split_pages(blocks, render, rel) if blocks else [(rel, [])]
            for k, (r, chunk) in enumerate(split, 1):
                site.write(r, render(chunk, k, len(split)))
                for _, _, it in chunk:
                    anchors[id(it)] = f'{r[len("nn/"):]}#{it["anchor"]}'
        except Exception as e:  # its declarations changed in a way this doesn't read: this family alone fails
            site.failed_page(rel, fam['name'], 2, NN_MANUAL, e)

    # the namespaces: each hook by its demangled name; the C functions by family
    spaces = {}
    for fam in families.values():
        for it in fam['items']:
            if it['kind'] != 'hook' or id(it) not in anchors:
                continue
            d, short = display(it['symbol'])
            if d:
                parts = strip_template_args(short).split('::')
                space = ('::'.join(parts[:2]) if parts[0] == 'nn' and len(parts) > 2 else parts[0] if len(parts) > 1
                         else 'Global C++')
            else:
                space = 'C'
            spaces.setdefault(space, []).append((short, d, it, fam))
            rows.append([short, f'nn/{anchors[id(it)]}', 'nn', f'{fam["name"]}, {it["symbol"]}'])

    def space_file(space):
        return 'C-functions' if space == 'C' else re.sub(r'[^\w]+', '-', space).strip('-')

    for space, entries in spaces.items():
        entries.sort(key=lambda e: (e[0].lower(), e[2]['line']))
        items_ = [f'<tr><td><a href="../{anchors[id(it)]}"><code>{html.escape(d or it["symbol"])}</code></a>'
                  f'{tags(it)}</td><td><a href="../f/{fam["name"]}.html">{fam["name"]}</a></td></tr>'
                  for short, d, it, fam in entries]
        title = 'The C functions' if space == 'C' else space

        def render(chunk, k, n, space=space, title=title):
            stem = space_file(space)
            nav = '' if n == 1 else '<p>Page ' + ' '.join(
                (f'<a href="{stem}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                for j in range(1, n + 1)) + '</p>'
            return site.page(title, title, f'<h1>{html.escape(title)}</h1>{nav}<table class="fields"><tr><th>Function'
                             f'</th><th>Family</th></tr>{"".join(chunk)}</table>{nav}', 2, manual=NN_MANUAL)

        rel = f'nn/n/{space_file(space)}.html'
        try:
            split = split_pages(items_, render, rel)
            for k, (r, chunk) in enumerate(split, 1):
                site.write(r, render(chunk, k, len(split)))
        except Exception as e:
            site.failed_page(rel, title, 2, NN_MANUAL, e)

    # the SVCs: a table by number, each SVC's registers in both ABIs
    n_svcs = 0
    svc_path = os.path.join(root, NN_SVC)
    svc_note = ''
    if os.path.exists(svc_path):
        try:
            types, svcs = parse_svcs(svc_path)
            n_svcs = len(svcs)

            def regs(r, abi):
                return '+'.join(('x' if abi else 'r') + str(x) for x in r) if r else ''

            trs = []
            for s in svcs:
                ins = '<br>'.join(f'{html.escape(a["type"])} {html.escape(a["name"])}: {regs(a["regs"][1], 1)} / '
                                  f'{regs(a["regs"][0], 0)}' for a in s['args'] if not a['output'])
                outs = ([f'{html.escape(s["ret"])}: {regs(s["ret_regs"][1], 1)} / {regs(s["ret_regs"][0], 0)}']
                        if s['ret_regs'][1] else []) + [
                    f'{html.escape(a["type"])} {html.escape(a["name"])}: {regs(a["regs"][1], 1)} / {regs(a["regs"][0], 0)}'
                    for a in s['args'] if a['output']]
                handler = 'none: it answers NotImplemented' if 'stub' in s['flags'] else handler_html('svc_' + s['name'])
                flags = ', '.join(f for f in s['flags'] if f != 'stub')
                trs.append(f'<tr id="{s["name"]}"><td>0x{s["number"]:02X}</td><td><a href="{src}/{NN_SVC}#L{s["line"]}">'
                           f'{html.escape(s["name"])}</a></td><td>{ins}</td><td>{"<br>".join(outs)}</td>'
                           f'<td>{handler}{(" (" + flags + ")") if flags else ""}</td></tr>')

            def render(chunk, k, n):
                nav = '' if n == 1 else '<p>Page ' + ' '.join(
                    (f'<a href="svc{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                    for j in range(1, n + 1)) + '</p>'
                return site.page('SVCs', 'SVCs', '<h1>SVCs</h1><p>The kernel\'s SVCs, from <a href="'
                                 f'{src}/{NN_SVC}">hos.svc</a>, each with its registers in the 64-bit ABI and the '
                                 '32-bit one (x / r: two registers for a value wider than one), as tools/svcgen lays '
                                 'them out: the inputs; the outputs, the return value first (an output by pointer '
                                 'in the declaration comes back in a register). <a href="svc-types.html">The types</a>. '
                                 'quiet: not in the crash report\'s ring of SVCs; nowarn: no warning for InvalidHandle.'
                                 f'</p>{nav}<table class="fields"><tr><th>SVC</th><th>Name</th><th>In</th><th>Out</th>'
                                 f'<th>Handler</th></tr>{"".join(chunk)}</table>{nav}', 1, manual=NN_MANUAL)

            split = split_pages(trs, render, 'nn/svc.html')
            for k, (r, chunk) in enumerate(split, 1):
                site.write(r, render(chunk, k, len(split)))
                for tr in chunk:
                    name = re.match(r'<tr id="(\w+)"', tr).group(1)
                    s = next(x for x in svcs if x['name'] == name)
                    rows.append([name, f'{r}#{name}', 'SVC', f'0x{s["number"]:02X}'])
            site.write('nn/svc-types.html', site.page('SVC types', 'SVC types', '<h1>The SVCs\' types</h1><p>Each '
                       'type\'s size in the 32-bit and the 64-bit ABI, and what a handler takes it as (-: a structure no '
                       'handler takes yet).</p><table class="fields"><tr><th>Type</th><th>32-bit</th><th>64-bit</th>'
                       '<th>Handler</th></tr>' + ''.join(
                           f'<tr><td>{html.escape(n)}</td><td>{t["size"][0]}</td><td>{t["size"][1]}</td>'
                           f'<td>{html.escape(t["ctype"])}</td></tr>' for n, t in types.items()) + '</table>',
                       1, manual=NN_MANUAL))
            svc_note = (f'<h2>SVCs</h2><p><a href="svc.html">The kernel\'s SVCs</a> ({n_svcs}): a table by number, '
                        'each with its registers in both ABIs and its handler.</p>')
        except Exception as e:
            site.failed_page('nn/svc.html', 'SVCs', 1, NN_MANUAL, e)
            svc_note = '<h2>SVCs</h2><p><a href="svc.html">The kernel\'s SVCs</a>: not made this time.</p>'

    n_hooks = sum(1 for f in families.values() for it in f['items'] if it['kind'] == 'hook')
    nn_spaces = sorted((s for s in spaces if s not in ('C',)), key=str.lower)
    fam_rows = ''.join(f'<tr><td><a href="f/{f["name"]}.html">{f["name"]}</a></td><td>{f["file"]}</td>'
                       f'<td>{sum(1 for it in f["items"] if it["kind"] == "hook")}</td></tr>'
                       for f in families.values())
    route_list = ''.join(f'<li><code>{html.escape(demangle(r["symbol"]) or r["symbol"])}</code></li>' for r in routes)
    site.write('nn/index.html', site.page('nn API', 'nn API',
        '<h1>nn API</h1><p>The functions of the Switch\'s SDK (nn::) and C library that ScarletNX runs natively in a '
        'game\'s place, hooked by their symbols (tools/hookgen\'s declarations: <code>src/nx/hle/hook/hooks.hook</code>, '
        f'whose families are to move to <code>{NN_DIR}</code>, and <code>{NN_DIR}/*.hook</code>), and the kernel\'s '
        f'SVCs. {n_hooks} hooks in {len(families)} families. A C++ function is shown demangled; its symbol, its '
        'arguments as the handler takes them and the handler are under it.</p>'
        '<div id="search" data-root="../" data-placeholder="Search: a function, a symbol or an SVC"></div>'
        '<h2>By namespace</h2><ul class="cols">' + ''.join(
            f'<li><a href="n/{space_file(s)}.html">{html.escape(s)}</a> ({len(spaces[s])})</li>' for s in nn_spaces)
        + (f'<li><a href="n/C-functions.html">The C functions</a> ({len(spaces["C"])})</li>' if 'C' in spaces else '')
        + '</ul>' + svc_note
        + f'<h2>Families</h2><table class="fields"><tr><th>Family</th><th>File</th><th>Hooks</th></tr>{fam_rows}</table>'
        + (f'<h2>Routes</h2><p>What the runtime calls through their dispatch slots, with C of its own around them:</p>'
           f'<ul>{route_list}</ul>' if routes else '') + other_manuals({'id': 'nn'}),
        1, search=['nn'], manual=NN_MANUAL))
    return n_hooks, len(families), n_svcs

# ---- Driver bugs: the Vulkan drivers' known bugs (extension_bans.txt), one table, sortable ----

DRIVER_BUGS = 'src/common/gpu/vk/extension_bans.txt'
DRIVER_BUGS_MAX = 128 * 1024  # the one table's page, check-site.py's exception for manual/driver-bugs/
DRIVER_MANUAL = ('Driver bugs', 'driver-bugs', 'The table is ScarletNX\'s (GPL-3.0-or-later).')
# the other projects the table cites by a file's line, at the revision its header names
DRIVER_PROJECTS = {
    'ANGLE': 'https://chromium.googlesource.com/angle/angle/+/{rev}/{path}#{line}',
    'DXVK': 'https://github.com/doitsujin/dxvk/blob/{rev}/{path}#L{line}',
    'vkd3d-proton': 'https://github.com/HansKristian-Work/vkd3d-proton/blob/{rev}/{path}#L{line}',
    'Dolphin': 'https://github.com/dolphin-emu/dolphin/blob/{rev}/{path}#L{line}',
    'PPSSPP': 'https://github.com/hrydgard/ppsspp/blob/{rev}/{path}#L{line}',
}


def parse_driver_bugs(path):
    """extension_bans.txt: its fields' names (the line of names between |), their descriptions in its header, the
    other projects' revisions, and its rows, each with its line and the comment over its group"""
    lines = open(path, encoding='utf-8').read().split('\n')
    names, header, rows, group, block, blank = None, [], [], None, [], True
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith('#'):
            text = s[1:]
            if names is None:
                header.append(text)
            else:
                if blank:
                    block = []
                block.append(text.strip())
                group = ' '.join(block)
            blank = False
            continue
        if not s:
            blank = True
            continue
        cells = [c.strip() for c in s.split('|')]
        if names is None:
            names = cells
            continue
        if len(cells) != len(names):
            raise GenError(f'{path}:{n}: {len(cells)} fields, not {len(names)}')
        rows.append({'line': n, 'cells': cells, 'group': group})
        blank = False
    if names is None:
        raise GenError(f'{path}: no line of the fields\' names')
    fields, cur = {}, None
    for h in header:  # "   key       an extension..." and the lines that go on with it
        m = re.match(r'\s{3}(\w+)\s{2,}(\S.*)$', h)
        if m and m.group(1) in names:
            cur = m.group(1)
            fields[cur] = m.group(2)
        elif cur and re.match(r'\s{6,}\S', h):
            fields[cur] += ' ' + h.strip()
        else:
            cur = None
    text = ' '.join(h.strip() for h in header)
    revisions = {m.group(1): (m.group(2), m.group(3).split(',')[0].strip())
                 for m in re.finditer(r'\b(' + '|'.join(re.escape(k) for k in DRIVER_PROJECTS) +
                                      r') ([0-9a-f]{7,40}) \(([^)]+)\)', text)}
    return names, fields, revisions, rows


def build_driver_bugs(site, root, rows_out):
    names, fields, revisions, rows = parse_driver_bugs(os.path.join(root, DRIVER_BUGS))
    src = f'{GITHUB}/{site.commit[:12]}/{DRIVER_BUGS}'

    def linked(text):
        """A source's text: ScarletNX's commits and the other projects' file:line linked"""
        out, last = [], 0
        pat = re.compile(r'\bScarletNX ([0-9a-f]{7,40})\b|\b(' + '|'.join(re.escape(k) for k in DRIVER_PROJECTS)
                         + r') ([\w.\-/]+):(\d+)')
        for m in pat.finditer(text):
            out.append(html.escape(text[last:m.start()]))
            if m.group(1):
                out.append(f'ScarletNX <a href="https://github.com/scarletnx/ScarletNX/commit/{m.group(1)}">'
                           f'{m.group(1)}</a>')
            else:
                project, file, line = m.group(2), m.group(3), m.group(4)
                rev = revisions.get(project)
                if rev and rev[1].rsplit('/', 1)[-1] == file.rsplit('/', 1)[-1]:
                    url = DRIVER_PROJECTS[project].format(rev=rev[0], path=rev[1], line=line)
                    out.append(f'{project} <a href="{url}">{html.escape(file)}:{line}</a>')
                else:
                    out.append(html.escape(m.group(0)))
            last = m.end()
        out.append(html.escape(text[last:]))
        return ''.join(out)

    def area(group):
        return re.split(r' \(|: |\. ', group or '', maxsplit=1)[0] if group else ''

    heads = ['line'] + names + ['area']
    trs = []
    for r in rows:
        cells = [f'<td data-sort="{r["line"]:05d}"><a href="{src}#L{r["line"]}">{r["line"]}</a></td>']
        for name, value in zip(names, r['cells']):
            shown = linked(value) if name == 'source' else html.escape(value)
            if name == 'key':  # a long key may break after its _ and its .
                shown = '<code>' + re.sub(r'([_.])', r'\1<wbr>', shown) + '</code>'
            cells.append(f'<td>{shown}</td>')
        cells.append(f'<td title="{html.escape(r["group"] or "")}">{html.escape(area(r["group"]))}</td>')
        trs.append('<tr>' + ''.join(cells) + '</tr>')
        rows_out.append(r)
    counts = {}
    for r in rows:
        counts[r['cells'][names.index('action')] if 'action' in names else ''] = counts.get(
            r['cells'][names.index('action')] if 'action' in names else '', 0) + 1
    legend = ''.join(f'<dt>{html.escape(n)}</dt><dd>{html.escape(fields[n])}</dd>' for n in names if n in fields)
    body = ('<h1>Driver bugs</h1><p>The Vulkan drivers known to break an extension or a feature the renderer uses, '
            f'as <a href="{src}">extension_bans.txt</a> lists them: {len(rows)} lines, '
            + ', '.join(f'{v} {html.escape(k)}' for k, v in sorted(counts.items())) +
            '. The renderer reads it before it turns anything on: an off line takes the extension out of the device\'s '
            'list or turns the feature off, a warn line is only said, a prefer line takes a way on the drivers it '
            'lists alone. A header sorts the table by its column (line: the file\'s order); area is the comment over '
            'the line\'s group, whole as its title.</p>'
            '<div class="wide"><table class="fields" id="bugs"><thead><tr>' + ''.join(f'<th>{html.escape(h)}</th>' for h in heads)
            + '</tr></thead><tbody>' + ''.join(trs) + '</tbody></table></div>'
            + (f'<h2>The columns</h2><dl>{legend}<dt>area</dt><dd>the comment over the group the line is in</dd></dl>'
               if legend else '') + other_manuals({'id': 'driver-bugs'}))
    site.write('driver-bugs/index.html', site.page('Driver bugs', 'Driver bugs', body, 1, manual=DRIVER_MANUAL,
                                                   scripts=('sort.js',)), limit=DRIVER_BUGS_MAX)
    return len(rows)


# ---- the NVN manual: the API ScarletNX implements (nvn.hook), its types (nvn.h), Switch 2's marked ----

NVN_DIR = 'src/nx/gpu/nvn'
VK_FORMATS = 'src/nx/gpu/vk/format.c'
VK_FORMAT_URL = 'https://docs.vulkan.org/refpages/latest/refpages/source/VkFormat.html#:~:text={}%20specifies'
NVN_MANUAL = ('NVN API', 'nvn', 'nvn.h is h1k421\'s reconstruction (MIT); nvn.hook, the handlers and the format table '
                                'ScarletNX\'s (GPL-3.0-or-later). The Switch 2 marks are the drivers\' procedure tables '
                                '(<code>tools/manual/nvn-drivers.txt</code>).')
HOOK_TYPES = 'i32, u32, i64, u64: integers of that many bits; f32: float; bool: NVNboolean; usize, isize: size_t, ptrdiff_t'


def friendly(comment):
    """A comment of ScarletNX's as the manual shows it: Switch 2 by its name, not its code name"""
    if not comment:
        return comment
    comment = re.sub(r"\bthe Ounce's\b", "Switch 2's", comment)
    return re.sub(r'\b([Aa])n Ounce\b', r'\1 Switch 2', comment).replace('Ounce', 'Switch 2')


def nvn_badge(where):
    """A function's or a type's platforms: Switch 2 alone, Switch alone (NVN2 dropped it), or both (no mark)"""
    if where == {'s2'}:
        return ' <span class="s2">Switch 2</span>'
    if where == {'s1'}:
        return ' <span class="s1">Switch 1</span>'
    return ''


def parse_doc(lines):
    """A function's doc comment (nvn.hook's ## lines, doxygen's commands): its brief, its parameters' (name, text),
    what it returns, and any other command's (name, text); a line not starting with a command goes on with the last"""
    items = []
    for line in lines:
        m = re.match(r'[@\\](\w+)\s*(.*)', line)
        if m:
            items.append([m.group(1), m.group(2).strip()])
        elif line:
            if not items:
                items.append(['brief', ''])
            items[-1][1] = (items[-1][1] + ' ' + line).strip()
    doc = {'brief': None, 'params': [], 'return': None, 'other': []}
    for tag, text in items:
        if tag == 'brief':
            doc['brief'] = text if doc['brief'] is None else doc['brief'] + ' ' + text
        elif tag == 'param':
            m = re.match(r'(?:\[\w,]+\]\s*)?(\w+)\s*(.*)', text)
            doc['params'].append((m.group(1), m.group(2)) if m else (text, ''))
        elif tag in ('return', 'returns'):
            doc['return'] = text
        else:
            doc['other'].append((tag, text))
    return doc


def parse_hook(path):
    """nvn.hook's families and functions: name, return, arguments, handler, the comment over it (a # comment may be
    over several), its doc comment (## lines right over it), its line"""
    families, fam, block, run, doc = [], None, None, [], None
    lines = open(path, encoding='utf-8').read().split('\n')
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith('##'):
            if fam is not None:
                doc = (doc or []) + [s[2:].strip()]
            continue
        if s.startswith('#'):
            if fam is not None:
                if run:  # a comment after functions starts anew
                    block, run = None, []
                block = (block + ' ' if block else '') + s[1:].strip()
            continue
        if not s:
            block, run, doc = None, [], None
            continue
        w = s.split()
        if w[0] == 'family':
            fam = {'name': w[1], 'funcs': []}
            families.append(fam)
            block, run, doc = None, [], None
        elif w[0] == 'route':
            if not families or families[0]['name'] != 'loader':
                families.insert(0, {'name': 'loader', 'funcs': []})
            families[0]['funcs'].append({'name': w[1], 'ret': 'PFNNVNGENERICFUNCPTRPROC', 'args': [],
                                         'handler': None, 'comment': None, 'doc': None, 'line': i, 'route': True})
        elif w[0] == 'hook':
            m = re.match(r'hook (\w+)\((.*)\)\s*(?:->\s*([^=]+?))?\s*(?:=\s*(\w+))?$', s)
            name, args, ret, handler = m.group(1), m.group(2), (m.group(3) or 'void').strip(), m.group(4)
            arglist = []
            for a in [a.strip() for a in args.split(',') if a.strip()]:
                am = re.match(r'(.*?)(\w+)$', a)
                arglist.append((am.group(1).strip(), am.group(2)))
            f = {'name': name, 'ret': ret, 'args': arglist, 'handler': handler or 'nvn_' + name[3:],
                 'comment': block, 'doc': parse_doc(doc) if doc else None, 'line': i}
            fam['funcs'].append(f)
            run.append(f)
            doc = None
    return families


def parse_nvn_h(path, inc):
    """nvn.h's types: typedefs, structs, enums (values, and the comment over each), the callbacks' typedefs"""
    text = open(path, encoding='utf-8').read()
    text = text[text.index('#pragma once'):]
    types, lines, i, comment = {}, text.split('\n'), 0, None
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith('/*') or s.startswith('//'):
            c = [s]
            while s.startswith('/*') and '*/' not in lines[i]:
                i += 1
                c.append(lines[i].strip())
            comment = clean_comment(c)
            i += 1
            continue
        if not s:
            comment = None
            i += 1
            continue
        m = re.match(r'typedef ([\w\s\*]+?)\s*\*?(\w+);$', s)
        if m and '(' not in s:
            types[m.group(2)] = {'kind': 'typedef', 'text': s, 'comment': comment, 'line': i + 1}
        elif s.startswith('typedef struct {') or s.startswith('typedef enum {') or re.match(r'enum \w+ \{', s):
            j = i
            while not re.match(r'\}\s*(\w+)?;', lines[j].strip()):
                j += 1
            name = re.match(r'\}\s*(\w+)?;', lines[j].strip()).group(1) or re.match(r'enum (\w+)', s).group(1)
            body = lines[i:j + 1]
            if 'enum' in s:
                values, vcomment, vs2 = [], None, False
                for b in body[1:-1]:
                    bs = b.strip()
                    if bs.startswith('/*') or bs.startswith('//'):
                        vcomment = clean_comment([bs])
                        vs2 = 'Ounce' in bs
                    elif not bs:
                        vcomment, vs2 = None, False
                    elif bs.startswith('#include'):
                        for f in re.finditer(r'NVN_TIC_FORMAT\((\w+), (\w+), (\d), (\d), (\d), (\w+), (\w+)\)', inc):
                            values.append({'name': 'NVN_FORMAT_' + f.group(7), 'value': f.group(1), 'comment': None,
                                           's2': False, 'tic': (int(f.group(2).rstrip('u'), 16), int(f.group(4)),
                                                                int(f.group(5)), int(f.group(6), 16))})
                    elif not bs.startswith('#'):
                        vm = re.match(r'(\w+)\s*=\s*([^,]+),?', bs)
                        if vm and not vm.group(1).endswith('_LARGE'):
                            values.append({'name': vm.group(1), 'value': vm.group(2).strip(), 'comment': vcomment,
                                           's2': vs2})
                types[name] = {'kind': 'enum', 'values': values, 'comment': comment, 'line': i + 1,
                               'text': '\n'.join(body)}
            else:
                types[name] = {'kind': 'struct', 'text': '\n'.join(body), 'comment': comment, 'line': i + 1}
            i = j + 1
            comment = None
            continue
        elif s.startswith('typedef') and '(' in s:
            j = i
            while not lines[j].rstrip().endswith(';'):
                j += 1
            full = ' '.join(l.strip() for l in lines[i:j + 1])
            name = re.search(r'\(\*(\w+)\)', full).group(1)
            types[name] = {'kind': 'callback', 'text': '\n'.join(lines[i:j + 1]), 'comment': comment, 'line': i + 1}
            i = j + 1
            continue
        i += 1
    return types


def vk_format_tables(path):
    """vk/format.c's switches: the render target codes', the depth targets', and the texture header's format field's
    (each case's VK_FORMAT names, in order)"""
    text = open(path, encoding='utf-8').read()

    def cases(fn):
        start = text.index(fn)
        body = text[start:text.index('\n}\n', start)]
        table, pending = {}, []
        for part in re.split(r'\n\s*case ', body)[1:]:
            code = int(re.match(r'(0x[0-9A-Fa-f]+|\d+)', part).group(1), 0)
            rest = part.split(':', 1)[1]
            pending.append(code)
            if 'return' in rest:  # else it falls through to the next case (a comment is no body)
                for c in pending:
                    table[c] = rest
                pending = []
        return table

    return cases('static VkFmt rt_format('), cases('VkFmt vk_zt_format('), cases('static VkFmt tic_format(')


def vk_of_format(tic, rt, zt, tex):
    """The Vulkan format whose layout an NVN format's texels have, as ScarletNX's tables give it (None: none)"""
    word, srgb, depth, code = tic

    def first(body):
        found = re.findall(r'VK_FORMAT_\w+', body)
        return found[0] if found else None

    if not word:
        return None
    if depth and code in zt:
        return first(zt[code])
    if code and not depth and code in rt:
        f = first(rt[code])
        return f.replace('_UNORM', '_SRGB') if srgb and f and '_SRGB' not in f and 'R8G8B8A8' in f else f
    body = tex.get(word & 0x7F)
    if body is None:
        return None
    tv = re.match(r'\s*return TV\((VK_FORMAT_\w+)', body)
    if tv:  # no Vulkan format has its layout: converted on upload
        return tv.group(1) + ' converted'
    ta = re.search(r'TA\((\d+), (\d+)', body)
    if ta:
        return f'VK_FORMAT_ASTC_{ta.group(1)}x{ta.group(2)}_{"SRGB" if srgb else "UNORM"}_BLOCK'
    zm = re.search(r'vk_zt_format\((0x[0-9A-Fa-f]+)\)', body)
    if zm:
        return first(zt.get(int(zm.group(1), 16), ''))
    found = list(dict.fromkeys(re.findall(r'VK_FORMAT_\w+', body)))
    if not found:
        return None
    blocks = [f for f in found if f.endswith('_BLOCK') and 'ASTC' not in f]
    pool = blocks or found
    pool = [f for f in pool if ('SRGB' in f) == bool(srgb)] or pool
    ct = (word >> 7) & 7
    want = {7: ('SFLOAT', 'UFLOAT'), 1: ('SNORM',), 4: ('UINT',), 3: ('SINT',)}.get(ct, ('UNORM', 'SRGB'))
    return next((f for f in pool if any(w in f for w in want)), pool[0])


def build_nvn(site, root, rows, here):
    base = os.path.join(root, NVN_DIR)
    families = parse_hook(os.path.join(base, 'nvn.hook'))
    types = parse_nvn_h(os.path.join(base, 'nvn.h'), open(os.path.join(base, 'nvn_tic_format.inc')).read())
    drivers = {}
    for line in open(os.path.join(here, 'manual', 'nvn-drivers.txt'), encoding='utf-8'):
        if line.strip() and not line.startswith('#'):
            name, where = line.rstrip('\n').split('\t')
            drivers['nvn' + name] = set(where.split())
    vk_path = os.path.join(root, VK_FORMATS)
    vk_tables = vk_format_tables(vk_path) if os.path.exists(vk_path) else ({}, {}, {})

    # the handlers' definitions: file and line, for the links
    handlers = {}
    for fname in sorted(os.listdir(base)):
        if fname.endswith('.c'):
            for n, line in enumerate(open(os.path.join(base, fname), encoding='utf-8'), 1):
                m = re.match(r'[A-Za-z][\w\s\*]*?\b(nvn_\w+)\(', line)
                if m and not line.rstrip().endswith(';'):
                    handlers.setdefault(m.group(1), (f'{NVN_DIR}/{fname}', n))
    hook_rel = f'{NVN_DIR}/nvn.hook'
    funcs = [f for fam in families for f in fam['funcs']]
    for f in funcs:
        f['where'] = drivers.get(f['name'], set())
    # where a comment ends: at the first function under it of other platforms than the first one's (nvn.hook's
    # comments run on into the functions after the ones they are about)
    for fam in families:
        first, cut = {}, set()
        for f in fam['funcs']:
            c = f['comment']
            if c is None:
                continue
            if c in cut:
                f['comment'] = None
            elif c not in first:
                first[c] = f['where']
            elif f['where'] != first[c]:
                cut.add(c)
                f['comment'] = None

    # a type's platforms: the functions that name it, when every one is of one platform
    users = {}
    for f in funcs:
        for t in set(re.findall(r'\b(?:NVN|PFNNVN)\w+', f['ret'] + ' ' + ' '.join(a for a, _ in f['args']))):
            users.setdefault(t, []).append(f)
    for name, t in types.items():
        wh = [frozenset(f['where']) for f in users.get(name, []) if f['where']]
        t['where'] = set(wh[0]) if wh and all(w == wh[0] for w in wh) else set()
        if t.get('comment') and 'Ounce' in t['comment']:
            t['where'] = {'s2'}
        t['users'] = users.get(name, [])

    def type_href(name, up):
        t = types.get(name)
        if not t:
            return None
        return f'{up}{"e" if t["kind"] == "enum" else "t"}/{name}.html'

    def linked(text, up):
        return re.sub(r'\b(NVN\w+|PFNNVN\w+)\b',
                      lambda m: f'<a href="{type_href(m.group(1), up)}">{m.group(1)}</a>' if type_href(m.group(1), up)
                      else m.group(1), html.escape(text))

    def signature(f, up):
        args = ', '.join(f'{linked(t, up)} {n}' for t, n in f['args'])
        return f'<pre class="sig">{linked(f["ret"], up)} {f["name"]}({args})</pre>'

    # a doc comment's text: the functions, types and enums' values it names linked
    func_names = {f['name'] for fam in families for f in fam['funcs']}
    value_of = {v['name']: name for name, t in types.items() if t['kind'] == 'enum' for v in t['values']}

    def doc_text(text, up):
        def link(m):
            w = m.group(0)
            if w in func_names:
                return f'<a href="{up}f/{w}.html">{w}</a>'
            if type_href(w, up):
                return f'<a href="{type_href(w, up)}">{w}</a>'
            if w in value_of:
                return f'<a href="{up}e/{value_of[w]}.html#{w}">{w}</a>'
            return w
        return re.sub(r'\b(?:nvn|NVN|PFNNVN)\w*', link, html.escape(friendly(text)))

    def doc_html(f, up):
        doc, parts = f['doc'], []
        if not doc:
            return parts
        documented = dict(doc['params'])
        names = [n for _, n in f['args']] + [n for n, _ in doc['params'] if n not in {a for _, a in f['args']}]
        if any(documented.get(n) for n in names):
            parts.append('<h2>Parameters</h2><table class="fields"><tr><th>Parameter</th><th>Type</th><th>Description</th></tr>'
                         + ''.join(f'<tr><td><code>{n}</code></td><td>{linked(dict((a, t) for t, a in f["args"]).get(n, ""), up)}'
                                   f'</td><td>{doc_text(documented.get(n, ""), up)}</td></tr>' for n in names) + '</table>')
        if doc['return']:
            parts.append(f'<h2>Returns</h2><p>{doc_text(doc["return"], up)}</p>')
        for tag, text in doc['other']:
            parts.append(f'<h2>{html.escape(tag.capitalize())}</h2><p>{doc_text(text, up)}</p>')
        return parts

    def page(rel, title, body, depth, search=False):
        site.write(f'nvn/{rel}', site.page(title, title, body, depth, search=['nvn'] if search else None,
                                          manual=NVN_MANUAL))

    def ftitle(fam):
        return fam['name'].replace('_', ' ').capitalize()

    legend = ('<p class="legend"><span class="s2">Switch 2</span> only in Switch 2\'s NVN (NVN2) '
              '<span class="s1">Switch 1</span> only in the Switch\'s, which NVN2 dropped; no mark: both</p>')

    # a page per function
    for fam in families:
        for f in fam['funcs']:
            try:
                parts = [f'<h1>{f["name"]}{nvn_badge(f["where"])}</h1>',
                         f'<p class="groups"><a href="../{fam["name"]}.html">{html.escape(ftitle(fam))}</a></p>',
                         signature(f, '../')]
                if f['doc'] and f['doc']['brief']:
                    parts.append(f'<p>{doc_text(f["doc"]["brief"], "../")}</p>')
                if f['comment']:
                    parts.append(f'<p>{html.escape(friendly(f["comment"]))}</p>')
                parts += doc_html(f, '../')
                plat = ('Switch and Switch 2' if f['where'] == {'s1', 's2'} else 'Switch 2 (NVN2)' if f['where'] == {'s2'}
                        else 'Switch (dropped in NVN2)' if f['where'] == {'s1'} else 'in no driver\'s procedure table: '
                        'the SDK exports it itself')
                rows_ = [('Drivers', plat),
                         ('Declared', f'<a href="{GITHUB}/{site.commit}/{hook_rel}#L{f["line"]}">nvn.hook</a>')]
                if f.get('route'):
                    rows_.append(('Handler', f'the loader\'s own (<code>nvn_loader.c</code>)'))
                else:
                    h = handlers.get(f['handler'])
                    rows_.append(('Handler', f'<a href="{GITHUB}/{site.commit}/{h[0]}#L{h[1]}"><code>{f["handler"]}</code></a> '
                                             f'({h[0].rsplit("/", 1)[1]})' if h else f'<code>{f["handler"]}</code>'))
                parts.append('<table class="fields">' + ''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in rows_)
                             + '</table>')
                parts.append(f'<p class="note">Types as nvn.hook writes them: {HOOK_TYPES}.</p>')
                page(f'f/{f["name"]}.html', f['name'], '\n'.join(parts), 2)
                rows.append([f['name'], f'nvn/f/{f["name"]}.html', 'NVN',
                             'function' + (', Switch 2' if f['where'] == {'s2'} else ', Switch 1' if f['where'] == {'s1'} else '')])
            except Exception as e:  # its sources changed in a way this doesn't read: this page alone fails
                site.failed_page(f'nvn/f/{f["name"]}.html', f['name'], 2, NVN_MANUAL, e)

    # a page per family, split when it must be
    for fam in families:
        briefs = any(f['doc'] and f['doc']['brief'] for f in fam['funcs'])
        trs = [f'<tr{" class=\"s2row\"" if f["where"] == {"s2"} else ""}><td><a href="f/{f["name"]}.html">{f["name"]}</a>'
               f'{nvn_badge(f["where"])}</td><td>{linked(f["ret"], "")}</td>'
               + (f'<td>{html.escape(friendly(f["doc"]["brief"])) if f["doc"] and f["doc"]["brief"] else ""}</td>' if briefs else '')
               + '</tr>' for f in sorted(fam['funcs'], key=lambda f: f['name'])]

        def render(chunk, k, n, fam=fam, briefs=briefs):
            nav = '' if n == 1 else '<p>Page ' + ' '.join(
                (f'<a href="{fam["name"]}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                for j in range(1, n + 1)) + '</p>'
            return site.page(ftitle(fam), ftitle(fam), f'<h1>{html.escape(ftitle(fam))}</h1>{legend}{nav}'
                             f'<table class="fields"><tr><th>Function</th><th>Returns</th>'
                             f'{"<th>Description</th>" if briefs else ""}</tr>{"".join(chunk)}</table>{nav}',
                             1, manual=NVN_MANUAL)

        split = split_pages(trs, render, f'nvn/{fam["name"]}.html')
        for k, (rel, chunk) in enumerate(split, 1):
            site.write(rel, render(chunk, k, len(split)))

    # a page per enum (its values split over pages when they must be), and per type
    rt, zt, tex = vk_tables
    for name, t in sorted(types.items()):
        try:
            used = sorted({f['name'] for f in t['users']})
            used_html = ('<h2>Used by</h2><ul class="cols">' + ''.join(f'<li><a href="../f/{u}.html">{u}</a></li>' for u in used)
                         + '</ul>') if used else ''
            src = f'<p><a class="src" href="{GITHUB}/{site.commit}/{NVN_DIR}/nvn.h#L{t["line"]}">nvn.h</a></p>'
            head = f'<h1>{name}{nvn_badge(t["where"])}</h1>{src}' + (f'<p>{html.escape(friendly(t["comment"]))}</p>' if t['comment'] else '')
            if t['kind'] == 'enum':
                is_format = name == 'NVNformat'
                trs = []
                for v in t['values']:
                    cells = f'<td id="{v["name"]}">{v["name"]}{" <span class=\"s2\">Switch 2</span>" if v["s2"] else ""}</td><td>{html.escape(v["value"])}</td>'
                    if is_format:
                        vk = vk_of_format(v['tic'], rt, zt, tex)
                        conv = vk and vk.endswith(' converted')
                        vk = vk.split()[0] if vk else vk
                        cells += (f'<td><a href="{VK_FORMAT_URL.format(vk)}">{vk}</a>'
                                  f'{" (converted to it on upload)" if conv else ""}</td>' if vk else
                                  '<td>(none: ScarletNX has no texture descriptor for it)</td>')
                    elif any(x['comment'] for x in t['values']):
                        cells += f'<td>{html.escape(friendly(v["comment"]) or "")}</td>'
                    trs.append(f'<tr{" class=\"s2row\"" if v["s2"] else ""}>{cells}</tr>')
                    rows.append([v['name'], f'nvn/e/{name}.html#{v["name"]}', 'NVN',
                                 f'{name} {v["value"]}' + (', Switch 2' if v['s2'] or t['where'] == {'s2'} else '')])
                hdr = '<tr><th>Name</th><th>Value</th>' + ('<th>Vulkan format</th>' if is_format else
                      '<th>Note</th>' if any(x['comment'] for x in t['values']) else '') + '</tr>'
                note = ('<p>The Vulkan format whose texels are laid out as the NVN format\'s, as ScarletNX\'s tables give it '
                        '(<code>nvn_tic_format.inc</code>, then <code>vk/format.c</code>); a block-compressed format the GPU '
                        'can\'t sample, ScarletNX decodes. The link is the format\'s definition on docs.vulkan.org.</p>'
                        if is_format else '')

                def render(chunk, k, n, name=name, head=head, hdr=hdr, note=note, used_html=used_html):
                    nav = '' if n == 1 else '<p>Page ' + ' '.join(
                        (f'<a href="{name}{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
                        for j in range(1, n + 1)) + '</p>'
                    return site.page(name, name, f'{head}{note}{nav}<table class="fields">{hdr}{"".join(chunk)}</table>{nav}'
                                     + (used_html if k == n else ''), 2, manual=NVN_MANUAL)

                split = split_pages(trs, render, f'nvn/e/{name}.html')
                for k, (rel, chunk) in enumerate(split, 1):
                    site.write(rel, render(chunk, k, len(split)))
            else:
                body = head + f'<pre>{linked(t["text"], "../")}</pre>' + used_html
                if len(site.page(name, name, body, 2, manual=NVN_MANUAL).encode()) > MAX_BYTES:
                    # too many users to name: how many of each family's
                    counts = {}
                    for f in t['users']:
                        fam = next(fm for fm in families if f in fm['funcs'])
                        counts[fam['name']] = counts.get(fam['name'], 0) + 1
                    body = head + f'<pre>{linked(t["text"], "../")}</pre><h2>Used by</h2><ul>' + ''.join(
                        f'<li>{c} functions of <a href="../{fn}.html">{html.escape(fn.replace("_", " ").capitalize())}</a></li>'
                        for fn, c in sorted(counts.items())) + '</ul>'
                page(f't/{name}.html', name, body, 2)
            rows.append([name, f'nvn/{"e" if t["kind"] == "enum" else "t"}/{name}.html', 'NVN',
                         t['kind'] + (', Switch 2' if t['where'] == {'s2'} else '')])
        except Exception as e:  # its sources changed in a way this doesn't read: this page alone fails
            site.failed_page(f'nvn/{"e" if t["kind"] == "enum" else "t"}/{name}.html', name, 2, NVN_MANUAL, e)

    # the drivers' functions nvn.hook doesn't have
    have = {f['name'] for f in funcs}
    missing = sorted(n for n in drivers if n not in have)
    def render_missing(chunk, k, n):
        nav = '' if n == 1 else '<p>Page ' + ' '.join(
            (f'<a href="missing{"" if j == 1 else f"-{j}"}.html">{j}</a>' if j != k else f'<b>{j}</b>')
            for j in range(1, n + 1)) + '</p>'
        return site.page('Not implemented', 'Not implemented', f'<h1>Not implemented</h1>{legend}<p>The functions of '
                         f'the drivers\' procedure tables that ScarletNX doesn\'t implement: a game that calls one '
                         f'stops with its name.</p>{nav}<ul class="cols">' + ''.join(chunk) + f'</ul>{nav}', 1,
                         manual=NVN_MANUAL)

    split = split_pages([f'<li>{n}{nvn_badge(drivers[n])}</li>' for n in missing], render_missing, 'nvn/missing.html')
    for k, (rel, chunk) in enumerate(split, 1):
        site.write(rel, render_missing(chunk, k, len(split)))

    def type_list(kind):
        return '<ul class="cols">' + ''.join(
            f'<li><a href="{type_href(n, "")}">{n}</a>{nvn_badge(t["where"])}</li>'
            for n, t in sorted(types.items()) if t['kind'] in kind) + '</ul>'

    page('enums.html', 'Enums', f'<h1>Enums</h1>{legend}' + type_list(('enum',)), 1)
    page('types.html', 'Types', f'<h1>Types</h1>{legend}<h2>Objects and structures</h2>' + type_list(('struct',))
         + '<h2>Typedefs</h2>' + type_list(('typedef',)) + '<h2>Callbacks</h2>' + type_list(('callback',)), 1)
    s2 = sum(1 for f in funcs if f['where'] == {'s2'})
    fams = ''.join(f'<li><a href="{fam["name"]}.html">{html.escape(ftitle(fam))}</a> ({len(fam["funcs"])}'
                   + (f', <span class="s2">{sum(1 for f in fam["funcs"] if f["where"] == {"s2"})} Switch 2</span>'
                      if any(f['where'] == {'s2'} for f in fam['funcs']) else '') + ')</li>' for fam in families)
    page('index.html', 'NVN API', f'<h1>NVN API</h1><p>NVN, the graphics API of the Switch and, as NVN2, of the Switch 2, '
         f'as ScarletNX implements it on Vulkan: every function a game resolves (<code>nvn.hook</code>), with its '
         f'signature, what it does (its doc comment there) and the handler that runs it, and the types and enums of '
         f'<code>nvn.h</code>. NVN2 keeps the '
         f'Switch\'s API and adds to it: what only Switch 2\'s drivers have is marked.</p>{legend}'
         '<div id="search" data-root="../" data-placeholder="Search: a function, type, enum or value"></div><p>The search takes a function, type, enum or value\'s name '
         '(the nearest when none is the same).</p>'
         f'<h2>Functions</h2><p>{len(funcs)} functions, {s2} of them Switch 2\'s.</p><ul>{fams}</ul>'
         f'<p><a href="missing.html">The drivers\' functions not implemented</a> ({len(missing)})</p>'
         f'<h2>Types</h2><ul><li><a href="enums.html">Enums</a> ({sum(1 for t in types.values() if t["kind"] == "enum")})</li>'
         f'<li><a href="types.html">Objects, structures, typedefs and callbacks</a> '
         f'({sum(1 for t in types.values() if t["kind"] != "enum")})</li></ul>'
         + other_manuals({'id': 'nvn'}),
         1, search=True)
    return len(funcs), s2


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
    out = argv[1] if len(argv) == 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_site', 'manual')
    commit = commit or find_commit(root, [a['dir'] for a in ARCHES] + [GPU_DIR] + [g['dir'] for g in DECODED]
                                   + [NVN_DIR, VK_FORMATS, CTR_DIR, ANDROID_DIR, NN_DIR, 'src/nx/hle/hook', 'src/nx/hle/svc',
                                      DRIVER_BUGS])
    here = os.path.dirname(os.path.abspath(__file__))

    # the manual is made whole each time: what the Sail no longer has goes
    for a in ARCHES + GPUS + DECODED:
        shutil.rmtree(os.path.join(out, a['id']), ignore_errors=True)
    BUILT.update(g['id'] for g in GPUS if os.path.exists(os.path.join(root, GPU_DIR, g['decode'])))
    BUILT.update(g['id'] for g in DECODED if os.path.exists(os.path.join(root, g['dir'], g['decode'])))
    ctr_dir = os.path.join(root, CTR_DIR)
    if os.path.isdir(ctr_dir) and any(f.endswith('.swipc') for f in os.listdir(ctr_dir)):
        BUILT.add('3ds-ipc')
    if os.path.exists(os.path.join(root, NVN_DIR, 'nvn.hook')):
        BUILT.add('nvn')
    if os.path.isdir(os.path.join(root, ANDROID_DIR)):
        BUILT.add('android')
    if any(os.path.exists(os.path.join(root, f)) for f in NN_HOOKS + [NN_SVC]) or os.path.isdir(os.path.join(root, NN_DIR)):
        BUILT.add('nn')
    shutil.rmtree(os.path.join(out, 'nn'), ignore_errors=True)
    if os.path.exists(os.path.join(root, DRIVER_BUGS)):
        BUILT.add('driver-bugs')
    shutil.rmtree(os.path.join(out, 'driver-bugs'), ignore_errors=True)
    shutil.rmtree(os.path.join(out, 'android'), ignore_errors=True)
    shutil.rmtree(os.path.join(out, '3ds-ipc'), ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    site = Site(out, commit)
    site.root = os.path.abspath(root) + os.sep
    parts = []  # the manuals that failed whole

    def part(pid, name, manual, make):
        """A manual made alone: when it fails, a page in its index's place says why, and the others are made"""
        try:
            return make()
        except Exception as e:  # its sources changed in a way this doesn't read
            traceback.print_exc()
            reason = f'{type(e).__name__}: {e}'.replace(site.root, '')
            report(f'{pid}: {reason}')
            parts.append((pid, reason))
            shutil.rmtree(os.path.join(out, pid), ignore_errors=True)
            BUILT.discard(pid)
            site.write(f'{pid}/index.html', site.page(
                name, name, f'<h1>{html.escape(name)}</h1><p>This manual could not be made from ScarletNX at '
                            f'{commit[:12]}: <code>{html.escape(reason)}</code>. The rest of the site was made; this '
                            f'page is in the manual\'s place until its generator reads ScarletNX\'s sources again.</p>'
                + other_manuals({'id': pid}), 1, manual=manual))
            return None

    def data(pid, what, rows):
        site.write(f'{pid}/data.js', f'// The search\'s data (tools/gen-manual.py): {what}\n'
                   'var ARM = (window.ARM || []).concat([\n' + ',\n'.join(
                       '[' + ','.join('"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"' for v in r) + ']'
                       for r in rows) + '\n]);\nwindow.ARM = ARM;\n')

    def made(pid, build, what, *args):
        def make():
            rows = []
            got = build(site, root, *args, rows) if args else build(site, root, rows)
            data(pid, what, rows)
            return got
        return make

    summary, arm_search = [], []
    for a in ARCHES:
        if not os.path.isdir(os.path.join(root, a['dir'])):
            continue
        got = part(a['id'], a['title'], None, made(a['id'], build_arch, 'title, page, instruction set, class, mask, '
                                                    'value, the bits that must not be a value (mask, value), and the '
                                                    'order the decoder tries it in', a))
        if got:
            arm_search.append(a['id'])
            summary.append(f'<li><a href="{a["id"]}/">{a["title"]}</a>: {a["about"]} ({got[0]} instructions, '
                           f'{got[1]} encodings)</li>')
        else:
            summary.append(f'<li><a href="{a["id"]}/">{a["title"]}</a>: {a["about"]} (not made this time)</li>')
    gpus = []
    for g in GPUS:
        if g['id'] not in BUILT:
            continue
        got = part(g['id'], g['name'], (g['name'], g['id'], ''), made(
            g['id'], build_gpu, 'title, page, instruction set, class, mask, value (of the 16-bit opcode), none, and '
                                'the order of the encodings\' file', g))
        gpus.append(f'<li><a href="{g["id"]}/">{g["name"]}</a>: {g["title"]} '
                    + (f'({got[0]} instructions, {got[1]} encodings)' if got else '(not made this time)') + '</li>')
    for g in DECODED:
        if g['id'] not in BUILT:
            continue
        got = part(g['id'], g['name'], (g['name'], g['id'], ''), made(
            g['id'], build_decoded, 'title, page, instruction set, group, mask, value (of the whole word), none, and '
                                    'the order of the encodings\' file', g))
        gpus.append(f'<li><a href="{g["id"]}/">{g["name"]}</a>: {g["title"]} '
                    + (f'({got[0]} instructions)' if got else '(not made this time)') + '</li>')
    if 'nvn' in BUILT:
        shutil.rmtree(os.path.join(out, 'nvn'), ignore_errors=True)
        part('nvn', 'NVN API', NVN_MANUAL, made('nvn', lambda site_, root_, rows: build_nvn(site_, root_, rows, here),
                                                'name, page, NVN, what it is'))
    ctr = part('3ds-ipc', '3DS IPC', CTR_MANUAL, made(
        '3ds-ipc', build_ctr_ipc, 'command, page, 3DS, service and command ID, the header word\'s mask and value, '
                                  'none, the ID')) if '3ds-ipc' in BUILT else None
    nn = part('nn', 'nn API', NN_MANUAL, made(
        'nn', build_nn, 'name (demangled), page, nn or SVC, the family and the symbol, or the SVC\'s number')) \
        if 'nn' in BUILT else None
    bugs = part('driver-bugs', 'Driver bugs', DRIVER_MANUAL,
                lambda: build_driver_bugs(site, root, [])) if 'driver-bugs' in BUILT else None
    android = part('android', 'Android API', ANDROID_MANUAL, made(
        'android', build_android, 'name, page, Java, what it is')) if 'android' in BUILT else None
    for name in ('manual.css', 'search.js', 'sort.js'):
        shutil.copyfile(os.path.join(here, 'manual', name), os.path.join(out, name))
    license_ = os.path.join(root, ARCHES[0]['dir'], 'LICENSE')
    if os.path.exists(license_):
        shutil.copyfile(license_, os.path.join(out, 'LICENSE-sail-arm.txt'))
    site.write('index.html', site.page('ARM ISA', 'ARM ISA',
               '<h1>ARM ISA</h1><p>The instructions ScarletNX recompiles, laid out as Arm\'s reference lays them out '
               'and made from the Sail it recompiles them from: <a href="https://github.com/rems-project/sail-arm">'
               'sail-arm</a>\'s model of Armv9.4-A, and ScarletNX\'s fixups of it. Each instruction has its encodings, '
               'their decode and its operation; every name they use is a page of the shared pseudocode.</p>'
               + ('<div id="search" data-root=""></div>' if arm_search else '') +
               f'<ul>{"".join(summary)}</ul>'
               '<p>The search takes a name (the nearest when none is the same) or an instruction word in hex '
               '(<code>0x1a020020</code>, or a Thumb halfword <code>0x4148</code>): it lists every encoding it '
               'matches.</p>' + (f'<h2>The GPUs\' instructions</h2><ul>{"".join(gpus)}</ul>' if gpus else '')
               + (f'<h2>The 3DS\'s services</h2><ul><li><a href="3ds-ipc/">3DS IPC</a>: the commands of the services\' '
                  f'schemas, word by word ({ctr[0]} interfaces, {ctr[1]} commands)</li></ul>' if ctr else '')
               + (f'<h2>The nn API</h2><ul><li><a href="nn/">nn API</a>: the SDK\'s and the C library\'s functions '
                  f'ScarletNX runs natively, by their symbols, and the kernel\'s SVCs ({nn[0]} hooks in {nn[1]} families, '
                  f'{nn[2]} SVCs)</li></ul>' if nn else '')
               + (f'<h2>Driver bugs</h2><ul><li><a href="driver-bugs/">Driver bugs</a>: the Vulkan drivers known to '
                  f'break an extension or a feature the renderer uses, in one table ({bugs} lines)</li></ul>'
                  if bugs else '')
               + (f'<h2>The Android API</h2><ul><li><a href="android/">Android API</a>: the Java side of the framework '
                  f'ScarletNX gives an Android app ({android[0]} types in {android[1]} packages, {android[2]} members)'
                  f'</li></ul>' if android else ''),
               0, search=arm_search or None))
    print(f'{len(site.written)} files in {out} (ScarletNX {commit[:12]})')
    if parts or site.failures:  # the site is whole, with pages in the failed ones' places
        print(f'gen-manual: made in part: {len(parts)} manual(s) and {len(site.failures)} page(s) or file(s) '
              'failed (above); a page in the place of each says why', file=sys.stderr)
        return 3
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
