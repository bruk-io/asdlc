// Grass: soft light and dark patches, curved blades and a few tiny daisies. Kept pale, so the material colour tints it. Tiles seamlessly.
TEXTURES.grass = (kit) => {
  const t = kit.canvasTex(512, 512, (g) => {
    g.fillStyle = '#dcdcdc'; g.fillRect(0, 0, 512, 512); const rnd = kit.rng(7);
    const wrap = (x, y, draw) => { for (const [dx, dy] of [[0, 0], [512, 0], [-512, 0], [0, 512], [0, -512]]) draw(x + dx, y + dy); };
    for (let i = 0; i < 160; i++) { const light = rnd() < 0.6, x = rnd() * 512, y = rnd() * 512, rx = 14 + rnd() * 44, ry = 9 + rnd() * 24, a = rnd() * 3;
      g.fillStyle = light ? 'rgba(255,255,255,' + (0.18 + rnd() * 0.3) + ')' : 'rgba(0,0,0,' + (0.03 + rnd() * 0.05) + ')';
      wrap(x, y, (px, py) => { g.beginPath(); g.ellipse(px, py, rx, ry, a, 0, 7); g.fill(); }); }
    g.lineCap = 'round';
    for (let i = 0; i < 520; i++) { const x = rnd() * 512, y = rnd() * 512, h = 5 + rnd() * 8; g.strokeStyle = rnd() < 0.7 ? 'rgba(255,255,255,0.75)' : 'rgba(0,0,0,0.12)'; g.lineWidth = 1.6 + rnd();
      g.beginPath(); g.moveTo(x - 3, y); g.quadraticCurveTo(x - 1, y - h * 0.6, x, y - h); g.moveTo(x + 3, y); g.quadraticCurveTo(x + 1, y - h * 0.5, x + 1, y - h * 0.8); g.stroke(); }
    for (let i = 0; i < 26; i++) { const x = 8 + rnd() * 496, y = 8 + rnd() * 496; g.fillStyle = '#ffffff'; for (let k = 0; k < 5; k++) { g.beginPath(); g.arc(x + Math.cos(k * 1.257) * 3, y + Math.sin(k * 1.257) * 3, 2.1, 0, 7); g.fill(); } }
  });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(0.11, 0.11); t.anisotropy = 8; return t;
};
