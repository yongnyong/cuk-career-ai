import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { buildCareerPath } = await import('../src/lib/engine.ts');
const { nodeWeights, layoutRadial, layoutFocus, advantagesOf, descendantRings, RADIAL_RX, RADIAL_RY } = await import('../src/lib/treeRadial.ts');
const { JOBS } = await import('../src/lib/data/catalog.ts');
const { PERSONAS } = await import('../src/lib/data/personas.ts');
const data = JSON.parse(readFileSync(new URL('../src/lib/data/startupCatalog.json', import.meta.url)));
const now = new Date('2026-11-21');

const node = (skill, extra = {}) => ({ skill, name: skill, kind: '역량', required: false, prereq: [], depth: 0, state: 'none', locked: false, opportunities: [], ...extra });
const opp = (id, extra = {}) => ({ id, type: '채용', title: id, org: `${id} 회사`, jobs: [], isVirtual: false, ...extra });

test('required nodes backed by postings are drawn larger than unsupported ones', () => {
  const tree = [
    node('A', { required: true, evidence: [{ basis: 'required', reference: { id: 'p1' } }] }),
    node('B', { prereq: ['A'] }),
    node('C'),
    node('D'),
  ];
  const weights = nodeWeights(tree);
  assert.equal(weights.get('A').tier, 3);
  assert.equal(weights.get('C').tier, 1);
  assert(weights.get('A').score > weights.get('B').score);
});

test('a tree with no signal at all keeps every node the same size', () => {
  const weights = nodeWeights([node('A'), node('B')]);
  assert.deepEqual([...weights.values()].map(w => w.tier), [2, 2]);
});

test('virtual postings do not add weight', () => {
  const weights = nodeWeights([node('A', { opportunities: [opp('v', { isVirtual: true })] }), node('B')]);
  assert.equal(weights.get('A').score, 0);
});

test('every track lays out radially with later stages further out and no overlapping nodes', () => {
  const profiles = [...JOBS.map(job => ({ ...PERSONAS[0].profile, jobId: job.id, skills: {} })), PERSONAS.at(-1).profile];
  for (const p of profiles) {
    const tree = buildCareerPath(p, data.opportunities, now, [], data).tree;
    if (!tree.length) continue;
    const { positions, rings } = layoutRadial(tree);
    assert.equal(positions.size, tree.length, p.jobId);
    const radius = s => Math.hypot(positions.get(s).x / RADIAL_RX, positions.get(s).y / RADIAL_RY);
    for (const n of tree) for (const parent of n.prereq) {
      assert(radius(parent) <= radius(n.skill) + 0.01, `${p.jobId}: ${parent} → ${n.skill}`);
    }
    assert.deepEqual(rings.map(r => r.r), rings.map(r => r.r).sort((a, b) => a - b));
    const points = [...positions.values()];
    // 전체 보기 노드는 최대 112×86px(원형 아이콘 + 이름)
    for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
      const dx = Math.abs(points[i].x - points[j].x), dy = Math.abs(points[i].y - points[j].y);
      assert(dx >= 112 || dy >= 86, `${p.jobId}: nodes ${i} and ${j} overlap (${dx.toFixed(0)}, ${dy.toFixed(0)})`);
    }
  }
});

test('focus view shows what a node unlocks and where it helps, without virtual postings', () => {
  const tree = [
    node('A', { evidence: [{ basis: 'preferred', reference: { id: 'old', organization: '옛 회사', historical: true } }],
      opportunities: [opp('o1', { jobs: ['data-analyst'] }), opp('v', { isVirtual: true })] }),
    node('B', { prereq: ['A'], depth: 1, opportunities: [opp('o2')] }),
    node('C', { prereq: ['B'], depth: 2 }),
    node('D'),
  ];
  assert.deepEqual(descendantRings(tree, 'A').map(r => r.map(n => n.skill)), [['B'], ['C']]);
  const advantages = advantagesOf(tree, 'A', [], now);
  assert.deepEqual(advantages.map(a => a.count).reduce((s, c) => s + c, 0), 3);
  assert(!advantages.some(a => a.orgs.includes('v 회사')));
  assert(advantages.some(a => a.orgs.includes('옛 회사')));
  const focus = layoutFocus(tree, 'A');
  assert.deepEqual(focus.positions.get('A'), { x: 0, y: 0 });
  assert(!focus.positions.has('D'));
  assert.equal(focus.advantagePositions.size, advantages.length);
});

test('a node shared by several tracks points to those jobs and the open postings filed under them', () => {
  const job = JOBS.find(j => j.nodes.length > 2);
  const skill = job.nodes[0].skill;
  const tree = [node(skill)];
  const future = new Date(now.getTime() + 7 * 864e5).toISOString();
  const posting = opp('open-1', { jobs: [job.id], versions: [{ deadline: future }] });
  const closed = opp('closed-1', { jobs: [job.id], versions: [{ deadline: '2026-01-01T00:00:00Z' }] });
  const advantages = advantagesOf(tree, skill, [posting, closed], now, job.id);
  const mine = advantages.find(a => a.id === `job:${job.id}`);
  assert.equal(mine.detail, '내 목표 직무');
  assert.equal(mine.count, 1);
  assert.deepEqual(mine.orgs, ['open-1 회사']);
});
