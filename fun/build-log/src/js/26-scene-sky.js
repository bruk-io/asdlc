    /* ---- the sky dome, and the planet's rim of air ---- */
    // The sky is a dome around the camera, painted by a shader: a gradient, drifting cartoon clouds, twinkling stars,
    // and a sun and a crescent moon that cross the sky with the clock.
    const skyU = { top: { value: new THREE.Color() }, bot: { value: new THREE.Color() }, dusk: { value: new THREE.Color('#ffb27a') }, sunDir: { value: new THREE.Vector3(0, 1, 0) }, moonDir: { value: new THREE.Vector3(0, -1, 0) }, night: { value: 0 }, duskAmt: { value: 0 }, time: { value: 0 }, space: { value: 0 } };
    const dome = new THREE.Mesh(new THREE.SphereGeometry(2300, 40, 24), new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false, fog: false, uniforms: skyU,
      vertexShader: 'varying vec3 vDir; void main() { vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: [
        'uniform vec3 top, bot, dusk, sunDir, moonDir; uniform float night, duskAmt, time, space; varying vec3 vDir;',
        'float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
        'float hash3(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }',
        'float noise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y); }',
        'float fbm(vec2 p) { float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * noise(p); p = p * 2.03 + 17.0; a *= 0.5; } return s; }',
        // One layer of stars: the sky is cut into small cells, and some cells hold a star of their own size, tint and twinkle.
        'vec3 stars(vec3 d, float scale, float density) { vec3 p = d * scale, c = floor(p); float r = hash3(c); if (r < density) return vec3(0.0);',
        '  vec3 at = c + 0.5 + (vec3(hash3(c + 1.7), hash3(c + 5.3), hash3(c + 9.1)) - 0.5) * 0.6; float size = 0.05 + 0.13 * hash3(c + 3.3), b = smoothstep(size, 0.0, length(p - at));',
        '  vec3 tint = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.86, 0.7), hash3(c + 7.7)); return tint * b * (0.6 + 0.4 * sin(time * (1.0 + r * 3.0) + r * 60.0)); }',
        'void main() {',
        '  vec3 d = normalize(vDir); float h = d.y, g = pow(1.0 - clamp(abs(h), 0.0, 1.0), 2.4);',                       // g: 1 at the horizon, 0 overhead
        '  float sd = max(dot(d, sunDir), 0.0), md = max(dot(d, moonDir), 0.0), day = 1.0 - night, dark = max(night, space);',
        '  float sunUp = smoothstep(-0.12, 0.05, sunDir.y), moonUp = smoothstep(-0.12, 0.05, moonDir.y);',
        // the air: deep overhead, pale at the horizon, and at dusk bands of orange, pink and violet on the side the sun is going down
        '  vec3 col = mix(top * mix(vec3(0.5, 0.7, 0.98), vec3(1.0), night), bot, g);',
        '  float side = 0.3 + 0.7 * pow(sd, 2.0);',
        '  col = mix(col, vec3(0.62, 0.42, 0.82), duskAmt * 0.45 * (1.0 - g));',
        '  col = mix(col, vec3(1.0, 0.56, 0.66), duskAmt * 0.7 * side * smoothstep(0.05, 0.6, g));',
        '  col = mix(col, vec3(1.0, 0.62, 0.3), duskAmt * side * pow(g, 2.2));',
        '  col += vec3(1.0, 0.82, 0.55) * (pow(sd, 5.0) * 0.16 + pow(sd, 30.0) * 0.22) * sunUp * day;',                 // light scattered round the sun
        // far out, the air gives way to space
        '  vec3 deep = vec3(0.012, 0.018, 0.06) + vec3(0.03, 0.02, 0.07) * fbm(d.xy * 2.0 + d.z);',
        '  col = mix(col, deep, space);',
        // the night sky: three layers of stars, a band of milky light with coloured clouds of gas in it
        '  if (dark > 0.02) {',
        '    vec3 axis = normalize(vec3(0.35, 0.5, 0.8)); float band = pow(1.0 - abs(dot(d, axis)), 6.0), dust = fbm(d.xz * 5.0 + d.y * 3.0), gas = fbm(d.zy * 2.6 + d.x * 2.0 + 9.0);',
        '    col += (vec3(0.5, 0.55, 0.85) * band * (0.25 + dust * 0.9) + vec3(0.75, 0.3, 0.7) * band * smoothstep(0.5, 0.8, gas) * 0.5 + vec3(0.15, 0.55, 0.6) * smoothstep(0.62, 0.9, gas) * 0.16) * dark * 0.55;',
        '    col += (stars(d, 55.0, 0.86) * 1.2 + stars(d, 110.0, 0.8) * 0.8 + stars(d, 190.0, 0.7) * 0.5 * (1.0 + band * 2.0)) * dark;',
        // a shooting star every few seconds
        '    float slot = floor(time / 5.0), ph = fract(time / 5.0) * 3.5; if (ph < 1.0 && hash(vec2(slot, 9.0)) > 0.45) {',   // now and then, not on a beat
        '      vec3 a0 = normalize(vec3(hash(vec2(slot, 1.0)) - 0.5, 0.35 + hash(vec2(slot, 2.0)) * 0.5, hash(vec2(slot, 3.0)) - 0.5)), v = normalize(cross(a0, vec3(hash(vec2(slot, 4.0)) - 0.5, 1.0, 0.3)));',
        '      vec3 a = normalize(a0 + v * ph * 0.5), b = normalize(a0 + v * max(0.0, ph - 0.45) * 0.5), ab = b - a; float k = clamp(dot(d - a, ab) / max(dot(ab, ab), 1e-6), 0.0, 1.0);',
        '      col += vec3(1.0, 0.97, 0.85) * (smoothstep(0.007, 0.0, length(d - a - ab * k)) * (1.0 - k) + smoothstep(0.016, 0.0, length(d - a)) * 0.8) * sin(ph * 3.14159) * dark * 1.4;',
        '    }',
        // curtains of green and violet light in the northern sky
        '    float ang = atan(d.x, d.z), wav = fbm(vec2(ang * 2.2 + time * 0.03, time * 0.02)), hc = 0.22 + wav * 0.3;',
        '    float curtain = exp(-pow((h - hc) / 0.09, 2.0)) * (0.55 + 0.45 * sin(ang * 46.0 + fbm(vec2(ang * 7.0, time * 0.1)) * 7.0)) * smoothstep(0.1, 0.75, d.z) * smoothstep(0.0, 0.15, h);',
        '    col += mix(vec3(0.2, 1.0, 0.6), vec3(0.6, 0.35, 1.0), smoothstep(hc - 0.05, hc + 0.12, h)) * curtain * night * (1.0 - space) * 0.42;',
        // a ringed world hanging far away
        '    vec3 wp = normalize(vec3(-0.55, 0.42, -0.72)); if (dot(d, wp) > 0.0) { vec3 bx = normalize(cross(vec3(0.0, 1.0, 0.0), wp)), by = cross(wp, bx); vec2 q = vec2(dot(d, bx), dot(d, by)) / 0.06; float rr = length(q);',
        '      float tilt = -q.x * 0.39 + q.y * 0.92, rl = length(vec2(q.x * 0.92 + q.y * 0.39, tilt * 3.3)), disc = smoothstep(1.0, 0.95, rr), ring = smoothstep(1.3, 1.4, rl) * smoothstep(2.15, 2.05, rl) * (0.7 + 0.3 * step(0.5, fract(rl * 5.0)));',
        '      vec3 n = vec3(q, sqrt(max(0.0, 1.0 - rr * rr))); float l = 0.3 + 0.7 * floor(clamp(dot(n, normalize(vec3(0.55, 0.45, 0.7))), 0.0, 1.0) * 3.0 + 0.5) / 3.0;',
        '      col = mix(col, mix(vec3(0.98, 0.66, 0.5), vec3(0.9, 0.5, 0.56), step(0.5, fract(q.y * 2.3 + 0.2 + sin(q.x * 2.0) * 0.06))) * l, disc * dark);',
        '      col = mix(col, vec3(0.98, 0.9, 0.75), ring * dark * 0.9 * (1.0 - disc * step(0.0, tilt)));',
        '    }',
        '  }',
        // sun and moon
        '  col += vec3(1.0, 0.94, 0.72) * (smoothstep(0.9985, 0.9989, sd) + pow(sd, 120.0) * 0.5 + pow(sd, 12.0) * 0.1 * (1.0 + duskAmt)) * sunUp;',
        '  float bite = smoothstep(0.9990, 0.9992, dot(d, normalize(moonDir + vec3(0.022, 0.01, 0.0))));',
        '  col += vec3(0.95, 0.96, 1.0) * (max(smoothstep(0.9990, 0.9992, md) - bite, 0.0) + pow(md, 260.0) * 0.25 + pow(md, 20.0) * 0.06) * moonUp;',
        // clouds, seen from the ground: three flat tones, with a bright rim where the sun is behind them, high streaks above and a bank on the horizon
        '  if (h > -0.02 && space < 0.98) { float air = 1.0 - space;',
        '    vec3 lit = mix(mix(vec3(1.0), vec3(0.4, 0.46, 0.72), night), dusk, duskAmt * 0.55) + vec3(1.0, 0.8, 0.55) * pow(sd, 10.0) * 0.5 * sunUp;',
        '    vec3 shade = mix(mix(vec3(0.6, 0.72, 0.9), vec3(0.2, 0.25, 0.48), night), vec3(0.75, 0.42, 0.5), duskAmt * 0.6);',
        '    float hh = max(h, 0.0); vec2 uv = d.xz / (hh + 0.22) * 2.6 + vec2(time * 0.012, time * 0.004);',
        '    float streak = fbm(uv * vec2(0.22, 1.5) + vec2(time * 0.02, 5.0)); col = mix(col, lit, smoothstep(0.6, 0.85, streak) * smoothstep(0.25, 0.6, h) * 0.3 * air);',
        '    float n = fbm(uv) + 0.25 * fbm(uv * 3.1 - time * 0.01), under = fbm(uv + vec2(0.0, 0.16)) + 0.25 * fbm((uv + vec2(0.0, 0.16)) * 3.1 - time * 0.01);',
        '    vec3 puff = mix(shade, mix(lit * 0.93, lit, smoothstep(0.02, 0.05, n - under)), smoothstep(-0.05, -0.01, n - under));',
        '    col = mix(col, puff, smoothstep(0.68, 0.7, n) * smoothstep(0.03, 0.2, h) * air);',
        '    vec2 ring = normalize(d.xz + 1e-5);',
        '    float bank = (fbm(ring * 2.6 + vec2(time * 0.004, 3.0)) - 0.34) * 0.46 + (fbm(ring * 9.0 - time * 0.006) - 0.5) * 0.06 + (fbm(ring * 22.0 + time * 0.008) - 0.5) * 0.025, depth = bank - h;',
        '    vec3 heap = mix(lit, mix(lit, shade, 0.4), smoothstep(0.012, 0.03, depth)); heap = mix(bot, heap, smoothstep(-0.01, 0.07, h));',
        '    col = mix(col, heap, smoothstep(0.0, 0.006, depth) * air);',
        '  }',
        '  gl_FragColor = vec4(col, 1.0);',
        '  #include <encodings_fragment>',
        '}'].join('\n') }));
    dome.renderOrder = -10; dome.frustumCulled = false; scene.add(dome);
    // The planet's air, seen from outside: a thin shell that glows along the planet's edge, blue by day, warm on the side of a low sun, dim at night.
    const airU = { tint: { value: new THREE.Color() }, warm: { value: new THREE.Color('#ff9a5a') }, sunView: { value: new THREE.Vector3() }, amount: { value: 0 }, duskAmt: skyU.duskAmt };
    const air = new THREE.Mesh(new THREE.SphereGeometry(PLANET * 1.16, 64, 40), new THREE.ShaderMaterial({ side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, uniforms: airU,
      vertexShader: 'varying vec3 vN; void main() { vN = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: 'uniform vec3 tint, warm, sunView; uniform float amount, duskAmt; varying vec3 vN; void main() { vec3 n = normalize(vN); float rim = pow(smoothstep(0.0, 0.55, -n.z), 1.6), lit = 0.35 + 0.65 * smoothstep(-0.4, 0.6, dot(-n, sunView)); gl_FragColor = vec4(mix(tint, warm, duskAmt * 0.6) * rim * lit * amount, 1.0); }' }));
    air.frustumCulled = false; air.renderOrder = -5; scene.add(air);

