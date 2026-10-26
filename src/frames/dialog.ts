// Dialog column markup. Each frame passes the turns visible at that moment.
export type Turn =
  | { type: 'ask'; dept: string; time: string; text: string; past?: boolean; changed?: string; answer?: string; steps?: string[]; live?: number }
  | { type: 'alert'; dept: string; time: string; text: string; detail: string };

export function renderDialog(root: HTMLElement, turns: Turn[], trace: { left: string; right: string }) {
  const html = turns.map(turn => {
    if (turn.type === 'alert') {
      return `<div class="alert"><div class="meta"><b>${turn.dept}</b><span>${turn.time}</span><span>自动提示</span></div><p>${turn.text}</p><small>${turn.detail}</small></div>`;
    }
    const steps = turn.steps?.length
      ? `<div class="steps">${turn.steps.map((s, i) => `<div class="step${turn.live === i ? ' live' : ''}"><span class="n">${String(i + 1).padStart(2, '0')}</span><span class="line">${s}</span></div>`).join('')}</div>`
      : '';
    const cls = ['turn', turn.past ? 'past' : '', turn.changed ? 'changed' : ''].filter(Boolean).join(' ');
    const flag = turn.changed ? `<span class="flag">${turn.changed}</span>` : '';
    return `<div class="${cls}"><div class="meta"><b>${turn.dept}</b><span>${turn.time}</span>${flag}</div><p class="ask">${turn.text}</p>${turn.answer ?? ''}${steps}</div>`;
  }).join('');
  root.innerHTML = `<div class="dialog"><header class="col-head"><span>提问</span><span>4 个部门 · 同一套对象</span></header><div class="turns">${html}</div><div class="trace"><span>${trace.left}</span><span class="spin">${trace.right}</span></div></div>`;
}
