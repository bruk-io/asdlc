// The drawing kit every asset is made from: toon materials named after CSS colour variables,
// canvas textures, and a few base shapes. The page and the asset viewer both use it.
const ASSETS = {}, TEXTURES = {}, FOOT = 2.8, BIG = FOOT / 1.5, DOOR = 1.35; // FOOT: the width of a building, in scene units. BIG: how much larger that is than the 1.5 the building parts were first drawn at. DOOR: extra size for doors, so a critter fits through

function makeKit(css) {
  // Pages that wrap the world onto a planet replace this with the real bend. Everywhere else, points stay where they are.
  if (!THREE.ShaderChunk.bend_world) THREE.ShaderChunk.bend_world = 'vec3 bendWorld(vec3 p) { return p; } vec3 bendDir(vec3 p, vec3 n) { return n; }';
  const ramp = new THREE.DataTexture(new Uint8Array([172, 172, 172, 255, 222, 222, 222, 255, 255, 255, 255, 255]), 3, 1, THREE.RGBAFormat);
  ramp.minFilter = ramp.magFilter = THREE.NearestFilter; ramp.needsUpdate = true;
  const mats = {}, textures = {}, walls = {};
  // Materials that carry a painted texture as well as their colour.
  const MAPS = { '--w-grass': 'grass', '--w-roof': 'roofTiles', '--w-roof-2': 'roofTiles', '--w-roof-3': 'roofTiles', '--w-path': 'dirt', '--w-plot': 'paving', '--w-wood': 'wood', '--w-trunk': 'bark' };
  const toon = (extra) => new THREE.MeshToonMaterial(Object.assign({ color: 0x888888, gradientMap: ramp }, extra));
  const colourOf = (name) => name === '@ink' ? '#2b2622' : name.startsWith('--') ? css(name) || '#888888' : name; // a CSS variable name, or a colour as it stands
  const outlineMats = {};
  const kit = {
    css, mats, toon, colour: colourOf,
    // A named material takes its colour from the CSS variable of that name, the moment it is made.
    mat(name) { return mats[name] || (mats[name] = toon(Object.assign({ color: new THREE.Color(colourOf(name)) }, MAPS[name] ? { map: kit.tex(MAPS[name]) } : {}))); },
    recolour() { for (const k in mats) mats[k].color.set(colourOf(k)); },
    canvasTex(w, h, draw) { const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h); const x = new THREE.CanvasTexture(c); x.encoding = THREE.sRGBEncoding; return x; },
    tex(name) { return textures[name] || (textures[name] = TEXTURES[name](kit)); },
    // (Wall textures are not flipped on upload: the wall's own coordinates run top to bottom.)
    // The wall texture for one wall colour (a CSS variable name) and window style. Painted once, then shared.
    wall(colourVar, style) { const key = colourVar + '/' + style; if (!walls[key]) { const t = kit.canvasTex(128, 128, (g) => paintWall(kit, g, colourOf(colourVar), style, false)); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4; t.flipY = false; walls[key] = t; } return walls[key]; },
    // The speech-bubble icon for one kind of action. Painted once, then shared.
    icon(name) { const key = 'icon/' + name; return textures[key] || (textures[key] = kit.canvasTex(128, 128, (g) => paintIcon(kit, g, name))); },
    // A soft round shadow to lay under an object so it sits on the ground.
    blob(radius, y) { const m = new THREE.Mesh(kit.geo.disc, kit.blobMat || (kit.blobMat = new THREE.MeshBasicMaterial({ map: kit.tex('blob'), transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 }))); m.rotation.x = -Math.PI / 2; m.scale.setScalar(radius); m.position.y = y === undefined ? 0.012 : y; m.renderOrder = 1; m.userData.blob = true; return m; },
    // Give every toon mesh under `obj` a thin dark outline: a copy of its shape, pushed out along its normals and drawn inside-out.
    // The width is in scene units, so outlines thin out with distance. Anything marked userData.plain is left alone, with all it holds.
    outline(obj, width) {
      const w = width || 0.022, m = outlineMats[w] || (outlineMats[w] = new THREE.ShaderMaterial({ side: THREE.BackSide, uniforms: { w: { value: w }, c: { value: new THREE.Color(colourOf('--w-ink')) } },
        vertexShader: ['#include <bend_world>', 'uniform float w;', 'void main() {', '  vec4 wp = modelMatrix * vec4(position, 1.0); vec3 nw = bendDir(wp.xyz, normalize(normalMatrix * normal) * mat3(viewMatrix)); wp.xyz = bendWorld(wp.xyz);',
          '  vec4 mv = viewMatrix * wp; mv.xyz += normalize(mat3(viewMatrix) * nw) * w; gl_Position = projectionMatrix * mv;', '}'].join('\n'),
        fragmentShader: 'uniform vec3 c; void main() { gl_FragColor = vec4(c, 1.0); }' }));
      const found = [], walk = (x) => { if (x.userData.plain || x.userData.blob || x.userData.outline) return; if (x.isMesh && (Array.isArray(x.material) ? x.material[0] : x.material).isMeshToonMaterial) found.push(x); x.children.forEach(walk); };
      walk(obj);
      for (const x of found) { const o = new THREE.Mesh(x.geometry, m); o.userData.outline = true; o.raycast = () => {}; o.castShadow = o.receiveShadow = false; x.add(o); }
      return obj;
    },
    // A rounded-rectangle footprint of height 1, centred on y, so it can be scaled in y without bending its corners.
    prism(w, d, r) {
      const s = new THREE.Shape(), x = -w / 2, y = -d / 2;
      s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + d - r); s.quadraticCurveTo(x + w, y + d, x + w - r, y + d);
      s.lineTo(x + r, y + d); s.quadraticCurveTo(x, y + d, x, y + d - r); s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
      const g = new THREE.ExtrudeGeometry(s, { depth: 1, bevelEnabled: false, curveSegments: 6 }); g.rotateX(-Math.PI / 2); g.translate(0, -0.5, 0); return g;
    },
    geo: { box: new THREE.BoxGeometry(1, 1, 1), sph: new THREE.SphereGeometry(1, 18, 14), cone: new THREE.ConeGeometry(1, 1, 12), tor: new THREE.TorusGeometry(1, 0.22, 8, 20), cyl: new THREE.CylinderGeometry(1, 1, 1, 10),
      disc: new THREE.CircleGeometry(1, 28), pad: (() => { const g = new THREE.PlaneGeometry(2, 2, 14, 14); g.rotateX(-Math.PI / 2); return g; })(), trunk: new THREE.CylinderGeometry(0.62, 1, 1, 10), bud: new THREE.SphereGeometry(1, 10, 8), hat: new THREE.SphereGeometry(1, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2) },
    // One mesh: geometry, material (or the name of one), scale, position.
    mesh(geo, m, sx, sy, sz, x, y, z, cast) {
      const o = new THREE.Mesh(geo, typeof m === 'string' ? kit.mat(m) : m); o.scale.set(sx, sy, sz); o.position.set(x || 0, y || 0, z || 0); o.receiveShadow = true; o.castShadow = cast !== false; return o;
    },
    group(...children) { const g = new THREE.Group(); children.forEach((c) => g.add(c)); return g; },
    make(name, opts) { if (!ASSETS[name]) throw new Error('no asset called ' + name); return ASSETS[name].build(kit, opts || {}); },
    rng(seed) { let s = seed; return () => { s = (s * 16807) % 2147483647; return s / 2147483647; }; },
  };
  return kit;
}
