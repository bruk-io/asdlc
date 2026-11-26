  /* ---------- controls and clock ---------- */
  function setupControls() {
    const group = (id, fn) => $(id).addEventListener('click', (ev) => { const b = ev.target.closest('button'); if (!b) return; $(id).querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', x === b)); fn(b.dataset.v); });
    // The speed scale runs from 1 to 50 minutes of the build per second of viewing. It is logarithmic, so the slow end has as much room as the fast end.
    { const el = $('#speed'), out = $('#speed-out'), LO = 1, HI = 50, mins = (v) => LO * Math.pow(HI / LO, v / 100);
      const set = (ev) => { const m = ev ? mins(+el.value) : S.speed / 60; S.speed = m * 60; const text = (m < 10 ? m.toFixed(1).replace(/\.0$/, '') : Math.round(m)) + ' min/s'; out.textContent = text; el.setAttribute('aria-valuetext', text + ' of the build per second'); el.style.setProperty('--fill', el.value + '%'); };
      el.value = Math.round(100 * Math.log(S.speed / 60 / LO) / Math.log(HI / LO)); el.addEventListener('input', set); set(); }
    document.addEventListener('keydown', (ev) => {
      const tag = (ev.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'select' || tag === 'textarea' || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      const onButton = tag === 'button' || tag === 'a' || tag === 'summary', k = ev.key.toLowerCase(), big = ev.shiftKey ? 3600 : 600;
      let used = true;
      if (k === ' ' && !onButton) $('#play').click();
      else if (k === 'arrowleft') { S.playing = false; S.t = Math.max(tMin, S.t - big); refresh(); }
      else if (k === 'arrowright') { S.playing = false; S.t = Math.min(tMax, S.t + big); refresh(); }
      else if (k === 'home') { S.playing = false; S.t = tMin; refresh(); }
      else if (k === 'end') { S.playing = false; S.t = tMax; refresh(); }
      else if (!three) used = false;
      else if (k === 'w') three.nudge(0, 1); else if (k === 's') three.nudge(0, -1);
      else if (k === 'a') three.nudge(-1, 0); else if (k === 'd') three.nudge(1, 0);
      else if (k === 'q') three.nudge(0, 0, 0.12); else if (k === 'e') three.nudge(0, 0, -0.12);
      else if (k === '+' || k === '=') three.nudge(0, 0, 0, 0.88); else if (k === '-' || k === '_') three.nudge(0, 0, 0, 1.14);
      else if (k === 'f') $('#cam').click();
      else used = false;
      if (used) ev.preventDefault();
    });
    // The two panels in the corner: opening one closes the other. The selected-building card closes from its own button.
    // The camera button: each press moves on to the next thing to follow (the work, Bruk, nothing) and reframes the view on it.
    { const names = { work: 'The Work', bruk: (D.owner && D.owner.name) || 'You', off: 'Free' }, order = ['work', 'bruk', 'off'], btn = $('#cam');
      btn.addEventListener('click', () => { S.follow = order[(order.indexOf(S.follow) + 1) % 3] || 'work'; btn.textContent = 'Camera: ' + names[S.follow]; btn.setAttribute('aria-pressed', S.follow !== 'off'); if (three && S.follow !== 'off') three.reframe(); }); }
    const panels = { 'open-list': 'drawer' };
    for (const id in panels) $('#' + id).addEventListener('click', () => { for (const other in panels) { const open = other === id && $('#' + panels[other]).hidden; $('#' + panels[other]).hidden = !open; $('#' + other).setAttribute('aria-expanded', open); } });
    $('#detail').addEventListener('click', (ev) => { if (ev.target.closest('#close-detail')) pick(null, false); });
    $('#stage').addEventListener('pointerdown', () => $('#hint').classList.add('gone'), { once: true });
    const awakeAt = (t) => agents.filter((a) => present(a, t) && !asleep(a, t) && a.kind !== 'Main');
    const jumpBusy = () => {
      let best = tMin, n = -1;
      for (let t = tMin; t < tMax; t += 120) { const k = awakeAt(t).length; if (k > n) { n = k; best = t; } }
      S.playing = false; S.t = best; refresh();
      const live = awakeAt(best); if (three && live.length) three.flyTo(live[Math.floor(live.length / 2)].tw);
    };
    $('#busy').addEventListener('click', jumpBusy);
    if (location.hash === '#busiest') setTimeout(jumpBusy, 0);
    // #at=0.4 starts with the playhead that fraction of the way along, for the screenshot tool. It can follow a #cam=... setting after an ampersand.
    { const m = /at=([\d.]+)/.exec(location.hash); if (m) S.t = tMin + (tMax - tMin) * Math.min(1, +m[1]); }
    $('#play').addEventListener('click', () => {
      if (S.playing) S.playing = false; else { if (S.t >= tMax - 1) S.t = tMin; S.playing = true; }
      refresh();
    });
  }
  function refresh() {
    const t = S.t, i = Math.min(cum.length - 1, Math.max(0, Math.round((t - tMin) / (tMax - tMin) * (cum.length - 1))));
    const d = new Date(t * 1000);
    $('#r-clock').textContent = d.toLocaleDateString(undefined, { day: '2-digit', month: 'short' }).toUpperCase() + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    $('#r-cost').textContent = '$' + Math.round(cum[i]);
    $('#r-live').textContent = agents.filter((a) => present(a, t) && !asleep(a, t) && a.kind !== 'Main').length;
    $('#r-merged').textContent = D.prs.filter((p) => p.task && p.t <= t).length;
    $('#play').textContent = S.playing ? 'Pause' : (t >= tMax - 1 ? 'Replay' : 'Play');
    const act = {}; agents.forEach((a) => { if (a.kind !== 'Main' && present(a, t) && !asleep(a, t)) (act[a.tw.rowName] = act[a.tw.rowName] || new Set()).add(a.tw.id); });
    const names = Object.keys(act);
    $('#now').textContent = names.length ? names.map((n) => n + ' · ' + act[n].size + (act[n].size === 1 ? ' tower' : ' towers')).join('   ') : (t >= tMax - 1 ? '' : 'Quiet');
    drawTimeline();
  }
  let last = 0, tick = 0;
  function loop(now) {
    const dt = Math.min(0.1, (now - last) / 1000 || 0); last = now;
    if (S.playing) {
      let rate = S.speed;
      S.t = Math.min(tMax, S.t + rate * dt);
      if (S.t >= tMax) S.playing = false;
      if (now - tick > 83) { tick = now; refresh(); }
    }
    if (three) three.update(now);
    requestAnimationFrame(loop);
  }
})();

