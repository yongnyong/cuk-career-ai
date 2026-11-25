import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { existsSync } from 'node:fs';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { outfitFor, hayangStage, hayangImage, evolution } = await import('../src/lib/hayang.ts');
const { JOBS } = await import('../src/lib/data/catalog.ts');

test('evolution follows the share of completed nodes, but the home stage also needs proof', () => {
  assert.deepEqual([0, 14, 15, 34, 35, 59, 60, 89, 90, 100].map(p => hayangStage(p)), [1, 1, 2, 2, 3, 3, 4, 4, 4, 4]);
  assert.deepEqual([89, 90, 100].map(p => hayangStage(p, true)), [4, 5, 5]);
  const tree = (done, total) => Array.from({ length: total }, (_, i) => ({ state: i < done ? 'self' : 'none' }));
  assert.deepEqual(evolution(tree(0, 19)), { pct: 0, stage: 1, done: 0, total: 19, toNext: 3, proofsNeeded: 0 });
  assert.equal(evolution(tree(3, 19)).stage, 2);
  assert.equal(evolution(tree(7, 19)).stage, 3);
  assert.deepEqual(evolution(tree(19, 19), 1), { pct: 100, stage: 4, done: 19, total: 19, toNext: 0, proofsNeeded: 2 });
  assert.deepEqual(evolution(tree(12, 19), 3), { pct: 63, stage: 4, done: 12, total: 19, toNext: 6, proofsNeeded: 0 });
  assert.equal(evolution(tree(17, 19), 3).stage, 4); // 17/19 = 89%
  assert.equal(evolution(tree(18, 19), 3).stage, 5);
  assert.equal(evolution(tree(19, 19), 3).toNext, null);
  assert.equal(evolution([]).stage, 1);
});

test('every job gets an outfit whose image exists, department tracks follow their base job', () => {
  for (const job of JOBS) {
    const outfit = outfitFor(job.id);
    assert(existsSync(new URL(`../public${hayangImage(2, outfit)}`, import.meta.url)), `${job.id} → ${outfit}`);
  }
  assert(existsSync(new URL(`../public${hayangImage(1, 'dev')}`, import.meta.url)));
  assert.equal(outfitFor('psy-counsel'), 'care');
  assert.equal(outfitFor('clinical'), 'medical');
  assert.equal(outfitFor('psy-counsel', true), 'startup');
});
