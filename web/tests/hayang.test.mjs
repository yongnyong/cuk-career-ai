import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { existsSync } from 'node:fs';
import { test } from 'node:test';
registerHooks({ resolve(s, c, next) { return next(c.parentURL?.endsWith('.ts') && s.startsWith('.') && !s.endsWith('.ts') ? s + '.ts' : s, c); } });
const { outfitFor, hayangStage, hayangImage } = await import('../src/lib/hayang.ts');
const { JOBS } = await import('../src/lib/data/catalog.ts');

test('evolution stages follow tree progress', () => {
  assert.deepEqual([0, 29, 30, 59, 60, 89, 90, 100].map(hayangStage), [1, 1, 2, 2, 3, 3, 4, 4]);
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
