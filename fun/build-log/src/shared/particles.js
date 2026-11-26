// Chunky toon particles: little puffs (spheres) and chips (boxes) that pop, drift and shrink away.
// One pool per scene, drawn as two instanced meshes, so hundreds of particles cost two draw calls.
const FX = {
  // Each effect: shape, colours (CSS variable names), and how a particle is born. Units are scene units and seconds.
  // They are kept apart by shape, colour and motion, so each reads as its own thing at a glance:
  dust: { shape: 'puff', colours: ['--w-path', '--w-wood'], life: [0.7, 1.1], size: [0.26, 0.46], speed: [0.5, 1.2], up: [0.2, 0.7], gravity: -0.25, spread: 0.6, grow: 1.9 },                                    // tan clouds rolling out low
  chips: { shape: 'chip', colours: ['--w-wood', '--w-trunk'], life: [0.7, 1.1], size: [0.14, 0.24], speed: [1.0, 2.2], up: [2.4, 4.0], gravity: 9, spread: 0.15, grow: 1, spin: 10 },                                // brown blocks flung up, falling fast
  sparks: { shape: 'chip', colours: ['--w-live', '--series-a', '--w-dome'], life: [0.35, 0.6], size: [0.07, 0.13], speed: [2.6, 4.6], up: [0.6, 2.2], gravity: 6, spread: 0.08, grow: 0.3, spin: 4, flat: true },   // quick yellow streaks shooting sideways
  mail: { shape: 'chip', colours: ['--w-cream', '--series-b'], life: [1.2, 1.7], size: [0.2, 0.28], speed: [0.1, 0.5], up: [1.6, 2.3], gravity: -0.4, spread: 0.2, grow: 1, spin: 1.5, flat: true },                  // pale envelopes floating straight up
  ticks: { shape: 'chip', colours: ['--ui-success', '--w-leaf'], life: [0.9, 1.4], size: [0.16, 0.24], speed: [0.8, 1.8], up: [2.6, 3.8], gravity: 4, spread: 0.2, grow: 1, spin: 6, flat: true },                  // green tiles popping up
  fume: { shape: 'puff', colours: ['--w-ink', '--w-fruit'], life: [0.7, 1.1], size: [0.14, 0.24], speed: [0.2, 0.6], up: [1.2, 2.0], gravity: -0.6, spread: 0.18, grow: 1.7 },                                       // dark and red puffs steaming off the head
  confetti: { shape: 'chip', colours: ['--series-a', '--series-b', '--series-c', '--series-d', '--w-dome', '--w-live', '--ui-success'], life: [1.8, 3.0], size: [0.2, 0.36], speed: [1.2, 3.6], up: [5.0, 8.5], gravity: 6, spread: 0.5, grow: 1, spin: 12, flat: true },
  sparkle: { shape: 'puff', colours: ['--w-live', '--w-cream'], life: [0.7, 1.2], size: [0.16, 0.28], speed: [1.0, 2.6], up: [1.4, 3.2], gravity: 1.4, spread: 0.4, grow: 0.3 },                                    // gold beads bursting outward
  smoke: { shape: 'puff', colours: ['--w-stone', '--w-cloud'], life: [2.4, 3.6], size: [0.22, 0.34], speed: [0.04, 0.16], up: [0.6, 0.9], gravity: -0.14, spread: 0.04, grow: 3.0 },                                  // slow grey puffs rising from chimneys
  poof: { shape: 'puff', colours: ['--w-cloud', '--w-cream'], life: [0.45, 0.75], size: [0.3, 0.5], speed: [1.2, 2.2], up: [0.1, 0.7], gravity: 0, spread: 0.25, grow: 1.9 },                                         // a white ring when a critter arrives
};

function makeParticles(kit, scene, capacity) {
  const N = capacity || 900, dummy = new THREE.Object3D(), colour = new THREE.Color(), rnd = Math.random;
  const pool = (geo) => {
    const mesh = new THREE.InstancedMesh(geo, new THREE.MeshToonMaterial({ gradientMap: kit.toon().gradientMap }), N);
    mesh.count = 0; mesh.frustumCulled = false; mesh.castShadow = false; mesh.receiveShadow = false; mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.setColorAt(0, colour.set('#ffffff')); scene.add(mesh); return { mesh, live: [] };
  };
  const pools = { puff: pool(new THREE.SphereGeometry(1, 10, 8)), chip: pool(new THREE.BoxGeometry(1, 1, 1)) };
  const between = (r) => r[0] + rnd() * (r[1] - r[0]);
  return {
    // Start `n` particles of effect `kind` at a point.
    emit(kind, x, y, z, n) {
      const f = FX[kind], p = pools[f.shape];
      for (let i = 0; i < (n || 1) && p.live.length < N; i++) {
        const a = rnd() * Math.PI * 2, sp = between(f.speed);
        p.live.push({ f, x: x + (rnd() - 0.5) * f.spread * 2, y: y + rnd() * f.spread * 0.4, z: z + (rnd() - 0.5) * f.spread * 2, vx: Math.cos(a) * sp, vy: between(f.up), vz: Math.sin(a) * sp,
          age: 0, life: between(f.life), size: between(f.size), c: kit.css(f.colours[Math.floor(rnd() * f.colours.length)]), rx: rnd() * 6, ry: rnd() * 6, spin: (f.spin || 0) * (rnd() - 0.5) * 2 });
      }
    },
    // Move everything on by `dt` seconds and redraw.
    update(dt) {
      for (const key in pools) {
        const p = pools[key]; let n = 0;
        for (const q of p.live) {
          q.age += dt; if (q.age >= q.life) continue;
          q.vy -= q.f.gravity * dt; q.x += q.vx * dt; q.y += q.vy * dt; q.z += q.vz * dt; if (q.y < 0.05 && q.f.gravity > 0) { q.y = 0.05; q.vy *= -0.35; q.vx *= 0.6; q.vz *= 0.6; }
          const k = q.age / q.life, pop = Math.min(1, k * 8), fade = k > 0.6 ? 1 - (k - 0.6) / 0.4 : 1, s = q.size * pop * fade * (1 + (q.f.grow - 1) * k);
          dummy.position.set(q.x, q.y, q.z); dummy.rotation.set(q.rx + q.spin * q.age, q.ry + q.spin * q.age * 0.7, 0); dummy.scale.set(s, q.f.flat ? s * 0.25 : s, s); dummy.updateMatrix();
          p.mesh.setMatrixAt(n, dummy.matrix); p.mesh.setColorAt(n, colour.set(q.c)); p.live[n++] = q;
        }
        p.live.length = n; p.mesh.count = n; p.mesh.instanceMatrix.needsUpdate = true; if (p.mesh.instanceColor) p.mesh.instanceColor.needsUpdate = true;
      }
    },
    get count() { return pools.puff.live.length + pools.chip.live.length; },
  };
}
