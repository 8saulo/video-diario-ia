/* Ilustração contínua "planta": a casa vista de cima, desenhada em código (canvas 2D), que muda conforme a narração.
   Cada cena do roteiro diz o PASSO (params.passo) e a ilustração faz a transição para ele, sem trocar de cena:
   o roteador emite ondas, as ondas perdem força nas paredes/obstáculos (o mapa de calor é calculado por distância
   e perda de cada parede), aparecem a zona morta, as bandas 2,4/5 GHz, a interferência, os nós mesh, o backhaul,
   o celular andando pela casa (roaming) e o melhor lugar para o roteador. Tudo é função do tempo (determinístico). */
(function () {
  'use strict';
  const WPL = { on: false };
  let CV = null, G = null, W = 0, H = 0, ST = null, R = null;  // R = retângulo da planta em px
  const CASA = { w: 12, h: 10 };
  // paredes: [x1, y1, x2, y2, material] em metros (portas são os vãos entre segmentos)
  const PAREDES = [
    [0, 0, 12, 0, 'alv'], [12, 0, 12, 10, 'alv'], [12, 10, 0, 10, 'alv'], [0, 10, 0, 0, 'alv'],
    [0, 4.5, 3, 4.5, 'alv'], [4.5, 0, 4.5, 3.3, 'alv'],                       // quarto 1
    [7, 0, 7, 3.3, 'alv'], [7, 4.5, 8, 4.5, 'alv'], [9, 4.5, 12, 4.5, 'alv'],  // suíte
    [4.5, 3, 5.3, 3, 'dry'], [6.2, 3, 7, 3, 'dry'],                           // banheiro (drywall)
    [7, 6, 7, 10, 'alv'],                                                      // sala | cozinha
  ];
  const PERDA = { alv: 12, dry: 4, metal: 15, espelho: 6 };  // dB por travessia em 2,4 GHz (5 GHz: x1,6)
  const OBST = [  // obstáculos: retângulos [x, y, w, h, material, rótulo]
    [10.9, 4.8, 0.9, 0.8, 'metal', 'GELADEIRA'], [6.75, 0.6, 0.15, 1.8, 'espelho', 'ESPELHO'], [9.3, 9.25, 0.7, 0.5, 'metal', 'MICRO-ONDAS'],
  ];
  const COMODOS = [['QUARTO', 2.25, 2.2], ['BANHEIRO', 5.75, 1.5], ['SUÍTE', 9.5, 2.2], ['SALA', 3.5, 7.4], ['COZINHA', 9.5, 7.3]];
  const MOVEIS = [[0.4, 1.0, 2.0, 2.4], [8.6, 0.6, 2.4, 2.0], [1.0, 8.4, 3.0, 1.1], [8.0, 8.9, 3.8, 0.8], [4.9, 0.4, 1.2, 0.8]];
  const POS = { canto: [0.7, 9.3], centro: [5.8, 5.6] };
  let NOS = [[5.8, 3.9], [9.6, 2.6]];  // nós mesh (o roteiro pode pedir outros: timeline.planta.nos)
  const VIZINHOS = [[-1.2, 2.0], [13.2, 8.0]];

  // ---------------------------------------------------------------- passos (o que cada um mostra)
  const BASE = { planta: 1, roteador: 0, ondas: 0, calor: 0, tagsParede: 0, tagsObst: 0, celular: 0, morta: 0, banda5: 0,
                 vizinhos: 0, nos: 0, links: 0, roaming: 0, centro: 0, dicas: 0, legenda: 0, fixo: 0 };
  const PASSOS = {
    casa: {},
    roteador: { roteador: 1 },
    ondas: { roteador: 1, ondas: 1, calor: 1, legenda: 1 },
    paredes: { roteador: 1, ondas: 1, calor: 1, tagsParede: 1, legenda: 1 },
    obstaculos: { roteador: 1, ondas: 1, calor: 1, tagsObst: 1, legenda: 1 },
    distancia: { roteador: 1, ondas: 1, calor: 1, celular: 1, legenda: 1 },
    zona_morta: { roteador: 1, ondas: 1, calor: 1, morta: 1, legenda: 1 },
    bandas: { roteador: 1, ondas: 1, calor: 1, banda5: 1, legenda: 1 },
    interferencia: { roteador: 1, ondas: 1, calor: 1, vizinhos: 1, legenda: 1 },
    mesh: { roteador: 1, ondas: 1, calor: 1, nos: 1, legenda: 1 },
    backhaul: { roteador: 1, ondas: 0.5, calor: 1, nos: 1, links: 1, legenda: 1 },
    roaming: { roteador: 1, ondas: 0.5, calor: 1, nos: 1, links: 1, roaming: 1, legenda: 1 },
    posicionamento: { roteador: 1, ondas: 1, calor: 1, centro: 1, dicas: 1, legenda: 1 },
    resumo: { roteador: 1, ondas: 1, calor: 1, nos: 1, links: 1, legenda: 1 },
    cta: { roteador: 1, ondas: 0.6, calor: 1, nos: 1, links: 1 },
    // parte 3D (planta3d.js) e as pontes entre 3D e 2D
    quarto_problema: {}, quarto_fraco: {}, quarto_sem_sinal: {}, corredor: {},
    transicao: { roteador: 1, calor: 1 },                                     // a câmera sobe e a casa vira planta
    cobertura: { roteador: 1, ondas: 1, calor: 1, nos: 1, links: 1, legenda: 1, fixo: 1 },  // suíte verde, zoom no celular
    quarto_resolvido: {},
  };
  WPL.PASSOS = Object.keys(PASSOS);
  function estado(passo) { return Object.assign({}, BASE, PASSOS[passo] || PASSOS.resumo); }

  // ---------------------------------------------------------------- modelo de sinal
  function cruza(ax, ay, bx, by, cx, cy, dx, dy) {
    const d = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx);
    if (Math.abs(d) < 1e-9) return false;
    const u = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / d, v = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / d;
    return u > 0 && u < 1 && v > 0 && v < 1;
  }
  function rssiDe(ap, x, y, b5) {
    const d = Math.max(0.6, Math.hypot(x - ap[0], y - ap[1]));
    let p = -31 - 27 * Math.log10(d) - (b5 ? 5 + 6 * Math.log10(d) : 0);
    const k = b5 ? 1.6 : 1;
    for (const w of PAREDES) if (cruza(ap[0], ap[1], x, y, w[0], w[1], w[2], w[3])) p -= PERDA[w[4]] * k;
    for (const o of OBST) {
      const [ox, oy, ow, oh, m] = o;
      if (cruza(ap[0], ap[1], x, y, ox, oy, ox + ow, oy + oh) || cruza(ap[0], ap[1], x, y, ox + ow, oy, ox, oy + oh)) p -= PERDA[m] * k;
    }
    return p;
  }
  function rssi(aps, x, y, b5) { let m = -120; for (const a of aps) m = Math.max(m, rssiDe(a, x, y, b5)); return m; }
  WPL.rssi = rssi;
  function corDe(p, a) {  // verde (ótimo) -> amarelo (bom) -> laranja (fraco) -> vermelho (sem sinal)
    const s = [[-55, [48, 209, 88]], [-63, [190, 230, 60]], [-70, [255, 196, 40]], [-77, [255, 120, 40]], [-85, [255, 59, 92]]];
    let c = s[s.length - 1][1];
    for (let i = 0; i < s.length - 1; i++) {
      if (p >= s[0][0]) { c = s[0][1]; break; }
      if (p <= s[i][0] && p >= s[i + 1][0]) { const u = (s[i][0] - p) / (s[i][0] - s[i + 1][0]); c = s[i][1].map((v, j) => v + (s[i + 1][1][j] - v) * u); break; }
    }
    return 'rgba(' + c.map(Math.round).join(',') + ',' + a + ')';
  }
  WPL.corDe = corDe;
  const CACHE = {};
  function mapa(aps, b5) {  // mapa de calor (canvas) para um conjunto de pontos de acesso e banda; calculado uma vez
    const k = JSON.stringify([aps, b5]);
    if (CACHE[k]) return CACHE[k];
    const passo = 0.12, nx = Math.ceil(CASA.w / passo), ny = Math.ceil(CASA.h / passo);
    const c = document.createElement('canvas'); c.width = nx; c.height = ny;
    const g = c.getContext('2d');
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { g.fillStyle = corDe(rssi(aps, (i + 0.5) * passo, (j + 0.5) * passo, b5), 1); g.fillRect(i, j, 1, 1); }
    return (CACHE[k] = c);
  }

  // ---------------------------------------------------------------- desenho
  const X = m => R.x + m * R.s, Y = m => R.y + m * R.s;
  function ease(u) { u = Math.max(0, Math.min(1, u)); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; }
  function txt(s, x, y, o) {
    o = o || {};
    G.font = (o.peso || 800) + ' ' + (o.tam || 26) + 'px ' + (o.mono ? '"DejaVu Sans Mono", Consolas, monospace' : 'Figtree, sans-serif');
    G.textAlign = o.al || 'center'; G.textBaseline = 'middle';
    if (o.fundo) {
      const w = G.measureText(s).width + 28, h = (o.tam || 26) + 18;
      const x0 = o.al === 'left' ? x - 14 : o.al === 'right' ? x - w + 14 : x - w / 2;
      G.fillStyle = o.fundo; rr(x0, y - h / 2, w, h, 12); G.fill();
      if (o.borda) { G.strokeStyle = o.borda; G.lineWidth = 3; G.stroke(); }
    }
    G.fillStyle = o.cor || '#e8ecf2'; G.fillText(s, x, y);
  }
  function rr(x, y, w, h, r) { G.beginPath(); G.moveTo(x + r, y); G.arcTo(x + w, y, x + w, y + h, r); G.arcTo(x + w, y + h, x, y + h, r); G.arcTo(x, y + h, x, y, r); G.arcTo(x, y, x + w, y, r); G.closePath(); }
  function acc(a) { return 'rgba(' + (ST.theme.accRgb || '25,195,255') + ',' + a + ')'; }

  function planta(u) {  // u: 0..1 desenho das paredes (entrada)
    G.save();
    G.fillStyle = 'rgba(14,20,30,.92)'; rr(X(0) - 18, Y(0) - 18, CASA.w * R.s + 36, CASA.h * R.s + 36, 22); G.fill();
    G.strokeStyle = 'rgba(255,255,255,.035)'; G.lineWidth = 1;
    for (let m = 1; m < CASA.w; m++) { G.beginPath(); G.moveTo(X(m), Y(0)); G.lineTo(X(m), Y(CASA.h)); G.stroke(); }
    for (let m = 1; m < CASA.h; m++) { G.beginPath(); G.moveTo(X(0), Y(m)); G.lineTo(X(CASA.w), Y(m)); G.stroke(); }
    G.restore();
  }
  function paredes(u, destaque) {
    G.save(); G.lineCap = 'round';
    PAREDES.forEach((w, i) => {
      const k = ease(u * PAREDES.length - i * 0.6); if (k <= 0) return;
      G.strokeStyle = destaque ? (w[4] === 'alv' ? '#ffb020' : '#7fdcff') : '#c9d2df';
      G.lineWidth = w[4] === 'alv' ? R.s * 0.2 : R.s * 0.1;
      G.beginPath(); G.moveTo(X(w[0]), Y(w[1])); G.lineTo(X(w[0] + (w[2] - w[0]) * k), Y(w[1] + (w[3] - w[1]) * k)); G.stroke();
    });
    G.restore();
  }
  function moveis(a) {
    G.save(); G.globalAlpha = a; G.strokeStyle = 'rgba(200,210,225,.25)'; G.lineWidth = 2;
    MOVEIS.forEach(m => { rr(X(m[0]), Y(m[1]), m[2] * R.s, m[3] * R.s, 8); G.stroke(); });
    OBST.forEach(o => { G.fillStyle = o[4] === 'metal' ? 'rgba(160,170,185,.55)' : 'rgba(170,230,255,.6)'; G.fillRect(X(o[0]), Y(o[1]), o[2] * R.s, o[3] * R.s); });
    COMODOS.forEach(c => txt(c[0], X(c[1]), Y(c[2]), { tam: Math.round(R.s * 0.34), peso: 800, cor: 'rgba(200,210,225,.55)', mono: true }));
    G.restore();
  }
  function aparelho(x, y, a, cor, rot, pulso) {  // roteador ou nó mesh
    a = Math.max(0, Math.min(1, a)); if (a <= 0.01) return;  // alpha negativo era ignorado e o nó aparecia sempre
    G.save(); G.globalAlpha = a;
    const r = R.s * 0.36;
    const gl = G.createRadialGradient(x, y, 0, x, y, r * 3.2); gl.addColorStop(0, cor.replace('A', '.55')); gl.addColorStop(1, cor.replace('A', '0'));
    G.fillStyle = gl; G.beginPath(); G.arc(x, y, r * 3.2 * (1 + 0.08 * pulso), 0, Math.PI * 2); G.fill();
    G.fillStyle = '#0d1219'; rr(x - r, y - r * 0.7, r * 2, r * 1.4, 10); G.fill();
    G.strokeStyle = cor.replace('A', '1'); G.lineWidth = 4; G.stroke();
    G.beginPath(); G.moveTo(x - r * 0.6, y - r * 0.7); G.lineTo(x - r * 0.75, y - r * 1.5); G.moveTo(x + r * 0.6, y - r * 0.7); G.lineTo(x + r * 0.75, y - r * 1.5); G.stroke();
    for (let i = 0; i < 3; i++) { G.fillStyle = i === 0 ? '#3dff9a' : cor.replace('A', '1'); G.beginPath(); G.arc(x - r * 0.45 + i * r * 0.45, y + r * 0.15, 4, 0, Math.PI * 2); G.fill(); }
    if (rot) txt(rot, x, y + r * 1.55, { tam: Math.round(R.s * 0.32), peso: 900, cor: '#fff', fundo: 'rgba(8,11,16,.85)' });
    G.restore();
  }
  function ondas(aps, t, a, b5) {  // anéis que se expandem; o brilho em cada ponto é o sinal ali (some nas paredes)
    if (a <= 0) return;
    G.save(); G.lineWidth = 4.5;
    const rmax = 9.5, vel = 2.4, esp = 1.6;
    aps.forEach((ap, ia) => {
      for (let k = 0; k < 6; k++) {
        const r = ((t * vel + k * esp + ia * 0.7) % (esp * 6));
        if (r < 0.3 || r > rmax) continue;
        const n = Math.max(40, Math.round(r * 26));
        for (let i = 0; i < n; i++) {
          const a0 = i / n * Math.PI * 2, a1 = (i + 1) / n * Math.PI * 2;
          const mx = ap[0] + r * Math.cos((a0 + a1) / 2), my = ap[1] + r * Math.sin((a0 + a1) / 2);
          if (mx < 0 || my < 0 || mx > CASA.w || my > CASA.h) continue;
          const p = rssiDe(ap, mx, my, b5), f = Math.max(0, Math.min(1, (p + 92) / 55));
          if (f < 0.03) continue;
          G.strokeStyle = corDe(p, (a * (0.35 + 0.65 * f) * (1 - r / rmax * 0.35)).toFixed(3));  // a onda muda de cor ao perder força
          G.beginPath(); G.arc(X(ap[0]), Y(ap[1]), r * R.s, a0, a1); G.stroke();
        }
      }
    });
    G.restore();
  }
  function calor(aps, b5, a, revela, centro) {
    if (a <= 0) return;
    G.save(); G.globalAlpha = a * 0.5; G.imageSmoothingEnabled = true; G.filter = 'blur(' + Math.round(R.s * 0.12) + 'px)';
    if (revela < 1) { G.beginPath(); G.arc(X(centro[0]), Y(centro[1]), revela * 16 * R.s, 0, Math.PI * 2); G.clip(); }
    G.drawImage(mapa(aps, b5), X(0), Y(0), CASA.w * R.s, CASA.h * R.s);
    G.restore();
  }
  function legenda(a) {
    if (a <= 0) return;
    G.save(); G.globalAlpha = a;
    const y = Y(CASA.h) + R.s * 0.75, w = CASA.w * R.s * 0.86, x0 = X(CASA.w / 2) - w / 2, h = R.s * 0.22;
    const gr = G.createLinearGradient(x0, 0, x0 + w, 0);
    [[0, -50], [0.3, -60], [0.5, -68], [0.7, -76], [1, -88]].forEach(([u, p]) => gr.addColorStop(u, corDe(p, 1)));
    G.fillStyle = gr; rr(x0, y, w, h, h / 2); G.fill();
    const tam = Math.round(R.s * 0.3);
    txt('ÓTIMO', x0, y + h + tam, { tam, al: 'left', cor: '#c9d2df' });
    txt('FRACO', x0 + w * 0.62, y + h + tam, { tam, cor: '#c9d2df' });
    txt('SEM SINAL', x0 + w, y + h + tam, { tam, al: 'right', cor: '#c9d2df' });
    G.restore();
  }
  function celular(x, y, p, a, ap) {
    G.save(); G.globalAlpha = a;
    if (ap) { G.setLineDash([8, 8]); G.strokeStyle = 'rgba(255,255,255,.55)'; G.lineWidth = 3; G.beginPath(); G.moveTo(X(ap[0]), Y(ap[1])); G.lineTo(x, y); G.stroke(); G.setLineDash([]); }
    const w = R.s * 0.36, h = R.s * 0.62;
    G.fillStyle = '#0d1219'; rr(x - w / 2, y - h / 2, w, h, 9); G.fill(); G.strokeStyle = '#fff'; G.lineWidth = 3.5; G.stroke();
    const barras = p > -55 ? 4 : p > -65 ? 3 : p > -72 ? 2 : p > -80 ? 1 : 0;
    for (let i = 0; i < 4; i++) { G.fillStyle = i < barras ? corDe(p, 1) : 'rgba(255,255,255,.2)'; G.fillRect(x - w * 0.3 + i * w * 0.17, y + h * 0.25 - (i + 1) * h * 0.09, w * 0.12, (i + 1) * h * 0.09); }
    txt(Math.round(p).toString().replace('-', '−') + ' dBm', x, y - h * 0.95, { tam: Math.round(R.s * 0.34), peso: 900, mono: true, cor: '#0b0d12', fundo: corDe(p, 1) });
    G.restore();
  }
  function tag(s, x, y, cor, a) { if (a > 0) { G.save(); G.globalAlpha = Math.min(1, a); txt(s, x, y, { tam: Math.round(R.s * 0.33), peso: 900, mono: true, cor: '#0b0d12', fundo: cor }); G.restore(); } }

  // caminho do celular (roaming) e da distância, em metros
  const ROTA = [[1.5, 8.0], [4.2, 6.5], [5.8, 4.0], [5.8, 2.0], [8.2, 3.9], [10.2, 2.5], [10.2, 7.0]];
  function naRota(rota, u) {
    const seg = rota.length - 1, f = Math.max(0, Math.min(0.9999, u)) * seg, i = Math.floor(f), k = f - i;
    return [rota[i][0] + (rota[i + 1][0] - rota[i][0]) * k, rota[i][1] + (rota[i + 1][1] - rota[i][1]) * k];
  }

  // ---------------------------------------------------------------- ciclo
  WPL.init = async function (stage, st) {
    ST = st; W = st.w; H = st.h;
    const box = document.createElement('div'); box.id = 'gl3d'; Object.assign(box.style, { position: 'absolute', left: '0', top: '0', width: W + 'px', height: H + 'px' });
    stage.appendChild(box);
    CV = document.createElement('canvas'); CV.width = W; CV.height = H;
    Object.assign(CV.style, { position: 'absolute', left: '0', top: '0', width: W + 'px', height: H + 'px' });
    G = CV.getContext('2d');
    const m = /^#?([0-9a-f]{6})$/i.exec(st.theme.accent || ''); if (m) { const n = parseInt(m[1], 16); st.theme.accRgb = (n >> 16 & 255) + ',' + (n >> 8 & 255) + ',' + (n & 255); }
    // 9:16: planta entre o título (topo) e a legenda das falas; 16:9: à direita do texto
    if (H > W) { const s = Math.min((W - 110) / CASA.w, 780 / CASA.h); R = { s, x: (W - CASA.w * s) / 2, y: 440 }; }
    else { const s = Math.min(1000 / CASA.w, (H - 300) / CASA.h); R = { s, x: W - CASA.w * s - 120, y: (H - CASA.h * s) / 2 - 20 }; }
    WPL.R = R;
    if (st.planta && Array.isArray(st.planta.nos) && st.planta.nos.length) NOS = st.planta.nos;
    // 3D (pessoa, celular, corredor) só se o roteiro usa algum passo 3D
    const usa3d = (st.segments || []).some(s => s.params && (TRES.has(s.params.passo) || s.params.passo === 'transicao'));
    if (usa3d && window.WPL3 && window.THREE) WPL3.init(box, st, { PAREDES, R });
    box.appendChild(CV);
    // pré-calcula os mapas usados (evita travar no meio do render)
    [[[POS.canto], 0], [[POS.canto], 1], [[POS.centro], 0], [[POS.canto].concat(NOS), 0]].forEach(([a, b]) => mapa(a, b));  // NOS já é o do roteiro
    WPL.on = true;
    return CV;
  };

  function quadroDe(seg) { return estado(seg && seg.params && seg.params.passo); }
  function misturar(a, b, u) { const o = {}; for (const k in BASE) o[k] = a[k] + (b[k] - a[k]) * u; return o; }

  function desenhar2D(t, segs, i, passo, lt, d) {
    const seg = segs[i];
    const atual = estado(passo), passoAnt = i > 0 ? segs[i - 1].params && segs[i - 1].params.passo : '';
    const ant = i > 0 && !TRES.has(passoAnt) ? estado(passoAnt) : Object.assign({}, BASE, { planta: 1 });
    const u = ease(lt / 0.8), S = misturar(ant, atual, u);
    G.clearRect(0, 0, W, H);
    // zoom no celular da suíte no fim da "cobertura" (o celular 2D vira o celular 3D na cena seguinte)
    const zoom = passo === 'cobertura' ? ease((lt - (d - 1.7)) / 1.5) : 0;
    G.save();
    if (zoom > 0) { const k = 1 + 5 * zoom, fx = X(CEL[0]), fy = Y(CEL[1]); G.translate(fx + (W / 2 - fx) * zoom, fy + (H * 0.42 - fy) * zoom); G.scale(k, k); G.translate(-fx, -fy); }
    // primeira vez que a planta aparece (sem vir do 3D): as paredes se desenham
    const primeira = segs.findIndex(s => !TRES.has(s.params && s.params.passo) && (s.params && s.params.passo) !== 'transicao');
    const desenho = (i === primeira && !TRES.has(passoAnt) && passoAnt !== 'transicao') ? ease(lt / 2.2) : 1;
    planta(desenho);
    // posição do roteador: canto da sala; no passo "posicionamento" ele vai para o centro da casa
    const cAnt = ant.centro, cAt = atual.centro;
    const kc = passo === 'posicionamento' ? ease((lt - 0.8) / 1.6) : (cAnt + (cAt - cAnt) * u);
    const rot = [POS.canto[0] + (POS.centro[0] - POS.canto[0]) * kc, POS.canto[1] + (POS.centro[1] - POS.canto[1]) * kc];
    const b5 = passo === 'bandas' ? (Math.floor(Math.max(0, lt - 0.6) / Math.max(1.6, d / 2 - 0.3)) % 2 === 1) : false;
    const apsBase = [rot];
    const apsMesh = S.nos > 0.5 ? [rot].concat(NOS) : apsBase;
    // mapa de calor: revela junto com a primeira onda
    const revela = (ant.calor < 0.5 && atual.calor > 0.5) ? Math.min(1, lt / 2.6) : 1;
    if (passo === 'posicionamento') { calor([POS.canto], false, S.calor * (1 - kc), 1, rot); calor([POS.centro], false, S.calor * kc, 1, rot); }
    else if (S.nos > 0 && S.nos < 1) { calor(apsBase, false, S.calor * (1 - S.nos), revela, rot); calor([rot].concat(NOS), false, S.calor * S.nos, 1, rot); }
    else calor(apsMesh, b5, S.calor, revela, rot);
    moveis(Math.min(1, desenho * 1.4));
    paredes(desenho, S.tagsParede > 0.5);
    ondas(apsMesh, t, S.ondas, b5);
    if (S.vizinhos > 0) {  // redes dos vizinhos: ondas tracejadas entrando pela parede
      G.save(); G.globalAlpha = S.vizinhos; G.setLineDash([10, 12]); G.lineWidth = 3;
      VIZINHOS.forEach((v, k) => { for (let j = 0; j < 4; j++) { const r = ((t * 2 + j * 1.3 + k) % 5.2) + 0.5; G.strokeStyle = 'rgba(255,120,60,' + (0.8 * (1 - r / 5.7)).toFixed(2) + ')'; G.beginPath(); G.arc(X(v[0]), Y(v[1]), r * R.s, 0, Math.PI * 2); G.stroke(); } });
      G.setLineDash([]); G.restore();
      tag('REDE DO VIZINHO', X(0.2) + R.s * 1.5, Y(1.2), '#ff7a3c', S.vizinhos);
      tag('REDE DO VIZINHO', X(CASA.w) - R.s * 1.5, Y(8.9), '#ff7a3c', S.vizinhos);
      const pisca = 0.5 + 0.5 * Math.sin(t * 14);
      tag('INTERFERÊNCIA', X(9.65), Y(8.75), 'rgba(255,59,92,' + (0.6 + 0.4 * pisca).toFixed(2) + ')', S.vizinhos);
    }
    // nós mesh e backhaul
    if (S.links > 0) {
      G.save(); G.globalAlpha = S.links; G.strokeStyle = '#3dff9a'; G.lineWidth = 5; G.setLineDash([14, 10]); G.lineDashOffset = -t * 40;
      const pares = [[rot, NOS[0]]].concat(NOS.slice(1).map((n, k) => [NOS[k], n]));
      pares.forEach(([a, b]) => { G.beginPath(); G.moveTo(X(a[0]), Y(a[1])); G.lineTo(X(b[0]), Y(b[1])); G.stroke(); });
      G.setLineDash([]);
      pares.forEach(([a, b], k) => { const f = (t * 0.7 + k * 0.5) % 1; G.fillStyle = '#3dff9a'; G.shadowColor = '#3dff9a'; G.shadowBlur = 20; G.beginPath(); G.arc(X(a[0] + (b[0] - a[0]) * f), Y(a[1] + (b[1] - a[1]) * f), 9, 0, Math.PI * 2); G.fill(); });
      G.restore();
      if (passo === 'backhaul') tag('BACKHAUL', X((rot[0] + NOS[0][0]) / 2) + R.s * 0.9, Y((rot[1] + NOS[0][1]) / 2), '#3dff9a', S.links);
    }
    NOS.forEach((n, k) => aparelho(X(n[0]), Y(n[1]), Math.min(1, S.nos * 1.2 - k * 0.2), acc('A'), 'NÓ ' + (k + 1), Math.sin(t * 3 + k)));
    aparelho(X(rot[0]), Y(rot[1]), S.roteador, acc('A'), S.nos > 0.5 ? 'PRINCIPAL' : 'ROTEADOR', Math.sin(t * 3));
    // paredes e obstáculos: perda em cada travessia
    if (S.tagsParede > 0) {
      tag('ALVENARIA  −12 dB', X(2.0), Y(4.5), '#ffb020', S.tagsParede);
      tag('ALVENARIA  −12 dB', X(7), Y(1.6) , '#ffb020', S.tagsParede * ease((lt - 0.4) / 0.5));
      tag('DRYWALL  −4 dB', X(5.75), Y(3.0), '#7fdcff', S.tagsParede * ease((lt - 0.8) / 0.5));
    }
    if (S.tagsObst > 0) {
      OBST.forEach((o, k) => { const a = S.tagsObst * ease((lt - 0.3 - k * 0.4) / 0.5); G.save(); G.globalAlpha = a; G.strokeStyle = '#ff3b5c'; G.lineWidth = 4; rr(X(o[0]) - 8, Y(o[1]) - 8, o[2] * R.s + 16, o[3] * R.s + 16, 10); G.stroke(); G.restore();
        tag(o[5] + '  −' + PERDA[o[4]] + ' dB', X(o[0] + o[2] / 2) - (o[0] > 10 ? R.s * 0.9 : 0), Y(o[1]) - R.s * 0.45, '#ff3b5c', a); });
    }
    if (S.morta > 0) {
      const p = 0.5 + 0.5 * Math.sin(t * 5);
      G.save(); G.globalAlpha = S.morta * (0.35 + 0.35 * p); G.strokeStyle = '#ff3b5c'; G.lineWidth = 6; rr(X(7.15), Y(0.15), 4.7 * R.s, 4.2 * R.s, 16); G.stroke(); G.restore();
      tag('ZONA MORTA', X(9.5), Y(3.4), '#ff3b5c', S.morta);
    }
    if (passo === 'bandas') {
      const s1 = b5 ? 'rgba(255,255,255,.18)' : '#3dff9a', s2 = b5 ? '#ffb020' : 'rgba(255,255,255,.18)';
      tag('2,4 GHz · alcança mais', X(3), Y(0) - R.s * 0.75, s1, 1);
      tag('5 GHz · mais rápido', X(9), Y(0) - R.s * 0.75, s2, 1);
    }
    if (S.dicas > 0) {
      const ds = [['NO CENTRO DA CASA', 5.8, 6.9], ['NO ALTO', 3.3, 5.6], ['LONGE DE METAL', 9.0, 5.6]];
      ds.forEach((dd, k) => tag(dd[0], X(dd[1]), Y(dd[2]), '#3dff9a', S.dicas * ease((lt - 1.6 - k * 0.45) / 0.5)));
    }
    // celular: afastando-se do roteador (distância) ou andando pela casa (roaming)
    if (S.celular > 0 || S.roaming > 0) {
      const ro = S.roaming > S.celular;
      const k = ease(Math.min(1, Math.max(0, (lt - 0.5) / Math.max(1.5, d - 1.5))));
      const pos = ro ? naRota(ROTA, k) : naRota([[rot[0] + 0.9, rot[1] - 0.4], [3.5, 6.5], [5.8, 4.0], [8.2, 3.9], [10.4, 2.0]], k);
      const aps = ro ? [rot].concat(NOS) : [rot];
      let melhor = aps[0], mp = -200; aps.forEach(a => { const p = rssiDe(a, pos[0], pos[1], false); if (p > mp) { mp = p; melhor = a; } });
      celular(X(pos[0]), Y(pos[1]), mp, Math.max(S.celular, S.roaming), melhor);
      if (ro) tag('MESMA REDE: MinhaCasa', X(CASA.w / 2), Y(0) - R.s * 0.75, '#3dff9a', S.roaming);
    }
    if (S.fixo > 0) {  // o celular da pessoa, na suíte: agora com sinal forte (mesh)
      const aps = [rot].concat(NOS); let melhor = aps[0], mp = -200;
      aps.forEach(a => { const p = rssiDe(a, CEL[0], CEL[1], false); if (p > mp) { mp = p; melhor = a; } });
      celular(X(CEL[0]), Y(CEL[1]), mp, S.fixo, melhor);
    }
    G.restore();
    legenda(S.legenda * (1 - zoom));
  }


  const TRES = new Set(['quarto_problema', 'quarto_fraco', 'quarto_sem_sinal', 'corredor', 'quarto_resolvido']);
  const CEL = [9.75, 3.0];  // onde está o celular da pessoa (igual ao 3D: planta3d.js, P)
  WPL.render = function (t, seg, idx) {
    if (!WPL.on) return;
    const segs = (ST.segments || []).filter(s => s.kind === 'scene');
    const i = Math.max(0, segs.indexOf(seg));
    const passo = (seg && seg.params && seg.params.passo) || (seg ? 'cta' : 'casa');
    const lt = seg ? Math.max(0, t - seg.start) : 0, d = seg ? Math.max(1, seg.dur) : 5, u = lt / d;
    let a2 = 1;  // opacidade da camada 2D por cima do 3D
    const em3d = !!(window.WPL3 && WPL3.on && (TRES.has(passo) || passo === 'transicao'));
    // run 45226402450: o render em partes (vários navegadores) deixava a última imagem 3D atrás da planta 2D;
    // nos passos 2D a camada 3D fica escondida
    if (window.WPL3 && WPL3.on) WPL3.cv.style.visibility = em3d ? 'visible' : 'hidden';
    if (em3d) {
      WPL3.render(passo, t, lt, d);
      a2 = passo === 'transicao' ? ease((u - 0.62) / 0.33) : 0;
      if (passo === 'quarto_resolvido') a2 = 1 - ease(lt / 0.55);  // o celular 2D (com zoom) se dissolve no celular 3D
    }
    CV.style.opacity = a2.toFixed(3);
    if (a2 <= 0.001) return;
    if (passo === 'quarto_resolvido') { const k = segs.findIndex(s => s.params && s.params.passo === 'cobertura'); if (k >= 0) desenhar2D(t, segs, k, 'cobertura', 99, 1.8); return; }
    desenhar2D(t, segs, i, passo, lt, d);
  };
  window.WPL = WPL;
})();
