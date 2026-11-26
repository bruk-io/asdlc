  /* ---------- timeline ---------- */
  let laneCount = 0, quiet = [];
  function setupTimeline() {
    const ends = [];
    agents.forEach((a) => { let i = ends.findIndex((e) => e <= a.t0); if (i < 0) { i = ends.length; ends.push(0); } ends[i] = a.t1 + 90; a.lane = i; });
    laneCount = ends.length;
    const marks = []; agents.filter((a) => a.kind !== 'Main').forEach((a) => { let s = a.t0; a.curve.forEach((c, i) => { if (c[2]) { marks.push([s, a.curve[i - 1][0]]); s = c[0]; } }); marks.push([s, a.t1]); });
    marks.sort((p, q) => p[0] - q[0]); let end = tMin; quiet = [];
    for (const [s, e] of marks) { if (s - end > 1500) quiet.push([end, s]); end = Math.max(end, e); }
    const cv = $('#tl'); let drag = false;
    const at = (ev) => { const r = cv.getBoundingClientRect(); return tMin + (tMax - tMin) * Math.min(1, Math.max(0, (ev.clientX - r.left - 8) / (r.width - 16))); };
    cv.addEventListener('pointerdown', (ev) => { drag = true; cv.setPointerCapture(ev.pointerId); S.t = at(ev); refresh(); });
    const tt = $('#tl-tip');
    cv.addEventListener('pointermove', (ev) => {
      const t = at(ev), r = cv.getBoundingClientRect();
      if (drag) { S.t = t; refresh(); }
      const i = Math.round((t - tMin) / (tMax - tMin) * (cum.length - 1)), d = new Date(t * 1000), px = (tMax - tMin) / r.width * 5;
      const near = D.prs.filter((p) => Math.abs(p.t - t) < px).map((p) => '#' + p.n + ' ' + esc(p.title.replace(/^Task: /, ''))).slice(0, 3);
      tt.innerHTML = '<b>' + d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0') + '</b>'
        + money(cum[Math.max(0, Math.min(cum.length - 1, i))]) + ' <span>spent · ' + agents.filter((a) => present(a, t) && !asleep(a, t) && a.kind !== 'Main').length + ' agents awake</span>'
        + (near.length ? '<br><span>Merged: ' + near.join('; ') + '</span>' : '');
      tt.hidden = false; tt.style.left = Math.max(0, Math.min(r.width - 290, ev.clientX - r.left + 12)) + 'px'; tt.style.top = '-8px'; tt.style.transform = 'translateY(-100%)';
    });
    cv.addEventListener('pointerleave', () => { tt.hidden = true; });
    cv.addEventListener('pointerup', () => { drag = false; });
    new ResizeObserver(drawTimeline).observe(cv);
    const longest = quiet.slice().sort((p, q) => (q[1] - q[0]) - (p[1] - p[0]))[0];
    $('#tl-note').textContent = longest ? 'Longest quiet stretch: ' + ((longest[1] - longest[0]) / 3600).toFixed(1) + ' h (usage limit)' : '';
  }
  function drawTimeline() {
    const cv = $('#tl'); if (!agents) return;
    const dpr = Math.min(2, devicePixelRatio || 1), W = cv.clientWidth, H = cv.clientHeight;
    if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const X = (t) => 8 + (W - 16) * (t - tMin) / (tMax - tMin), costH = Math.round(H * 0.3), laneTop = costH + 20, laneH = Math.max(2, Math.min(4, (H - laneTop - 22) / laneCount));
    const muted = css('--ui-text-muted'), border = css('--ui-border'), text = css('--ui-text');
    g.fillStyle = css('--ui-surface-recessed'); for (const [s, e] of quiet) g.fillRect(X(s), 0, X(e) - X(s), H - 18);
    g.strokeStyle = border; g.lineWidth = 1; g.font = '11px ui-monospace, Menlo, Consolas, monospace'; g.fillStyle = muted; g.textBaseline = 'alphabetic';
    const h0 = new Date(tMin * 1000); h0.setMinutes(0, 0, 0);
    for (let t = h0.getTime() / 1000; t < tMax; t += 3600) {
      if (t < tMin) continue; const d = new Date(t * 1000), x = Math.round(X(t)) + 0.5, six = d.getHours() % 6 === 0;
      if (six) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H - 18); g.stroke(); g.textAlign = x < 40 ? 'left' : x > W - 40 ? 'right' : 'center'; g.fillText(d.getHours() === 0 ? d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : String(d.getHours()).padStart(2, '0') + ':00', x, H - 4); }
    }
    const max = cum[cum.length - 1] || 1;
    g.beginPath(); g.moveTo(X(tMin), costH); for (let i = 0; i < cum.length; i++) g.lineTo(X(tMin + (tMax - tMin) * i / (cum.length - 1)), costH - (costH - 6) * cum[i] / max); g.lineTo(X(tMax), costH); g.closePath();
    g.globalAlpha = 0.18; g.fillStyle = text; g.fill(); g.globalAlpha = 1;
    g.beginPath(); for (let i = 0; i < cum.length; i++) { const x = X(tMin + (tMax - tMin) * i / (cum.length - 1)), y = costH - (costH - 6) * cum[i] / max; i ? g.lineTo(x, y) : g.moveTo(x, y); } g.strokeStyle = text; g.lineWidth = 2; g.stroke();
    g.textAlign = 'left'; g.fillStyle = muted; g.fillText('SPENT SO FAR', 10, 12); g.textAlign = 'right'; g.fillText(money(max), W - 10, 12);
    g.fillStyle = css('--ui-success');
    for (const p of D.prs) { const x = X(p.t); g.fillRect(Math.round(x) - 1, costH + 6, 2, p.task ? 7 : 11); }
    
    for (const a of agents) { g.fillStyle = segColour(a, 'r'); const x = X(a.t0); g.fillRect(x, laneTop + a.lane * laneH, Math.max(1.5, X(a.t1) - x), Math.max(1, laneH - 1)); }
    const px = Math.round(X(S.t)) + 0.5; g.strokeStyle = css('--ui-primary'); g.lineWidth = 2; g.beginPath(); g.moveTo(px, 0); g.lineTo(px, H - 18); g.stroke();
    g.fillStyle = css('--ui-primary'); g.beginPath(); g.moveTo(px - 5, 0); g.lineTo(px + 5, 0); g.lineTo(px, 7); g.closePath(); g.fill();
  }

