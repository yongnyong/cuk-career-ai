import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { registerHooks } from 'node:module';
import { test } from 'node:test';

registerHooks({ resolve(specifier, context, nextResolve) {
  if (context.parentURL?.endsWith('.ts') && specifier.startsWith('.') && !specifier.endsWith('.ts')) return nextResolve(specifier + '.ts', context);
  return nextResolve(specifier, context);
} });
const { buildCareerPath, recommend, isOpen, dday } = await import('../src/lib/engine.ts');
const { careerInterestOf } = await import('../src/lib/interest.ts');
const { questItems } = await import('../src/lib/quest.ts');
const { PERSONAS, restoreDemoProfile } = await import('../src/lib/data/personas.ts');
const data = JSON.parse(readFileSync(new URL('../src/lib/data/startupCatalog.json', import.meta.url)));
const profile = { careerInterest: 'startup', departmentId: 'ai', jobId: 'founder', grade: 3, status: '재학', interests: [], skills: {} };
const now = new Date('2026-11-21T12:00:00+09:00');

test('startup uses all 22 sourced preparation nodes with freely accessible document relationships', () => {
  const result = buildCareerPath(profile, data.opportunities, now, [], data);
  assert.equal(result.tree.length, 22);
  assert(result.tree.every(n => n.skill.startsWith('SU-') && !n.locked && n.prereq.length === 0));
  assert(result.tree.some(n => n.connections?.length));
  assert.equal(result.recommendedQuest.skillId, 'SU-DOC-pitch-deck');
  assert.equal(result.tree.find(n => n.skill === result.recommendedQuest.skillId).depth, 0);
  const done = buildCareerPath({ ...profile, skills: { 'SU-DOC-pitch-deck': 'self' } }, data.opportunities, now, [], data);
  assert.notEqual(done.recommendedQuest.skillId, 'SU-DOC-pitch-deck');
  assert.equal(done.treeProgress.exp, 60);
});

test('historic founder records and employment profiles keep their intended mode and completion', () => {
  assert.equal(careerInterestOf({ jobId: 'founder' }), 'startup');
  assert.equal(careerInterestOf({ jobId: 'ai-startup' }), 'startup');
  assert.equal(careerInterestOf({ jobId: 'ai-research' }), 'employment');
  assert.equal(careerInterestOf({ jobId: 'ai-startup', careerInterest: 'employment' }), 'employment');
  const result = buildCareerPath({ ...profile, skills: { 'SK-MVP': 'self' } }, data.opportunities, now, [], data);
  assert.equal(result.tree.find(n => n.skill === 'SU-DOC-prototype').state, 'self');
  assert.equal(result.treeProgress.exp, 60);
});

test('recommendations filter by career interest and preserve unknown eligibility', () => {
  const founder = recommend(data.opportunities, profile, now);
  assert.equal(founder.length, 1);
  assert.equal(founder[0].opp.id, 'startup-cuk-277825');
  assert.equal(founder[0].verdict, 'check');
  assert.equal(recommend(data.opportunities, { ...profile, careerInterest: 'employment', jobId: 'ai-research' }, now).length, 0);
});

test('date-only notices stay open through their Korean closing date and unknown dates remain unresolved', () => {
  const notice = data.opportunities.find(o => o.id === 'startup-cuk-277825');
  const closing = new Date('2026-11-23T23:59:00+09:00');
  assert.equal(dday(notice, closing), 0);
  assert.equal(isOpen(notice, closing), true);
  assert.equal(isOpen(notice, new Date('2026-11-24T00:00:00+09:00')), false);
  assert.equal(isOpen({ ...notice, deadlineStatus: 'unknown' }, now), false);
  assert.equal(isOpen({ ...notice, startup: { ...notice.startup, status: 'closed' } }, now), false);
});

test('startup quest checklist uses the actual required application deliverables', () => {
  const notice = data.opportunities.find(o => o.id === 'startup-cuk-277825');
  const items = questItems(notice);
  assert(items.includes('발표자료 준비'));
  assert(!items.includes('사업계획서 초안 작성'));
  assert(!items.includes('시제품 준비'));
});

test('employment scenarios stay employment and the new business senior uses the startup tree', () => {
  const employment = PERSONAS.filter(p => p.id !== 'demo-seojun');
  assert.equal(employment.length, 4);
  assert(employment.every(p => careerInterestOf(p.profile) === 'employment'));
  const founder = PERSONAS.find(p => p.id === 'demo-seojun').profile;
  assert.equal(founder.departmentId, 'business');
  assert.equal(founder.grade, 4);
  const demo = JSON.parse(readFileSync(new URL('../src/lib/data/startupDemo.json', import.meta.url)));
  const path = buildCareerPath(founder, data.opportunities, now, [], data, demo);
  assert.equal(path.tree.length, 14);
  assert.equal(path.tree.filter(n => n.state !== 'none').length, 4);
  const haneul = PERSONAS.find(p => p.id === 'demo-haneul').profile;
  const restored = restoreDemoProfile(haneul, { ...haneul, jobId: 'founder', careerInterest: 'startup', skills: { 'SW-SOCIAL': 'self' } });
  assert.equal(careerInterestOf(restored), 'employment');
  assert.equal(restored.jobId, 'sw-social');
  assert.equal(restored.skills['SW-SOCIAL'], 'self');
  // 예전에 저장된 시연 프로필에도 시나리오에 새로 더한 완료 노드가 채워지고, 직접 취소한 노드는 그대로 둔다
  const minji = PERSONAS.find(p => p.id === 'demo-minji').profile;
  const old = restoreDemoProfile(minji, { ...minji, skills: { 'SK-PY-01': 'verified', 'AI-ML': 'none', 'SK-SQLD': 'self' } });
  assert.deepEqual(old.skills, { ...minji.skills, 'AI-ML': 'none', 'SK-SQLD': 'self' });
  assert(buildCareerPath(old, [], now, []).treeProgress.pct > 0);
  assert.deepEqual(restoreDemoProfile(minji, { ...minji, jobId: 'data-analyst', skills: {} }).skills, {});
  for (const id of ['demo-minji', 'demo-jiwoo']) {
    assert(buildCareerPath(PERSONAS.find(p => p.id === id).profile, [], now, []).treeProgress.pct > 0, id);
  }
});
