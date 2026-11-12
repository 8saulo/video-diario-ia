/* Motor de cenas: cada quadro é renderAt(t). Nada depende do relógio real. */
(function () {
  'use strict';
  let ST = null, STAGE = null, SCN = null, HUD = {}, BG = {};
  const T = {};

  // ---------- utilidades ----------
  function el(tag, cls, parent, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }
  function css(e, o) { Object.assign(e.style, o); return e; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  const NF = {};
  function fmt(v, d) { d = d || 0; NF[d] = NF[d] || new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }); return NF[d].format(v); }
  function norm(s) { return String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9%$]/g, ''); }
  function words(s) { return String(s || '').trim().split(/\s+/).filter(Boolean); }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  /* Reduz a fonte até o bloco caber em maxW × maxH (medido sem transformações). */
  function fit(e, maxF, minF, maxW, maxH) {
    let f = maxF;
    e.style.fontSize = f + 'px';
    for (let i = 0; i < 60; i++) {
      const r = e.getBoundingClientRect();
      const rg = document.createRange(); rg.selectNodeContents(e);
      const cw = rg.getBoundingClientRect().width;
      const over = e.scrollWidth > e.clientWidth + 1 || (maxW && cw > maxW + 1) || (maxH && r.height > maxH + 1);
      if (!over || f <= minF) break;
      f = Math.max(minF, f * 0.95);
      e.style.fontSize = f + 'px';
    }
    return f;
  }
  function wordSpans(parent, text, hl) {
    const H = (hl || []).map(norm).filter(Boolean);
    const out = [];
    words(text).forEach((w, i) => {
      if (i) parent.appendChild(document.createTextNode(' '));
      const s = el('span', 'w' + (H.includes(norm(w)) ? ' hl' : ''), parent);
      s.textContent = w;
      out.push(s);
    });
    return out;
  }
  function iconTile(parent, name, size) {
    const w = el('div', '', parent);
    css(w, { width: size + 'px', height: size + 'px', position: 'relative', flex: 'none' });
    const t = el('div', 'tile chk', w, window.iconSVG(name, 2.6));
    return { wrap: w, tile: t, svg: t.querySelector('svg') };
  }
  function drawOn(tl, svg, at, dur) {
    svg.querySelectorAll('path,circle,rect,ellipse').forEach((p, i) => {
      const L = (p.getTotalLength ? p.getTotalLength() : 120) + 2;
      p.style.strokeDasharray = L + ' ' + L;
      tl.fromTo(p, { strokeDashoffset: L }, { strokeDashoffset: 0, duration: dur, ease: 'power2.inOut' }, at + i * 0.07);
    });
  }
  function popIn(tl, e, at, extra) {
    tl.fromTo(e, Object.assign({ autoAlpha: 0, scale: 0.6, y: 30 }, (extra && extra.from) || {}),
      Object.assign({ autoAlpha: 1, scale: 1, y: 0, duration: 0.55, ease: 'back.out(1.7)' }, (extra && extra.to) || {}), at);
  }
  function riseIn(tl, e, at, dist) {
    tl.fromTo(e, { autoAlpha: 0, y: dist == null ? 40 : dist }, { autoAlpha: 1, y: 0, duration: 0.5, ease: 'power3.out' }, at);
  }
  function wordsIn(tl, spans, at, stagger) {
    if (!spans.length) return;
    tl.fromTo(spans, { autoAlpha: 0, y: 46, filter: 'blur(10px)' },
      { autoAlpha: 1, y: 0, filter: 'blur(0px)', duration: 0.5, ease: 'power3.out', stagger: stagger == null ? 0.06 : stagger }, at);
  }
  function numBlock(parent, p, cls) {
    const d = el('div', 'num chk ' + (cls || ''), parent);
    const px = el('span', 'px', d); px.textContent = p.prefix || '';
    const n = el('span', 'n', d);
    const sx = el('span', 'sx', d); sx.textContent = p.suffix || '';
    const dec = p.decimals || 0;
    const ano = isNum(p.value) && Number.isInteger(p.value) && p.value >= 1900 && p.value <= 2100 && !p.prefix && !p.suffix;
    if (ano) { n.textContent = String(p.value); return { d, n, dec, ano: true }; }
    if (isNum(p.value)) n.textContent = fmt(p.value, dec); else n.textContent = String(p.text || p.value || '');
    return { d, n, dec };
  }
  function countUp(c, nb, p, at, dur) {
    const neg = /[-−]/.test(p.prefix || '') || (isNum(p.value) && p.value < 0);
    if (p.count === false || neg) return;  // negativo (ex.: −27 dBm) contando a partir de "−0" parece defeito
    if (isNum(p.value) && !nb.ano) c.counters.push({ el: nb.n, from: isNum(p.from) ? p.from : 0, to: p.value, dec: nb.dec, at, dur: dur || 1.3 });
  }
  function hlColor(tl, spans, at) {
    spans.forEach((s, i) => {
      if (s.classList.contains('hl')) tl.fromTo(s, { color: '#fafafa' }, { color: getAcc(), duration: 0.3 }, at + i * 0.06 + 0.35);
    });
  }
  function applyTheme(root) {
    const a = ST.theme.accent, m = /^#?([0-9a-f]{6})$/i.exec(a || '');
    root.style.setProperty('--acc', a); root.style.setProperty('--acc2', ST.theme.accent2);
    if (m) {
      const n = parseInt(m[1], 16), r = n >> 16 & 255, g = n >> 8 & 255, b = n & 255;
      root.style.setProperty('--acc-rgb', r + ',' + g + ',' + b);
      const L = v => Math.round(v + (255 - v) * 0.35);
      if (!ST.theme.accentSoft) root.style.setProperty('--acc-soft', 'rgb(' + L(r) + ',' + L(g) + ',' + L(b) + ')');
    }
    if (ST.theme.accentSoft) root.style.setProperty('--acc-soft', ST.theme.accentSoft);
  }
  // 3D: "gpon" = cena fixa de fibra óptica (scene3d.js); qualquer outro valor = objetos do tema por cena (tema3d.js)
  function modulo3d() { return ST && ST.scene3d === 'gpon' ? window.W3D : window.W3T; }
  function getAcc() { return (ST && ST.theme && ST.theme.accent) || '#ff4f12'; }

  // ---------- templates ----------
  T.headline = function (c, p) {
    const wrap = el('div', '', c.box);
    const ic = p.icon ? true : false;
    css(wrap, { display: 'flex', flexDirection: c.port ? 'column' : 'row', alignItems: 'center', gap: c.port ? '56px' : '80px' });
    let tile = null;
    const isz = c.port ? 300 : 360;
    if (ic) tile = iconTile(wrap, p.icon, isz);
    const col = el('div', '', wrap);
    css(col, { display: 'flex', flexDirection: 'column', alignItems: ic && !c.port ? 'flex-start' : 'center', gap: '34px' });
    let eb = null;
    if (p.eyebrow) eb = el('div', 'eyebrow chk', col, '<span class="dot"></span>' + esc(p.eyebrow));
    const h = el('div', 'h1 chk', col);
    const maxW = ic && !c.port ? c.cw - isz - 80 : c.cw;
    css(h, { width: maxW + 'px', textAlign: ic && !c.port ? 'left' : 'center' });
    const spans = wordSpans(h, p.text, p.highlight);
    let sub = null;
    if (p.sub) { sub = el('div', 'sub chk', col); sub.textContent = p.sub; css(sub, { width: maxW + 'px', textAlign: ic && !c.port ? 'left' : 'center' }); fit(sub, c.port ? 42 : 40, 26, maxW, 120); }
    const avail = c.ch - (eb ? 90 : 0) - (sub ? sub.getBoundingClientRect().height + 34 : 0) - (ic && c.port ? isz + 56 : 0);
    fit(h, c.port ? 120 : 132, 46, maxW, avail);
    if (eb) popIn(c.tl, eb, 0.05);
    if (tile) { popIn(c.tl, tile.tile, 0.08); drawOn(c.tl, tile.svg, 0.25, 0.9); c.tl.fromTo(tile.wrap, { y: -10 }, { y: 10, duration: c.d, ease: 'sine.inOut' }, 0); }
    wordsIn(c.tl, spans, 0.15);
    hlColor(c.tl, spans, 0.15);
    if (sub) riseIn(c.tl, sub, 0.5 + spans.length * 0.05);
  };
  T.statement = T.headline;

  T.bignumber = function (c, p) {
    const rw = el('div', 'abs', c.cam, null); css(rw, { inset: '0' }); c.cam.insertBefore(rw, c.box);
    const rays = el('div', 'rays', rw);
    c.tl.fromTo(rw, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.5 }, 0);
    c.tl.fromTo(rays, { rotation: 0 }, { rotation: 24, duration: c.d, ease: 'none' }, 0);
    const col = el('div', '', c.box);
    css(col, { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '26px' });
    let tile = null;
    if (p.icon) tile = iconTile(col, p.icon, c.port ? 200 : 170);
    let eb = null;
    if (p.label) eb = el('div', 'eyebrow chk', col, '<span class="dot"></span>' + esc(p.label));
    const nb = numBlock(col, p);
    const sub = p.sub ? el('div', 'sub chk', col) : null;
    if (sub) { sub.textContent = p.sub; css(sub, { width: c.cw + 'px' }); fit(sub, c.port ? 48 : 46, 28, c.cw, 150); }
    const used = (tile ? (c.port ? 226 : 196) : 0) + (eb ? 90 : 0) + (sub ? sub.getBoundingClientRect().height + 26 : 0);
    fit(nb.d, c.port ? 300 : 320, 90, c.cw, c.ch - used);
    const ring = el('div', 'ring', c.box); css(ring, { width: '640px', height: '640px', left: '50%', top: '50%', marginLeft: '-320px', marginTop: '-320px', opacity: 0, visibility: 'hidden' });
    if (tile) { popIn(c.tl, tile.tile, 0.05); drawOn(c.tl, tile.svg, 0.15, 0.8); }
    if (eb) popIn(c.tl, eb, 0.1);
    c.tl.fromTo(nb.d, { autoAlpha: 0, scale: 0.72 }, { autoAlpha: 1, scale: 1, duration: 0.6, ease: 'back.out(1.6)' }, 0.25);
    countUp(c, nb, p, 0.3, 1.3);
    c.tl.fromTo(ring, { autoAlpha: 0.9, scale: 0.35 }, { autoAlpha: 0, scale: 1.7, duration: 0.9, ease: 'power2.out', immediateRender: false }, 1.45);
    c.tl.fromTo(nb.d, { textShadow: '0 0 0px rgba(var(--acc-rgb),0)' }, { textShadow: '0 0 60px rgba(var(--acc-rgb),.55)', duration: 0.4 }, 1.5);
    if (sub) riseIn(c.tl, sub, 1.2);
  };

  T.compare = function (c, p) {
    const col = el('div', '', c.box);
    css(col, { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: c.port ? '40px' : '50px', width: '100%' });
    let ttl = null;
    if (p.title) { ttl = el('div', 'h2 chk', col); ttl.textContent = p.title; css(ttl, { width: c.cw + 'px', textAlign: 'center' }); fit(ttl, c.port ? 74 : 70, 38, c.cw, 170); }
    const row = el('div', '', col);
    css(row, { position: 'relative', display: 'flex', flexDirection: c.port ? 'column' : 'row', gap: c.port ? '70px' : '110px', alignItems: 'stretch' });
    const cardW = c.port ? c.cw : Math.min(700, (c.cw - 110) / 2);
    const sides = [p.left || {}, p.right || {}];
    const cards = sides.map((s, i) => {
      const k = el('div', 'card chk' + ((p.winner === (i ? 'right' : 'left')) ? ' hot' : ''), row);
      css(k, { width: cardW + 'px', padding: c.port ? '40px 48px' : '50px 54px', display: 'flex', flexDirection: 'column', gap: '18px' });
      const lb = el('div', '', k); lb.textContent = s.label || '';
      css(lb, { fontWeight: 800, fontSize: '34px', letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--fog-200)' });
      fit(lb, 34, 22, cardW - 110, 90);
      const nb = numBlock(k, s);
      css(nb.d, { color: 'var(--fog-50)' });
      fit(nb.d, c.port ? 140 : 150, 56, cardW - 110, 170);
      let note = null;
      if (s.note) { note = el('div', 'sub', k); note.textContent = s.note; css(note, { textAlign: 'left', fontSize: '32px' }); fit(note, 32, 22, cardW - 110, 100); }
      let bd = null;
      if (s.tone === 'good' || s.tone === 'bad') {
        bd = el('div', 'badge ' + (s.tone === 'good' ? 'ok' : 'no'), k, window.iconSVG(s.tone === 'good' ? 'check' : 'cross', 4).replace('<circle cx="24" cy="24" r="19"/>', ''));
        css(bd, { right: '-22px', top: '-22px' });
      }
      return { k, nb, s, bd };
    });
    const vs = el('div', 'chip', row, 'VS');
    css(vs, { position: 'absolute', width: '120px', height: '120px', borderRadius: '50%', fontSize: '52px', left: '50%', top: '50%', marginLeft: '-60px', marginTop: '-60px', boxShadow: '0 0 0 10px var(--ink-900), 0 0 40px rgba(var(--acc-rgb),.5)' });
    // limita altura total
    const total = col.getBoundingClientRect().height;
    if (total > c.ch) css(col, { transform: 'scale(' + (c.ch / total).toFixed(3) + ')' });
    if (ttl) riseIn(c.tl, ttl, 0.05);
    cards.forEach((o, i) => {
      const at = 0.2 + i * 0.45;
      c.tl.fromTo(o.k, c.port ? { autoAlpha: 0, y: i ? 80 : -80 } : { autoAlpha: 0, x: i ? 110 : -110 }, { autoAlpha: 1, x: 0, y: 0, duration: 0.6, ease: 'power3.out' }, at);
      countUp(c, o.nb, o.s, at + 0.15, 1.1);
      if (o.bd) popIn(c.tl, o.bd, at + 1.0, { from: { scale: 0, y: 0 }, to: { ease: 'back.out(3)' } });
    });
    popIn(c.tl, vs, 0.5, { from: { scale: 0, y: 0, rotation: -90 }, to: { rotation: 0 } });
  };

  T.list = function (c, p) {
    const items = (p.items || []).slice(0, 5);
    const col = el('div', '', c.box);
    const W = Math.min(c.cw, c.port ? c.cw : 1400);
    css(col, { display: 'flex', flexDirection: 'column', gap: '22px', width: W + 'px' });
    let ttl = null;
    if (p.title) { ttl = el('div', 'h2 chk', col); ttl.textContent = p.title; css(ttl, { width: W + 'px', marginBottom: '14px' }); fit(ttl, c.port ? 76 : 72, 40, W, 180); }
    const rows = items.map((txt, i) => {
      const r = el('div', 'card chk', col);
      css(r, { display: 'flex', alignItems: 'center', gap: '30px', padding: '22px 34px 22px 22px', borderRadius: '28px' });
      const gw = el('div', 'abs', r); css(gw, { inset: '0' });
      const glow = el('div', 'abs', gw); css(glow, { inset: '0', borderRadius: '28px', boxShadow: 'inset 0 0 0 3px var(--acc), 0 0 40px rgba(var(--acc-rgb),.22)' });
      const ch = el('div', 'chip', r, p.numbered === false ? window.iconSVG('check', 4).replace('<circle cx="24" cy="24" r="19"/>', '') : String(i + 1));
      css(ch, { width: '84px', height: '84px', fontSize: '50px', position: 'relative' });
      if (p.numbered === false) css(ch.querySelector('svg'), { width: '56px', height: '56px' });
      const tx = el('div', '', r); tx.textContent = txt;
      css(tx, { fontWeight: 700, lineHeight: 1.18, position: 'relative', flex: '1' });
      return { r, gw, glow, tx, ch };
    });
    const avail = c.ch - (ttl ? ttl.getBoundingClientRect().height + 36 : 0) - rows.length * 22;
    const perRow = avail / Math.max(1, rows.length);
    rows.forEach(o => fit(o.tx, 46, 26, W - 170, Math.max(50, perRow - 44)));
    const tot = col.getBoundingClientRect().height;
    if (tot > c.ch) css(col, { transform: 'scale(' + (c.ch / tot).toFixed(3) + ')' });
    if (ttl) riseIn(c.tl, ttl, 0.05);
    const n = rows.length;
    const step = Math.min(1.4, Math.max(0.35, (c.d - 1.4) / Math.max(1, n)));
    rows.forEach((o, i) => {
      const at = 0.35 + i * step;
      c.tl.fromTo(o.r, { autoAlpha: 0, x: -70 }, { autoAlpha: 1, x: 0, duration: 0.5, ease: 'power3.out' }, at);
      popIn(c.tl, o.ch, at + 0.1, { from: { y: 0, scale: 0.3 } });
      c.tl.fromTo(o.glow, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.25 }, at + 0.1);
      if (i < n - 1) c.tl.fromTo(o.gw, { autoAlpha: 1 }, { autoAlpha: 0, duration: 0.3, immediateRender: false }, 0.35 + (i + 1) * step);
    });
  };

  T.bars = function (c, p) {
    const bars = (p.bars || []).slice(0, 6);
    const col = el('div', '', c.box);
    const W = Math.min(c.cw, 1500);
    css(col, { display: 'flex', flexDirection: 'column', gap: c.port ? '30px' : '24px', width: W + 'px' });
    let ttl = null;
    if (p.title) { ttl = el('div', 'h2 chk', col); ttl.textContent = p.title; css(ttl, { width: W + 'px', marginBottom: '10px' }); fit(ttl, c.port ? 72 : 68, 38, W, 170); }
    const mx = Math.max.apply(null, bars.map(b => Math.abs(b.value) || 0).concat([1e-9]));
    const labW = c.port ? W : Math.round(W * 0.27);
    const rows = bars.map((b, i) => {
      const r = el('div', 'chk', col);
      css(r, { display: 'flex', flexDirection: c.port ? 'column' : 'row', alignItems: c.port ? 'stretch' : 'center', gap: c.port ? '12px' : '28px' });
      const lb = el('div', '', r); lb.textContent = b.label || '';
      css(lb, { width: labW + 'px', fontWeight: 700, fontSize: '36px', color: b.highlight ? 'var(--fog-50)' : 'var(--fog-200)', textAlign: c.port ? 'left' : 'right' });
      fit(lb, 36, 22, labW, 92);
      const tr = el('div', '', r);
      css(tr, { position: 'relative', flex: c.port ? 'none' : '1', height: c.port ? '70px' : '74px', borderRadius: '18px', background: 'var(--ink-700)', boxShadow: 'inset 0 0 0 2px var(--ink-600)' });
      const fill = el('div', 'abs', tr);
      const frac = Math.max(0.04, Math.abs(b.value || 0) / mx);
      css(fill, { left: '0', top: '0', bottom: '0', width: (frac * 100).toFixed(2) + '%', borderRadius: '18px', transformOrigin: '0 50%',
        background: b.highlight ? 'linear-gradient(90deg, var(--acc), var(--acc-soft))' : 'linear-gradient(90deg, var(--ink-500), var(--fog-600))',
        boxShadow: b.highlight ? '0 0 34px rgba(var(--acc-rgb),.45)' : 'none' });
      const vb = numBlock(tr, { value: b.value, prefix: b.prefix || p.prefix, suffix: b.suffix || p.suffix || '', decimals: b.decimals != null ? b.decimals : p.decimals, text: b.text });
      const inside = frac > 0.55;
      css(vb.d, { position: 'absolute', top: '50%', transform: 'translateY(-50%)', fontSize: '50px', color: inside ? 'var(--ink-950)' : 'var(--fog-50)',
        left: inside ? 'auto' : 'calc(' + (frac * 100).toFixed(2) + '% + 20px)', right: inside ? 'calc(' + ((1 - frac) * 100).toFixed(2) + '% + 22px)' : 'auto' });
      vb.d.querySelectorAll('.px,.sx').forEach(s => { s.style.color = 'inherit'; });
      return { r, fill, vb, b };
    });
    const tot = col.getBoundingClientRect().height;
    if (tot > c.ch) css(col, { transform: 'scale(' + (c.ch / tot).toFixed(3) + ')' });
    if (ttl) riseIn(c.tl, ttl, 0.05);
    rows.forEach((o, i) => {
      const at = 0.3 + i * 0.28;
      riseIn(c.tl, o.r, at, 24);
      c.tl.fromTo(o.fill, { scaleX: 0 }, { scaleX: 1, duration: 1.0, ease: 'power3.out' }, at + 0.1);
      countUp(c, o.vb, Object.assign({}, o.b, { value: o.b.value }), at + 0.1, 1.0);
      c.tl.fromTo(o.vb.d, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }, at + 0.35);
    });
  };

  T.quote = function (c, p) {
    const W = c.port ? c.cw : Math.min(c.cw, 1450);
    const k = el('div', 'card chk', c.box);
    css(k, { width: W + 'px', padding: c.port ? '90px 56px 56px' : '80px 90px 64px', display: 'flex', flexDirection: 'column', gap: '40px' });
    const bar = el('div', 'abs', k); css(bar, { left: '0', top: '40px', bottom: '40px', width: '8px', borderRadius: '8px', background: 'var(--acc)' });
    const qm = el('div', 'abs', k, '“'); css(qm, { left: c.port ? '30px' : '46px', top: '-110px', fontFamily: 'Anton', fontSize: '300px', lineHeight: 1, color: 'var(--acc)' });
    const tx = el('div', 'h2', k); css(tx, { fontWeight: 750, letterSpacing: '-.025em', lineHeight: 1.16, width: (W - (c.port ? 112 : 180)) + 'px' });
    const spans = wordSpans(tx, p.text, p.highlight);
    spans.forEach(s => { s.style.display = 'inline-block'; });
    const au = el('div', '', k); css(au, { display: 'flex', alignItems: 'center', gap: '24px' });
    const ini = words(p.author || '?').slice(0, 2).map(w => w[0]).join('').toUpperCase();
    const av = el('div', 'chip', au, esc(ini)); css(av, { width: '92px', height: '92px', borderRadius: '50%', fontSize: '40px', background: 'var(--acc2)' });
    const nm = el('div', '', au, '<div style="font-weight:800;font-size:38px">' + esc(p.author || '') + '</div><div style="font-weight:500;font-size:28px;color:var(--fog-400)">' + esc(p.role || '') + '</div>');
    css(nm, { flex: '1' });
    let tag = null;
    if (p.paraphrase) { tag = el('div', 'pill', au, 'PARÁFRASE'); css(tag, { fontSize: '24px', padding: '12px 24px', letterSpacing: '.14em', background: 'rgba(255,214,10,.14)', color: 'var(--sun)', boxShadow: 'inset 0 0 0 2px rgba(255,214,10,.5)' }); }
    fit(tx, c.port ? 64 : 66, 34, W - (c.port ? 112 : 180), c.ch - 300);
    c.tl.fromTo(k, { autoAlpha: 0, y: 60, scale: 0.96 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.6, ease: 'power3.out' }, 0.05);
    c.tl.fromTo(qm, { autoAlpha: 0, scale: 0.4 }, { autoAlpha: 1, scale: 1, duration: 0.5, ease: 'back.out(2)' }, 0.3);
    const st = Math.min(0.08, Math.max(0.025, (c.d * 0.5) / Math.max(1, spans.length)));
    c.tl.fromTo(spans, { autoAlpha: 0.12 }, { autoAlpha: 1, duration: 0.2, stagger: st }, 0.45);
    hlColor(c.tl, spans, 0.45);
    riseIn(c.tl, au, 0.6, 20);
    if (tag) popIn(c.tl, tag, 1.0);
  };

  T.timeline = function (c, p) {
    const ev = (p.events || []).slice(0, 5);
    const col = el('div', '', c.box);
    css(col, { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '40px', width: c.cw + 'px' });
    let ttl = null;
    if (p.title) { ttl = el('div', 'h2 chk', col); ttl.textContent = p.title; css(ttl, { width: c.cw + 'px', textAlign: 'center' }); fit(ttl, c.port ? 74 : 70, 38, c.cw, 170); }
    const wrap = el('div', '', col);
    const n = ev.length || 1;
    let line, items = [];
    if (!c.port) {
      css(wrap, { position: 'relative', width: c.cw + 'px', height: '380px' });
      line = el('div', 'abs', wrap); css(line, { left: '30px', right: '30px', top: '170px', height: '6px', borderRadius: '6px', background: 'linear-gradient(90deg,var(--acc),var(--acc2))', transformOrigin: '0 50%' });
      const cw = c.cw / n;
      ev.forEach((e, i) => {
        const x = cw * (i + 0.5);
        const g = el('div', 'abs', wrap); css(g, { left: (x - cw / 2 + 10) + 'px', width: (cw - 20) + 'px', top: '0', height: '380px' });
        const dt = el('div', 'num chk', g); dt.textContent = e.date || ''; css(dt, { position: 'absolute', left: '0', right: '0', top: '40px', textAlign: 'center', color: 'var(--acc)' });
        fit(dt, 70, 30, cw - 20, 100);
        const dot = el('div', 'abs', g); css(dot, { left: '50%', top: '154px', width: '38px', height: '38px', marginLeft: '-19px', borderRadius: '50%', background: 'var(--ink-900)', boxShadow: 'inset 0 0 0 8px var(--acc2), 0 0 24px rgba(212,255,58,.6)' });
        const lb = el('div', 'chk', g); lb.textContent = e.label || ''; css(lb, { position: 'absolute', left: '0', right: '0', top: '226px', textAlign: 'center', fontWeight: 700, lineHeight: 1.18 });
        fit(lb, 34, 20, cw - 20, 150);
        items.push({ dt, dot, lb });
      });
    } else {
      css(wrap, { position: 'relative', width: c.cw + 'px', display: 'flex', flexDirection: 'column', gap: '36px', paddingLeft: '90px' });
      line = el('div', 'abs', wrap); css(line, { left: '30px', top: '10px', bottom: '10px', width: '6px', borderRadius: '6px', background: 'linear-gradient(180deg,var(--acc),var(--acc2))', transformOrigin: '50% 0' });
      ev.forEach(e => {
        const r = el('div', 'chk', wrap); css(r, { position: 'relative' });
        const dot = el('div', 'abs', r); css(dot, { left: '-79px', top: '14px', width: '38px', height: '38px', borderRadius: '50%', background: 'var(--ink-900)', boxShadow: 'inset 0 0 0 8px var(--acc2)' });
        const dt = el('div', 'num', r); dt.textContent = e.date || ''; css(dt, { color: 'var(--acc)' }); fit(dt, 64, 30, c.cw - 100, 80);
        const lb = el('div', '', r); lb.textContent = e.label || ''; css(lb, { fontWeight: 700, lineHeight: 1.18 }); fit(lb, 40, 24, c.cw - 100, 110);
        items.push({ dt, dot, lb });
      });
    }
    if (ttl) riseIn(c.tl, ttl, 0.05);
    const dl = Math.min(1.6, c.d * 0.35);
    c.tl.fromTo(line, c.port ? { scaleY: 0 } : { scaleX: 0 }, c.port ? { scaleY: 1, duration: dl, ease: 'power2.inOut' } : { scaleX: 1, duration: dl, ease: 'power2.inOut' }, 0.2);
    const step = Math.min(1.2, Math.max(0.3, (c.d - 1.5) / n));
    items.forEach((o, i) => {
      const at = 0.35 + i * step;
      popIn(c.tl, o.dot, at, { from: { y: 0, scale: 0 }, to: { ease: 'back.out(3)' } });
      riseIn(c.tl, o.dt, at + 0.08, -24);
      riseIn(c.tl, o.lb, at + 0.18, 24);
    });
  };

  T.kpis = function (c, p) {
    const its = (p.items || []).slice(0, 4);
    const col = el('div', '', c.box);
    css(col, { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '40px', width: c.cw + 'px' });
    let ttl = null;
    if (p.title) { ttl = el('div', 'h2 chk', col); ttl.textContent = p.title; css(ttl, { width: c.cw + 'px', textAlign: 'center' }); fit(ttl, c.port ? 74 : 70, 38, c.cw, 170); }
    const n = its.length;
    const cols = c.port ? (n > 2 ? 2 : 1) : (n === 4 ? 2 : n);
    const gap = 36;
    const tw = Math.min(c.port ? 900 : 620, (c.cw - gap * (cols - 1)) / cols);
    const grid = el('div', '', col); css(grid, { display: 'grid', gridTemplateColumns: 'repeat(' + cols + ',' + tw + 'px)', gap: gap + 'px' });
    const tiles = its.map(it => {
      const k = el('div', 'card chk', grid); css(k, { padding: '40px 40px 36px', display: 'flex', flexDirection: 'column', gap: '14px' });
      let ic = null;
      if (it.icon) { ic = el('div', '', k, window.iconSVG(it.icon, 3)); css(ic, { width: '70px', height: '70px', color: 'var(--acc)' }); }
      const nb = numBlock(k, it); fit(nb.d, c.port ? 120 : 112, 46, tw - 80, 140);
      const lb = el('div', '', k); lb.textContent = it.label || ''; css(lb, { fontWeight: 600, color: 'var(--fog-200)', lineHeight: 1.2 }); fit(lb, 32, 20, tw - 80, 120);
      return { k, nb, it, ic };
    });
    const tot = col.getBoundingClientRect().height;
    if (tot > c.ch) css(col, { transform: 'scale(' + (c.ch / tot).toFixed(3) + ')' });
    if (ttl) riseIn(c.tl, ttl, 0.05);
    tiles.forEach((o, i) => { const at = 0.25 + i * 0.3; popIn(c.tl, o.k, at, { from: { scale: 0.85 } }); countUp(c, o.nb, o.it, at + 0.1, 1.1); });
  };

  T.chat = function (c, p) {
    const W = c.port ? c.cw : Math.min(1300, c.cw);
    const win = el('div', 'card chk', c.box);
    css(win, { width: W + 'px', borderRadius: '30px', overflow: 'hidden' });
    const bar = el('div', '', win); css(bar, { height: '70px', display: 'flex', alignItems: 'center', gap: '12px', padding: '0 28px', background: 'var(--ink-700)' });
    ['var(--rec)', 'var(--sun)', 'var(--green)'].forEach(col => { const d = el('div', '', bar); css(d, { width: '18px', height: '18px', borderRadius: '50%', background: col }); });
    const tt = el('div', '', bar, '<span style="color:var(--acc)">✦</span> ' + esc(p.app || 'Assistente de IA')); css(tt, { flex: '1', textAlign: 'center', fontWeight: 700, fontSize: '24px', color: 'var(--fog-400)', marginRight: '78px' });
    const body = el('div', '', win); css(body, { padding: '40px', display: 'flex', flexDirection: 'column', gap: '30px' });
    const ub = el('div', '', body); ub.textContent = p.prompt || '';
    css(ub, { alignSelf: 'flex-end', maxWidth: '80%', padding: '24px 32px', borderRadius: '30px 30px 8px 30px', background: 'var(--acc)', color: 'var(--ink-950)', fontWeight: 700, lineHeight: 1.22 });
    fit(ub, 38, 24, W * 0.8 - 80, 220);
    const slot = el('div', '', body); css(slot, { position: 'relative', alignSelf: 'flex-start', maxWidth: '86%' });
    const ab = el('div', '', slot); css(ab, { padding: '26px 32px', borderRadius: '30px 30px 30px 8px', background: 'var(--ink-700)', fontWeight: 500, lineHeight: 1.28 });
    const spans = wordSpans(ab, p.answer || '', p.highlight);
    spans.forEach(s => { s.style.display = 'inline-block'; });
    fit(ab, 36, 22, W * 0.86 - 80, Math.max(140, c.ch - ub.getBoundingClientRect().height - 220));
    const typing = el('div', 'abs', slot); css(typing, { left: '0', top: '0', padding: '30px 34px', borderRadius: '30px 30px 30px 8px', background: 'var(--ink-700)', display: 'flex', gap: '12px' });
    const dots = [0, 1, 2].map(() => { const d = el('div', '', typing); css(d, { width: '16px', height: '16px', borderRadius: '50%', background: 'var(--fog-400)' }); return d; });
    c.tl.fromTo(win, { autoAlpha: 0, y: 70, scale: 0.95 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.6, ease: 'power3.out' }, 0.05);
    c.tl.fromTo(ub, { autoAlpha: 0, x: 60 }, { autoAlpha: 1, x: 0, duration: 0.45, ease: 'power3.out' }, 0.45);
    const tStart = 1.0, tEnd = Math.min(2.0, c.d * 0.35);
    c.tl.fromTo(typing, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.2 }, tStart);
    dots.forEach((d, i) => c.tl.fromTo(d, { y: 0 }, { y: -12, duration: 0.25, repeat: 5, yoyo: true, ease: 'sine.inOut' }, tStart + i * 0.1));
    c.tl.fromTo(ab, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.2 }, tEnd);
    const wrapHide = el('div', 'abs', slot); wrapHide.appendChild(typing); css(wrapHide, { left: '0', top: '0' });
    c.tl.fromTo(wrapHide, { autoAlpha: 1 }, { autoAlpha: 0, duration: 0.15 }, tEnd);
    const st = Math.min(0.07, Math.max(0.02, (c.d - tEnd - 0.8) / Math.max(1, spans.length)));
    c.tl.fromTo(spans, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.12, stagger: st }, tEnd + 0.05);
    hlColor(c.tl, spans, tEnd);
  };

  T.icons = function (c, p) {
    const its = (p.items || []).slice(0, 4);
    const col = el('div', '', c.box);
    css(col, { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '50px', width: c.cw + 'px' });
    let ttl = null;
    if (p.title) { ttl = el('div', 'h2 chk', col); ttl.textContent = p.title; css(ttl, { width: c.cw + 'px', textAlign: 'center' }); fit(ttl, c.port ? 76 : 72, 38, c.cw, 170); }
    const n = its.length;
    const cols = c.port && n > 2 ? 2 : n;
    const sz = c.port ? 250 : Math.min(260, (c.cw - 60 * (n - 1)) / n - 40);
    const cellW = c.port ? (c.cw - 40) / cols : (c.cw - 60 * (n - 1)) / n;
    const grid = el('div', '', col); css(grid, { display: 'grid', gridTemplateColumns: 'repeat(' + cols + ',' + cellW + 'px)', gap: (c.port ? '50px 40px' : '60px') });
    const cells = its.map(it => {
      const g = el('div', '', grid); css(g, { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '28px' });
      const t = iconTile(g, it.icon || 'ia', sz);
      const lb = el('div', 'chk', g); lb.textContent = it.label || ''; css(lb, { width: cellW + 'px', textAlign: 'center', fontWeight: 800, lineHeight: 1.12, letterSpacing: '-.02em' });
      fit(lb, c.port ? 44 : 42, 24, cellW, 110);
      return { t, lb };
    });
    const tot = col.getBoundingClientRect().height;
    if (tot > c.ch) css(col, { transform: 'scale(' + (c.ch / tot).toFixed(3) + ')' });
    if (ttl) riseIn(c.tl, ttl, 0.05);
    const step = Math.min(0.9, Math.max(0.25, (c.d - 1.5) / Math.max(1, n)));
    cells.forEach((o, i) => { const at = 0.25 + i * step; popIn(c.tl, o.t.tile, at); drawOn(c.tl, o.t.svg, at + 0.1, 0.8); riseIn(c.tl, o.lb, at + 0.2, 20); });
  };

  T.question = function (c, p) {
    const bgq = el('div', 'abs', c.cam, '?'); c.cam.insertBefore(bgq, c.box);
    css(bgq, { left: '0', right: '0', top: c.port ? '120px' : '-140px', textAlign: 'center', fontFamily: 'Anton', fontSize: c.port ? '1300px' : '1200px', lineHeight: 1, color: 'rgba(255,255,255,.05)' });
    const col = el('div', '', c.box); css(col, { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '56px' });
    const W = c.port ? c.cw : Math.min(1400, c.cw);
    const b = el('div', 'chk', col); css(b, { width: W + 'px', padding: c.port ? '50px 54px' : '56px 70px', borderRadius: '56px 56px 56px 12px', background: 'var(--fog-50)', color: 'var(--ink-950)', fontWeight: 900, letterSpacing: '-.035em', lineHeight: 1.06, boxShadow: '0 30px 80px rgba(0,0,0,.55)' });
    const spans = wordSpans(b, p.text, p.highlight);
    spans.forEach(s => { s.style.display = 'inline-block'; if (s.classList.contains('hl')) s.style.color = 'var(--acc)'; });
    const opts = (p.options || []).slice(0, 2);
    let row = null, pills = [];
    if (opts.length) {
      row = el('div', '', col); css(row, { display: 'flex', gap: '40px', flexWrap: 'wrap', justifyContent: 'center' });
      pills = opts.map((o, i) => { const q = el('div', 'pill chk', row); q.textContent = o; css(q, { fontSize: c.port ? '52px' : '50px', background: i ? 'var(--acc2)' : 'var(--acc)', color: 'var(--ink-950)', boxShadow: '0 20px 50px rgba(0,0,0,.45)' }); return q; });
    }
    fit(b, c.port ? 92 : 88, 44, W, c.ch - (row ? 190 : 0));
    c.tl.fromTo(bgq, { autoAlpha: 0, scale: 0.8 }, { autoAlpha: 1, scale: 1, duration: 0.8, ease: 'power2.out' }, 0);
    c.tl.fromTo(b, { autoAlpha: 0, scale: 0.85, rotation: -2 }, { autoAlpha: 1, scale: 1, rotation: 0, duration: 0.5, ease: 'back.out(1.6)' }, 0.1);
    c.tl.fromTo(spans, { autoAlpha: 0, y: 24 }, { autoAlpha: 1, y: 0, duration: 0.3, stagger: 0.05, ease: 'power2.out' }, 0.3);
    pills.forEach((q, i) => popIn(c.tl, q, 0.6 + spans.length * 0.05 + i * 0.25));
  };

  T.gauge = function (c, p) {
    const v = Math.max(0, Math.min(100, Number(p.value) || 0));
    const col = el('div', '', c.box); css(col, { display: 'flex', flexDirection: c.port ? 'column' : 'row', alignItems: 'center', gap: c.port ? '40px' : '100px' });
    const S = c.port ? 560 : Math.min(560, c.ch - 20);
    const g = el('div', 'chk', col); css(g, { position: 'relative', width: S + 'px', height: S + 'px', flex: 'none' });
    const r = 220, Cc = 2 * Math.PI * r;
    g.innerHTML = '<svg viewBox="0 0 520 520" style="width:100%;height:100%;transform:rotate(-90deg)"><circle cx="260" cy="260" r="220" fill="none" stroke="#212126" stroke-width="40"/>' +
      '<circle class="arc" cx="260" cy="260" r="220" fill="none" stroke="' + getAcc() + '" stroke-width="40" stroke-linecap="round" stroke-dasharray="' + Cc + ' ' + Cc + '" style="filter:drop-shadow(0 0 14px rgba(var(--acc-rgb),.6))"/></svg>';
    const arc = g.querySelector('.arc');
    const center = el('div', 'abs', g); css(center, { inset: '0', display: 'grid', placeItems: 'center' });
    const nb = numBlock(center, { value: v, suffix: p.suffix == null ? '%' : p.suffix, decimals: p.decimals || 0 });
    fit(nb.d, S * 0.3, 50, S * 0.7, S * 0.4);
    const tx = el('div', '', col); css(tx, { display: 'flex', flexDirection: 'column', gap: '20px', alignItems: c.port ? 'center' : 'flex-start' });
    const tw = c.port ? c.cw : c.cw - S - 100;
    const lb = el('div', 'h2 chk', tx); lb.textContent = p.label || ''; css(lb, { width: tw + 'px', textAlign: c.port ? 'center' : 'left' }); fit(lb, 76, 36, tw, 260);
    let sub = null; if (p.sub) { sub = el('div', 'sub chk', tx); sub.textContent = p.sub; css(sub, { width: tw + 'px', textAlign: c.port ? 'center' : 'left' }); fit(sub, 40, 24, tw, 160); }
    popIn(c.tl, g, 0.05, { from: { y: 0, scale: 0.7 } });
    c.tl.fromTo(arc, { strokeDashoffset: Cc }, { strokeDashoffset: Cc * (1 - v / 100), duration: 1.4, ease: 'power3.out' }, 0.3);
    countUp(c, nb, { value: v }, 0.3, 1.4);
    riseIn(c.tl, lb, 0.35);
    if (sub) riseIn(c.tl, sub, 0.6);
  };

  T.flow = function (c, p) {
    const st = (p.steps || []).slice(0, 4);
    const col = el('div', '', c.box); css(col, { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '50px', width: c.cw + 'px' });
    let ttl = null;
    if (p.title) { ttl = el('div', 'h2 chk', col); ttl.textContent = p.title; css(ttl, { width: c.cw + 'px', textAlign: 'center' }); fit(ttl, c.port ? 74 : 70, 38, c.cw, 170); }
    const row = el('div', '', col); css(row, { display: 'flex', flexDirection: c.port ? 'column' : 'row', alignItems: 'center', gap: '0' });
    const n = st.length || 1;
    const arW = c.port ? 70 : 110;
    const nodeW = c.port ? Math.min(760, c.cw) : (c.cw - arW * (n - 1)) / n;
    const nodes = [], arrows = [];
    st.forEach((s, i) => {
      if (i) {
        const a = el('div', '', row, c.port
          ? '<svg viewBox="0 0 40 70" style="width:40px;height:70px"><path d="M20 4v54M8 46l12 14 12-14" fill="none" stroke="' + getAcc() + '" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
          : '<svg viewBox="0 0 110 40" style="width:110px;height:40px"><path d="M6 20h90M82 8l14 12-14 12" fill="none" stroke="' + getAcc() + '" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>');
        arrows.push(a.querySelector('svg'));
      }
      const k = el('div', 'card chk', row); css(k, { width: nodeW + 'px', padding: '34px 30px', display: 'flex', flexDirection: c.port ? 'row' : 'column', alignItems: 'center', gap: '22px' });
      const label = typeof s === 'string' ? s : s.label;
      const icon = typeof s === 'string' ? null : s.icon;
      let ic = null;
      if (icon) { ic = el('div', '', k, window.iconSVG(icon, 3)); css(ic, { width: '96px', height: '96px', color: 'var(--acc)', flex: 'none' }); }
      const nm = el('div', '', k); css(nm, { fontFamily: 'Anton', fontSize: '34px', color: 'var(--acc2)' }); nm.textContent = String(i + 1).padStart(2, '0');
      if (c.port) k.insertBefore(nm, k.firstChild);
      const lb = el('div', '', k); lb.textContent = label || ''; css(lb, { fontWeight: 800, lineHeight: 1.12, textAlign: c.port ? 'left' : 'center', flex: c.port ? '1' : 'none' });
      fit(lb, 40, 22, nodeW - (c.port ? 230 : 60), 140);
      nodes.push({ k, ic });
    });
    const tot = col.getBoundingClientRect().height;
    if (tot > c.ch) css(col, { transform: 'scale(' + (c.ch / tot).toFixed(3) + ')' });
    if (ttl) riseIn(c.tl, ttl, 0.05);
    const step = Math.min(1.2, Math.max(0.35, (c.d - 1.4) / n));
    nodes.forEach((o, i) => {
      const at = 0.3 + i * step;
      if (i) drawOn(c.tl, arrows[i - 1], at - 0.3, 0.35);
      popIn(c.tl, o.k, at, { from: { scale: 0.8 } });
      if (o.ic) drawOn(c.tl, o.ic.querySelector('svg'), at + 0.1, 0.7);
    });
  };

  T.cta = function (c, p) {
    const col = el('div', '', c.box); css(col, { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '46px' });
    const h = el('div', 'h1 chk', col); css(h, { width: c.cw + 'px' });
    const spans = wordSpans(h, p.text || 'Comenta aí!', p.highlight);
    let sub = null; if (p.sub) { sub = el('div', 'sub chk', col); sub.textContent = p.sub; css(sub, { width: c.cw + 'px' }); fit(sub, 42, 26, c.cw, 120); }
    const kind = p.kind || 'comment';
    const opts = (p.options || []).slice(0, 2);
    const row = el('div', '', col); css(row, { display: 'flex', gap: '36px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'center' });
    let btns = [];
    if (opts.length) {
      btns = opts.map((o, i) => { const b = el('div', 'pill chk', row); b.textContent = o; css(b, { fontSize: '50px', background: i ? 'var(--acc2)' : 'var(--acc)', color: 'var(--ink-950)' }); return b; });
    } else {
      const label = p.button || (kind === 'subscribe' ? 'INSCREVA-SE' : kind === 'like' ? 'CURTIR' : 'COMENTAR');
      const b = el('div', 'pill chk', row, '<span style="width:58px;height:58px;display:inline-block;margin-right:18px">' + window.iconSVG(kind === 'subscribe' ? 'play' : kind === 'like' ? 'heart' : 'chat', 3.4) + '</span>' + esc(label));
      css(b, { fontSize: '50px', background: 'var(--acc)', color: 'var(--ink-950)', boxShadow: '0 0 60px rgba(var(--acc-rgb),.45)' });
      btns = [b];
    }
    fit(h, c.port ? 112 : 120, 50, c.cw, c.ch - 260 - (sub ? 120 : 0));
    wordsIn(c.tl, spans, 0.05);
    hlColor(c.tl, spans, 0.05);
    if (sub) riseIn(c.tl, sub, 0.5);
    btns.forEach((b, i) => popIn(c.tl, b, 0.55 + i * 0.2));
    // cursor que toca o botão
    const tgt = btns[0];
    const br = tgt.getBoundingClientRect(), cr = c.cam.getBoundingClientRect();
    const tx = br.left - cr.left + br.width * 0.92, ty = br.top - cr.top + br.height * 0.95;
    const curw = el('div', 'abs', c.cam); css(curw, { left: '0', top: '0' });
    const cur = el('div', 'abs', curw); css(cur, { left: '0', top: '0', width: '86px', height: '86px', marginLeft: '-43px', marginTop: '-43px', borderRadius: '50%', background: 'rgba(255,255,255,.55)', boxShadow: '0 0 0 5px rgba(255,255,255,.95), 0 12px 30px rgba(0,0,0,.45)' });
    const rip = el('div', 'ring', c.cam); css(rip, { left: tx - 60 + 'px', top: ty - 60 + 'px', width: '120px', height: '120px', borderColor: '#fff' });
    const t0 = Math.min(1.3, c.d * 0.35);
    c.tl.fromTo(cur, { x: STAGE.clientWidth + 100, y: STAGE.clientHeight + 100, autoAlpha: 1 }, { x: tx, y: ty, duration: 0.7, ease: 'power3.out' }, t0);
    c.tl.fromTo(cur, { scale: 1 }, { scale: 0.8, duration: 0.12, yoyo: true, repeat: 1 }, t0 + 0.75);
    c.tl.fromTo(curw, { autoAlpha: 1 }, { autoAlpha: 0, duration: 0.3, immediateRender: false }, t0 + 1.25);
    c.tl.fromTo(rip, { scale: 0.3, autoAlpha: 1 }, { scale: 2.2, autoAlpha: 0, duration: 0.6, ease: 'power2.out' }, t0 + 0.8);
    c.tl.fromTo(row, { scale: 1 }, { scale: 0.94, duration: 0.12, yoyo: true, repeat: 1 }, t0 + 0.75);
  };

  T.__chapter = function (c, p) {
    const wipe = el('div', 'wipe', c.root); const wipe2 = el('div', 'wipe', c.root); css(wipe2, { background: 'var(--acc2)', width: '30%' });
    c.tl.fromTo(wipe, { xPercent: -170 }, { xPercent: 260, duration: 0.6, ease: 'power3.inOut' }, 0);
    c.tl.fromTo(wipe2, { xPercent: -400 }, { xPercent: 700, duration: 0.6, ease: 'power3.inOut' }, 0.05);
    const row = el('div', '', c.box); css(row, { display: 'flex', flexDirection: c.port ? 'column' : 'row', alignItems: 'center', gap: c.port ? '30px' : '80px' });
    const num = el('div', 'chapnum chk', row); num.textContent = String(p.num || 1).padStart(2, '0'); css(num, { fontSize: c.port ? '380px' : '420px' });
    const col = el('div', '', row); css(col, { display: 'flex', flexDirection: 'column', gap: '30px', alignItems: c.port ? 'center' : 'flex-start' });
    const eb = el('div', 'eyebrow chk', col, '<span class="dot"></span>Capítulo ' + (p.num || 1) + (p.total ? ' de ' + p.total : ''));
    const tw = c.port ? c.cw : c.cw - 520;
    const h = el('div', 'h1 chk', col); css(h, { width: tw + 'px', textAlign: c.port ? 'center' : 'left' });
    const spans = wordSpans(h, p.title || '', p.highlight);
    fit(h, c.port ? 110 : 116, 48, tw, c.port ? 420 : 520);
    const ln = el('div', '', col); css(ln, { width: '220px', height: '10px', borderRadius: '10px', background: 'var(--acc)', transformOrigin: c.port ? '50% 50%' : '0 50%' });
    c.tl.fromTo(num, { autoAlpha: 0, x: c.port ? 0 : -90, y: c.port ? -60 : 0 }, { autoAlpha: 1, x: 0, y: 0, duration: 0.6, ease: 'power3.out' }, 0.25);
    popIn(c.tl, eb, 0.35);
    wordsIn(c.tl, spans, 0.45, 0.05);
    c.tl.fromTo(ln, { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: 'power3.inOut' }, 0.7);
  };

  // ---------- construção ----------
  function buildBg(stage, port) {
    const bg = el('div', '', stage); bg.id = 'bg';
    const W = ST.w, H = ST.h;
    const mk = (color, a, size) => { const o = el('div', 'orb', bg); css(o, { width: size + 'px', height: size + 'px', background: 'radial-gradient(circle, ' + color + ' 0%, transparent 62%)', opacity: a }); return { o, size }; };
    BG.o1 = mk(ST.theme.accent, 0.34, Math.max(W, H) * 0.75);
    BG.o2 = mk(ST.theme.accent2, 0.10, Math.max(W, H) * 0.6);
    BG.o3 = mk('#4dc3ff', 0.10, Math.max(W, H) * 0.55);
    BG.grid = el('div', '', bg); BG.grid.id = 'grid';
    BG.grain = el('div', '', bg); BG.grain.id = 'grain';
    css(BG.grain, { backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")" });
    BG.vig = el('div', '', bg); BG.vig.id = 'vig';
  }
  function updateBg(t) {
    const W = ST.w, H = ST.h;
    const P = (o, cx, cy, ax, ay, fx, fy, ph) => {
      const x = cx * W + Math.sin(t * fx + ph) * ax * W - o.size / 2;
      const y = cy * H + Math.cos(t * fy + ph) * ay * H - o.size / 2;
      o.o.style.transform = 'translate3d(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px,0)';
    };
    P(BG.o1, 0.2, 0.18, 0.1, 0.08, 0.13, 0.11, 0);
    P(BG.o2, 0.86, 0.78, 0.08, 0.1, 0.09, 0.12, 1.7);
    P(BG.o3, 0.75, 0.1, 0.1, 0.06, 0.07, 0.1, 3.1);
    BG.grid.style.transform = 'translate3d(' + (-(t * 9) % 46).toFixed(2) + 'px,' + (-(t * 5) % 46).toFixed(2) + 'px,0)';
  }
  function buildHud(stage) {
    const hud = el('div', '', stage); hud.id = 'hud';
    HUD.chip = el('div', '', hud, '<span class="dot"></span><span class="t"></span>'); HUD.chip.id = 'chip';
    HUD.chipT = HUD.chip.querySelector('.t');
    HUD.credit = el('div', '', hud); HUD.credit.id = 'credit';
    HUD.brand = el('div', '', hud); HUD.brand.id = 'brand'; HUD.brand.textContent = ST.brand || '';
    if (ST.brandLogo) {  // marca d'água discreta (logo do canal)
      HUD.logo = el('img', '', hud); HUD.logo.id = 'brandlogo'; HUD.logo.src = ST.brandLogo; HUD.logo.alt = '';
      if (ST.brandLogoOpacity != null) HUD.logo.style.opacity = ST.brandLogoOpacity;
    }
    HUD.src = el('div', '', hud); HUD.src.id = 'src';
    HUD.cap = el('div', '', hud); HUD.cap.id = 'cap';
    HUD.capin = el('div', '', HUD.cap); HUD.capin.id = 'capin';
    HUD.prog = el('div', '', hud); HUD.prog.id = 'prog';
    HUD.fill = el('div', '', HUD.prog); HUD.fill.id = 'progfill';
    (ST.segments || []).forEach(s => { if (s.kind === 'chapter' && s.start > 0.5) { const k = el('div', 'tick', HUD.prog); k.style.left = (100 * s.start / ST.duration).toFixed(3) + '%'; } });
    HUD.lastCap = -2; HUD.lastWord = -2; HUD.lastChip = null; HUD.lastSrc = null;
  }
  let SEGS_N = 0;
  function quadro(v, k) { return v.dir + 'q' + String(k + 1).padStart(4, '0') + '.jpg'; }
  // vídeo de fundo: troca o quadro e espera decodificar (o render quadro a quadro aguarda a promessa)
  function quadroVideo(seg, lt) {
    const v = seg.vid, k = Math.max(0, Math.min(v.n - 1, Math.floor(lt * v.fps)));
    if (k === v.k) return null;
    v.k = k; v.img.src = quadro(v, k);
    return v.img.decode().catch(() => null);
  }
  function makeSeg(seg) {
    const root = el('div', 'seg', SCN);
    const P = seg.params || {};
    let photoImg = null, photo = null;
    if (P._photo || P._video) {  // foto ou vídeo de fundo da cena (licença livre; crédito em P._credit)
      photo = el('div', 'photo', root);
      photoImg = el('img', '', photo); photoImg.alt = '';
      if (P._video) { seg.vid = { img: photoImg, dir: P._video.dir, n: P._video.n, fps: P._video.fps || 30, k: -1 }; photoImg.src = quadro(seg.vid, 0); }
      else photoImg.src = P._photo;
      el('div', 'tint', photo);
    }
    const cam = el('div', 'cam', root);
    const box = el('div', 'box', cam);
    root.style.visibility = 'visible';
    const tl = gsap.timeline({ paused: true });
    const r = box.getBoundingClientRect();
    const c = { root, cam, box, tl, d: seg.dur, port: ST.port, cw: r.width, ch: r.height, counters: [], seg };
    const fn = seg.kind === 'chapter' ? T.__chapter : (T[seg.template] || T.headline);
    try { fn(c, seg.kind === 'chapter' ? seg : (seg.params || {})); }
    catch (err) { box.innerHTML = ''; c.counters = []; T.headline(c, { text: (seg.params && (seg.params.text || seg.params.title)) || seg.text || '' }); seg.error = String(err); }
    tl.fromTo(cam, { scale: 1 }, { scale: seg.kind === 'chapter' ? 1.06 : 1.04, duration: seg.dur, ease: 'none' }, 0);
    if (photoImg) {  // Ken Burns: zoom e deslize lentos (vídeo: mais sutil), direção alternada por cena
      const dir = (SEGS_N++ % 2) ? 1 : -1, v = P._video ? 0.4 : 1;
      tl.fromTo(photoImg, { scale: 1 + 0.06 * v, xPercent: -1.6 * dir * v }, { scale: 1 + 0.16 * v, xPercent: 1.6 * dir * v, duration: seg.dur, ease: 'none' }, 0);
      tl.fromTo(photo, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3, ease: 'power1.out' }, 0);
    }
    if (seg.dur > 1.2) tl.fromTo(box, { autoAlpha: 1, y: 0, filter: 'blur(0px)' }, { autoAlpha: 0, y: -26, filter: 'blur(8px)', duration: 0.26, ease: 'power2.in', immediateRender: false }, seg.dur - 0.26);
    tl.seek(0, false);
    root.style.visibility = 'hidden';
    seg.el = root; seg.tl = tl; seg.counters = c.counters; seg.vis = false;
  }
  function updateCounters(seg, lt) {
    for (const k of seg.counters) {
      let pr = (lt - k.at) / k.dur;
      pr = pr < 0 ? 0 : pr > 1 ? 1 : pr;
      const e = 1 - Math.pow(1 - pr, 3);
      const v = k.from + (k.to - k.from) * e;
      k.el.textContent = fmt(pr >= 1 ? k.to : v, k.dec);
    }
  }
  function findIdx(arr, t) { // último índice com start <= t
    let lo = 0, hi = arr.length - 1, ans = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (arr[m].start <= t) { ans = m; lo = m + 1; } else hi = m - 1; }
    return ans;
  }
  function updateHud(t, seg) {
    const D = ST.duration;
    HUD.fill.style.width = (100 * Math.min(1, t / D)).toFixed(3) + '%';
    const chip = seg ? (seg.kind === 'chapter' ? '' : (seg.chapterTitle || '')) : '';
    if (chip !== HUD.lastChip) { HUD.chipT.textContent = chip; HUD.chip.style.visibility = chip ? 'visible' : 'hidden'; HUD.lastChip = chip; }
    const src = seg && seg.source ? 'Fonte: ' + seg.source : '';
    if (src !== HUD.lastSrc) { HUD.src.textContent = src; HUD.lastSrc = src; }
    const c0 = seg && seg.params && seg.params._credit ? String(seg.params._credit) : '';
    const cr = !c0 || /^(Foto|Vídeo):/.test(c0) ? c0 : 'Foto: ' + c0;
    if (HUD.credit && cr !== HUD.lastCr) { HUD.credit.textContent = cr; HUD.lastCr = cr; }
    // legendas
    const caps = ST.captions || [];
    let gi = -1;
    if (ST.showCaptions !== false) {
      const k = findIdx(caps, t);
      if (k >= 0 && t < caps[k].end) gi = k;
    }
    let wi = -1;
    if (gi >= 0) { const ws = caps[gi].words; for (let i = 0; i < ws.length; i++) if (ws[i].s <= t) wi = i; }
    if (gi !== HUD.lastCap || wi !== HUD.lastWord) {
      if (gi < 0) { HUD.cap.style.visibility = 'hidden'; }
      else {
        HUD.cap.style.visibility = 'visible';
        HUD.capin.innerHTML = caps[gi].words.map((w, i) => '<span class="' + (i === wi ? 'on' : i > wi ? 'fut' : '') + '">' + esc(w.w) + '</span>').join('');
      }
      HUD.lastCap = gi; HUD.lastWord = wi;
    }
    if (gi >= 0) {
      const pr = Math.min(1, Math.max(0, (t - caps[gi].start) / 0.14));
      HUD.capin.style.transform = 'translateY(' + ((1 - pr) * 14).toFixed(1) + 'px) scale(' + (0.94 + 0.06 * pr).toFixed(3) + ')';
    }
  }

  window.renderAt = function (t) {
    updateBg(t);
    const segs = ST.segments;
    let active = null, espera = null;
    for (const s of segs) {
      const on = t >= s.start && (t < s.start + s.dur || (s === segs[segs.length - 1] && t <= s.start + s.dur + 1));
      if (on) { active = s; const lt = Math.min(t - s.start, s.dur); s.tl.seek(lt, false); updateCounters(s, lt); if (s.vid) espera = quadroVideo(s, lt); }
      if (on !== s.vis) { s.el.style.visibility = on ? 'visible' : 'hidden'; s.vis = on; }
    }
    updateHud(t, active);
    moveLogo(t);
    const m3 = modulo3d();
    if (m3 && m3.on) {
      // foto/vídeo cobrem a tela: sem desenhar o 3D (é o que mais pesa no render em CPU)
      const coberto = !!(active && active.params && (active.params._photo || active.params._video));
      const cv = document.getElementById('gl3d');
      if (cv && cv.style.visibility !== (coberto ? 'hidden' : 'visible')) cv.style.visibility = coberto ? 'hidden' : 'visible';
      if (!coberto) m3.render(t, active, active ? segs.indexOf(active) : 0);
    }
    return espera ? espera.then(() => true) : true;
  };

  /* Marca d'água que troca de canto ao longo do vídeo (com fade), longe da legenda e dos botões do app. */
  function moveLogo(t) {
    if (!HUD.logo) return;
    const P = ST.brandLogoPeriod || 9, F = 0.45;
    const spots = ST.port
      ? [{ right: 44, top: 54 }, { left: 44, top: 54 }, { left: 44, top: ST.scene3d ? 1170 : 1470 }]
      : [{ right: 56, top: 40 }, { left: 56, top: 110 }, { right: 56, top: 880 }];
    const k = Math.floor(t / P) % spots.length, lt = t - Math.floor(t / P) * P;
    if (HUD.logoK !== k) { const s = spots[k]; css(HUD.logo, { left: s.left != null ? s.left + 'px' : 'auto', right: s.right != null ? s.right + 'px' : 'auto', top: s.top + 'px' }); HUD.logoK = k; }
    const base = ST.brandLogoOpacity != null ? ST.brandLogoOpacity : 0.5;
    const f = t < F ? 1 : Math.min(1, lt / F, (P - lt) / F);
    HUD.logo.style.opacity = (base * Math.max(0, f)).toFixed(3);
  }

  window.boot = async function (data) {
    ST = data;
    ST.theme = Object.assign({ accent: '#ff4f12', accent2: '#d4ff3a' }, data.theme || {});
    ST.port = data.h > data.w;
    const root = document.documentElement;
    applyTheme(root);
    STAGE = document.getElementById('stage');
    css(STAGE, { width: data.w + 'px', height: data.h + 'px' });
    STAGE.className = (ST.port ? 'port' : 'land') + (ST.brandLogo ? ' has-logo' : '');
    await document.fonts.load('900 60px Figtree'); await document.fonts.load('700 60px Figtree'); await document.fonts.load('500 60px Figtree');
    await document.fonts.load('60px Anton'); await document.fonts.ready;
    buildBg(STAGE, ST.port);
    if (ST.scene3d && modulo3d() && window.THREE) { STAGE.classList.add('mode3d'); await modulo3d().init(STAGE, ST); }
    const fotos = [...new Set((ST.segments || []).map(s => s.params && s.params._photo).filter(Boolean))];
    if (fotos.length) {
      STAGE.classList.add('mode-photo');
      await Promise.all(fotos.map(u => { const im = new Image(); im.src = u; return im.decode().catch(() => null); }));
    }
    SCN = el('div', '', STAGE); css(SCN, { position: 'absolute', inset: '0' });
    ST.segments.forEach(makeSeg);
    buildHud(STAGE);
    if (HUD.logo) { try { await HUD.logo.decode(); } catch (e) { HUD.logo.remove(); HUD.logo = null; } }
    window.renderAt(0);
    return { ok: true, n: ST.segments.length, errors: ST.segments.filter(s => s.error).map(s => [s.id, s.error]) };
  };

  /* CRIVO 5 automático: tudo dentro da área segura, nada vazando da caixa de conteúdo. */
  window.audit = function () {
    const issues = [];
    const W = ST.w, H = ST.h, m = 14;
    const capR = () => HUD.capin.getBoundingClientRect();
    ST.segments.forEach((s, i) => {
      const t = s.start + Math.max(0.05, Math.min(s.dur - 0.32, s.dur * 0.82));
      window.renderAt(t);
      const box = s.el.querySelector('.box').getBoundingClientRect();
      const tol = 40;
      s.el.querySelectorAll('.chk').forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) return;
        const txt = (e.textContent || '').trim().slice(0, 50);
        if (r.left < m || r.top < m || r.right > W - m || r.bottom > H - m) issues.push({ seg: s.id, tipo: 'fora_da_tela', txt });
        else if (r.left < box.left - tol || r.right > box.right + tol || r.top < box.top - tol || r.bottom > box.bottom + tol) issues.push({ seg: s.id, tipo: 'vaza_da_area', txt });
        if (e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflow === 'hidden') issues.push({ seg: s.id, tipo: 'texto_cortado', txt });
      });
      if (HUD.cap.style.visibility === 'visible') {
        const cr = capR();
        if (cr.bottom > (ST.port ? 1550 : H - 60)) issues.push({ seg: s.id, tipo: 'legenda_no_rodape', txt: HUD.capin.textContent.slice(0, 40) });
        s.el.querySelectorAll('.chk').forEach(e => {
          const r = e.getBoundingClientRect();
          const ov = Math.max(0, Math.min(r.right, cr.right) - Math.max(r.left, cr.left)) * Math.max(0, Math.min(r.bottom, cr.bottom) - Math.max(r.top, cr.top));
          if (ov > 600 && getComputedStyle(e).visibility !== 'hidden' && parseFloat(getComputedStyle(e).opacity) > 0.2) issues.push({ seg: s.id, tipo: 'sobre_legenda', txt: (e.textContent || '').trim().slice(0, 40) });
        });
      }
    });
    return issues;
  };

  // ---------- thumbnail ----------
  window.bootThumb = async function (data) {
    ST = { w: data.w, h: data.h, theme: Object.assign({ accent: '#ff4f12', accent2: '#d4ff3a' }, data.theme || {}), segments: [], duration: 1 };
    const port = data.h > data.w;
    const root = document.documentElement;
    applyTheme(root);
    STAGE = document.getElementById('stage');
    css(STAGE, { width: data.w + 'px', height: data.h + 'px' });
    STAGE.className = port ? 'port' : 'land';
    await document.fonts.load('900 60px Figtree'); await document.fonts.load('60px Anton'); await document.fonts.ready;
    buildBg(STAGE, port); updateBg(4.2);
    const M = 40, W = data.w, H = data.h;
    const icS = port ? 560 : Math.round(H * 0.6);
    const icX = port ? (W - icS) / 2 : W - M - icS - 30, icY = port ? 210 : (H - icS) / 2;
    const rw = el('div', 'abs', STAGE); css(rw, { left: (icX + icS / 2 - 1300) + 'px', top: (icY + icS / 2 - 1300) + 'px', width: '2600px', height: '2600px' });
    const rays = el('div', 'rays', rw); css(rays, { left: '0', top: '0', margin: '0', transform: 'rotate(8deg)', opacity: 1.6 });
    const glow = el('div', 'abs', STAGE); css(glow, { left: (icX - icS * 0.4) + 'px', top: (icY - icS * 0.4) + 'px', width: icS * 1.8 + 'px', height: icS * 1.8 + 'px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(var(--acc-rgb),.55), transparent 60%)' });
    const icw = el('div', 'abs', STAGE); css(icw, { left: icX + 'px', top: icY + 'px', width: icS + 'px', height: icS + 'px', transform: 'rotate(-6deg)' });
    const tile = el('div', 'tile', icw, window.iconSVG(data.icon || 'ia', 2.6));
    css(tile.querySelector('svg'), { filter: 'drop-shadow(0 0 26px rgba(var(--acc-rgb),.8))' });
    const txW = port ? W - 2 * M : icX - M - 40;
    const col = el('div', 'abs', STAGE); css(col, { left: M + 'px', width: txW + 'px', display: 'flex', flexDirection: 'column', gap: port ? '22px' : '14px', alignItems: port ? 'center' : 'flex-start' });
    const lines = (data.lines || []).slice(0, 2);
    const lineEls = lines.map((ln, i) => {
      const d = el('div', 'thumbtxt chk', col);
      if (ln.hl) { d.innerHTML = '<span class="thumbhl">' + esc(ln.text) + '</span>'; } else d.textContent = ln.text;
      fit(d, port ? 170 : 128, 40, txW, port ? 200 : 150);
      css(d, { width: 'auto' });
      return d;
    });
    let nb = null;
    if (data.number) {
      nb = el('div', 'num chk', col); nb.textContent = data.number;
      css(nb, { color: 'var(--acc2)', textShadow: '0 0 40px rgba(212,255,58,.45), 0 8px 0 rgba(0,0,0,.4)' });
      fit(nb, port ? 330 : 210, 60, txW, port ? 330 : 220);
    }
    let lbl = null;
    if (data.numberLabel) { lbl = el('div', 'chk', col); lbl.textContent = data.numberLabel; css(lbl, { fontWeight: 800, fontSize: port ? '58px' : '40px', color: 'var(--fog-200)', whiteSpace: 'nowrap' }); fit(lbl, port ? 58 : 40, 22, txW, 80); }
    const ch = col.getBoundingClientRect().height;
    css(col, { top: (port ? icY + icS + 60 : Math.max(M, (H - ch) / 2)) + 'px' });
    if (port) { const avail = H - M - (icY + icS + 60); if (ch > avail) css(col, { top: (H - M - ch) + 'px' }); }
    // auditoria CRIVO 7
    const issues = [];
    const ir = tile.getBoundingClientRect();
    STAGE.querySelectorAll('.chk').forEach(e => {
      const r = e.getBoundingClientRect();
      if (r.left < M - 1 || r.top < M - 1 || r.right > W - M + 1 || r.bottom > H - M + 1) issues.push({ tipo: 'fora_da_margem', txt: e.textContent });
      const ov = Math.max(0, Math.min(r.right, ir.right) - Math.max(r.left, ir.left)) * Math.max(0, Math.min(r.bottom, ir.bottom) - Math.max(r.top, ir.top));
      if (ov > 400) issues.push({ tipo: 'texto_atras_do_icone', txt: e.textContent });
    });
    const main = lineEls[0] ? parseFloat(lineEls[0].style.fontSize) : 0;
    return { issues, mainFont: main, mainFontAt25: main * 0.25 };
  };
})();
