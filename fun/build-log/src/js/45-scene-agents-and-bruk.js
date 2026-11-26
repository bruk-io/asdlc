    /* ---- critters: one per agent run (src/assets/critter.js), with an unseen box around each so it is easy to point at ---- */
    agents.forEach((a) => {
      a.slot = a.tw.agents.indexOf(a); a.evT = []; a.evK = []; a.errT = []; { let at = a.t0; (a.ev || '').replace(/(\d+)([a-z])/g, (m, gap, kind) => { at += +gap; if (kind === 'x') a.errT.push(at); else { a.evT.push(at); a.evK.push(kind); } }); }
      const c = a.critter = kit.make('critter', { model: a.model, job: a.ph, seed: a.slot });
      const hit = kit.mesh(box, new THREE.MeshBasicMaterial({ visible: false }), 0.95, 1.7, 0.95, 0, 0.85, 0, false); hit.userData = { agent: a, critter: true }; c.add(hit); pickables.push(hit);
      c.visible = false; scene.add(c);
    });
    const fx = makeParticles(kit, scene, 700); let fxClock = 0, fxTick = 0, followAgent = null; const lightDir = new THREE.Vector3(), lightWas = new THREE.Vector3(), sunVil = new THREE.Vector3(), moonVil = new THREE.Vector3(), unframe = new THREE.Quaternion(); let lightAt = 0;


    // What a critter should be acting out at clock time t. During replay many tool calls pass each second, so this takes the calls in a window
    // about a second of viewing long and picks the kind that stands out, weighting the rarer kinds up so they get seen.
    const ACT_WEIGHT = { r: 1, s: 0.7, w: 1.6, g: 1.8, b: 2, z: 1.2, n: 5, d: 5, k: 5, o: 6 };
    function actionAt(a, t) {
      const T = a.evT; let lo = 0, hi = T.length; while (lo < hi) { const m = (lo + hi) >> 1; if (T[m] <= t) lo = m + 1; else hi = m; }
      const last = lo - 1; if (last < 0) return null;
      const span = S.playing ? Math.max(90, S.speed * 1.3) : 0, score = {}; let best = null;
      for (let k = last; k >= 0 && T[k] >= t - span; k--) { const kind = a.evK[k]; score[kind] = (score[kind] || 0) + (ACT_WEIGHT[kind] || 0); if (best === null || score[kind] > score[best]) best = kind; }
      if (best === null && t - T[last] < 300) best = a.evK[last];
      return best && ASSETS.critter.KIND[best] || null;
    }
    // Did one of this agent's tool calls fail just before clock time t? "Just" is about a second of viewing during replay, two minutes when paused.
    function failedAt(a, t) { const T = a.errT, span = S.playing ? Math.max(60, S.speed * 0.9) : 120; let lo = 0, hi = T.length; while (lo < hi) { const m = (lo + hi) >> 1; if (T[m] <= t) lo = m + 1; else hi = m; } return lo > 0 && t - T[lo - 1] <= span; }

    /* ---- Bruk: he walks up to the orchestrator's building when he sends a message, and leaves a while after his last one ---- */
    const ownerData = D.owner || { name: 'You', msgs: [] }, visits = [], mainTower = towers.find((tw) => tw.agents.some((a) => a.kind === 'Main')) || towers[0];
    for (const m of ownerData.msgs) { const v = visits[visits.length - 1]; if (v && m - v[1] < 1500) v[1] = m + 600; else visits.push([m - 240, m + 600]); }
    const owner = place('person', {}, mainTower.x - 2.2, 0.07, mainTower.z + 2.4); owner.visible = false;
    { const tagS = sign(ownerData.name, 0.5); scene.remove(tagS); tagS.position.set(0, 2.05, 0); owner.add(tagS); owner.userData.tag = tagS; }
    // He is always somewhere. Around his own messages he stands by the orchestrator and talks. The rest of the time he follows the build:
    // he walks to a building that is being worked on, cheers the crew on for a few seconds, then moves to another. With nothing going on he waits at home.
    let cheerFor = null, cheerUntil = 0, spot = 0, partyFor = null, partyUntil = 0; owner.visible = true;
    // Where he stands at a building: one of three places round the front, picked afresh each time.
    const SPOTS = [[-FOOT / 2 - 1.7, FOOT / 2 + 1.5], [FOOT / 2 + 1.7, FOOT / 2 + 1.5], [-FOOT / 2 - 2.0, 0.2]];
    // His own time: whenever nothing is being built and he has nothing to say, and after the build is over. A loop of things he likes doing,
    // picked at random and never twice running, with foraging the most likely. Each is a place to go, a way to face, a pose to hold and how long to hold it.
    const yard = { x: -widest / 2 - 9.5, z: ROW_GAP * 1.6 };   // a patch of open grass beside the village, clear of the rows and paths
    const printer = place('printer', {}, yard.x - 2.4, 0, yard.z, 0.5), rack = place('rack', {}, yard.x, 0, yard.z - 2.0, 0.2), desk = place('desk', {}, yard.x + 2.4, 0, yard.z + 0.4, -0.4),
      workbench = place('workbench', {}, yard.x - 1.6, 0, yard.z + 3.0, 0.15), stove = place('stove', {}, yard.x + 1.8, 0, yard.z + 3.2, -0.2);
    const at = (prop, back, mode, ms) => { const a = prop.rotation.y; return { x: prop.position.x + Math.sin(a) * back, z: prop.position.z + Math.cos(a) * back, fx: prop.position.x, fz: prop.position.z, mode, ms }; };
    let doing = null, lastKind = '';
    const ROUTINE = {
      forage() { for (const m of mushrooms) if (!m.visible && performance.now() > m.userData.back) m.visible = true;
        let best = null, near = 1e9; for (const m of mushrooms) { if (!m.visible) continue; const d = Math.hypot(m.position.x - owner.position.x, m.position.z - owner.position.z); if (d < near) { near = d; best = m; } }
        if (!best) return ROUTINE.bench();
        return { x: best.position.x + 0.45, z: best.position.z + 0.3, fx: best.position.x, fz: best.position.z, mode: 'crouch', ms: 2200, done() { best.visible = false; best.userData.back = performance.now() + 50000 + Math.random() * 40000; fx.emit('sparkle', best.position.x, 0.5, best.position.z, 8); } }; },
      print() { return at(printer, 1.1, Math.random() < 0.5 ? 'tinker' : 'admire', 9000); },                // watching a print, or fiddling with it
      homelab() { return at(rack, 1.0, 'tinker', 8000); },                                                 // tinkering with the rack
      design() { return at(desk, 0.95, 'sketch', 9000); },
      wood() { return at(workbench, 0.85, 'saw', 9000); },                                                  // woodworking
      cook() { return at(stove, 0.85, 'stir', 9000); },                                                    // cooking, with whatever he foraged                                                 // sketching a part to print
      bench() { const b = benches[firstDo && !doing ? 0 : Math.floor(Math.random() * benches.length)]; return { x: b.position.x, z: b.position.z + 0.08, fx: b.position.x, fz: b.position.z + 10, mode: 'sit', ms: 11000 }; },
      admire() { const done = towers.filter((w) => w.top > 1); const w = done[Math.floor(Math.random() * done.length)] || mainTower; return { x: w.x - 0.4, z: w.z + FOOT / 2 + 3.2, fx: w.x, fz: w.z, mode: 'admire', ms: 6000 }; },
      shore() { const side = Math.random() < 0.5 ? -1 : 1, z = z0 + 6 + Math.random() * (z1 - z0 - 12); return { x: side * (halfW - 2.2), z, fx: side * (halfW + 40), fz: z, mode: 'gaze', ms: 7500 }; },
      wave() { return { x: mainTower.x - 3, z: mainTower.z + FOOT / 2 + 4, cam: true, mode: 'wave', ms: 4500 }; },
    };
    const ODDS = ['forage', 'forage', 'forage', 'print', 'print', 'wood', 'wood', 'cook', 'cook', 'homelab', 'design', 'bench', 'admire', 'shore', 'wave'];
    const firstDo = (/do=(\w+)/.exec(location.hash) || [])[1];   // #do=bench starts his free time on one activity, for the screenshot tool
    function ownerFreeTime(now, dt) {
      if (!doing && ROUTINE[firstDo]) { lastKind = firstDo; doing = ROUTINE[firstDo](); doing.since = 0; }
      if (!doing || (doing.since && now > doing.since + doing.ms)) { if (doing && doing.done) doing.done(); const kinds = ODDS.filter((k) => k !== lastKind || k === 'forage'); lastKind = kinds[Math.floor(Math.random() * kinds.length)]; doing = ROUTINE[lastKind](); doing.since = 0; }
      const dx = doing.x - owner.position.x, dz = doing.z - owner.position.z, dist = Math.hypot(dx, dz), arrived = dist < 0.08;
      if (!owner.userData.placed) { owner.position.set(doing.x, 0.07, doing.z); owner.userData.placed = true; }
      else if (!arrived) { const step = Math.min(dist, (dist > 18 ? 11 : 4.2) * dt); owner.position.x += dx / dist * step; owner.position.z += dz / dist * step; const px = owner.position.x, pz = owner.position.z; steerClear(doing.x, doing.z); owner.lookAt(owner.position.x + (owner.position.x - px) * 6 + dx / dist, owner.position.y, owner.position.z + (owner.position.z - pz) * 6 + dz / dist); }
      else { if (!doing.since) doing.since = now; if (doing.cam) owner.lookAt(camera.position.x, 0.07, camera.position.z); else owner.lookAt(doing.fx, 0.07, doing.fz); }
      const mode = arrived ? doing.mode : dist > 18 ? 'run' : 'walk';
      owner.position.y = 0.07 + Math.max(0, ground(owner.position.x, owner.position.z));
      ASSETS.person.animate(owner, { mode, now, moving: true }); owner.userData.tag.position.y = mode === 'party' ? 3.2 : 2.05;
      ASSETS.printer.animate(printer, { now }); ASSETS.rack.animate(rack, { now }); ASSETS.stove.animate(stove, { now });
    }
    // Keep him out of the buildings: if a step lands inside one's keep-out circle, slide him back to its edge and a little round it.
    const KEEP = FOOT * 0.71 + 0.55;
    // The same for any walker: given where it is and where it is heading, return a place outside every building's keep-out circle.
    function clearOf(x, z, tx, tz, keep) {
      for (const w of towers) { const dx = x - w.x, dz = z - w.z, d = Math.hypot(dx, dz); if (d >= keep || Math.hypot(tx - w.x, tz - w.z) < keep) continue;
        const nx = d > 1e-3 ? dx / d : 0, nz = d > 1e-3 ? dz / d : 1, side = (tx - w.x) * -nz + (tz - w.z) * nx > 0 ? 1 : -1; x = w.x + nx * keep - nz * side * 0.08; z = w.z + nz * keep + nx * side * 0.08; }
      return [x, z];
    }
    function steerClear(tx, tz) {
      for (const w of towers) { const dx = owner.position.x - w.x, dz = owner.position.z - w.z, d = Math.hypot(dx, dz); if (d >= KEEP || Math.hypot(tx - w.x, tz - w.z) < KEEP) continue;
        const nx = d > 1e-3 ? dx / d : 1, nz = d > 1e-3 ? dz / d : 0, side = (tx - w.x) * -nz + (tz - w.z) * nx > 0 ? 1 : -1;
        owner.position.x = w.x + nx * KEEP - nz * side * 0.06; owner.position.z = w.z + nz * KEEP + nx * side * 0.06; }
    }
    function ownerParty(tw, now) { partyFor = tw; partyUntil = now + 6500; spot = Math.floor(Math.random() * 2); }   // a merge: he runs over and celebrates
    function ownerAt(t, now, moving, dt, working) {
      if (t >= tMax - 1 && !(partyFor && now < partyUntil)) return ownerFreeTime(now, dt);
      const visiting = visits.some((x) => t >= x[0] && t <= x[1]), party = partyFor && now < partyUntil, homeX = mainTower.x - FOOT / 2 - 1.5, homeZ = mainTower.z + FOOT / 2 + 1.2; let tx = homeX, tz = homeZ, face = mainTower;
      if (party) { tx = partyFor.x + SPOTS[spot][0]; tz = partyFor.z + SPOTS[spot][1]; face = partyFor; }
      else if (!visiting && working.length) {
        if (!working.includes(cheerFor) || now > cheerUntil) { const others = working.filter((w) => w !== cheerFor); cheerFor = (others.length ? others : working)[Math.floor(Math.random() * (others.length || working.length))]; cheerUntil = now + 5000 + Math.random() * 3000; spot = Math.floor(Math.random() * 3); }
        tx = cheerFor.x + SPOTS[spot][0]; tz = cheerFor.z + SPOTS[spot][1]; face = cheerFor;
      } else if (!visiting) { cheerFor = null; return ownerFreeTime(now, dt); }   // nothing going on: his own time
      doing = null;
      const dx = tx - owner.position.x, dz = tz - owner.position.z, dist = Math.hypot(dx, dz), arrived = dist < 0.08;
      if (dist > 90 || !owner.userData.placed) { owner.position.set(tx, 0.07, tz); owner.userData.placed = true; }       // a jump in time: just be there
      else if (!arrived) { const step = Math.min(dist, Math.max(party ? 14 : 6, dist * 1.3) * dt); owner.position.x += dx / dist * step; owner.position.z += dz / dist * step; const px = owner.position.x, pz = owner.position.z; steerClear(tx, tz); owner.lookAt(owner.position.x + (owner.position.x - px) * 6 + dx / dist, owner.position.y, owner.position.z + (owner.position.z - pz) * 6 + dz / dist); }
      if (arrived) owner.lookAt(face.x, 0.07, face.z);
      const span = S.playing ? Math.max(180, S.speed * 1.5) : 300, said = visiting && !party && ownerData.msgs.some((m) => m <= t && t - m <= span);
      const mode = !arrived ? (dist > 7 || party ? 'run' : 'walk') : party ? 'party' : said ? 'talk' : !visiting && cheerFor ? 'cheer' : 'idle';
      owner.position.y = 0.07 + Math.max(0, ground(owner.position.x, owner.position.z));
      ASSETS.person.animate(owner, { mode, now, moving: true }); owner.userData.tag.position.y = mode === 'talk' || mode === 'cheer' || mode === 'party' ? 3.2 : 2.05;
      ASSETS.printer.animate(printer, { now }); ASSETS.rack.animate(rack, { now }); ASSETS.stove.animate(stove, { now });
    }
