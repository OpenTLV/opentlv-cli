// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

// Execute the actual workflow script with mocked API and artifact reads.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const workflow = fs.readFileSync(path.join(__dirname, '../.github/workflows/docs-notify.yml'), 'utf8')
  .replace(/\r\n/g, '\n');
const script = workflow.split('          script: |\n')[1].split('\n')
  .map(line => line.startsWith('            ') ? line.slice(12) : line).join('\n');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const notify = new AsyncFunction('require', 'context', 'github', script);

function fixture() {
  const run = {id: 123, run_attempt: 2, head_sha: 'b'.repeat(40)};
  const result = {
    status: 'passed', jobs: {validation: 'success', quality: 'success'},
    request: {
      cli_sha: 'a'.repeat(40), tag: 'v0.1.0', version: '0.1.0',
      workflow_sha: run.head_sha, run_id: '123', run_attempt: '2'
    }
  };
  const calls = [];
  const execute = () => notify(
    name => {
      assert.equal(name, 'fs');
      return {readFileSync: filename => {
        assert.equal(filename, 'evidence/result.json');
        return JSON.stringify(result);
      }};
    },
    {payload: {workflow_run: run}, repo: {owner: 'OpenTLV', repo: 'opentlv-cli'}},
    {rest: {repos: {createDispatchEvent: async data => calls.push(data)}}}
  );
  return {run, result, calls, execute};
}

test('notifies the candidate SHA, not the workflow SHA', async () => {
  const f = fixture();
  await f.execute();
  assert.deepEqual(f.calls, [{
    owner: 'OpenTLV', repo: 'opentlv-docs', event_type: 'cli-docs-released',
    client_payload: {source: 'cli', repository: 'OpenTLV/opentlv-cli',
      commit: 'a'.repeat(40), ref: 'v0.1.0', run_id: 123, run_attempt: 2}
  }]);
});

test('supports prerelease notification and a safe resend', async () => {
  const f = fixture();
  Object.assign(f.result.request, {tag: 'v0.2.0-rc.1', version: '0.2.0-rc.1'});
  await f.execute();
  await f.execute();
  assert.equal(f.calls.length, 2);
  assert.deepEqual(f.calls[0], f.calls[1]);
});

for (const [key, value] of [
  ['cli_sha', 'main'], ['tag', 'v0.1.0\nevil'], ['version', '0.2.0'],
  ['workflow_sha', 'c'.repeat(40)], ['run_id', '456'], ['run_attempt', '1']
]) {
  test(`rejects mismatched or invalid ${key} without dispatch`, async () => {
    const f = fixture();
    f.result.request[key] = value;
    await assert.rejects(f.execute, /does not authorize/);
    assert.equal(f.calls.length, 0);
  });
}

test('rejects failed or skipped release validation', async () => {
  for (const mutate of [
    result => result.status = 'failed',
    result => result.jobs.validation = 'failure',
    result => result.jobs.quality = 'skipped',
    result => delete result.request
  ]) {
    const f = fixture();
    mutate(f.result);
    await assert.rejects(f.execute, /does not authorize/);
    assert.equal(f.calls.length, 0);
  }
});
