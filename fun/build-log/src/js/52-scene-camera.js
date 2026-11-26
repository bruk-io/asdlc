    /* ---- camera: flights, reframing, keyboard nudges, grab-and-roll dragging and zoom ---- */
    const V = (a) => new THREE.Vector3().fromArray(a);
    function flight(pos, tgt, ms) { if (reduced) { camera.position.copy(pos); controls.target.copy(tgt); return; } fly = { p0: camera.position.clone(), t0: controls.target.clone(), p1: pos, t1: tgt, at: performance.now(), ms: ms || 900 }; }
    // #cam=x,y,z,tx,ty,tz puts the camera somewhere exact, for the screenshot tool.
    const camHash = /cam=([-\d.,]+)/.exec(location.hash); if (camHash) { const n = camHash[1].split(',').map(Number); camera.position.set(n[0], n[1], n[2]); controls.target.set(n[3], n[4], n[5]); userMoved = 1e18; }
    // Put the view back to a good angle and distance over whatever the camera is following, and let following carry on from there.
    let lastWorkX = null, lastWorkZ = 0;
    function reframe() {
      let x = lastWorkX === null ? mainTower.x : lastWorkX, z = lastWorkX === null ? mainTower.z : lastWorkZ, dist = 46;
      if (S.follow === 'bruk' || (S.follow === 'work' && S.t >= tMax - 1)) { x = owner.position.x; z = owner.position.z; dist = 24; }
      else if (S.follow === 'pick' && S.picked) { x = S.picked.x; z = S.picked.z; dist = 30; }
      const tgt = new THREE.Vector3(x, 1.5, z); flight(tgt.clone().add(new THREE.Vector3(-0.52, 0.62, 0.58).normalize().multiplyScalar(dist)), tgt, 1000); userMoved = -1e9;
    }
    function flyTo(tw, dist) {
      userMoved = performance.now();
      const tgt = new THREE.Vector3(tw.x, Math.max(1.2, (tw.top || 1) * 0.55), tw.z), dir = camera.position.clone().sub(controls.target);
      dir.y = Math.max(dir.y, dir.length() * 0.36); dir.setLength(dist || Math.max(11, (tw.top || 2) * 2.2 + 7)); flight(tgt.clone().add(dir), tgt, 900);
    }
    function nudge(dx, dz, turn, zoom) {
      userMoved = performance.now(); fly = null;
      const off = camera.position.clone().sub(controls.target), f = new THREE.Vector3(-off.x, 0, -off.z).normalize(), r = new THREE.Vector3(-f.z, 0, f.x);
      const move = f.multiplyScalar(dz).add(r.multiplyScalar(dx)).multiplyScalar(off.length() * 0.06); controls.target.add(move); camera.position.add(move);
      if (turn) { off.applyAxisAngle(new THREE.Vector3(0, 1, 0), turn); camera.position.copy(controls.target).add(off); }
      if (zoom) camera.position.copy(controls.target).add(camera.position.clone().sub(controls.target).multiplyScalar(zoom));
    }
    // Zoom toward the point under the pointer: slide the view so that spot stays put while the wheel changes the distance.
    const ray = new THREE.Raycaster(), ptr = new THREE.Vector2(), under = new THREE.Vector3(), grab = new THREE.Vector3(), probe = new THREE.Vector3();
    // Find the spot on the planet under the pointer, as a place in the flat world: walk out along the line of sight until it goes below the land or the sea.
    function surfaceUnder(ev, out) {
      const r = el.getBoundingClientRect(); ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1); syncView(); ray.setFromCamera(ptr, view);
      const o = ray.ray.origin, d = ray.ray.direction, reach = camera.position.distanceTo(controls.target) + PLANET * 2.2, below = (s) => { unbendPoint(probe.copy(d).multiplyScalar(s).add(o)); return probe.y <= Math.max(ground(probe.x, probe.z), -1.9); };
      let lo = 0, hi = -1; for (let i = 1; i <= 90; i++) { const s = reach * i / 90; if (below(s)) { hi = s; break; } lo = s; }
      if (hi < 0) return false; for (let i = 0; i < 12; i++) { const m = (lo + hi) / 2; if (below(m)) hi = m; else lo = m; }
      below(hi); out.copy(probe); return true;
    }
    const slideView = (dx, dz, cap) => { const len = Math.hypot(dx, dz); if (len > cap) { dx *= cap / len; dz *= cap / len; } controls.target.x += dx; controls.target.z += dz; camera.position.x += dx; camera.position.z += dz; };
    // Grab and roll: the spot under the pointer when the button goes down stays under the pointer while it is dragged, so the planet turns in the hand.
    // Shift-drag and right-drag still turn the view; touch keeps the plain one-finger slide.
    // While dragging, the pointer is matched against a smooth ball at the height of the grabbed spot, not against the hills. That has an exact answer,
    // found in one step, so the view does not hunt back and forth or jump when the pointer crosses a ridge.
    let grabbing = false, grabH = 0; const centre = new THREE.Vector3(), toO = new THREE.Vector3();
    function shellUnder(ev, h, out) {
      const r = el.getBoundingClientRect(); ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1); syncView(); ray.setFromCamera(ptr, view);
      const o = ray.ray.origin, d = ray.ray.direction, R = PLANET + h; centre.set(BEND.value.x, -PLANET, BEND.value.y); toO.copy(o).sub(centre);
      const b = toO.dot(d), disc = b * b - (toO.lengthSq() - R * R); if (disc < 0) return false; const s = -b - Math.sqrt(disc); if (s <= 0) return false;
      unbendPoint(out.copy(d).multiplyScalar(s).add(o)); return true;
    }
    const fingers = new Set(); let grabId = -1;
    el.addEventListener('pointerdown', (ev) => { const touch = ev.pointerType === 'touch'; if (touch) { fingers.add(ev.pointerId); if (fingers.size > 1) grabbing = false; }
      const roll = touch ? fingers.size === 1 : ev.button === 0 && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey; if (!touch) controls.mouseButtons.LEFT = roll ? -1 : THREE.MOUSE.ROTATE;
      if (roll && surfaceUnder(ev, grab)) { grabH = Math.max(-1.9, grab.y); shellUnder(ev, grabH, grab); grabbing = true; grabId = ev.pointerId; fly = null; userMoved = performance.now(); try { el.setPointerCapture(ev.pointerId); } catch (e) { /* not capturable: the drag still works over the canvas */ } } }, { capture: true });
    el.addEventListener('pointermove', (ev) => { if (!grabbing || ev.pointerId !== grabId) return; userMoved = performance.now();
      for (let i = 0; i < 3; i++) { if (!shellUnder(ev, grabH, under)) break; const dx = grab.x - under.x, dz = grab.z - under.z; if (Math.hypot(dx, dz) < 0.002) break; slideView(dx, dz, 60); } });
    const letGo = (ev) => { fingers.delete(ev.pointerId); if (ev.pointerId === grabId) grabbing = false; }; el.addEventListener('pointerup', letGo); el.addEventListener('pointercancel', letGo);
    // Zoom toward the spot under the pointer.
    el.addEventListener('wheel', (ev) => {
      if (!surfaceUnder(ev, under)) return;
      const s = Math.pow(0.95, controls.zoomSpeed), k = ev.deltaY < 0 ? 1 - s : 1 - 1 / s; slideView((under.x - controls.target.x) * k, (under.z - controls.target.z) * k, 40);
    }, { passive: true });
