/* Cena própria do episódio #03 da série "Redes na Prática" (splitter óptico).
   Modelos feitos só para este vídeo, em código (Three.js), sobre uma bancada com manta de corte verde:
   splitter PLC em caixa ABS (entrada + 8 saídas no código de cores com conectores SC/APC), splitter em mini tubo
   de aço, splitter em cassete com adaptadores, o chip PLC em macro (arranjos de fibra em V e guias de onda em Y,
   a luz se dividindo) e o FBT (duas fibras torcidas, fundidas e afinadas). Materiais leves (sem transmissão real
   de vidro): o render no GitHub cabe folgado no tempo. A câmera voa entre as peças (params.peca). */
(function () {
  'use strict';
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  let R, S, C, W, H, ST, PORT, GLOW, ACC, ACC2;
  const ANIM = [], P = {};
  const CORES = [0x1f6fe0, 0xf28c28, 0x2fb34a, 0x8a5a2b, 0x9aa0a8, 0xf4f4f4, 0xe0322f, 0x15171a];  // código de cores das fibras
  function ease(u) { u = Math.max(0, Math.min(1, u)); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; }
  const std = (c, o) => new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.45, metalness: 0.1 }, o || {}));
  const bas = (c, o) => new THREE.MeshBasicMaterial(Object.assign({ color: c }, o || {}));
  function RB(w, h, d, r) { return (window.THREEX && THREEX.RoundedBoxGeometry) ? new THREEX.RoundedBoxGeometry(w, h, d, 3, r) : new THREE.BoxGeometry(w, h, d); }
  function m(geo, mat, x, y, z, pai) { const o = new THREE.Mesh(geo, mat); o.position.set(x || 0, y || 0, z || 0); (pai || S).add(o); return o; }
  function glow(cor, t, op) { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: cor, transparent: true, opacity: op == null ? 1 : op, blending: THREE.AdditiveBlending, depthWrite: false })); s.scale.set(t, t, 1); return s; }
  function tex(w, h, f) { const c = document.createElement('canvas'); c.width = w; c.height = h; f(c.getContext('2d'), w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; }
  function tubo(pts, r, mat, pai, seg) { const c = new THREE.CatmullRomCurve3(pts); const o = m(new THREE.TubeGeometry(c, seg || 64, r, 8, false), mat, 0, 0, 0, pai); o.userData.curva = c; return o; }
  function sc(pai, x, y, z, rotY, esc) {  // conector SC/APC verde (corpo, capa, ferrolho e capinha)
    const g = new THREE.Group(); g.position.set(x, y, z); g.rotation.y = rotY || 0; g.scale.setScalar(esc || 1); pai.add(g);
    m(RB(0.09, 0.09, 0.2, 0.012), std(0x35b45a, { roughness: 0.35 }), 0, 0, 0, g);
    m(RB(0.07, 0.07, 0.08, 0.01), std(0xe9edf1), 0, 0, -0.13, g);
    const bota = m(new THREE.CylinderGeometry(0.03, 0.022, 0.16, 16), std(0x35b45a), 0, 0, -0.24, g); bota.rotation.x = Math.PI / 2;
    const cap = m(new THREE.CylinderGeometry(0.018, 0.018, 0.06, 12), std(0x2a7d40), 0, 0, 0.13, g); cap.rotation.x = Math.PI / 2;
    return g;
  }

  // ---------------------------------------------------------------- bancada
  function bancada() {
    const manta = tex(1024, 1024, (c, w, h) => { c.fillStyle = '#123322'; c.fillRect(0, 0, w, h);
      c.strokeStyle = 'rgba(200,255,220,.08)'; c.lineWidth = 2; for (let i = 0; i <= 32; i++) { c.beginPath(); c.moveTo(i * 32, 0); c.lineTo(i * 32, h); c.moveTo(0, i * 32); c.lineTo(w, i * 32); c.stroke(); }
      c.strokeStyle = 'rgba(200,255,220,.16)'; c.lineWidth = 3; for (let i = 0; i <= 8; i++) { c.beginPath(); c.moveTo(i * 128, 0); c.lineTo(i * 128, h); c.moveTo(0, i * 128); c.lineTo(w, i * 128); c.stroke(); }
      c.fillStyle = 'rgba(200,255,220,.28)'; c.font = '700 20px monospace'; for (let i = 1; i < 8; i++) c.fillText(String(i * 4), i * 128 + 4, 22);
      c.strokeStyle = 'rgba(220,255,230,.25)'; c.beginPath(); c.moveTo(0, h); c.lineTo(w, 0); c.stroke(); });
    manta.wrapS = manta.wrapT = THREE.RepeatWrapping; manta.repeat.set(4, 2);
    m(RB(26, 0.4, 12, 0.1), std(0x23272d, { roughness: 0.7 }), 10, -0.2, 0);
    const tapete = m(new THREE.PlaneGeometry(24, 10), std(0xffffff, { map: manta, roughness: 0.9, metalness: 0, envMapIntensity: 0.4 }), 10, 0.005, 0); tapete.rotation.x = -Math.PI / 2;
    const fundo = m(new THREE.PlaneGeometry(80, 30), bas(0xffffff, { map: tex(16, 256, (g, w, h) => { const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#04060a'); gr.addColorStop(0.7, '#0a2533'); gr.addColorStop(1, '#04060a'); g.fillStyle = gr; g.fillRect(0, 0, w, h); }) }), 10, 6, -10);
  }

  // ---------------------------------------------------------------- splitter PLC em caixa ABS (herói)
  function plcCaixa() {
    const g = new THREE.Group(); g.position.set(0, 0.12, 0); S.add(g);
    m(RB(1.5, 0.22, 0.8, 0.06), std(0x16181c, { roughness: 0.4 }), 0, 0.11, 0, g);
    const rot = tex(512, 256, (c, w, h) => { c.fillStyle = '#d7dce2'; c.fillRect(0, 0, w, h); c.fillStyle = '#1b1f26'; c.font = '900 64px Figtree'; c.fillText('PLC 1x8', 28, 88);
      c.font = '700 34px monospace'; c.fillText('SC/APC · 1260-1650 nm', 28, 150); c.fillText('IL ≤ 10,5 dB', 28, 200); });
    const lab = m(new THREE.PlaneGeometry(0.9, 0.45), bas(0xffffff, { map: rot }), 0.05, 0.225, 0, g); lab.rotation.x = -Math.PI / 2;
    // entrada (cordão branco) e 8 saídas no código de cores, terminando em leque de conectores SC/APC
    tubo([V(-0.75, 0.11, 0), V(-1.3, 0.06, 0.15), V(-2.0, 0.03, 0.6), V(-2.6, 0.03, 0.4)], 0.025, std(0xf2f4f6), g);
    sc(g, -2.75, 0.06, 0.32, -Math.PI / 2 - 0.4);
    const saidas = [];
    CORES.forEach((cor, k) => {
      const z = -0.28 + k * 0.08, zf = -1.4 + k * 0.4;
      const t = tubo([V(0.75, 0.11, z), V(1.3, 0.05, z * 1.6), V(2.1, 0.03, zf * 0.8), V(2.8, 0.03, zf)], 0.016, std(cor, { roughness: 0.4 }), g);
      const cx = 2.95, c = sc(g, cx, 0.06, zf, Math.PI / 2);
      saidas.push({ t, ponta: V(cx + 0.15, 0.06, zf) });
    });
    // leituras de potência em cada saída (aparecem na cena "saidas")
    const leit = [-7.4, -7.6, -7.5, -7.8, -7.3, -7.6, -7.7, -7.5];
    const tags = saidas.map((s, k) => { const t = tex(256, 96, (c, w, h) => { c.fillStyle = 'rgba(8,11,16,.9)'; c.beginPath(); c.roundRect(4, 4, w - 8, h - 8, 18); c.fill(); c.strokeStyle = '#3dff9a'; c.lineWidth = 5; c.stroke();
        c.fillStyle = '#3dff9a'; c.font = '800 46px monospace'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(leit[k].toFixed(1).replace('.', ',').replace('-', '−'), w / 2, h / 2 + 2); });
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false })); sp.scale.set(0.5, 0.19, 1); sp.position.copy(s.ponta).add(V(0.45, 0.05, 0)); sp.visible = false; g.add(sp); return sp; });
    const luzIn = glow(ACC2, 0.35); g.add(luzIn);
    const luzes = saidas.map(() => { const s = glow(ACC2, 0.2); g.add(s); return s; });
    ANIM.push((t, ativo, lt) => {
      const u = (t * 0.35) % 1;
      luzIn.position.set(-2.6 + 1.85 * Math.min(1, u * 2), 0.06, 0.4 - 0.4 * Math.min(1, u * 2)); luzIn.material.opacity = u < 0.5 ? 1 : 0;
      luzes.forEach((s, k) => { const v = Math.max(0, (u - 0.5) * 2); s.position.copy(saidas[k].t.userData.curva.getPoint(Math.min(0.999, v))); s.material.opacity = u >= 0.5 ? 0.55 : 0; });
      const on = ativo === 'saidas';
      tags.forEach((sp, k) => { sp.visible = on && lt > 0.8 + k * 0.12; });
    });
    P.plc = { alvo: V(0.35, 0.2, 0), cam: V(-1.8, 2.3, 3.9) };
    P.saidas = { alvo: V(3.25, 0.2, 0), cam: V(-1.7, 2.8, 3.9) };
  }

  // ---------------------------------------------------------------- os três formatos lado a lado
  function formatos() {
    // mini tubo de aço com fibras 0,9 mm (para emendar dentro da CEO)
    const g = new THREE.Group(); g.position.set(7.5, 0.1, -1.2); S.add(g);
    const aco = new THREE.MeshStandardMaterial({ color: 0xc9ced6, metalness: 1, roughness: 0.25 });
    const tb = m(new THREE.CylinderGeometry(0.07, 0.07, 1.3, 32), aco, 0, 0.07, 0, g); tb.rotation.z = Math.PI / 2;
    [-0.68, 0.68].forEach(x => { const r = m(new THREE.CylinderGeometry(0.06, 0.07, 0.12, 24), std(0x15171a), x, 0.07, 0, g); r.rotation.z = Math.PI / 2; });
    tubo([V(-0.72, 0.07, 0), V(-1.3, 0.05, 0.1), V(-1.9, 0.03, 0.3)], 0.012, std(0xf4f4f4), g);
    CORES.forEach((cor, k) => tubo([V(0.72, 0.07, -0.03 + k * 0.009), V(1.3, 0.05, -0.35 + k * 0.1), V(1.9, 0.03, -0.7 + k * 0.2)], 0.01, std(cor), g));
    // cassete com adaptadores (para rack/DIO)
    const k2 = new THREE.Group(); k2.position.set(7.5, 0.1, 1.3); S.add(k2);
    const chapa = new THREE.MeshStandardMaterial({ color: 0x2c3138, metalness: 0.8, roughness: 0.35 });
    m(RB(1.6, 0.12, 1.0, 0.04), chapa, 0, 0.06, 0, k2);
    m(RB(1.6, 0.3, 0.06, 0.02), chapa, 0, 0.15, 0.5, k2);
    for (let i = 0; i < 8; i++) m(RB(0.12, 0.12, 0.1, 0.015), std(0x35b45a, { roughness: 0.35 }), -0.61 + i * 0.175, 0.17, 0.55, k2);
    m(RB(0.12, 0.12, 0.1, 0.015), std(0x2f6fd8), -0.78, 0.17, 0.55, k2).position.x = -0.78;
    for (let i = 0; i < 3; i++) { const o = m(new THREE.TorusGeometry(0.3 - i * 0.05, 0.008, 6, 48), std(0xf2f4f6), -0.1, 0.13, 0.05, k2); o.rotation.x = Math.PI / 2; o.scale.set(1.5, 1, 1); }
    m(RB(0.3, 0.04, 0.12, 0.01), new THREE.MeshStandardMaterial({ color: 0xc9ced6, metalness: 1, roughness: 0.3 }), 0.45, 0.14, 0.05, k2);
    ANIM.push((t, ativo) => { g.rotation.y = ativo === 'formatos' ? 0.15 * Math.sin(t * 0.6) : 0; k2.rotation.y = ativo === 'formatos' ? -0.12 * Math.sin(t * 0.6) : 0; });
    P.formatos = { alvo: V(7.5, 0.1, 0.2), cam: V(-0.9, 4.4, 3.1) };
  }

  // ---------------------------------------------------------------- chip PLC em macro
  function chip() {
    const g = new THREE.Group(); g.position.set(14, 0.6, 0); S.add(g);
    const vidro = new THREE.MeshStandardMaterial({ color: 0x0d2a44, roughness: 0.15, metalness: 0.2, transparent: true, opacity: 0.85, depthWrite: false, emissive: 0x04121e, emissiveIntensity: 0.5 });
    m(RB(3.2, 0.36, 1.5, 0.04), vidro, 0, 0, 0, g);
    m(RB(3.3, 0.12, 1.6, 0.03), new THREE.MeshStandardMaterial({ color: 0x8b95a3, metalness: 0.9, roughness: 0.3 }), 0, -0.26, 0, g);
    // arranjos de fibra (FA): blocos com sulcos em V e as fibras encaixadas
    const fa = (x, n, larg) => { const b = new THREE.Group(); b.position.set(x, 0, 0); g.add(b);
      m(RB(0.6, 0.3, larg, 0.03), new THREE.MeshStandardMaterial({ color: 0x5c7f99, roughness: 0.2, metalness: 0.3, transparent: true, opacity: 0.8, depthWrite: false }), 0, 0, 0, b);
      for (let i = 0; i < n; i++) { const z = n === 1 ? 0 : -larg / 2 + 0.12 + i * (larg - 0.24) / (n - 1);
        const f = m(new THREE.CylinderGeometry(0.014, 0.014, 0.9, 10), std(0xdfe8f0, { roughness: 0.3 }), (x < 0 ? -0.45 : 0.45), 0.02, z, b); f.rotation.z = Math.PI / 2;
        const v = m(new THREE.BoxGeometry(0.6, 0.02, 0.05), std(0x6c7a8a), 0, -0.05, z, b); } return b; };
    fa(-1.9, 1, 0.4); fa(1.9, 8, 1.4);
    // guias de onda em Y: 1 -> 2 -> 4 -> 8
    const guias = [], niveis = [0, 1, 2], zs = n => Array.from({ length: n }, (_, i) => n === 1 ? 0 : -0.58 + i * (1.16 / (n - 1)));
    const xs = [-1.55, -0.6, 0.35, 1.55];
    niveis.forEach(k => { const a = zs(2 ** k), b = zs(2 ** (k + 1));
      a.forEach((z, i) => [b[i * 2], b[i * 2 + 1]].forEach(z2 => {
        const c = new THREE.CatmullRomCurve3([V(xs[k], 0.19, z), V((xs[k] + xs[k + 1]) / 2, 0.19, (z + z2) / 2 + (z2 - z) * 0.1), V(xs[k + 1], 0.19, z2)]);
        const o = m(new THREE.TubeGeometry(c, 30, 0.03, 8, false), bas(0x46d8ff, { transparent: true, opacity: 1, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false }), 0, 0, 0, g); o.renderOrder = 5;
        guias.push({ c, k });
      })); });
    const pulsos = guias.map(o => { const s = glow(ACC2, 0.22 * Math.pow(0.8, o.k)); s.renderOrder = 6; s.material.depthTest = false; g.add(s); return { s, ...o }; });
    const entrada = glow(ACC2, 0.3); entrada.renderOrder = 6; entrada.material.depthTest = false; g.add(entrada);
    ANIM.push(t => {
      const u = (t * 0.4) % 1;
      entrada.position.set(-2.6 + 1.05 * Math.min(1, u * 4), 0.19, 0); entrada.material.opacity = u < 0.25 ? 1 : 0;
      pulsos.forEach(p => { const ini = 0.25 + p.k * 0.25, v = (u - ini) / 0.25; p.s.visible = v >= 0 && v <= 1; if (p.s.visible) { p.s.position.copy(p.c.getPoint(v)); p.s.material.opacity = Math.pow(0.62, p.k); } });
    });
    P.chip = { alvo: V(14, 0.6, 0), cam: V(-0.7, 3.8, 2.3) };
  }

  // ---------------------------------------------------------------- FBT: fibras torcidas, fundidas e afinadas
  function fbt() {
    const g = new THREE.Group(); g.position.set(20, 0.7, 0); S.add(g);
    const fibra = std(0xf4fbff, { roughness: 0.15, emissive: 0x1d6f9a, emissiveIntensity: 0.7 });
    const helice = (fase) => { const pts = []; for (let i = 0; i <= 60; i++) { const u = i / 60, x = -2.2 + u * 4.4, r = 0.12 * (1 - Math.exp(-Math.pow(x / 0.9, 2)) * 0.95) + 0.006;
        const a = fase + x * 3.2; pts.push(V(x, Math.sin(a) * r, Math.cos(a) * r)); } return new THREE.CatmullRomCurve3(pts); };
    const c1 = helice(0), c2 = helice(Math.PI);
    m(new THREE.TubeGeometry(c1, 160, 0.045, 10, false), fibra, 0, 0, 0, g); m(new THREE.TubeGeometry(c2, 160, 0.045, 10, false), fibra, 0, 0, 0, g);
    // cintura fundida (bicônica)
    const perfil = []; for (let i = 0; i <= 30; i++) { const y = -1 + i / 15; perfil.push(new THREE.Vector2(0.03 + 0.07 * Math.pow(Math.abs(y), 1.6), y * 0.9)); }
    const cin = m(new THREE.LatheGeometry(perfil, 32), new THREE.MeshStandardMaterial({ color: 0xbfe9ff, roughness: 0.1, transparent: true, opacity: 0.55, emissive: 0x0a3550, emissiveIntensity: 0.6 }), 0, 0, 0, g); cin.rotation.z = Math.PI / 2;
    m(RB(5.0, 0.08, 0.5, 0.02), new THREE.MeshStandardMaterial({ color: 0x8b95a3, metalness: 0.9, roughness: 0.3 }), 0, -0.25, 0, g);  // substrato
    const a = glow(ACC2, 0.4), b1 = glow(ACC2, 0.36), b2 = glow(0xffb020, 0.2); g.add(a, b1, b2);
    ANIM.push(t => {
      const u = (t * 0.35) % 1;
      if (u < 0.5) { a.visible = true; a.position.copy(c1.getPoint(u)); b1.visible = b2.visible = false; }
      else { a.visible = false; b1.visible = b2.visible = true; b1.position.copy(c1.getPoint(u)); b2.position.copy(c2.getPoint(u)); b1.material.opacity = 0.95; b2.material.opacity = 0.45; }
    });
    P.fbt = { alvo: V(20, 0.7, 0), cam: V(-1.2, 1.3, 2.9) };
  }

  // ---------------------------------------------------------------- ciclo
  const M3 = { on: false };
  M3.PECAS = ['plc', 'saidas', 'formatos', 'chip', 'fbt', 'geral'];
  M3.init = async function (stage, st) {
    ST = st; W = st.w; H = st.h; PORT = H > W;
    ACC = new THREE.Color(st.theme.accent || '#19c3ff'); ACC2 = new THREE.Color(st.theme.accent2 || '#3dff9a');
    GLOW = tex(128, 128, (g) => { const r = g.createRadialGradient(64, 64, 0, 64, 64, 64); r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.3, 'rgba(255,255,255,.55)'); r.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = r; g.fillRect(0, 0, 128, 128); });
    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    R.setPixelRatio(st.scale3d || 0.75); R.setSize(W, H, false);
    R.outputColorSpace = THREE.SRGBColorSpace; R.toneMapping = THREE.ACESFilmicToneMapping; R.toneMappingExposure = 1.1;
    const cv = R.domElement; cv.id = 'gl3d'; Object.assign(cv.style, { position: 'absolute', left: '0', top: '0', width: W + 'px', height: H + 'px' }); stage.appendChild(cv);
    S = new THREE.Scene(); S.background = new THREE.Color(0x05070b); S.fog = new THREE.Fog(0x05070b, 12, 50);
    if (window.THREEX && THREEX.RoomEnvironment) { const pm = new THREE.PMREMGenerator(R); S.environment = pm.fromScene(new THREEX.RoomEnvironment(R), 0.04).texture; pm.dispose(); }
    S.add(new THREE.HemisphereLight(0xb8c8e8, 0x05070b, 0.7));
    const key = new THREE.DirectionalLight(0xffffff, 2.0); key.position.set(6, 12, 9); S.add(key);
    const rim = new THREE.DirectionalLight(ACC, 1.8); rim.position.set(-8, 5, -8); S.add(rim);
    const rim2 = new THREE.DirectionalLight(ACC2, 0.9); rim2.position.set(24, 4, -8); S.add(rim2);
    C = new THREE.PerspectiveCamera(PORT ? 46 : 34, W / H, 0.03, 200);
    if (PORT) C.setViewOffset(W, H, 0, -H * 0.15, W, H);
    bancada(); plcCaixa(); formatos(); chip(); fbt();
    P.geral = { alvo: V(10, 0.3, 0), cam: V(0.01, 13, 12) };
    M3.on = true; return cv;
  };
  function pose(n) { const p = P[n] || P.geral; return { pos: p.alvo.clone().add(p.cam), alvo: p.alvo.clone() }; }
  M3.render = function (t, seg) {
    const segs = (ST.segments || []).filter(s => s.kind === 'scene');
    const i = Math.max(0, segs.indexOf(seg));
    const pc = s => (s && s.params && s.params.peca) || null;
    let atual = pc(seg); if (!atual) for (let k = i; k >= 0; k--) if (pc(segs[k])) { atual = pc(segs[k]); break; } atual = atual || 'geral';
    let ant = null; for (let k = i - 1; k >= 0; k--) if (pc(segs[k])) { ant = pc(segs[k]); break; }
    const lt = seg ? Math.max(0, t - seg.start) : 0, d = seg ? Math.max(1, seg.dur) : 5;
    const a = pose(ant || atual), b = pose(atual), dist = a.pos.distanceTo(b.pos), voo = Math.min(1.8, 0.8 + dist / 25), u = ease(lt / voo);
    const pos = a.pos.clone().lerp(b.pos, u), alvo = a.alvo.clone().lerp(b.alvo, u);
    pos.y += Math.sin(Math.PI * u) * Math.min(3, dist * 0.1);
    const k = Math.max(0, lt - voo) / Math.max(1, d - voo);
    const off = pos.clone().sub(alvo); off.applyAxisAngle(V(0, 1, 0), (atual === 'geral' ? 0.05 : 0.2) * Math.sin(k * Math.PI * 0.8)).multiplyScalar(1 - 0.07 * k);
    C.position.copy(alvo).add(off); C.lookAt(alvo);
    ANIM.forEach(f => f(t, atual, lt));
    R.render(S, C);
  };
  window.VIDEO3D = window.VIDEO3D || {};
  window.VIDEO3D.redes03 = M3;
})();
