import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { titlesFor, equippedTitle } = await import('../src/lib/titles.ts');

const node = (skill, kind, state = 'none') => ({ skill, kind, state });
const base = { pct: 0, outfit: 'care', questsStarted: 0, coreSkills: new Set() };
const byId = (titles) => Object.fromEntries(titles.map(t => [t.id, t]));

test('a fresh student only has the starter title, with progress shown for the rest', () => {
  const t = byId(titlesFor({ ...base, tree: [node('a', '자격증')] }));
  assert.equal(t.freshman.earned, true);
  assert.equal(t['first-step'].earned, false);
  assert.equal(t.collector.progress, '0/2');
  assert.equal(t.job.name, '상담가 하양이');
  assert.equal(t.job.progress, '0/15%');
});

test('titles come only from recorded progress', () => {
  const tree = [node('a', '자격증', 'self'), node('b', '자격증', 'verified'), node('c', '어학', 'self'), node('d', '프로젝트')];
  const t = byId(titlesFor({ ...base, tree, pct: 65, questsStarted: 1, coreSkills: new Set(['a', 'b']) }));
  for (const id of ['first-step', 'hunter', 'collector', 'global', 'proven', 'core', 'job', 'car']) assert.equal(t[id].earned, true, id);
  for (const id of ['maker', 'home', 'allclear']) assert.equal(t[id].earned, false, id);
});

test('the equipped title falls back to the rarest earned one', () => {
  const titles = titlesFor({ ...base, tree: [node('a', '어학', 'self')], pct: 35 });
  assert.equal(equippedTitle(titles).id, 'job');
  assert.equal(equippedTitle(titles, 'global').id, 'global');
  assert.equal(equippedTitle(titles, 'allclear').id, 'job');
});
