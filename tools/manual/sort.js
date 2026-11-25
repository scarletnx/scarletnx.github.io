// SPDX-License-Identifier: GPL-3.0-or-later
// The driver bugs' table (tools/gen-manual.py), sorted by a column: a header's button sorts by it, again the other
// way. Numbers inside the text sort as numbers. Without it the table reads in the file's order.
(function () {
    var t = document.getElementById('bugs');
    if (!t || !t.tHead || !t.tBodies || !document.createElement) return;
    var heads = t.tHead.rows[0].cells, body = t.tBodies[0], by = -1, down = false, i;

    function text(row, k) {
        var c = row.cells[k];
        return c ? (c.getAttribute('data-sort') || c.textContent || c.innerText || '') : '';
    }

    function compare(a, b) {
        if (a.localeCompare) return a.localeCompare(b, undefined, {numeric: true, sensitivity: 'base'});
        return a < b ? -1 : a > b ? 1 : 0;
    }

    function sort(k) {
        var rows = [], j;
        down = by == k ? !down : false;
        by = k;
        for (j = 0; j < body.rows.length; j++) rows.push([text(body.rows[j], k), j, body.rows[j]]);
        rows.sort(function (a, b) { return (down ? -1 : 1) * compare(a[0], b[0]) || a[1] - b[1]; });
        for (j = 0; j < rows.length; j++) body.appendChild(rows[j][2]);
        for (j = 0; j < heads.length; j++)
            heads[j].setAttribute('aria-sort', j == k ? (down ? 'descending' : 'ascending') : 'none');
    }

    for (i = 0; i < heads.length; i++) (function (k) {
        var b = document.createElement('button');
        b.type = 'button';
        while (heads[k].firstChild) b.appendChild(heads[k].firstChild);
        heads[k].appendChild(b);
        b.onclick = function () { sort(k); };
    })(i);
})();
