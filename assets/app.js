(() => {
  const DATA_URL = 'data/posts.json';
  const REFRESH_MS = 5 * 60 * 1000;
  const grid = document.getElementById('grid');
  const empty = document.getElementById('empty');
  const q = document.getElementById('q');
  const updated = document.getElementById('updated');
  const chips = [...document.querySelectorAll('.chip')];
  document.getElementById('yr').textContent = new Date().getFullYear();

  let posts = [], filter = 'all', updatedAt = null;

  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = s => s ? Number(String(s).replace(/,/g, '')) : NaN;
  const inr = n => '₹' + n.toLocaleString('en-IN');

  function ago(iso) {
    if (!iso) return '';
    const s = Math.max(0, (Date.now() - new Date(iso)) / 1000);
    if (s < 60) return 'just now';
    const m = s / 60; if (m < 60) return `${Math.floor(m)} min ago`;
    const h = m / 60; if (h < 24) return `${Math.floor(h)} hr ago`;
    const d = h / 24; if (d < 7) return `${Math.floor(d)} day${d >= 2 ? 's' : ''} ago`;
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  }

  // "Loot : Foo Bar @299." -> { badge: 'Loot', title: 'Foo Bar' }
  function splitTitle(raw) {
    let t = raw || '', badge = '';
    const m = t.match(/^\s*([^:|]{2,22}?)\s*[:|]\s+(.{6,})$/);
    if (m && m[1].split(/\s+/).length <= 3 && !/^\d+$/.test(m[1].trim())) { badge = m[1].trim(); t = m[2]; }
    t = t.replace(/\s*(⚡️|⚡)?\s*@\s*(₹|rs\.?)?\s*[\d,]+.*$/i, '').replace(/[\s.:|-]+$/, '').trim();
    if (badge && /^(amazon|flipkart|✅)$/i.test(badge)) badge = '';
    return { badge, title: t || raw };
  }

  function card(p, i) {
    const store = p.store || 'other';
    const { badge, title } = splitTitle(p.title);
    const price = num(p.price), mrp = num(p.mrp);
    const off = price && mrp && mrp > price ? Math.round((1 - price / mrp) * 100) : 0;
    const priceHtml = price
      ? `<span class="price">${inr(price)}</span>${mrp > price ? `<span class="mrp">${inr(mrp)}</span>` : ''}${off ? `<span class="off">${off}% off</span>` : ''}`
      : `<span class="noprice">See price on store</span>`;
    const storeName = store === 'amazon' ? 'Amazon' : store === 'flipkart' ? 'Flipkart' : 'Deal';
    const ph = `<div class="ph ${store}"><span class="ic">${store === 'flipkart' ? '🛍️' : store === 'amazon' ? '📦' : '🔥'}</span>${price ? `<span class="pp">${inr(price)}</span>` : ''}<span class="st">${storeName} deal</span></div>`;
    const img = p.image
      ? `<img src="${esc(p.image)}" alt="${esc(title)}" loading="${i < 8 ? 'eager' : 'lazy'}" decoding="async" referrerpolicy="no-referrer" data-ph="1">`
      : ph;
    const buy = p.buy_url
      ? `<a class="btn-buy ${store}" href="${esc(p.buy_url)}" target="_blank" rel="noopener nofollow sponsored">Buy Now<span aria-hidden="true">→</span></a>`
      : `<a class="btn-buy other" href="${esc(p.url)}" target="_blank" rel="noopener">Open deal<span aria-hidden="true">→</span></a>`;
    const more = (p.store_links?.length > 1 || (p.text || '').split('\n').filter(Boolean).length > 2)
      ? `<details class="more"><summary>Full deal details</summary><div class="txt">${p.html || esc(p.text)}</div></details>` : '';
    return `<article class="card" style="animation-delay:${Math.min(i, 12) * 25}ms">
      <div class="media">${img}${badge ? `<span class="badge">${esc(badge)}</span>` : ''}<span class="store ${store}">${storeName}</span><time class="when" datetime="${esc(p.date)}">${ago(p.date)}</time></div>
      <div class="body">
        <h3 class="title" title="${esc(p.title)}">${esc(title)}</h3>
        <div class="priceRow">${priceHtml}</div>
        ${more}
        ${buy}
        <div class="meta"><a href="${esc(p.url)}" target="_blank" rel="noopener">View on Telegram ↗</a></div>
      </div>
    </article>`;
  }

  function render() {
    const term = q.value.trim().toLowerCase();
    const list = posts.filter(p =>
      (filter === 'all' || p.store === filter) &&
      (!term || (p.text || '').toLowerCase().includes(term)));
    grid.innerHTML = list.map(card).join('');
    empty.hidden = list.length > 0;
    grid.querySelectorAll('img[data-ph]').forEach(im => im.addEventListener('error', () => {
      const p = posts.find(x => x.image === im.getAttribute('src'));
      im.replaceWith(Object.assign(document.createElement('div'), { className: `ph ${p?.store || 'other'}`, innerHTML: '<span class="ic">🔥</span><span class="st">Hot deal</span>' }));
    }, { once: true }));
    chips.forEach(c => {
      const f = c.dataset.f;
      const n = f === 'all' ? posts.length : posts.filter(p => p.store === f).length;
      c.innerHTML = `${c.textContent.replace(/\s*\d+$/, '')}<span class="n">${n}</span>`;
    });
  }

  function setUpdated() {
    if (updatedAt) updated.textContent = `${posts.length} live deals · updated ${ago(updatedAt)}`;
  }

  async function load() {
    try {
      const r = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: 'no-store' });
      const d = await r.json();
      posts = d.posts || []; updatedAt = d.updated_at;
      render(); setUpdated();
    } catch (e) {
      updated.textContent = 'Could not load deals right now. Check our Telegram!';
      grid.innerHTML = '';
    }
  }

  let t; q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(render, 120); });
  chips.forEach(c => c.addEventListener('click', () => {
    filter = c.dataset.f;
    chips.forEach(x => { x.classList.toggle('active', x === c); x.setAttribute('aria-selected', x === c); });
    render();
  }));
  load();
  setInterval(load, REFRESH_MS);
  setInterval(setUpdated, 60 * 1000);
})();
