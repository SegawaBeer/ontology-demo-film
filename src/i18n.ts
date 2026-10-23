import { translateEnglish } from './translations';

export type Language = 'zh' | 'en';
const params = new URLSearchParams(location.search);
let language: Language = params.get('lang') === 'en' ? 'en' : 'zh';
try { if (!params.get('lang')) language = localStorage.getItem('turbofan-language') === 'en' ? 'en' : 'zh'; } catch { /* Storage is optional. */ }

const sources = new WeakMap<Node, { source: string; rendered: string }>();
const attributes = new WeakMap<Element, Map<string, { source: string; rendered: string }>>();
const listeners = new Set<() => void>();
export const getLanguage = () => language;
export const onLanguage = (listener: () => void) => { listeners.add(listener); return () => listeners.delete(listener); };
export const t = (source: string) => (language === 'zh' ? source : translateEnglish(source));

function translateNode(node: Node) {
  if (node instanceof Element && node.closest('script,style,[data-language-control]')) return;
  if (node.nodeType === Node.TEXT_NODE) {
    if (node.parentElement?.closest('script,style,[data-language-control]')) return;
    const value = node.nodeValue ?? '';
    const old = sources.get(node);
    const source = old && old.rendered === value ? old.source : value;
    const rendered = t(source);
    sources.set(node, { source, rendered });
    if (value !== rendered) node.nodeValue = rendered;
  } else {
    if (node instanceof Element) {
      const map = attributes.get(node) ?? new Map();
      attributes.set(node, map);
      for (const name of ['aria-label', 'title', 'alt', 'placeholder']) {
        const value = node.getAttribute(name);
        if (value === null) continue;
        const old = map.get(name);
        const source = old && old.rendered === value ? old.source : value;
        const rendered = t(source);
        map.set(name, { source, rendered });
        if (value !== rendered) node.setAttribute(name, rendered);
      }
    }
    node.childNodes.forEach(translateNode);
  }
}

const observer = new MutationObserver(records => {
  observer.disconnect();
  for (const record of records) {
    if (record.type === 'childList') record.addedNodes.forEach(translateNode);
    else translateNode(record.target);
  }
  observe();
});
function observe() {
  observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['aria-label', 'title', 'alt', 'placeholder'] });
}

export function setLanguage(next: Language) {
  language = next;
  observer.disconnect();
  try { localStorage.setItem('turbofan-language', next); } catch { /* Keep in-memory setting. */ }
  const url = new URL(location.href);
  url.searchParams.set('lang', next);
  history.replaceState(null, '', url);
  document.documentElement.lang = next === 'zh' ? 'zh-CN' : 'en';
  document.title = next === 'zh' ? '涡轮风扇发动机 | 交互模型' : 'Turbofan engine | Interactive model';
  translateNode(document.body);
  document.querySelectorAll<HTMLButtonElement>('[data-language]').forEach(button =>
    button.setAttribute('aria-pressed', String(button.dataset.language === next)));
  listeners.forEach(listener => listener());
  observe();
}

export function languageControl() {
  const control = document.createElement('div');
  control.className = 'language-control';
  control.dataset.languageControl = '';
  control.innerHTML = '<button type="button" data-language="zh" aria-label="切换到中文">中文</button><button type="button" data-language="en" aria-label="Switch to English">EN</button>';
  control.querySelectorAll<HTMLButtonElement>('button').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.language === language));
    button.onclick = () => setLanguage(button.dataset.language as Language);
  });
  return control;
}
