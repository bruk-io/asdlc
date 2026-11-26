// Packed dirt for the paths: soft blotches and pebbles.
TEXTURES.dirt = (kit) => {
  const t = kit.canvasTex(256, 256, (g) => { g.fillStyle = '#e9e9e9'; g.fillRect(0, 0, 256, 256); const rnd = kit.rng(3);
    for (let i = 0; i < 60; i++) { g.fillStyle = rnd() < 0.5 ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.06)'; g.beginPath(); g.ellipse(rnd() * 256, rnd() * 256, 6 + rnd() * 20, 4 + rnd() * 10, rnd() * 3, 0, 7); g.fill(); }
    for (let i = 0; i < 90; i++) { g.fillStyle = 'rgba(0,0,0,' + (0.08 + rnd() * 0.1) + ')'; g.beginPath(); g.ellipse(rnd() * 256, rnd() * 256, 1.5 + rnd() * 3, 1.2 + rnd() * 2, rnd() * 3, 0, 7); g.fill(); } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(0.35, 0.35); t.anisotropy = 8; return t;
};
// Rounded paving stones for the plot under each building.
TEXTURES.paving = (kit) => {
  const t = kit.canvasTex(128, 128, (g) => { g.fillStyle = '#fff'; g.fillRect(0, 0, 128, 128); g.strokeStyle = 'rgba(0,0,0,0.16)'; g.lineWidth = 3;
    for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) { const x = c * 43 + (r % 2 ? 21 : 0) - 32, y = r * 32; g.beginPath(); g.roundRect(x + 2, y + 2, 39, 28, 7); g.fillStyle = 'rgba(0,0,0,' + (((r * 3 + c) % 4) * 0.025) + ')'; g.fill(); g.stroke(); } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1.1, 1.1); return t;
};
// Wood grain for signs, benches and scaffolding; bark for trunks.
TEXTURES.wood = (kit) => {
  const t = kit.canvasTex(128, 128, (g) => { g.fillStyle = '#f2f2f2'; g.fillRect(0, 0, 128, 128); const rnd = kit.rng(9); g.lineCap = 'round';
    for (let i = 0; i < 26; i++) { const y = rnd() * 128; g.strokeStyle = 'rgba(0,0,0,' + (0.06 + rnd() * 0.1) + ')'; g.lineWidth = 1 + rnd() * 2; g.beginPath(); g.moveTo(-4, y); g.bezierCurveTo(40, y + rnd() * 8 - 4, 90, y + rnd() * 8 - 4, 132, y + rnd() * 6 - 3); g.stroke(); }
    for (let i = 0; i < 3; i++) { const x = 20 + rnd() * 90, y = 20 + rnd() * 90; g.strokeStyle = 'rgba(0,0,0,0.16)'; g.lineWidth = 2; g.beginPath(); g.ellipse(x, y, 7, 4, 0, 0, 7); g.stroke(); } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
};
TEXTURES.bark = (kit) => {
  const t = kit.canvasTex(64, 128, (g) => { g.fillStyle = '#f0f0f0'; g.fillRect(0, 0, 64, 128); const rnd = kit.rng(4); g.lineCap = 'round';
    for (let i = 0; i < 16; i++) { const x = rnd() * 64, y = rnd() * 128, h = 14 + rnd() * 30; g.strokeStyle = 'rgba(0,0,0,' + (0.1 + rnd() * 0.12) + ')'; g.lineWidth = 2 + rnd() * 2; g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + rnd() * 6 - 3, y + h / 2, x, y + h); g.stroke(); } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(2, 1); return t;
};
// Gentle ripples for the sea.
TEXTURES.water = (kit) => {
  const t = kit.canvasTex(256, 256, (g) => { g.fillStyle = '#f0f0f0'; g.fillRect(0, 0, 256, 256); const rnd = kit.rng(12); g.lineCap = 'round';
    for (let i = 0; i < 46; i++) { const x = rnd() * 256, y = rnd() * 256, w = 16 + rnd() * 34; g.strokeStyle = 'rgba(255,255,255,' + (0.25 + rnd() * 0.35) + ')'; g.lineWidth = 3;
      for (const dx of [0, 256, -256]) { g.beginPath(); g.moveTo(x + dx - w / 2, y); g.quadraticCurveTo(x + dx, y - 5, x + dx + w / 2, y); g.stroke(); } } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(110, 110); return t;
};
// A soft round shadow that sits under things to ground them.
TEXTURES.blob = (kit) => kit.canvasTex(128, 128, (g) => { const r = g.createRadialGradient(64, 64, 4, 64, 64, 62); r.addColorStop(0, 'rgba(20,40,20,0.42)'); r.addColorStop(0.6, 'rgba(20,40,20,0.18)'); r.addColorStop(1, 'rgba(20,40,20,0)'); g.fillStyle = r; g.fillRect(0, 0, 128, 128); });
// A soft point of light: a bright core fading out to nothing. Tinted by the material that uses it.
TEXTURES.glow = (kit) => kit.canvasTex(128, 128, (g) => { const r = g.createRadialGradient(64, 64, 0, 64, 64, 64); r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.12, 'rgba(255,255,255,0.95)'); r.addColorStop(0.3, 'rgba(255,255,255,0.35)'); r.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = r; g.fillRect(0, 0, 128, 128); });
