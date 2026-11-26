// One agent run: a round little animal. The species is the model, the prop is the job.
ASSETS.critter = {
  title: 'Critter',
  controls: { model: ['sonnet', 'opus', 'fable'], job: ['build', 'review', 'fix', 'verify', 'other'], mode: ['work', 'walk', 'idle', 'sleep'], mood: ['calm', 'grumpy'], action: ['none', 'read', 'write', 'git', 'build', 'shell', 'web', 'delegate', 'skill', 'report', 'wait'] },
  // The data's one-letter tool kinds, as the actions a critter can act out.
  KIND: { r: 'read', w: 'write', g: 'git', b: 'build', s: 'shell', n: 'web', d: 'delegate', k: 'skill', o: 'report', z: 'wait' },
  SPECIES: { sonnet: 'beaver', opus: 'owl', fable: 'fox' }, BODY: { sonnet: '--series-b', opus: '--series-a', fable: '--series-c' },
  build(kit, o) {
    const { sph, cone, tor, cyl, box, hat } = kit.geo, model = o.model || 'sonnet', job = o.job || 'build', body = ASSETS.critter.BODY[model], ink = '@ink', pale = '--w-cream';
    const g = new THREE.Group(), p = (geo, m, sx, sy, sz, x, y, z) => kit.mesh(geo, m, sx, sy, sz, x, y, z);
    g.add(p(sph, body, 0.3, 0.33, 0.28, 0, 0.35, 0), p(sph, pale, 0.21, 0.23, 0.1, 0, 0.32, 0.21), p(sph, body, 0.08, 0.15, 0.09, -0.3, 0.4, 0.04), p(sph, body, 0.08, 0.15, 0.09, 0.3, 0.4, 0.04));
    const head = new THREE.Group(); head.position.y = 0.88; g.add(head);
    head.add(p(sph, body, 0.35, 0.31, 0.31, 0, 0, 0), p(sph, ink, 0.042, 0.062, 0.03, -0.13, 0.03, 0.29), p(sph, ink, 0.042, 0.062, 0.03, 0.13, 0.03, 0.29),
      p(sph, pale, 0.014, 0.02, 0.01, -0.12, 0.055, 0.315), p(sph, pale, 0.014, 0.02, 0.01, 0.14, 0.055, 0.315), p(sph, '--w-blush', 0.055, 0.035, 0.02, -0.22, -0.06, 0.25), p(sph, '--w-blush', 0.055, 0.035, 0.02, 0.22, -0.06, 0.25));
    if (model === 'sonnet') { // beaver: round ears, buck teeth, flat tail
      head.add(p(sph, body, 0.1, 0.1, 0.06, -0.26, 0.25, 0), p(sph, body, 0.1, 0.1, 0.06, 0.26, 0.25, 0), p(sph, pale, 0.12, 0.09, 0.07, 0, -0.08, 0.28), p(sph, ink, 0.05, 0.036, 0.03, 0, -0.03, 0.335), p(box, pale, 0.07, 0.07, 0.02, 0, -0.14, 0.32));
      g.add(p(sph, ink, 0.17, 0.045, 0.26, 0, 0.12, -0.36));
    } else if (model === 'opus') { // owl: ear tufts, big eye discs, beak
      head.add(p(cone, body, 0.08, 0.2, 0.08, -0.22, 0.3, 0), p(cone, body, 0.08, 0.2, 0.08, 0.22, 0.3, 0), p(sph, pale, 0.12, 0.12, 0.03, -0.13, 0.03, 0.27), p(sph, pale, 0.12, 0.12, 0.03, 0.13, 0.03, 0.27));
      const beak = p(cone, '--w-dome', 0.05, 0.11, 0.05, 0, -0.07, 0.33); beak.rotation.x = Math.PI / 2; head.add(beak);
    } else { // fox: pointed ears, snout, bushy tail with a pale tip
      head.add(p(cone, body, 0.11, 0.28, 0.09, -0.2, 0.33, 0), p(cone, body, 0.11, 0.28, 0.09, 0.2, 0.33, 0), p(cone, pale, 0.05, 0.13, 0.04, -0.2, 0.31, 0.03), p(cone, pale, 0.05, 0.13, 0.04, 0.2, 0.31, 0.03));
      const snout = p(cone, pale, 0.11, 0.2, 0.1, 0, -0.07, 0.33); snout.rotation.x = Math.PI / 2; head.add(snout, p(sph, ink, 0.04, 0.032, 0.03, 0, -0.06, 0.43));
      const tail = p(cone, body, 0.14, 0.5, 0.14, 0, 0.36, -0.42); tail.rotation.x = -Math.PI / 2.6; g.add(tail, p(sph, pale, 0.09, 0.09, 0.09, 0, 0.54, -0.6));
    }
    g.add(p(sph, ink, 0.1, 0.055, 0.14, -0.13, 0.045, 0.05), p(sph, ink, 0.1, 0.055, 0.14, 0.13, 0.045, 0.05));
    const prop = new THREE.Group(); g.add(prop);
    if (job === 'build') head.add(p(hat, '--w-dome', 0.36, 0.26, 0.33, 0, 0.12, 0), p(cyl, '--w-dome', 0.4, 0.025, 0.37, 0, 0.13, 0.04));
    else if (job === 'review') prop.add(p(tor, ink, 0.12, 0.12, 0.12, 0.42, 0.52, 0.16), p(cyl, '--w-wood', 0.022, 0.22, 0.022, 0.42, 0.3, 0.16));
    else if (job === 'fix') { const w = p(cyl, '--w-stone', 0.03, 0.38, 0.03, 0.42, 0.46, 0.1); w.rotation.z = -0.5; prop.add(w, p(tor, '--w-stone', 0.065, 0.065, 0.065, 0.52, 0.64, 0.1)); }
    else if (job === 'verify') prop.add(p(box, pale, 0.24, 0.3, 0.03, 0.4, 0.44, 0.18), p(box, '--w-wood', 0.11, 0.035, 0.04, 0.4, 0.6, 0.18), p(box, '--ui-success', 0.14, 0.03, 0.035, 0.4, 0.46, 0.2));
    else { const s = p(cyl, pale, 0.045, 0.34, 0.045, 0.4, 0.44, 0.12); s.rotation.z = 0.5; prop.add(s); }
    const halo = p(tor, '--w-live', 0.38, 0.38, 0.07, 0, 0.02, 0); halo.rotation.x = Math.PI / 2; halo.castShadow = false; g.add(halo);
    const zz = p(sph, pale, 0.07, 0.07, 0.07, 0.24, 1.4, 0); zz.castShadow = false; g.add(zz);
    const inner = new THREE.Group(); while (g.children.length) inner.add(g.children[0]); g.add(inner); // inner carries the pose, so the outer group is free to be placed and turned
    inner.scale.setScalar(1.25); if (halo) halo.userData.plain = true; if (zz) zz.userData.plain = true; kit.outline(inner, 0.016); g.add(kit.blob(0.48)); g.userData = { inner, head, prop, halo, zz, eyes: [head.children[1], head.children[2]], acts: {}, action: null, phase: (o.seed || 0) * 1.7 };
    if (o.action && o.action !== 'none') ASSETS.critter.setAction(kit, g, o.action);
    g.userData.kit = kit; ASSETS.critter.animate(g, { mode: o.mode || 'idle', mood: o.mood, now: 0, moving: false }); return g;
  },
  // mode: 'work' | 'walk' | 'idle' | 'sleep'. `moving` is false when motion should be still (paused, or reduced motion).
  animate(g, s) {
    const u = g.userData, t = s.now || 0, ph = u.phase, go = s.moving !== false, i = u.inner;
    const sleep = s.mode === 'sleep', walk = s.mode === 'walk', work = s.mode === 'work';
    i.position.y = !go || sleep ? 0 : walk ? Math.abs(Math.sin(t * 0.014 + ph)) * 0.11 : work ? Math.abs(Math.sin(t * 0.007 + ph)) * 0.07 : Math.sin(t * 0.003 + ph) * 0.015 + 0.015;
    i.scale.set(1.25, sleep ? 1.18 : 1.25, 1.25);
    i.rotation.z = sleep ? 0.5 : go && walk ? Math.sin(t * 0.014 + ph) * 0.12 : 0;
    u.head.rotation.x = go && work ? Math.sin(t * 0.005 + ph) * 0.14 - 0.05 : sleep ? 0.25 : 0;
    u.prop.rotation.x = go && work ? Math.sin(t * 0.01 + ph) * 0.35 : 0;
    // Acting out a tool call: only while working. Each action has its own prop and its own motion.
    const act = work && u.action && u.acts[u.action], w = go ? t : 0, beat = Math.abs(Math.sin(w * 0.012 + ph));
    for (const k in u.acts) u.acts[k].visible = u.acts[k] === act; u.prop.visible = !act; if (u.bubble) { u.bubble.visible = !!act; u.bubble.position.y = (u.action === 'git' || u.action === 'report' ? 2.62 : 2.1) + Math.sin(w * 0.004 + ph) * 0.05; }
    u.head.rotation.y = 0; u.head.rotation.z = 0;
    if (act) {
      const A = u.action; act.rotation.set(0, 0, 0); act.scale.setScalar(1);
      if (A === 'read' || A === 'skill') { u.head.rotation.x = 0.3; u.head.rotation.y = Math.sin(w * 0.004 + ph) * 0.22; i.position.y = 0; }
      else if (A === 'write') act.rotation.x = go ? 0.9 - beat * 1.5 : 0;
      else if (A === 'git') { i.position.y = go ? beat * 0.12 : 0; act.rotation.y = w * 0.002; u.head.rotation.x = -0.12; }
      else if (A === 'build') { act.rotation.z = w * 0.006; u.head.rotation.x = 0.1; u.head.rotation.z = Math.sin(w * 0.006) * 0.08; }
      else if (A === 'shell') { u.head.rotation.x = 0.24; i.position.y = 0; i.rotation.z = go ? Math.sin(w * 0.035) * 0.025 : 0; }
      else if (A === 'web') { u.head.rotation.x = -0.05; u.head.rotation.y = act.rotation.y = Math.sin(w * 0.002 + ph) * 0.7; i.position.y = 0; }
      else if (A === 'delegate') { act.scale.setScalar(1 + (go ? beat * 0.28 : 0)); u.head.rotation.x = -0.18; }
      else if (A === 'report') { i.position.y = go ? beat * 0.17 : 0; act.rotation.z = Math.sin(w * 0.012) * 0.16; u.head.rotation.x = -0.15; }
      else if (A === 'wait') { const turn = (w * 0.0006) % 1; act.rotation.z = turn > 0.85 ? (turn - 0.85) / 0.15 * Math.PI : 0; i.position.y = 0; u.head.rotation.z = Math.sin(w * 0.003 + ph) * 0.12; i.rotation.z = go ? Math.sin(w * 0.004) * 0.05 : 0; }
    }
    // Idle: never quite still. It breathes, shifts its weight, looks about, and every few seconds gives a little hop.
    if (s.mode === 'idle' && go) {
      const hopAt = (t * 0.00017 + ph * 0.37) % 1, look = Math.sin(t * 0.0011 + ph * 2.3);
      i.position.y = 0.015 + Math.sin(t * 0.003 + ph) * 0.015 + (hopAt < 0.07 ? Math.sin(hopAt / 0.07 * Math.PI) * 0.14 : 0);
      i.scale.set(1.25, 1.25 * (1 + Math.sin(t * 0.003 + ph) * 0.03), 1.25); i.rotation.z = Math.sin(t * 0.0013 + ph) * 0.05;
      u.head.rotation.y = look * Math.abs(look) * 0.55; u.head.rotation.z = Math.sin(t * 0.0017 + ph) * 0.09; u.head.rotation.x = Math.sin(t * 0.0009 + ph * 1.7) * 0.07;
      u.prop.rotation.x = Math.sin(t * 0.002 + ph) * 0.12;
    }
    // Everyone blinks, each at its own moment.
    { const blink = go && !sleep && ((t * 0.00028 + ph * 0.61) % 1) < 0.035; for (const e of u.eyes) e.scale.y = sleep ? 0.012 : blink ? 0.01 : e.userData.open || (e.userData.open = e.scale.y); }
    // Grumpy: a tool call just failed. Angry brows, a stomp and a shake, and a scribble that jitters over the head in place of the bubble.
    const grumpy = work && (s.grumpy || s.mood === 'grumpy');
    if (grumpy && !u.brows) { u.brows = [-1, 1].map((sd) => { const b = u.kit.mesh(u.kit.geo.box, '@ink', 0.13, 0.03, 0.02, sd * 0.13, 0.1, 0.31, false); b.rotation.z = sd * -0.5; u.head.add(b); return b; });
      u.scribble = new THREE.Sprite(new THREE.SpriteMaterial({ map: u.kit.tex('scribble'), transparent: true, depthWrite: false })); u.scribble.scale.set(0.95, 0.95, 1); g.add(u.scribble); }
    if (u.brows) { u.brows.forEach((b) => { b.visible = grumpy; }); u.scribble.visible = grumpy; }
    if (grumpy) { if (u.bubble) u.bubble.visible = false; const f = go ? Math.floor(t / 110) : 0; u.scribble.material.rotation = (f % 4) * 0.5 - 0.7; u.scribble.position.set((f % 3 - 1) * 0.04, 2.12 + (f % 2) * 0.05, 0); u.scribble.scale.setScalar(1.25 + (f % 2) * 0.12);
      u.head.rotation.x = 0.2; u.head.rotation.z = go ? Math.sin(t * 0.03) * 0.07 : 0; i.rotation.y = go ? Math.sin(t * 0.045) * 0.12 : 0; i.position.y = go ? Math.max(0, Math.sin(t * 0.02)) * 0.09 : 0; } else i.rotation.y = 0;
    u.halo.visible = work; u.zz.visible = sleep; if (sleep) u.zz.position.y = 1.4 + (go ? ((t * 0.0006 + ph) % 1) * 0.5 : 0);
  },
  // Give the critter something to act out: one of the action names, or nothing. The prop and the bubble are made the first time they are needed.
  setAction(kit, g, name) {
    const u = g.userData, want = name && name !== 'none' && ASSETS.critter.PROPS[name] ? name : null; if (u.action === want) return; u.action = want; if (!want) return;
    if (!u.acts[want]) { const a = kit.outline(ASSETS.critter.PROPS[want](kit), 0.014); a.visible = false; u.inner.add(a); u.acts[want] = a; }
    if (!u.bubble) { u.bubble = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthWrite: false })); u.bubble.scale.set(0.7, 0.7, 1); u.bubble.visible = false; g.add(u.bubble); }
    u.bubble.material.map = kit.icon(want); u.bubble.material.needsUpdate = true;
  },
  // The prop for each action. Each is a group whose origin is where it turns or swings from.
  PROPS: {
    read(kit) { const g = kit.group(kit.mesh(kit.geo.box, '--w-cream', 0.36, 0.28, 0.02, 0, 0, 0, false), kit.mesh(kit.geo.box, '@ink', 0.24, 0.02, 0.01, 0, 0.06, -0.012, false), kit.mesh(kit.geo.box, '@ink', 0.24, 0.02, 0.01, 0, 0, -0.012, false), kit.mesh(kit.geo.box, '@ink', 0.16, 0.02, 0.01, -0.04, -0.06, -0.012, false)); g.children.forEach((c) => { c.rotation.x = 0.45; }); g.position.set(0, 0.52, 0.36); return g; },
    skill(kit) { const g = kit.group(kit.mesh(kit.geo.box, '--series-d', 0.4, 0.3, 0.04, 0, 0, 0.012, false), kit.mesh(kit.geo.box, '--w-cream', 0.34, 0.25, 0.03, 0, 0, -0.012, false), kit.mesh(kit.geo.sph, '--w-dome', 0.06, 0.06, 0.06, 0.16, 0.3, 0, false)); g.children.forEach((c, k) => { if (k < 2) c.rotation.x = 0.45; }); g.position.set(0, 0.52, 0.36); return g; },
    write(kit) { const g = kit.group(kit.mesh(kit.geo.cyl, '--w-wood', 0.028, 0.38, 0.028, 0, 0.19, 0, false), kit.mesh(kit.geo.box, '--w-stone', 0.2, 0.1, 0.1, 0, 0.4, 0, false)); g.position.set(0.38, 0.42, 0.14); return g; },
    git(kit) { const g = kit.group(kit.mesh(kit.geo.box, '--w-wood', 0.34, 0.26, 0.34, 0, 0, 0, false), kit.mesh(kit.geo.box, '--w-fruit', 0.36, 0.06, 0.06, 0, 0.11, 0, false), kit.mesh(kit.geo.box, '--w-fruit', 0.06, 0.06, 0.36, 0, 0.11, 0, false)); g.position.set(0, 1.4, 0); return g; },
    build(kit) { const g = kit.group(kit.mesh(kit.geo.tor, '--w-stone', 0.15, 0.15, 0.3, 0, 0, 0, false)); for (let k = 0; k < 6; k++) { const a = k * Math.PI / 3, tooth = kit.mesh(kit.geo.box, '--w-stone', 0.07, 0.09, 0.06, Math.cos(a) * 0.2, Math.sin(a) * 0.2, 0, false); tooth.rotation.z = a - Math.PI / 2; g.add(tooth); } g.position.set(0.5, 0.56, 0.12); return g; },
    shell(kit) { const g = kit.group(kit.mesh(kit.geo.box, '@ink', 0.44, 0.3, 0.04, 0, 0.12, 0, false), kit.mesh(kit.geo.box, '--ui-success', 0.12, 0.03, 0.01, -0.1, 0.18, 0.024, false), kit.mesh(kit.geo.box, '--ui-success', 0.2, 0.03, 0.01, -0.06, 0.11, 0.024, false), kit.mesh(kit.geo.box, '--w-stone', 0.44, 0.03, 0.22, 0, -0.04, 0.1, false)); g.children.forEach((c, k) => { if (k < 3) c.rotation.x = -0.3; }); g.position.set(0, 0.34, 0.4); g.rotation.y = Math.PI; const wrap = kit.group(g); return wrap; },
    web(kit) { const tube = kit.mesh(kit.geo.cyl, '--w-wood', 0.05, 0.34, 0.05, 0, 0, 0.17, false), rim = kit.mesh(kit.geo.cyl, '--w-dome', 0.065, 0.05, 0.065, 0, 0, 0.36, false); tube.rotation.x = rim.rotation.x = Math.PI / 2; const g = kit.group(tube, rim); g.children.forEach((c) => { c.position.x = 0.13; c.position.y = 0.92; c.position.z += 0.3; }); return g; },
    delegate(kit) { const horn = kit.mesh(kit.geo.cone, '--w-roof', 0.2, 0.4, 0.2, 0, 0, 0.2, false); horn.rotation.x = -Math.PI / 2; const g = kit.group(horn, kit.mesh(kit.geo.cyl, '--w-cream', 0.21, 0.03, 0.21, 0, 0, 0.4, false)); g.children[1].rotation.x = Math.PI / 2; g.position.set(0.24, 0.78, 0.4); return g; },
    report(kit) { const g = kit.group(kit.mesh(kit.geo.box, '--w-wood', 0.36, 0.44, 0.03, 0, 0, 0, false), kit.mesh(kit.geo.box, '--w-cream', 0.3, 0.36, 0.02, 0, -0.01, 0.02, false), kit.mesh(kit.geo.box, '--ui-success', 0.07, 0.16, 0.02, 0.05, 0, 0.035, false), kit.mesh(kit.geo.box, '--ui-success', 0.07, 0.09, 0.02, -0.05, -0.04, 0.035, false)); g.children[2].rotation.z = -0.6; g.children[3].rotation.z = 0.7; g.position.set(0, 1.5, 0.05); return g; },
    wait(kit) { const top = kit.mesh(kit.geo.cone, '--w-dome', 0.09, 0.14, 0.09, 0, 0.07, 0, false), bot = kit.mesh(kit.geo.cone, '--w-dome', 0.09, 0.14, 0.09, 0, -0.07, 0, false); top.rotation.x = Math.PI; const g = kit.group(top, bot, kit.mesh(kit.geo.cyl, '--w-wood', 0.11, 0.025, 0.11, 0, 0.15, 0, false), kit.mesh(kit.geo.cyl, '--w-wood', 0.11, 0.025, 0.11, 0, -0.15, 0, false)); g.position.set(0.44, 0.56, 0.16); return g; },
  },
};
