// Export the existing TypeScript catalog for server-side profile adaptation.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'web/node_modules/typescript'));
require.extensions['.ts'] = (module, filename) => {
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  });
  module._compile(output.outputText, filename);
};
const { DEPARTMENTS } = require(path.join(root, 'web/src/lib/data/departments.ts'));
const { JOBS, SKILLS, SCALES } = require(path.join(root, 'web/src/lib/data/catalog.ts'));
fs.writeFileSync(path.join(root, 'api/app/career/web_catalog.json'),
  JSON.stringify({ departments: DEPARTMENTS, jobs: JOBS, skills: SKILLS, scales: SCALES }, null, 2));
console.log(JSON.stringify({ departments: DEPARTMENTS.length, jobs: JOBS.length, skills: SKILLS.length }));
