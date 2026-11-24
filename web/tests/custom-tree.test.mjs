import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { emptyTree, newNode, wouldCycle, removeNode, toTreeNodes, fromCareerTree } = await import('../src/lib/customTree.ts');

const now = new Date('2026-11-24');
const n = (id, prereq = [], extra = {}) => ({ ...newNode(id), id, prereq, ...extra });

test('a hand-made tree becomes skill tree nodes with depth, lock state and weights', () => {
  const tree = { ...emptyTree(now), title: '토브넷 입사', nodes: [n('a', [], { done: true, weight: 3 }), n('b', ['a']), n('c', ['b']), n('d', ['missing'])] };
  const { nodes, weights } = toTreeNodes(tree);
  const by = Object.fromEntries(nodes.map(x => [x.skill, x]));
  assert.deepEqual([by.a.depth, by.b.depth, by.c.depth, by.d.depth], [0, 1, 2, 0]);
  assert.equal(by.a.state, 'self');
  assert.equal(by.b.locked, false);
  assert.equal(by.c.locked, true);
  assert.deepEqual(by.d.prereq, []);
  assert.equal(weights.get('a').tier, 3);
  assert.equal(by.a.required, true);
});

test('prerequisites cannot form a cycle and deleting a node clears links to it', () => {
  const nodes = [n('a'), n('b', ['a']), n('c', ['b'])];
  assert.equal(wouldCycle(nodes, 'a', 'c'), true);
  assert.equal(wouldCycle(nodes, 'a', 'a'), true);
  assert.equal(wouldCycle(nodes, 'c', 'a'), false);
  assert.deepEqual(removeNode(nodes, 'b').map(x => [x.id, x.prereq]), [['a', []], ['c', []]]);
});

test('copying the current skill tree keeps names, links, completion and node sizes', () => {
  const career = [
    { skill: 'S1', name: '심리통계', kind: '역량', prereq: [], state: 'self' },
    { skill: 'S2', name: '상담면접', kind: '경험', prereq: ['S1', 'GONE'], state: 'none' },
  ];
  const copy = fromCareerTree('토브넷 입사', '토브넷', career, new Map([['S1', { tier: 3 }]]), now);
  assert.deepEqual(copy.nodes.map(x => [x.id, x.weight, x.prereq, x.done]), [['S1', 3, [], true], ['S2', 2, ['S1'], false]]);
});
