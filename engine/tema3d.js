// 3D temático em código (Three.js): cada cena monta os objetos que o roteiro pediu em params._3d
// ({objetos: ["foguete", "moedas"], camera: "orbita"}). Nada é baixado: tudo é desenhado aqui,
// nas cores da paleta do vídeo. Determinístico: o mesmo t gera sempre o mesmo quadro.
(function () {
  'use strict';
  const W3T = { on: false };
  let R, S, C, W, H, PORT, ACC, ACC2, GLOW, DUST;
  const GRUPOS = [];  // por segmento: { holder, upds: [fn], cam, vals }

  // ------------------------------------------------------------------ utilidades
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const ease = u => 0.5 - 0.5 * Math.cos(Math.PI * Math.min(1, Math.max(0, u)));
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const std = (c, o) => new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.6, metalness: 0.1 }, o || {}));
  const bas = (c, o) => new THREE.MeshBasicMaterial(Object.assign({ color: c }, o || {}));
  const M = {};  // materiais compartilhados (criados no init, já com a paleta)
  function mesh(geo, mat, x, y, z) { const m = new THREE.Mesh(geo, mat); m.position.set(x || 0, y || 0, z || 0); return m; }
  function glowTex() {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d'); const r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.25, 'rgba(255,255,255,.7)'); r.addColorStop(0.6, 'rgba(255,255,255,.15)'); r.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = r; g.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }
  function glow(color, size, op) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color, transparent: true, opacity: op == null ? 1 : op, blending: THREE.AdditiveBlending, depthWrite: false }));
    s.scale.set(size, size, 1); s.userData.nofit = true; return s;
  }
  function canvasTex(w, h, desenha) {
    const c = document.createElement('canvas'); c.width = w; c.height = h; desenha(c.getContext('2d'), w, h);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
  }
  const hex = c => '#' + c.getHexString();

  // ------------------------------------------------------------------ kit de objetos
  // Cada função recebe ctx {rnd, vals} e devolve {g, upd?(t, lt, dur), size?, lift?}.
  const KIT = {};

  KIT.foguete = () => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.CylinderGeometry(0.6, 0.62, 4, 28), M.branco, 0, 2.6, 0));
    g.add(mesh(new THREE.ConeGeometry(0.6, 1.5, 28), M.acc, 0, 5.35, 0));
    g.add(mesh(new THREE.CylinderGeometry(0.63, 0.63, 0.28, 28), M.escuro, 0, 3.9, 0));
    for (let i = 0; i < 4; i++) {
      const f = mesh(new THREE.BoxGeometry(0.08, 1.1, 0.8), M.acc, Math.cos(i * Math.PI / 2) * 0.75, 1.05, Math.sin(i * Math.PI / 2) * 0.75);
      f.rotation.y = -i * Math.PI / 2; g.add(f);
    }
    g.add(mesh(new THREE.CylinderGeometry(0.42, 0.55, 0.5, 20), M.metal, 0, 0.4, 0));
    const f1 = glow(ACC2, 2.2), f2 = glow(ACC, 3.2, 0.8); f1.position.y = -0.2; f2.position.y = -0.7; g.add(f1, f2);
    return { g, lift: 0.08, upd(t, lt) {
      const k = 1 + 0.18 * Math.sin(t * 31) + 0.1 * Math.sin(t * 17.3);
      f1.scale.set(2.2 * k, 2.6 * k, 1); f2.scale.set(3.2 * k, 4 * k, 1);
      g.position.x = 0.02 * Math.sin(t * 43); g.position.y = Math.min(1.2, lt * 0.18);
    } };
  };

  KIT.satelite = () => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.BoxGeometry(1.3, 1.3, 1.7), M.ouro));
    for (const s of [-1, 1]) {
      const haste = mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.9, 8), M.metal, s * 1.1, 0, 0); haste.rotation.z = Math.PI / 2; g.add(haste);
      const p = mesh(new THREE.BoxGeometry(2.8, 0.06, 1.2), M.painel, s * 2.95, 0, 0); g.add(p);
    }
    const prato = mesh(new THREE.SphereGeometry(0.7, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2.4), std(0xdfe3ea, { side: THREE.DoubleSide, metalness: 0.5 }), 0, 1.05, 0);
    prato.rotation.x = Math.PI; g.add(prato);
    const luz = glow(ACC2, 0.7); luz.position.set(0, 1.5, 0); g.add(luz);
    return { g, lift: 0.35, upd(t) { g.rotation.y = t * 0.3; g.rotation.z = 0.15 * Math.sin(t * 0.6); g.position.y = 0.25 * Math.sin(t * 1.1); luz.material.opacity = 0.5 + 0.5 * Math.sin(t * 6); } };
  };

  KIT.planeta = () => {
    const g = new THREE.Group();
    const p = mesh(new THREE.SphereGeometry(1.6, 48, 32), std(0xb5532d, { roughness: 0.9 })); g.add(p);
    const anel = mesh(new THREE.RingGeometry(2.2, 3.0, 64), bas(ACC, { transparent: true, opacity: 0.45, side: THREE.DoubleSide })); anel.rotation.x = -Math.PI / 2.3; g.add(anel);
    const lua = mesh(new THREE.SphereGeometry(0.28, 20, 14), M.cinza); g.add(lua);
    g.add(Object.assign(glow(ACC, 6, 0.25), {}));
    return { g, lift: 0.3, upd(t) { p.rotation.y = t * 0.2; const a = t * 0.8; lua.position.set(Math.cos(a) * 3.6, Math.sin(a) * 0.6, Math.sin(a) * 3.6); } };
  };

  KIT.lua = (ctx) => {
    const g = new THREE.Group();
    const l = mesh(new THREE.SphereGeometry(1.8, 48, 32), std(0xb9bec7, { roughness: 0.95 })); g.add(l);
    for (let i = 0; i < 14; i++) {
      const a = ctx.rnd() * Math.PI * 2, b = (ctx.rnd() - 0.5) * 2.4, r = 0.12 + ctx.rnd() * 0.3;
      const c = mesh(new THREE.SphereGeometry(r, 12, 8), std(0x8d929b, { roughness: 1 }));
      c.position.setFromSphericalCoords(1.74, Math.PI / 2 + b * 0.5, a); l.add(c);
    }
    return { g, lift: 0.3, upd(t) { l.rotation.y = t * 0.12; } };
  };

  KIT.globo = (ctx) => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.SphereGeometry(1.8, 48, 32), std(0x0d2442, { emissive: 0x061630, roughness: 0.7 })));
    g.add(mesh(new THREE.IcosahedronGeometry(1.83, 3), bas(ACC2, { wireframe: true, transparent: true, opacity: 0.22 })));
    const pts = []; for (let i = 0; i < 8; i++) pts.push(V(0, 0, 0).setFromSphericalCoords(1.85, 0.5 + ctx.rnd() * 2.1, ctx.rnd() * Math.PI * 2));
    const pulsos = [];
    for (let i = 0; i < 7; i++) {
      const a = pts[i], b = pts[(i + 3) % 8], meio = a.clone().add(b).normalize().multiplyScalar(2.9);
      const curva = new THREE.QuadraticBezierCurve3(a, meio, b);
      g.add(mesh(new THREE.TubeGeometry(curva, 40, 0.025, 6, false), bas(ACC, { transparent: true, opacity: 0.6 })));
      const p = glow(ACC2, 0.45); g.add(p); pulsos.push({ p, curva, f: ctx.rnd() });
    }
    pts.forEach(p => { const s = glow(ACC, 0.5); s.position.copy(p); g.add(s); });
    return { g, lift: 0.3, upd(t) { g.rotation.y = t * 0.18; pulsos.forEach(o => o.p.position.copy(o.curva.getPoint((t * 0.45 + o.f) % 1))); } };
  };

  KIT.chip = (ctx) => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.BoxGeometry(4, 0.3, 4), M.escuro));
    g.add(mesh(new THREE.BoxGeometry(2.5, 0.14, 2.5), M.metal, 0, 0.22, 0));
    const nucleo = mesh(new THREE.BoxGeometry(1.5, 0.06, 1.5), std(ACC, { emissive: ACC, emissiveIntensity: 0.7 }), 0, 0.31, 0); g.add(nucleo);
    const pino = new THREE.BoxGeometry(0.12, 0.08, 0.45), pinos = new THREE.InstancedMesh(pino, M.ouro, 48), q = new THREE.Object3D();
    for (let i = 0; i < 48; i++) {
      const lado = Math.floor(i / 12), k = (i % 12) / 11 * 3.3 - 1.65;
      q.position.set([k, 2.15, k, -2.15][lado], -0.05, [2.15, k, -2.15, k][lado]); q.rotation.y = lado % 2 ? Math.PI / 2 : 0; q.updateMatrix(); pinos.setMatrixAt(i, q.matrix);
    }
    g.add(pinos);
    const trilhas = [];
    for (let i = 0; i < 10; i++) {
      const tr = mesh(new THREE.BoxGeometry(0.05, 0.02, 0.6 + ctx.rnd()), bas(ACC2), (ctx.rnd() - 0.5) * 3.4, 0.16, (ctx.rnd() > 0.5 ? 1 : -1) * (1.5 + ctx.rnd() * 0.3));
      if (i % 2) { tr.rotation.y = Math.PI / 2; tr.position.set(tr.position.z, 0.16, tr.position.x); }
      g.add(tr); trilhas.push(tr);
    }
    return { g, lift: 0.15, upd(t) { g.rotation.y = t * 0.15; nucleo.material.emissiveIntensity = 0.45 + 0.4 * Math.sin(t * 3); trilhas.forEach((tr, i) => { tr.visible = Math.sin(t * 4 + i * 1.7) > -0.3; }); } };
  };

  KIT.gpu = () => {
    const g = new THREE.Group(), card = new THREE.Group(); g.add(card);
    card.add(mesh(new THREE.BoxGeometry(5.2, 0.9, 1.9), M.escuro));
    card.add(mesh(new THREE.BoxGeometry(5.2, 0.06, 0.12), std(ACC, { emissive: ACC, emissiveIntensity: 0.9 }), 0, 0.2, 0.96));
    card.add(mesh(new THREE.BoxGeometry(0.15, 1.1, 2.0), M.metal, -2.65, 0, 0));
    const helices = [];
    for (const x of [-1.25, 1.25]) {
      const aro = mesh(new THREE.TorusGeometry(0.78, 0.06, 8, 32), M.metal, x, 0.47, 0); aro.rotation.x = Math.PI / 2; card.add(aro);
      const h = new THREE.Group(); h.position.set(x, 0.48, 0);
      for (let i = 0; i < 7; i++) { const b = mesh(new THREE.BoxGeometry(0.7, 0.02, 0.18), M.cinza, 0.35, 0, 0); const p = new THREE.Group(); p.rotation.y = i * Math.PI * 2 / 7; b.rotation.x = 0.4; p.add(b); h.add(p); }
      card.add(h); helices.push(h);
    }
    card.rotation.x = -0.35;
    return { g, lift: 0.25, upd(t) { helices.forEach(h => { h.rotation.y = t * 14; }); g.rotation.y = 0.35 * Math.sin(t * 0.4); } };
  };

  KIT.servidor = (ctx) => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.BoxGeometry(1.9, 4.4, 1.7), M.escuro, 0, 2.2, 0));
    const leds = [];
    for (let u = 0; u < 9; u++) {
      g.add(mesh(new THREE.BoxGeometry(1.7, 0.36, 0.04), M.cinzaEscuro, 0, 0.45 + u * 0.44, 0.86));
      for (let k = 0; k < 3; k++) { const l = mesh(new THREE.BoxGeometry(0.08, 0.08, 0.04), bas(k === 2 ? ACC : ACC2), -0.6 + k * 0.16, 0.45 + u * 0.44, 0.89); g.add(l); leds.push({ l, f: ctx.rnd() * 9, v: 3 + ctx.rnd() * 7 }); }
    }
    return { g, upd(t) { leds.forEach(o => { o.l.visible = Math.sin(t * o.v + o.f) > -0.2; }); g.rotation.y = -0.4 + 0.25 * Math.sin(t * 0.35); } };
  };

  KIT.datacenter = (ctx) => {
    const g = new THREE.Group(), q = new THREE.Object3D(), n = 14;
    const racks = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 2.6, 1.1), M.escuro, n);
    const fitas = new THREE.InstancedMesh(new THREE.BoxGeometry(0.06, 2.2, 0.02), bas(ACC2), n);
    for (let i = 0; i < n; i++) {
      const fila = i < n / 2 ? -1 : 1, x = (i % (n / 2)) * 1.15 - 3.5;
      q.position.set(x, 1.3, fila * 1.6); q.updateMatrix(); racks.setMatrixAt(i, q.matrix);
      q.position.set(x, 1.3, fila * 1.6 - fila * 0.56); q.updateMatrix(); fitas.setMatrixAt(i, q.matrix);
    }
    g.add(racks, fitas);
    g.add(mesh(new THREE.BoxGeometry(8.4, 0.02, 0.18), bas(ACC), 0, 0.02, 0));
    return { g, size: 7, lift: 0, upd(t) { fitas.material.color.copy(ACC2).multiplyScalar(0.6 + 0.4 * Math.sin(t * 4)); } };
  };

  KIT.robo = () => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.BoxGeometry(1.9, 2.1, 1.1), M.branco, 0, 3.0, 0));
    g.add(mesh(new THREE.CircleGeometry(0.28, 24), bas(ACC), 0, 3.3, 0.56));
    const cab = new THREE.Group(); cab.position.set(0, 4.55, 0); g.add(cab);
    cab.add(mesh(new THREE.BoxGeometry(1.25, 1.0, 1.05), M.branco));
    cab.add(mesh(new THREE.BoxGeometry(1.0, 0.32, 0.05), bas(ACC2), 0, 0.05, 0.53));
    g.add(mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.4, 12), M.metal, 0, 4.1, 0));
    const braco = (x) => { const p = new THREE.Group(); p.position.set(x, 3.85, 0); p.add(mesh(new THREE.CapsuleGeometry(0.24, 1.5, 6, 12), M.cinza, 0, -0.95, 0)); g.add(p); return p; };
    const be = braco(-1.25), bd = braco(1.25);
    for (const x of [-0.5, 0.5]) g.add(mesh(new THREE.CapsuleGeometry(0.28, 1.4, 6, 12), M.cinza, x, 1.0, 0));
    return { g, upd(t) { bd.rotation.z = 0.5 + 0.55 * (0.5 + 0.5 * Math.sin(t * 2.4)); be.rotation.z = -0.12; cab.rotation.y = 0.35 * Math.sin(t * 0.8); g.rotation.y = 0.3 * Math.sin(t * 0.3); } };
  };

  KIT.rede_neural = (ctx) => {
    const g = new THREE.Group(), camadas = [4, 6, 6, 3], nos = [];
    camadas.forEach((n, c) => { nos.push([]); for (let i = 0; i < n; i++) { const p = V(c * 2.1 - 3.15, (i - (n - 1) / 2) * 0.95 + 2.6, (ctx.rnd() - 0.5) * 0.8); nos[c].push(p); g.add(mesh(new THREE.SphereGeometry(0.2, 16, 12), std(0xeef2f8, { emissive: ACC, emissiveIntensity: 0.25 }), p.x, p.y, p.z)); } });
    const pos = [], arestas = [];
    for (let c = 0; c < camadas.length - 1; c++) for (const a of nos[c]) for (const b of nos[c + 1]) { pos.push(a.x, a.y, a.z, b.x, b.y, b.z); arestas.push([a, b]); }
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: ACC, transparent: true, opacity: 0.22 })));
    const pulsos = []; for (let i = 0; i < 16; i++) { const p = glow(ACC2, 0.4); g.add(p); pulsos.push({ p, e: arestas[Math.floor(ctx.rnd() * arestas.length)], f: ctx.rnd() }); }
    return { g, upd(t) { g.rotation.y = 0.35 * Math.sin(t * 0.3); pulsos.forEach(o => { const u = (t * 0.6 + o.f) % 1; o.p.position.lerpVectors(o.e[0], o.e[1], u); }); } };
  };

  KIT.nuvem = (ctx) => {
    const g = new THREE.Group(), mat = std(0xdfe6f2, { emissive: 0x223044, roughness: 0.9 });
    [[0, 0, 0, 1.2], [1.1, -0.2, 0.1, 0.9], [-1.1, -0.25, 0, 0.85], [0.4, 0.55, -0.2, 0.85], [-0.5, 0.4, 0.2, 0.7]].forEach(([x, y, z, r]) => g.add(mesh(new THREE.SphereGeometry(r, 24, 16), mat, x, y + 3.6, z)));
    const pacotes = [];
    for (let i = 0; i < 4; i++) { const x = -1.2 + i * 0.8; g.add(mesh(new THREE.CylinderGeometry(0.03, 0.03, 2.6, 6), bas(ACC2, { transparent: true, opacity: 0.4 }), x, 1.6, 0)); const p = glow(ACC, 0.45); g.add(p); pacotes.push({ p, x, f: ctx.rnd() }); }
    return { g, upd(t) { g.rotation.y = 0.2 * Math.sin(t * 0.4); pacotes.forEach(o => o.p.position.set(o.x, 2.8 - ((t * 0.7 + o.f) % 1) * 2.6, 0)); } };
  };

  function telaTex(tipo) {
    return canvasTex(256, 480, (c, w, h) => {
      const gr = c.createLinearGradient(0, 0, w, h); gr.addColorStop(0, '#0d1220'); gr.addColorStop(1, hex(ACC).replace('#', '#') + '55');
      c.fillStyle = gr; c.fillRect(0, 0, w, h);
      if (tipo === 'codigo') { const cores = [hex(ACC), hex(ACC2), '#9aa3b2', '#e4e4e7']; for (let i = 0; i < 26; i++) { c.fillStyle = cores[i % 4]; c.fillRect(18 + (i % 5) * 14, 20 + i * 17, 40 + ((i * 37) % 150), 7); } return; }
      c.fillStyle = hex(ACC); c.fillRect(20, 40, w - 40, 90); c.fillStyle = '#e4e4e7';
      for (let i = 0; i < 5; i++) c.fillRect(20, 160 + i * 52, (w - 40) * (0.4 + ((i * 0.37) % 0.6)), 26);
      c.fillStyle = hex(ACC2); c.fillRect(20, h - 80, w - 40, 44);
    });
  }

  KIT.celular = () => {
    const g = new THREE.Group(), cel = new THREE.Group(); g.add(cel);
    cel.add(mesh(new THREE.BoxGeometry(2.1, 4.2, 0.24), M.escuro));
    cel.add(mesh(new THREE.PlaneGeometry(1.9, 3.95), bas(0xffffff, { map: telaTex('app') }), 0, 0, 0.125));
    cel.position.y = 2.3;
    return { g, upd(t) { cel.rotation.y = -0.5 + 0.35 * Math.sin(t * 0.5); cel.position.y = 2.3 + 0.12 * Math.sin(t * 1.3); } };
  };

  KIT.notebook = () => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.BoxGeometry(4.2, 0.16, 2.9), M.metal, 0, 0.08, 0));
    const teclado = mesh(new THREE.PlaneGeometry(3.6, 1.8), M.cinzaEscuro, 0, 0.17, 0.2); teclado.rotation.x = -Math.PI / 2; g.add(teclado);
    const tampa = new THREE.Group(); tampa.position.set(0, 0.16, -1.42); tampa.rotation.x = -0.22; g.add(tampa);
    tampa.add(mesh(new THREE.BoxGeometry(4.2, 2.8, 0.1), M.metal, 0, 1.4, 0));
    const tela = mesh(new THREE.PlaneGeometry(3.9, 2.5), bas(0xffffff, { map: telaTex('codigo') }), 0, 1.42, 0.06); tampa.add(tela);
    return { g, upd(t) { g.rotation.y = -0.45 + 0.3 * Math.sin(t * 0.4); } };
  };

  KIT.moedas = (ctx) => {
    const g = new THREE.Group(), geo = new THREE.CylinderGeometry(0.7, 0.7, 0.14, 32), q = new THREE.Object3D();
    const alturas = [5, 9, 7], total = alturas.reduce((a, b) => a + b, 0), pilhas = new THREE.InstancedMesh(geo, M.ouro, total);
    let k = 0; alturas.forEach((n, p) => { for (let i = 0; i < n; i++) { q.position.set((p - 1) * 1.7 + (ctx.rnd() - 0.5) * 0.06, 0.07 + i * 0.15, (ctx.rnd() - 0.5) * 0.06); q.updateMatrix(); pilhas.setMatrixAt(k++, q.matrix); } });
    g.add(pilhas);
    const caindo = []; for (let i = 0; i < 3; i++) { const m = mesh(geo, M.ouro); m.scale.setScalar(0.75); g.add(m); caindo.push({ m, x: (i - 1) * 1.7, topo: 0.2 + alturas[i] * 0.15, f: i / 3, r: ctx.rnd() * 6 }); }
    return { g, upd(t) { caindo.forEach(o => { const u = (t * 0.5 + o.f) % 1; o.m.position.set(o.x, o.topo + 1.5 * (1 - u), 0); o.m.rotation.set(t * 3 + o.r, 0, t * 2 + o.r); o.m.visible = u < 0.97; }); g.rotation.y = 0.3 * Math.sin(t * 0.35); } };
  };

  function grafico(ctx, alta) {
    const g = new THREE.Group();
    let vals = (ctx.vals && ctx.vals.length >= 2) ? ctx.vals.slice(0, 6) : (alta ? [3, 4, 5.5, 7, 9.5] : [9.5, 7.5, 6, 4, 2.5]);
    const mx = Math.max(...vals.map(v => Math.abs(v))) || 1, n = vals.length, barras = [];
    vals.forEach((v, i) => {
      const h = Math.max(0.2, Math.abs(v) / mx * 4.2), dest = alta ? i === n - 1 : i === 0;
      const b = mesh(new THREE.BoxGeometry(0.85, h, 0.85), dest ? std(ACC, { emissive: ACC, emissiveIntensity: 0.35, metalness: 0.3 }) : M.cinzaBarra, (i - (n - 1) / 2) * 1.2, h / 2, 0);
      b.geometry.translate(0, h / 2, 0); b.position.y = 0;  // base no chão: cresce para cima
      g.add(b); barras.push(b);
    });
    const pts = vals.map((v, i) => V((i - (n - 1) / 2) * 1.2, Math.abs(v) / mx * 4.2 + 0.7, 0.6));
    const curva = new THREE.CatmullRomCurve3(pts);
    const cor = alta ? ACC2 : new THREE.Color(0xff3b5c);
    const seta = mesh(new THREE.TubeGeometry(curva, 60, 0.07, 8, false), bas(cor)); g.add(seta);
    const ponta = mesh(new THREE.ConeGeometry(0.26, 0.6, 16), bas(cor)); g.add(ponta);
    const fim = pts[n - 1], dir = fim.clone().sub(pts[n - 2]).normalize();
    ponta.position.copy(fim); ponta.quaternion.setFromUnitVectors(V(0, 1, 0), dir);
    return { g, upd(t, lt) {
      barras.forEach((b, i) => { b.scale.y = 0.02 + 0.98 * ease((lt - i * 0.12) / 0.9); });
      const u = ease((lt - 0.5) / 1.2); seta.visible = ponta.visible = u > 0.02; seta.geometry.setDrawRange(0, Math.floor(u * seta.geometry.index.count / 3) * 3);
      g.rotation.y = -0.25 + 0.12 * Math.sin(t * 0.4);
    } };
  }
  KIT.grafico_alta = ctx => grafico(ctx, true);
  KIT.grafico_queda = ctx => grafico(ctx, false);

  KIT.cidade = (ctx) => {
    const g = new THREE.Group(), q = new THREE.Object3D(), n = 46;
    const jan = canvasTex(64, 128, (c, w, h) => { c.fillStyle = '#10141c'; c.fillRect(0, 0, w, h); for (let y = 6; y < h; y += 12) for (let x = 6; x < w; x += 14) { if (((x * 7 + y * 13) % 5) < 3) { c.fillStyle = ((x + y) % 3) ? '#ffd48e' : '#dfe9ff'; c.fillRect(x, y, 7, 6); } } });
    const predios = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), std(0xffffff, { map: jan, emissiveMap: jan, emissive: 0xffffff, emissiveIntensity: 0.55, roughness: 0.8 }), n);
    for (let i = 0; i < n; i++) {
      const x = (i % 8) * 1.25 - 4.4 + (ctx.rnd() - 0.5) * 0.3, z = Math.floor(i / 8) * 1.3 - 3.2, h = 1 + ctx.rnd() * (z > -1 && Math.abs(x) < 2 ? 6 : 3.5);
      q.position.set(x, h / 2, z); q.scale.set(0.9 + ctx.rnd() * 0.3, h, 0.9 + ctx.rnd() * 0.3); q.updateMatrix(); predios.setMatrixAt(i, q.matrix);
    }
    g.add(predios);
    const topo = glow(ACC, 1.2); topo.position.set(0, 7.2, 0); g.add(topo);
    return { g, size: 7, upd(t) { topo.material.opacity = 0.5 + 0.5 * Math.sin(t * 3); } };
  };

  function fumaca(g, n, x, y, z, cor, alt, rnd) {
    const ps = []; for (let i = 0; i < n; i++) { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: cor, transparent: true, opacity: 0.5, depthWrite: false })); s.userData.nofit = true; g.add(s); ps.push({ s, f: i / n + rnd() * 0.05 }); }
    return t => ps.forEach(o => { const u = (t * 0.35 + o.f) % 1; o.s.position.set(x + u * 0.8, y + u * alt, z); const k = 0.6 + u * 2.4; o.s.scale.set(k, k, 1); o.s.material.opacity = 0.55 * (1 - u); });
  }

  KIT.fabrica = (ctx) => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.BoxGeometry(4.4, 1.8, 2.6), std(0x3a3f4a), 0, 0.9, 0));
    for (let i = 0; i < 3; i++) { const t = mesh(new THREE.CylinderGeometry(0.75, 0.75, 2.6, 3, 1, false), std(0x4b515e), -1.45 + i * 1.45, 2.05, 0); t.rotation.set(Math.PI / 2, 0, Math.PI / 2); t.scale.set(1, 1, 0.55); g.add(t); }
    const chams = [[-1.3, 0.6], [0.9, -0.5]];
    chams.forEach(([x, z]) => { g.add(mesh(new THREE.CylinderGeometry(0.28, 0.36, 4.4, 16), std(0x5c6370), x, 2.2, z)); g.add(mesh(new THREE.CylinderGeometry(0.37, 0.37, 0.25, 16), M.acc, x, 3.9, z)); });
    const f1 = fumaca(g, 9, -1.3, 4.5, 0.6, 0x9aa1ab, 3.5, ctx.rnd), f2 = fumaca(g, 9, 0.9, 4.5, -0.5, 0x9aa1ab, 3.5, ctx.rnd);
    return { g, upd(t) { f1(t); f2(t + 0.4); } };
  };

  KIT.usina = (ctx) => {
    const g = new THREE.Group(), p = [];
    for (let i = 0; i <= 12; i++) { const y = i / 12 * 5, r = 1.1 + 0.9 * Math.pow((y - 3.3) / 3.3, 2); p.push(new THREE.Vector2(r, y)); }
    g.add(mesh(new THREE.LatheGeometry(p, 40), std(0xc4c9d1, { side: THREE.DoubleSide, roughness: 0.9 }), -0.8, 0, 0));
    g.add(mesh(new THREE.SphereGeometry(1.2, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), std(0xdfe3ea), 2.2, 0.9, 0.6));
    g.add(mesh(new THREE.CylinderGeometry(1.2, 1.2, 0.9, 32), std(0xdfe3ea), 2.2, 0.45, 0.6));
    const vapor = fumaca(g, 12, -0.8, 5.2, 0, 0xe8edf3, 4, ctx.rnd);
    const luz = glow(ACC, 1.2); luz.position.set(2.2, 2.3, 0.6); g.add(luz);
    return { g, upd(t) { vapor(t); luz.material.opacity = 0.4 + 0.4 * Math.sin(t * 2); } };
  };

  KIT.painel_solar = () => {
    const g = new THREE.Group(), paineis = [];
    for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) {
      const x = (c - 1.5) * 1.7, z = (r - 1) * 1.6;
      g.add(mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.9, 8), M.metal, x, 0.45, z));
      const p = mesh(new THREE.BoxGeometry(1.5, 0.05, 1.0), std(0x16306b, { metalness: 0.6, roughness: 0.25, emissive: 0x0a1a40 }), x, 0.95, z); p.rotation.x = -0.5; g.add(p); paineis.push(p);
    }
    const sol = glow(ACC2, 3.5, 0.8); sol.position.set(3, 5, -3); g.add(sol);
    return { g, size: 6, upd(t) { paineis.forEach((p, i) => { p.material.emissiveIntensity = 0.8 + 0.6 * Math.sin(t * 2 + i * 0.5); }); } };
  };

  KIT.turbina_eolica = () => {
    const g = new THREE.Group(), rotores = [];
    [[0, 0, 1], [-3, -2.5, 0.75], [3.2, -3, 0.7]].forEach(([x, z, s]) => {
      const tg = new THREE.Group(); tg.position.set(x, 0, z); tg.scale.setScalar(s); g.add(tg);
      tg.add(mesh(new THREE.CylinderGeometry(0.1, 0.22, 6, 12), M.branco, 0, 3, 0));
      tg.add(mesh(new THREE.BoxGeometry(0.35, 0.35, 0.9), M.branco, 0, 6.1, 0));
      const rot = new THREE.Group(); rot.position.set(0, 6.1, 0.5); tg.add(rot); rotores.push(rot);
      rot.add(mesh(new THREE.SphereGeometry(0.2, 12, 8), M.acc));
      for (let i = 0; i < 3; i++) { const p = new THREE.Group(); p.rotation.z = i * Math.PI * 2 / 3; p.add(mesh(new THREE.BoxGeometry(0.2, 2.8, 0.05), M.branco, 0, 1.5, 0)); rot.add(p); }
    });
    return { g, size: 6, upd(t) { rotores.forEach((r, i) => { r.rotation.z = t * (1.4 + i * 0.2); }); } };
  };

  KIT.bateria = () => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.CylinderGeometry(1.15, 1.15, 3.4, 40, 1, true), std(0x2a3140, { transparent: true, opacity: 0.55, side: THREE.DoubleSide, metalness: 0.5 }), 0, 1.7, 0));
    g.add(mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.3, 24), M.metal, 0, 3.55, 0));
    g.add(mesh(new THREE.CylinderGeometry(1.17, 1.17, 0.1, 40), M.metal, 0, 3.4, 0));
    const nivel = mesh(new THREE.CylinderGeometry(1.0, 1.0, 3.2, 40), std(ACC2, { emissive: ACC2, emissiveIntensity: 0.6 }), 0, 0.1, 0);
    nivel.geometry.translate(0, 1.6, 0); g.add(nivel);
    return { g, upd(t, lt, d) { nivel.scale.y = 0.15 + 0.82 * ease(lt / Math.max(1.5, d * 0.8)); g.rotation.y = t * 0.2; } };
  };

  KIT.raio = (ctx) => {
    const g = new THREE.Group(), pts = [];
    for (let i = 0; i <= 8; i++) pts.push(V((i % 2 ? 0.6 : -0.6) + (ctx.rnd() - 0.5) * 0.3, 6 - i * 0.75, 0));
    const tubo = mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.05), 80, 0.12, 8, false), bas(ACC2)); g.add(tubo);
    const halos = pts.map(p => { const s = glow(ACC2, 1.6, 0.6); s.position.copy(p); g.add(s); return s; });
    const chao = glow(ACC, 4, 0.7); chao.position.set(0, 0.1, 0); g.add(chao);
    return { g, upd(t) { const k = Math.sin(t * 23) > 0.2 ? 1 : 0.35; tubo.material.opacity = k; tubo.material.transparent = true; halos.forEach(h => { h.material.opacity = 0.6 * k; }); } };
  };

  KIT.carro = () => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.BoxGeometry(4.2, 0.8, 1.9), std(ACC, { metalness: 0.6, roughness: 0.3 }), 0, 0.85, 0));
    g.add(mesh(new THREE.BoxGeometry(2.3, 0.75, 1.7), std(0x111722, { metalness: 0.8, roughness: 0.1 }), -0.2, 1.6, 0));
    const rodas = [];
    for (const x of [-1.35, 1.35]) for (const z of [-0.95, 0.95]) { const r = mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.3, 24), M.escuro, x, 0.45, z); r.rotation.x = Math.PI / 2; g.add(r); rodas.push(r); }
    for (const z of [-0.6, 0.6]) { const f = glow(ACC2, 0.9); f.position.set(2.15, 0.95, z); g.add(f); }
    return { g, upd(t) { rodas.forEach(r => { r.rotation.y = t * 8; }); g.position.y = 0.03 * Math.sin(t * 9); g.rotation.y = 0.5 + 0.2 * Math.sin(t * 0.4); } };
  };

  KIT.drone = () => {
    const g = new THREE.Group(), d = new THREE.Group(); g.add(d);
    d.add(mesh(new THREE.BoxGeometry(1.3, 0.4, 1.3), M.escuro));
    const helices = [];
    for (let i = 0; i < 4; i++) {
      const a = Math.PI / 4 + i * Math.PI / 2, x = Math.cos(a) * 1.5, z = Math.sin(a) * 1.5;
      const braco = mesh(new THREE.BoxGeometry(2.0, 0.12, 0.16), M.cinza, x / 2, 0, z / 2); braco.rotation.y = -a; d.add(braco);
      d.add(mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.3, 12), M.metal, x, 0.15, z));
      const h = mesh(new THREE.CylinderGeometry(0.75, 0.75, 0.02, 24), bas(0xcfd6e0, { transparent: true, opacity: 0.35 }), x, 0.32, z); d.add(h); helices.push(h);
      const l = glow(i < 2 ? ACC : ACC2, 0.5); l.position.set(x, -0.05, z); d.add(l);
    }
    return { g, lift: 0.3, upd(t) { d.position.y = 0.3 * Math.sin(t * 1.5); d.rotation.y = t * 0.3; d.rotation.z = 0.06 * Math.sin(t * 1.1); helices.forEach(h => { h.rotation.y = t * 30; }); } };
  };

  KIT.cadeado = () => {
    const g = new THREE.Group(), c = new THREE.Group(); g.add(c);
    c.add(mesh(new THREE.BoxGeometry(2.4, 2.0, 0.9), std(ACC, { metalness: 0.7, roughness: 0.3 }), 0, 1.0, 0));
    const arco = mesh(new THREE.TorusGeometry(0.8, 0.17, 16, 32, Math.PI), M.metal, 0, 2.0, 0); c.add(arco);
    c.add(mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.4, 16), M.metal, -0.8, 2.0, 0), mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.4, 16), M.metal, 0.8, 2.0, 0));
    const buraco = mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.1, 16), M.escuro, 0, 1.15, 0.46); buraco.rotation.x = Math.PI / 2; c.add(buraco);
    c.add(mesh(new THREE.BoxGeometry(0.14, 0.45, 0.1), M.escuro, 0, 0.82, 0.46));
    const anel = mesh(new THREE.TorusGeometry(2.3, 0.04, 8, 64), bas(ACC2, { transparent: true, opacity: 0.5 }), 0, 1.4, -0.6); g.add(anel);
    return { g, upd(t) { c.rotation.y = 0.5 * Math.sin(t * 0.6); anel.rotation.z = t * 0.5; anel.scale.setScalar(1 + 0.05 * Math.sin(t * 2)); } };
  };

  KIT.documento = () => {
    const g = new THREE.Group();
    const tex = canvasTex(256, 330, (c, w, h) => { c.fillStyle = '#eef1f5'; c.fillRect(0, 0, w, h); c.fillStyle = '#1b2230'; c.fillRect(24, 26, 150, 16); c.fillStyle = '#9aa3b2'; for (let i = 0; i < 12; i++) c.fillRect(24, 64 + i * 19, 150 + ((i * 47) % 60), 7); c.fillStyle = hex(ACC); c.fillRect(24, 64 + 5 * 19 - 4, 190, 14); });
    const folha = new THREE.BoxGeometry(2.6, 0.03, 3.4), papel = std(0xe6e9ee, { roughness: 0.9 });
    for (let i = 0; i < 5; i++) { const f = mesh(folha, papel, (i % 2) * 0.08, 0.03 + i * 0.05, -(i % 3) * 0.05); f.rotation.y = (i - 2) * 0.04; g.add(f); }
    const topo = new THREE.Group(); g.add(topo);
    topo.add(mesh(folha, papel)); const face = mesh(new THREE.PlaneGeometry(2.55, 3.35), bas(0xffffff, { map: tex }), 0, 0.02, 0); face.rotation.x = -Math.PI / 2; topo.add(face);
    return { g, upd(t, lt) { const u = ease(lt / 1.4); topo.position.set(0, 0.3 + u * 1.6, 0.4 * u); topo.rotation.x = -0.9 * u; g.rotation.y = -0.3 + 0.15 * Math.sin(t * 0.4); } };
  };

  KIT.lupa = () => {
    const g = new THREE.Group(), l = new THREE.Group(); g.add(l);
    l.add(mesh(new THREE.TorusGeometry(1.1, 0.16, 16, 48), M.metal));
    l.add(mesh(new THREE.CircleGeometry(1.05, 40), bas(0xbfe4ff, { transparent: true, opacity: 0.18, side: THREE.DoubleSide })));
    const cabo = mesh(new THREE.CylinderGeometry(0.17, 0.2, 2.0, 16), M.escuro, 1.45, -1.45, 0); cabo.rotation.z = Math.PI / 4; l.add(cabo);
    const brilho = glow(ACC2, 1.2, 0.5); brilho.position.set(-0.35, 0.35, 0.05); l.add(brilho);
    l.position.y = 2.6;
    return { g, upd(t) { l.position.x = 0.8 * Math.sin(t * 0.7); l.rotation.z = 0.2 * Math.sin(t * 0.7); l.rotation.y = 0.3 * Math.sin(t * 0.5); } };
  };

  KIT.relogio = () => {
    const g = new THREE.Group(), r = new THREE.Group(); r.position.y = 2.4; g.add(r);
    const face = mesh(new THREE.CylinderGeometry(1.9, 1.9, 0.25, 64), M.escuro); face.rotation.x = Math.PI / 2; r.add(face);
    const aro = mesh(new THREE.TorusGeometry(1.95, 0.12, 12, 64), M.metal); r.add(aro);
    for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2, m = mesh(new THREE.BoxGeometry(0.08, i % 3 ? 0.22 : 0.4, 0.04), i % 3 ? M.cinza : M.acc, Math.sin(a) * 1.6, Math.cos(a) * 1.6, 0.15); m.rotation.z = -a; r.add(m); }
    const ponteiro = (c, cor, larg) => { const p = new THREE.Group(); p.position.z = 0.18; p.add(mesh(new THREE.BoxGeometry(larg, c, 0.04), cor, 0, c / 2 - 0.15, 0)); r.add(p); return p; };
    const hora = ponteiro(1.0, M.branco, 0.12), min = ponteiro(1.45, M.acc, 0.08);
    const eixo = mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.1, 16), M.metal, 0, 0, 0.22); eixo.rotation.x = Math.PI / 2; r.add(eixo);
    return { g, upd(t) { min.rotation.z = -t * 2.2; hora.rotation.z = -t * 0.18; r.rotation.y = 0.35 * Math.sin(t * 0.4); } };
  };

  KIT.explosao = (ctx) => {
    const g = new THREE.Group();
    const nucleo = glow(ACC2, 2), onda = glow(ACC, 4, 0.8); nucleo.position.y = onda.position.y = 2.2; g.add(onda, nucleo);
    const lascas = []; for (let i = 0; i < 26; i++) { const m = mesh(new THREE.BoxGeometry(0.18, 0.18, 0.18), i % 3 ? M.cinza : M.acc); g.add(m); lascas.push({ m, d: V(ctx.rnd() - 0.5, ctx.rnd() * 0.8 - 0.2, ctx.rnd() - 0.5).normalize(), f: ctx.rnd() * 0.15 }); }
    const fum = fumaca(g, 10, 0, 2.6, 0, 0x4b4f57, 3, ctx.rnd);
    const base = mesh(new THREE.BoxGeometry(0.1, 4.4, 0.1), bas(0x000000, { transparent: true, opacity: 0 }), 0, 2.2, 0); g.add(base);  // só para o enquadramento
    return { g, upd(t) {
      const u = (t * 0.6) % 1, k = 1.6 + 4 * u;
      nucleo.scale.set(k, k, 1); nucleo.material.opacity = 1 - u; onda.scale.set(k * 1.6, k * 1.6, 1); onda.material.opacity = 0.8 * (1 - u);
      lascas.forEach(o => { const uu = Math.min(1, ((t * 0.6 + o.f) % 1) * 1.3); o.m.position.copy(o.d).multiplyScalar(uu * 3.2).add(V(0, 2.2 - uu * uu * 1.2, 0)); o.m.rotation.set(t * 4, t * 3, 0); });
      fum(t);
    } };
  };

  KIT.gota = () => {
    const g = new THREE.Group(), p = [];
    for (let i = 0; i <= 24; i++) { const a = i / 24 * Math.PI; const r = Math.sin(a) * (1 - Math.cos(a) * 0.55) * 1.1; p.push(new THREE.Vector2(Math.max(0.001, r), 1.1 - Math.cos(a) * 1.5)); }
    const gota = mesh(new THREE.LatheGeometry(p, 40), std(0x4dc3ff, { transparent: true, opacity: 0.8, roughness: 0.05, metalness: 0.1, emissive: 0x0b3a66 })); gota.rotation.x = Math.PI; g.add(gota);
    const ondas = []; for (let i = 0; i < 3; i++) { const o = mesh(new THREE.RingGeometry(0.9, 1.0, 48), bas(ACC2, { transparent: true, opacity: 0.5, side: THREE.DoubleSide })); o.rotation.x = -Math.PI / 2; o.position.y = 0.02; g.add(o); ondas.push(o); }
    return { g, upd(t) { gota.position.y = 3.1 + 0.2 * Math.sin(t * 1.4); ondas.forEach((o, i) => { const u = (t * 0.5 + i / 3) % 1; o.scale.setScalar(0.5 + u * 2.6); o.material.opacity = 0.5 * (1 - u); }); } };
  };

  KIT.pessoas = () => {
    const g = new THREE.Group(), gente = [];
    for (let i = 0; i < 7; i++) {
      const a = (i - 3) * 0.32, p = new THREE.Group(); p.position.set(Math.sin(a) * 3.4, 0, -Math.cos(a) * 3.4 + 3.4 - Math.abs(i - 3) * 0.1);
      const mat = i === 3 ? std(ACC, { emissive: ACC, emissiveIntensity: 0.25 }) : M.cinza;
      p.add(mesh(new THREE.CapsuleGeometry(0.42, 1.1, 6, 16), mat, 0, 1.0, 0)); p.add(mesh(new THREE.SphereGeometry(0.34, 20, 14), mat, 0, 2.15, 0));
      g.add(p); gente.push(p);
    }
    return { g, upd(t) { gente.forEach((p, i) => { p.position.y = Math.max(0, 0.12 * Math.sin(t * 2.2 + i)); }); } };
  };

  KIT.predio_governo = () => {
    const g = new THREE.Group(), mat = std(0xe6e2d8, { roughness: 0.8 });
    g.add(mesh(new THREE.BoxGeometry(5.6, 0.3, 3), mat, 0, 0.15, 0), mesh(new THREE.BoxGeometry(5.2, 0.3, 2.7), mat, 0, 0.45, 0));
    for (let i = 0; i < 6; i++) g.add(mesh(new THREE.CylinderGeometry(0.2, 0.23, 2.6, 16), mat, -2.1 + i * 0.84, 1.9, 1.0));
    g.add(mesh(new THREE.BoxGeometry(4.6, 2.6, 1.4), std(0xcfcabd), 0, 1.9, -0.3));
    g.add(mesh(new THREE.BoxGeometry(5.2, 0.35, 2.7), mat, 0, 3.35, 0));
    const fr = mesh(new THREE.CylinderGeometry(1, 1, 2.7, 3), mat, 0, 4.0, 0); fr.rotation.set(Math.PI / 2, 0, Math.PI / 2); fr.scale.set(0.6, 1, 2.75); g.add(fr);
    const luz = glow(ACC, 2, 0.5); luz.position.set(0, 4.2, 1.4); g.add(luz);
    return { g, upd(t) { g.rotation.y = -0.3 + 0.2 * Math.sin(t * 0.35); } };
  };

  KIT.balanca = () => {
    const g = new THREE.Group();
    g.add(mesh(new THREE.CylinderGeometry(1.0, 1.2, 0.3, 32), M.metal, 0, 0.15, 0), mesh(new THREE.CylinderGeometry(0.1, 0.12, 4, 16), M.metal, 0, 2.2, 0));
    const travessa = new THREE.Group(); travessa.position.y = 4.2; g.add(travessa);
    travessa.add(mesh(new THREE.BoxGeometry(4.4, 0.12, 0.12), M.ouro));
    const pratos = [-2.1, 2.1].map((x, i) => { const p = new THREE.Group(); g.add(p); p.add(mesh(new THREE.CylinderGeometry(0.9, 0.6, 0.18, 32), i ? M.acc : M.ouro, 0, -1.6, 0)); p.add(mesh(new THREE.CylinderGeometry(0.02, 0.02, 1.6, 6), M.metal, 0, -0.8, 0)); return { p, x }; });
    return { g, upd(t) { const a = 0.16 * Math.sin(t * 0.9); travessa.rotation.z = a; pratos.forEach(o => { o.p.position.set(o.x * Math.cos(a), 4.2 + o.x * Math.sin(a), 0); }); } };
  };

  // ------------------------------------------------------------------ montagem
  function caixa(g) {
    g.updateMatrixWorld(true);
    const b = new THREE.Box3();
    g.traverse(o => {
      if (!o.isMesh || o.userData.nofit) return;
      if (o.isInstancedMesh) { o.computeBoundingBox(); b.union(o.boundingBox.clone().applyMatrix4(o.matrixWorld)); }
      else { if (!o.geometry.boundingBox) o.geometry.computeBoundingBox(); b.union(o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld)); }
    });
    return b;
  }

  function construir(nome, tam, seed, vals, principal) {
    const fab = KIT[nome] || KIT.rede_neural;
    let r;
    try { r = fab({ rnd: rng(seed), vals }); } catch (e) { r = KIT.rede_neural({ rnd: rng(seed), vals }); }
    // w (posição na cena) → ajuste (tamanho e centro) → r.g (o objeto, livre para animar)
    const w = new THREE.Group(), ajuste = new THREE.Group(); w.add(ajuste); ajuste.add(r.g);
    const b = caixa(w), s = b.getSize(V(0, 0, 0)), m = Math.max(s.x, s.y, s.z) || 1;
    ajuste.scale.setScalar(tam * (principal && r.size ? r.size / 4.4 : 1) / m);  // cenário amplo (cidade, data center) só cresce como principal
    const b2 = caixa(w);
    ajuste.position.set(-(b2.min.x + b2.max.x) / 2, -b2.min.y + (r.lift || 0) * tam, -(b2.min.z + b2.max.z) / 2);
    return { w, upd: r.upd || null, alt: (b2.max.y - b2.min.y) + (r.lift || 0) * tam };
  }

  function valoresDaCena(p) {
    // só usa os números da cena quando são comparáveis (mesma unidade); senão o gráfico enganaria
    if (!p) return null;
    const mesma = arr => new Set(arr.map(x => String((x.suffix != null ? x.suffix : p.suffix) || '').trim())).size === 1;
    if (Array.isArray(p.bars) && p.bars.length >= 2 && mesma(p.bars)) return p.bars.map(b => +b.value).filter(isFinite);
    if (p.left && p.right && mesma([p.left, p.right])) return [+p.left.value, +p.right.value].filter(isFinite);
    return null;
  }

  function montarGrupo(seg, idx) {
    const p = seg.params || {}, cfg = p._3d || {}, objs = (cfg.objetos && cfg.objetos.length ? cfg.objetos : ['rede_neural']).slice(0, 3);
    const holder = new THREE.Group(), upds = [], vals = valoresDaCena(p);
    const lados = PORT ? [[-2.9, -2.8], [2.9, -2.8]] : [[-4.6, -2.6], [4.6, -2.6]];
    let alt = 4;
    objs.forEach((nome, i) => {
      const o = construir(nome, i === 0 ? 4.4 : 2.3, 1000 + idx * 17 + i, i === 0 ? vals : null, i === 0);
      if (i === 0) alt = Math.max(2, o.alt); else o.w.position.set(lados[i - 1][0], 0, lados[i - 1][1]);
      if (o.upd) upds.push(o.upd);
      holder.add(o.w);
    });
    holder.visible = false; S.add(holder);
    return { holder, upds, cam: cfg.camera || ['orbita', 'aproxima', 'sobe', 'lateral'][idx % 4], alt, idx };
  }

  // ------------------------------------------------------------------ câmera
  function camera(gr, u, t) {
    const R0 = (PORT ? 12.5 : 10.5) * Math.max(0.85, gr.alt / 4.4), alvoY = Math.min(gr.alt * 0.5, 3.2) + 0.3;
    const a0 = ((gr.idx * 0.83) % 1.3) - 0.65;
    let pos, alvo = V(0, alvoY, 0);
    if (gr.cam === 'aproxima') { const r = R0 * (1.45 - 0.3 * u); pos = V(Math.sin(a0) * r, alvoY + 1.6, Math.cos(a0) * r); }
    else if (gr.cam === 'sobe') { pos = V(Math.sin(a0) * R0, 0.6 + u * 4.5, Math.cos(a0) * R0); }
    else if (gr.cam === 'lateral') { pos = V(-3.5 + 7 * u, alvoY + 1.4, R0); alvo.x = (-3.5 + 7 * u) * 0.25; }
    else { const a = a0 + (u - 0.5) * 0.9; pos = V(Math.sin(a) * R0, alvoY + 1.8, Math.cos(a) * R0); }
    pos.y += 0.08 * Math.sin(t * 0.7);
    C.position.copy(pos); C.lookAt(alvo);
  }

  // ------------------------------------------------------------------ init / render
  W3T.init = function (stage, data) {
    W = data.w; H = data.h; PORT = H > W;
    ACC = new THREE.Color(data.theme.accent); ACC2 = new THREE.Color(data.theme.accent2);
    GLOW = glowTex();
    M.branco = std(0xe9edf3, { roughness: 0.45 }); M.escuro = std(0x232a38, { metalness: 0.3, roughness: 0.5 });
    M.cinzaEscuro = std(0x0f131b, { roughness: 0.6 }); M.metal = std(0xc3c9d3, { metalness: 0.4, roughness: 0.35 });
    M.cinza = std(0x7d8592, { roughness: 0.55 }); M.ouro = std(0xf2c14e, { metalness: 0.35, roughness: 0.35, emissive: 0x4a3505, emissiveIntensity: 0.6 });
    M.acc = std(ACC, { emissive: ACC, emissiveIntensity: 0.35, metalness: 0.3, roughness: 0.4 });
    M.painel = std(0x1b3a8c, { metalness: 0.6, roughness: 0.25, emissive: 0x0a1a40 }); M.cinzaBarra = std(0x3b4252, { metalness: 0.4, roughness: 0.45 });

    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
    R.setPixelRatio(data.scale3d || 0.75); R.setSize(W, H);
    R.outputColorSpace = THREE.SRGBColorSpace; R.toneMapping = THREE.ACESFilmicToneMapping; R.toneMappingExposure = 1.25;
    const cv = R.domElement; cv.id = 'gl3d'; stage.appendChild(cv);
    S = new THREE.Scene(); S.background = new THREE.Color(0x06080d); S.fog = new THREE.Fog(0x06080d, 16, 48);
    C = new THREE.PerspectiveCamera(PORT ? 48 : 36, W / H, 0.1, 200);
    if (PORT) C.setViewOffset(W, H, 0, -H * 0.06, W, H);   // objeto entre os cartões (em cima) e a legenda (embaixo)
    else C.setViewOffset(W, H, -W * 0.25, 0, W, H);       // objeto à direita: os cartões ficam à esquerda

    const chao = mesh(new THREE.CircleGeometry(70, 64), std(0x0a0d13, { roughness: 0.95 })); chao.rotation.x = -Math.PI / 2; S.add(chao);
    const grade = new THREE.GridHelper(90, 60, ACC, 0x1a2030); grade.material.transparent = true; grade.material.opacity = 0.22; grade.position.y = 0.01; S.add(grade);
    S.add(new THREE.HemisphereLight(0x9aa8d0, 0x0c0c12, 1.2));
    const key = new THREE.DirectionalLight(0xffffff, 1.7); key.position.set(6, 11, 9); S.add(key);
    const frente = new THREE.DirectionalLight(0xdfe6ff, 0.9); frente.position.set(-2, 4, 12); S.add(frente);
    const r1 = new THREE.PointLight(ACC, 55, 30, 1.6); r1.position.set(-6, 5, -4); S.add(r1);
    const r2 = new THREE.PointLight(ACC2, 30, 26, 1.6); r2.position.set(6, 3, -5); S.add(r2);
    const halo = glow(ACC, 16, 0.12); halo.position.set(0, 3, -6); S.add(halo);

    const rnd = rng(42), n = 260, pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { pos[i * 3] = (rnd() - 0.5) * 30; pos[i * 3 + 1] = rnd() * 10; pos[i * 3 + 2] = (rnd() - 0.5) * 24; }
    const gd = new THREE.BufferGeometry(); gd.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    DUST = new THREE.Points(gd, new THREE.PointsMaterial({ color: ACC, size: 0.07, transparent: true, opacity: 0.55, depthWrite: false }));
    DUST.userData.base = pos.slice(); S.add(DUST);

    // um grupo por segmento; cartelas de capítulo usam os objetos da cena seguinte
    const segs = data.segments || [];
    segs.forEach((s, i) => {
      let alvo = s;
      if (!(s.params && s.params._3d)) alvo = segs.slice(i + 1).find(x => x.params && x.params._3d) || s;
      GRUPOS.push(montarGrupo(alvo, i));
    });
    const shade = document.createElement('div'); shade.id = 'shade3d'; stage.appendChild(shade);
    W3T.on = true;
    return cv;
  };

  W3T.render = function (t, seg, idx) {
    if (!W3T.on) return;
    const gr = GRUPOS[idx || 0] || GRUPOS[0];
    GRUPOS.forEach(g => { g.holder.visible = g === gr; });
    const lt = seg ? Math.max(0, t - seg.start) : t, d = seg ? Math.max(0.5, seg.dur) : 5;
    if (gr) { gr.upds.forEach(f => f(t, lt, d)); camera(gr, ease(lt / d), t); }
    const b = DUST.userData.base, p = DUST.geometry.attributes.position.array;
    for (let i = 0; i < p.length; i += 3) { p[i + 1] = (b[i + 1] + t * 0.25) % 10; p[i] = b[i] + 0.3 * Math.sin(t * 0.3 + i); }
    DUST.geometry.attributes.position.needsUpdate = true;
    R.render(S, C);
  };

  W3T._grupos = GRUPOS;  // só para inspeção em testes
  window.W3T = W3T;
})();
