import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { replayScript, replayState } = await import('../src/lib/growthReplay.ts');

const node = (skill, depth, done) => ({ skill, name: skill, state: done ? 'self' : 'none', depth });
const tree = [node('C', 3, true), node('A', 0, true), node('B', 1, true), node('D', 4, false), node('E', 2, true), node('F', 1, false), node('G', 2, false), node('H', 3, false), node('I', 0, false), node('J', 4, false)];

test('the replay lights finished nodes from the inner stage outward and never the unfinished ones', () => {
  const events = replayScript(tree);
  assert.deepEqual(events.filter(e => e.type === 'node').map(e => e.skill), ['A', 'B', 'E', 'C']);
  assert.deepEqual(events.filter(e => e.type === 'ring').map(e => e.stage), [0, 1, 2, 3, 4]);
  assert.equal(events.at(-1).type, 'end');
  const end = replayState(events, events.length - 1);
  assert.deepEqual(end.lit, ['A', 'B', 'E', 'C']);
  assert.equal(end.stage, 3); // 4/10 = 40%
});

test('evolution cuts in exactly when the completion share crosses a threshold', () => {
  const events = replayScript(tree);
  const evolve = events.filter(e => e.type === 'evolve');
  assert.deepEqual(evolve.map(e => [e.from, e.to]), [[1, 2], [2, 3]]);
  assert.equal(events[events.indexOf(evolve[0]) - 1].skill, 'B'); // 2/10 = 20% ≥ 15%
  const full = replayScript(tree, true);
  assert.equal(full.filter(e => e.type === 'node').length, tree.length);
  assert.equal(replayState(full, full.length - 1).stage, 4);
});

test('the lighting part stays near twelve seconds however many nodes there are', () => {
  for (const count of [1, 5, 20, 60]) {
    const big = Array.from({ length: count }, (_, i) => node('N' + i, i % 5, true));
    const total = replayScript(big).filter(e => e.type === 'node').reduce((sum, e) => sum + e.ms, 0);
    assert(total <= 60 * 260 && (count < 14 || total >= 11000), `${count}: ${total}`);
  }
});
