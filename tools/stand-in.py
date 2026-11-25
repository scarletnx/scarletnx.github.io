#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A page in the place of a part of the site that could not be made (tools/build-site.sh).

    tools/stand-in.py SITE PART WHY     PART is a folder of SITE (manual/snx): it is emptied, and its index.html says
                                        that it could not be made, and why. PART manual/ alone keeps its folders,
                                        which are the other manuals.

The page is plain HTML, as any page of the site may be: no CSS, no script.
"""
import html
import os
import shutil
import sys


def stand_in(site, part, why):
    part = part.strip('/')
    folder = os.path.join(site, part)
    if part != 'manual':
        shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder, exist_ok=True)
    up = '../' * (part.count('/') + 1)
    with open(os.path.join(folder, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                f'<title>Not made - ScarletNX</title>\n</head>\n<body>\n<p><a href="{up}">ScarletNX</a></p>\n'
                f'<h1>Not made this time</h1>\n<p>This part of the site ({html.escape(part)}/) could not be made from '
                f'its sources: {html.escape(why)}. The rest of the site was made; this page is in its place until '
                'the next build makes it again.</p>\n</body>\n</html>\n')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__.strip())
    stand_in(*sys.argv[1:])
