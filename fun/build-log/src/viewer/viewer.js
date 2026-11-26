// The asset viewer: shows one asset from src/assets on a turntable, with a button for each of its options.
// Locally, options can also be set in the address (?model=opus&mode=walk&t=1200&spin=0) so a screenshot can be scripted.
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s), css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const query = new URLSearchParams(location.search), reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let renderer, scene, camera, controls, kit, current = null, name = '', opts = {}, groundMesh;
  try { start(); } catch (e) { $('#err').hidden = false; $('#err').textContent = 'The viewer could not start: ' + e.message; }

  function start() {
    if (THREE.ColorManagement) THREE.ColorManagement.legacyMode = false;
    const stage = $('#stage');
    renderer = new THREE.WebGLRenderer({ antialias: true }); renderer.setPixelRatio(Math.min(2, devicePixelRatio || 1)); renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; stage.insertBefore(renderer.domElement, stage.firstChild);
    scene = new THREE.Scene(); scene.background = new THREE.Color(css('--w-sky-bot'));
    camera = new THREE.PerspectiveCamera(36, 1, 0.05, 200); controls = new THREE.OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.maxPolarAngle = Math.PI * 0.49;
    const hemi = new THREE.HemisphereLight(0xffffff, 0xcfe9b4, 0.5), amb = new THREE.AmbientLight(0xffffff, 0.17), sun = new THREE.DirectionalLight(0xfff1cf, 0.5);
    sun.position.set(-6, 10, 5); sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024); sun.shadow.normalBias = 0.05;
    Object.assign(sun.shadow.camera, { left: -12, right: 12, top: 12, bottom: -12, near: 0.5, far: 40 }); sun.shadow.camera.updateProjectionMatrix(); scene.add(hemi, amb, sun);
    kit = makeKit(css);
    groundMesh = kit.mesh(new THREE.CylinderGeometry(1, 1, 0.2, 48), '--w-grass', 6, 1, 6, 0, -0.1, 0, false); scene.add(groundMesh);
    const size = () => { const w = stage.clientWidth, h = stage.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); };
    new ResizeObserver(size).observe(stage); size();
    const names = Object.keys(ASSETS).sort((a, b) => ASSETS[a].title.localeCompare(ASSETS[b].title));
    $('#list').innerHTML = names.map((n) => '<button type="button" data-n="' + n + '">' + ASSETS[n].title + '</button>').join('');
    $('#list').addEventListener('click', (ev) => { const b = ev.target.closest('button'); if (b) show(b.dataset.n, {}); });
    $('#controls').addEventListener('click', (ev) => { const b = ev.target.closest('button'); if (b) { opts[b.dataset.k] = b.dataset.v; show(name, opts, true); } });
    $('#ground').addEventListener('change', (e) => { groundMesh.visible = e.target.checked; });
    if (query.get('spin') === '0') $('#spin').checked = false;
    if (query.get('ground') === '0') { $('#ground').checked = false; groundMesh.visible = false; }
    window.addEventListener('hashchange', () => show(location.hash.slice(1), {}));
    const first = location.hash.slice(1), fromQuery = {}; query.forEach((v, k) => { fromQuery[k] = v; });
    show(ASSETS[first] ? first : 'critter', fromQuery);
    requestAnimationFrame(loop);
  }

  function show(n, o, keepView) {
    if (!ASSETS[n]) return; name = n; const def = ASSETS[n], ctl = def.controls || {};
    opts = {}; for (const k in ctl) opts[k] = o[k] !== undefined && ctl[k].includes(String(o[k])) ? String(o[k]) : ctl[k][0];
    if (current) scene.remove(current);
    current = kit.make(n, opts); scene.add(current);
    const box = new THREE.Box3().setFromObject(current), c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3()), r = Math.max(s.x, s.y, s.z, 0.6);
    groundMesh.scale.set(Math.max(2.4, r * 1.5), 1, Math.max(2.4, r * 1.5));
    if (!keepView) { controls.target.set(0, c.y, 0); camera.position.set(r * 1.5, c.y + r * 0.8, r * 2.3); }
    $('#list').querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', b.dataset.n === n));
    $('#controls').innerHTML = Object.keys(ctl).map((k) => '<span class="group"><span class="name">' + k + '</span>' + ctl[k].map((v) => '<button type="button" data-k="' + k + '" data-v="' + v + '" aria-pressed="' + (opts[k] === v) + '">' + String(v).replace(/^--(w|series|ui)-/, '') + '</button>').join('') + '</span>').join('');
    let parts = 0; current.traverse((x) => { if (x.isMesh) parts++; });
    $('#info').textContent = parts + ' parts · ' + s.x.toFixed(1) + ' × ' + s.y.toFixed(1) + ' × ' + s.z.toFixed(1) + ' units' + (def.animate ? '' : ' · no animation');
    if (location.hash.slice(1) !== n) { try { history.replaceState(null, '', '#' + n); } catch (e) { /* the address stays as it is */ } }
  }

  function loop(now) {
    const fixed = query.get('t'), t = fixed !== null ? +fixed : now, def = ASSETS[name];
    if (current) {
      if ($('#spin').checked && !reduced && fixed === null) current.rotation.y = now * 0.0005; else if (query.get('turn')) current.rotation.y = +query.get('turn');
      if (def && def.animate) def.animate(current, Object.assign({}, opts, { now: t, moving: $('#anim').checked && !reduced }));
    }
    controls.update(); renderer.render(scene, camera); requestAnimationFrame(loop);
  }
})();
