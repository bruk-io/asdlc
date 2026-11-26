    /* ---- the frame loop: everything that changes from one frame to the next ---- */
    const tmp = new THREE.Vector3(), tagEl = $('#tag'); let shadowT = NaN;
    function update(now) {
      const t = S.t; let sumX = 0, sumZ = 0, fn = 0; const working = [];
      // Particles only while the replay runs: dust and chips where work is happening, smoke from finished chimneys, confetti on a merge.
      const firstFrame = fxClock === 0;
      const dt = Math.min(0.05, Math.max(0, (now - fxClock) / 1000)), lively = S.playing && !reduced; fxClock = now;
      const beat = lively && now - fxTick > 240; if (beat) fxTick = now;
      if (t !== shadowT || S.playing) { renderer.shadowMap.needsUpdate = true; shadowT = t; }
      { const want = nightAt(S.t), next = firstFrame || Math.abs(want - night) < 0.004 ? want : night + (want - night) * Math.min(1, dt * 3); if (next !== night) setNight(next); }
      const pulse = reduced ? 1 : 0.8 + Math.sin(now * 0.006) * 0.25;
      const crowd = [];
      for (const tw of towers) {
        let y = 0.07, building = false, last = 0;
        for (const a of tw.agents) {
          const f = frac(a, t), here = present(a, t), sleeping = here && asleep(a, t), work = here && !sleeping; last = Math.max(last, a.t1);
          for (const m of a.segs) {
            const h = m.userData.h * f; m.visible = h > 0.004;
            if (m.visible) {
              m.scale.set(1, h, 1); m.position.set(tw.x, y + h / 2, tw.z); y += h; const u = m.userData;
              ASSETS.storey.fit(m, h);
              if (work) { u.side.emissive.copy(liveCol); u.side.emissiveIntensity = 1.1 * pulse; } else { u.side.emissive.copy(glowCol); u.side.emissiveIntensity = night * 1.6; }
            }
          }
          a.slab.visible = f > 0; if (f > 0) { a.slab.position.y = y + 0.03; y += 0.06; }
          if (here) building = true;
          const c = a.critter; c.visible = here; if (!here) a.wasHere = false;
          if (here) {
            const ang = (a.slot * 2.39996) % (Math.PI * 2), rad = FOOT * 0.5 + 0.85;
            const hx = tw.x + Math.cos(ang) * rad, hz = tw.z + Math.sin(ang) * rad, sx = tw.x + 1.2 + (a.slot % 3) * 0.5, sz = tw.z + FOOT / 2 + 1.1;
            /* Agents walk for themselves. The data only says what an agent is doing; where it stands is worked out step by step as the replay plays:
               it comes in from the avenue along the front of its row, goes to its working place, steps out onto the grass to nap when its agent goes quiet,
               paces while it waits on something, and walks back out to the avenue at the end. On the way it goes round buildings and keeps clear of the others.
               When the replay is paused, or the time jumps, it is simply put where it would have ended up. */
            const span = Math.max(60, a.t1 - a.t0), edge = Math.min(0.12, 420 / span) * span, leaving = a.t1 - t < edge, moving = S.playing && !reduced;
            const frontZ = tw.z + FOOT / 2 + 0.75, avenue = widest / 2 + 2.6, pacing = a.act === 'wait' && !sleeping && !leaving;
            let gx = hx, gz = hz;
            if (leaving) { gx = avenue; gz = frontZ; } else if (sleeping) { gx = tw.x + (a.slot % 3 - 1) * 1.2 + 0.6; gz = tw.z + FOOT / 2 + 2.4; } else if (pacing) { gx = tw.x + Math.sin(now * 0.0007 + a.slot * 2.1) * 2.4; gz = frontZ + 0.25; }
            const live = moving && a.liveT !== undefined && Math.abs(t - a.liveT) < S.speed * 0.3 + 30; a.liveT = t;
            if (!live || a.px === undefined) { a.px = gx; a.pz = gz; }
            else if (!a.wasHere) { if (t - a.t0 < edge * 3) { a.px = avenue; a.pz = frontZ; } else { a.px = gx; a.pz = gz; } }
            let tx = gx, tz = gz; if (Math.abs(a.px - gx) > 2.6) tz = frontZ;                       // a long way along the row: keep to the path in front of the buildings first
            const far = Math.hypot(gx - a.px, gz - a.pz), walking = far > 0.14;
            if (live && walking) { const dx = tx - a.px, dz = tz - a.pz, d = Math.hypot(dx, dz) || 1, step = Math.min(d, Math.min(16, Math.max(3.2, far * 1.6)) * dt); a.px += dx / d * step; a.pz += dz / d * step;
              const cl = clearOf(a.px, a.pz, tx, tz, FOOT * 0.5 + 0.5); a.faceX = a.px + (cl[0] - a.px) * 8 + dx / d; a.faceZ = a.pz + (cl[1] - a.pz) * 8 + dz / d; a.px = cl[0]; a.pz = cl[1]; }
            c.position.set(a.px, 0.07, a.pz); crowd.push(a);
            if (walking && live) c.lookAt(a.faceX, 0.07, a.faceZ); else if (!sleeping) c.lookAt(tw.x, 0.07, tw.z);
            if (sleeping || leaving || (walking && !pacing)) a.act = null; else if (now >= (a.actUntil || 0) || a.actT > t) { a.act = actionAt(a, t); a.actUntil = now + (S.playing ? 1100 : 150); } a.actT = t;
            ASSETS.critter.setAction(kit, c, a.act);
            const arrived = !a.wasHere; a.wasHere = true;
            const resting = !S.playing || !work;   // paused, or between bursts of work: stand easy, but stay alive
            ASSETS.critter.animate(c, { mode: sleeping ? 'sleep' : walking ? 'walk' : resting ? 'idle' : 'work', grumpy: !walking && !sleeping && failedAt(a, t), now, moving: resting && !walking ? !reduced : moving });
            if (work && a.kind !== 'Main') { sumX += tw.x; sumZ += tw.z; fn++; working.push(tw); }
            // Each kind of work throws off its own particles, so the village can be read from a distance.
            if (arrived && lively) fx.emit('poof', c.position.x, 0.5, c.position.z, 12);
            if (beat && !walking && !sleeping) { const px = c.position.x, pz = c.position.z, wx = tw.x + (hx - tw.x) * 0.6, wz = tw.z + (hz - tw.z) * 0.6;
              if (failedAt(a, t)) fx.emit('fume', px, 1.9, pz, 2);
              else if (a.act === 'write' || (!a.act && work)) { fx.emit('chips', wx, 0.6, wz, 2); fx.emit('dust', wx, Math.max(0.3, y - 0.2), wz, 1); }
              else if (a.act === 'build') fx.emit('sparks', px, 0.9, pz, 3);
              else if (a.act === 'git') fx.emit('mail', px, 2.3, pz, 1);
              else if (a.act === 'report') fx.emit('ticks', px, 2.0, pz, 2); }
          }
        }
        tw.top = y; const merged = !!(tw.merged && tw.merged <= t), done = !tw.pr && t > last && y > 0.2;
        tw.door.visible = y > 0.86 * BIG * DOOR;
        tw.roof.visible = merged; if (merged) { tw.roof.position.y = y; y += 1.1 * BIG; }
        tw.dome.visible = done; if (done) { tw.dome.position.y = y; y += 0.36; }
        tw.flag.visible = merged; if (merged) tw.flag.position.set(tw.x, y - 0.1, tw.z);
        if (lively && merged && tw.wasMerged === false) { fx.emit('confetti', tw.x, y + 0.5, tw.z, 110); fx.emit('sparkle', tw.x, y + 0.5, tw.z, 26); fx.emit('poof', tw.x, y, tw.z, 14); if (audio) audio.chime(); ownerParty(tw, now); }
        if (beat && merged && Math.random() < 0.3) fx.emit('smoke', tw.x + 0.42 * BIG, y + 0.02, tw.z - 0.3 * BIG, 1);
        tw.wasMerged = merged;
        tw.scaffold.visible = building && !merged && tw.top > 0.14;
        if (tw.scaffold.visible) ASSETS.scaffold.resize(tw.scaffold, tw.top + 0.55);
      }
      busyNow = S.playing ? fn : 0;
      // Nobody stands on anybody: agents that end up too close step apart, and they make room for Bruk.
      if (S.playing && !reduced) { for (let i = 0; i < crowd.length; i++) { const p = crowd[i];
          for (let k = i + 1; k < crowd.length; k++) { const q = crowd[k], dx = q.px - p.px, dz = q.pz - p.pz, d = Math.hypot(dx, dz); if (d < 0.95 && d > 1e-3) { const push = (0.95 - d) / 2 / d; p.px -= dx * push; p.pz -= dz * push; q.px += dx * push; q.pz += dz * push; } }
          const ox = p.px - owner.position.x, oz = p.pz - owner.position.z, od = Math.hypot(ox, oz); if (od < 1.0 && od > 1e-3) { p.px += ox / od * (1.0 - od); p.pz += oz / od * (1.0 - od); }
          p.critter.position.x = p.px; p.critter.position.z = p.pz; } }
      ownerAt(t, now, S.playing && !reduced, dt, working);
      // Night lights: lamp pools and halos come up as it gets dark, and the fairy lights drift out.
      { const dusk = Math.max(0, (night - 0.25) / 0.75), clock = reduced ? 0 : now;
        for (const [pool, halo] of pools) { pool.material.opacity = dusk * 0.55; halo.material.opacity = dusk * (0.75 + Math.sin(clock * 0.004 + pool.position.z) * 0.06); pool.visible = halo.visible = dusk > 0; }
        for (const q of fairies) { const a = clock * 0.0004 * q.v + q.ph, lag = a - 0.22, at = (k, s) => s.position.set(q.x + Math.sin(k) * q.r + Math.sin(k * 2.7) * 0.5, q.y0 + q.h + Math.sin(k * 3.3) * 0.5 + Math.sin(k * 7.1) * 0.12, q.z + Math.cos(k * 1.3) * q.r);
          const twinkle = 0.7 + Math.sin(clock * 0.006 + q.ph * 9) * 0.3; q.f.visible = q.tail.visible = dusk > 0; if (!dusk) continue;
          at(a, q.f); at(lag, q.tail); q.f.material.opacity = dusk * twinkle; q.tail.material.opacity = dusk * twinkle * 0.35; q.f.scale.setScalar(q.size * (0.85 + twinkle * 0.3)); q.tail.scale.setScalar(q.size * 0.6); } }
      // The sky: sun and moon cross with the clock, the light follows whichever is up, clouds and their shadows drift, birds circle by day.
      { const d = new Date(S.t * 1000), hr = d.getHours() + d.getMinutes() / 60, a = (hr - 6) / 12 * Math.PI;
        sunVil.set(Math.cos(a) * 0.82, Math.sin(a), -0.42).normalize(); moonVil.set(-Math.cos(a) * 0.82, -Math.sin(a), 0.3).normalize();   // where the sun and moon stand, as seen from the village
        if (!reduced) skyU.time.value = now / 1000; syncView(); dome.position.copy(view.position); dome.quaternion.copy(frameQ);
        unframe.copy(frameQ).invert(); skyU.sunDir.value.copy(sunVil).applyQuaternion(unframe); skyU.moonDir.value.copy(moonVil).applyQuaternion(unframe);   // and where that puts them in the sky from here
        const high = (v) => tmp.copy(v).setY(Math.max(0.42, v.y)).normalize(); lightDir.copy(high(night < 0.5 ? sunVil : moonVil));
        // Sunlight hands over to moonlight at dusk by fading out and back in, so shadows melt away and return instead of swinging across the sky.
        const fade = Math.min(1, Math.abs(night - 0.5) / 0.24), ease = fade * fade * (3 - 2 * fade); sun.intensity = sunBase * ease; amb.intensity = ambBase + (1 - ease) * sunBase * 0.5;
        if (firstFrame || (lightDir.distanceTo(lightWas) > 0.0012 && now - lightAt > 30)) { lightWas.copy(lightDir); lightAt = now; sun.position.copy(sun.target.position).addScaledVector(lightDir, 80 * K); renderer.shadowMap.needsUpdate = true; } }
      if (!reduced) {
        for (const c of clouds) { c.position.x += c.userData.v * dt; if (c.position.x > SKYW) c.position.x = -SKYW; }
        birds.forEach((b) => { const k = b.userData.k, a = now * 0.00016 + k * 0.11, R = 34 + (k % 3) * 2.5; b.visible = night < 0.6;
          b.position.set(Math.cos(a) * R * 1.3 + (k % 2) * 1.6, 19 + Math.sin(a * 2.0 + k) * 1.5 + (k % 3), mid + Math.sin(a) * R); b.rotation.y = -a; ASSETS.bird.animate(b, { now, k }); });
      }
      if (!reduced) { // ambient life: trees and flowers sway, butterflies wander, the sea drifts and laps at the shore
        for (const tr of trees) ASSETS.tree.animate(tr, { now });
        for (const f of blooms) f.rotation.z = Math.sin(now * 0.002 + f.position.x) * 0.07;
        for (const b of flutter) { const u = b.userData, a = now * 0.0005 + u.ph, x = u.home[0] + Math.sin(a) * 1.7 + Math.sin(a * 2.3) * 0.6, z = u.home[1] + Math.cos(a * 1.3) * 1.5;
          b.rotation.y = Math.atan2(x - b.position.x, z - b.position.z); b.position.set(x, 0.75 + Math.sin(a * 3.1) * 0.3, z); ASSETS.butterfly.animate(b, { now }); }
        waterTex.offset.set(BEND.value.x * 0.08 + now * 0.000012, -BEND.value.y * 0.08 + now * 0.000018); waterU.time.value = now / 1000;
      }
      if (fly) {
        const k = Math.min(1, (now - fly.at) / fly.ms), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        camera.position.lerpVectors(fly.p0, fly.p1, e); controls.target.lerpVectors(fly.t0, fly.t1, e); if (k >= 1) fly = null;
      } else if (S.follow !== 'off' && !grabbing && now - userMoved > 2200) {
        // Follow by sliding only: the view glides to keep its subject in the middle and keeps whatever zoom and angle the viewer has set.
        // The subject is the work (and Bruk once the build is over), Bruk himself, or whatever was last clicked.
        let sx = null, sz = 0, rate = 1.1; const over = t >= tMax - 1;
        if (S.follow === 'bruk' || (S.follow === 'work' && over)) { sx = owner.position.x; sz = owner.position.z; rate = 1.6; }
        else if (S.follow === 'pick') { const c = followAgent && followAgent.critter; if (c && c.visible) { sx = c.position.x; sz = c.position.z; rate = 1.6; } else if (S.picked) { sx = S.picked.x; sz = S.picked.z; } }
        else if (S.follow === 'work' && S.playing && fn) { sx = sumX / fn; sz = sumZ / fn; }
        if (fn) { lastWorkX = sumX / fn; lastWorkZ = sumZ / fn; }
        if (sx !== null) { const k = 1 - Math.exp(-dt * rate); slideView((sx - controls.target.x) * k, (sz - controls.target.z) * k, 1e9); }
      }
      waterU.night.value = night; if (scene.fog) waterU.sky.value.copy(scene.fog.color); waterU.sunDir.value.copy(lightDir); waterU.sunCol.value.copy(sun.color); waterU.sunAmt.value = sun.intensity / 0.58;
      fx.update(lively ? dt : 0.05);
      // How far the view may tip: right down to the horizon up close, and from far away round past it, so the planet can be seen from the side or from below.
      { const dist = camera.position.distanceTo(controls.target); controls.maxPolarAngle = Math.min(Math.PI * 0.93, Math.acos(Math.max(-1, -Math.max(0, dist - 14) / (2 * PLANET))) - 0.05); }
      controls.update();
      // The view may travel most of the way round the planet, but not to the far point where the wrap closes.
      const tg = controls.target, roam = PLANET * 2.0, off0 = Math.hypot(tg.x - BEND.value.x, tg.z - BEND.value.y), pull = off0 > roam ? roam / off0 : 1, cx = BEND.value.x + (tg.x - BEND.value.x) * pull, cz = BEND.value.y + (tg.z - BEND.value.y) * pull, cy = Math.min(14, Math.max(0, tg.y));
      if (cx !== tg.x || cz !== tg.z || cy !== tg.y) { camera.position.x += cx - tg.x; camera.position.y += cy - tg.y; camera.position.z += cz - tg.z; tg.set(cx, cy, cz); }
      if (camera.position.y < 0.6 && camera.position.distanceTo(tg) < 16) camera.position.y = 0.6;   // up close, stay above the ground; far out the view may drop below the horizon
      // How far out the camera is decides how much of the sky is air and how much is space, and how strongly the planet's rim of air shows.
      { syncView(); air.position.set(BEND.value.x, -PLANET, BEND.value.y); const alt = view.position.distanceTo(air.position) - PLANET, sm = (a, b, v) => { const u = Math.min(1, Math.max(0, (v - a) / (b - a))); return u * u * (3 - 2 * u); };
        skyU.space.value = sm(190, 500, alt); airU.amount.value = sm(PLANET * 0.25, PLANET * 0.9, alt) * (1 - 0.55 * night); airU.tint.value.set('#6fc1ff'); airU.sunView.value.copy(lightDir).applyQuaternion(frameQ).transformDirection(view.matrixWorldInverse); }
      const p = S.picked; sel.visible = !!p; tagEl.hidden = !p;
      if (p) {
        sel.position.set(p.x, 0.12, p.z); bendPoint(tmp.set(p.x, (p.top || 0) + 2.3, p.z)).project(view);
        const w = stage.clientWidth, h = stage.clientHeight, x = (tmp.x * 0.5 + 0.5) * w, y = (-tmp.y * 0.5 + 0.5) * h;
        tagEl.hidden = tmp.z > 1 || x < 0 || x > w || y < 0 || y > h; tagEl.style.left = x + 'px'; tagEl.style.top = y + 'px';
      }
      renderer.render(scene, view);
    }

