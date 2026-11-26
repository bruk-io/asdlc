// The things Bruk spends his own time on, set up on a patch of grass by the orchestrator's plot.
// A 3D printer with a part growing on its bed, a small homelab rack with blinking lights, a drafting table for sketching designs,
// a woodworking bench and a camp kitchen.
ASSETS.printer = {
  title: '3D printer',
  build(kit) {
    const { box, cyl } = kit.geo, g = new THREE.Group(), p = (geo, m, sx, sy, sz, x, y, z) => kit.mesh(geo, m, sx, sy, sz, x, y, z);
    g.add(kit.blob(1.0), p(box, '--w-wood', 1.3, 0.5, 0.9, 0, 0.25, 0), p(box, '--p-pants', 0.9, 0.08, 0.8, 0, 0.54, 0), p(box, '--w-stone', 0.62, 0.03, 0.62, 0, 0.6, 0));
    [[-0.42, -0.36], [0.42, -0.36], [-0.42, 0.36], [0.42, 0.36]].forEach(([x, z]) => g.add(p(box, '--p-pants', 0.06, 0.95, 0.06, x, 1.05, z)));
    g.add(p(box, '--p-pants', 0.9, 0.06, 0.8, 0, 1.53, 0));
    const gantry = p(box, '--w-stone', 0.86, 0.04, 0.05, 0, 1.0, 0), head = p(box, '--series-a', 0.13, 0.13, 0.13, 0, 0.98, 0), part = p(kit.prism(0.3, 0.2, 0.07), '--series-a', 1, 0.01, 1, 0, 0.62, 0);
    const spool = p(cyl, '--series-a', 0.2, 0.09, 0.2, 0.62, 1.2, 0); spool.rotation.z = Math.PI / 2;
    g.add(gantry, head, part, spool); g.userData = { gantry, head, part, spool }; return kit.outline(g, 0.014);
  },
  // The part grows layer by layer over about 25 seconds, then a new one starts.
  animate(g, s) { const u = g.userData, t = s.moving === false ? 0 : s.now || 0, f = (t * 0.00004) % 1, h = 0.02 + f * 0.3;
    u.part.scale.y = h; u.part.position.y = 0.615 + h / 2; u.gantry.position.y = u.head.position.y = 0.7 + h; u.head.position.x = Math.sin(t * 0.006) * 0.14; u.head.position.z = Math.sin(t * 0.0041) * 0.08; u.spool.rotation.x = t * 0.001; },
};
ASSETS.rack = {
  title: 'Homelab rack',
  build(kit) {
    const { box, sph } = kit.geo, g = new THREE.Group(), lights = [];
    g.add(kit.blob(0.8), kit.mesh(box, '--p-pants', 0.8, 1.5, 0.7, 0, 0.75, 0));
    for (let r = 0; r < 5; r++) { g.add(kit.mesh(box, '--w-stone', 0.7, 0.2, 0.03, 0, 0.26 + r * 0.26, 0.355, false));
      for (let k = 0; k < 4; k++) { const m = new THREE.Mesh(sph, new THREE.MeshBasicMaterial({ color: k === 3 ? '#ffb347' : '#5dea8b' })); m.scale.setScalar(0.022); m.position.set(-0.26 + k * 0.07, 0.26 + r * 0.26, 0.375); m.userData = { plain: true, k: r * 4 + k }; g.add(m); lights.push(m); } }
    g.userData.lights = lights; return kit.outline(g, 0.014);
  },
  animate(g, s) { const t = s.moving === false ? 0 : s.now || 0; for (const m of g.userData.lights) m.visible = Math.sin(t * (0.004 + (m.userData.k % 5) * 0.0021) + m.userData.k * 1.7) > -0.35; },
};
ASSETS.desk = {
  title: 'Drafting table',
  build(kit) {
    const { box, cyl } = kit.geo, g = new THREE.Group(), top = new THREE.Group(); top.position.set(0, 0.86, 0); top.rotation.x = 0.32;
    top.add(kit.mesh(box, '--w-wood', 1.3, 0.05, 0.85, 0, 0, 0), kit.mesh(box, '--w-cream', 0.95, 0.012, 0.62, 0, 0.032, 0, false), kit.mesh(box, '--series-b', 0.5, 0.008, 0.012, -0.1, 0.042, -0.1, false), kit.mesh(box, '--series-b', 0.012, 0.008, 0.3, 0.15, 0.042, 0.02, false), kit.mesh(cyl, '--series-b', 0.11, 0.008, 0.11, -0.2, 0.042, 0.1, false));
    g.add(kit.blob(1.0), top, kit.mesh(cyl, '--w-trunk', 0.04, 0.82, 0.04, -0.55, 0.41, 0.3), kit.mesh(cyl, '--w-trunk', 0.04, 0.82, 0.04, 0.55, 0.41, 0.3), kit.mesh(cyl, '--w-trunk', 0.04, 1.06, 0.04, -0.55, 0.53, -0.3), kit.mesh(cyl, '--w-trunk', 0.04, 1.06, 0.04, 0.55, 0.53, -0.3));
    return kit.outline(g, 0.014);
  },
};
ASSETS.workbench = {
  title: 'Woodworking bench',
  build(kit) {
    const { box, cyl } = kit.geo, g = new THREE.Group(), p = (geo, m, sx, sy, sz, x, y, z) => kit.mesh(geo, m, sx, sy, sz, x, y, z);
    g.add(kit.blob(1.1), p(box, '--w-wood', 1.6, 0.1, 0.7, 0, 0.8, 0), p(box, '--w-trunk', 1.4, 0.06, 0.5, 0, 0.3, 0));
    [[-0.7, -0.28], [0.7, -0.28], [-0.7, 0.28], [0.7, 0.28]].forEach(([x, z]) => g.add(p(box, '--w-trunk', 0.09, 0.78, 0.09, x, 0.39, z)));
    g.add(p(box, '--m-tan', 1.1, 0.06, 0.2, 0.1, 0.88, 0.05), p(box, '--w-stone', 0.16, 0.14, 0.2, -0.68, 0.9, 0.2), p(box, '--m-tan', 0.5, 0.05, 0.16, 0.3, 0.36, 0), p(box, '--m-tan', 0.4, 0.05, 0.16, -0.25, 0.36, 0.1));
    for (let k = 0; k < 5; k++) g.add(p(cyl, '--m-stem', 0.04, 0.008, 0.03, 0.2 + Math.cos(k * 2.1) * 0.3, 0.855, 0.25 + Math.sin(k * 1.7) * 0.06));   // shavings
    return kit.outline(g, 0.014);
  },
};
ASSETS.stove = {
  title: 'Camp kitchen',
  build(kit) {
    const { box, cyl, sph } = kit.geo, g = new THREE.Group(), p = (geo, m, sx, sy, sz, x, y, z) => kit.mesh(geo, m, sx, sy, sz, x, y, z);
    g.add(kit.blob(1.0), p(box, '--w-stone', 1.3, 0.75, 0.7, 0, 0.375, 0), p(box, '--w-wood', 1.4, 0.06, 0.8, 0, 0.78, 0), p(cyl, '--p-pants', 0.2, 0.03, 0.2, -0.3, 0.83, 0), p(cyl, '--p-pants', 0.24, 0.22, 0.24, -0.3, 0.95, 0), p(cyl, '--series-a', 0.21, 0.02, 0.21, -0.3, 1.06, 0),
      p(box, '--m-tan', 0.42, 0.03, 0.3, 0.35, 0.83, 0.05), p(sph, '--w-fruit', 0.06, 0.06, 0.06, 0.28, 0.88, 0.05), p(sph, '--w-leaf', 0.07, 0.04, 0.1, 0.42, 0.86, 0.02), p(sph, '--m-brown', 0.05, 0.04, 0.05, 0.38, 0.87, 0.14));
    const steam = [0, 1, 2].map((k) => { const m = p(sph, '--w-cloud', 0.07, 0.07, 0.07, -0.3, 1.2, 0); m.castShadow = false; m.userData = { plain: true, k }; g.add(m); return m; });
    g.userData.steam = steam; return kit.outline(g, 0.014);
  },
  animate(g, s) { const t = s.moving === false ? 0 : s.now || 0; for (const m of g.userData.steam) { const f = (t * 0.0005 + m.userData.k / 3) % 1; m.position.set(-0.3 + Math.sin(f * 6 + m.userData.k) * 0.06, 1.12 + f * 0.6, 0); m.scale.setScalar(0.05 + f * 0.08 * (1 - f) * 4); } },
};
