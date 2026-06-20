import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import process from 'node:process';

import Ajv from 'ajv';
import {
  SCHEMA_VERSION,
  computeAssetId,
  verifyAssetId,
} from '@evomap/gep-sdk';

const require = createRequire(import.meta.url);
const schemaFiles = {
  Capsule: require.resolve('@evomap/gep-sdk/schemas/capsule.schema.json'),
  EvolutionEvent: require.resolve('@evomap/gep-sdk/schemas/evolution-event.schema.json'),
};
const schemas = Object.fromEntries(
  Object.entries(schemaFiles).map(([type, file]) => [
    type,
    JSON.parse(fs.readFileSync(file, 'utf8')),
  ]),
);
const ajv = new Ajv({ allErrors: true, strict: false });
const validators = Object.fromEntries(
  Object.entries(schemas).map(([type, schema]) => [type, ajv.compile(schema)]),
);

function readStdin() {
  return new Promise((resolve, reject) => {
    let input = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => {
      input += chunk;
    });
    process.stdin.on('end', () => {
      try {
        resolve(JSON.parse(input || '{}'));
      } catch (error) {
        reject(new Error(`Invalid JSON input: ${error.message}`));
      }
    });
  });
}

function validateAsset(asset) {
  const validate = validators[asset?.type];
  if (!validate) {
    throw new Error(`Unsupported GEP asset type: ${asset?.type || 'missing'}`);
  }
  if (!validate(asset)) {
    throw new Error(ajv.errorsText(validate.errors, { separator: '; ' }));
  }
  if (!verifyAssetId(asset)) {
    throw new Error('GEP asset_id verification failed');
  }
  return asset;
}

function buildCapsule(input) {
  const asset = {
    type: 'Capsule',
    schema_version: SCHEMA_VERSION,
    id: input.id,
    trigger: input.trigger,
    gene: input.gene,
    summary: input.summary,
    confidence: input.confidence,
    blast_radius: input.blast_radius,
    outcome: input.outcome,
    source_type: input.source_type,
    content: input.content,
    strategy: input.strategy,
    asset_id: '',
  };
  asset.asset_id = computeAssetId(asset);
  return validateAsset(asset);
}

function buildEvolutionEvent(input) {
  const asset = {
    type: 'EvolutionEvent',
    schema_version: SCHEMA_VERSION,
    id: input.id,
    parent: input.parent ?? null,
    intent: input.intent,
    signals: input.signals,
    genes_used: input.genes_used,
    mutation_id: input.mutation_id,
    blast_radius: input.blast_radius,
    outcome: input.outcome,
    capsule_id: input.capsule_id ?? null,
    source_type: input.source_type,
    reused_asset_id: input.reused_asset_id ?? null,
    meta: input.meta ?? null,
    asset_id: '',
  };
  asset.asset_id = computeAssetId(asset);
  return validateAsset(asset);
}

function persistAsset(asset, outputDir) {
  fs.mkdirSync(outputDir, { recursive: true });
  const safeId = asset.id.replace(/[^a-zA-Z0-9_.-]/g, '_');
  const file = path.join(outputDir, `${safeId}.json`);
  fs.writeFileSync(file, `${JSON.stringify(asset, null, 2)}\n`, 'utf8');
  return file;
}

const request = await readStdin();
let asset;
if (request.operation === 'build_capsule') {
  asset = buildCapsule(request.payload);
} else if (request.operation === 'build_event') {
  asset = buildEvolutionEvent(request.payload);
} else if (request.operation === 'validate') {
  asset = validateAsset(request.payload);
} else {
  throw new Error(`Unsupported operation: ${request.operation || 'missing'}`);
}

const file = request.output_dir ? persistAsset(asset, request.output_dir) : null;
process.stdout.write(JSON.stringify({ ok: true, asset, file }));
