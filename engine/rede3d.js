/* Cenário contínuo "rota": o caminho da internet da origem até a casa do cliente, num só mundo 3D feito em código
   (sem modelo pronto). Estações ao longo do caminho: servidor de origem, cabo submarino, estação de ancoragem,
   operadoras gigantes/PTT, provedor regional, concentrador (BNG), CGNAT, switch de borda, OLT, DIO, postes com
   CEO e CTO, casa do cliente com ONU e Wi-Fi. Uma fibra contínua liga tudo e os pacotes de dados correm por ela.
   Cada cena diz params.local; a câmera voa até a estação (movimento contínuo, sem corte) e as cenas técnicas
   (terminal, topologia, faixa) aparecem por cima, em 2D. "mapa" sobe a câmera e mostra o caminho inteiro de cima. */
(function () {
  'use strict';
  const WRT = { on: false };
  let R, S, C, W, H, ST, PORT, CAMINHO, PACOTES = [], ANIM = [], GLOW;
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const ACC = new THREE.Color(0x19c3ff), ACC2 = new THREE.Color(0x3dff9a);
  function std(c, o) { return new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.55, metalness: 0.2 }, o || {})); }
  const bas = (c, o) => new THREE.MeshBasicMaterial(Object.assign({ color: c }, o || {}));
  function caixa(w, h, d, mat, x, y, z, pai) { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); (pai || S).add(m); return m; }
  function ease(u) { u = Math.max(0, Math.min(1, u)); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; }
  function glow(cor, tam, op) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: cor, transparent: true, opacity: op == null ? 1 : op, blending: THREE.AdditiveBlending, depthWrite: false }));
    s.scale.set(tam, tam, 1); return s;
  }
  function texto(t1, t2, cor) {  // placa de nome sempre virada para a câmera
    const c = document.createElement('canvas'); c.width = 768; c.height = 220; const g = c.getContext('2d');
    g.fillStyle = 'rgba(8,11,16,.88)'; const r = 30; g.beginPath(); g.moveTo(r, 0); g.arcTo(768, 0, 768, 220, r); g.arcTo(768, 220, 0, 220, r); g.arcTo(0, 220, 0, 0, r); g.arcTo(0, 0, 768, 0, r); g.fill();
    g.strokeStyle = cor || '#19c3ff'; g.lineWidth = 8; g.stroke();
    g.fillStyle = '#fff'; g.font = '900 92px Figtree, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(t1, 384, t2 ? 82 : 110);
    if (t2) { g.fillStyle = cor || '#19c3ff'; g.font = '700 52px "DejaVu Sans Mono", monospace'; g.fillText(t2, 384, 165); }
    const tx = new THREE.CanvasTexture(c); tx.colorSpace = THREE.SRGBColorSpace;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tx, transparent: true, depthWrite: false })); s.scale.set(3.4, 0.97, 1); s.renderOrder = 10;
    return s;
  }
  // as placas 3D com o nome da estação competiam com o título da cena (o título 2D já nomeia cada parada)
  function placa() { return null; }
  function base(x, z, w, d) {  // plataforma escura com borda acesa
    caixa(w, 0.25, d, std(0x121821, { roughness: 0.8 }), x, 0.125, z);
    const borda = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w, 0.25, d)), new THREE.LineBasicMaterial({ color: ACC, transparent: true, opacity: 0.6 }));
    borda.position.set(x, 0.125, z); S.add(borda);
  }
  function rack(x, z, alt, pai) {
    const g = new THREE.Group(); g.position.set(x, 0.25, z); (pai || S).add(g);
    caixa(0.9, alt, 0.9, std(0x1b222d, { metalness: 0.5 }), 0, alt / 2, 0, g);
    const leds = [];
    for (let u = 0; u < Math.floor(alt / 0.28); u++) {
      caixa(0.8, 0.2, 0.02, std(0x0b0e13), 0, 0.2 + u * 0.28, 0.46, g);
      for (let k = 0; k < 4; k++) { const l = caixa(0.05, 0.04, 0.02, bas(k % 2 ? ACC : ACC2), -0.3 + k * 0.08, 0.2 + u * 0.28, 0.475, g); leds.push({ l, f: Math.random() * 9, v: 3 + (u * 7 + k * 3) % 9 }); }
    }
    ANIM.push(t => leds.forEach(o => { o.l.visible = Math.sin(t * o.v + o.f) > -0.3; }));
    return g;
  }
  function roteador(x, y, z, pai) {
    const g = new THREE.Group(); g.position.set(x, y, z); (pai || S).add(g);
    caixa(1.0, 0.35, 0.7, std(0x223044, { metalness: 0.6 }), 0, 0.17, 0, g);
    const l = caixa(0.6, 0.04, 0.02, bas(ACC2), 0, 0.2, 0.36, g); ANIM.push(t => { l.visible = Math.sin(t * 6 + x) > -0.5; });
    return g;
  }

  // ---------------------------------------------------------------- estações (x ao longo do caminho)
  const L = {};  // local -> {alvo, cam (deslocamento da câmera)}
  function local(nome, alvo, cam) { L[nome] = { alvo, cam }; }
  function montar() {
    // chão: grade escura (o "mundo" de rede)
    const chao = new THREE.Mesh(new THREE.PlaneGeometry(260, 80), std(0x080b10, { roughness: 1, metalness: 0 })); chao.rotation.x = -Math.PI / 2; chao.position.set(55, -0.01, 0); S.add(chao);
    const grade = new THREE.GridHelper(260, 130, ACC, 0x1a2230); grade.material.transparent = true; grade.material.opacity = 0.16; grade.position.set(55, 0, 0); S.add(grade);

    // 1. origem: data center do serviço (onde o vídeo está guardado)
    base(0, 0, 7, 5); for (let i = 0; i < 5; i++) rack(-2.4 + i * 1.2, -0.6, 2.2); for (let i = 0; i < 5; i++) rack(-2.4 + i * 1.2, 1.2, 2.2);
    placa('ORIGEM', 'servidor do vídeo', 0, 3.4, 0);
    local('origem', V(0, 1.2, 0), V(-4.5, 2.6, 6.5));

    // 2. oceano com cabo submarino no fundo (x 6..30)
    const agua = new THREE.Mesh(new THREE.BoxGeometry(24, 5, 16), std(0x0b4f7a, { transparent: true, opacity: 0.28, roughness: 0.1, metalness: 0, depthWrite: false }));
    agua.position.set(18, -2.5, 0); S.add(agua);
    const sup = new THREE.Mesh(new THREE.PlaneGeometry(24, 16), std(0x2aa7e0, { transparent: true, opacity: 0.22, roughness: 0.05, depthWrite: false, side: THREE.DoubleSide }));
    sup.rotation.x = -Math.PI / 2; sup.position.set(18, 0.02, 0); S.add(sup);
    ANIM.push(t => { sup.position.y = 0.02 + 0.04 * Math.sin(t * 1.3); });
    const fundo = new THREE.Mesh(new THREE.PlaneGeometry(24, 16), std(0x1d2a33, { roughness: 1 })); fundo.rotation.x = -Math.PI / 2; fundo.position.set(18, -4.95, 0); S.add(fundo);
    for (let i = 0; i < 40; i++) { const p = new THREE.Mesh(new THREE.DodecahedronGeometry(0.15 + (i % 5) * 0.08), std(0x2c3a44, { roughness: 1 })); p.position.set(7 + (i * 7.3) % 22, -4.9, -6 + (i * 3.7) % 12); S.add(p); }
    const rep = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 1.4, 20), std(0x8a96a8, { metalness: 0.8 })); rep.rotation.z = Math.PI / 2; rep.position.set(18, -4.55, 0); S.add(rep);
    placa('CABO SUBMARINO', 'fibra no fundo do mar', 18, -1.6, 0);
    local('submarino', V(16, -4.2, 0), V(-4.2, 1.4, 4.8));

    // 3. estação de ancoragem no litoral
    base(33, 0, 5, 4); caixa(3.2, 2.0, 2.4, std(0xd6dde6, { roughness: 0.7, metalness: 0 }), 33, 1.25, 0); caixa(0.9, 1.2, 0.05, bas(0xffe1a8), 33, 1.0, 1.23);
    placa('ESTAÇÃO DE ANCORAGEM', 'o cabo chega ao litoral', 33, 3.2, 0);
    local('estacao', V(32, 0.9, 0), V(-4.5, 2.4, 6));

    // 4. operadoras gigantes e PTT (anel de roteadores com o ponto de troca no centro)
    base(43, 0, 8, 8);
    const nucleo = roteador(43, 0.25, 0); nucleo.scale.setScalar(1.6);
    const anel = []; for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; anel.push(V(43 + Math.cos(a) * 3, 0.45, Math.sin(a) * 3)); roteador(anel[i].x, 0.25, anel[i].z); }
    anel.forEach((p, i) => { [V(43, 0.55, 0), anel[(i + 1) % 6]].forEach(q => { const d = q.clone().sub(p); const tb = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, d.length(), 8), bas(ACC, { transparent: true, opacity: 0.7 }));
      tb.position.copy(p).add(q).multiplyScalar(0.5); tb.quaternion.setFromUnitVectors(V(0, 1, 0), d.normalize()); S.add(tb); }); });
    placa('OPERADORAS + PTT', 'troca de tráfego', 43, 3.0, 0);
    local('operadora', V(43, 0.6, 0), V(-5.5, 4.2, 7));

    // 5. provedor regional (o seu ISP): sala com racks; dentro dele, concentrador, CGNAT, switch, OLT e DIO
    base(62, 0, 26, 7);
    placa('PROVEDOR REGIONAL', 'o seu provedor (ISP)', 52.5, 3.4, -1.5);
    rack(51, -1.2, 2.2); rack(52.2, -1.2, 2.2); roteador(54, 1.25, -1.2);
    local('isp', V(52.5, 1.2, -1), V(-4.2, 2.6, 6.5));
    // concentrador (BNG): autentica o PPPoE e entrega o IP
    rack(57, 0, 2.4); placa('CONCENTRADOR', 'BNG · PPPoE', 57, 3.4, 0, '#3dff9a');
    local('concentrador', V(57, 1.3, 0), V(-2.6, 1.9, 4.2));
    // CGNAT: tela com a tradução de endereço
    const cg = rack(61, 0, 2.0);
    const telaC = document.createElement('canvas'); telaC.width = 512; telaC.height = 256; const tg = telaC.getContext('2d');
    tg.fillStyle = '#071018'; tg.fillRect(0, 0, 512, 256); tg.font = '700 34px "DejaVu Sans Mono", monospace'; tg.fillStyle = '#3dff9a';
    ['100.64.12.34', '      ↓ NAT', '203.0.113.7'].forEach((s, i) => tg.fillText(s, 40, 70 + i * 70));
    const ttx = new THREE.CanvasTexture(telaC); ttx.colorSpace = THREE.SRGBColorSpace;
    const tela = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 0.7), bas(0xffffff, { map: ttx })); tela.position.set(61, 2.75, 0.2); S.add(tela);
    placa('CGNAT', 'muitos clientes, um IP', 61, 3.7, 0, '#3dff9a');
    local('cgnat', V(61, 1.6, 0), V(-2.4, 1.9, 4.4));
    // switch de borda com cabos coloridos (VLANs)
    caixa(1.2, 0.9, 0.7, std(0x1b222d), 65, 0.7, 0); const sw = caixa(1.6, 0.18, 0.6, std(0x2a3546, { metalness: 0.6 }), 65, 1.25, 0);
    const swl = []; for (let i = 0; i < 12; i++) swl.push(caixa(0.06, 0.04, 0.02, bas([ACC, ACC2, 0xffb020][i % 3]), 64.4 + i * 0.1, 1.25, 0.31));
    ANIM.push(t => swl.forEach((l, i) => { l.visible = Math.sin(t * (5 + i) + i) > -0.4; }));
    placa('SWITCH DE BORDA', 'VLAN por serviço', 65, 2.6, 0);
    local('switch_borda', V(65, 1.2, 0), V(-2.2, 1.5, 3.6));
    // OLT: chassi com placas PON e cordões amarelos
    const olt = new THREE.Group(); olt.position.set(69.5, 0.25, 0); S.add(olt);
    caixa(1.4, 1.6, 0.8, std(0x1f2733, { metalness: 0.6 }), 0, 0.8, 0, olt);
    const pons = [];
    for (let i = 0; i < 8; i++) { caixa(0.12, 1.3, 0.05, std(0x2d3a4d), -0.55 + i * 0.157, 0.8, 0.41, olt); const l = caixa(0.05, 0.05, 0.02, bas(ACC2), -0.55 + i * 0.157, 1.35, 0.44, olt); pons.push(l);
      const fio = new THREE.Mesh(new THREE.TorusGeometry(0.35 + i * 0.02, 0.012, 6, 24, Math.PI), std(0xf2d14b)); fio.position.set(-0.55 + i * 0.157, 0.6, 0.6); fio.rotation.y = Math.PI / 2; olt.add(fio); }
    ANIM.push(t => pons.forEach((l, i) => { l.visible = Math.sin(t * 9 + i) > -0.6; }));
    placa('OLT', 'luz em 1490 e 1310 nm', 69.5, 2.9, 0, '#3dff9a');
    local('olt', V(69.5, 1.1, 0), V(-2.3, 1.6, 3.6));
    // DIO: painel de fibras na parede, saindo para a rua
    caixa(0.2, 1.4, 1.8, std(0xcfd6df, { metalness: 0.3 }), 73.5, 1.2, 0);
    for (let i = 0; i < 12; i++) caixa(0.04, 0.08, 0.1, bas(i % 4 ? 0x19c3ff : 0x3dff9a), 73.38, 0.75 + (i % 6) * 0.18, -0.4 + Math.floor(i / 6) * 0.8);
    placa('DIO', 'distribuidor óptico', 73.5, 2.6, 0);
    local('dio', V(73.5, 1.2, 0), V(-2.4, 1.4, 3.2));

    // 6. rua: postes, cabo aéreo, CEO (emenda + splitter primário) e CTO (splitter secundário)
    for (let i = 0; i < 6; i++) { const x = 78 + i * 6; const p = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.16, 7, 10), std(0x8a8f96, { roughness: 0.9, metalness: 0 })); p.position.set(x, 3.5, -1.2); S.add(p);
      caixa(1.4, 0.1, 0.1, std(0x8a8f96), x, 6.3, -1.2); }
    const ceo = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 1.1, 20), std(0x1c1f24, { roughness: 0.6 })); ceo.rotation.z = Math.PI / 2; ceo.position.set(86.5, 5.55, -1.2); S.add(ceo);
    placa('CEO', 'emenda + splitter 1:8', 86.5, 7.2, -1.2, '#3dff9a');
    local('ceo', V(86.5, 5.5, -1.2), V(-2.6, 0.8, 3.6));
    caixa(0.7, 0.9, 0.35, std(0xe9edf3, { roughness: 0.5, metalness: 0 }), 96, 4.6, -0.95);
    placa('CTO', 'splitter 1:8 · drops', 96, 6.4, -1.2, '#3dff9a');
    local('cto', V(96, 4.6, -1.0), V(-2.4, 0.6, 3.6));

    // 7. casa do cliente (sem a parede da frente: dá para ver a ONU e o roteador)
    const cx = 104, cz = 2.5;
    caixa(5, 0.2, 4, std(0x9b7a5a, { roughness: 0.9, metalness: 0 }), cx, 0.1, cz);
    caixa(5, 2.8, 0.15, std(0x5d6673, { roughness: 0.9, metalness: 0 }), cx, 1.5, cz - 2);
    caixa(0.15, 2.8, 4, std(0x5d6673, { roughness: 0.9, metalness: 0 }), cx - 2.5, 1.5, cz); caixa(0.15, 2.8, 4, std(0x5d6673, { roughness: 0.9, metalness: 0 }), cx + 2.5, 1.5, cz);
    const tel = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 3.6, 1.6, 4, 1), std(0xa8432f, { roughness: 0.8, metalness: 0 })); tel.rotation.y = Math.PI / 4; tel.scale.set(1, 1, 0.8); tel.position.set(cx, 3.7, cz); S.add(tel);
    caixa(0.9, 0.6, 0.5, std(0x6b4a33, { metalness: 0 }), cx - 1.2, 0.5, cz - 1.5);
    caixa(0.45, 0.08, 0.32, std(0xf4f6fa, { metalness: 0 }), cx - 1.35, 0.84, cz - 1.5);   // ONU
    const onuL = [0, 1, 2].map(i => caixa(0.03, 0.02, 0.02, bas(0x30d158), cx - 1.5 + i * 0.08, 0.86, cz - 1.33));
    caixa(0.4, 0.07, 0.28, std(0x10141b), cx - 0.85, 0.84, cz - 1.5);                     // roteador Wi-Fi
    const ondas = [0, 1, 2].map(i => { const o = new THREE.Mesh(new THREE.TorusGeometry(0.4 + i * 0.4, 0.025, 6, 40), bas(ACC2, { transparent: true })); o.rotation.x = Math.PI / 2; o.position.set(cx - 0.85, 0.95, cz - 1.5); S.add(o); return o; });
    ANIM.push(t => { ondas.forEach((o, i) => { const u = (t * 0.7 + i / 3) % 1; o.scale.setScalar(0.4 + u * 2.4); o.material.opacity = 0.8 * (1 - u); }); onuL.forEach((l, i) => { l.visible = i < 2 || Math.sin(t * 12) > 0; }); });
    caixa(1.6, 0.5, 0.7, std(0x3d4a5c, { metalness: 0 }), cx + 1.2, 0.45, cz + 0.6);  // sofá
    placa('CASA DO CLIENTE', 'ONU + Wi-Fi', cx, 5.0, cz);
    local('casa', V(cx, 1.0, cz), V(-2.2, 1.6, 10.5));
    local('onu', V(cx - 1.1, 0.85, cz - 1.4), V(1.4, 1.5, 2.4));
    local('mapa', V(55, 0, 0), V(0.001, 95, 28));

    // a fibra que liga tudo (o caminho dos dados)
    const pts = [V(0, 1.0, 0.4), V(3.5, 0.5, 0.6), V(7, -1, 0.3), V(10, -4.6, 0), V(26, -4.6, 0), V(29.5, -1, 0), V(31.5, 0.4, 0.2), V(39, 0.5, 0), V(43, 0.6, 0),
      V(48, 0.5, 0.3), V(52.5, 0.45, 0.6), V(57, 0.45, 0.6), V(61, 0.45, 0.6), V(65, 0.45, 0.6), V(69.5, 0.45, 0.8), V(73.4, 0.6, 0.6), V(76, 1.0, -0.6),
      V(77.8, 5.9, -1.0), V(86.5, 5.85, -1.0), V(96, 5.0, -0.9), V(98.5, 3.4, 0.0), V(101.6, 1.0, 1.0), V(cx - 1.35, 0.9, cz - 1.5)];
    CAMINHO = new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.2);
    S.add(new THREE.Mesh(new THREE.TubeGeometry(CAMINHO, 900, 0.07, 8, false), std(0xf2d14b, { emissive: 0x4a3a05, roughness: 0.4 })));
    for (let i = 0; i < 26; i++) { const p = glow(i % 3 ? ACC : ACC2, 0.9); S.add(p); PACOTES.push({ p, f: i / 26 }); }
  }

  // ---------------------------------------------------------------- câmera entre locais (voo contínuo)
  function pose(nome) { const l = L[nome] || L.mapa; return { pos: l.alvo.clone().add(l.cam), alvo: l.alvo.clone() }; }
  WRT.LOCAIS = ['origem', 'submarino', 'estacao', 'operadora', 'isp', 'concentrador', 'cgnat', 'switch_borda', 'olt', 'dio', 'ceo', 'cto', 'casa', 'onu', 'mapa'];

  WRT.init = async function (stage, st) {
    ST = st; W = st.w; H = st.h; PORT = H > W;
    GLOW = (() => { const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d'); const r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.3, 'rgba(255,255,255,.6)'); r.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = r; g.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c); })();
    if (st.theme && st.theme.accent) ACC.set(st.theme.accent);
    if (st.theme && st.theme.accent2) ACC2.set(st.theme.accent2);
    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    R.setPixelRatio(st.scale3d || 0.75); R.setSize(W, H, false);
    R.outputColorSpace = THREE.SRGBColorSpace; R.toneMapping = THREE.ACESFilmicToneMapping; R.toneMappingExposure = 1.15;
    const cv = R.domElement; cv.id = 'gl3d'; Object.assign(cv.style, { position: 'absolute', left: '0', top: '0', width: W + 'px', height: H + 'px' });
    stage.appendChild(cv);
    S = new THREE.Scene(); S.background = new THREE.Color(0x06080d); S.fog = new THREE.Fog(0x06080d, 30, 140);
    if (window.THREEX && THREEX.RoomEnvironment) { const pm = new THREE.PMREMGenerator(R); S.environment = pm.fromScene(new THREEX.RoomEnvironment(R), 0.04).texture; pm.dispose(); }
    S.add(new THREE.HemisphereLight(0xaab8e0, 0x0c0c12, 0.9));
    const k = new THREE.DirectionalLight(0xffffff, 1.4); k.position.set(30, 40, 30); S.add(k);
    C = new THREE.PerspectiveCamera(PORT ? 52 : 38, W / H, 0.05, 400);
    // 9:16: o assunto fica na metade de baixo (o texto/cartão técnico ocupa o alto da tela)
    if (PORT) C.setViewOffset(W, H, 0, -H * 0.14, W, H);
    montar();
    WRT.on = true;
    return cv;
  };

  WRT.render = function (t, seg) {
    if (!WRT.on) return;
    const segs = (ST.segments || []).filter(s => s.kind === 'scene');
    const i = Math.max(0, segs.indexOf(seg));
    const loc = l => (l && l.params && l.params.local) || null;
    let atual = loc(seg); if (!atual) { for (let k = i; k >= 0; k--) if (loc(segs[k])) { atual = loc(segs[k]); break; } } atual = atual || 'mapa';
    let ant = null; for (let k = i - 1; k >= 0; k--) if (loc(segs[k])) { ant = loc(segs[k]); break; }
    const lt = seg ? Math.max(0, t - seg.start) : 0, d = seg ? Math.max(1, seg.dur) : 5;
    const a = pose(ant || atual), b = pose(atual);
    const dist = a.pos.distanceTo(b.pos), voo = Math.min(2.2, 0.9 + dist / 40), u = ease(lt / voo);
    const pos = a.pos.clone().lerp(b.pos, u), alvo = a.alvo.clone().lerp(b.alvo, u);
    pos.y += Math.sin(Math.PI * u) * Math.min(14, dist * 0.18);  // arco por cima entre estações distantes
    // depois de chegar: aproximação lenta e leve giro (a cena continua viva)
    const k = Math.max(0, lt - voo) / Math.max(1, d - voo);
    const giro = (atual === 'mapa' ? 0 : 0.18) * Math.sin(k * Math.PI * 0.9);
    const off = pos.clone().sub(alvo); off.applyAxisAngle(V(0, 1, 0), giro).multiplyScalar(1 - 0.08 * k);
    C.position.copy(alvo).add(off); C.up.set(0, 1, 0); C.lookAt(alvo);
    PACOTES.forEach(o => { o.p.position.copy(CAMINHO.getPointAt((t * 0.035 + o.f) % 1)); });
    ANIM.forEach(f => f(t));
    R.render(S, C);
  };
  window.WRT = WRT;
})();
