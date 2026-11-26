/* Cena própria do episódio #02 da série "Redes na Prática" (atenuação e orçamento óptico no GPON).
   Modelos feitos só para este vídeo, em código (Three.js): OLT com módulo SFP C+, fibra em corte com a luz refletindo
   no núcleo e perdendo força por km, bobina de fibra, conector SC/APC encaixando, emenda por fusão com arco elétrico,
   chip splitter PLC 1:8 com a luz se dividindo, ONU e power meter. Uma bancada escura com as cores da série; a câmera
   voa de uma peça para a outra (params.peca) e os quadros técnicos 2D aparecem por cima. */
(function () {
  'use strict';
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  let R, S, C, W, H, ST, PORT, GLOW, ACC, ACC2;
  const ANIM = [], P = {};
  function ease(u) { u = Math.max(0, Math.min(1, u)); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; }
  const phys = o => new THREE.MeshPhysicalMaterial(Object.assign({ roughness: 0.35, metalness: 0 }, o));
  const std = (c, o) => new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.45, metalness: 0.1 }, o || {}));
  const bas = (c, o) => new THREE.MeshBasicMaterial(Object.assign({ color: c }, o || {}));
  function RB(w, h, d, r) { return (window.THREEX && THREEX.RoundedBoxGeometry) ? new THREEX.RoundedBoxGeometry(w, h, d, 4, r) : new THREE.BoxGeometry(w, h, d); }
  function m(geo, mat, x, y, z, pai) { const o = new THREE.Mesh(geo, mat); o.position.set(x || 0, y || 0, z || 0); (pai || S).add(o); return o; }
  function glow(cor, t, op) { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: cor, transparent: true, opacity: op == null ? 1 : op, blending: THREE.AdditiveBlending, depthWrite: false })); s.scale.set(t, t, 1); return s; }
  function tex(w, h, f) { const c = document.createElement('canvas'); c.width = w; c.height = h; f(c.getContext('2d'), w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; }
  function etiqueta() { return null; }  // as placas 3D cobriam o título; os números ficam no quadro 2D
  function _etiquetaAntiga(txt, cor, x, y, z, larg) {
    const t = tex(512, 128, (g, w, h) => { g.fillStyle = 'rgba(8,11,16,.9)'; g.beginPath(); g.roundRect(4, 4, w - 8, h - 8, 26); g.fill(); g.strokeStyle = cor; g.lineWidth = 6; g.stroke();
      g.fillStyle = cor; g.font = '800 58px "DejaVu Sans Mono", monospace'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, w / 2, h / 2 + 2); });
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false })); s.scale.set(larg || 1.6, (larg || 1.6) / 4, 1); s.position.set(x, y, z); S.add(s); return s;
  }
  function tubo(pts, r, mat, seg) { const c = new THREE.CatmullRomCurve3(pts); const o = m(new THREE.TubeGeometry(c, seg || 120, r, 12, false), mat); o.userData.curva = c; return o; }

  // ---------------------------------------------------------------- peças
  function bancada() {
    const piso = tex(1024, 1024, (g, w, h) => { g.fillStyle = '#0a0e14'; g.fillRect(0, 0, w, h); g.strokeStyle = 'rgba(25,195,255,.08)'; g.lineWidth = 2; for (let i = 0; i <= 16; i++) { g.beginPath(); g.moveTo(i * 64, 0); g.lineTo(i * 64, h); g.moveTo(0, i * 64); g.lineTo(w, i * 64); g.stroke(); } });
    piso.wrapS = piso.wrapT = THREE.RepeatWrapping; piso.repeat.set(12, 4);
    const chao = m(new THREE.PlaneGeometry(90, 30), std(0xffffff, { map: piso, roughness: 0.22, metalness: 0.65 }), 20, 0, 0); chao.rotation.x = -Math.PI / 2;
    // faixa de luz no fundo (horizonte de estúdio)
    const fundo = m(new THREE.PlaneGeometry(90, 14), bas(0xffffff, { map: tex(16, 256, (g, w, h) => { const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#05070b'); gr.addColorStop(0.75, '#0b2a3a'); gr.addColorStop(1, '#05070b'); g.fillStyle = gr; g.fillRect(0, 0, w, h); }) }), 20, 7, -9);
  }
  function olt() {  // chassi com portas PON e um módulo SFP C+ entrando
    const g = new THREE.Group(); g.position.set(0, 2.55, 0.1); g.scale.setScalar(0.48); S.add(g);
    const metal = phys({ color: 0x2a313c, metalness: 1, roughness: 0.32, clearcoat: 0.6 });
    m(RB(4.4, 1.6, 2.4, 0.08), metal, 0, 0.8, 0, g);
    m(RB(4.3, 0.06, 0.04, 0.01), bas(ACC), 0, 1.55, 1.21, g);
    const face = tex(1024, 360, (c, w, h) => { c.fillStyle = '#151a21'; c.fillRect(0, 0, w, h); c.fillStyle = '#9aa6b5'; c.font = '700 30px Figtree, sans-serif'; c.fillText('GPON OLT · PON 1-16', 30, 44);
      for (let i = 0; i < 16; i++) { const x = 40 + (i % 8) * 120, y = 80 + Math.floor(i / 8) * 130; c.fillStyle = '#05070a'; c.fillRect(x, y, 90, 70); c.strokeStyle = '#6f7b8a'; c.lineWidth = 4; c.strokeRect(x, y, 90, 70); c.fillStyle = '#9aa6b5'; c.font = '600 22px monospace'; c.fillText('PON ' + (i + 1), x + 6, y + 100); } });
    m(new THREE.PlaneGeometry(4.2, 1.48), bas(0xffffff, { map: face }), 0, 0.82, 1.205, g);
    const leds = []; for (let i = 0; i < 16; i++) { const l = m(new THREE.SphereGeometry(0.025, 10, 8), bas(i === 2 ? 0x3dff9a : 0x19c3ff), -1.87 + (i % 8) * 0.49, 1.18 - Math.floor(i / 8) * 0.53, 1.22, g); leds.push(l); }
    // módulo SFP (corpo metálico, alça verde = C+) deslizando para a porta 3
    const sfp = new THREE.Group(); g.add(sfp);
    m(RB(0.34, 0.27, 1.3, 0.03), phys({ color: 0xc8ced6, metalness: 1, roughness: 0.18 }), 0, 0, 0, sfp);
    const alca = m(new THREE.TorusGeometry(0.17, 0.035, 10, 24, Math.PI), std(0x3dff9a, { roughness: 0.35 }), 0, 0, 0.7, sfp); alca.rotation.z = Math.PI;
    const rot = tex(256, 128, (c, w, h) => { c.fillStyle = '#e9edf3'; c.fillRect(0, 0, w, h); c.fillStyle = '#10141b'; c.font = '900 46px Figtree'; c.fillText('GPON C+', 18, 56); c.font = '700 30px monospace'; c.fillText('+5 dBm 1490', 18, 104); });
    const lab = m(new THREE.PlaneGeometry(0.3, 0.6), bas(0xffffff, { map: rot }), 0, 0.137, 0.1, sfp); lab.rotation.x = -Math.PI / 2; lab.rotation.z = Math.PI / 2;
    const luz = glow(ACC2, 0.9); g.add(luz);
    const xp = -1.87 + 2 * 0.49, yp = 1.18;
    ANIM.push((t, ativo, lt) => {
      leds.forEach((l, i) => { l.visible = Math.sin(t * (6 + i) + i) > -0.5; });
      const u = ativo === 'olt' ? ease((lt - 0.4) / 1.4) : 1;
      sfp.position.set(xp, yp, 1.85 - 0.75 * u); luz.position.set(xp, yp, 2.55); luz.material.opacity = 0.4 + 0.6 * u * (0.7 + 0.3 * Math.sin(t * 20));
    });
    P.olt = { alvo: V(0, 2.95, 0.6), cam: V(-1.4, 0.7, 3.6) };
  }
  function fibraCorte() {  // cabo descascado em degraus: capa amarela, revestimento branco e o vidro com o núcleo aceso
    const g = new THREE.Group(); g.position.set(10, 1.5, 0); S.add(g);
    const eixo = o => { o.rotation.z = Math.PI / 2; return o; };
    eixo(m(new THREE.CylinderGeometry(0.72, 0.72, 3.2, 64), phys({ color: 0xf2c230, roughness: 0.45, clearcoat: 0.4 }), -3.0, 0, 0, g));
    eixo(m(new THREE.CylinderGeometry(0.725, 0.725, 0.04, 64), std(0xd9a91c), -1.4, 0, 0, g));
    eixo(m(new THREE.CylinderGeometry(0.4, 0.4, 2.2, 48), phys({ color: 0xf4f6fa, roughness: 0.35, clearcoat: 0.6 }), -0.3, 0, 0, g));
    eixo(m(new THREE.CylinderGeometry(0.26, 0.26, 4.2, 48), phys({ color: 0xbfe9ff, transmission: 0.6, thickness: 0.4, ior: 1.46, roughness: 0.05, clearcoat: 1, transparent: true, opacity: 0.5, emissive: 0x0a3a55, emissiveIntensity: 0.6, depthWrite: false }), 2.9, 0, 0, g));
    eixo(m(new THREE.CylinderGeometry(0.075, 0.075, 4.3, 24), std(0x19c3ff, { emissive: 0x19c3ff, emissiveIntensity: 1.2 }), 2.9, 0, 0, g));
    const ponta = m(new THREE.SphereGeometry(0.075, 16, 12), bas(0x9ff0ff), 5.05, 0, 0, g);
    // raio de luz refletindo entre núcleo e casca, perdendo força ao avançar
    const n = 22, raio = [];
    for (let i = 0; i < n; i++) {
      const x0 = 0.8 + i * 4.2 / n, x1 = x0 + 4.2 / n, y0 = (i % 2 ? 1 : -1) * 0.065, d = V(x1 - x0, -2 * y0, 0);
      const seg = m(new THREE.CylinderGeometry(0.022, 0.022, d.length(), 6), bas(0xffffff, { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }), (x0 + x1) / 2, 0, 0, g);
      seg.quaternion.setFromUnitVectors(V(0, 1, 0), d.normalize()); seg.renderOrder = 5; raio.push(seg);
    }
    const pulsos = [0, 1, 2].map(() => { const s0 = glow(ACC2, 0.35); g.add(s0); return s0; });
    const saida = glow(0x9ff0ff, 0.9); saida.position.set(5.1, 0, 0); g.add(saida);
    ANIM.push(t => {
      raio.forEach((s0, i) => { s0.material.opacity = 0.95 * Math.exp(-i / n * 1.4) * (0.7 + 0.3 * Math.sin(t * 8 - i * 0.6)); });
      pulsos.forEach((s0, k) => { const u = ((t * 0.3 + k / 3) % 1); s0.position.set(0.8 + u * 4.2, 0, 0); s0.material.opacity = Math.exp(-u * 1.4); });
      saida.material.opacity = 0.35 + 0.15 * Math.sin(t * 6);
    });
    P.fibra = { alvo: V(10.6, 1.5, 0), cam: V(-2.0, 1.3, 6.2) };
    P.fibra_perto = { alvo: V(13.0, 1.5, 0), cam: V(-1.2, 0.7, 2.9) };
  }
  function bobina() {  // bobina (carretel) de cabo óptico: abas de tábuas, cubo metálico, cabo preto enrolado em camadas
    const g = new THREE.Group(); g.position.set(17.5, 0, -0.4); g.rotation.y = 0.55; S.add(g);
    const R0 = 1.55, ESP = 0.11, LARG = 1.25;
    // aba: tábuas de pinus com veios, furos de manuseio e borda escurecida
    const madeira = tex(1024, 1024, (c, w, h) => {
      for (let i = 0; i < 8; i++) { const x = i * w / 8; const tom = 175 + (i * 37) % 35;
        c.fillStyle = `rgb(${tom},${Math.round(tom * 0.74)},${Math.round(tom * 0.48)})`; c.fillRect(x, 0, w / 8, h);
        for (let k = 0; k < 26; k++) { c.strokeStyle = `rgba(90,55,25,${0.08 + (k % 4) * 0.04})`; c.lineWidth = 1 + (k % 3); c.beginPath(); const xx = x + 6 + k * 4.6;
          c.moveTo(xx, 0); for (let y = 0; y <= h; y += 64) c.lineTo(xx + Math.sin(y / 90 + k) * 3, y); c.stroke(); }
        c.fillStyle = 'rgba(40,24,10,.55)'; c.fillRect(x, 0, 3, h); }
      c.fillStyle = 'rgba(30,18,8,.9)'; [[0.18, 0.18], [0.82, 0.18], [0.82, 0.82], [0.18, 0.82]].forEach(([a, b]) => { c.beginPath(); c.arc(a * w, b * h, 36, 0, Math.PI * 2); c.fill(); });
      const r = c.createRadialGradient(w / 2, h / 2, w * 0.3, w / 2, h / 2, w * 0.5); r.addColorStop(0, 'rgba(0,0,0,0)'); r.addColorStop(1, 'rgba(40,22,8,.45)'); c.fillStyle = r; c.fillRect(0, 0, w, h);
      c.save(); c.translate(w / 2, h / 2); c.rotate(-Math.PI / 2); c.fillStyle = '#20242a'; c.font = '900 64px Figtree'; c.textAlign = 'center'; c.fillText('CABO ÓPTICO', 0, -h * 0.25); c.font = '700 46px monospace'; c.fillText('12 FO · AS-80 · 4.000 m', 0, -h * 0.18); c.restore();
    });
    const matAba = std(0xffffff, { map: madeira, roughness: 0.85, metalness: 0 });
    const matBorda = std(0x9a7448, { roughness: 0.9, metalness: 0 });
    [-LARG / 2 - ESP / 2, LARG / 2 + ESP / 2].forEach(z => {
      const aba = m(new THREE.CylinderGeometry(R0, R0, ESP, 96), [matBorda, matAba, matAba], 0, R0, z, g); aba.rotation.x = Math.PI / 2;
      const aro = m(new THREE.TorusGeometry(R0 - 0.02, 0.025, 8, 96), phys({ color: 0x6d737c, metalness: 1, roughness: 0.4 }), 0, R0, z + Math.sign(z) * ESP / 2, g);
      const cubo = m(new THREE.CylinderGeometry(0.3, 0.3, 0.05, 48), phys({ color: 0x8a919b, metalness: 1, roughness: 0.3 }), 0, R0, z + Math.sign(z) * (ESP / 2 + 0.02), g); cubo.rotation.x = Math.PI / 2;
      const furo = m(new THREE.CylinderGeometry(0.1, 0.1, 0.06, 32), std(0x0b0d10), 0, R0, z + Math.sign(z) * (ESP / 2 + 0.03), g); furo.rotation.x = Math.PI / 2;
      for (let k = 0; k < 8; k++) { const a = k / 8 * Math.PI * 2; const p = m(new THREE.CylinderGeometry(0.035, 0.035, 0.05, 6), phys({ color: 0xb8bec6, metalness: 1, roughness: 0.25 }), Math.cos(a) * 0.45, R0 + Math.sin(a) * 0.45, z + Math.sign(z) * (ESP / 2 + 0.03), g); p.rotation.x = Math.PI / 2; }
    });
    const tambor = m(new THREE.CylinderGeometry(0.72, 0.72, LARG, 64), std(0x8a6a44, { roughness: 0.85, metalness: 0 }), 0, R0, 0, g); tambor.rotation.x = Math.PI / 2;
    // cabo enrolado: hélice em camadas, indo e voltando de uma aba à outra
    const rc = 0.05, pts = [], camadas = 6, voltas = Math.floor(LARG / (rc * 2.05));
    for (let L = 0; L < camadas; L++) {
      const raio = 0.72 + rc + L * rc * 1.75;
      for (let i = 0; i <= voltas * 24; i++) {
        const u = i / (voltas * 24), a = u * voltas * Math.PI * 2, z = (L % 2 ? 1 : -1) * (LARG / 2 - rc * 1.1) * (1 - 2 * u);
        pts.push(V(Math.cos(a) * raio, R0 + Math.sin(a) * raio, z));
      }
    }
    const ult = pts[pts.length - 1];
    [V(ult.x + 0.4, ult.y - 0.6, ult.z), V(ult.x + 0.9, 0.35, ult.z + 0.2), V(ult.x + 1.6, rc, ult.z + 0.8), V(ult.x + 3.2, rc, ult.z + 1.3)].forEach(p => pts.push(p));
    const curva = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
    m(new THREE.TubeGeometry(curva, pts.length * 2, rc, 10, false), phys({ color: 0x15181c, roughness: 0.38, clearcoat: 0.5, clearcoatRoughness: 0.4 }), 0, 0, 0, g);
    // calço de madeira no chão (a bobina não rola)
    [-0.9, 0.9].forEach(x => m(RB(0.5, 0.22, LARG + 0.5, 0.03), matBorda, x * 1.2, 0.11, 0, g));
    ANIM.push(() => {});
    P.bobina = { alvo: V(17.5, 1.4, -0.4), cam: V(-4.2, 1.6, 7.8) };
  }
  function conectorSC(cor) {  // SC: corpo, ferrolho cerâmico, capa traseira
    const g = new THREE.Group();
    m(RB(0.5, 0.5, 1.1, 0.06), std(cor, { roughness: 0.3 }), 0, 0, 0, g);
    m(RB(0.38, 0.38, 0.5, 0.04), std(0xe8edf2, { roughness: 0.35 }), 0, 0, -0.65, g);
    const fer = m(new THREE.CylinderGeometry(0.06, 0.06, 0.5, 32), phys({ color: 0xf6f3ea, roughness: 0.25, clearcoat: 1 }), 0, 0, 0.75, g); fer.rotation.x = Math.PI / 2;
    const ponta = m(new THREE.CylinderGeometry(0.061, 0.061, 0.02, 32), bas(0x19c3ff), 0, 0, 1.0, g); ponta.rotation.x = Math.PI / 2 + 0.14;  // ponta em 8° (APC)
    const bota = m(new THREE.LatheGeometry([0.2, 0.19, 0.16, 0.12, 0.09].map((r, i) => new THREE.Vector2(r, i * 0.3)), 32), std(cor, { roughness: 0.5 }), 0, 0, -0.9, g); bota.rotation.x = -Math.PI / 2;
    const cabo = m(new THREE.CylinderGeometry(0.07, 0.07, 3, 16), std(0xf2c230), 0, 0, -3.4, g); cabo.rotation.x = Math.PI / 2;
    return g;
  }
  function conectores() {  // SC/APC verde encaixando no adaptador
    const g = new THREE.Group(); g.position.set(5, 1.1, 0.4); g.rotation.y = Math.PI / 2; S.add(g);
    const ad = m(RB(0.62, 0.62, 0.9, 0.05), std(0x2fae5b, { roughness: 0.35 }), 0, 0, 0, g);
    const flange = m(RB(1.1, 0.12, 0.2, 0.03), std(0x2fae5b), 0, 0.37, 0, g);
    const a = conectorSC(0x2fae5b), b = conectorSC(0x2fae5b); b.rotation.y = Math.PI; g.add(a, b);
    const brilho = glow(0x3dff9a, 0.8, 0); g.add(brilho);
    etiqueta('SC/APC  −0,3 a −0,5 dB', '#3dff9a', 5, 2.35, 0.4, 2.4);
    ANIM.push((t, ativo, lt) => {
      const u = ativo === 'conector' ? ease((lt - 0.3) / 1.2) : 1;
      a.position.z = -1.05 - 1.3 * (1 - u); b.position.z = 1.05 + 1.3 * (1 - u);
      brilho.material.opacity = u > 0.98 ? 0.6 + 0.4 * Math.sin(t * 10) : 0;
    });
    P.conector = { alvo: V(5, 1.1, 0.4), cam: V(-2.6, 1.4, 4.6) };
  }
  function fusao() {  // máquina de fusão aberta: sulcos em V, eletrodos e arco elétrico; depois o tubete
    const g = new THREE.Group(); g.position.set(23.5, 0, 0.3); S.add(g);
    m(RB(3.2, 0.9, 2.2, 0.15), std(0x2d333c, { roughness: 0.6 }), 0, 0.45, 0, g);
    m(RB(2.6, 0.12, 1.2, 0.05), phys({ color: 0x8c96a3, metalness: 1, roughness: 0.25 }), 0, 0.96, 0, g);
    [-0.7, 0.7].forEach(x => m(RB(0.7, 0.16, 0.35, 0.04), phys({ color: 0xb9c2cd, metalness: 1, roughness: 0.2 }), x, 1.08, 0, g));
    const vidro = phys({ color: 0xdff3ff, transmission: 1, roughness: 0.02, thickness: 0.05, ior: 1.46 });
    const f1 = m(new THREE.CylinderGeometry(0.018, 0.018, 1.3, 12), vidro, 0, 1.2, 0, g); f1.rotation.z = Math.PI / 2;
    const f2 = m(new THREE.CylinderGeometry(0.018, 0.018, 1.3, 12), vidro, 0, 1.2, 0, g); f2.rotation.z = Math.PI / 2;
    [[0, 1.7, 0.0, Math.PI], [0, 0.72, 0, 0]].forEach(([x, y, z, r]) => { const e = m(new THREE.ConeGeometry(0.05, 0.5, 16), phys({ color: 0xd9dde3, metalness: 1, roughness: 0.15 }), x, y, z, g); e.rotation.z = r; });
    const arco = glow(0x9fdcff, 0.8, 0); arco.position.set(0, 1.2, 0); g.add(arco);
    const raio = m(new THREE.CylinderGeometry(0.01, 0.01, 0.55, 6), bas(0xffffff, { transparent: true }), 0, 1.2, 0, g);
    const tubete = m(new THREE.CylinderGeometry(0.08, 0.08, 0.9, 24), phys({ color: 0xffffff, transmission: 0.9, roughness: 0.1, thickness: 0.1, transparent: true, opacity: 0.7 }), 0, 1.2, 0, g); tubete.rotation.z = Math.PI / 2;
    etiqueta('FUSÃO  −0,05 a −0,1 dB', '#7fdcff', 23.5, 2.7, 0.3, 2.4);
    ANIM.push((t, ativo, lt) => {
      const fase = ativo === 'fusao' ? lt : 9;
      const aprox = ease(fase / 1.1);
      f1.position.x = -0.65 - 0.5 * (1 - aprox) - 0.01; f2.position.x = 0.65 + 0.5 * (1 - aprox) + 0.01;
      const arcoOn = fase > 1.1 && fase < 2.0;
      arco.material.opacity = arcoOn ? 0.6 + 0.4 * Math.abs(Math.sin(t * 60)) : 0;
      raio.visible = arcoOn && Math.sin(t * 90) > 0; raio.rotation.x = Math.sin(t * 50) * 0.3;
      const tub = ease((fase - 2.1) / 1.0); tubete.visible = fase > 2.0; tubete.position.x = -1.6 + 1.6 * tub; tubete.material.opacity = 0.7 * tub;
    });
    P.fusao = { alvo: V(23.5, 1.15, 0.3), cam: V(-1.8, 1.4, 3.4) };
  }
  function splitter() {  // chip PLC: bloco de vidro com a árvore de guias de onda 1 -> 8
    const g = new THREE.Group(); g.position.set(33.6, 0.9, 1.4); S.add(g);
    m(RB(3.6, 0.2, 1.8, 0.05), phys({ color: 0x9aa4b1, metalness: 1, roughness: 0.3 }), 0, -0.2, 0, g);
    m(RB(3.0, 0.4, 1.4, 0.04), phys({ color: 0xcfefff, transmission: 0.5, roughness: 0.08, thickness: 0.4, ior: 1.46, transparent: true, opacity: 0.32, emissive: 0x06202e, emissiveIntensity: 0.5, depthWrite: false }), 0, 0.1, 0, g);
    const guias = [], luzes = [];
    for (let k = 0; k < 8; k++) {
      const zf = -0.6 + k * (1.2 / 7), z2 = zf * 0.5, z1 = zf * 0.2;
      const c = new THREE.CatmullRomCurve3([V(-1.4, 0.12, 0), V(-0.6, 0.12, z1), V(0.2, 0.12, z2), V(1.4, 0.12, zf)]);
      const o = m(new THREE.TubeGeometry(c, 60, 0.03, 8, false), bas(0x3dd6ff, { transparent: true, opacity: 1, blending: THREE.AdditiveBlending, depthWrite: false }), 0, 0, 0, g); o.renderOrder = 5; guias.push(o);
      const s = glow(0x3dff9a, 0.32); g.add(s); luzes.push({ s, c });
      const saida = new THREE.CatmullRomCurve3([V(1.4, 0.12, zf), V(2.4, 0.1, zf * 1.6), V(3.6, 0.0, zf * 2.4)]);
      m(new THREE.TubeGeometry(saida, 30, 0.03, 8, false), std(0xf2c230), 0, 0, 0, g);
    }
    m(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([V(-3.6, 0, 0), V(-2.4, 0.1, 0), V(-1.4, 0.12, 0)]), 30, 0.035, 8, false), std(0xf2c230), 0, 0, 0, g);
    const entrada = glow(0x3dff9a, 0.7); g.add(entrada);
    etiqueta('1:8  −10,5 dB', '#3dff9a', 29.5, 2.2, 0.2, 1.9);
    ANIM.push(t => {
      const u = (t * 0.45) % 1;
      entrada.position.set(-3.6 + 2.2 * Math.min(1, u * 2), 0.1, 0); entrada.material.opacity = u < 0.5 ? 1 : 0;
      luzes.forEach(o => { const k = Math.max(0, (u - 0.5) * 2); o.s.position.copy(o.c.getPoint(Math.min(0.999, k))); o.s.material.opacity = u >= 0.5 ? 0.55 : 0; });  // cada saída leva 1/8 da luz
    });
    P.splitter = { alvo: V(33.6, 1.0, 1.4), cam: V(-1.6, 2.6, 4.4) };
  }
  function onu() {
    const g = new THREE.Group(); g.position.set(44, 0, 0.2); S.add(g);
    const corpo = m(RB(2.4, 0.5, 1.7, 0.2), phys({ color: 0xf4f6fa, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.15 }), 0, 0.55, 0, g);
    m(RB(2.2, 0.06, 1.5, 0.05), std(0xdfe4ec), 0, 0.27, 0, g);
    const nomes = ['PWR', 'PON', 'LOS', 'LAN', 'WLAN'], cores = [0x30d158, 0x30d158, 0xff3b5c, 0x30d158, 0x30d158], leds = [];
    nomes.forEach((n, i) => { const l = m(new THREE.SphereGeometry(0.04, 12, 10), bas(cores[i]), -0.8 + i * 0.4, 0.62, 0.86, g); leds.push(l); });
    m(new THREE.PlaneGeometry(2.0, 0.16), bas(0xffffff, { map: tex(512, 48, (c, w, h) => { c.fillStyle = '#f4f6fa'; c.fillRect(0, 0, w, h); c.fillStyle = '#8a93a0'; c.font = '700 26px Figtree'; nomes.forEach((n, i) => { c.textAlign = 'center'; c.fillText(n, 50 + i * 103, 34); }); }) }), 0, 0.47, 0.86, g);
    
    ANIM.push(t => { leds[2].visible = false; leds[1].visible = true; leds[3].visible = Math.sin(t * 13) > -0.3; leds[4].visible = Math.sin(t * 9 + 1) > -0.3; });
    P.onu = { alvo: V(44, 0.6, 0.2), cam: V(-2.6, 2.2, 5.6) };
  }
  function medidor() {  // power meter de mão mostrando a leitura
    const g = new THREE.Group(); g.position.set(48, 0.9, 0.6); g.rotation.set(-0.5, -0.35, 0); S.add(g);
    m(RB(1.2, 2.2, 0.38, 0.18), std(0xff7a1a, { roughness: 0.55 }), 0, 0, 0, g);
    m(RB(1.0, 2.0, 0.4, 0.14), std(0x1b2027, { roughness: 0.6 }), 0, 0, 0.02, g);
    const tela = tex(512, 320, (c, w, h) => { c.fillStyle = '#c9f5d8'; c.fillRect(0, 0, w, h); c.fillStyle = '#0b2a17'; c.font = '700 40px monospace'; c.fillText('1490 nm', 24, 60); c.font = '900 120px monospace'; c.fillText('-21.1', 24, 200); c.font = '700 44px monospace'; c.fillText('dBm', 360, 200); c.font = '700 32px monospace'; c.fillText('GPON  OK', 24, 280); });
    m(new THREE.PlaneGeometry(0.82, 0.52), bas(0xffffff, { map: tela }), 0, 0.42, 0.225, g);
    for (let i = 0; i < 6; i++) m(new THREE.CylinderGeometry(0.08, 0.08, 0.06, 20), std(i === 0 ? 0x3dff9a : 0x3a424e), -0.25 + (i % 3) * 0.25, -0.3 - Math.floor(i / 3) * 0.28, 0.22, g).rotation.x = Math.PI / 2;
    m(new THREE.CylinderGeometry(0.1, 0.1, 0.25, 20), phys({ color: 0xc8ced6, metalness: 1, roughness: 0.2 }), 0, 1.2, 0, g);
    P.medidor = { alvo: V(48, 1.0, 0.6), cam: V(-1.6, 1.4, 4.6) };
  }

  function rack() {  // rack 19" com OLT em cima, organizador e DIO embaixo
    const g = new THREE.Group(); S.add(g);
    const preto = phys({ color: 0x151a21, metalness: 0.8, roughness: 0.4 });
    [[-1.2, -0.75], [1.2, -0.75], [-1.2, 0.75], [1.2, 0.75]].forEach(([x, z]) => m(RB(0.12, 4.4, 0.12, 0.02), preto, x, 2.2, z, g));
    m(RB(2.52, 0.12, 1.62, 0.03), preto, 0, 4.4, 0, g); m(RB(2.52, 0.12, 1.62, 0.03), preto, 0, 0.06, 0, g);
    [-1.08, 1.08].forEach(x => { const t = tex(32, 512, (c, w, h) => { c.fillStyle = '#20262f'; c.fillRect(0, 0, w, h); c.fillStyle = '#05070a'; for (let i = 0; i < 64; i++) c.fillRect(10, 4 + i * 8, 12, 4); });
      m(new THREE.PlaneGeometry(0.12, 4.2), bas(0xffffff, { map: t }), x, 2.2, 0.82, g); });
    m(RB(2.1, 0.22, 0.3, 0.03), preto, 0, 1.86, 0.7, g);
    for (let i = 0; i < 6; i++) m(RB(0.08, 0.2, 0.28, 0.02), phys({ color: 0x2a313c, metalness: 0.8, roughness: 0.4 }), -0.9 + i * 0.36, 1.86, 0.86, g);
    m(RB(2.1, 0.3, 0.1, 0.02), phys({ color: 0x1d232c, metalness: 0.7, roughness: 0.5 }), 0, 0.55, 0.78, g);
  }
  function dio() {  // DIO 1U retangular: 24 adaptadores SC/APC verdes; a gaveta desliza e mostra a bandeja de emenda
    const g = new THREE.Group(); g.position.set(0, 1.25, 0); S.add(g);
    const chapa = phys({ color: 0xd9dee5, metalness: 0.9, roughness: 0.28 });
    m(RB(2.1, 0.34, 1.3, 0.03), phys({ color: 0x1f252e, metalness: 0.8, roughness: 0.4 }), 0, 0, -0.05, g);
    const gaveta = new THREE.Group(); g.add(gaveta);
    m(RB(2.1, 0.34, 0.06, 0.02), chapa, 0, 0, 0.62, gaveta);
    for (let i = 0; i < 24; i++) {
      const x = -0.92 + (i % 12) * 0.167, y = (i < 12 ? 0.075 : -0.075);
      m(RB(0.1, 0.1, 0.08, 0.015), std(0x2fae5b, { roughness: 0.35 }), x, y, 0.67, gaveta);
      m(RB(0.06, 0.06, 0.02, 0.01), std(0x1b6b39), x, y, 0.715, gaveta);
      if ([2, 3, 7, 14].includes(i)) m(RB(0.09, 0.09, 0.16, 0.015), std(0x2fae5b), x, y, 0.78, gaveta);
    }
    const lab = tex(512, 64, (c, w, h) => { c.fillStyle = '#d9dee5'; c.fillRect(0, 0, w, h); c.fillStyle = '#3a424e'; c.font = '700 30px Figtree'; c.fillText('DIO 24 FO · SC/APC', 14, 42); });
    m(new THREE.PlaneGeometry(0.9, 0.1), bas(0xffffff, { map: lab }), 0.55, 0.13, 0.656, gaveta);
    const band = new THREE.Group(); band.position.set(0, 0.02, 0.1); gaveta.add(band);
    m(RB(1.8, 0.03, 0.9, 0.02), std(0x2a313c), 0, 0, 0, band);
    for (let k = 0; k < 3; k++) { const o = m(new THREE.TorusGeometry(0.28 - k * 0.05, 0.012, 8, 48), std(0xf2c230), -0.45, 0.03, 0, band); o.rotation.x = Math.PI / 2; o.scale.set(1.4, 1, 1); }
    for (let k = 0; k < 6; k++) m(new THREE.CylinderGeometry(0.02, 0.02, 0.3, 12), phys({ color: 0xffffff, transmission: 0.8, roughness: 0.1, thickness: 0.05 }), 0.35, 0.04, -0.25 + k * 0.1, band).rotation.z = Math.PI / 2;
    ANIM.push((t, ativo, lt) => { const u = ativo === 'dio' ? ease((lt - 0.8) / 1.3) : 0; gaveta.position.z = 0.75 * u; });
    P.dio = { alvo: V(0, 1.3, 0.8), cam: V(-1.2, 0.75, 2.6) };
  }
  function poste(x, alt) { m(new THREE.CylinderGeometry(0.16, 0.22, alt, 16), std(0x9aa0a8, { roughness: 0.9 }), x, alt / 2, -0.8); m(RB(1.6, 0.12, 0.12, 0.02), std(0x9aa0a8), x, alt - 0.5, -0.8); }
  function ceo() {  // CEO tipo domo (referência: domo preto com nervuras, base com entradas redondas, bandejas brancas com suportes azuis)
    poste(30, 7.5);
    const g = new THREE.Group(); g.position.set(30, 4.3, -0.3); S.add(g);
    const preto = phys({ color: 0x17191d, roughness: 0.42, clearcoat: 0.35 });
    // base: flange e entradas de cabo (cilindros) para baixo
    m(new THREE.CylinderGeometry(0.46, 0.46, 0.12, 48), preto, 0, 0, 0, g);
    m(new THREE.CylinderGeometry(0.4, 0.4, 0.18, 48), preto, 0, -0.14, 0, g);
    [[0, 0, 0.13], [0.2, 0.12, 0.09], [-0.2, 0.12, 0.09], [0.2, -0.12, 0.09], [-0.2, -0.12, 0.09], [0, 0.24, 0.07], [0, -0.24, 0.07]].forEach(([x, z, r]) =>
      m(new THREE.CylinderGeometry(r, r, 0.42, 24), preto, x, -0.44, z, g));
    // domo com nervuras horizontais
    const tampa = new THREE.Group(); g.add(tampa);
    m(new THREE.CylinderGeometry(0.4, 0.4, 1.5, 48, 1, true), phys({ color: 0x1b1e22, roughness: 0.4, clearcoat: 0.4, side: THREE.DoubleSide }), 0, 0.82, 0, tampa);
    m(new THREE.SphereGeometry(0.4, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2), phys({ color: 0x1b1e22, roughness: 0.4, clearcoat: 0.4 }), 0, 1.57, 0, tampa);
    for (let k = 0; k < 10; k++) { const anel = m(new THREE.TorusGeometry(0.405, 0.012, 6, 64), preto, 0, 0.22 + k * 0.13, 0, tampa); anel.rotation.x = Math.PI / 2; }
    [0.3, 1.1].forEach(y => m(RB(0.1, 0.12, 0.08, 0.02), preto, 0.42, y, 0, tampa));  // abas de fixação
    // bandejas brancas com suportes de emenda azuis, articuladas atrás
    const bandejas = [];
    for (let k = 0; k < 6; k++) {
      const piv = new THREE.Group(); piv.position.set(0, 0.12 + k * 0.17, -0.22); g.add(piv);
      const b = new THREE.Group(); b.position.set(0, 0, 0.22); piv.add(b);
      m(RB(0.6, 0.04, 0.46, 0.02), std(0xf0f2f5, { roughness: 0.35 }), 0, 0, 0, b);
      m(RB(0.62, 0.05, 0.02, 0.01), std(0xdfe3e8), 0, 0.03, 0.23, b);
      for (let i = 0; i < 2; i++) m(RB(0.18, 0.04, 0.09, 0.012), std(0x2b3fb8, { roughness: 0.4 }), -0.12 + i * 0.24, 0.04, -0.04, b);
      const v = m(new THREE.TorusGeometry(0.13, 0.008, 6, 40), std(0xf4f6f8), 0, 0.03, 0.1, b); v.rotation.x = Math.PI / 2; v.scale.set(1.6, 1, 0.7);
      if (k === 3) m(RB(0.12, 0.035, 0.14, 0.01), std(0x19c3ff, { emissive: 0x19c3ff, emissiveIntensity: 0.4 }), 0.2, 0.05, 0.12, b);  // splitter
      bandejas.push(piv);
    }
    ANIM.push((t, ativo, lt) => {
      const on = ativo === 'ceo' || ativo === 'ceo_dentro';
      const tt = ativo === 'ceo_dentro' ? 9 : lt;
      const subir = on ? ease((tt - 0.6) / 1.0) : 0;
      tampa.position.y = 2.3 * subir; tampa.visible = !(on && subir > 0.995);
      bandejas.forEach((piv, k) => { const a2 = on ? ease((tt - 1.4 - (5 - k) * 0.16) / 0.6) : 0; piv.rotation.x = -a2 * (0.25 + k * 0.17); });
    });
    P.ceo = { alvo: V(30, 4.8, -0.3), cam: V(-1.7, 0.5, 3.1) };
    P.ceo_dentro = { alvo: V(30, 5.0, -0.2), cam: V(-0.9, 0.9, 2.1) };
  }
  function cto() {  // CTO (referência: caixa cinza-escura com dobradiça e travas; por dentro preta, adaptadores verdes, fibra enrolada)
    poste(38, 7.5);
    const g = new THREE.Group(); g.position.set(38, 3.9, -0.5); S.add(g);
    const casca = phys({ color: 0x3b3f45, roughness: 0.5, clearcoat: 0.25 });
    const interno = std(0x121417, { roughness: 0.7 });
    m(RB(0.72, 1.12, 0.26, 0.05), casca, 0, 0, -0.02, g);
    m(RB(0.66, 1.06, 0.02, 0.02), interno, 0, 0, 0.115, g);
    for (let i = 0; i < 8; i++) { const y = 0.42 - Math.floor(i / 2) * 0.1, x = -0.2 + (i % 2) * 0.13;
      m(RB(0.11, 0.08, 0.08, 0.012), std(0x7ed957, { roughness: 0.35 }), x, y, 0.16, g);
      if (i < 3) m(RB(0.1, 0.07, 0.16, 0.012), std(0x7ed957), x, y, 0.24, g); }
    const rolo = m(new THREE.TorusGeometry(0.2, 0.012, 6, 48), std(0xf2f4f6), 0, -0.08, 0.15, g); rolo.scale.set(1.3, 0.75, 1);
    const rolo2 = m(new THREE.TorusGeometry(0.17, 0.01, 6, 48), std(0xf2f4f6), 0, -0.08, 0.155, g); rolo2.scale.set(1.3, 0.75, 1);
    m(RB(0.09, 0.03, 0.03, 0.01), std(0xdfe3e8), 0.02, -0.06, 0.17, g);  // splitter em tubo no meio da bobina
    [-0.12, 0.12].forEach(x => { m(new THREE.CylinderGeometry(0.035, 0.035, 0.16, 16), phys({ color: 0x9aa0a8, metalness: 1, roughness: 0.3 }), x, -0.5, 0.1, g);
      m(new THREE.CylinderGeometry(0.018, 0.018, 3.0, 8), std(0x101214), x, -2.05, 0.1, g); });
    // tampa articulada à esquerda, com dentes de dobradiça e duas travas à direita
    const piv = new THREE.Group(); piv.position.set(-0.36, 0, 0.12); g.add(piv);
    m(RB(0.72, 1.12, 0.07, 0.04), casca, 0.36, 0, 0.0, piv);
    const nerv = tex(256, 512, (c, w, h) => { c.fillStyle = '#3b3f45'; c.fillRect(0, 0, w, h); c.strokeStyle = 'rgba(0,0,0,.25)'; c.lineWidth = 3; for (let i = 0; i < 24; i++) { c.beginPath(); c.moveTo(30, 40 + i * 18); c.lineTo(w - 30, 40 + i * 18); c.stroke(); } });
    m(new THREE.PlaneGeometry(0.6, 1.0), bas(0xffffff, { map: nerv }), 0.36, 0, 0.037, piv);
    for (let k = 0; k < 9; k++) m(RB(0.06, 0.07, 0.08, 0.01), std(0x2a2d31), -0.02, -0.48 + k * 0.12, 0, piv);
    [0.32, -0.32].forEach(y => m(RB(0.08, 0.16, 0.1, 0.02), std(0x202226), 0.73, y, 0.01, piv));
    ANIM.push((t, ativo, lt) => { const on = ativo === 'cto' || ativo === 'cto_dentro'; const u = on ? ease(((ativo === 'cto_dentro' ? 9 : lt) - 1.0) / 0.9) : 0; piv.rotation.y = -1.9 * u; });
    P.cto = { alvo: V(38, 3.9, -0.4), cam: V(-1.3, 0.4, 2.8) };
    P.cto_dentro = { alvo: V(38, 3.95, -0.4), cam: V(-0.45, 0.3, 1.8) };
  }
  let HUD = null;  // medidor de potência fixo na tela: cai a cada parada (params.hud = valor em dBm)
  function hudInit(stage) {
    HUD = document.createElement('div'); stage.appendChild(HUD);
    Object.assign(HUD.style, { position: 'absolute', left: '40px', top: PORT ? '1085px' : '880px', padding: '14px 26px', borderRadius: '18px', background: 'rgba(7,10,15,.86)',
      font: '800 46px "DejaVu Sans Mono", monospace', color: '#fff', zIndex: 30, display: 'none', whiteSpace: 'nowrap' });
  }
  function hud(segs, i, lt) {
    const val = s => (s && s.params && s.params.hud != null) ? Number(s.params.hud) : null;
    const v = val(segs[i]); if (v == null) { HUD.style.display = 'none'; return; }
    let v0 = v; for (let k = i - 1; k >= 0; k--) if (val(segs[k]) != null) { v0 = val(segs[k]); break; }
    const x = v0 + (v - v0) * ease((lt - 0.3) / 1.2), cor = x > -8 ? '#19c3ff' : x > -25 ? '#3dff9a' : x > -27 ? '#ffb020' : '#ff4d4d';
    HUD.style.display = 'block'; HUD.style.boxShadow = 'inset 0 0 0 3px ' + cor;
    HUD.innerHTML = '<span style="font:700 26px Figtree;color:#9aa6b5;letter-spacing:.12em">POTÊNCIA NA FIBRA</span><br><span style="color:' + cor + '">' + (x > 0.05 ? '+' : x < -0.05 ? '−' : '') + Math.abs(x).toFixed(1).replace('.', ',') + ' dBm</span>';
  }


  function enlace() {  // o cordão amarelo ligando tudo, com pulsos de luz que enfraquecem a cada peça
    const pts = [V(0.6, 1.25, 1.5), V(1.4, 0.6, 1.9), V(2.6, 0.08, 1.9), V(8.4, 0.08, 1.8), V(14, 0.08, 1.8), V(16.4, 0.08, 1.4), V(19, 0.08, 1.4),
      V(22.2, 0.08, 1.2), V(24.8, 0.08, 1.2), V(28, 0.08, 0.4), V(29.6, 0.3, -0.6), V(29.7, 4.1, -0.6), V(30.4, 6.9, -0.8), V(34, 6.8, -0.8), V(37.8, 6.9, -0.8),
      V(38.1, 4.6, -0.6), V(38.0, 3.2, -0.2), V(40.5, 1.6, 0.4), V(42.6, 0.3, 0.5), V(43.2, 0.5, 0.4)];
    const o = tubo(pts, 0.04, std(0xf2c230, { roughness: 0.45 }), 400);
    const ps = []; for (let i = 0; i < 10; i++) { const s = glow(ACC2, 0.4); S.add(s); ps.push({ s, f: i / 10 }); }
    ANIM.push(t => ps.forEach(p => { const u = (t * 0.06 + p.f) % 1; p.s.position.copy(o.userData.curva.getPointAt(u)); p.s.material.opacity = 0.9 * Math.exp(-u * 1.4); }));
    P.geral = { alvo: V(24, 1.5, 0), cam: V(0.01, 24, 30) };
  }

  // ---------------------------------------------------------------- ciclo
  const M3 = { on: false };
  M3.PECAS = ['olt', 'dio', 'fibra', 'fibra_perto', 'bobina', 'fusao', 'ceo', 'ceo_dentro', 'splitter', 'cto', 'cto_dentro', 'onu', 'medidor', 'geral'];
  M3.init = async function (stage, st) {
    ST = st; W = st.w; H = st.h; PORT = H > W;
    ACC = new THREE.Color(st.theme.accent || '#19c3ff'); ACC2 = new THREE.Color(st.theme.accent2 || '#3dff9a');
    GLOW = tex(128, 128, (g) => { const r = g.createRadialGradient(64, 64, 0, 64, 64, 64); r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.3, 'rgba(255,255,255,.55)'); r.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = r; g.fillRect(0, 0, 128, 128); });
    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    R.setPixelRatio(st.scale3d || 0.75); R.setSize(W, H, false);
    R.outputColorSpace = THREE.SRGBColorSpace; R.toneMapping = THREE.ACESFilmicToneMapping; R.toneMappingExposure = 1.1;
    const cv = R.domElement; cv.id = 'gl3d'; Object.assign(cv.style, { position: 'absolute', left: '0', top: '0', width: W + 'px', height: H + 'px' }); stage.appendChild(cv);
    S = new THREE.Scene(); S.background = new THREE.Color(0x05070b); S.fog = new THREE.Fog(0x05070b, 14, 60);
    if (window.THREEX && THREEX.RoomEnvironment) { const pm = new THREE.PMREMGenerator(R); S.environment = pm.fromScene(new THREEX.RoomEnvironment(R), 0.04).texture; pm.dispose(); }
    S.add(new THREE.HemisphereLight(0x9fb4d8, 0x05070b, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 2.0); key.position.set(10, 14, 12); S.add(key);
    const rim1 = new THREE.DirectionalLight(ACC, 2.2); rim1.position.set(-10, 6, -10); S.add(rim1);
    const rim2 = new THREE.DirectionalLight(ACC2, 1.2); rim2.position.set(30, 5, -10); S.add(rim2);
    C = new THREE.PerspectiveCamera(PORT ? 46 : 34, W / H, 0.03, 300);
    if (PORT) C.setViewOffset(W, H, 0, -H * 0.15, W, H);  // a peça fica na metade de baixo; o quadro técnico em cima
    bancada(); rack(); olt(); dio(); fibraCorte(); ceo(); cto(); hudInit(stage); bobina(); fusao(); splitter(); onu(); medidor(); enlace();
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
    const a = pose(ant || atual), b = pose(atual), dist = a.pos.distanceTo(b.pos), voo = Math.min(2.0, 0.8 + dist / 30), u = ease(lt / voo);
    const pos = a.pos.clone().lerp(b.pos, u), alvo = a.alvo.clone().lerp(b.alvo, u);
    pos.y += Math.sin(Math.PI * u) * Math.min(5, dist * 0.12);
    const k = Math.max(0, lt - voo) / Math.max(1, d - voo);
    const off = pos.clone().sub(alvo); off.applyAxisAngle(V(0, 1, 0), (atual === 'geral' ? 0.05 : 0.22) * Math.sin(k * Math.PI * 0.8)).multiplyScalar(1 - 0.07 * k);
    C.position.copy(alvo).add(off); C.lookAt(alvo);
    ANIM.forEach(f => f(t, atual, lt));
    hud(segs, i, lt);
    R.render(S, C);
  };
  window.VIDEO3D = window.VIDEO3D || {};
  window.VIDEO3D.redes02 = M3;
})();
