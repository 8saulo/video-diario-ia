// Cena 3D em código (Three.js) para vídeos de fibra óptica / GPON.
// Tudo é desenhado aqui: cidade à noite, postes com cabo, CTO, OLT com cordões e ONU.
// Determinístico: a mesma t gera sempre o mesmo quadro (RNG com semente, sem relógio).
(function () {
  'use strict';
  const W3D = { on: false };
  let R, S, C, W, H, ACC, ACC2;
  const CUR = {};      // curvas da fibra
  const PULSES = [];   // { spr, curve, u0, speed, dir, kind }
  const OBJ = {};      // objetos usados nos planos de câmera
  const LABELS = [];   // { spr, shots }
  const SHOTS = {};

  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const std = (c, o) => new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.85, metalness: 0 }, o || {}));
  const bas = (c, o) => new THREE.MeshBasicMaterial(Object.assign({ color: c }, o || {}));
  const ease = u => 0.5 - 0.5 * Math.cos(Math.PI * Math.min(1, Math.max(0, u)));

  function glowTex() {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d'); const r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.25, 'rgba(255,255,255,.75)'); r.addColorStop(0.6, 'rgba(255,255,255,.18)'); r.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = r; g.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }
  let GLOW;
  function glow(color, size, op) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color, transparent: true, opacity: op == null ? 1 : op, blending: THREE.AdditiveBlending, depthWrite: false }));
    s.scale.set(size, size, 1); return s;
  }
  function label(txt, sub, color, h) {
    const c = document.createElement('canvas'); const g = c.getContext('2d');
    const f1 = '800 64px Figtree', f2 = '600 40px Figtree';
    g.font = f1; let w = g.measureText(txt).width; if (sub) { g.font = f2; w = Math.max(w, g.measureText(sub).width); }
    c.width = Math.ceil(w + 80); c.height = sub ? 170 : 110;
    g.fillStyle = 'rgba(10,14,24,.88)'; g.strokeStyle = color; g.lineWidth = 5;
    const rr = (x, y, ww, hh, r) => { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + ww, y, x + ww, y + hh, r); g.arcTo(x + ww, y + hh, x, y + hh, r); g.arcTo(x, y + hh, x, y, r); g.arcTo(x, y, x + ww, y, r); g.closePath(); };
    rr(4, 4, c.width - 8, c.height - 8, 22); g.fill(); g.stroke();
    g.fillStyle = color; g.font = f1; g.textBaseline = 'middle'; g.fillText(txt, 40, sub ? 58 : c.height / 2);
    if (sub) { g.fillStyle = 'rgba(235,240,250,.85)'; g.font = f2; g.fillText(sub, 40, 122); }
    const t = new THREE.CanvasTexture(c); t.anisotropy = 4;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false, depthTest: false }));
    const hh = h || 1; s.scale.set(hh * c.width / c.height, hh, 1); s.renderOrder = 10;
    return s;
  }
  function textPlane(lines, w, h, opts) {
    const c = document.createElement('canvas'); c.width = Math.round(w * 160); c.height = Math.round(h * 160);
    const g = c.getContext('2d'); g.fillStyle = opts.bg || 'rgba(0,0,0,0)'; g.fillRect(0, 0, c.width, c.height);
    g.fillStyle = opts.color || '#9aa3b2'; g.font = opts.font || '700 40px Figtree'; g.textAlign = 'center'; g.textBaseline = 'middle';
    lines.forEach(([t, x, y]) => g.fillText(t, x * c.width, y * c.height));
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true }));
    return m;
  }

  // ------------------------------------------------------------------ cidade
  function city() {
    const rnd = rng(7);
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), std(0x0c1018));
    ground.rotation.x = -Math.PI / 2; S.add(ground);
    const roadM = std(0x161b24);
    [-48, -24, 0, 24, 48].forEach(z => { const r = new THREE.Mesh(new THREE.PlaneGeometry(300, 5), roadM); r.rotation.x = -Math.PI / 2; r.position.set(0, 0.02, z); S.add(r); });
    [-60, -30, 0, 30, 60].forEach(x => { const r = new THREE.Mesh(new THREE.PlaneGeometry(5, 300), roadM); r.rotation.x = -Math.PI / 2; r.position.set(x, 0.021, 0); S.add(r); });

    const houses = [];
    for (let gx = -11; gx <= 11; gx++) for (let gz = -9; gz <= 9; gz++) {
      const x = gx * 7.5 + (rnd() - 0.5) * 1.2, z = gz * 6 + 3 + (rnd() - 0.5) * 0.8;
      if ([-48, -24, 0, 24, 48].some(r => Math.abs(z - r) < 4.6)) continue;
      if ([-60, -30, 0, 30, 60].some(r => Math.abs(x - r) < 5)) continue;
      const w = 4.2 + rnd() * 2, d = 3.8 + rnd() * 1.6, fl = rnd() < 0.35 ? 2 : 1, h = fl * 2.9;
      houses.push({ x, z, w, d, h, fl, roof: rnd() < 0.6, tank: rnd() < 0.5, col: rnd() });
    }
    const pal = [0xece3d3, 0xdfd3be, 0xf3ece0, 0xd2c6b0, 0xe6dccb];
    const hb = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), std(0xffffff), houses.length);
    const roofs = houses.filter(h => h.roof), tanks = houses.filter(h => !h.roof && h.tank);
    const rb = new THREE.InstancedMesh(new THREE.ConeGeometry(0.75, 1, 4, 1), std(0xffffff, { roughness: 0.7 }), roofs.length);
    const tk = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.5, 0.5, 0.7, 10), std(0x2f68d8, { roughness: 0.5 }), tanks.length);
    const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), Sc = V(1, 1, 1), E = new THREE.Euler();
    const col = new THREE.Color();
    houses.forEach((h, i) => {
      M.compose(V(h.x, h.h / 2, h.z), Q.identity(), V(h.w, h.h, h.d)); hb.setMatrixAt(i, M);
      hb.setColorAt(i, col.setHex(pal[Math.floor(h.col * pal.length)]));
    });
    roofs.forEach((h, i) => {
      E.set(0, Math.PI / 4, 0); Q.setFromEuler(E);
      M.compose(V(h.x, h.h + 0.8, h.z), Q, V(h.w * 0.98, 1.6, h.d * 0.98)); rb.setMatrixAt(i, M);
      rb.setColorAt(i, col.setHex(i % 3 ? 0xa9452b : 0x8c3a26));
    });
    tanks.forEach((h, i) => { M.compose(V(h.x + h.w * 0.2, h.h + 0.35, h.z - h.d * 0.15), Q.identity(), Sc); tk.setMatrixAt(i, M); });
    S.add(hb, rb, tk);

    // janelas: acesas (quentes ou frias) e apagadas
    const wins = [];
    houses.forEach(h => {
      for (let f = 0; f < h.fl; f++) for (const side of ['z', 'x']) {
        const n = side === 'z' ? Math.max(1, Math.floor(h.w / 1.8)) : Math.max(1, Math.floor(h.d / 1.9));
        for (let k = 0; k < n; k++) {
          const off = (k + 0.5) / n - 0.5;
          const y = f * 2.9 + 1.55;
          const p = side === 'z' ? V(h.x + off * h.w * 0.8, y, h.z + h.d / 2 + 0.02) : V(h.x + h.w / 2 + 0.02, y, h.z + off * h.d * 0.8);
          wins.push({ p, side, lit: rnd() < 0.62, cold: rnd() < 0.25 });
        }
      }
    });
    const wg = new THREE.PlaneGeometry(0.8, 0.9);
    const lit = wins.filter(w => w.lit), dark = wins.filter(w => !w.lit);
    const wl = new THREE.InstancedMesh(wg, bas(0xffffff), lit.length);
    const wd = new THREE.InstancedMesh(wg, std(0x1a2230), dark.length);
    const put = (im, arr, colored) => arr.forEach((w, i) => {
      E.set(0, w.side === 'z' ? 0 : Math.PI / 2, 0); Q.setFromEuler(E);
      M.compose(w.p, Q, Sc); im.setMatrixAt(i, M);
      if (colored) im.setColorAt(i, col.setHex(w.cold ? 0xdfe9ff : 0xffd48e));
    });
    put(wl, lit, true); put(wd, dark, false); S.add(wl, wd);

    // postes de luz com poça de luz no chão
    const lamps = [];
    [-48, -24, 0, 24, 48].forEach(z => { for (let x = -84; x <= 84; x += 14) lamps.push(V(x + (z % 48 ? 7 : 0), 0, z - 3.2)); });
    const lp = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.07, 0.09, 5, 6), std(0x20242c), lamps.length);
    const pool = new THREE.InstancedMesh(new THREE.PlaneGeometry(9, 9), new THREE.MeshBasicMaterial({ map: GLOW, color: 0xffb35a, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }), lamps.length);
    const bulb = new THREE.InstancedMesh(new THREE.SphereGeometry(0.22, 8, 6), bas(0xffe2a8), lamps.length);
    lamps.forEach((p, i) => {
      M.compose(V(p.x, 2.5, p.z), Q.identity(), Sc); lp.setMatrixAt(i, M);
      M.compose(V(p.x, 5.05, p.z), Q.identity(), Sc); bulb.setMatrixAt(i, M);
      E.set(-Math.PI / 2, 0, 0); Q.setFromEuler(E); M.compose(V(p.x, 0.05, p.z), Q, Sc); pool.setMatrixAt(i, M);
    });
    S.add(lp, pool, bulb);
  }

  // ------------------------------------------------------------------ rede: postes, cabo, CTO, ONU da casa
  function network() {
    const poleM = std(0x6d6a66, { roughness: 0.95 });
    const xs = [-56, -40, -24, -8, 8, 24, 40];
    const top = 8.6, z = 3.2;
    xs.forEach(x => {
      const p = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.22, 9, 8), poleM); p.position.set(x, 4.5, z); S.add(p);
      const arm = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.12, 1.6), poleM); arm.position.set(x, top, z); S.add(arm);
    });
    // cabo com catenária entre postes; a central (OLT) fica na ponta x = -64
    const pts = [V(-64, 6.5, z)];
    xs.forEach((x, i) => { pts.push(V(x, top, z)); if (i < xs.length - 1) pts.push(V(x + 8, top - 0.7, z)); });
    CUR.main = new THREE.CatmullRomCurve3(pts);
    S.add(new THREE.Mesh(new THREE.TubeGeometry(CUR.main, 300, 0.05, 6, false), std(0x15171c)));
    // central (prédio da OLT)
    const co = new THREE.Mesh(new THREE.BoxGeometry(8, 7, 7), std(0x2a3140)); co.position.set(-68, 3.5, z); S.add(co);
    const coL = label('OLT', 'central', '#4dc3ff', 1.4); coL.position.set(-68, 8.6, z); S.add(coL); LABELS.push({ spr: coL, shots: ['fibra', 'cidade', 'comparar'] });
    // CTO no poste 24
    const cto = new THREE.Mesh(new THREE.BoxGeometry(0.7, 1.1, 0.45), std(0x1c1f25)); cto.position.set(24, 6.6, z + 0.35); S.add(cto);
    OBJ.cto = cto.position.clone();
    const ctoL = label('CTO', 'splitter', '#4dc3ff', 0.9); ctoL.position.set(24, 7.9, z + 0.6); S.add(ctoL); LABELS.push({ spr: ctoL, shots: ['fibra', 'comparar'] });
    // drop até a casa do cliente (x 31, z 9.5)
    const house = V(31.5, 2.2, 8.2);
    const hs = new THREE.Mesh(new THREE.BoxGeometry(5.2, 4.4, 4.2), std(0xf0e7d8)); hs.position.set(31.5, 2.2, 10.3); S.add(hs);
    const hr = new THREE.Mesh(new THREE.ConeGeometry(0.75, 1, 4, 1), std(0xa9452b)); hr.rotation.y = Math.PI / 4; hr.scale.set(5.1, 1.6, 4.1); hr.position.set(31.5, 5.2, 10.3); S.add(hr);
    const hw = new THREE.Mesh(new THREE.PlaneGeometry(1, 1.1), bas(0xffd48e)); hw.position.set(30.2, 2.4, 8.18); S.add(hw);
    // macrocurvatura: laço apertado no poste, logo abaixo da CTO
    const loop = [];
    for (let i = 0; i <= 120; i++) { const a = i / 120 * Math.PI * 2 * 2.2; loop.push(V(24.45 + Math.cos(a) * 0.32, 5.3 + Math.sin(a) * 0.32 - i * 0.002, z + 0.42 + i * 0.0025)); }
    const drop = [V(24, 6.1, z + 0.4), V(24.3, 5.7, z + 0.42)].concat(loop).concat([V(25.5, 4.6, z + 1.5), V(28.5, 3.6, 6), house]);
    CUR.drop = new THREE.CatmullRomCurve3(drop);
    S.add(new THREE.Mesh(new THREE.TubeGeometry(CUR.drop, 400, 0.035, 6, false), std(0x1b1d22)));
    OBJ.loop = V(24.45, 5.3, z + 0.45);
    const pl = new THREE.PointLight(0xffd29a, 60, 22, 1.6); pl.position.set(27, 9, 9); S.add(pl);
    OBJ.ring = glow(0xff3b3b, 2.2, 0.0); OBJ.ring.position.copy(OBJ.loop).add(V(0, 0, 0.1)); S.add(OBJ.ring);
    const ringM = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.035, 8, 48), bas(0xff4a4a, { transparent: true, opacity: 0 }));
    ringM.position.copy(OBJ.loop).add(V(0, 0, 0.12)); S.add(ringM); OBJ.ringM = ringM;
    const onuL = label('ONU', 'cliente', '#4dc3ff', 1.0); onuL.position.set(31.5, 6.9, 8.4); S.add(onuL); LABELS.push({ spr: onuL, shots: ['fibra', 'comparar'] });
  }

  // ------------------------------------------------------------------ OLT (close) em x = -200
  function olt() {
    const g = new THREE.Group(); g.position.set(-200, 0, 0); S.add(g);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), std(0x0d1016)); floor.rotation.x = -Math.PI / 2; g.add(floor);
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(40, 20), std(0x111622)); wall.position.set(0, 6, -1.6); g.add(wall);
    const ch = new THREE.Mesh(new THREE.BoxGeometry(9, 1.7, 2.4), std(0x1d2431, { metalness: 0.4, roughness: 0.5 })); ch.position.set(0, 2.2, 0); g.add(ch);
    const strip = new THREE.Mesh(new THREE.BoxGeometry(9, 0.08, 0.05), bas(0x1aa3ff)); strip.position.set(0, 3.05, 1.21); g.add(strip);
    const cageM = std(0x9aa3b2, { metalness: 0.6, roughness: 0.35 }), conM = std(0x2f6bff, { roughness: 0.4 }), ledM = bas(0x3bff8a);
    const cordM = std(0xf2c21b, { roughness: 0.55 });
    const nums = [];
    OBJ.oltPorts = [];
    for (let r = 0; r < 2; r++) for (let k = 0; k < 8; k++) {
      const x = -3.85 + k * 1.1, y = 2.65 - r * 0.85, idx = r * 8 + k + 1;
      const cage = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.32, 0.1), cageM); cage.position.set(x, y, 1.23); g.add(cage);
      const led = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.08, 0.02), ledM); led.position.set(x + 0.42, y + 0.1, 1.23); g.add(led);
      nums.push([String(idx), (x + 4.5) / 9, 1 - ((y + 0.33) - 1.35) / 1.7]);
      const used = [1, 2, 3, 4, 6, 9, 10, 12, 13].includes(idx);
      if (!used) continue;
      const con = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.26, 0.5), conM); con.position.set(x, y, 1.5); g.add(con);
      const c = new THREE.CatmullRomCurve3([V(x, y, 1.75), V(x, y - 0.1, 2.3), V(x + (k - 3.5) * 0.08, y - 1.2, 2.6), V(x + (k - 3.5) * 0.25, 0.05, 3.4 + r * 0.4)]);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(c, 40, 0.06, 6, false), cordM); g.add(tube);
      OBJ.oltPorts.push({ idx, curve: c, x, y });
    }
    const np = textPlane(nums.map(([t, x, y]) => [t, x, y - 0.12]), 9, 1.7, { color: '#c7cfdb', font: '700 34px Figtree' });
    np.position.set(0, 2.2, 1.215); g.add(np);
    const ol = new THREE.PointLight(0xcfe2ff, 70, 30, 1.6); ol.position.set(2, 6, 7); g.add(ol);
    const l = label('GBIC GPON', 'classe B+ / C+', '#4dc3ff', 0.42); l.position.set(-0.55, 3.35, 1.6); g.add(l); LABELS.push({ spr: l, shots: ['olt'] });
    OBJ.oltG = g;
  }

  // ------------------------------------------------------------------ ONU (close) em x = +200
  function onu() {
    const g = new THREE.Group(); g.position.set(200, 0, 0); S.add(g);
    const table = new THREE.Mesh(new THREE.BoxGeometry(14, 0.4, 8), std(0x5a3b26, { roughness: 0.7 })); table.position.set(0, -0.2, 0); g.add(table);
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(30, 14), std(0x3a2f28)); wall.position.set(0, 6, -3); g.add(wall);
    const body = new THREE.Mesh(new THREE.BoxGeometry(4.2, 0.75, 2.8), std(0xf4f5f7, { roughness: 0.45 })); body.position.set(0, 0.38, 0); g.add(body);
    const top = new THREE.Mesh(new THREE.BoxGeometry(4.0, 0.06, 2.6), std(0xffffff, { roughness: 0.35 })); top.position.set(0, 0.78, 0); g.add(top);
    const fr = textPlane([['PWR', 0.12, 0.62], ['PON', 0.3, 0.62], ['LOS', 0.48, 0.62], ['LAN', 0.66, 0.62], ['WLAN', 0.86, 0.62]], 4.1, 0.6, { color: '#9aa1ab', font: '700 30px Figtree' });
    fr.position.set(0, 0.38, 1.405); g.add(fr);
    const ledM = bas(0x3bff8a);
    [0.12, 0.3, 0.66, 0.86].forEach(u => { const l = new THREE.Mesh(new THREE.CircleGeometry(0.05, 12), ledM); l.position.set(-2.05 + u * 4.1, 0.5, 1.41); g.add(l); });
    const c = new THREE.CatmullRomCurve3([V(-6, 3.5, -2.8), V(-4.5, 1.4, -2.2), V(-2.8, 0.45, -1.5), V(-1.6, 0.4, -1.4)]);
    g.add(new THREE.Mesh(new THREE.TubeGeometry(c, 40, 0.06, 6, false), std(0xf2c21b, { roughness: 0.55 })));
    OBJ.onuCurve = c;
    const l = label('ONU', 'na casa do cliente', '#4dc3ff', 0.55); l.position.set(0.6, 1.55, 0.6); g.add(l); LABELS.push({ spr: l, shots: ['onu'] });
    const lamp = new THREE.PointLight(0xffd2a0, 55, 30, 1.6); lamp.position.set(3, 6, 5); g.add(lamp);
  }

  // ------------------------------------------------------------------ pulsos de luz
  function pulses() {
    const D = ACC, U = ACC2;
    const add = (curve, n, speed, dir, color, size, kind, off) => {
      for (let i = 0; i < n; i++) {
        const s = glow(color, size, 1); S.add(s);
        PULSES.push({ spr: s, curve, u0: (off || 0) + i / n, speed, dir, kind });
      }
    };
    add(CUR.main, 6, 0.06, 1, D, 1.6, 'down');
    add(CUR.main, 5, 0.05, -1, U, 1.3, 'up', 0.07);
    add(CUR.drop, 3, 0.12, 1, D, 0.75, 'down_drop');
    add(CUR.drop, 3, 0.1, -1, U, 0.62, 'up_drop', 0.15);
    OBJ.oltPorts.forEach((p, i) => {
      add(p.curve, 2, 0.35, 1, D, 0.55, 'olt_down', i * 0.13);
      add(p.curve, 2, 0.3, -1, U, 0.5, 'olt_up', i * 0.13 + 0.25);
    });
    // curvas locais dos grupos (coordenadas do grupo → mundo)
    OBJ.oltPorts.forEach(p => { p.curve.points.forEach(v => v.add(OBJ.oltG.position)); p.curve.updateArcLengths && p.curve.updateArcLengths(); });
    const oc = OBJ.onuCurve; oc.points.forEach(v => v.add(V(200, 0, 0)));
    add(oc, 3, 0.3, 1, D, 0.5, 'onu_down');
  }

  // ------------------------------------------------------------------ planos de câmera
  // p: posição; q: alvo; cada plano vai de [0] a [1] ao longo da cena.
  SHOTS.cidade = { p: [V(-70, 46, 92), V(-28, 34, 68)], q: [V(0, 0, 0), V(8, 2, 0)], show: ['down', 'up'] };
  SHOTS.fibra = { p: [V(-58, 15, 26), V(4, 13, 24)], q: [V(-44, 7, 3), V(18, 6.5, 3)], show: ['down', 'up', 'down_drop', 'up_drop'] };
  SHOTS.olt = { p: [V(-192.5, 4.6, 14.5), V(-195.8, 3.6, 11.2)], q: [V(-200.2, 1.6, 1.2), V(-200.6, 1.6, 1.3)], show: ['olt_down'] };
  SHOTS.olt_up = { p: [V(-207.5, 3.8, 12.5), V(-205, 3.2, 10)], q: [V(-199.8, 1.6, 1.3), V(-199.6, 1.7, 1.3)], show: ['olt_up'] };
  SHOTS.onu = { p: [V(205.5, 4.2, 8.2), V(202.6, 2.6, 5.6)], q: [V(199.6, 0.4, 0), V(199.8, 0.5, 0.3)], show: ['onu_down'] };
  SHOTS.curva = { p: [V(29.8, 7.4, 14.5), V(28.3, 6.5, 11.6)], q: [V(24.2, 4.4, 3.6), V(24.3, 4.3, 3.6)], show: ['down_drop', 'up_drop'], ring: true };
  SHOTS.comparar = { p: [V(44, 12, 30), V(36, 9, 22)], q: [V(22, 4.8, 3), V(25, 4.6, 4)], show: ['down', 'up', 'down_drop', 'up_drop'], ring: true, dim: true };
  const ORDEM = ['cidade', 'fibra', 'olt', 'olt', 'onu', 'olt_up', 'curva', 'comparar', 'cidade'];

  W3D.init = function (stage, data) {
    W = data.w; H = data.h;
    ACC = new THREE.Color(data.theme.accent); ACC2 = new THREE.Color(data.theme.accent2);
    GLOW = glowTex();
    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
    R.setPixelRatio(data.scale3d || 0.75); R.setSize(W, H);
    R.outputColorSpace = THREE.SRGBColorSpace;
    R.toneMapping = THREE.ACESFilmicToneMapping; R.toneMappingExposure = 1.35;
    const cv = R.domElement; cv.id = 'gl3d'; W3D.cv = cv;
    stage.appendChild(cv);
    S = new THREE.Scene(); S.background = new THREE.Color(0x070b16); S.fog = new THREE.Fog(0x0a1020, 70, 240);
    C = new THREE.PerspectiveCamera(data.h > data.w ? 50 : 38, W / H, 0.1, 400);
    if (data.h > data.w) C.setViewOffset(W, H, 0, -H * 0.13, W, H);  // assunto mais para baixo: cartões ficam em cima
    S.add(new THREE.HemisphereLight(0x8a9cc8, 0x2a2018, 1.7));
    const moon = new THREE.DirectionalLight(0xb8c6ff, 1.1); moon.position.set(-30, 60, 40); S.add(moon);
    const warm = new THREE.DirectionalLight(0xffc48a, 0.9); warm.position.set(40, 25, 50); S.add(warm);
    city(); network(); olt(); onu(); pulses();
    const shade = document.createElement('div'); shade.id = 'shade3d'; stage.appendChild(shade);
    W3D.on = true;
    return cv;
  };

  function shotOf(seg, idx) {
    const p = seg && seg.params ? seg.params._shot : null;
    return SHOTS[p] ? p : ORDEM[idx % ORDEM.length];
  }

  W3D.render = function (t, seg, idx) {
    if (!W3D.on) return;
    const name = shotOf(seg, idx || 0), sh = SHOTS[name];
    const lt = seg ? Math.max(0, t - seg.start) : t, d = seg ? Math.max(0.5, seg.dur) : 5;
    const u = ease(lt / d);
    C.position.lerpVectors(sh.p[0], sh.p[1], u);
    const q = new THREE.Vector3().lerpVectors(sh.q[0], sh.q[1], u);
    C.lookAt(q);
    for (const P of PULSES) {
      const vis = sh.show.includes(P.kind);
      P.spr.visible = vis;
      if (!vis) continue;
      let uu = (P.u0 + t * P.speed) % 1; if (P.dir < 0) uu = 1 - uu;
      P.spr.position.copy(P.curve.getPointAt(uu));
      let op = Math.min(1, uu * 12, (1 - uu) * 12);
      if (sh.dim && P.kind === 'down_drop' && uu > 0.25) op *= 0.25;   // download perde mais depois da curva
      if (sh.dim && P.kind === 'up_drop' && uu < 0.25) op *= 0.75;
      P.spr.material.opacity = op;
    }
    for (const L of LABELS) L.spr.visible = L.shots.includes(name);
    const ringOn = !!sh.ring;
    const pulse = 0.55 + 0.45 * Math.sin(t * 5.5);
    OBJ.ring.material.opacity = ringOn ? 0.35 * pulse : 0;
    OBJ.ringM.material.opacity = ringOn ? 0.9 : 0;
    OBJ.ringM.scale.setScalar(ringOn ? 1 + 0.08 * pulse : 1);
    // troca de plano suave: 0,25 s de entrada e 0,2 s de saída a partir do fundo escuro
    const fin = seg ? Math.min(1, lt / 0.25) : 1, fout = seg ? Math.min(1, Math.max(0, (d - lt) / 0.2)) : 1;
    const f = idx === 0 && lt < 0.25 ? 1 : Math.max(0.12, Math.min(fin, fout));
    if (W3D.cv) W3D.cv.style.opacity = f.toFixed(3);
    R.render(S, C);
  };

  window.W3D = W3D;
})();
