// Bruk, the person the agents work for: a small figure in the same toy style, with dreadlocks on top and shaved sides.
// He turns up beside the orchestrator when he sends a message.
ASSETS.person = {
  title: 'Bruk', controls: { mode: ['cheer', 'party', 'talk', 'idle', 'walk', 'run', 'sit', 'admire', 'gaze', 'crouch', 'wave', 'tinker', 'sketch', 'saw', 'stir'], top: ['stripes', '--p-hoodie', '--series-a', '--series-d'] },
  build(kit, o) {
    const { sph, cyl } = kit.geo, skin = '--p-skin', hair = '--p-hair', striped = !o.top || o.top === 'stripes', g = new THREE.Group(), inner = new THREE.Group(), p = (geo, m, sx, sy, sz, x, y, z) => kit.mesh(geo, m, sx, sy, sz, x, y, z);
    const top = striped ? kit.stripeMat || (kit.stripeMat = kit.toon({ color: 0xffffff, map: kit.tex('stripes') })) : kit.mat(o.top);
    // legs, shoes, a striped tee (or a plain top), arms that turn at the shoulder
    inner.add(p(cyl, '--p-pants', 0.075, 0.3, 0.075, -0.11, 0.2, 0), p(cyl, '--p-pants', 0.075, 0.3, 0.075, 0.11, 0.2, 0), p(sph, '--w-cream', 0.1, 0.055, 0.15, -0.11, 0.05, 0.04), p(sph, '--w-cream', 0.1, 0.055, 0.15, 0.11, 0.05, 0.04),
      p(sph, top, 0.27, 0.3, 0.22, 0, 0.58, 0), p(sph, skin, 0.1, 0.07, 0.1, 0, 0.84, 0));
    const arms = [-1, 1].map((s) => { const a = new THREE.Group(); a.position.set(s * 0.26, 0.74, 0); a.add(p(sph, top, 0.085, 0.12, 0.095, s * 0.04, -0.09, 0), p(sph, skin, 0.062, 0.13, 0.066, s * 0.055, -0.22, 0.005), p(sph, skin, 0.062, 0.062, 0.062, s * 0.06, -0.32, 0.01)); a.userData.side = s; inner.add(a); return a; });
    const head = new THREE.Group(); head.position.y = 1.08; inner.add(head);
    head.add(p(sph, skin, 0.3, 0.29, 0.28, 0, 0, 0), p(sph, skin, 0.05, 0.07, 0.04, -0.3, -0.02, 0), p(sph, skin, 0.05, 0.07, 0.04, 0.3, -0.02, 0),
      p(sph, '@ink', 0.04, 0.05, 0.03, -0.115, 0.03, 0.262), p(sph, '@ink', 0.04, 0.05, 0.03, 0.115, 0.03, 0.262), p(sph, '--w-cream', 0.013, 0.018, 0.01, -0.105, 0.05, 0.288), p(sph, '--w-cream', 0.013, 0.018, 0.01, 0.125, 0.05, 0.288));
    [-1, 1].forEach((s) => { const b = p(kit.geo.box, hair, 0.1, 0.022, 0.02, s * 0.12, 0.105, 0.265); b.position.y = 0.115; head.add(b); });   // eyebrows, level and a little raised
    // a short full beard from ear to ear, a moustache, and a wide smile
    const G = ASSETS.person.geo || (ASSETS.person.geo = { beard: new THREE.SphereGeometry(1, 20, 8, Math.PI * 0.04, Math.PI * 0.92, Math.PI * 0.67, Math.PI * 0.33) });
    { const beard = p(G.beard, '--p-fade', 0.311, 0.301, 0.291, 0, 0, 0); beard.userData.plain = true; beard.castShadow = false; head.add(beard); }   // cropped as close as the sides, and joined to them at the ear
    head.add(p(sph, '--p-fade', 0.1, 0.02, 0.025, 0, -0.088, 0.277),);
    G.smile = G.smile || new THREE.TorusGeometry(1, 0.16, 6, 14, Math.PI);   // a thin curved line for the mouth: no lips, no teeth
    { const smile = p(G.smile, hair, 0.05, 0.036, 0.05, 0, -0.112, 0.276, false); smile.rotation.z = Math.PI; smile.userData.plain = true; head.add(smile); }
    // shaved sides: a close crop low on each side and round the back
    // It is a thin band that hugs the head from temple to temple round the back, so nothing sticks out.
    G.crop = G.crop || new THREE.SphereGeometry(1, 28, 8, Math.PI * 0.8, Math.PI * 1.4, Math.PI * 0.2, Math.PI * 0.48);
    { const crop = p(G.crop, '--p-fade', 0.311, 0.301, 0.291, 0, 0, 0); crop.userData.plain = true; crop.castShadow = false; head.add(crop); }
    // dreadlocks on top, over a cap of hair
    head.add(p(sph, hair, 0.215, 0.1, 0.25, 0, 0.235, -0.03));
    const locks = [], rnd = kit.rng(31), down = new THREE.Vector3(0, -1, 0), dir = new THREE.Vector3();
    // A lock leaves the head in its own direction for a short way, then bends and hangs nearly straight down, so long ones drape and do not stick out.
    const hang = new THREE.Vector3(), inv = new THREE.Quaternion();
    const lock = (x, y, z, dx, dy, dz, len) => { const pivot = new THREE.Group(); pivot.position.set(x, y, z); dir.set(dx, dy, dz).normalize(); pivot.quaternion.setFromUnitVectors(down, dir);
      const first = Math.min(len, 0.17), rest = len - first; pivot.add(p(cyl, hair, 0.038, first, 0.038, 0, -first / 2, 0), p(sph, hair, 0.04, 0.04, 0.04, 0, 0, 0), p(sph, hair, 0.04, 0.04, 0.04, 0, -first, 0));
      if (rest > 0.02) { const bend = new THREE.Group(); bend.position.y = -first; hang.copy(dir).multiplyScalar(0.22).add(down).normalize().applyQuaternion(inv.copy(pivot.quaternion).invert()); bend.quaternion.setFromUnitVectors(down, hang);
        bend.add(p(cyl, hair, 0.038, rest, 0.038, 0, -rest / 2, 0), p(sph, hair, 0.042, 0.042, 0.042, 0, -rest, 0)); pivot.add(bend); }
      pivot.userData.rest = pivot.quaternion.clone(); pivot.userData.k = locks.length; head.add(pivot); locks.push(pivot); };
    // Tied back: locks run from the hairline over the crown to the back of the head, then hang together down the back as a ponytail.
    const up = new THREE.Vector3(0, 1, 0), A = new THREE.Vector3(), B = new THREE.Vector3(), tie = [0, 0.13, -0.3];
    const seg = (a, b) => { A.fromArray(a); B.fromArray(b); const len = A.distanceTo(B), m = p(cyl, hair, 0.04, len, 0.04, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2); m.quaternion.setFromUnitVectors(up, B.sub(A).normalize()); head.add(m, p(sph, hair, 0.042, 0.042, 0.042, a[0], a[1], a[2]), p(sph, hair, 0.042, 0.042, 0.042, b[0], b[1], b[2])); };
    for (let k = 0; k < 7; k++) { const f = k / 6 - 0.5, x = f * 0.42, edge = Math.abs(f) * 2; seg([x, 0.265 - edge * 0.07, 0.115 - edge * 0.07], [x * 0.9, 0.325 - edge * 0.06, -0.06]); seg([x * 0.9, 0.325 - edge * 0.06, -0.06], [x * 0.55, 0.26 - edge * 0.03, -0.22]); seg([x * 0.55, 0.26 - edge * 0.03, -0.22], tie); }
    for (let k = 0; k < 9; k++) { const a = k * 2.4, r = k ? 0.035 + (k % 3) * 0.012 : 0; lock(tie[0] + Math.cos(a) * r, tie[1] - 0.03, tie[2] - 0.04 + Math.sin(a) * r * 0.6, Math.cos(a) * 0.12, -0.75, -0.55 + Math.sin(a) * 0.08, 0.5 + rnd() * 0.2); }
    inner.scale.setScalar(1.2); kit.outline(inner, 0.015); g.add(kit.blob(0.48), inner);
    g.userData = { inner, head, arms, locks, kit, eyes: [head.children[3], head.children[4]], legs: [inner.children[0], inner.children[1]], shoes: [inner.children[2], inner.children[3]], q: new THREE.Quaternion(), e: new THREE.Euler() }; ASSETS.person.animate(g, { mode: o.mode || 'idle', now: 0, moving: false }); return g;
  },
  // mode: 'talk' | 'cheer' | 'party' | 'walk' | 'run' | 'idle', and for his own time 'sit' | 'admire' | 'gaze' | 'crouch' | 'wave'.
  // Cheering and idling each cycle through a few different moves, so he is never doing one thing for long.
  animate(g, s) {
    const u = g.userData, still = s.moving === false, t = still ? 0 : s.now || 0, m = s.mode, run = m === 'run', walk = m === 'walk' || run, talk = m === 'talk', party = m === 'party', cheer = m === 'cheer' || party, idle = m === 'idle';
    const i = u.inner, L = u.arms[0], R = u.arms[1], pace = run ? 0.021 : 0.013, step = Math.sin(t * pace), beat = Math.abs(Math.sin(t * (party ? 0.016 : 0.011)));
    const sit = m === 'sit', slice = cheer ? 1700 : 3200, move = m === 'wave' ? 3 : Math.floor(t / slice) % 4, into = (t % slice) / slice;      // which move he is on, and how far through it
    let y = Math.sin(t * 0.003) * 0.012 + 0.012, lean = 0, tilt = 0, turn = 0, headX = 0, headY = 0, headZ = 0, swing = Math.sin(t * 0.004) * 0.03;
    L.rotation.set(0, 0, 0); R.rotation.set(0, 0, 0);
    if (walk) { y = Math.abs(step) * (run ? 0.16 : 0.1); tilt = step * 0.08; lean = run ? 0.24 : 0.1; L.rotation.x = step * (run ? 1.1 : 0.7); R.rotation.x = -step * (run ? 1.1 : 0.7); swing = step * (run ? 0.3 : 0.16); }
    else if (talk) { R.rotation.z = 2.3 + Math.sin(t * 0.012) * 0.35; L.rotation.z = -0.25 - Math.sin(t * 0.006) * 0.12; headZ = Math.sin(t * 0.004) * 0.08; headX = Math.sin(t * 0.007) * 0.05 - 0.04; swing = Math.sin(t * 0.004) * 0.06; }
    else if (cheer) {
      headX = -0.18; swing = beat * 0.14;
      if (party || move === 0) { y = beat * (party ? 0.3 : 0.18); L.rotation.z = -2.5 - Math.sin(t * 0.022) * 0.3; R.rotation.z = 2.5 - Math.sin(t * 0.022) * 0.3; if (party) turn = (t * 0.006) % (Math.PI * 2); }   // jumping with both arms up; at a merge, spinning too
      else if (move === 1) { y = beat * 0.07; R.rotation.z = 2.2 + Math.sin(t * 0.02) * 0.6; L.rotation.z = -0.5; tilt = Math.sin(t * 0.02) * 0.05; headZ = 0.08; }                                                // fist pump
      else if (move === 2) { const c = Math.abs(Math.sin(t * 0.018)); y = beat * 0.05; L.rotation.x = R.rotation.x = -1.35; L.rotation.z = 0.15 + c * 0.5; R.rotation.z = -0.15 - c * 0.5; headX = 0.05; }       // clapping
      else { turn = into < 0.6 ? into / 0.6 * Math.PI * 2 : 0; y = into < 0.6 ? Math.sin(into / 0.6 * Math.PI) * 0.22 : beat * 0.06; L.rotation.z = -1.5; R.rotation.z = 1.5; swing = 0.3; }                    // a spin with arms out
    } else if (sit) { y = -0.03 + Math.sin(t * 0.003) * 0.008; lean = -0.1 + Math.sin(t * 0.0012) * 0.04; headY = Math.sin(t * 0.0009) * 0.6; headX = Math.sin(t * 0.0006) * 0.12 - 0.05; L.rotation.x = R.rotation.x = -0.35; L.rotation.z = -0.25; R.rotation.z = 0.25; }   // on a bench, legs out, looking about
    else if (m === 'admire') { headX = -0.38; headY = Math.sin(t * 0.001) * 0.2; L.rotation.z = -0.75; R.rotation.z = 0.75; lean = -0.06; tilt = Math.sin(t * 0.0012) * 0.03; }                                                        // hands on hips, looking up at a building
    else if (m === 'gaze') { R.rotation.set(-0.7, 0, 2.75); L.rotation.z = -0.7; headY = Math.sin(t * 0.0008) * 0.35; tilt = Math.sin(t * 0.001) * 0.03; }                                                                              // a hand shading his eyes, looking out to sea
    else if (m === 'tinker') { headX = 0.22; headY = Math.sin(t * 0.0013) * 0.25; lean = 0.1; L.rotation.x = -1.25 + Math.sin(t * 0.009) * 0.18; R.rotation.x = -1.25 + Math.sin(t * 0.011 + 1) * 0.18; L.rotation.z = 0.2; R.rotation.z = -0.2; y += Math.abs(Math.sin(t * 0.004)) * 0.012; }   // both hands in the machine
    else if (m === 'sketch') { headX = 0.3; headZ = Math.sin(t * 0.0015) * 0.06; lean = 0.14; R.rotation.x = -1.15 + Math.sin(t * 0.013) * 0.07; R.rotation.z = -0.2 + Math.sin(t * 0.008) * 0.22; L.rotation.x = -0.9; L.rotation.z = 0.35; }                                                  // drawing, one hand steadying the sheet
    else if (m === 'saw') { const push = Math.sin(t * 0.012); headX = 0.25; lean = 0.2 + push * 0.04; R.rotation.x = -0.95 + push * 0.5; R.rotation.z = -0.1; L.rotation.x = -1.1; L.rotation.z = 0.3; swing = push * 0.08; }   // sawing a board, the other hand holding it down
    else if (m === 'stir') { headX = 0.22; headY = Math.sin(t * 0.0012) * 0.2; lean = 0.08; R.rotation.x = -1.2 + Math.sin(t * 0.007) * 0.14; R.rotation.z = -0.15 + Math.cos(t * 0.007) * 0.2; L.rotation.z = -0.55; y += Math.sin(t * 0.0035) * 0.01; }      // stirring a pot, a hand on his hip
    else if (m === 'crouch') { y = -0.2; lean = 0.38; headX = 0.25; R.rotation.x = -1.0 - Math.sin(t * 0.004) * 0.15; L.rotation.z = -0.3; }                                                                                             // bending down to the flowers
    else if (idle || m === 'wave') {
      headY = Math.sin(t * 0.0011) * 0.5; headZ = Math.sin(t * 0.0017) * 0.07; tilt = Math.sin(t * 0.0013) * 0.04;
      if (move === 1) { const up = Math.sin(Math.min(1, into * 1.6) * Math.PI); L.rotation.z = -2.7 * up; R.rotation.z = 2.7 * up; lean = -0.12 * up; headX = -0.2 * up; y += up * 0.04; }                         // a stretch
      else if (move === 2) { L.rotation.x = -1.25; L.rotation.z = 0.5; headX = 0.3; headY = -0.25; y += Math.abs(Math.sin(t * 0.012)) * 0.015; }                                                                  // checking his wrist
      else if (move === 3) { R.rotation.z = 2.4 + Math.sin(t * 0.013) * 0.4; headZ = 0.1; }                                                                                                                      // a wave
    }
    // Sitting swings the legs out in front; everything else stands on them.
    u.legs.forEach((leg, k) => { const sd = k ? 1 : -1, kick = sit ? Math.sin(t * 0.004 + k * 2) * 0.03 : 0; leg.rotation.x = sit ? -Math.PI / 2 : 0; leg.position.set(sd * 0.11, sit ? 0.36 + kick : 0.2, sit ? 0.16 : 0);
      u.shoes[k].position.set(sd * 0.11, sit ? 0.37 + kick : 0.05, sit ? 0.36 : 0.04); u.shoes[k].rotation.x = sit ? -1.2 : 0; });
    i.position.y = y; i.rotation.set(lean, turn, tilt); u.head.rotation.set(headX, headY, headZ);
    for (const l of u.locks) { u.e.set(swing * Math.cos(l.userData.k * 1.7) - lean * 0.6, 0, swing * Math.sin(l.userData.k * 1.3 + 1)); l.quaternion.copy(l.userData.rest).multiply(u.q.setFromEuler(u.e)); }   // the ponytail swings behind every movement
    { const blink = !still && ((t * 0.00027) % 1) < 0.035; for (const e of u.eyes) e.scale.y = blink ? 0.008 : e.userData.open || (e.userData.open = e.scale.y); }
    const icon = talk ? 'chat' : cheer ? 'cheer' : null;   // a speech bubble when he is talking, a star when he is cheering the agents on
    if (icon && !u.bubble) { u.bubble = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthWrite: false })); u.bubble.scale.set(0.7, 0.7, 1); g.add(u.bubble); }
    if (icon && u.shown !== icon) { u.shown = icon; u.bubble.material.map = u.kit.icon(icon); u.bubble.material.needsUpdate = true; }
    if (u.bubble) { u.bubble.visible = !!icon; u.bubble.position.set(0.1, 2.35 + y * 1.2 + Math.sin(t * 0.004) * 0.05, 0); }
  },
};
