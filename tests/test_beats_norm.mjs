/* B() 节拍匹配的回归测试（零依赖）。
 *
 * 守的是同一条不变式的一半：小数点不是标点。
 * 屏幕文本那边的规则由 tests/test_subs_text.py 守；这里守「用文本查节拍」这条路 ——
 * 帧作者写 B('营收增长了2.4%')，归一化时不能把小数点削掉：
 *   削掉之后 '2.4%' 变成 '24%'，会去撞另一个真的念 24% 的块（静默配错节拍），
 *   或者反过来匹配不上而 throw（画面直接崩）。
 *
 * 做法：从 scripts/subs.py 里取出 BEATS_TMPL 模板本体（脚本真源，不复制一份），
 * 注入假数据后在 node 里跑。模板是 Python 三引号字符串，文件里写的是 \\s / \\u0000，
 * 所以取出来要先还原一层转义 —— 还原错的话 canary 断言（逗号必须被削掉）会立刻炸。
 *
 * 失败即 process.exit(1)。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

const py = fs.readFileSync(path.join(ROOT, 'scripts', 'subs.py'), 'utf8');
const m = py.match(/BEATS_TMPL = """([\s\S]*?)"""/);
if (!m) {
  console.error('✗ 没能从 scripts/subs.py 里取到 BEATS_TMPL');
  process.exit(1);
}
// 还原一层 Python 字符串转义（\\s → \s，\\u0000 → \u0000）
const tmpl = m[1].replace(/\\\\/g, '\\');

const beats = [
  // 关键样本：这一条归一化后是 '24%左右'，且**排在 2.4% 那条前面**。
  // 削掉小数点的年代，B('2.4%左右') 会先撞上它 → 静默返回错误的节拍秒。
  { text: '24%左右', start: 3.0, end: 4.0 },
  { text: '2.4%左右', start: 0.1, end: 2.0 },
  { text: '营收增长了2.4%，', start: 0.5, end: 2.0 },
  { text: '版本升到1.2.3之后，', start: 4.0, end: 6.0 },
];
const seg = { id: 't', duration: 6.2, speech_end: 6.0, tail: 0.2 };

const code = tmpl
  .replace('__BEATS_DATA__', JSON.stringify(beats))
  .replace('__SEG_DATA__', JSON.stringify(seg));

const sandbox = { window: {} };
const fn = new Function('window', code);
fn(sandbox.window);
const { B, Be } = sandbox.window;

let failed = 0;
function check(label, actual, want) {
  const ok = actual === want;
  if (!ok) failed++;
  console.log(`  ${ok ? 'OK ' : '✗  '} ${label}` + (ok ? '' : `\n      得到: ${actual}\n      应为: ${want}`));
}
function checkThrows(label, fn2) {
  let threw = false;
  try { fn2(); } catch { threw = true; }
  if (!threw) failed++;
  console.log(`  ${threw ? 'OK ' : '✗  '} ${label}` + (threw ? '' : '（本应 throw，却静默返回了）'));
}

console.log('B() 节拍匹配（JS 侧）');
// canary：证明模板转义还原正确 —— 逗号必须被削掉
check('逗号被归一化掉', B('营收增长了2.4%'), 0.5);
// ★ 证伪核心：'2.4%左右' 必须命中自己那条，不许撞上先出现的 '24%左右'
check('2.4%左右 命中自己（不撞 24%左右）', B('2.4%左右'), 0.1);
check('真的 24%左右 也能查到', B('24%左右'), 3.0);
check('版本号整条命中', B('版本升到1.2.3之后'), 4.0);
// ★ 前缀语义：只能从块文本**开头**取（写少一点可以）
check('块文本开头的前几字能查（前缀匹配）', B('版本升到'), 4.0);
// ★ 反过来：取**中间**一段必须抛错 —— 这条用例守住「不是 contains」这件事。
//   块文本是「版本升到1.2.3之后，」，'1.2.3之后' 不在开头，任何块都不以它开头。
checkThrows("取中间一段应报错（B() 不是 contains）", () => B('1.2.3之后'));
check('Be 同规则', Be('2.4%左右'), 2.0);
checkThrows('查不存在的 2.5% 应报错（别静默返回）', () => B('2.5%左右'));

if (failed) {
  console.error(`\n失败 ${failed} 项`);
  process.exit(1);
}
console.log('\n全部通过');
