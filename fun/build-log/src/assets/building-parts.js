// The pieces a building is put together from. The page stacks them itself, because each floor grows as its agent works.
ASSETS.storey = {
  title: 'Wall block', controls: { colour: ['--series-a', '--series-b', '--series-c', '--series-d', '--series-e'], style: ['0', '1', '2'] },
  // A wall block one unit tall with a row of windows. Scale it in y, then call fit() so the windows keep their shape.
  // style picks the windows: 0 plain, 1 shuttered, 2 arched with a flower box. paint() gives it a wall colour.
  build(kit, o) {
    const side = kit.toon({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0 }), top = kit.toon();
    const m = new THREE.Mesh(ASSETS.storey.geo || (ASSETS.storey.geo = kit.prism(FOOT, FOOT, 0.24)), [top, side]); m.castShadow = m.receiveShadow = true;
    const style = +o.style || 0, em = kit.tex(style === 2 ? 'windowGlowArched' : 'windowGlow').clone(); em.needsUpdate = true; side.emissiveMap = em;
    m.userData = { side, top, style, em, rep: new THREE.Vector2(2, 2) }; kit.outline(m, 0.02);
    if (o.colour) ASSETS.storey.paint(kit, m, o.colour);
    if (o.height) { m.scale.y = o.height; m.position.y = o.height / 2; ASSETS.storey.fit(m, o.height); } return m;
  },
  // Set the wall colour: a CSS variable name or a colour. The wall is a painted texture, so this swaps the texture.
  paint(kit, m, colour) {
    const u = m.userData; if (u.colour === colour) return; u.colour = colour; if (u.map) u.map.dispose();
    u.map = kit.wall(colour, u.style).clone(); u.map.needsUpdate = true; u.map.repeat.copy(u.rep); u.side.map = u.map; u.side.needsUpdate = true; u.top.color.set(kit.colour(colour));
  },
  fit(m, h) { const u = m.userData; u.rep.set(2, Math.max(0.25, h / (0.5 * BIG))); if (u.map) u.map.repeat.copy(u.rep); u.em.repeat.copy(u.rep); },
};
ASSETS.slab = { title: 'Floor ledge', build(kit) { return kit.mesh(ASSETS.slab.geo || (ASSETS.slab.geo = kit.prism(FOOT + 0.16, FOOT + 0.16, 0.3)), '--w-cream', 1, 0.06, 1, 0, 0.03, 0); } };
ASSETS.plot = { title: 'Plot', build(kit) { return kit.group(kit.blob(FOOT * 1.45, 0.006), kit.mesh(ASSETS.plot.geo || (ASSETS.plot.geo = kit.prism(FOOT + 0.56, FOOT + 0.56, 0.34)), '--w-plot', 1, 0.07, 1, 0, 0.035, 0, false)); } };
ASSETS.roof = {
  title: 'Roof', controls: { style: ['pyramid', 'gable', 'mansard'], colour: ['--w-roof', '--w-roof-2', '--w-roof-3'] },
  build(kit, o) {
    const W = 1.5 + 0.34, G = ASSETS.roof.geo || (ASSETS.roof.geo = {
      eave: kit.prism(2.0, 2.0, 0.2),
      pyramid: (() => { const c = new THREE.ConeGeometry(W / Math.SQRT2, 1, 4); c.rotateY(Math.PI / 4); c.translate(0, 0.5, 0); return c; })(),
      mansard: (() => { const c = new THREE.CylinderGeometry(W / Math.SQRT2 * 0.5, W / Math.SQRT2, 1, 4); c.rotateY(Math.PI / 4); c.translate(0, 0.5, 0); return c; })(),
      // Two tiled slopes meeting at a ridge, and two plaster ends.
      gable: (() => { const w = W / 2, d = W / 2, g = new THREE.BufferGeometry();
        const P = [-w, 0, d, w, 0, d, w, 1, 0, -w, 0, d, w, 1, 0, -w, 1, 0, w, 0, -d, -w, 0, -d, -w, 1, 0, w, 0, -d, -w, 1, 0, w, 1, 0, -w, 0, -d, -w, 0, d, -w, 1, 0, w, 0, d, w, 0, -d, w, 1, 0];
        const U = [0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 0.5, 1, 0, 0, 1, 0, 0.5, 1];
        g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(U, 2)); g.addGroup(0, 12, 0); g.addGroup(12, 6, 1); g.computeVertexNormals(); return g; })(),
    });
    const style = o.style || 'pyramid', col = o.colour || '--w-roof', g = kit.group(kit.mesh(G.eave, '--w-cream', 1, 0.09, 1, 0, 0.045, 0));
    if (style === 'gable') { const m = new THREE.Mesh(G.gable, [kit.mat(col), kit.mat('--w-cream')]); m.scale.set(1.12, 1.0, 1.12); m.position.y = 0.09; m.castShadow = m.receiveShadow = true; g.add(m); }
    else g.add(kit.mesh(G[style], col, 1.12, style === 'mansard' ? 0.78 : 1.05, 1.12, 0, 0.09, 0));
    if (style === 'mansard') g.add(kit.mesh(G.eave, '--w-cream', 0.5, 0.06, 0.5, 0, 0.88, 0));
    g.add(kit.mesh(kit.geo.box, '--w-stone', 0.24, 0.6, 0.24, 0.42, 0.72, -0.3), kit.mesh(kit.geo.box, '--w-cream', 0.3, 0.07, 0.3, 0.42, 1.05, -0.3));
    g.scale.setScalar(BIG); return kit.outline(g, 0.022);
  },
};
ASSETS.dome = { title: 'Dome', build(kit) { return kit.outline(kit.group(kit.mesh(ASSETS.dome.geo || (ASSETS.dome.geo = new THREE.SphereGeometry(FOOT * 0.52, 18, 10, 0, Math.PI * 2, 0, Math.PI / 2)), '--w-dome', 1, 0.7, 1, 0, 0, 0))); } };
ASSETS.door = {
  title: 'Door', controls: { colour: ['--w-door', '--w-door-2', '--w-door-3'] },
  build(kit, o) {
    const G = ASSETS.door.geo || (ASSETS.door.geo = { door: kit.prism(0.46, 0.08, 0.03), frame: kit.prism(0.58, 0.07, 0.03), step: kit.prism(0.8, 0.34, 0.08), awning: kit.prism(0.78, 0.3, 0.06) });
    const awning = kit.mesh(G.awning, o.colour || '--w-door', 1, 0.05, 1, 0, 0.78, 0.14, false); awning.rotation.x = 0.35;
    const g = kit.group(kit.mesh(G.frame, '--w-cream', 1, 0.7, 1, 0, 0.35, 0.01, false), kit.mesh(G.door, o.colour || '--w-door', 1, 0.6, 1, 0, 0.3, 0.03, false),
      kit.mesh(kit.geo.sph, '--w-glow', 0.1, 0.1, 0.02, 0, 0.44, 0.075, false), kit.mesh(kit.geo.sph, '--w-dome', 0.04, 0.04, 0.04, 0.15, 0.27, 0.08, false), kit.mesh(G.step, '--w-stone', 1, 0.06, 1, 0, 0, 0.2, false), awning); g.scale.setScalar(BIG * DOOR); return g;
  },
};
ASSETS.scaffold = {
  title: 'Scaffold', controls: { height: ['2', '4', '8'] },
  build(kit, o) {
    const g = new THREE.Group(), h = FOOT / 2 + 0.26, { cyl } = kit.geo;
    [[-h, -h], [h, -h], [h, h], [-h, h]].forEach(([x, z]) => g.add(kit.mesh(cyl, '--w-wood', 0.045, 1, 0.045, x, 0.5, z)));
    [[0, -h, 1], [0, h, 1], [-h, 0, 0], [h, 0, 0]].forEach(([x, z, along]) => [0.55, 1].forEach((yy) => { const b = kit.mesh(cyl, '--w-wood', 0.035, h * 2, 0.035, x, yy, z); b.rotation.z = along ? Math.PI / 2 : 0; b.rotation.x = along ? 0 : Math.PI / 2; b.userData.bar = yy; g.add(b); }));
    ASSETS.scaffold.resize(g, +o.height || 2); return g;
  },
  resize(g, height) { g.children.forEach((c) => { if (c.userData.bar) c.position.y = height * c.userData.bar; else { c.scale.y = height; c.position.y = height / 2; } }); },
};
ASSETS.flag = { title: 'Flag', build(kit) { const g = kit.outline(kit.group(kit.mesh(kit.geo.cyl, '--w-wood', 0.03, 0.9, 0.03, 0, 0.45, 0), kit.mesh(kit.geo.box, '--ui-success', 0.5, 0.28, 0.03, 0.27, 0.74, 0)), 0.014); g.scale.setScalar(BIG); return g; } };
