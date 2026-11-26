    /* ---- camera controls ---- */
    const OV = Math.max(K, PLANET * 3.4 / 91);   // far enough back to see the whole planet
    const VIEWS = {
      overview: { pos: [-58 * OV, 47 * OV, mid + 52 * OV], tgt: [0, 1.5, mid] },
    };
    camera.position.fromArray(VIEWS.overview.pos);
    const controls = new THREE.OrbitControls(camera, el);
    controls.target.fromArray(VIEWS.overview.tgt);
    controls.enableDamping = true; controls.dampingFactor = 0.1; controls.rotateSpeed = 0.65; controls.zoomSpeed = 0.9; controls.panSpeed = 1.1;
    controls.screenSpacePanning = false; controls.maxPolarAngle = Math.PI * 0.49; controls.minDistance = 4; controls.maxDistance = Math.max(230 * K, PLANET * 6);
    // Map-style mouse: left-drag moves across the ground, right-drag (or Shift-drag) turns, wheel zooms toward the pointer.
    controls.mouseButtons = { LEFT: -1, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
    controls.touches = { ONE: -1, TWO: THREE.TOUCH.DOLLY_ROTATE };   // one finger rolls the planet (see the grab code); two fingers zoom and turn
    let userMoved = -1e9, fly = null;
    controls.addEventListener('start', () => { userMoved = performance.now(); fly = null; });

