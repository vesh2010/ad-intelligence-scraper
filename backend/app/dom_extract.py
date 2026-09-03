from __future__ import annotations

DOM_SCRIPT = """
() => {
  const selectorFor = (el) => {
    if (el.id) return `#${CSS.escape(el.id)}`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      if (node.classList.length) {
        const stable = [...node.classList]
          .filter(c => /^[a-zA-Z0-9_-]+$/.test(c))
          .slice(0, 2);
        if (stable.length) part += '.' + stable.map(CSS.escape).join('.');
      }
      const parent = node.parentElement;
      if (parent) {
        const siblings = [...parent.children].filter(x => x.tagName === node.tagName);
        if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(' > ');
  };

  return Array.from(document.querySelectorAll('div, aside, section, iframe')).map((el) => {
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    const hrefs = Array.from(el.querySelectorAll('a[href]')).map(a => a.href).slice(0, 10);
    const image_urls = Array.from(el.querySelectorAll('img[src]')).map(img => img.src).slice(0, 10);
    const video_urls = [
      ...Array.from(el.querySelectorAll('video[src]')).map(v => v.src),
      ...Array.from(el.querySelectorAll('video source[src]')).map(s => s.src)
    ].filter(Boolean).slice(0, 10);
    const audio_urls = [
      ...Array.from(el.querySelectorAll('audio[src]')).map(a => a.src),
      ...Array.from(el.querySelectorAll('audio source[src]')).map(s => s.src)
    ].filter(Boolean).slice(0, 10);
    const video_posters = Array.from(el.querySelectorAll('video[poster]'))
      .map(v => v.poster || v.getAttribute('poster')).filter(Boolean).slice(0, 5);
    const dataset = {};
    for (const key of ['ad', 'adClient', 'adSlot', 'adUnit', 'googleQueryId']) {
      const attr = `data-${key.replace(/[A-Z]/g, m => '-' + m.toLowerCase())}`;
      const value = el.getAttribute(attr);
      if (value) dataset[attr] = value;
    }
    const viewport_x = Math.round(r.x);
    const viewport_y = Math.round(r.y);

    return {
      tag: el.tagName.toLowerCase(),
      id: el.id || null,
      class_name: typeof el.className === 'string' ? el.className.slice(0, 300) : null,
      aria_label: el.getAttribute('aria-label'),
      role: el.getAttribute('role'),
      title: el.getAttribute('title'),
      text: (el.innerText || '').trim().slice(0, 240),
      width: Math.round(r.width),
      height: Math.round(r.height),
      x: Math.round(viewport_x + window.scrollX),
      y: Math.round(viewport_y + window.scrollY),
      viewport_x,
      viewport_y,
      visible: r.width > 0 && r.height > 0,
      iframe_src: el.tagName === 'IFRAME' ? el.getAttribute('src') : null,
      hrefs,
      image_urls,
      video_urls,
      audio_urls,
      video_posters,
      position_mode: style.position || null,
      z_index: style.zIndex || null,
      dataset,
      selector: selectorFor(el)
    };
  }).filter(x => x.visible && x.width >= 20 && x.height >= 20)
}
"""
