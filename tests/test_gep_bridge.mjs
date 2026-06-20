import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import test from 'node:test';

const root = path.resolve(import.meta.dirname, '..');
const bridge = path.join(root, 'scripts', 'gep_bridge.mjs');

test('bridge builds a schema-valid Capsule with a verified asset id', () => {
  const request = {
    operation: 'build_capsule',
    payload: {
      id: 'CAP-NODE-001',
      trigger: ['test_signal'],
      gene: 'test_gene',
      summary: 'Bridge test',
      confidence: 0.8,
      blast_radius: { files: 0, lines: 0 },
      outcome: { status: 'success', score: 0.8 },
      source_type: 'user_authored',
      content: { safe: true },
      strategy: ['validate'],
    },
  };
  const result = spawnSync('node', [bridge], {
    cwd: root,
    input: JSON.stringify(request),
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  const response = JSON.parse(result.stdout);
  assert.equal(response.ok, true);
  assert.match(response.asset.asset_id, /^sha256:[a-f0-9]{64}$/);
  assert.match(response.asset.schema_version, /^\d+\.\d+\.\d+$/);
});
