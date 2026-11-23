import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { assignProgression, routeFor } = await import('../src/lib/treeProgression.ts');
const { layoutTree, layoutKey } = await import('../src/lib/treeLayout.ts');
const { buildCareerPath, countsTowardTrack } = await import('../src/lib/engine.ts');
const { questOutcome } = await import('../src/lib/questOutcome.ts');
const { PERSONAS } = await import('../src/lib/data/personas.ts');
const { sanitizeJob } = await import('../src/lib/data/catalog.ts');
const node = (skill, prereq = [], route) => ({ skill, name: skill, kind: '프로젝트', required: false, state: 'none', locked: false, depth: 0, prereq, opportunities: [], route });

test('invalid mandatory paths are diagnosed instead of drawing backwards', () => {
  assert.throws(() => assignProgression([node('a', ['b']), node('b', ['a'])], 'employment'), /순환/);
  assert.throws(() => assignProgression([node('a', ['missing'])], 'employment'), /없는 선행/);
});

test('cross-domain recommendations progress downwards without locking an optional path', () => {
  const graph = assignProgression([
    node('work', [], { domain: 'specialist', stage: 2 }),
    node('application', [], { domain: 'common', stage: 2, recommendedBefore: ['work'] }),
  ], 'employment');
  const application = graph.find(n => n.skill === 'application');
  assert.equal(application.depth, 3);
  assert.equal(application.locked, false);
  assert.deepEqual(application.prereq, []);
  assert.deepEqual(application.sequence, ['work']);
  const contradictory = assignProgression([
    node('a', ['b']), node('b', [], { domain: 'common', stage: 0, recommendedBefore: ['a'] }),
  ], 'employment');
  assert(contradictory.find(n => n.skill === 'a').depth > contradictory.find(n => n.skill === 'b').depth);
});

test('ELK keeps peers level, separates rectangles and preserves completion placement', async () => {
  for (const jobId of ['ai-research', 'psy-counsel']) {
    const profile = { ...PERSONAS[0].profile, jobId, skills: {} };
    const tree = buildCareerPath(profile, [], new Date('2026-11-22'), []).tree;
    assert.equal(new Set(tree.map(n => n.skill)).size, tree.length);
    assert(tree.some(n => routeFor(n).domain === 'common'));
    assert(tree.some(n => routeFor(n).domain === 'specialist'));
    for (const domain of ['common', 'specialist']) {
      const group = tree.filter(n => routeFor(n).domain === domain);
      const layout = await layoutTree(group);
      for (const a of group) for (const b of group) {
        if (a.skill === b.skill) continue;
        const p = layout.positions.get(a.skill), q = layout.positions.get(b.skill);
        assert(Math.abs(p.x - q.x) >= 192 || Math.abs(p.y - q.y) >= 150);
        if (a.depth === b.depth) assert.equal(p.y, q.y);
        if (a.depth < b.depth) assert(p.y < q.y);
      }
      const completed = group.map(n => ({ ...n, state: 'verified' }));
      assert.equal(layoutKey(group), layoutKey(completed));
      assert.deepEqual(layout.positions, (await layoutTree(completed.reverse())).positions);
    }
  }
});

test('admin catalog sanitization preserves explicit route metadata', () => {
  const route = { domain: 'common', stage: 2, recommendedBefore: ['b'] };
  const job = sanitizeJob({ id: 'job', nodes: [{ skill: 'a', required: false, route }, { skill: 'b', required: false }] }, new Set(['a', 'b']));
  assert.deepEqual(job.nodes[0].route, route);
});

test('common work can start early and optional exams gain priority only with role evidence', () => {
  const profile = PERSONAS.find(p => p.id === 'demo-minji').profile;
  const now = new Date('2026-11-22');
  const baseline = buildCareerPath(profile, [], now, []);
  const common = baseline.tree.filter(n => n.route?.domain === 'common');
  assert(common.some(n => n.depth === 0 && !n.locked && questOutcome(n)?.completion));
  assert(common.find(n => n.skill === 'SK-RESUME').sequence.includes('CW-EVIDENCE'));
  const exams = common.filter(n => n.commonExamOption);
  assert.equal(exams.length, 4);
  assert(exams.every(n => !countsTowardTrack(n) && questOutcome(n).label === '공통 선택 시험'));
  const held = buildCareerPath({ ...profile, skills: { ...profile.skills, 'SK-COMP': 'verified' } }, [], now, []);
  assert.equal(held.treeProgress.pct, baseline.treeProgress.pct);
  assert.equal(held.treeProgress.bonusExp, baseline.treeProgress.bonusExp + 100);
  const quote = '컴퓨터활용능력 우대';
  const opp = { id: 'role-with-exam', org: '테스트', type: '채용', title: '연구원', jobs: [profile.jobId],
    versions: [{version: 1, deadline: '2026-12-01'}], reviewed: true, required: [], preferred: ['SK-COMP'],
    source: { url: 'https://example.org/job' }, sections: [{ id: 'p', text: quote }],
    skillEvidence: [{ skill: 'SK-COMP', basis: 'preferred', scope: 'role', src: 'p', quote }] };
  const path = buildCareerPath(profile, [opp], now, []);
  const matches = path.tree.filter(n => n.skill === 'SK-COMP');
  assert.equal(matches.length, 1);
  assert(countsTowardTrack(matches[0]));
  assert.equal(questOutcome(matches[0]).label, '공고 우대에 명시');
  assert.equal(path.recommendedQuest.skillId, 'SK-COMP');
});
