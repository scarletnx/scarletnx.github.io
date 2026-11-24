# scarletnx.github.io

The site is plain HTML, so it loads on low-memory devices and old browsers: no JavaScript, no CSS, pages of 16 KB at
most and no element an old browser does not draw. `tools/check-site.py` checks it on every push and pull request.

`manual/` is the ISA manuals: the ARM instructions ScarletNX recompiles (A64 and AArch32, `manual/`) and the GPU
instructions it translates (Maxwell's SM53, `manual/sm53/`, and Ampere's SM86, `manual/sm86/`), laid out as Arm's
reference lays them out (each encoding's diagram, its decode, the operation, and the shared pseudocode they use),
made from ScarletNX's Sail by `tools/gen-manual.py` (the GPUs' encodings from its `sm53.decode` and `sm86.decode`),
and the NVN API (`manual/nvn/`): every function of ScarletNX's `nvn.hook` with its signature and handler, the types
and enums of its `nvn.h`, each format's Vulkan equivalent (its `vk/format.c`), and what only Switch 2's drivers have
marked, by `tools/manual/nvn-drivers.txt` (the drivers' procedure tables, which `tools/nvn_hash.py --json` reads). It
is the one part with CSS (`manual.css`) and JavaScript (the search, `search.js`: a name, the nearest names, or the
encodings an instruction word matches), from files and small, and its pages read without them. Do not edit it:
`.github/workflows/manual.yml` makes it again every day from ScarletNX's `main` (or when run by hand) and commits it
when it changed. To make it from a checkout:

```sh
python3 tools/gen-manual.py ~/ScarletNX
```

`tests/check-manual.sh` makes it from `tests/sail`, a few instructions cut from that Sail.

`manual/cs-book/` is a book, *From Derivatives to Attention*: mathematics for programmers, from derivatives, ODEs
and integrals to what the paper RefineKV (arXiv:2611.28171) needs (linear algebra, norms and inequalities, convexity,
probability and statistics, floating point, softmax, attention and the KV cache), with a C program for each idea and
the works it draws on in `refs.html`. It is written by hand, not generated. Its pages may be 64 KB, have inline svg
figures, and load its stylesheet (`book.css`) and MathJax 3.2.2 from jsDelivr, which typesets their TeX formulas:
`check-site.py` allows these for `manual/cs-book/` only, and `tests/check-site.sh` checks that it does.
