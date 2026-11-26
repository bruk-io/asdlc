    /* ---- lights: sky light, fill, and the sun (or moon) that casts the shadows ---- */
    const skyTex = canvasTex(4, 256, () => {}); scene.background = skyTex;
    const hemi = new THREE.HemisphereLight(0xffffff, 0x8899aa, 0.62), amb = new THREE.AmbientLight(0xffffff, 0.12); scene.add(hemi, amb);
    const sun = new THREE.DirectionalLight(0xffffff, 0.8); sun.position.set(-30, 48, mid + 22); sun.target.position.set(0, 0, mid); scene.add(sun, sun.target);
    sun.castShadow = true; sun.shadow.mapSize.set(4096, 4096); sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.05; sun.shadow.radius = 3;
    const sc = sun.shadow.camera, ext = Math.max(mid, halfW) + 70; sc.left = -ext; sc.right = ext; sc.top = ext; sc.bottom = -ext; sc.near = 1; sc.far = 260 * K; sc.updateProjectionMatrix(); PLANET_VIEW.flatFrustum = sun.shadow._frustum;
