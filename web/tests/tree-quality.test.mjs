import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { JOBS, skillById } = await import('../src/lib/data/catalog.ts');
const { buildCareerPath, suggestJobs } = await import('../src/lib/engine.ts');
const { PERSONAS } = await import('../src/lib/data/personas.ts');

const now = new Date('2026-11-25');
const treeOf = (jobId, departmentId = 'business') => buildCareerPath({ ...PERSONAS[0].profile, departmentId, jobId, skills: {} }, [], now, []).tree;

test('a required node never disappears from its track unless it is a course with no deliverable', () => {
  for (const job of JOBS) {
    const ids = new Set(treeOf(job.id, job.departments?.[0]).map(n => n.skill));
    for (const n of job.nodes.filter(n => n.required && skillById(n.skill).kind !== '교육')) {
      assert(ids.has(n.skill), `${job.id}: ${n.skill} 빠짐`);
    }
  }
});

test('model-operations practice only appears in tracks that have a machine learning node', () => {
  const ml = ['PR-SPLIT-AUDIT', 'PR-TRAIN-REPLAY', 'PR-INFERENCE-TESTS', 'PR-DEPLOY-ROLLBACK', 'PR-LATENCY'];
  for (const jobId of ['marketer', 'sw-developer', 'public-sector', 'nurse']) {
    const ids = treeOf(jobId).map(n => n.skill);
    assert.deepEqual(ids.filter(id => ml.includes(id)), [], jobId);
  }
  assert(treeOf('ai-engineer', 'ai').some(n => ml.includes(n.skill)));
});

test('the main common tracks are real trees: enough nodes, several stages, mostly connected', () => {
  for (const jobId of ['sw-developer', 'marketer', 'public-sector', 'nurse']) {
    const tree = treeOf(jobId);
    assert(tree.length >= 10, `${jobId}: ${tree.length}`);
    assert(new Set(tree.map(n => n.depth)).size >= 4, `${jobId}: stages`);
    assert(tree.filter(n => n.prereq.length).length >= tree.length / 2, `${jobId}: connected`);
  }
});

test('nursing students are offered the nurse track first', () => {
  assert.equal(suggestJobs('nursing')[0].id, 'nurse');
});
