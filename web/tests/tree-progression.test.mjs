import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { buildCareerPath } = await import('../src/lib/engine.ts');
const { layoutProgression, unifiedTree, layoutEmployment, employmentSection, EMPLOYMENT_SECTIONS, assignProgression, startupSection } = await import('../src/lib/treeProgression.ts');
const { questOutcome } = await import('../src/lib/questOutcome.ts');
const { JOBS } = await import('../src/lib/data/catalog.ts');
const { PERSONAS } = await import('../src/lib/data/personas.ts');
const data = JSON.parse(readFileSync(new URL('../src/lib/data/startupCatalog.json', import.meta.url)));
const now = new Date('2026-11-21');
const path = p => buildCareerPath(p, data.opportunities, now, [], data).tree;

// 2026-11-25: 트리가 너무 작아 보여 과목 노드를 되살리고 작은 트랙에 공통 준비를 붙였다
test('a small track keeps its courses and is filled with common preparation', () => {
  const profile = { ...PERSONAS[0].profile, departmentId: 'chemistry', jobId: 'che-semi', skills: {} };
  const result = buildCareerPath(profile, [], now, [], data);
  const ids = result.tree.map(n => n.skill);
  assert.equal(questOutcome(result.tree.find(n => n.skill === 'CHE-INORG')).label, '전공 과목');
  assert(ids.includes('PR-ROLE-COMPARISON'));
  assert(ids.includes('SK-INTERVIEW'));
  assert(result.tree.length >= 10);
  const material = result.tree.find(n => n.skill === 'CHE-MATERIAL');
  assert.match(questOutcome(material).title, /데이터시트/);
  assert.deepEqual(material.prereq, ['CHE-INORG']);
  assert(ids.includes(result.recommendedQuest.skillId));
  const big = buildCareerPath({ ...profile, departmentId: 'cs', jobId: 'sw-developer' }, [], now, [], data).tree;
  assert(!big.some(n => n.skill === 'PR-ROLE-COMPARISON'));
});

test('every employment track and startup sequence progresses downward with no missing prerequisite', () => {
  const profiles = [...JOBS.map(job => ({ ...PERSONAS[0].profile, jobId: job.id, skills: {} })), PERSONAS.at(-1).profile];
  for (const p of profiles) {
    const tree = path(p);
    assert(tree.length > 0, p.jobId);
    assert(tree.every(n => questOutcome(n)?.completion), p.jobId);
    for (const columns of [1, 3]) {
      const { positions } = layoutProgression(tree, columns);
      assert.equal(positions.size, tree.length);
      for (const node of tree) {
        for (const id of [...node.prereq, ...(node.sequence ?? [])]) {
          const parent = tree.find(n => n.skill === id);
          assert(parent, `${p.jobId}: missing ${id}`);
          assert(parent.depth < node.depth, `${p.jobId}: ${id} must precede ${node.skill}`);
          assert(positions.get(id).y + 110 < positions.get(node.skill).y);
        }
        for (const later of tree.filter(n => n.depth > node.depth)) {
          assert(positions.get(node.skill).y + 110 < positions.get(later.skill).y);
        }
      }
    }
  }
});

test('completion preserves placement and legacy startup topics can run in parallel', () => {
  const p = PERSONAS.at(-1).profile;
  const before = path(p);
  const after = path({ ...p, skills: Object.fromEntries(before.map(n => [n.skill, 'self'])) });
  assert.deepEqual(layoutProgression(before), layoutProgression(after));
  const depth = id => before.find(n => n.skill === id).depth;
  assert.equal(depth('SU-PREP-market'), depth('SU-DOC-prototype'));
  assert.equal(depth('SU-PREP-feasibility'), depth('SU-DOC-pitch-deck'));
  assert(depth('SU-DOC-prototype') < depth('SU-PREP-item-images'));
  assert.equal(startupSection(before.find(n => n.skill === 'SU-PREP-business-model')), '공통 준비');
  assert(before.every(n => !n.locked && n.prereq.length === 0));
});


test('unified tree retains both domains and every dependency while trimming generic extras', () => {
  const make = (skill, domain, extra = {}) => ({ skill, route: { domain, stage: 0 }, depth: 0, state: 'none', prereq: [], opportunities: [], ...extra });
  const nodes = [make('CW-EVIDENCE', 'common'), make('SK-RESUME', 'common'),
    make('CW-BUDGET', 'common'), make('SK-TOEIC', 'common'),
    make('SK-PY-01', 'specialist', { prereq: ['CW-EVIDENCE'] })];
  assert.deepEqual(unifiedTree(nodes, 'employment').filter(n => !n.groupChildren).map(n => n.skill), ['CW-EVIDENCE', 'SK-RESUME', 'SK-PY-01', 'SK-TOEIC']);
  assert(unifiedTree(nodes, 'employment', 'SK-TOEIC').some(n => n.skill === 'SK-TOEIC'));
  const dependent = [...nodes, make('project', 'specialist', { sequence: ['CW-BUDGET'] })];
  assert(unifiedTree(dependent, 'employment').some(n => n.skill === 'CW-BUDGET'));
  for (const persona of PERSONAS) {
    const full = path(persona.profile);
    const shown = unifiedTree(full, persona.profile.careerInterest === 'startup' ? 'startup' : 'employment');
    const ids = new Set(shown.map(n => n.skill));
    assert(shown.length > 0);
    for (const node of shown) for (const id of [...node.prereq, ...(node.sequence ?? [])]) assert(ids.has(id), id);
  }
});


test('common language choices retain scores without creating eligibility prerequisites', () => {
  const full = path({ ...PERSONAS[0].profile, skills: { 'SK-OPIC': 'self' }, scores: { 'SK-OPIC': 'IH' } });
  const shown = unifiedTree(full, 'employment');
  const group = shown.find(n => n.skill === 'COMMON-LANGUAGE');
  assert.equal(group.kind, '분류');
  assert.equal(group.groupChildren.length, 6);
  const opic = shown.find(n => n.skill === 'SK-OPIC');
  assert.equal(opic.score, 'IH');
  assert.equal(opic.state, 'self');
  assert.equal(opic.groupParent, group.skill);
  assert(!opic.prereq.includes(group.skill));
  assert(shown.some(n => n.skill === 'SK-COMP'));
  assert(shown.some(n => n.skill === 'SK-RESUME'));
});


test('psychology projects converge on one optional portfolio without all-project locking', () => {
  const persona = PERSONAS.find(p => p.id === 'demo-jiwoo').profile;
  for (const jobId of ['psy-counsel', 'psy-clinical', 'psy-org', 'psy-research']) {
    const full = path({ ...persona, jobId, skills: {} });
    const shown = unifiedTree(full, 'employment');
    const portfolios = shown.filter(n => n.portfolioSources);
    assert.equal(portfolios.length, 1);
    const portfolio = portfolios[0];
    assert.equal(portfolio.name, '심리학 포트폴리오 완성');
    assert.equal(portfolio.portfolioSources.length, 8);
    assert.equal(portfolio.locked, false);
    assert.deepEqual(portfolio.prereq, []);
    assert.deepEqual(portfolio.sequence, []);
    for (const id of portfolio.portfolioSources) {
      const project = shown.find(n => n.skill === id);
      assert(project, id);
      assert(project.depth < portfolio.depth);
      assert(questOutcome(project).completion.length > 20);
    }
    const updated = path({ ...persona, jobId, skills: { 'PSY-PROJECT-SURVEY': 'self', 'SK-PORT': 'self' } });
    assert.equal(updated.find(n => n.skill === 'PSY-PROJECT-SURVEY').state, 'self');
    assert.equal(updated.find(n => n.skill === 'SK-PORT').state, 'self');
  }
  assert.equal(path(PERSONAS.find(p => p.id === 'demo-minji').profile).find(n => n.portfolioSources).portfolioSources.length, 12);
});


test('both demo tracks show agreed credential and project pools in three sections', () => {
  for (const [personaId, credentials, projects] of [['demo-minji', 15, 12], ['demo-jiwoo', 10, 8]]) {
    const profile = PERSONAS.find(persona => persona.id === personaId).profile;
    const result = buildCareerPath(profile, [], now, [], data);
    const shown = unifiedTree(result.tree, 'employment', result.recommendedQuest?.skillId);
    assert.equal(shown.filter(node => node.credentialPriority).length, credentials);
    const portfolio = shown.find(node => node.portfolioSources);
    assert.equal(portfolio.portfolioSources.length, projects);
    assert.equal(shown.filter(node => node.portfolioSources).length, 1);
    assert(shown.some(node => node.skill === result.recommendedQuest.skillId));
    const layout = layoutEmployment(shown);
    assert.deepEqual(layout.bands.map(band => band.title), EMPLOYMENT_SECTIONS);
    assert.equal(layout.positions.size, shown.length);
    assert.equal(new Set([...layout.positions.values()].map(point => `${point.x},${point.y}`)).size, shown.length);
    const end = layout.positions.get(portfolio.skill);
    for (const id of portfolio.portfolioSources) assert(layout.positions.get(id).y < end.y);
    for (const node of shown.filter(node => node.credentialPriority)) {
      assert.equal(employmentSection(node), '직무 자격증');
      assert.equal(node.required, false);
      assert.deepEqual(node.prereq, []);
      assert(!node.evidence?.some(signal => signal.basis === 'required' || signal.basis === 'preferred'));
    }
  }
});


test('startup sections stay stable when cross-section prerequisites change depth', () => {
  const make = (skill, section, prereq = []) => ({ skill, name: skill, kind: '프로젝트',
    startupSection: section, personalCompletion: '결과물 저장', route: { domain: 'specialist', stage: 99 },
    prereq, sequence: [], depth: 99, state: 'none', opportunities: [], locked: false });
  const tree = assignProgression([
    make('prototype', '아이템 구체화'),
    make('test', '고객·시장 검증', ['prototype']),
    make('interview', '고객·시장 검증'),
    make('application', '사업화 준비', ['test']),
  ], 'startup');
  const get = id => tree.find(n => n.skill === id);
  assert.equal(get('prototype').depth, 0);
  assert.equal(get('interview').depth, 0);
  assert.equal(get('test').depth, 1);
  assert.equal(get('application').depth, 2);
  assert.equal(startupSection(get('test')), '고객·시장 검증');
  const layout = layoutProgression(tree);
  assert(layout.positions.get('prototype').y < layout.positions.get('test').y);
});
