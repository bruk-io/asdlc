  /* ---------- three ---------- */
  function setupThree() {
    const stage = $('#stage');
    if (THREE.ColorManagement) THREE.ColorManagement.legacyMode = false;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(2, devicePixelRatio || 1));
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.shadowMap.autoUpdate = false;
    const el = renderer.domElement; el.tabIndex = 0; el.setAttribute('aria-label', '3D village of task buildings. Drag to move, right-drag to turn, scroll to zoom. Arrow keys scrub time; W A S D move, Q and E turn, plus and minus zoom.');
    stage.insertBefore(el, stage.firstChild);
    el.addEventListener('contextmenu', (ev) => ev.preventDefault());
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 2600);
    const depth = (rows.length - 1) * ROW_GAP, mid = depth * 0.5;
    const widest = Math.max(...rows.map((r) => Math.max(1, r.towers.length) * COL_GAP + 1.2)), halfW = widest / 2 + 13, z0 = -13, z1 = depth + 11;
    const K = Math.max(1, depth / 78, widest / 25.5); // how much bigger the village is than the size the camera, fog and light were first tuned for
