# scarletnx.github.io

The site is plain HTML, so it loads on low-memory devices and old browsers: no JavaScript, no CSS, pages of 16 KB at
most and no element an old browser does not draw. `tools/check-site.py` checks it on every push and pull request.

`manual/` is the ARM manual: the A64 and AArch32 instructions ScarletNX recompiles, laid out as Arm's reference lays
them out (each encoding's diagram, its decode, the operation, and the shared pseudocode they use), made from the Sail
it recompiles them from by `tools/gen-arm-manual.py`. It is the one part with CSS (`manual.css`) and JavaScript (the
search, `search.js`: a name, the nearest names, or the encodings an instruction word matches), from files and small,
and its pages read without them. Do not edit it: `.github/workflows/manual.yml` makes it again every day from
ScarletNX's `main` (or when run by hand) and commits it when it changed. To make it from a checkout:

```sh
python3 tools/gen-arm-manual.py ~/ScarletNX
```

`tests/check-manual.sh` makes it from `tests/sail`, a few instructions cut from that Sail.
