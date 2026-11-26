  /* ---------- panels ---------- */
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function buildTable() {
    const body = $('#table tbody');
    body.innerHTML = towers.slice().sort((a, b) => b.cost - a.cost).map((t) => {
      const hrs = t.agents.reduce((s, a) => s + (a.t1 - a.t0), 0) / 3600;
      return '<tr class="pick" data-id="' + esc(t.id) + '"><td>' + esc(t.rowName) + '</td><td class="t">' + esc(t.title) + '</td><td class="n">' + money(t.cost) + '</td><td class="n">' + t.agents.length + '</td><td class="n">' + hrs.toFixed(1) + '</td><td>'
        + (t.pr ? '<a href="' + esc(t.url) + '">#' + t.pr + '</a> ' + (t.merged ? 'merged' : 'open') : '') + '</td></tr>';
    }).join('');
    body.addEventListener('click', (ev) => { const tr = ev.target.closest('tr.pick'); if (tr && !ev.target.closest('a')) pick(towers.find((t) => t.id === tr.dataset.id), true); });
  }
  function pick(t, fly) {
    S.picked = t;
    $('#detail').hidden = !t; if (!t) return;
    $('#tag').innerHTML = esc(t.title.length > 34 ? t.title.slice(0, 33) + '…' : t.title) + ' · <b>' + money(t.cost) + '</b>';
    if (fly && three) three.flyTo(t);
    const by = {}; t.agents.forEach((a) => { by[a.ph] = (by[a.ph] || 0) + a.cost; });
    const tok = t.agents.reduce((s, a) => ({ o: s.o + a.co, r: s.r + a.cr, w: s.w + a.cw }), { o: 0, r: 0, w: 0 });
    const bar = (obj, keys) => '<div class="split">' + keys.filter((k) => obj[k]).map((k) => '<i title="' + k + '" style="flex:' + obj[k] + ';background:var(' + SERIES[k] + ')"></i>').join('') + '</div>';
    const list = (obj, names, keys) => keys.filter((k) => obj[k]).map((k) => names[k] + ' ' + money(obj[k])).join(' · ');
    const pk = ['build', 'review', 'fix', 'verify', 'other'], tk = ['r', 'w', 'o'];
    $('#detail').innerHTML = '<button class="close" type="button" id="close-detail" aria-label="Close">×</button><h2>' + esc(t.rowName) + '</h2><h3>' + esc(t.title) + '</h3>'
      + '<dl class="kv"><dt>Cost</dt><dd>' + money(t.cost) + '</dd><dt>Agent runs</dt><dd>' + t.agents.length + '</dd><dt>Pull request</dt><dd>' + (t.pr ? '<a href="' + esc(t.url) + '">#' + t.pr + '</a> ' + (t.merged ? 'merged' : 'open') : 'none') + '</dd></dl>'
      + bar(by, pk) + '<p class="foot" style="margin-top:6px">' + list(by, PHASE_NAME, pk) + '</p>' + bar(tok, tk) + '<p class="foot" style="margin-top:6px">' + list(tok, TOKEN_NAME, tk) + '</p>';
  }

