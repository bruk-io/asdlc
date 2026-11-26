(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const money = (v) => '$' + (v >= 100 ? Math.round(v).toLocaleString('en-US') : v.toFixed(2));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const PHASE_OF = { Build: 'build', Review: 'review', Fix: 'fix', Verify: 'verify' };
  const PHASE_NAME = { build: 'Build', review: 'Review', fix: 'Fix', verify: 'Verify', other: 'Planning, research, repair' };
  const MODEL_NAME = { sonnet: 'Sonnet 5 · beaver', opus: 'Opus 5 · owl', fable: 'Fable 5.2 · fox' };
  const TOKEN_NAME = { o: 'Output', r: 'Cache read', w: 'Cache write' };
  const SERIES = { build: '--series-a', review: '--series-b', fix: '--series-c', verify: '--series-d', other: '--series-e',
                   sonnet: '--series-b', opus: '--series-a', fable: '--series-c', o: '--series-c', r: '--series-a', w: '--series-b' };
  const HS = 0.12 * BIG, ROW_GAP = FOOT + 4.2, COL_GAP = FOOT + 3.6; // HS: building height per dollar
  const S = { t: 0, playing: false, speed: 420, follow: 'bruk', mode: 'phase', picked: null };
  let D, agents, towers, rows, tMin, tMax, cum, three = null;

  fetch('data.json').then((r) => r.json()).then(init).catch((e) => { $('#err').hidden = false; $('#err').textContent = 'Could not load the data file: ' + e.message; });

  // Button icons: small line drawings in the button's own colour. label() puts one on a button, with words beside it or only as its name.
  const ICONS = {
    play: '<path d="M8 5.5v13l11-6.5z" fill="currentColor"/>', pause: '<path d="M7.5 5.5v13M16.5 5.5v13" stroke-width="3.2"/>',
    replay: '<path d="M5 12a7 7 0 1 0 2.3-5.2"/><path d="M4.5 4.5v4.6h4.6"/>',
    music: '<path d="M9.5 17.5V6l9-2v11.5"/><circle cx="7" cy="17.5" r="2.5" fill="currentColor"/><circle cx="16" cy="15.5" r="2.5" fill="currentColor"/>',
    mute: '<path d="M9.5 17.5V6l9-2v11.5"/><circle cx="7" cy="17.5" r="2.5" fill="currentColor"/><circle cx="16" cy="15.5" r="2.5" fill="currentColor"/><path d="M4 4l16 16" stroke-width="2.6"/>',
    camera: '<path d="M4 8.5h3.2l1.5-2.3h6.6l1.5 2.3H20a1 1 0 0 1 1 1V18a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.500a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.500" r="3.4"/>',
    list: '<path d="M9 6.500h11M9 12h11M9 17.500h11"/><path d="M4.500 6.500h.01M4.500 12h.01M4.500 17.500h.01" stroke-width="3.2"/>',
    bolt: '<path d="M13 3L5.500 13.500H11l-1 7.500 7.500-10.500H12z" fill="currentColor" stroke-width="1.2"/>',
  };
  function label(el, icon, name, words) {
    const key = icon + '|' + name + '|' + (words || ''); if (el.dataset.face === key) return; el.dataset.face = key;
    el.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[icon] + '</svg>' + (words ? '<span>' + esc(words) + '</span>' : '');
    el.setAttribute('aria-label', name); el.title = name; el.classList.toggle('icon', !words);
  }
  function frac(a, t) {
    const c = a.curve;
    if (t <= c[0][0]) return 0;
    if (t >= c[c.length - 1][0]) return 1;
    let i = 1;
    while (c[i][0] < t) i++;
    const p = c[i - 1], q = c[i];
    return p[1] + (q[1] - p[1]) * ((t - p[0]) / Math.max(1, q[0] - p[0]));
  }
  function asleep(a, t) {
    const c = a.curve;
    for (let i = 1; i < c.length; i++) if (c[i][2] && t > c[i - 1][0] + 240 && t < c[i][0]) return true;
    return false;
  }
  const present = (a, t) => t >= a.t0 && t <= a.t1;

  function init(data) {
    D = data; if (D.title) { document.title = D.title; $('#title').textContent = D.title; }
    agents = D.agents.slice().sort((a, b) => a.t0 - b.t0);
    const byId = {};
    towers = D.towers.map((t) => (byId[t.id] = Object.assign({ agents: [], cost: 0 }, t)));
    rows = D.rows;
    agents.forEach((a) => { a.ph = PHASE_OF[a.phase] || 'other'; a.tw = byId[a.tower]; a.tw.agents.push(a); a.tw.cost += a.cost; });
    rows.forEach((r, ri) => r.towers.forEach((id, i) => {
      const t = byId[id]; t.rowName = r.name; t.ri = ri;
      t.x = (i - (r.towers.length - 1) / 2) * COL_GAP; t.z = ri * ROW_GAP;
    }));
    tMin = Math.min(...agents.map((a) => a.t0)) - 600;
    tMax = Math.max(...agents.map((a) => a.t1)) + 600;
    const N = 720; cum = new Float32Array(N + 1);
    for (let i = 0; i <= N; i++) { const t = tMin + (tMax - tMin) * i / N; let s = 0; for (const a of agents) s += a.cost * frac(a, t); cum[i] = s; }
    S.t = tMin;   // the page opens at the start of the story
    buildTable(); setupControls(); setupTimeline();
    try { three = setupThree(); } catch (e) { console.error('The 3D scene could not start:', e && (e.stack || e)); $('#err').hidden = false; $('#hint').hidden = true; }
    const total = agents.reduce((s, a) => s + a.cost, 0), tasks = towers.filter((t) => t.pr).length;
      + money(total) + ' across ' + tasks + ' tasks with pull requests, plus planning and repair work. Times are shown in your local time zone. Source: <a href="' + D.repo + '">' + D.repo.replace('https://', '') + '</a>. Data generated ' + D.generated.slice(0, 10) + '.';
    refresh(true);
    requestAnimationFrame(loop);
  }

