// A whole building, put together from the parts, for looking at in the viewer. The page builds its own, floor by floor.
ASSETS.cottage = {
  title: 'Cottage', controls: { state: ['merged', 'building', 'planning'], floors: ['2', '4', '9'], look: ['1', '2', '3'] },
  build(kit, o) {
    const g = new THREE.Group(), n = +o.floors || 4, colours = ['--series-a', '--series-b', '--series-c', '--series-d'], rnd = kit.rng(n * 31 + 3), look = (+o.look || 1) - 1; let y = 0.07;
    g.add(kit.make('plot'));
    const floors = [];
    for (let i = 0; i < n; i++) { const h = (0.35 + rnd() * 0.7) * BIG, m = kit.make('storey', { colour: colours[(i + look) % 4], style: look }); m.userData.h = h; m.userData.y = y; floors.push(m); g.add(m);
      const s = kit.make('slab'); s.userData.y = y + h; floors.push(s); g.add(s); y += h + 0.06; }
    const door = kit.make('door', { colour: ['--w-door', '--w-door-2', '--w-door-3'][look] }); door.position.set(0, 0.07, FOOT / 2); g.add(door);
    const roof = kit.make(o.state === 'planning' ? 'dome' : 'roof', { style: ['pyramid', 'gable', 'mansard'][look], colour: ['--w-roof', '--w-roof-3', '--w-roof-2'][look] }), flag = kit.make('flag'), scaffold = kit.make('scaffold');
    scaffold.position.y = 0.07; g.add(roof, flag, scaffold);
    g.userData = { floors, roof, flag, scaffold, top: y, state: o.state || 'merged' }; ASSETS.cottage.animate(g, { now: 0, moving: false }); return g;
  },
  animate(g, s) {
    const u = g.userData, building = u.state === 'building', grow = building && s.moving !== false ? ((s.now || 0) * 0.00018) % 1.15 : 1; let top = 0.07;
    for (const m of u.floors) {
      if (m.userData.h) { const f = Math.max(0, Math.min(1, (grow * u.top - m.userData.y) / m.userData.h)), h = m.userData.h * f; m.visible = h > 0.01; m.scale.y = Math.max(h, 0.001); m.position.y = m.userData.y + h / 2; ASSETS.storey.fit(m, h);
        m.userData.side.emissive.set(building && f > 0 && f < 1 ? '#ffe14d' : '#000000'); m.userData.side.emissiveIntensity = 1; if (m.visible) top = m.userData.y + h; }
      else { m.visible = grow * u.top > m.userData.y; m.position.y = m.userData.y + 0.03; if (m.visible) top = m.userData.y + 0.06; }
    }
    u.roof.visible = !building; u.roof.position.y = top; u.flag.visible = u.state === 'merged'; u.flag.position.y = top + 1.0 * BIG;
    u.scaffold.visible = building; ASSETS.scaffold.resize(u.scaffold, top + 0.5);
  },
};
