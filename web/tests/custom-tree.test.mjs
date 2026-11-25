import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { newNode, wouldCycle, removeNode, toTreeNodes, withMyNodes, nodeIdeas } = await import('../src/lib/customTree.ts');
const { nodeWeights } = await import('../src/lib/treeRadial.ts');

const n = (id, prereq = [], extra = {}) => ({ ...newNode(id), id, prereq, ...extra });
const base = (skill, depth, prereq = [], state = 'none') => ({ skill, name: skill, kind: '역량', required: false, prereq, depth, state, locked: false, opportunities: [], sequence: [] });

test('a hand-made tree becomes skill tree nodes with depth, lock state and weights', () => {
  const tree = { id: 't', title: '명예의 전당', goal: '', createdAt: '', updatedAt: '', nodes: [n('a', [], { done: true, weight: 3 }), n('b', ['a']), n('c', ['b']), n('d', ['missing'])] };
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

test('new nodes get an id that cannot clash with catalog skills', () => {
  assert.match(newNode().id, /^my-/);
});

test('my nodes join the skill tree after their prerequisites, in depth order', () => {
  const tree = [base('S1', 0, [], 'self'), base('S2', 1, ['S1']), base('S3', 2, ['S2'])];
  const merged = withMyNodes(tree, [
    n('my-a', ['S1'], { name: '토브넷 직무 인터뷰', weight: 3, note: '대표님께 질문 정리' }),
    n('my-b', ['my-a', 'S2']),
    n('my-c', ['gone'], { done: true }),
  ]);
  const by = Object.fromEntries(merged.map(x => [x.skill, x]));
  assert.deepEqual([by['my-a'].depth, by['my-b'].depth, by['my-c'].depth], [1, 2, 0]);
  assert.equal(by['my-a'].locked, false); // S1 완료
  assert.equal(by['my-b'].locked, true);
  assert.equal(by['my-c'].state, 'self');
  assert.deepEqual(by['my-c'].prereq, []);
  assert.deepEqual(by['my-a'].mine, { weight: 3, note: '대표님께 질문 정리' });
  assert.deepEqual(merged.map(x => x.depth), [...merged.map(x => x.depth)].sort((a, b) => a - b));
  assert.equal(withMyNodes(tree, []), tree);
});

test('my nodes are sized by their own stars and do not shift the other nodes', () => {
  const tree = [base('S1', 0), { ...base('S2', 1, ['S1']), required: true }, base('S3', 2, ['S2'])];
  const before = nodeWeights(tree);
  const after = nodeWeights(withMyNodes(tree, [n('my-a', ['S3'], { weight: 1 }), n('my-b', [], { weight: 3 })]));
  for (const id of ['S1', 'S2', 'S3']) assert.equal(after.get(id).tier, before.get(id).tier);
  assert.equal(after.get('my-a').tier, 1);
  assert.equal(after.get('my-b').tier, 3);
});

test('the add form suggests common preparation for the job group and skips names already in the tree', () => {
  const dev = nodeIdeas('sw-developer').map(i => i.name);
  assert.ok(dev.includes('깃허브 포트폴리오 정리'));
  assert.ok(nodeIdeas('welfare').some(i => i.name === '상담센터 자원봉사'));
  assert.ok(nodeIdeas('sw-developer', true).some(i => i.name === '고객 인터뷰 10명'));
  assert.ok(!nodeIdeas('sw-developer', false, ['정보처리기사']).some(i => i.name === '정보처리기사'));
});
