import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { buildCareerPath } = await import('../src/lib/engine.ts');
const { layoutProgression } = await import('../src/lib/treeProgression.ts');
const { questOutcome } = await import('../src/lib/questOutcome.ts');
const { JOBS } = await import('../src/lib/data/catalog.ts');
const { PERSONAS } = await import('../src/lib/data/personas.ts');
const data = JSON.parse(readFileSync(new URL('../src/lib/data/startupCatalog.json', import.meta.url)));
const now = new Date('2026-11-21');
const path = p => buildCareerPath(p, data.opportunities, now, [], data).tree;

test('a course with no deliverable cannot become a quest or block a real deliverable', () => {
  const profile = { ...PERSONAS[0].profile, departmentId: 'chemistry', jobId: 'che-semi', skills: {} };
  const result = buildCareerPath(profile, [], now, [], data);
  const ids = result.tree.map(n => n.skill);
  assert(!ids.includes('CHE-INORG'));
  assert(!ids.includes('PR-ROLE-COMPARISON'));
  assert(!ids.includes('PR-COURSE-EVIDENCE'));
  const material = result.tree.find(n => n.skill === 'CHE-MATERIAL');
  assert.match(questOutcome(material).title, /데이터시트/);
  assert.equal(material.locked, false);
  assert(ids.includes(result.recommendedQuest.skillId));
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

test('completion preserves placement and startup advances from validation to prototype to final documents', () => {
  const p = PERSONAS.at(-1).profile;
  const before = path(p);
  const after = path({ ...p, skills: Object.fromEntries(before.map(n => [n.skill, 'self'])) });
  assert.deepEqual(layoutProgression(before), layoutProgression(after));
  const depth = id => before.find(n => n.skill === id).depth;
  assert(depth('SU-PREP-problem') < depth('SU-PREP-market'));
  assert(depth('SU-PREP-market') < depth('SU-PREP-feasibility'));
  assert(depth('SU-PREP-feasibility') < depth('SU-DOC-prototype'));
  assert(depth('SU-DOC-prototype') < depth('SU-DOC-pitch-deck'));
  assert(before.every(n => !n.locked && n.prereq.length === 0));
});
