/* Parte 3D da ilustração "planta": a MESMA casa da planta 2D (mesmas paredes, em metros), em Three.js e só com
   geometria feita em código (sem modelo pronto). Uma pessoa na suíte com o celular sem sinal, a câmera que vai ao
   celular, atravessa o corredor até o roteador e sobe até a vista de cima, que casa com a planta 2D (transição
   3D -> 2D). No fim, a volta: o celular com sinal cheio e a pessoa feliz. Tudo é função do tempo. */
(function () {
  'use strict';
  const P3 = { on: false };
  let R, S, C, W, H, ST, PL;               // PL = dados da planta 2D (paredes, escala na tela)
  let tetoMat, pessoa, rosto, celular, tela, telaCv, telaG, telaTex, roteadorLeds = [], paredesMat = [], estadoTela = '';
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const P = V(10.0, 0, 3.0);                // onde a pessoa está (na suíte), olhando para -x (para a porta)
  function std(c, o) { return new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.6, metalness: 0 }, o || {})); }
  function caixa(w, h, d, mat, x, y, z) { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); S.add(m); return m; }
  function ease(u) { u = Math.max(0, Math.min(1, u)); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; }
  function cilindroEntre(a, b, r, mat, pai) {
    const d = b.clone().sub(a), m = new THREE.Mesh(new THREE.CapsuleGeometry(r, Math.max(0.01, d.length() - 2 * r), 6, 12), mat);
    m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(V(0, 1, 0), d.normalize()); pai.add(m); return m;
  }
  function texPiso(c1, c2, tabuas) {
    const cv = document.createElement('canvas'); cv.width = 256; cv.height = 256; const g = cv.getContext('2d');
    g.fillStyle = c1; g.fillRect(0, 0, 256, 256);
    if (tabuas) for (let i = 0; i < 8; i++) { g.fillStyle = i % 2 ? c2 : c1; g.fillRect(0, i * 32, 256, 31); g.fillStyle = 'rgba(0,0,0,.12)'; g.fillRect(((i * 97) % 200) + 20, i * 32, 2, 31); }
    else { g.strokeStyle = c2; g.lineWidth = 3; for (let i = 0; i <= 4; i++) { g.beginPath(); g.moveTo(i * 64, 0); g.lineTo(i * 64, 256); g.moveTo(0, i * 64); g.lineTo(256, i * 64); g.stroke(); } }
    const t = new THREE.CanvasTexture(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; return t;
  }

  // ---------------------------------------------------------------- tela do celular (canvas atualizado por estado)
  function desenharTela(estado, t) {
    const g = telaG, w = 256, h = 512;
    const chave = estado + (estado === 'carregando' || estado === 'ok' ? Math.floor(t * 8) : '');
    if (chave === estadoTela) return; estadoTela = chave;
    g.fillStyle = '#f4f6fa'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#11151c'; g.font = 'bold 22px sans-serif'; g.textAlign = 'left'; g.fillText('14:31', 18, 34);
    // ícone de Wi-Fi: arcos acesos conforme as barras
    const barras = estado === 'ok' ? 4 : estado === 'sem' ? 0 : 1;
    for (let i = 0; i < 4; i++) {
      g.strokeStyle = i < barras ? '#11151c' : 'rgba(17,21,28,.18)'; g.lineWidth = 5;
      g.beginPath(); g.arc(214, 40, 6 + i * 8, -Math.PI * 0.75, -Math.PI * 0.25); g.stroke();
    }
    if (estado === 'sem') { g.strokeStyle = '#ff3b5c'; g.lineWidth = 5; g.beginPath(); g.moveTo(228, 14); g.lineTo(244, 30); g.moveTo(244, 14); g.lineTo(228, 30); g.stroke(); }
    if (estado === 'ok') {  // vídeo tocando + página carregada
      const gr = g.createLinearGradient(0, 70, 0, 250); gr.addColorStop(0, '#19c3ff'); gr.addColorStop(1, '#3dff9a');
      g.fillStyle = gr; g.fillRect(14, 70, w - 28, 170);
      g.fillStyle = 'rgba(255,255,255,.95)'; g.beginPath(); g.moveTo(112, 128); g.lineTo(112, 184); g.lineTo(156, 156); g.closePath(); g.fill();
      g.fillStyle = '#dfe4ec'; g.fillRect(14, 244, w - 28, 6); g.fillStyle = '#ff3b5c'; g.fillRect(14, 244, (w - 28) * ((t * 0.08) % 1), 6);
      g.fillStyle = '#11151c'; g.font = 'bold 22px sans-serif'; g.fillText('Wi-Fi forte', 18, 290);
      for (let i = 0; i < 5; i++) { g.fillStyle = '#dfe4ec'; g.fillRect(18, 310 + i * 36, w - 36 - (i % 2) * 50, 18); }
    } else if (estado === 'sem') {
      g.strokeStyle = '#b8c0cc'; g.lineWidth = 10; g.lineCap = 'round';
      for (let i = 0; i < 3; i++) { g.beginPath(); g.arc(128, 250, 26 + i * 26, -Math.PI * 0.78, -Math.PI * 0.22); g.stroke(); }
      g.strokeStyle = '#ff3b5c'; g.beginPath(); g.moveTo(90, 160); g.lineTo(166, 260); g.stroke();
      g.fillStyle = '#11151c'; g.font = 'bold 26px sans-serif'; g.textAlign = 'center'; g.fillText('Sem internet', 128, 310);
      g.fillStyle = '#6b7280'; g.font = '18px sans-serif'; g.fillText('Verifique a conexão', 128, 340);
    } else {  // carregando, com uma barra só
      g.textAlign = 'center';
      for (let i = 0; i < 4; i++) { g.fillStyle = '#e3e7ee'; g.fillRect(18, 80 + i * 40, w - 36, 22); }
      const a = t * 7; g.strokeStyle = '#19c3ff'; g.lineWidth = 9; g.lineCap = 'round';
      g.beginPath(); g.arc(128, 330, 34, a, a + Math.PI * 1.3); g.stroke();
      g.fillStyle = '#6b7280'; g.font = 'bold 20px sans-serif'; g.fillText('Carregando…', 128, 400);
    }
    telaTex.needsUpdate = true;
  }

  // ---------------------------------------------------------------- casa (mesmas coordenadas da planta 2D)
  function montarCasa() {
    const madeira = std(0xffffff, { map: texPiso('#b98b5e', '#a77b51', true), roughness: 0.7 }); madeira.map.repeat.set(3, 3);
    const piso = std(0xffffff, { map: texPiso('#dfe3e8', '#c3c9d2', false), roughness: 0.4 }); piso.map.repeat.set(4, 4);
    const chao = (x, z, w, d, m) => { const p = new THREE.Mesh(new THREE.PlaneGeometry(w, d), m); p.rotation.x = -Math.PI / 2; p.position.set(x + w / 2, 0, z + d / 2); S.add(p); };
    chao(0, 0, 4.5, 4.5, madeira); chao(7, 0, 5, 4.5, madeira); chao(0, 4.5, 7, 5.5, madeira); chao(4.5, 3, 2.5, 1.5, madeira);
    chao(4.5, 0, 2.5, 3, piso); chao(7, 4.5, 5, 5.5, piso);
    const alt = 2.6;
    PL.PAREDES.forEach(w => {
      const [x1, z1, x2, z2, mat] = w, L = Math.hypot(x2 - x1, z2 - z1), esp = mat === 'alv' ? 0.15 : 0.1;
      const m = std(mat === 'alv' ? 0xf1ede6 : 0xe8eef4, { roughness: 0.85, transparent: true });
      paredesMat.push(m);
      const p = new THREE.Mesh(new THREE.BoxGeometry(L + esp, alt, esp), m);
      p.position.set((x1 + x2) / 2, alt / 2, (z1 + z2) / 2); p.rotation.y = -Math.atan2(z2 - z1, x2 - x1); S.add(p);
    });
    // janela da suíte (luz natural entrando)
    const jan = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 1.3), new THREE.MeshBasicMaterial({ color: 0xe6f6ff })); jan.position.set(11.91, 1.55, 2.3); jan.rotation.y = -Math.PI / 2; S.add(jan);
    const caixilho = std(0xffffff); [[0, 0.68, 1.9, 0.06], [0, -0.68, 1.9, 0.06], [0, 0, 0.05, 1.4]].forEach(([dz, dy, w, h]) => { const b = new THREE.Mesh(new THREE.BoxGeometry(0.04, h, w), caixilho); b.position.set(11.9, 1.55 + dy, 2.3 + dz); S.add(b); });
    const cortina = std(0xd9cbb4, { roughness: 0.95 }); [1.15, 3.45].forEach(z => { const c = new THREE.Mesh(new THREE.BoxGeometry(0.05, 2.0, 0.45), cortina); c.position.set(11.86, 1.3, z); S.add(c); });
    const sol = new THREE.DirectionalLight(0xfff1dc, 2.4); sol.position.set(16, 4.5, 2.3); sol.target.position.set(9.5, 0.5, 2.6); S.add(sol, sol.target);
    // teto (some quando a câmera sobe para a vista de cima)
    tetoMat = std(0xf6f3ee, { roughness: 0.9, transparent: true, side: THREE.DoubleSide });
    const teto0 = new THREE.Mesh(new THREE.PlaneGeometry(12, 10), tetoMat); teto0.rotation.x = Math.PI / 2; teto0.position.set(6, 2.6, 5); S.add(teto0);
    // tapete, criado-mudo com abajur e quadro
    const tap = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 1.5), std(0x8a5a8c, { roughness: 1 })); tap.rotation.x = -Math.PI / 2; tap.position.set(9.6, 0.005, 3.2); S.add(tap);
    caixa(0.45, 0.5, 0.4, std(0x6b4a33), 11.45, 0.25, 0.45); caixa(0.12, 0.3, 0.12, std(0xf2e3c4), 11.45, 0.65, 0.45);
    const aba = new THREE.PointLight(0xffd59a, 3, 3, 2); aba.position.set(11.45, 0.95, 0.5); S.add(aba);
    caixa(0.9, 0.6, 0.03, std(0x19c3ff, { roughness: 0.4 }), 9.9, 1.75, 0.09);
    // móveis (as mesmas manchas da planta 2D)
    const cama = (x, z, w, d, cor) => { caixa(w, 0.35, d, std(0x6b4a33), x + w / 2, 0.18, z + d / 2); caixa(w - 0.1, 0.2, d - 0.1, std(0xf3f1ec), x + w / 2, 0.45, z + d / 2);
      caixa(w - 0.12, 0.08, d * 0.6, std(cor), x + w / 2, 0.58, z + d * 0.62); caixa(w * 0.35, 0.12, 0.35, std(0xffffff), x + w * 0.3, 0.6, z + 0.3); caixa(w * 0.35, 0.12, 0.35, std(0xffffff), x + w * 0.7, 0.6, z + 0.3); };
    cama(0.4, 1.0, 2.0, 2.4, 0x5b7bb3); cama(8.6, 0.6, 2.4, 2.0, 0x2f9e8f);
    caixa(3.0, 0.45, 1.1, std(0x3d4a5c), 2.5, 0.22, 8.95); caixa(3.0, 0.5, 0.25, std(0x3d4a5c), 2.5, 0.65, 9.4);  // sofá
    caixa(2.0, 0.5, 0.4, std(0x2a2f38), 1.6, 0.25, 4.85); caixa(1.6, 0.9, 0.06, std(0x0b0d12, { roughness: 0.2 }), 1.6, 1.1, 4.8);  // rack + TV
    caixa(3.8, 0.9, 0.8, std(0xe9e4da), 9.9, 0.45, 9.3);                      // bancada da cozinha
    caixa(0.9, 1.8, 0.8, std(0xc9ced6, { metalness: 0.7, roughness: 0.3 }), 11.35, 0.9, 5.2);  // geladeira
    caixa(0.7, 0.4, 0.5, std(0x2a2f38, { metalness: 0.5 }), 9.65, 1.1, 9.5);   // micro-ondas
    caixa(1.2, 0.85, 0.5, std(0xffffff), 5.5, 0.43, 0.65);                     // pia do banheiro
    caixa(0.04, 1.1, 1.6, std(0xbfe6ff, { metalness: 1, roughness: 0.05 }), 6.88, 1.45, 1.5);  // espelho
    // roteador no canto da sala, num aparador
    caixa(0.7, 0.6, 0.45, std(0x2a2f38), 0.7, 0.3, 9.45);
    const rot = caixa(0.42, 0.08, 0.3, std(0x10141b, { roughness: 0.3 }), 0.7, 0.64, 9.4);
    [-0.15, 0.15].forEach(dx => { const a = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.015, 0.32), std(0x10141b)); a.position.set(0.7 + dx, 0.82, 9.52); a.rotation.z = dx * 0.6; S.add(a); });
    for (let i = 0; i < 4; i++) { const l = caixa(0.025, 0.012, 0.012, new THREE.MeshBasicMaterial({ color: i ? 0x19c3ff : 0x3dff9a }), 0.58 + i * 0.07, 0.67, 9.25); roteadorLeds.push(l); }
    // ambiente
    S.add(new THREE.HemisphereLight(0xfff6e8, 0x3a3f4a, 1.2));
    const teto = new THREE.PointLight(0xffe2b8, 12, 9, 1.6); teto.position.set(9.5, 2.4, 2.3); S.add(teto);
    const sala = new THREE.PointLight(0xffe2b8, 14, 10, 1.6); sala.position.set(3.2, 2.4, 7.2); S.add(sala);
  }

  // ---------------------------------------------------------------- pessoa (bonequinho estilizado, olhando para -x)
  function montarPessoa() {
    pessoa = new THREE.Group(); pessoa.position.copy(P); S.add(pessoa);
    const pele = std(0xe0ac83, { roughness: 0.55 }), camisa = std(0x19a8d8, { roughness: 0.7 }), calca = std(0x2c3e66), cabelo = std(0x2a1d17, { roughness: 0.8 });
    [-0.1, 0.1].forEach(z => { const l = new THREE.Mesh(new THREE.CapsuleGeometry(0.075, 0.72, 6, 12), calca); l.position.set(0, 0.45, z); pessoa.add(l);
      const pe = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.07, 0.11), std(0xf4f4f4)); pe.position.set(-0.05, 0.04, z); pessoa.add(pe); });
    const tronco = new THREE.Mesh(new THREE.CapsuleGeometry(0.15, 0.4, 8, 16), camisa); tronco.position.set(0, 1.13, 0); tronco.scale.set(0.72, 1, 1.12); pessoa.add(tronco);
    const quadril = new THREE.Mesh(new THREE.CapsuleGeometry(0.12, 0.12, 6, 12), calca); quadril.position.set(0, 0.88, 0); quadril.rotation.x = Math.PI / 2; quadril.scale.set(0.62, 0.95, 0.72); pessoa.add(quadril);
    const pesc = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.055, 0.1), pele); pesc.position.set(-0.01, 1.43, 0); pessoa.add(pesc);
    rosto = new THREE.Group(); rosto.position.set(-0.02, 1.58, 0); pessoa.add(rosto);
    rosto.add(new THREE.Mesh(new THREE.SphereGeometry(0.13, 32, 24), pele));
    const cab = new THREE.Mesh(new THREE.SphereGeometry(0.138, 32, 24, 0, Math.PI * 2, 0, Math.PI * 0.55), cabelo); cab.position.set(0.02, 0.015, 0); cab.rotation.z = -0.35; rosto.add(cab);
    const olho = std(0x15110f, { roughness: 0.2 });
    rosto.userData.olhos = [-0.045, 0.045].map(z => { const o = new THREE.Mesh(new THREE.SphereGeometry(0.017, 12, 10), olho); o.position.set(-0.118, 0.02, z); rosto.add(o); return o; });
    rosto.userData.sobr = [-0.045, 0.045].map(z => { const s = new THREE.Mesh(new THREE.BoxGeometry(0.01, 0.012, 0.05), cabelo); s.position.set(-0.122, 0.062, z); rosto.add(s); return s; });
    const boca = new THREE.Mesh(new THREE.TorusGeometry(0.032, 0.008, 6, 16, Math.PI), std(0x7a2e2e)); boca.position.set(-0.124, -0.05, 0); boca.rotation.y = -Math.PI / 2; rosto.add(boca);
    rosto.userData.boca = boca;
    // braços segurando o celular na frente do peito
    const ombro = z => V(0, 1.33, z), cotovelo = z => V(-0.06, 1.08, z * 1.05), mao = z => V(-0.32, 1.19, z * 0.3);
    [-0.19, 0.19].forEach(z => { cilindroEntre(ombro(z), cotovelo(z), 0.048, camisa, pessoa); cilindroEntre(cotovelo(z), mao(z), 0.04, pele, pessoa); });
    celular = new THREE.Group(); pessoa.add(celular); celular.position.set(-0.36, 1.24, 0);
    celular.add(new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.16, 0.01), std(0x10141b, { roughness: 0.25, metalness: 0.4 })));
    telaCv = document.createElement('canvas'); telaCv.width = 256; telaCv.height = 512; telaG = telaCv.getContext('2d');
    telaTex = new THREE.CanvasTexture(telaCv); telaTex.colorSpace = THREE.SRGBColorSpace;
    tela = new THREE.Mesh(new THREE.PlaneGeometry(0.072, 0.146), new THREE.MeshBasicMaterial({ map: telaTex, toneMapped: false })); tela.position.z = 0.0056; celular.add(tela);
    S.updateMatrixWorld(true);
    const olhos = new THREE.Vector3(); rosto.getWorldPosition(olhos); olhos.x -= 0.1;
    celular.lookAt(olhos);  // a tela (+z) fica virada para o rosto
  }
  function humor(feliz, t) {
    const b = rosto.userData.boca;
    b.rotation.x = feliz ? Math.PI : 0;  // ∪ (sorriso) ou ∩ (frustração)
    b.position.y = feliz ? -0.038 : -0.055;
    rosto.userData.sobr.forEach((s, i) => { s.rotation.x = feliz ? 0 : (i ? -0.45 : 0.45); s.position.y = feliz ? 0.07 : 0.058; });
    rosto.rotation.z = feliz ? 0.05 * Math.sin(t * 3) : -0.25;  // cabeça baixa olhando o celular / leve balanço feliz
    pessoa.position.y = feliz ? Math.max(0, 0.025 * Math.sin(t * 6)) : 0;
  }

  // ---------------------------------------------------------------- câmera
  function telaMundo() {
    const p = new THREE.Vector3(), n = new THREE.Vector3(0, 0, 1), q = new THREE.Quaternion();
    tela.getWorldPosition(p); tela.getWorldQuaternion(q); n.applyQuaternion(q);
    return { p, n };
  }
  const FRENTE = () => ({ pos: V(P.x - 2.35, 1.5, P.z + 0.75), alvo: V(P.x + 0.1, 1.18, P.z - 0.15) });
  const PERTO = () => { const { p, n } = telaMundo(); return { pos: p.clone().add(n.clone().multiplyScalar(0.27)), alvo: p.clone() }; };
  const LADO = () => ({ pos: V(P.x - 0.75, 1.62, P.z + 0.95), alvo: V(P.x - 0.33, 1.22, P.z) });
  const CORREDOR = [  // da suíte até o roteador na sala
    [V(8.4, 1.55, 3.8), V(6.5, 1.45, 3.95)], [V(7.0, 1.55, 3.95), V(5.0, 1.45, 4.2)], [V(5.75, 1.6, 4.1), V(4.0, 1.3, 6.2)],
    [V(4.6, 1.6, 5.6), V(1.5, 1.0, 8.6)], [V(3.1, 1.5, 7.3), V(0.7, 0.7, 9.4)]];
  function topo() {  // câmera de cima que casa exatamente com a planta 2D (mesma escala e posição na tela)
    const fov = C.fov * Math.PI / 180, h = (H / PL.R.s) / (2 * Math.tan(fov / 2));
    const cx = (W / 2 - PL.R.x) / PL.R.s, cz = (H / 2 - PL.R.y) / PL.R.s;
    return { pos: V(cx, h, cz + 0.0001), alvo: V(cx, 0, cz) };
  }
  function olhar(pos, alvo, up) { C.position.copy(pos); C.up.copy(up || V(0, 1, 0)); C.lookAt(alvo); }
  function entre(a, b, u) { return { pos: a.pos.clone().lerp(b.pos, u), alvo: a.alvo.clone().lerp(b.alvo, u) }; }
  function caminho(pts, u) {
    const f = Math.max(0, Math.min(0.9999, u)) * (pts.length - 1), i = Math.floor(f), k = ease(f - i);
    return { pos: pts[i][0].clone().lerp(pts[i + 1][0], k), alvo: pts[i][1].clone().lerp(pts[i + 1][1], k) };
  }

  P3.init = function (box, st, pl) {
    ST = st; PL = pl; W = st.w; H = st.h;
    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    R.setPixelRatio(st.scale3d || 0.75); R.setSize(W, H, false);
    R.outputColorSpace = THREE.SRGBColorSpace; R.toneMapping = THREE.ACESFilmicToneMapping; R.toneMappingExposure = 1.05;
    Object.assign(R.domElement.style, { position: 'absolute', left: '0', top: '0', width: W + 'px', height: H + 'px' });
    box.appendChild(R.domElement);
    S = new THREE.Scene(); S.background = new THREE.Color(0x0b0f16);
    if (window.THREEX && THREEX.RoomEnvironment) { const pm = new THREE.PMREMGenerator(R); S.environment = pm.fromScene(new THREEX.RoomEnvironment(R), 0.04).texture; pm.dispose(); }
    C = new THREE.PerspectiveCamera(H > W ? 50 : 38, W / H, 0.03, 200);
    montarCasa(); montarPessoa();
    P3.cv = R.domElement; P3.on = true;
  };

  /* passo: quarto_problema | quarto_fraco | quarto_sem_sinal | corredor | transicao | quarto_resolvido */
  P3.render = function (passo, t, lt, d) {
    const u = lt / Math.max(0.5, d);
    let cam, telaEstado = 'carregando', feliz = false, paredes = 1;
    if (passo === 'quarto_problema') { const f = FRENTE(); cam = entre({ pos: f.pos.clone().add(V(-0.5, 0.1, 0.25)), alvo: f.alvo }, f, ease(u)); }
    else if (passo === 'quarto_fraco') { cam = u < 0.5 ? entre(FRENTE(), LADO(), ease(u / 0.5)) : entre(LADO(), PERTO(), ease((u - 0.5) / 0.5)); }
    else if (passo === 'quarto_sem_sinal') { telaEstado = lt < 0.5 ? 'carregando' : 'sem'; cam = u < 0.45 ? PERTO() : entre(PERTO(), FRENTE(), ease((u - 0.45) / 0.55)); }
    else if (passo === 'corredor') { telaEstado = 'sem'; cam = caminho(CORREDOR, ease(u)); }
    else if (passo === 'transicao') {
      telaEstado = 'sem';
      const a = caminho(CORREDOR, 1), b = topo(), k = ease(u / 0.85);
      const pos = a.pos.clone().lerp(b.pos, k); pos.y = a.pos.y + (b.pos.y - a.pos.y) * Math.pow(k, 1.6);
      // orientação: da vista do corredor para a vista de cima (slerp), sem girar a planta
      olhar(a.pos, a.alvo); const q0 = C.quaternion.clone();
      olhar(b.pos, b.alvo, V(0, 0, -1)); const q1 = C.quaternion.clone();
      C.position.copy(pos); C.quaternion.copy(q0).slerp(q1, k);
      paredes = 1 - 0.85 * ease((u - 0.25) / 0.5);
    }
    else if (passo === 'quarto_resolvido') { telaEstado = 'ok'; feliz = lt > 0.9; cam = u < 0.3 ? PERTO() : entre(PERTO(), FRENTE(), ease((u - 0.3) / 0.6)); }
    else { const f = FRENTE(); cam = f; }
    paredesMat.forEach(m => { m.opacity = paredes; m.depthWrite = paredes > 0.95; });
    const teto = passo === 'transicao' ? 1 - ease((u - 0.04) / 0.2) : 1;  // "o teto desaparece"
    tetoMat.opacity = teto; tetoMat.visible = teto > 0.01; tetoMat.depthWrite = teto > 0.95;
    humor(feliz, t);
    roteadorLeds.forEach((l, i) => { l.visible = Math.sin(t * (9 + i * 3) + i) > -0.3; });
    desenharTela(telaEstado, t);
    if (cam) olhar(cam.pos, cam.alvo);
    R.render(S, C);
  };
  P3.PASSOS = ['quarto_problema', 'quarto_fraco', 'quarto_sem_sinal', 'corredor', 'transicao', 'quarto_resolvido'];
  P3.P = P;
  window.WPL3 = P3;
})();
