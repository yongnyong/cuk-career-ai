import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { currentSemester, assignSemesters } = await import('../src/lib/treeRadial.ts');

const node = (skill, depth, state = 'none', prereq = []) => ({ skill, depth, state, prereq, kind: '역량', required: false, locked: false, opportunities: [] });

test('current semester follows grade and the academic calendar', () => {
  assert.equal(currentSemester(1, new Date('2026-03-10')), 0);
  assert.equal(currentSemester(3, new Date('2026-11-24')), 5);
  assert.equal(currentSemester(3, new Date('2027-01-15')), 5);
  assert.equal(currentSemester(6, new Date('2026-05-01')), 6);
});

test('nodes spread over all eight semesters in stage order, prerequisites never later', () => {
  const tree = Array.from({ length: 16 }, (_, i) => node(`n${i}`, Math.floor(i / 3), i < 4 ? 'self' : 'none', i ? [`n${i - 1}`] : []));
  const slots = assignSemesters(tree);
  assert.deepEqual(new Set(slots.values()).size, 8);
  for (const n of tree) for (const q of n.prereq) assert(slots.get(q) <= slots.get(n.skill));
  assert.deepEqual([...assignSemesters([node('a', 0)]).values()], [0]);
});
