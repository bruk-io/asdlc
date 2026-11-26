    /* ---- buildings: a plot per task, three wall blocks per agent run (cache read, cache write, output), then the parts that come and go ---- */
    const pickables = [];
    const ROOFS = ['pyramid', 'gable', 'mansard'], ROOF_COLS = ['--w-roof', '--w-roof-2', '--w-roof-3'], DOORS = ['--w-door', '--w-door-2', '--w-door-3'];
    towers.forEach((t, i) => {
      // Each building picks its windows, roof and door from its place in the list, so the same task always looks the same.
      const look = { win: (i * 7 + 1) % 3, roof: ROOFS[(i * 5) % 3], roofCol: ROOF_COLS[(i * 11 + (i >> 2)) % 3], door: DOORS[(i * 3 + (i >> 1)) % 3] };
      place('plot', {}, t.x, 0, t.z);
      t.agents.forEach((a) => {
        a.segs = ['r', 'w', 'o'].map((k) => { const m = kit.make('storey', { style: look.win }); Object.assign(m.userData, { agent: a, kind: k, h: a['c' + k] * HS }); m.visible = false; scene.add(m); pickables.push(m); return m; });
        a.slab = place('slab', {}, t.x, 0, t.z); a.slab.visible = false;
      });
      t.roof = place('roof', { style: look.roof, colour: look.roofCol }, t.x, 0, t.z); t.dome = place('dome', {}, t.x, 0, t.z); t.door = place('door', { colour: look.door }, t.x, 0.07, t.z + FOOT / 2);
      t.scaffold = place('scaffold', {}, t.x, 0.07, t.z); t.flag = place('flag', {}, t.x, 0, t.z);
      t.roof.visible = t.dome.visible = t.door.visible = t.scaffold.visible = t.flag.visible = false;
    });
    const sel = new THREE.Mesh(new THREE.TorusGeometry(FOOT * 0.92, 0.06, 8, 40), new THREE.MeshBasicMaterial({ color: 0xffffff })); sel.rotation.x = Math.PI / 2; sel.visible = false; scene.add(sel);

