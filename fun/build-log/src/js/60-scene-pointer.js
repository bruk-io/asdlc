    /* ---- hover and pick ---- */
    const tip = $('#tip'); let down = null;
    const piece = new THREE.Raycaster(), stepA = new THREE.Vector3(), stepB = new THREE.Vector3(), stepDir = new THREE.Vector3();
    function hitAt(ev) {
      const r = el.getBoundingClientRect(); ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1); syncView(); ray.setFromCamera(ptr, view);
      // The pointer's ray is straight on screen but curved in the flat world the buildings live in. So walk along it in short steps,
      // carry each step back to the flat world, and test each short piece in turn.
      const list = pickables.filter((m) => m.userData.critter ? m.parent.visible : m.visible), reach = camera.position.distanceTo(controls.target) * 2.4 + 20, o = ray.ray.origin, d = ray.ray.direction; let hits = [];
      unbendPoint(stepA.copy(o));
      for (let i = 1; i <= 48 && !hits.length; i++) { unbendPoint(stepB.copy(d).multiplyScalar(reach * i / 48).add(o)); const len = stepA.distanceTo(stepB);
        if (len > 1e-4) { piece.set(stepA, stepDir.copy(stepB).sub(stepA).divideScalar(len)); piece.far = len; hits = piece.intersectObjects(list, false); } stepA.copy(stepB); }
      return { hit: hits[0] && hits[0].object.userData, r };
    }
    el.addEventListener('pointermove', (ev) => {
      if (ev.buttons) { tip.hidden = true; el.style.cursor = 'grabbing'; return; }
      const { hit, r } = hitAt(ev); el.style.cursor = hit ? 'pointer' : 'grab';
      if (!hit) { tip.hidden = true; return; }
      const a = hit.agent, mins = Math.max(1, Math.round((a.t1 - a.t0) / 60));
      tip.innerHTML = '<b>' + esc(a.tw.title) + '</b><span>' + esc(a.tw.rowName) + ' · ' + (PHASE_NAME[a.ph] || a.phase) + ' · ' + MODEL_NAME[a.model].split(' · ')[0] + '</span><br>'
        + money(a.cost) + ' <span>this agent · ' + mins + ' min · ' + a.req + ' requests</span><br><span>read ' + money(a.cr) + ' · write ' + money(a.cw) + ' · output ' + money(a.co) + '</span>';
      tip.hidden = false;
      const x = Math.min(r.width - 290, ev.clientX - r.left + 14), y = Math.min(r.height - 110, ev.clientY - r.top + 14);
      tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, y) + 'px';
    });
    el.addEventListener('pointerleave', () => { tip.hidden = true; });
    el.addEventListener('pointerdown', (ev) => { down = [ev.clientX, ev.clientY]; });
    el.addEventListener('pointerup', (ev) => {
      el.style.cursor = 'grab';
      if (!down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 5) return;
      const { hit } = hitAt(ev); followAgent = hit && hit.critter ? hit.agent : null; if (hit) pick(hit.agent.tw, false); else pick(null, false);
    });
    el.addEventListener('dblclick', (ev) => { const { hit } = hitAt(ev); if (hit) { pick(hit.agent.tw, false); flyTo(hit.agent.tw); } });
    return { update, recolour, flyTo, nudge, reframe };
  }

