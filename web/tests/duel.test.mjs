import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { duel, duelistOf, encodeDuelist, decodeDuelist } = await import('../src/lib/duel.ts');
const { buildCareerPath } = await import('../src/lib/engine.ts');
const { PERSONAS } = await import('../src/lib/data/personas.ts');

const now = new Date('2026-11-25');
const of = (persona) => duelistOf(persona.label, persona.desc, persona.profile.jobId, false, buildCareerPath(persona.profile, [], now, []).tree);
const node = (skill, kind, done, depth = 1) => ({ skill, name: skill, kind, state: done ? 'self' : 'none', depth });

test('a duel finds things to do together instead of a winner', () => {
  const me = duelistOf('나', '', 'a', false, [node('TOEIC', '어학', false), node('SQL', '교육', true), node('PORT', '프로젝트', false, 4), node('A-ONLY', '경험', false)]);
  const other = duelistOf('친구', '', 'b', false, [node('TOEIC', '어학', false), node('SQL', '교육', false), node('PORT', '프로젝트', true, 4), node('B-ONLY', '경험', false)]);
  const result = duel(me, other);
  assert.deepEqual(result.together.map(t => t.type), ['both', 'teach', 'learn', 'kind']);
  assert.equal(result.together[0].name, 'TOEIC');
  assert.deepEqual(result.together[3], { type: 'kind', kind: '경험', mine: 'A-ONLY', theirs: 'B-ONLY' });
  assert.deepEqual(result.team, { done: 2, total: 8 });
  assert.deepEqual(result.axes.find(a => a.kind === '교육'), { kind: '교육', me: { done: 1, total: 1 }, other: { done: 0, total: 1 } });
  assert(!('winner' in result));
});

test('every pair of demo students gets at least one shared suggestion', () => {
  const players = PERSONAS.filter(p => p.profile.careerInterest !== 'startup').map(of);
  for (const a of players) for (const b of players) if (a !== b) assert(duel(a, b).together.length > 0, `${a.name}·${b.name}`);
});

test('a friend link round-trips and rejects or trims bad data', () => {
  const me = of(PERSONAS[1]);
  assert.deepEqual(decodeDuelist(encodeDuelist(me)), me);
  assert.equal(decodeDuelist('not-a-code'), null);
  const forged = Buffer.from(JSON.stringify({ n: 'x'.repeat(500), k: [['S', 'N', 99, 1, 0], ['S2', 'n'.repeat(500), 0, 1, 9999], 'junk'] })).toString('base64url');
  const read = decodeDuelist(forged);
  assert.equal(read.name.length, 20);
  assert.equal(read.nodes.length, 1);
  assert.equal(read.nodes[0].name.length, 60);
  assert.equal(read.nodes[0].depth, 20);
});
