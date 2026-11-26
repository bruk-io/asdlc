    /* ---- the sea ---- */
    // The sea is a sheet that covers the whole planet. It stays centred under the view and its ripples stay put on the surface.
    const waterTex = kit.tex('water'); waterTex.repeat.set(0.08, 0.08); mats['--w-water'] = new THREE.MeshBasicMaterial({ color: 0x888888, map: waterTex });
    /* The sea. A map of how deep the water is everywhere lets it behave differently by depth:
       - colour runs from pale turquoise over the sand, through blue, to dark blue in deep water;
       - waves are a sum of four swells running in different directions, lower in the shallows so they do not climb the beach;
       - foam hugs the waterline and breathes in and out, with thin lines of surf rolling toward the shore behind it;
       - a moving web of light plays over the shallows. Open water is left calm: no white patches;
       - the surface mirrors the sky, more at flat angles, and carries a broken path of glints toward the sun or the moon. */
    const waterU = { time: { value: 0 }, night: { value: 0 }, depth: { value: null }, box: { value: new THREE.Vector3() }, sky: { value: new THREE.Color() }, sunDir: { value: new THREE.Vector3(0, 1, 0) }, sunCol: { value: new THREE.Color() }, sunAmt: { value: 1 } };
    { const N = 256, X = islandW + Math.PI * PLANET * 2, Z = islandD + Math.PI * PLANET * 2, px = new Uint8Array(N * N * 4);
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) { const h = ground((i + 0.5) / N * X - X / 2, (j + 0.5) / N * Z - Z / 2 + zc), v = Math.round(Math.min(1, Math.max(0, (h + 5) / 6)) * 255), o = (j * N + i) * 4; px[o] = px[o + 1] = px[o + 2] = v; px[o + 3] = 255; }
      const tex = new THREE.DataTexture(px, N, N, THREE.RGBAFormat); tex.minFilter = tex.magFilter = THREE.LinearFilter; tex.needsUpdate = true; waterU.depth.value = tex; waterU.box.value.set(X, Z, zc); }
    mats['--w-water'].onBeforeCompile = (shader) => { Object.assign(shader.uniforms, { uBend: BEND, uSea: waterU.time, uSeaNight: waterU.night, uDepthTex: waterU.depth, uBox: waterU.box, uSkyCol: waterU.sky, uSunFlat: waterU.sunDir, uSunCol: waterU.sunCol, uSunAmt: waterU.sunAmt });
      const head = 'uniform float uSea, uSeaNight; uniform sampler2D uDepthTex; uniform vec3 uBox; varying vec3 vSea, vBent; varying vec2 vSeaUv; varying float vWave, vCalm; uniform vec3 uSkyCol, uSunFlat, uSunCol; uniform float uSunAmt;\nfloat seaDepth(vec2 uv) { return max(0.0, -1.84 - (texture2D(uDepthTex, uv).r * 6.0 - 5.0)); }\n';
      shader.vertexShader = head + shader.vertexShader.replace('#include <begin_vertex>', ['#include <begin_vertex>', 'vec4 sea0 = modelMatrix * vec4(transformed, 1.0); vSea = sea0.xyz; vSeaUv = vec2(sea0.x / uBox.x + 0.5, (sea0.z - uBox.z) / uBox.y + 0.5);',
        'float sw = sin(dot(sea0.xz, vec2(0.28, 0.10)) + uSea * 1.2) + sin(dot(sea0.xz, vec2(-0.12, 0.24)) + uSea * 0.95) * 0.8 + sin(dot(sea0.xz, vec2(0.20, -0.33)) + uSea * 1.5) * 0.5 + sin(dot(sea0.xz, vec2(0.45, 0.38)) + uSea * 2.0) * 0.25;',
        'float calm = 1.0 - smoothstep(1.85, 2.1, length(sea0.xz - uBend.xy) / uBend.z); vWave = sw / 2.55 * calm; transformed.y += sw * 0.14 * (0.2 + 0.8 * min(1.0, seaDepth(vSeaUv) / 3.0)) * calm; vCalm = calm; vec4 seaB = modelMatrix * vec4(transformed, 1.0); vBent = bendWorld(seaB.xyz);'].join('\n'));
      shader.fragmentShader = head + 'float seaHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }\nfloat seaNoise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(seaHash(i), seaHash(i + vec2(1.0, 0.0)), f.x), mix(seaHash(i + vec2(0.0, 1.0)), seaHash(i + vec2(1.0, 1.0)), f.x), f.y); }\n' + shader.fragmentShader.replace('#include <map_fragment>', ['#include <map_fragment>',
        'float depth = mix(seaDepth(vSeaUv), 6.0, smoothstep(1.9, 2.4, length(vSea.xz - uBend.xy) / uBend.z)), day = 1.0 - 0.75 * uSeaNight;',   // round the far side it is all deep water
        'vec3 shallowC = mix(diffuse * 1.2, vec3(0.5, 0.93, 0.85), 0.7 * day), seaC = mix(shallowC, diffuse, smoothstep(0.0, 1.7, depth)); seaC = mix(seaC, diffuse * 0.68, smoothstep(1.7, 3.2, depth));',
        'seaC = mix(mix(seaC, vec3(0.93, 0.89, 0.7) * day, 0.45), seaC, smoothstep(0.0, 0.5, depth));',                                         // the sand shows through at the very edge
        'vec2 q = vSea.xz * 0.34; for (int i = 0; i < 3; i++) q += vec2(sin(q.y * 1.3 + uSea * 0.7), cos(q.x * 1.1 - uSea * 0.6)) * 0.6;',
        'float web = smoothstep(0.5, 0.95, abs(sin(q.x * 2.0) * sin(q.y * 2.0))); seaC += vec3(0.5, 0.6, 0.55) * web * (0.1 + 0.28 * (1.0 - smoothstep(0.3, 2.4, depth))) * day;',
        'seaC *= (0.93 + 0.09 * vWave) * (0.9 + 0.2 * seaNoise(vSea.xz * 0.035 + uSea * 0.012));',                                                  // lighter crests, and broad slow patches like currents
        // the shape of the surface here: the slope of the four swells, roughened by fine ripples, and stood upright on the planet
        'vec2 sl = vec2(0.28, 0.10) * cos(dot(vSea.xz, vec2(0.28, 0.10)) + uSea * 1.2) + vec2(-0.12, 0.24) * cos(dot(vSea.xz, vec2(-0.12, 0.24)) + uSea * 0.95) * 0.8 + vec2(0.20, -0.33) * cos(dot(vSea.xz, vec2(0.20, -0.33)) + uSea * 1.5) * 0.5 + vec2(0.45, 0.38) * cos(dot(vSea.xz, vec2(0.45, 0.38)) + uSea * 2.0) * 0.25;',
        'vec2 rp = vSea.xz * 1.5; vec2 fine = vec2(seaNoise(rp + vec2(uSea * 0.5, 0.0)) - seaNoise(rp + vec2(0.35 + uSea * 0.5, 0.0)), seaNoise(rp * 1.3 - vec2(0.0, uSea * 0.4)) - seaNoise(rp * 1.3 + vec2(0.0, 0.35 - uSea * 0.4)));',
        'vec3 nSea = normalize(bendDir(vSea, normalize(vec3(-sl.x * 0.14 * vCalm + fine.x * 0.5, 1.0, -sl.y * 0.14 * vCalm + fine.y * 0.5)))), toEye = normalize(cameraPosition - vBent), toSun = normalize(uSunFlat);',
        // the sky mirrored in it, more strongly the flatter the angle it is seen from
        'float mirror = pow(1.0 - max(dot(nSea, toEye), 0.0), 4.0); seaC = mix(seaC, uSkyCol * (1.0 + 0.15 * day), clamp(mirror, 0.0, 1.0) * 0.42);',
        // the path of light from the sun or moon, broken into glints by the ripples
        'float shine = pow(max(dot(nSea, normalize(toSun + toEye)), 0.0), 220.0), halo = pow(max(dot(nSea, normalize(toSun + toEye)), 0.0), 24.0);',
        'seaC += uSunCol * (smoothstep(0.3, 0.55, shine) * 0.9 + halo * 0.12) * uSunAmt * step(0.02, depth);',
        'float wobble = sin(vSea.x * 0.5 + vSea.z * 0.4) * 1.5, breath = 0.3 + 0.14 * sin(uSea * 1.3 + wobble);',
        'float edge = 1.0 - smoothstep(breath * 0.55, breath, depth), surf = smoothstep(0.78, 0.96, sin(depth * 6.5 - uSea * 2.0 + wobble)) * (1.0 - smoothstep(0.45, 1.7, depth)) * step(0.02, depth) * 0.75;',
        'float broken = smoothstep(0.25, 0.6, seaNoise(vSea.xz * 1.6 + vec2(uSea * 0.25, -uSea * 0.2)));',
        'diffuseColor.rgb = mix(seaC, vec3(1.0) * (0.55 + 0.45 * day), clamp(edge + surf * broken, 0.0, 1.0)) * mix(0.38, 1.0, smoothstep(-0.3, 0.3, dot(bendDir(vSea, vec3(0.0, 1.0, 0.0)), toSun)));'].join('\n')); };
    const SEA = Math.PI * 2 * PLANET * 1.01, water = new THREE.Mesh(sheet(SEA, SEA, 0, SEA / 230), mat('--w-water')); water.position.set(0, -1.9, mid); scene.add(water);
