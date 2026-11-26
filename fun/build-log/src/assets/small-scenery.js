// The small things scattered on the grass: tulips, bushes, rocks, stumps, benches, lamps, clouds and butterflies.
ASSETS.tulips = {
  title: 'Tulips', controls: { colour: ['--w-blush', '--w-dome', '--w-cream', '--w-fruit', '--series-b'] },
  build(kit, o) {
    const { cyl, bud } = kit.geo, g = new THREE.Group(), colour = o.colour || '--w-blush';
    for (let q = 0; q < 3; q++) { const x = q * 0.34, z = (q % 2) * 0.2;
      g.add(kit.mesh(cyl, '--w-leaf-2', 0.028, 0.34, 0.028, x, 0.17, z, false)); const l = kit.mesh(bud, '--w-leaf', 0.05, 0.16, 0.1, x + 0.07, 0.12, z, false); l.rotation.z = -0.5; g.add(l);
      g.add(kit.mesh(bud, colour, 0.1, 0.14, 0.1, x, 0.4, z, false)); }
    return g;
  },
};
ASSETS.bush = { title: 'Bush', build(kit) { const { sph } = kit.geo; return kit.outline(kit.group(kit.blob(0.75), kit.mesh(sph, '--w-leaf-2', 0.5, 0.36, 0.5, 0, 0.14, 0), kit.mesh(sph, '--w-leaf', 0.36, 0.3, 0.36, 0.36, 0.16, 0.12)), 0.022); } };
ASSETS.rock = { title: 'Rock', build(kit, o) { const r = kit.mesh(kit.geo.sph, '--w-stone', o.size || 0.45, 0.22, 0.3, 0, 0.03, 0); r.rotation.y = o.turn || 0; return kit.outline(kit.group(kit.blob((o.size || 0.45) * 1.3), r), 0.018); } };
ASSETS.stump = { title: 'Stump', build(kit) { return kit.outline(kit.group(kit.blob(0.45), kit.mesh(kit.geo.trunk, '--w-trunk', 0.3, 0.26, 0.3, 0, 0.13, 0), kit.mesh(kit.geo.cyl, '--w-wood', 0.19, 0.02, 0.19, 0, 0.27, 0, false)), 0.018); } };
ASSETS.bench = { title: 'Bench', build(kit) { const { cyl } = kit.geo, slat = kit.prism(1.5, 0.5, 0.1), back = kit.mesh(slat, '--w-wood', 1, 0.07, 0.7, 0, 0.72, -0.24); back.rotation.x = Math.PI / 2 - 0.15;
  return kit.outline(kit.group(kit.blob(0.95), kit.mesh(slat, '--w-wood', 1, 0.09, 1, 0, 0.42, 0), back, kit.mesh(cyl, '--w-trunk', 0.07, 0.4, 0.07, -0.55, 0.2, 0), kit.mesh(cyl, '--w-trunk', 0.07, 0.4, 0.07, 0.55, 0.2, 0)), 0.018); } };
ASSETS.lamp = { title: 'Lamp post', build(kit) { return kit.outline(kit.group(kit.blob(0.3), kit.mesh(kit.geo.cyl, '--w-trunk', 0.05, 1.5, 0.05, 0, 0.75, 0), kit.mesh(kit.geo.cone, '--w-trunk', 0.24, 0.14, 0.24, 0, 1.8, 0, false), kit.mesh(kit.geo.sph, '--w-glow', 0.17, 0.17, 0.17, 0, 1.6, 0, false)), 0.016); } };
ASSETS.cloud = {
  title: 'Cloud',
  build(kit, o) {
    const rnd = kit.rng(o.seed || 5), g = new THREE.Group();
    for (let j = 0; j < 5; j++) g.add(kit.mesh(kit.geo.sph, '--w-cloud', 1.5 + rnd() * 1.2, 0.8 + rnd() * 0.6, 1.2 + rnd(), j * 1.4 - 2.8, rnd() * 0.5, rnd() * 0.8, false));
    g.traverse((c) => { c.receiveShadow = false; }); return g;
  },
};
ASSETS.butterfly = {
  title: 'Butterfly', controls: { colour: ['--w-blush', '--w-dome', '--w-cream', '--w-fruit', '--series-b'] },
  build(kit, o) {
    const g = new THREE.Group(), wings = [-1, 1].map((s) => { const pivot = new THREE.Group(); pivot.add(kit.mesh(kit.geo.sph, o.colour || '--w-blush', 0.11, 0.012, 0.09, s * 0.11, 0, 0.03, false), kit.mesh(kit.geo.sph, o.colour || '--w-blush', 0.075, 0.012, 0.06, s * 0.08, 0, -0.07, false)); pivot.userData.side = s; return pivot; });
    g.add(kit.mesh(kit.geo.sph, '@ink', 0.022, 0.022, 0.09, 0, 0, 0, false), ...wings); g.userData.wings = wings; return g;
  },
  animate(g, s) { const f = 0.25 + Math.abs(Math.sin((s.now || 0) * 0.018 + g.position.x)) * 1.0; for (const w of g.userData.wings) w.rotation.z = w.userData.side * f; },
};
ASSETS.bird = {
  title: 'Bird',
  build(kit) {
    const g = new THREE.Group(), wings = [-1, 1].map((s) => { const pivot = new THREE.Group(), w = kit.mesh(kit.geo.sph, '--w-cream', 0.42, 0.03, 0.2, s * 0.42, 0, 0, false); pivot.add(w); pivot.userData.side = s; return pivot; });
    g.add(kit.mesh(kit.geo.sph, '--w-cream', 0.14, 0.13, 0.34, 0, 0, 0, false), kit.mesh(kit.geo.cone, '--w-dome', 0.05, 0.14, 0.05, 0, 0, 0.42, false), ...wings); g.children[1].rotation.x = Math.PI / 2; g.userData.wings = wings; return g;
  },
  animate(g, s) { const f = Math.sin((s.now || 0) * 0.009 + (s.k || 0) * 1.3) * 0.6; for (const w of g.userData.wings) w.rotation.z = w.userData.side * f; },
};
// Mushrooms of the kind found in a wood, in three sorts: a fat brown bolete with a thick stem, a cluster of small tan caps, and a golden funnel.
ASSETS.mushroom = {
  title: 'Mushroom', controls: { kind: ['bolete', 'caps', 'funnel'] },
  build(kit, o) {
    const { cyl, hat, cone, trunk } = kit.geo, rnd = kit.rng((o.seed || 1) * 13 + 5), g = new THREE.Group(), kind = o.kind || 'bolete';
    const lean = (m, a) => { m.rotation.z = a; return m; };
    const bolete = (x, z, s, a) => { const one = new THREE.Group(); one.position.set(x, 0, z); one.rotation.z = a;
      one.add(kit.mesh(trunk, '--m-stem', 0.11 * s, 0.24 * s, 0.11 * s, 0, 0.12 * s, 0), kit.mesh(cyl, '--m-gill', 0.21 * s, 0.03 * s, 0.21 * s, 0, 0.25 * s, 0, false), kit.mesh(hat, '--m-brown', 0.24 * s, 0.15 * s, 0.24 * s, 0, 0.26 * s, 0)); g.add(one); };
    const cap = (x, z, s, a) => { const one = new THREE.Group(); one.position.set(x, 0, z); one.rotation.z = a;
      one.add(kit.mesh(cyl, '--m-stem', 0.035 * s, 0.26 * s, 0.035 * s, 0, 0.13 * s, 0), kit.mesh(cyl, '--m-gill', 0.13 * s, 0.015, 0.13 * s, 0, 0.255 * s, 0, false), kit.mesh(hat, '--m-tan', 0.15 * s, 0.1 * s, 0.15 * s, 0, 0.26 * s, 0)); g.add(one); };
    const funnel = (x, z, s, a) => { const one = new THREE.Group(); one.position.set(x, 0, z); one.rotation.z = a; const f = kit.mesh(cone, '--m-gold', 0.17 * s, 0.26 * s, 0.17 * s, 0, 0.15 * s, 0); f.rotation.x = Math.PI;   // a cone standing on its point
      one.add(f, kit.mesh(cyl, '--m-gold', 0.19 * s, 0.02 * s, 0.19 * s, 0, 0.285 * s, 0, false), kit.mesh(cyl, '--m-gill', 0.1 * s, 0.01, 0.1 * s, 0, 0.297 * s, 0, false)); g.add(one); };
    if (kind === 'bolete') { bolete(0, 0, 1.2, 0.06); if (rnd() < 0.7) bolete(0.34, 0.14, 0.7, -0.12); }
    else if (kind === 'caps') [[0, 0, 1, 0.1], [0.16, 0.1, 0.8, -0.18], [-0.14, 0.12, 0.7, 0.22], [0.05, -0.15, 0.6, -0.08], [-0.2, -0.06, 0.5, 0.3]].forEach((c) => cap(...c));
    else { funnel(0, 0, 1.1, 0.08); funnel(0.26, 0.1, 0.75, -0.16); if (rnd() < 0.6) funnel(-0.2, 0.18, 0.6, 0.2); }
    g.add(kit.blob(0.5)); return kit.outline(g, 0.012);
  },
};
