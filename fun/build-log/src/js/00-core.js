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
  const S = { t: 0, playing: false, speed: 420, follow: 'work', mode: 'phase', picked: null };
  let D, agents, towers, rows, tMin, tMax, cum, three = null;

  fetch('data.json').then((r) => r.json()).then(init).catch((e) => { $('#err').hidden = false; $('#err').textContent = 'Could not load the data file: ' + e.message; });

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
    S.t = tMax;
    buildTable(); setupControls(); setupTimeline();
    try { three = setupThree(); } catch (e) { console.error('The 3D scene could not start:', e && (e.stack || e)); $('#err').hidden = false; $('#hint').hidden = true; }
    const total = agents.reduce((s, a) => s + a.cost, 0), tasks = towers.filter((t) => t.pr).length;
      + money(total) + ' across ' + tasks + ' tasks with pull requests, plus planning and repair work. Times are shown in your local time zone. Source: <a href="' + D.repo + '">' + D.repo.replace('https://', '') + '</a>. Data generated ' + D.generated.slice(0, 10) + '.';
    refresh(true);
    requestAnimationFrame(loop);
  }

