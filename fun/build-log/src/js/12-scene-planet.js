    /* ---- the planet ----
       The village is laid out flat, and the replay, the walking and the shadows are all worked out on that flat map. When it is drawn, the map is wrapped
       onto a ball once and for all, with the middle of the village at the top: how far a point is from the middle becomes an angle round the ball, and its
       height becomes height above the surface. The planet never changes shape. The camera is steered on the flat map too (which keeps the controls
       simple), and is then carried onto the ball to the matching place, standing upright on the surface there. The wrap closes at the point opposite the
       village, where everything would be squeezed together, so land, trees and clouds sink under the sea as they near it and that point is open water. */
    const PLANET_VIEW = { flatFrustum: null };   // the sun's shadow frustum, once the sun exists
    const PLANET = 90, BEND = { value: new THREE.Vector4(0, mid, PLANET, 1) };   // x, z of the top; radius; on
    const BEND_GLSL = ['uniform vec4 uBend;',
      'vec3 bendWorld(vec3 p) { if (uBend.w < 0.5) return p; vec2 d = p.xz - uBend.xy; float len = length(d); if (len < 0.0001) return p; float th = min(len / uBend.z, 3.14159), far = smoothstep(2.15, 2.8, th), y = mix(p.y, p.y > -1.86 ? -4.9 : (p.y < -2.0 ? p.y : -1.9), far), r = uBend.z + y, s = sin(th) * r / len; return vec3(uBend.x + d.x * s, cos(th) * r - uBend.z, uBend.y + d.y * s); }',
      'vec3 bendDir(vec3 p, vec3 n) { if (uBend.w < 0.5) return n; vec2 d = p.xz - uBend.xy; float len = length(d); if (len < 0.0001) return n; vec2 e = d / len; float th = min(len / uBend.z, 3.14159), a = dot(n.xz, e), b = dot(n.xz, vec2(-e.y, e.x));',
      '  return a * vec3(e.x * cos(th), -sin(th), e.y * cos(th)) + n.y * vec3(e.x * sin(th), cos(th), e.y * sin(th)) + b * vec3(-e.y, 0.0, e.x); }'].join('\n');
    THREE.ShaderChunk.bend_world = BEND_GLSL;
    if (!THREE.ShaderChunk.common.includes('uBend')) {
      THREE.ShaderChunk.common += '\n' + BEND_GLSL + '\n';
      // The shadow pass looks through a flat (orthographic) camera and must stay unbent; the view camera is in perspective.
      THREE.ShaderChunk.project_vertex = ['vec4 mvPosition = vec4( transformed, 1.0 );', '#ifdef USE_INSTANCING', '  mvPosition = instanceMatrix * mvPosition;', '#endif',
        'if ( isPerspectiveMatrix( projectionMatrix ) ) { vec4 bw = modelMatrix * mvPosition; bw.xyz = bendWorld( bw.xyz ); mvPosition = viewMatrix * bw; } else mvPosition = modelViewMatrix * mvPosition;', 'gl_Position = projectionMatrix * mvPosition;'].join('\n');
      // Surfaces are lit by the way they face on the ball, not on the flat map, so the sun lights one side of the planet and leaves the other in shade.
      THREE.ShaderChunk.defaultnormal_vertex += ['', 'if ( isPerspectiveMatrix( projectionMatrix ) ) {', '  vec4 bendAt = vec4( position, 1.0 );', '#ifdef USE_INSTANCING', '  bendAt = instanceMatrix * bendAt;', '#endif',
        '  transformedNormal = normalize( mat3( viewMatrix ) * bendDir( ( modelMatrix * bendAt ).xyz, normalize( transformedNormal * mat3( viewMatrix ) ) ) );', '}'].join('\n');
      const sv = THREE.ShaderLib.sprite.vertexShader, flat = 'vec4 mvPosition = modelViewMatrix * vec4( 0.0, 0.0, 0.0, 1.0 );';
      if (sv.includes(flat)) THREE.ShaderLib.sprite.vertexShader = sv.replace(flat, 'vec4 bw = modelMatrix * vec4( 0.0, 0.0, 0.0, 1.0 ); bw.xyz = bendWorld( bw.xyz ); vec4 mvPosition = viewMatrix * bw;');
      THREE.Material.prototype.onBeforeCompile = function (shader) { shader.uniforms.uBend = BEND; };   // every material shares the one value, set once a frame
      // What is out of view is skipped, as usual, but the test has to be made where a thing is drawn, not where it sits on the flat map:
      // its bounding ball is carried onto the planet first. The shadow pass looks at the flat map, so it keeps the ordinary test.
      // Anything beyond the far side's sinking zone is under the sea and is skipped outright.
      const flatTest = THREE.Frustum.prototype.intersectsObject, ball = new THREE.Sphere(), spot = new THREE.Vector3();
      const onPlanet = (frustum, radius) => { if (Math.hypot(spot.x - BEND.value.x, spot.z - BEND.value.y) / PLANET > 2.85) return false; bendPoint(ball.center.copy(spot)); ball.radius = radius * 1.4 + 0.6; return frustum.intersectsSphere(ball); };
      THREE.Frustum.prototype.intersectsObject = function (object) {
        if (this === PLANET_VIEW.flatFrustum) return flatTest.call(this, object);
        const geo = object.geometry; if (geo.userData.wide) return true; if (geo.boundingSphere === null) geo.computeBoundingSphere();
        spot.copy(geo.boundingSphere.center).applyMatrix4(object.matrixWorld); return onPlanet(this, geo.boundingSphere.radius * object.matrixWorld.getMaxScaleOnAxis());
      };
      THREE.Frustum.prototype.intersectsSprite = function (sprite) { spot.setFromMatrixPosition(sprite.matrixWorld); const e = sprite.matrixWorld.elements; return onPlanet(this, 0.7072 * Math.max(Math.hypot(e[0], e[1], e[2]), Math.hypot(e[4], e[5], e[6]))); };   // what is in view is decided after the bend, so nothing is culled before it
    }
    // The same wrap, and its reverse, for the few things worked out in script: labels, and what is under the pointer.
    const bendPoint = (v) => { const dx = v.x - BEND.value.x, dz = v.z - BEND.value.y, len = Math.hypot(dx, dz); if (len < 1e-4) return v; const th = Math.min(len / PLANET, Math.PI), r = PLANET + v.y, s = Math.sin(th) * r / len; return v.set(BEND.value.x + dx * s, Math.cos(th) * r - PLANET, BEND.value.y + dz * s); };
    const unbendPoint = (v) => { const x = v.x - BEND.value.x, y = v.y + PLANET, z = v.z - BEND.value.y, r = Math.hypot(x, y, z), h = Math.hypot(x, z); if (h < 1e-5) return v.set(BEND.value.x, r - PLANET, BEND.value.y); const k = Math.acos(Math.max(-1, Math.min(1, y / r))) * PLANET / h; return v.set(BEND.value.x + x * k, r - PLANET, BEND.value.y + z * k); };
    // The camera that actually looks at the planet. `camera` is the one the controls steer on the flat map; syncView() carries it onto the ball.
    const view = new THREE.PerspectiveCamera(), frameQ = new THREE.Quaternion(), fM = new THREE.Matrix4(), fX = new THREE.Vector3(), fY = new THREE.Vector3(), fZ = new THREE.Vector3(), fO = new THREE.Vector3();
    const frameDir = (T, nx, ny, nz, out) => { const dx = T.x - BEND.value.x, dz = T.z - BEND.value.y, len = Math.hypot(dx, dz); if (len < 1e-4) return out.set(nx, ny, nz);
      const ex = dx / len, ez = dz / len, th = Math.min(len / PLANET, Math.PI), a = nx * ex + nz * ez, b = -nx * ez + nz * ex, c = Math.cos(th), s = Math.sin(th); return out.set(a * ex * c + ny * ex * s - b * ez, -a * s + ny * c, a * ez * c + ny * ez * s + b * ex); };
    function syncView() { const T = controls.target; frameQ.setFromRotationMatrix(fM.makeBasis(frameDir(T, 1, 0, 0, fX), frameDir(T, 0, 1, 0, fY), frameDir(T, 0, 0, 1, fZ))); bendPoint(fO.copy(T));
      view.position.copy(camera.position).sub(T).applyQuaternion(frameQ).add(fO); view.quaternion.copy(frameQ).multiply(camera.quaternion);
      view.projectionMatrix.copy(camera.projectionMatrix); view.projectionMatrixInverse.copy(camera.projectionMatrixInverse); view.updateMatrixWorld(true); }
    // A flat rounded rectangle made of a fine grid, so that it can follow the curve. Its texture coordinates are in scene units.
    const sheet = (w, d, r, cell) => { const g = new THREE.PlaneGeometry(w, d, Math.max(1, Math.round(w / cell)), Math.max(1, Math.round(d / cell))); g.rotateX(-Math.PI / 2); const p = g.attributes.position, uv = g.attributes.uv;
      for (let i = 0; i < p.count; i++) { let x = p.getX(i), z = p.getZ(i); const ax = Math.abs(x) - (w / 2 - r), az = Math.abs(z) - (d / 2 - r);
        if (r > 0 && ax > 0 && az > 0) { const l = Math.hypot(ax, az); if (l > r) { x = Math.sign(x) * (w / 2 - r + ax / l * r); z = Math.sign(z) * (d / 2 - r + az / l * r); p.setX(i, x); p.setZ(i, z); } } uv.setXY(i, x, -z); } g.userData.wide = true; return g; };   // wide: too big for the in-view test, always drawn
