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
        const stable = [...node.classList].filter(c => /^[a-zA-Z0-9_-]+$/.test(c)).slice(0, 2);
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
      x: Math.round(r.x),
      y: Math.round(r.y),
      visible: r.width > 0 && r.height > 0,
      iframe_src: el.tagName === 'IFRAME' ? el.getAttribute('src') : null,
      selector: selectorFor(el)
    };
  }).filter(x => x.visible && x.width >= 20 && x.height >= 20)
}
"""
