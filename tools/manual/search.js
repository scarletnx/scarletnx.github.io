// SPDX-License-Identifier: GPL-3.0-or-later
// The ISA manuals' search (tools/gen-manual.py): a name, or the nearest names when none is the same, or an
// instruction word in hex and every encoding it matches. The pages read without it: it only adds the box.
// The data (each manual's data.js, data-load) loads when the box is first used, not with the page.
(function () {
    var box = document.getElementById('search'), rows = null, loading = 0;
    if (!box || !box.appendChild || !document.createElement || !box.getAttribute) return;
    var root = box.getAttribute('data-root') || '', load = (box.getAttribute('data-load') || '').split(' ');

    // the data's scripts, one after the other, then the search
    function fetchData() {
        if (rows || loading) return;
        loading = 1;
        status.innerHTML = 'Loading\u2026';
        (function next(k) {
            if (k == load.length || !load[k]) { rows = window.ARM || []; status.innerHTML = ''; run(); return; }
            var s = document.createElement('script');
            s.src = load[k];
            s.onload = function () { next(k + 1); };
            s.onerror = function () { status.innerHTML = 'The search\'s data did not load.'; };
            document.getElementsByTagName('head')[0].appendChild(s);
        })(0);
    }
    var input = document.createElement('input'), status = document.createElement('p'), list = document.createElement('ul');
    input.type = 'search';
    input.placeholder = box.getAttribute('data-placeholder') || 'Search: a name or an instruction word in hex';
    box.appendChild(input); box.appendChild(status); box.appendChild(list);

    function mnemonic(title) { return title.split(' ')[0].toUpperCase(); }

    function distance(a, b) {
        var prev = [], cur, i, j;
        for (j = 0; j <= b.length; j++) prev[j] = j;
        for (i = 1; i <= a.length; i++) {
            cur = [i];
            for (j = 1; j <= b.length; j++)
                cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a.charAt(i - 1) == b.charAt(j - 1) ? 0 : 1));
            prev = cur;
        }
        return prev[b.length];
    }

    // An instruction word: 0x and hex digits, or exactly 4, 8, 16 or 32 of them. An ARM word is its value; a GPU's
    // the 16-bit opcode the encodings' file decodes: SM53's bits 63:48, SM86's 15:0 (of the low 64 bits, the last)
    function word(q) {
        var m = /^(0x)?([0-9a-f]+)$/i.exec(q.replace(/[\s_]/g, ''));
        if (!m) return null;
        var h = m[2], n = h.length;
        if (!m[1] && n != 4 && n != 8 && n != 16 && n != 32) return null;
        return {
            arm: n <= 8 ? parseInt(h, 16) : -1,
            SM53: n == 16 ? parseInt(h.substr(0, 4), 16) : (m[1] && n <= 4 ? parseInt(h, 16) : -1),
            SM86: n == 16 || n == 32 ? parseInt(h.substr(n - 4), 16) : (m[1] && n <= 4 ? parseInt(h, 16) : -1)
        };
    }

    function matches(r, w) {
        if (!r[4]) return false; // a name alone (the NVN API's)
        var op = r[2] == 'SM53' || r[2] == 'SM86' ? w[r[2]] : w.arm;
        if (op < 0) return false;
        if (r[2] == 'T16' && op > 0xffff) return false;
        var mask = parseInt(r[4], 16), value = parseInt(r[5], 16), exmask = parseInt(r[6], 16);
        if (((op & mask) >>> 0) != value) return false;
        return !exmask || ((op & exmask) >>> 0) != parseInt(r[7], 16);
    }

    function item(r, decodes) {
        var li = document.createElement('li'), a = document.createElement('a');
        a.href = root + r[1];
        a.appendChild(document.createTextNode(r[0]));
        li.appendChild(a);
        li.appendChild(document.createTextNode(' ' + r[2] + ', ' + r[3] + (decodes ? ': the ' + r[2] + ' decoder takes this one' : '')));
        return li;
    }

    function run() {
        if (!rows) { fetchData(); return; }
        var q = input.value.replace(/^\s+|\s+$/g, ''), found = [], i, s, op;
        while (list.firstChild) list.removeChild(list.firstChild);
        status.innerHTML = '';
        if (!q) return;
        op = word(q);
        // the encodings a word matches, each instruction set's in the order its decoder tries them: the first decodes it
        if (op) for (i = 0; i < rows.length; i++) if (matches(rows[i], op)) found.push([-1, rows[i]]);
        found.sort(function (a, b) { return a[1][2] < b[1][2] ? -1 : a[1][2] > b[1][2] ? 1 : a[1][8] - b[1][8]; });
        var first = {};
        for (i = 0; i < found.length; i++) if (!first[found[i][1][2]]) first[found[i][1][2]] = found[i][1];
        var words_found = found.length, Q = q.toUpperCase(), best = 1e9;
        for (i = 0; i < rows.length; i++) {
            var t = rows[i][0].toUpperCase(), m = mnemonic(t);
            if (m == Q) s = 0;
            else if (m.indexOf(Q) == 0) s = 1;
            else if (t.indexOf(Q) >= 0 || (rows[i][3] || '').toUpperCase().indexOf(Q) >= 0) s = 2;
            else s = 3 + distance(Q, m);
            if (s < best) best = s;
            found.push([s, rows[i]]);
        }
        found = found.slice(0, words_found).concat(found.slice(words_found).sort(function (a, b) {
            return a[0] - b[0] || (a[1][0] < b[1][0] ? -1 : a[1][0] > b[1][0] ? 1 : 0); }));
        var shown = 0, words = 0, seen = {};
        for (i = 0; i < found.length && shown < 30; i++) {
            if (found[i][0] > 2 && (words || found[i][0] > best + 1)) break;
            if (seen[found[i][1][1] + found[i][0]]) continue;
            seen[found[i][1][1] + found[i][0]] = 1;
            if (found[i][0] < 0) words++;
            list.appendChild(item(found[i][1], found[i][0] < 0 && first[found[i][1][2]] == found[i][1]));
            shown++;
        }
        status.appendChild(document.createTextNode(
            op ? (words ? words + ' encoding(s) match the word' + (shown > words ? ', then the names like it' : '')
                             : 'No encoding here matches the word; the names like it:')
                    : best > 2 ? 'No name is the same; the nearest:' : ''));
    }

    if (input.addEventListener) {
        input.addEventListener('input', run, false);
        input.addEventListener('focus', fetchData, false);
    } else input.onkeyup = run;
    var q = /[?&]q=([^&]*)/.exec(location.search);
    if (q) { input.value = decodeURIComponent(q[1].replace(/\+/g, ' ')); run(); }
})();
