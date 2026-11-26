// A chunky round tree, sometimes with fruit, or a three-tier pine. The crown sways from the top of the trunk.
ASSETS.tree = {
  title: 'Tree', controls: { kind: ['round', 'pine'], fruit: ['yes', 'no'] },
  build(kit, o) {
    const { sph, cone, trunk } = kit.geo, g = new THREE.Group(), crown = new THREE.Group(); crown.position.y = 1.0;
    g.add(kit.blob(1.35), kit.mesh(trunk, '--w-trunk', 0.3, 1.1, 0.3, 0, 0.55, 0), crown);
    if (o.kind === 'pine') [[1.05, 1.3, 0.25], [0.82, 1.15, 1.0], [0.56, 1.0, 1.7]].forEach(([r, h, y]) => crown.add(kit.mesh(cone, '--w-leaf-2', r, h, r, 0, y, 0)));
    else {
      [[0, 0.9, 0, 1.15], [0.75, 0.75, 0.2, 0.78], [-0.75, 0.7, -0.15, 0.8], [0.1, 0.65, 0.75, 0.74], [-0.1, 0.75, -0.75, 0.72], [0, 1.55, 0, 0.8]]
        .forEach(([x, y, z, r], i) => crown.add(kit.mesh(sph, i % 2 ? '--w-leaf-2' : '--w-leaf', r, r * 0.9, r, x, y, z)));
      if (o.fruit !== 'no' && o.fruit !== false) [[0.95, 0.6, 0.5], [-0.8, 0.9, 0.75], [0.25, 1.2, 0.95], [-0.2, 0.35, 1.0]].forEach(([x, y, z]) => crown.add(kit.mesh(sph, '--w-fruit', 0.16, 0.16, 0.16, x, y, z, false)));
    }
    g.userData.crown = crown; kit.outline(g, 0.03); g.scale.setScalar(o.scale || 1); return g;
  },
  animate(g, s) { const c = g.userData.crown, a = (s.now || 0) * 0.0011 + g.position.x * 0.6 + g.position.z * 0.35; c.rotation.z = Math.sin(a) * 0.035; c.rotation.x = Math.sin(a * 0.7 + 1) * 0.025; },
};
