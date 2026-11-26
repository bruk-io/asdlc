// The little picture in the bubble over a working critter: one per kind of action, drawn with plain shapes.
function paintIcon(kit, g, name) {
  const ink = kit.css('--w-ink') || '#3a2a1c', cream = kit.css('--w-cream'), accent = { read: '--series-b', write: '--series-a', git: '--series-c', build: '--w-stone', shell: '--ui-success', web: '--series-b', delegate: '--w-roof', skill: '--w-dome', report: '--ui-success', wait: '--w-dome', chat: '--series-b', cheer: '--w-dome' }[name];
  g.clearRect(0, 0, 128, 128); g.lineJoin = g.lineCap = 'round';
  g.fillStyle = cream; g.strokeStyle = ink; g.lineWidth = 6; g.beginPath(); g.roundRect(10, 6, 108, 96, 30); g.fill(); g.stroke();
  g.beginPath(); g.moveTo(50, 100); g.lineTo(64, 122); g.lineTo(78, 100); g.fill(); g.beginPath(); g.moveTo(50, 102); g.lineTo(64, 122); g.lineTo(78, 102); g.stroke(); g.fillRect(50, 92, 28, 9);
  g.fillStyle = kit.css(accent); g.strokeStyle = ink; g.lineWidth = 5; const fs = () => { g.fill(); g.stroke(); };
  if (name === 'read' || name === 'skill') { g.beginPath(); g.roundRect(38, 26, 52, 58, 6); fs(); g.strokeStyle = cream; g.lineWidth = 4; if (name === 'read') for (const y of [42, 55, 68]) { g.beginPath(); g.moveTo(48, y); g.lineTo(y === 68 ? 70 : 80, y); g.stroke(); }
    else { g.fillStyle = ink; g.beginPath(); for (let k = 0; k < 10; k++) { const a = -Math.PI / 2 + k * Math.PI / 5, r = k % 2 ? 7 : 16; g.lineTo(64 + Math.cos(a) * r, 55 + Math.sin(a) * r); } g.closePath(); g.fill(); } }
  else if (name === 'write') { g.save(); g.translate(64, 54); g.rotate(-0.6); g.fillStyle = kit.css('--w-wood'); g.beginPath(); g.roundRect(-5, -8, 10, 44, 4); fs(); g.fillStyle = kit.css('--w-stone'); g.beginPath(); g.roundRect(-24, -26, 48, 22, 6); fs(); g.restore(); }
  else if (name === 'git') { g.lineWidth = 6; g.beginPath(); g.moveTo(48, 34); g.lineTo(48, 78); g.moveTo(48, 60); g.quadraticCurveTo(80, 60, 80, 42); g.stroke(); for (const [x, y] of [[48, 32], [48, 78], [80, 38]]) { g.beginPath(); g.arc(x, y, 9, 0, 7); fs(); } }
  else if (name === 'build') { g.beginPath(); for (let k = 0; k < 16; k++) { const a = k * Math.PI / 8, r = k % 2 ? 20 : 29; g.lineTo(64 + Math.cos(a) * r, 54 + Math.sin(a) * r); g.lineTo(64 + Math.cos(a + Math.PI / 8) * r, 54 + Math.sin(a + Math.PI / 8) * r); } g.closePath(); fs(); g.fillStyle = cream; g.beginPath(); g.arc(64, 54, 9, 0, 7); fs(); }
  else if (name === 'shell') { g.fillStyle = ink; g.beginPath(); g.roundRect(30, 26, 68, 56, 10); g.fill(); g.strokeStyle = kit.css(accent); g.lineWidth = 6; g.beginPath(); g.moveTo(42, 42); g.lineTo(56, 54); g.lineTo(42, 66); g.moveTo(64, 68); g.lineTo(84, 68); g.stroke(); }
  else if (name === 'web') { g.beginPath(); g.arc(64, 54, 28, 0, 7); fs(); g.lineWidth = 4; g.beginPath(); g.ellipse(64, 54, 12, 28, 0, 0, 7); g.moveTo(36, 54); g.lineTo(92, 54); g.stroke(); }
  else if (name === 'delegate') { g.beginPath(); g.moveTo(38, 46); g.lineTo(56, 46); g.lineTo(84, 28); g.lineTo(84, 80); g.lineTo(56, 62); g.lineTo(38, 62); g.closePath(); fs(); g.lineWidth = 5; g.beginPath(); g.arc(86, 54, 12, -0.9, 0.9); g.stroke(); }
  else if (name === 'report') { g.beginPath(); g.arc(64, 54, 28, 0, 7); fs(); g.strokeStyle = cream; g.lineWidth = 8; g.beginPath(); g.moveTo(50, 55); g.lineTo(60, 66); g.lineTo(79, 43); g.stroke(); }
  else if (name === 'cheer') { g.beginPath(); for (let k = 0; k < 10; k++) { const a = -Math.PI / 2 + k * Math.PI / 5, r = k % 2 ? 13 : 30; g.lineTo(64 + Math.cos(a) * r, 55 + Math.sin(a) * r); } g.closePath(); fs(); }
  else if (name === 'chat') { for (const x of [42, 64, 86]) { g.beginPath(); g.arc(x, 54, 9, 0, 7); fs(); } }
  else if (name === 'wait') { g.beginPath(); g.moveTo(44, 28); g.lineTo(84, 28); g.lineTo(64, 54); g.lineTo(84, 80); g.lineTo(44, 80); g.lineTo(64, 54); g.closePath(); fs(); g.lineWidth = 6; g.beginPath(); g.moveTo(40, 26); g.lineTo(88, 26); g.moveTo(40, 82); g.lineTo(88, 82); g.stroke(); }
}

// An angry scribble: the tangle that floats over a critter when a tool call fails.
TEXTURES.scribble = (kit) => kit.canvasTex(128, 128, (g) => {
  const rnd = kit.rng(77), pts = []; for (let k = 0; k < 15; k++) { const a = k * 2.4 + rnd() * 1.2, r = 20 + rnd() * 30; pts.push([64 + Math.cos(a) * r, 62 + Math.sin(a) * r * 0.85]); }
  const draw = (w, colour) => { g.strokeStyle = colour; g.lineWidth = w; g.lineJoin = g.lineCap = 'round'; g.beginPath(); g.moveTo(pts[0][0], pts[0][1]); for (let k = 1; k < pts.length - 1; k++) g.quadraticCurveTo(pts[k][0], pts[k][1], (pts[k][0] + pts[k + 1][0]) / 2, (pts[k][1] + pts[k + 1][1]) / 2); g.stroke(); };
  draw(11, kit.css('--w-cream')); draw(5, kit.css('--w-ink') || '#3a2a1c');
  g.fillStyle = kit.css('--w-fruit'); for (const [x, y, r] of [[20, 26, 7], [108, 30, 6], [104, 100, 7]]) { g.beginPath(); for (let k = 0; k < 8; k++) { const a = k * Math.PI / 4, rr = k % 2 ? r * 0.45 : r * 1.5; g.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } g.closePath(); g.fill(); }
});

// Black and white stripes for a tee shirt.
TEXTURES.stripes = (kit) => { const t = kit.canvasTex(8, 64, (g) => { g.fillStyle = '#f6f3ea'; g.fillRect(0, 0, 8, 64); g.fillStyle = '#26252b'; for (let y = 2; y < 64; y += 13) g.fillRect(0, y, 8, 6); }); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t; };
