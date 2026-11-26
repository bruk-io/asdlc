    /* ---- theme: day in the light theme, night in the dark one ---- */
    let night = 0, sunBase = 0.58, ambBase = 0.17; const glowCol = new THREE.Color(), liveCol = new THREE.Color(), tmpA = new THREE.Color(), tmpB = new THREE.Color();
    const NIGHT = { top: '#0d1640', bot: '#34407f', dusk: '#ffb27a', water: '#2c4a8c', hemi: '#8fa4e8', ground: '#4a5f7a', moon: '#b9c8ff', sprite: '#8c98c6' };
    const hex = (c) => '#' + c.getHexString();
    // Set how far into the night the scene is: 0 is midday, 1 is deep night, and the middle of the change glows like dusk.
    function setNight(k) {
      night = k; const dusk = 4 * k * (1 - k);
      tmpA.set(css('--w-sky-top')).lerp(tmpB.set(NIGHT.top), k); const top = hex(tmpA);
      tmpA.set(css('--w-sky-bot')).lerp(tmpB.set(NIGHT.bot), k).lerp(tmpB.set(NIGHT.dusk), dusk * 0.75); const bot = hex(tmpA);
      const g = skyTex.image.getContext('2d'), grad = g.createLinearGradient(0, 0, 0, 256); grad.addColorStop(0, top); grad.addColorStop(0.62, bot); grad.addColorStop(1, bot);
      g.fillStyle = grad; g.fillRect(0, 0, 4, 256); skyTex.needsUpdate = true;
      if (!scene.fog) scene.fog = new THREE.Fog(0xffffff, Math.max(170 * K, PLANET * 7), Math.max(620 * K, PLANET * 14)); scene.fog.color.set(bot);
      hemi.intensity = 0.48 - 0.1 * k; hemi.color.set('#eaf6ff').lerp(tmpB.set(NIGHT.hemi), k); hemi.groundColor.set('#d9efb8').lerp(tmpB.set(NIGHT.ground), k); ambBase = 0.17 + 0.03 * k;
      sunBase = 0.58 - 0.24 * k; sun.color.set('#ffedc2').lerp(tmpB.set(NIGHT.dusk), dusk * 0.6).lerp(tmpB.set(NIGHT.moon), k * k);
      skyU.top.value.set(top); skyU.bot.value.set(bot); skyU.night.value = k; skyU.duskAmt.value = dusk;
      mats['--w-water'].color.set(css('--w-water')).lerp(tmpB.set(NIGHT.water), k * 0.8);
      tmpA.set('#ffffff').lerp(tmpB.set(NIGHT.sprite), k * 0.8); for (const s of signs) s.s.material.color.copy(tmpA);
      const lampMat = mat('--w-glow'); lampMat.emissive.copy(glowCol); lampMat.emissiveIntensity = k * 1.6;
      stage.style.background = bot; stage.parentNode.classList.toggle('night', k > 0.5);
    }
    // The hour on the replay clock decides day or night: light from about 7:30, dark from about 20:00.
    function nightAt(t) { const d = new Date(t * 1000), h = d.getHours() + d.getMinutes() / 60, ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); }; return h < 12 ? 1 - ss(5.5, 7.5, h) : ss(17.5, 20, h); }
    function applyTheme() {
      kit.recolour();
      glowCol.set(css('--w-glow')); liveCol.set(css('--w-live'));
      sel.material.color.set(css('--ui-text-bright'));
      paintSigns(); recolour(); setNight(night); renderer.shadowMap.needsUpdate = true;
    }
    function recolour() { agents.forEach((a) => a.segs.forEach((m) => ASSETS.storey.paint(kit, m, segColour(a, m.userData.kind)))); }
    function size() { const w = stage.clientWidth, h = stage.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.setViewOffset(w, h, 0, Math.round(Math.min(110, h * 0.12)), w, h); camera.updateProjectionMatrix(); }
    new ResizeObserver(size).observe(stage); size(); applyTheme();
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { applyTheme(); drawTimeline(); });
    new MutationObserver(() => { applyTheme(); drawTimeline(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

