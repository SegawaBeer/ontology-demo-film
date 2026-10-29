// Narration subtitles (脚本/字幕方案-v1.1.md 3.2), drawn on frame=opening, film and ending
// when the address carries &narration=1. Times are the original film's seconds; the title
// cards cut in later do not count. Each line is a pure function of t.
import { seg, ease } from './timing';

/** [from, to, text]; `<br>` is where the line breaks. Copied from 字幕方案-v1.1 3.2, word for word. */
export const NARRATION: readonly (readonly [number, number, string])[] = [
  [0.8, 4.6, '这是一枚涡轮叶片，<br>右边，是它在系统里的对象'],
  [5.4, 9.2, '一百枚同样的叶片落满一圈，<br>在系统里仍是一个节点，带着计数'],
  [10.0, 13.8, '涡轮、主轴、压气机一层层套上，<br>右边的产品结构跟着长出来'],
  [17.4, 21.4, '燃烧室、机匣、风扇依次合拢，<br>这棵装配树，设计系统里本来就有'],
  [21.9, 25.1, '7 号发动机装好了，<br>明早九点，它要上试车台'],
  [25.5, 28.9, '真正多出来的，是这些线：<br>零件和工单、批次、供应商的关系'],
  [36.3, 39.9, '系统从设计版本出发，<br>顺着关系线一步步往外查'],
  [40.4, 43.6, '孔径一改，两套打孔程序、<br>一份检验标准都得跟着改'],
  [44.0, 48.0, '装好的 1 到 7 号不受影响，<br>牵连的是在制和在途的叶片'],
  [51.8, 54.8, '整机拆成 9 个模块逐个核对，<br>在闪的那套，就是缺的'],
  [55.2, 58.0, '顺着采购订单查下去：<br>燃烧室凌晨 02:40 到厂'],
  [58.4, 61.8, '到这里，一切还顺利，<br>质检那边的复检结果，就要出来了'],
  [67.8, 71.0, '这批粉末用在叶片涂层上，<br>最外层的陶瓷层，就是它喷的'],
  [71.4, 75.0, '1,016 枚叶片逐枚核对：<br>装上的、库里的、在做的，一枚不漏'],
  [75.4, 79.0, '46 枚受影响：16 枚在厂里，<br>30 枚已在澜川航空的飞机上'],
  [80.6, 82.8, '7 号上的 16 枚当场停用，<br>整批粉末冻结'],
  [83.2, 86.0, '质量这边一停用，<br>总装的答案自己变成了红色'],
  [92.0, 95.0, '先确认库存叶片<br>用的不是那批问题粉末'],
  [95.4, 97.8, '两个方案摆在面前，<br>调拨可以不耽误试车'],
  [98.2, 101.0, '16 枚补齐，<br>总装的答案又自己变回了绿色'],
  [103.2, 106.6, '回头看，四个问题走过的路，<br>都经过这一枚叶片'],
  [107.0, 111.0, '以前，四个部门各有各的系统，<br>今晚，它们查的是同一张网'],
];
/** The ending's own closing line (ending.ts draws it, unchanged); listed here for the subtitle file. */
export const CLOSING = [116.4, 120.0, '同一套对象，整个工厂一起用。'] as const;

const FADE_IN = 0.25, RISE = 6, FADE_OUT = 0.2;

/** Index of the line on screen at t (opacity above 0 only strictly inside [from, to]), or -1. */
export const narrationIndex = (t: number) => NARRATION.findIndex(([a, b]) => t > a && t < b);

/** Adds the subtitle box to the frame; returns the draw function for a moment t. */
export function mountNarration(frame: HTMLElement) {
  const box = document.createElement('div');
  box.className = 'narration';
  box.style.display = 'none';
  frame.append(box);
  let shown = -1;
  return (t: number) => {
    const i = narrationIndex(t);
    if (i < 0) { box.style.display = 'none'; return; }
    const [a, b, text] = NARRATION[i];
    if (i !== shown) {
      box.replaceChildren(...text.split('<br>').map(line => {
        const span = document.createElement('span');
        span.textContent = line;
        return span;
      }));
      shown = i;
    }
    const rise = ease(seg(t, a, a + FADE_IN));
    box.style.display = '';
    box.style.opacity = (rise * (1 - ease(seg(t, b - FADE_OUT, b)))).toFixed(3);
    box.style.transform = `translate(-50%, -50%) translateY(${(RISE * (1 - rise)).toFixed(2)}px)`;
  };
}
