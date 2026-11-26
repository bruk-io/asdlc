    /* ---- paths, plots, signs, ruler ---- */
    const signs = [];
    function sign(text, h, opts) {
      const c = document.createElement('canvas'), o = Object.assign({ plate: true }, opts), g = c.getContext('2d'); g.font = '700 54px ui-rounded, "SF Pro Rounded", system-ui, sans-serif';
      c.width = Math.ceil(g.measureText(text).width) + 64; c.height = 100;
      const tex = new THREE.CanvasTexture(c); tex.encoding = THREE.sRGBEncoding; tex.minFilter = THREE.LinearFilter;
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false })); s.scale.set(h * c.width / c.height, h, 1); signs.push({ c, tex, text, o, s }); scene.add(s); return s;
    }
    function paintSigns() {
      for (const s of signs) {
        const g = s.c.getContext('2d'), w = s.c.width; g.clearRect(0, 0, w, 100);
        if (s.o.plate) { g.fillStyle = css('--w-wood'); g.strokeStyle = css('--w-trunk'); g.lineWidth = 5; g.beginPath(); g.roundRect(4, 8, w - 8, 84, 26); g.fill(); g.stroke(); }
        g.font = '700 54px ui-rounded, "SF Pro Rounded", system-ui, sans-serif'; g.textBaseline = 'middle'; g.textAlign = 'center';
        g.fillStyle = s.o.plate ? css('--w-cream') : css('--ui-text-bright'); g.fillText(s.text, w / 2, 52); s.tex.needsUpdate = true;
      }
    }
    // Where two paths meet at a right angle, a fillet rounds the inside corner: a square with a quarter circle cut out of it.
    // (x, z) is the corner; sx and sz say which way the fillet opens.
    const FILLET = 0.7, filletGeo = [0, 1, 2, 3].map((k) => { const s = new THREE.Shape(); s.moveTo(0, 0); s.lineTo(1, 0); s.absarc(1, 1, 1, -Math.PI / 2, Math.PI, true); s.lineTo(0, 0);
      const g = new THREE.ExtrudeGeometry(s, { depth: 1, bevelEnabled: false, curveSegments: 10 }); g.rotateX(-Math.PI / 2); g.translate(0, -0.5, 0); g.rotateY(k * Math.PI / 2); return g; });
    const fillet = (x, z, sx, sz) => add(filletGeo[sx > 0 ? (sz < 0 ? 0 : 3) : (sz < 0 ? 1 : 2)], mat('--w-path'), FILLET, 0.06, FILLET, x, -0.026, z);
    rows.forEach((r, ri) => {
      const w = Math.max(1, r.towers.length) * COL_GAP + 1.4, z = ri * ROW_GAP;
      add(sheet(w, FOOT + 1.4, 1.1, 1.8), mat('--w-path'), 1, 1, 1, 0, 0.015, z);
      add(sheet(widest / 2 + 2.6 - w / 2 + 1.2, 0.9, 0.3, 1.5), mat('--w-path'), 1, 1, 1, (w / 2 + widest / 2 + 2.6) / 2 - 0.3, 0.004, z);
      for (const sz of [-1, 1]) { fillet(w / 2 - 0.03, z + sz * 0.45, 1, sz); fillet(widest / 2 + 2.6 - 0.85, z + sz * 0.45, -1, sz); }
      const s = sign(r.name, 0.66); s.position.set(-w / 2 - 2.2, 1.12, z);
      add(cyl, mat('--w-trunk'), 0.07, 0.86, 0.07, -w / 2 - 2.2, 0.4, z, true);
    });
    add(sheet(1.7, depth + 9, 0.8, 1.8), mat('--w-path'), 1, 1, 1, widest / 2 + 2.6, 0.004, mid);
    const maxCost = Math.max(...towers.map((t) => t.cost)), step = 25, rx = -widest / 2 - 5.4, rz = -ROW_GAP * 1.1, rulerTop = Math.ceil(maxCost / step) * step;
    for (let v = 0; v < rulerTop; v += step / 2) add(cyl, mat(v / (step / 2) % 2 ? '--w-cream' : '--w-roof'), 0.11, step / 2 * HS, 0.11, rx, (v + step / 4) * HS, rz, true);
    add(sph, mat('--w-dome'), 0.2, 0.2, 0.2, rx, rulerTop * HS + 0.12, rz, true);
    for (let v = step; v <= rulerTop; v += step) { const s = sign('$' + v, 0.62, { plate: false }); s.position.set(rx + 1.15, v * HS, rz); }
    const cap = sign('height = cost', 0.6); cap.position.set(rx, rulerTop * HS + 1.05, rz);

