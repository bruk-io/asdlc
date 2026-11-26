// The particle effects, shown one at a time in the viewer. In the page they are fired by what the agents do.
(() => {
  const demo = (title, kind, every, n, at, extra) => ({
    title: 'Effect: ' + title,
    build(kit) {
      const g = new THREE.Group(); g.add(kit.make('plot'));
      if (extra) extra(kit, g);
      g.userData = { ps: makeParticles(kit, g, 300), last: 0, next: 0 }; return g;
    },
    animate(g, s) {
      const u = g.userData, now = s.now || 0, dt = Math.min(0.05, Math.max(0, (now - u.last) / 1000)); u.last = now;
      if (s.moving !== false && now >= u.next) { u.ps.emit(kind, at[0], at[1], at[2], n); u.next = now + every; }
      u.ps.update(dt);
    },
  });
  const house = (kit, g) => { const m = kit.make('storey', { colour: '--series-a', height: 0.9 * BIG }); m.position.y += 0.07; g.add(m); const r = kit.make('roof'); r.position.y = 0.07 + 0.9 * BIG; g.add(r); };
  ASSETS.fxDust = demo('building dust', 'dust', 260, 3, [0, 0.5, 0.85], (kit, g) => { const m = kit.make('storey', { colour: '--series-a', height: 0.5 }); m.position.y += 0.07; g.add(m); });
  ASSETS.fxChips = demo('wood chips', 'chips', 380, 4, [0.9, 0.5, 0.6], (kit, g) => { const c = kit.make('critter', { model: 'sonnet', job: 'build', mode: 'work' }); c.position.set(1.2, 0.07, 0.6); c.rotation.y = -1.6; g.add(c); });
  ASSETS.fxConfetti = demo('merge confetti', 'confetti', 2600, 110, [0, 3.2, 0], house);
  ASSETS.fxSparkle = demo('sparkles', 'sparkle', 700, 20, [0, 3.2, 0], house);
  ASSETS.fxSmoke = demo('chimney smoke', 'smoke', 520, 1, [0.42 * BIG, 0.07 + 0.9 * BIG + 1.05 * BIG, -0.3 * BIG], house);
  ASSETS.fxSparks = demo('build sparks', 'sparks', 260, 3, [0, 0.9, 0.4], (kit, g) => { const c = kit.make('critter', { model: 'sonnet', job: 'build', mode: 'work', action: 'build' }); c.position.set(0, 0.07, 0.4); g.add(c); });
  ASSETS.fxMail = demo('git mail', 'mail', 420, 1, [0, 2.3, 0.4], (kit, g) => { const c = kit.make('critter', { model: 'sonnet', job: 'build', mode: 'work', action: 'git' }); c.position.set(0, 0.07, 0.4); g.add(c); });
  ASSETS.fxTicks = demo('report ticks', 'ticks', 380, 2, [0, 2.0, 0.4], (kit, g) => { const c = kit.make('critter', { model: 'sonnet', job: 'build', mode: 'work', action: 'report' }); c.position.set(0, 0.07, 0.4); g.add(c); });
  ASSETS.fxFume = demo('error fumes', 'fume', 300, 2, [0, 1.9, 0.4], (kit, g) => { const c = kit.make('critter', { model: 'sonnet', job: 'build', mode: 'work', action: 'shell', mood: 'grumpy' }); c.position.set(0, 0.07, 0.4); g.add(c); });
  ASSETS.fxPoof = demo('arrival poof', 'poof', 1400, 9, [0, 0.4, 0], null);
})();
