from __future__ import annotations

DOM_SCRIPT = """
() => Array.from(document.querySelectorAll('div, aside, section, iframe')).map((el) => ({
  id: el.id || null,
  class_name: typeof el.className === 'string' ? el.className.slice(0, 300) : null,
  aria_label: el.getAttribute('aria-label'),
  text: (el.innerText || '').trim().slice(0, 160),
  width: Math.round(el.getBoundingClientRect().width),
  height: Math.round(el.getBoundingClientRect().height),
  visible: (() => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; })(),
  iframe_src: el.tagName === 'IFRAME' ? el.getAttribute('src') : null
})).filter(x => x.visible)
"""
