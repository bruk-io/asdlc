    /* ---- the shared kit: materials, textures and base shapes (src/shared/kit.js) ---- */
    const kit = makeKit(css), { mat, mats, toon, canvasTex, prism } = kit, { box, sph, cone, tor, cyl } = kit.geo;
    const add = (geo, m, sx, sy, sz, x, y, z, cast) => { const o = kit.mesh(geo, m, sx, sy, sz, x, y, z, !!cast); scene.add(o); return o; };
    const place = (name, opts, x, y, z, turn) => { const o = kit.make(name, opts); o.position.set(x, y, z); if (turn) o.rotation.y = turn; scene.add(o); return o; };
