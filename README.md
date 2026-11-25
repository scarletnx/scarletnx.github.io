# scarletnx.github.io

The site is plain HTML, so it loads on low-memory devices and old browsers: no JavaScript, no CSS, pages of 16 KB at
most and no element an old browser does not draw. `tools/check-site.py` checks it on every push and pull request.

The repository holds the site's sources; the pages are made from them. `tools/build-site.sh` makes the whole site
into `_site/` (not committed) and checks it, and `.github/workflows/site.yml` runs it on every push and pull request
and deploys it to GitHub Pages from `main`, and again every day for ScarletNX's changes:

```sh
sh tools/build-site.sh ~/ScarletNX        # _site/, as Pages serves it
```

`manual/` is the ISA manuals: the ARM instructions ScarletNX recompiles (A64 and AArch32, `manual/`) and the GPU
instructions it translates (Maxwell's SM53, `manual/sm53/`, Ampere's SM86, `manual/sm86/`, the 3DS's PICA200,
`manual/pica/`, and the Vita's USSE, `manual/usse/`), laid out as Arm's reference lays them out (each encoding's
diagram, its decode, the operation, and the shared pseudocode they use), made from ScarletNX's Sail by
`tools/gen-manual.py` (the GPUs' encodings from its `sm53.decode`, `sm86.decode`, `pica.decode` and `usse.decode`),
and the NVN API (`manual/nvn/`): every function of ScarletNX's `nvn.hook` with its signature, doc comment and handler, the types
and enums of its `nvn.h`, each format's Vulkan equivalent (its `vk/format.c`), and what only Switch 2's drivers have
marked, by `tools/manual/nvn-drivers.txt` (the drivers' procedure tables, which `tools/nvn_hash.py --json` reads),
and the 3DS IPC (`manual/3ds-ipc/`): the commands of ScarletNX's `src/3ds/services/*.swipc`, each request's and
response's words as `swipc --ctr`'s dispatcher reads and writes them, with the handler, and the Android API
(`manual/android/`): the Java side of ScarletNX's `src/android/framework` as javadoc reads it, each public and
protected type and member with its declaration, doc comment and the source's groups, and the nn API (`manual/nn/`):
the SDK's and C library's functions ScarletNX hooks (`src/nx/hle/hook/hooks.hook`, `src/nx/nn/*.hook`) by family
and namespace, C++ symbols demangled, with their handlers, and the kernel's SVCs (`src/nx/hle/svc/hos.svc`) in a
table by number with each one's registers in both ABIs, and the driver bugs (`manual/driver-bugs/`): ScarletNX's
`src/common/gpu/vk/extension_bans.txt` as one table that its headers sort (`sort.js`), a page up to 128 KB. It is
the one part with CSS (`manual.css`) and JavaScript (the search, `search.js`: a name, the nearest names, or the
encodings an instruction word matches), from files and small, and its pages read without them. It is made, by the
site's workflow from ScarletNX's `main`, or from a checkout (into `_site/manual/`):

```sh
python3 tools/gen-manual.py ~/ScarletNX
```

`tests/check-manual.sh` makes it from `tests/sail`, a few instructions cut from that Sail.

`manual/snx/` is ScarletNX's documentation, its `docs/` made into pages by `tools/gen-docs.py` from ScarletNX's
`main` (`docs/README.md`, the documents' index, is its first page). A document too long for a 16 KB page is cut at
its sections, then its subsections, then between its blocks, and its links go to the page that has the heading
they name; links out of `docs/` go to the file in ScarletNX's repository at that commit. It reads the Markdown the
documents use (headings, lists, fenced code, GitHub's tables, links, emphasis); other HTML in them is text.
`tests/check-docs.sh` makes a few documents written for it and checks the pages.

`manual/cs-book/` is a book, *From Derivatives to Attention*: mathematics for programmers, from derivatives, ODEs
and integrals to what the paper RefineKV (arXiv:2611.28171) needs (linear algebra, norms and inequalities, convexity,
probability and statistics, floating point, softmax, attention and the KV cache), with C programs where they show something,
and the works it draws on in `refs.html`. Its sources are `book/`: each page's body (`index.html`, `refs.html`, a chapter
`NN-name.html`) and the programs a chapter shows (`NN-name/NAME.c`) beside what they printed (`NAME.out`).
`tools/gen-book.py` makes the pages (into `_site/manual/cs-book/`): it writes each head and the chapters' links to
one another, and puts each program where its chapter has `<!--prog NAME.c-->` (or only its output, `<!--out
NAME.c-->`), after compiling it (C99, no warnings) and running it: what it prints must be its `.out`, which the text
quotes, or the book is not made. A program whose output depends on the machine (a timing, `rand()`, a C library's
last digits) is marked `recorded`: compiled, not run, its `.out` what it printed on the machine the page names.
`tests/check-book.sh` checks the book is made and that a wrong `.out` stops it. Its pages may be 64 KB, have inline
svg figures, and load its stylesheet (`book.css`) and MathJax 3.2.2 from jsDelivr, which typesets their TeX
formulas: `check-site.py` allows these for `manual/cs-book/` only, and `tests/check-site.sh` checks that it does.
