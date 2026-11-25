import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { HALL_OF_FAME, fameTree, mentorScore, fameFor } = await import('../src/lib/data/hallOfFame.ts');
const { skillById } = await import('../src/lib/data/catalog.ts');
const { DEPARTMENTS } = await import('../src/lib/data/departments.ts');
const { toTreeNodes } = await import('../src/lib/customTree.ts');

test('every hall of fame entry has a source, valid links and a drawable tree', () => {
  const depts = new Set(DEPARTMENTS.map(d => d.id));
  for (const e of HALL_OF_FAME) {
    assert.match(e.source.url, /^https:\/\//, e.id);
    for (const d of e.departments) assert(depts.has(d), `${e.id}: ${d}`);
    const ids = new Set(e.nodes.map(n => n.id));
    for (const n of e.nodes) {
      if (n.skill) assert(skillById(n.skill), `${e.id}: ${n.skill}`);
      for (const q of n.prereq) assert(ids.has(q), `${e.id}: ${q}`);
    }
    assert.equal(toTreeNodes(fameTree(e, {})).nodes.length, e.nodes.length);
  }
});

test('mentor score counts only linked steps, weighting verified above self-check', () => {
  const yang = HALL_OF_FAME.find(e => e.id === 'yang-jaewon');
  assert.equal(mentorScore(yang, {}).score, 0);
  const some = mentorScore(yang, { 'PSY-STAT': 'self', 'PSY-TEST': 'verified' });
  assert.equal(some.done, 2);
  assert(some.score > 0 && some.score < 100);
  const all = Object.fromEntries(yang.nodes.filter(n => n.skill).map(n => [n.skill, 'verified']));
  assert.equal(mentorScore(yang, all).score, 100);
  assert.equal(fameTree(yang, { 'PSY-STAT': 'self' }).nodes.find(n => n.id === 'y1').done, true);
});

test('every department has its own hall of fame people, shown before the others', () => {
  assert.equal(new Set(HALL_OF_FAME.map(e => e.id)).size, HALL_OF_FAME.length);
  for (const d of DEPARTMENTS.filter(d => d.field !== 'open')) {
    assert(fameFor(d.id).mine.length > 0, `no one for ${d.id}`);
  }
  const ai = fameFor('ai');
  assert(ai.mine.every(e => e.departments.includes('ai')));
  assert(!ai.mine.some(e => e.id === 'yang-jaewon'));
  assert.equal(ai.mine.length + ai.others.length, HALL_OF_FAME.length);
  assert.equal(fameFor('free-major').mine.length, HALL_OF_FAME.length);
});
