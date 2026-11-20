// Quadro de dossiê: recortes presos num quadro (polaroide com alfinete, moldura dourada, logo da marca, recorte de jornal,
// post-it, carimbo e etiquetas), montados por cena a partir de params._quadro (videobot/elementos.py).
// Determinístico: tudo entra na timeline GSAP da cena (o render quadro a quadro só faz seek).
(function () {
  'use strict';
  const MONO = "'DejaVu Sans Mono', Consolas, 'Courier New', monospace";
  const SERIF = "Georgia, 'DejaVu Serif', 'Times New Roman', serif";

  function el(tag, cls, pai, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; if (pai) pai.appendChild(e); return e; }
  function css(e, o) { Object.assign(e.style, o); return e; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function hash(s) { let h = 2166136261; for (const c of String(s)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
  // encolhe a fonte até o texto caber na caixa (largura e altura), sem quebrar palavra no meio
  function caber(e, maxW, maxH, min) {
    let f = parseFloat(e.style.fontSize) || parseFloat(getComputedStyle(e).fontSize) || 40;
    for (let n = 0; n < 60 && f > min && (e.scrollWidth > maxW + 1 || (maxH && e.scrollHeight > maxH + 1)); n++) {
      f -= 2; e.style.fontSize = f + 'px';
    }
    return f;
  }
  // tamanho inicial pela maior palavra (antes de medir): palavra longa nunca estoura a largura
  function fontePorPalavra(txt, largura, base, k) {
    const maior = Math.max(1, ...String(txt || '').split(/\s+/).map(p => p.length));
    return Math.max(14, Math.min(base, Math.floor(largura / (maior * k))));
  }
  function lum(hex) { const m = /^#?([0-9a-f]{6})$/i.exec(hex || ''); if (!m) return 0.5; const n = parseInt(m[1], 16); return (0.2126 * (n >> 16 & 255) + 0.7152 * (n >> 8 & 255) + 0.0722 * (n & 255)) / 255; }

  // posições (centro x/y em fração da área do quadro, largura em px da tela 1080 de largura, rotação)
  const LAYOUT = {
    1: [[0.5, 0.47, 560, -3]],
    2: [[0.28, 0.46, 450, -6], [0.72, 0.52, 450, 5]],
    3: [[0.5, 0.33, 420, 1], [0.23, 0.66, 380, -8], [0.77, 0.68, 380, 7]],
    4: [[0.27, 0.3, 390, -6], [0.73, 0.29, 390, 5], [0.28, 0.72, 370, 4], [0.72, 0.73, 370, -5]],
  };

  function alfinete(card, cor) {
    const p = el('div', 'q-pin', card);
    css(p, { background: `radial-gradient(circle at 35% 30%, #fff 0 10%, ${cor} 22% 62%, #5a0010 100%)` });
    return p;
  }

  // ---------------------------------------------------------------- peças
  const PECA = {};

  PECA.polaroide = function (q, it, w, rnd) {
    const card = el('div', 'q-card q-polaroid', q.area);
    const alto = it.tipo === 'pessoa' ? w * 1.02 : w * 0.78;
    const jan = el('div', 'q-janela', card); css(jan, { height: alto + 'px' });
    const img = el('img', '', jan); img.alt = ''; img.src = it.src || '';
    if (it.foco) img.style.objectPosition = it.foco;
    else if (it.tipo === 'pessoa') img.style.objectPosition = '50% 18%';
    if (it.video && it.video.dir) q.video = { img, dir: it.video.dir, n: it.video.n, fps: it.video.fps || 30, k: -1 };
    const leg = el('div', 'q-legenda', card);
    if (it.tipo === 'pessoa') {
      el('div', 'q-nome', leg, esc(String(it.nome || '').toUpperCase()));
      if (it.papel) el('div', 'q-papel', leg, esc(String(it.papel).toUpperCase()));
    }
    if (it.credito) el('div', 'q-credito', card, esc(String(it.credito).replace(/^Foto: |^Vídeo: /, '')));
    if (rnd() < 0.7) alfinete(card, '#e8183c'); else el('div', 'q-fita', card);
    return { card, zoom: img };
  };

  PECA.moldura = function (q, it, w) {
    const card = el('div', 'q-card q-moldura', q.area);
    const jan = el('div', 'q-janela', card); css(jan, { height: (w * 1.18) + 'px' });
    const img = el('img', '', jan); img.alt = ''; img.src = it.src || ''; img.style.objectPosition = '50% 15%';
    const placa = el('div', 'q-placa', card);
    el('div', 'q-nome', placa, esc(String(it.nome || '').toUpperCase()));
    if (it.papel) el('div', 'q-papel', placa, esc(String(it.papel).toUpperCase()));
    if (it.credito) el('div', 'q-credito', card, esc(String(it.credito).replace(/^Foto: /, '')));
    return { card, zoom: img };
  };

  PECA.logo = function (q, it, w) {
    const card = el('div', 'q-card q-logo', q.area);
    const claro = it.fundo === 'claro' || lum(it.cor) < 0.22;  // logo escura (ex.: preta) ou colorida da Commons: fundo claro
    css(card, { width: w + 'px', height: (w * 0.72) + 'px', background: claro ? '#f4f5f8' : '#0e1118',
                boxShadow: `0 0 0 3px ${it.cor}, 0 0 46px ${it.cor}99, 0 24px 40px rgba(0,0,0,.55)` });
    const img = el('img', '', card); img.alt = ''; img.src = it.svg || '';
    el('div', 'q-marca', card, esc(String(it.nome || '').toUpperCase()));
    alfinete(card, '#e8183c');
    return { card, zoom: img };
  };

  PECA.manchete = function (q, it, w) {
    const card = el('div', 'q-card q-jornal', q.area);
    css(card, { width: w + 'px' });
    el('div', 'q-jornal-topo', card, '— EDIÇÃO EXTRA —');
    const h = el('div', 'q-jornal-texto', card, esc(it.texto || ''));
    const n = (it.texto || '').length;
    const util = w - 44;
    css(h, { width: util + 'px', fontSize: fontePorPalavra(it.texto, util, Math.round(w * (n > 40 ? 0.085 : n > 24 ? 0.1 : 0.12)), 0.62) + 'px' });
    caber(h, util, Math.round(w * 0.5), 16);
    el('div', 'q-jornal-linhas', card);
    el('div', 'q-fita', card);
    return { card, zoom: null };
  };

  PECA.nota = function (q, it, w) {
    const card = el('div', 'q-card q-postit', q.area);
    const lado = Math.round(w * 0.78);
    css(card, { width: lado + 'px', height: lado + 'px' });
    const v = el('div', 'q-postit-valor', card, esc(it.valor || ''));
    const util = lado - 44;
    css(v, { maxWidth: util + 'px', fontSize: fontePorPalavra(it.valor, util, Math.round(lado * ((it.valor || '').length > 7 ? 0.2 : 0.27)), 0.5) + 'px' });
    const r = el('div', 'q-postit-rotulo', card, esc(it.rotulo || ''));
    css(r, { maxWidth: util + 'px', fontSize: fontePorPalavra(it.rotulo, util, 24, 0.6) + 'px' });
    caber(r, util, Math.round(util * 0.3), 12);
    caber(v, util, util - r.scrollHeight - 10, 16);
    alfinete(card, '#1e6bff');
    return { card, zoom: null };
  };

  function peca(q, it, w, rnd) {
    if (it.tipo === 'pessoa' && it.destaque) return PECA.moldura(q, it, w * 0.9);
    if (it.tipo === 'pessoa' || it.tipo === 'foto' || it.tipo === 'video') return PECA.polaroide(q, it, w, rnd);
    if (it.tipo === 'logo') return PECA.logo(q, it, w * 0.9);
    if (it.tipo === 'manchete') return PECA.manchete(q, it, w);
    if (it.tipo === 'nota') return PECA.nota(q, it, w);
    return null;
  }

  // ---------------------------------------------------------------- montagem da cena
  function montar(root, seg, ST) {
    const P = seg.params || {}, Q = P._quadro || {};
    const port = ST.h > ST.w, W = ST.w, H = ST.h;
    const rnd = rng(hash(seg.id || seg.start));
    const q = { video: null };
    const fundo = el('div', 'q-fundo', root);
    el('div', 'q-holofote', fundo); el('div', 'q-linhas', fundo);
    // área do quadro: no vertical, entre os cartões de cima e a legenda; no horizontal, à direita
    const R = port ? { x: 0, y: 770, w: W, h: 615 } : { x: Math.round(W * 0.44), y: 120, w: Math.round(W * 0.54), h: H - 300 };
    q.area = el('div', 'q-area', root);
    css(q.area, { left: R.x + 'px', top: R.y + 'px', width: R.w + 'px', height: R.h + 'px' });
    const k = port ? 1 : 1.05;
    // destaque primeiro (vai para a posição principal)
    const itens = (Q.itens || []).slice().sort((a, b) => (b.destaque ? 1 : 0) - (a.destaque ? 1 : 0)).slice(0, 4);
    const lay = LAYOUT[itens.length] || LAYOUT[4];
    const pecas = [];
    itens.forEach((it, i) => {
      const [fx, fy, w, rot] = lay[i];
      const pc = peca(q, it, w * k, rnd);
      if (!pc) return;
      const c = pc.card;
      css(c, { width: c.style.width || (w * k) + 'px', left: (fx * R.w) + 'px', top: (fy * R.h) + 'px' });
      c.dataset.rot = String(rot + (rnd() - 0.5) * 3);
      c.style.zIndex = it.destaque ? 6 : 2 + i;  // a figura em destaque fica na frente
      pecas.push({ c, zoom: pc.zoom, it });
    });
    // carimbo sobre a primeira foto/pessoa (ou sobre o centro)
    let carimbo = null;
    if (Q.carimbo) {
      // nunca sobre a foto de uma pessoa: vai na foto/vídeo, no recorte de jornal ou no post-it
      const alvo = pecas.find(p => ['foto', 'video'].includes(p.it.tipo)) || pecas.find(p => ['manchete', 'nota', 'logo'].includes(p.it.tipo));
      const canto = alvo && ['manchete', 'nota'].includes(alvo.it.tipo);
      carimbo = el('div', 'q-carimbo', canto || !alvo ? q.area : alvo.c, esc(Q.carimbo));
      if (canto) {
        // jornal/post-it: o carimbo vai no canto de cima do recorte, por cima de tudo, sem cobrir o texto principal
        const c = alvo.c, cw = c.offsetWidth, chh = c.offsetHeight, lw = Math.round(cw * 0.62);
        carimbo.classList.add('q-carimbo-canto');
        css(carimbo, { width: lw + 'px', marginLeft: '0', left: (parseFloat(c.style.left) + cw * 0.5 - lw * 0.72) + 'px',
                       top: (parseFloat(c.style.top) - chh * 0.5 - 52) + 'px' });
      }
    }
    // etiquetas de dossiê
    const et = el('div', 'q-etiqueta', root, '// ' + esc(Q.etiqueta || 'DOSSIÊ'));
    const vivo = el('div', 'q-vivo', root, '<i></i>AO VIVO');
    css(et, port ? { left: '58px', top: (R.y - 4) + 'px' } : { left: (R.x + 10) + 'px', top: (R.y + R.h + 10) + 'px' });
    css(vivo, port ? { right: '58px', top: (R.y - 4) + 'px' } : { right: '60px', top: (R.y + R.h + 10) + 'px' });
    if (q.video) seg.vid = q.video;

    return {
      animar(tl, d) {
        pecas.forEach((p, i) => {
          const rot = parseFloat(p.c.dataset.rot), t0 = 0.08 + i * 0.22;
          tl.fromTo(p.c, { xPercent: -50, yPercent: -50, autoAlpha: 0, y: -90, rotation: rot - 14, scale: 1.18 },
            { autoAlpha: 1, y: 0, rotation: rot, scale: 1, duration: 0.55, ease: 'back.out(1.7)' }, t0);
          const pin = p.c.querySelector('.q-pin');
          if (pin) tl.fromTo(pin, { scale: 0 }, { scale: 1, duration: 0.22, ease: 'back.out(3)' }, t0 + 0.4);
          // flutuação leve até o fim da cena
          tl.to(p.c, { y: i % 2 ? 7 : -7, rotation: rot + (i % 2 ? 0.8 : -0.8), duration: Math.max(0.6, d - t0 - 0.6), ease: 'sine.inOut' }, t0 + 0.6);
          if (p.zoom) tl.fromTo(p.zoom, { scale: 1.0 }, { scale: 1.09, duration: d, ease: 'none' }, 0);
        });
        if (carimbo) tl.fromTo(carimbo, { autoAlpha: 0, scale: 2.6, rotation: -4 }, { autoAlpha: 1, scale: 1, rotation: -14, duration: 0.2, ease: 'power4.in' }, 0.75 + pecas.length * 0.12)
          .fromTo(carimbo.parentNode === q.area ? carimbo : carimbo.parentNode, { x: 0 }, { x: 6, duration: 0.05, repeat: 3, yoyo: true, ease: 'none' }, 0.95 + pecas.length * 0.12);
        tl.fromTo([et, vivo], { autoAlpha: 0, y: 10 }, { autoAlpha: 1, y: 0, duration: 0.35, ease: 'power2.out', stagger: 0.1 }, 0.2);
        const ponto = vivo.querySelector('i');
        const n = Math.max(1, Math.floor(d / 0.5));
        tl.to(ponto, { opacity: 0.15, duration: 0.5, repeat: n, yoyo: true, ease: 'none' }, 0);
        tl.fromTo(fundo, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }, 0);
      },
    };
  }

  window.QUADRO = { montar };
})();
