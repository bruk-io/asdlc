    /* ---- terrain: the height of the land everywhere, and the mesh that shows it ---- */
    const islandW = halfW * 2, islandD = z1 - z0;
    /* The land. The village sits on a level plain; around it the ground rolls into hills and a few mountains, runs down to a beach along an uneven
       coast, and drops under the sea. Further off there are other islands. ground(x, z) gives the height anywhere, so anything can be stood on it. */
    const zc = (z0 + z1) / 2, flatHW = widest / 2 + 11, flatC = (depth + 9 - ROW_GAP * 1.1 - 5) / 2, flatHD = (depth + 9 + ROW_GAP * 1.1 + 5) / 2;
    const hash2 = (x, z) => { const s = Math.sin(x * 127.1 + z * 311.7) * 43758.5453; return s - Math.floor(s); };
    const vnoise = (x, z) => { const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi, u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf); return (hash2(xi, zi) * (1 - u) + hash2(xi + 1, zi) * u) * (1 - v) + (hash2(xi, zi + 1) * (1 - u) + hash2(xi + 1, zi + 1) * u) * v; };
    const fbm2 = (x, z) => vnoise(x, z) * 0.5 + vnoise(x * 2.03 + 17, z * 2.03 + 5) * 0.25 + vnoise(x * 4.1 + 3, z * 4.1 + 29) * 0.125 + vnoise(x * 8.2, z * 8.2) * 0.0625;
    const rectDist = (x, z, hw, hd, c) => { const dx = Math.abs(x) - hw, dz = Math.abs(z - c) - hd; return Math.hypot(Math.max(dx, 0), Math.max(dz, 0)) + Math.min(Math.max(dx, dz), 0); };
    const PEAKS = [[-(halfW + 24), mid * 0.45, 24, 17], [halfW + 28, mid * 1.45, 18, 15], [-(halfW + 14), z1 + 30, 14, 13], [halfW + 16, z0 - 24, 11, 12]];   // x, z, height, spread
    const ease = (v) => { const c = Math.min(1, Math.max(0, v)); return c * c * (3 - 2 * c); };
    function ground(x, z) {
      const out = rectDist(x, z, flatHW, flatHD, flatC), edge = rectDist(x, z, halfW, (z1 - z0) / 2, zc); let peak = 0, pull = 0;
      for (const [px, pz, ph, pr] of PEAKS) { const g = Math.exp(-((x - px) * (x - px) + (z - pz) * (z - pz)) / (pr * pr)); peak += g * ph; pull += g; }
      const coast = 12 + 26 * fbm2(x * 0.021 + 9, z * 0.021 + 4) + pull * 34, land = ease((coast - edge) / 11), rise = ease(out / 12);        // how far the land runs here; 1 inland, 0 out at sea; 0 on the plain, 1 in the hills
      let h = -5 + (5 + Math.max(-0.25, (fbm2(x * 0.045, z * 0.045) - 0.32) * 8 * rise + peak * rise)) * land;
      if (edge > 70) { const isle = ease((fbm2(x * 0.0075 + 40, z * 0.0075 + 70) - 0.55) / 0.12) * ease((edge - 70) / 30); h = Math.max(h, -5 + isle * (6 + fbm2(x * 0.04 + 7, z * 0.04) * 9)); }   // other islands, well away from the village
      return h;
    }
    const grass = mat('--w-grass');
    { const reach = Math.PI * PLANET, tw = islandW + reach * 2, td = islandD + reach * 2, g = sheet(tw, td, 0, 3.2), pos = g.attributes.position, col = new Float32Array(pos.count * 3), c = new THREE.Color(), c2 = new THREE.Color();
      const SAND = '#f3e3ad', GRASS = css('--w-grass'), DEEP = css('--w-leaf-2'), ROCK = '#aaa49b', SNOW = '#ffffff', BED = '#d8c890';
      for (let i = 0; i < pos.count; i++) { const x = pos.getX(i), z = pos.getZ(i) + zc, h = ground(x, z), slope = Math.hypot(ground(x + 1.2, z) - h, ground(x, z + 1.2) - h) / 1.2; pos.setY(i, h);
        if (h < -2.6) c.set(BED); else if (h < -0.9) c.set(SAND); else { c.set(GRASS).lerp(c2.set(DEEP), ease((h - 1.5) / 7) * 0.55); if (h > 1 && slope > 0.75) c.lerp(c2.set(ROCK), ease((slope - 0.75) / 0.5)); if (h > 11) c.lerp(c2.set(ROCK), ease((h - 11) / 3)); if (h > 16) c.lerp(c2.set(SNOW), ease((h - 16) / 2)); if (h < -0.4) c.lerp(c2.set(SAND), ease((-0.4 - h) / 0.5)); }
        col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b; }
      g.setAttribute('color', new THREE.BufferAttribute(col, 3)); g.computeVertexNormals();
      const land = new THREE.Mesh(g, kit.toon({ color: 0xffffff, vertexColors: true, map: kit.tex('grass') })); land.position.set(0, -0.06, zc); land.receiveShadow = true; land.castShadow = true; scene.add(land); }   // hills and mountains throw shadows too
