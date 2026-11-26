// Building walls, painted in full colour: plaster in the wall colour with one window per tile.
// There are three window styles (plain, shuttered, arched with a flower box), so a street of buildings does not repeat.
// kit.wall(colourVar, style) returns the texture for one wall colour and style; windowGlow is the matching mask of lit panes.
function paintWall(kit, g, wallColour, style, mask) {
  const S = 128, shade = (hex, k) => { const c = new THREE.Color(hex); const f = (v) => Math.round(Math.max(0, Math.min(1, k > 0 ? v + (1 - v) * k : v * (1 + k))) * 255); return 'rgb(' + f(c.r) + ',' + f(c.g) + ',' + f(c.b) + ')'; };
  const pane = (draw) => { g.beginPath(); if (style === 2) { g.moveTo(40, 96); g.lineTo(40, 52); g.quadraticCurveTo(40, 26, 64, 26); g.quadraticCurveTo(88, 26, 88, 52); g.lineTo(88, 96); g.closePath(); } else g.roundRect(40, 30, 48, 66, 8); draw(); };
  if (mask) { g.fillStyle = '#000'; g.fillRect(0, 0, S, S); g.fillStyle = '#fff'; pane(() => g.fill()); g.fillStyle = '#000'; g.fillRect(62, 26, 4, 72); g.fillRect(40, 60, 48, 4); return; }
  const rnd = kit.rng(11 + style);
  const grad = g.createLinearGradient(0, 0, 0, S); grad.addColorStop(0, shade(wallColour, 0.1)); grad.addColorStop(1, shade(wallColour, -0.07)); g.fillStyle = grad; g.fillRect(0, 0, S, S);
  for (let i = 0; i < 70; i++) { g.fillStyle = rnd() < 0.5 ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.045)'; g.beginPath(); g.ellipse(rnd() * S, rnd() * S, 2 + rnd() * 7, 1.5 + rnd() * 4, rnd() * 3, 0, 7); g.fill(); }
  if (style === 1) { // shutters, in a deeper tone of the wall colour
    for (const x of [20, 90]) { g.fillStyle = shade(wallColour, -0.38); g.beginPath(); g.roundRect(x, 28, 18, 70, 4); g.fill(); g.fillStyle = shade(wallColour, -0.5); for (let y = 34; y < 94; y += 9) g.fillRect(x + 3, y, 12, 3); }
  }
  g.fillStyle = kit.css('--w-cream'); pane(() => { g.lineWidth = 12; g.strokeStyle = kit.css('--w-cream'); g.stroke(); });      // frame
  const glass = g.createLinearGradient(0, 28, 0, 98); glass.addColorStop(0, '#bfe4f7'); glass.addColorStop(1, '#6fa9cf'); g.fillStyle = glass; pane(() => g.fill());
  g.fillStyle = 'rgba(255,255,255,0.55)'; g.beginPath(); g.moveTo(45, 58); g.lineTo(60, 34); g.lineTo(52, 34); g.lineTo(45, 46); g.fill();               // glint
  g.fillStyle = kit.css('--w-cream'); g.fillRect(62, 26, 4, 72); g.fillRect(40, 60, 48, 4);                                                             // glazing bars
  g.fillStyle = 'rgba(0,0,0,0.16)'; g.fillRect(34, 102, 60, 4); g.fillStyle = kit.css('--w-cream'); g.beginPath(); g.roundRect(32, 96, 64, 7, 3); g.fill(); // sill and its shadow
  if (style === 2) { // flower box
    g.fillStyle = kit.css('--w-wood'); g.beginPath(); g.roundRect(36, 100, 56, 12, 4); g.fill(); g.fillStyle = kit.css('--w-leaf-2'); for (let x = 40; x < 90; x += 8) { g.beginPath(); g.arc(x, 99, 5, 0, 7); g.fill(); }
    const petals = ['--w-fruit', '--w-dome', '--w-blush']; for (let i = 0, x = 42; x < 90; x += 9, i++) { g.fillStyle = kit.css(petals[i % 3]); g.beginPath(); g.arc(x, 95, 3.4, 0, 7); g.fill(); }
  }
}
TEXTURES.windowGlow = (kit) => { const t = kit.canvasTex(128, 128, (g) => paintWall(kit, g, '#ffffff', 0, true)); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.flipY = false; return t; };
TEXTURES.windowGlowArched = (kit) => { const t = kit.canvasTex(128, 128, (g) => paintWall(kit, g, '#ffffff', 2, true)); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.flipY = false; return t; };
