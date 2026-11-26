// Rounded roof tiles in offset rows, each with a highlight along its top and a shadow under its lip.
TEXTURES.roofTiles = (kit) => {
  const t = kit.canvasTex(256, 256, (g) => { g.fillStyle = '#e9e9e9'; g.fillRect(0, 0, 256, 256);
    for (let r = -1; r < 5; r++) for (let c = -1; c < 5; c++) { const x = c * 64 + (r % 2 ? 32 : 0), y = r * 64;
      const grad = g.createLinearGradient(0, y, 0, y + 70); grad.addColorStop(0, '#ffffff'); grad.addColorStop(0.75, '#e2e2e2'); grad.addColorStop(1, '#b9b9b9');
      g.fillStyle = grad; g.beginPath(); g.moveTo(x, y); g.lineTo(x + 64, y); g.lineTo(x + 64, y + 36); g.quadraticCurveTo(x + 32, y + 78, x, y + 36); g.closePath(); g.fill();
      g.strokeStyle = 'rgba(0,0,0,0.22)'; g.lineWidth = 3; g.stroke(); g.strokeStyle = 'rgba(255,255,255,0.7)'; g.lineWidth = 2; g.beginPath(); g.moveTo(x + 8, y + 8); g.lineTo(x + 26, y + 8); g.stroke(); } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(4, 1.6); t.anisotropy = 8; return t;
};
