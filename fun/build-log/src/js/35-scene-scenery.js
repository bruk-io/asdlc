    /* ---- scenery: trees, bushes, flowers, rocks, lamps, clouds. Placed by a fixed seed so every visit looks the same. ---- */
    const rnd = kit.rng(20261124), trees = [], blooms = [], flutter = [];
    const free = (x, z) => Math.abs(x) < halfW - 2.5 && z > z0 + 2.5 && z < z1 - 2.5 && !(z > -5 && z < depth + 4 && x > -widest / 2 - 4.6 && x < widest / 2 + 4.4) && Math.hypot(x - rx, z - rz) > 3 && Math.hypot(x + widest / 2 + 9.5, z - ROW_GAP * 1.6 - 1.5) > 6.5;   // and off Bruk's yard
    for (let i = 0, n = 0; i < 900 && n < 64; i++) { const x = (rnd() * 2 - 1) * halfW, z = z0 + rnd() * (z1 - z0); if (!free(x, z)) continue; n++;
      const scale = 0.8 + rnd() * 0.7, kind = rnd() < 0.38 ? 'pine' : 'round'; trees.push(place('tree', { kind, scale, fruit: rnd() < 0.55 }, x, 0, z, rnd() * 6.3)); }
    const petals = ['--w-blush', '--w-dome', '--w-cream', '--w-fruit', '--series-b'];
    for (let i = 0, n = 0; i < 1500 && n < 110; i++) {
      const x = (rnd() * 2 - 1) * halfW, z = z0 + rnd() * (z1 - z0); if (!free(x, z)) continue; n++;
      const k = rnd();
      if (k < 0.5) { blooms.push(place('tulips', { colour: petals[n % 5] }, x, 0, z)); if (n % 5 === 0) { const b = place('butterfly', { colour: petals[(n + 2) % 5] }, x, 0.7, z); b.userData.home = [x, z]; b.userData.ph = rnd() * 20; flutter.push(b); } }
      else if (k < 0.8) place('bush', {}, x, 0, z);
      else if (k < 0.92) place('rock', { size: 0.36 + rnd() * 0.2, turn: rnd() * 3 }, x, 0, z);
      else place('stump', {}, x, 0, z);
    }
    // Woods on the hills. Trees keep to gentle grassy ground below the rock line: round ones low down, pines higher, smaller the higher they grow.
    // Each is sunk a little on the downhill side so no trunk hangs in the air.
    const steep = (x, z, h) => Math.hypot(ground(x + 1.2, z) - h, ground(x, z + 1.2) - h) / 1.2;
    for (let i = 0, n = 0; i < 9000 && n < 150; i++) { const x = (rnd() * 2 - 1) * (halfW + 60), z = z0 - 60 + rnd() * (z1 - z0 + 120), h = ground(x, z); if (h < 0.5 || h > 7.5 || rectDist(x, z, flatHW, flatHD, flatC) < 2) continue;
      const s = steep(x, z, h); if (s > 0.45) continue; n++; const high = ease((h - 2.5) / 4);
      trees.push(place('tree', { kind: high > 0.35 || rnd() < 0.25 ? 'pine' : 'round', scale: (0.85 + rnd() * 0.7) * (1 - high * 0.35), fruit: rnd() < 0.4 }, x, h - 0.1 - s * 0.9, z, rnd() * 6.3)); }
    // Mushrooms grow in the grass round the edge of the village, most of them near a tree. Bruk picks them when things are quiet, and they grow back.
    const mushrooms = [];
    for (let i = 0, n = 0; i < 4000 && n < 34; i++) { const near = trees[Math.floor(rnd() * Math.min(trees.length, 64))], x = near.position.x + (rnd() - 0.5) * 5, z = near.position.z + (rnd() - 0.5) * 5;
      if (!free(x, z) || Math.hypot(x - near.position.x, z - near.position.z) < 1.2) continue; n++; const m = place('mushroom', { kind: ['bolete', 'caps', 'bolete', 'funnel'][n % 4], seed: n }, x, 0, z, rnd() * 6.3); m.userData.back = 0; mushrooms.push(m); }
    const benches = [[-1, 0.2], [1, 0.55], [-1, 0.85]].map(([side, f]) => place('bench', {}, side * (widest / 2 + 7.5), 0, depth * f));
    const lamps = []; for (let z = 0; z <= depth; z += ROW_GAP * 2) lamps.push(place('lamp', {}, widest / 2 + 4.0, 0, z + ROW_GAP / 2));
    // Night lights. Each lamp throws a warm pool on the ground and has a halo round its head.
    // Fairy lights come out after dark: small glowing motes in soft colours that drift and bob among the trees and flowers, each trailing a fainter one.
    const glowTex = kit.tex('glow'), glowMat = (colour) => new THREE.SpriteMaterial({ map: glowTex, color: colour, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, fog: false });
    const pools = lamps.map((l) => { const m = new THREE.Mesh(kit.geo.pad, new THREE.MeshBasicMaterial({ map: glowTex, color: '#ffd98a', transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending })); m.scale.set(4.2, 1, 4.2); m.position.set(l.position.x, 0.1, l.position.z); m.renderOrder = 3; scene.add(m);
      const halo = new THREE.Sprite(glowMat('#ffe2a0')); halo.scale.setScalar(2.4); halo.position.set(l.position.x, 1.6, l.position.z); scene.add(halo); return [m, halo]; });
    const fairies = [], FAIRY = ['#9fe8ff', '#ffb3f0', '#b9ffb0', '#fff2a0', '#c9b8ff'];
    for (let i = 0; i < 70; i++) { const near = i % 3 === 0 && blooms.length ? blooms[Math.floor(rnd() * blooms.length)] : trees[Math.floor(rnd() * trees.length)], colour = FAIRY[i % FAIRY.length];
      const f = new THREE.Sprite(glowMat(colour)), tail = new THREE.Sprite(glowMat(colour)); scene.add(f, tail);
      fairies.push({ f, tail, y0: near.position.y, x: near.position.x + (rnd() - 0.5) * 3, z: near.position.z + (rnd() - 0.5) * 3, ph: rnd() * 60, r: 1.2 + rnd() * 2.6, h: 0.9 + rnd() * 2.2, v: 0.5 + rnd() * 0.8, size: 0.8 + rnd() * 0.7 }); }
    // Clouds drift high across the whole sky and wrap round; each throws a real shadow that slides over the land and drapes across the hills.
    const clouds = [], SKYW = Math.PI * PLANET * 0.95;   // clouds ride low round the planet, anywhere on it
    for (let i = 0; i < 14; i++) { const g = place('cloud', { seed: 11 + i }, (rnd() * 2 - 1) * SKYW, 30 + rnd() * 16, mid + (rnd() * 2 - 1) * SKYW * 0.8), s = 1.5 + rnd() * 1.5; g.scale.setScalar(s);
      g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); g.userData.v = 1.1 + rnd() * 1.6; clouds.push(g); }
    const birds = []; for (let i = 0; i < 7; i++) { const b = place('bird', {}, 0, 20, mid); b.userData.k = i; birds.push(b); }

