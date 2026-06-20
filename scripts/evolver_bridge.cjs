const fs = require('fs');
const path = require('path');
const process = require('process');

const evolverRoot = path.dirname(require.resolve('@evomap/evolver/package.json'));
const { formatSessionLog } = require(path.join(evolverRoot, 'src', 'evolve.js'));

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  input += chunk;
});
process.stdin.on('end', () => {
  try {
    const request = JSON.parse(input || '{}');
    const raw = fs.readFileSync(request.session_file, 'utf8');
    const transcript = formatSessionLog(raw);
    const messageCount = transcript
      .split('\n')
      .filter(line => line.startsWith('**USER**:') || line.startsWith('**ASSISTANT**:'))
      .length;
    process.stdout.write(JSON.stringify({
      ok: true,
      engine: '@evomap/evolver',
      mode: 'offline_session_inspection',
      message_count: messageCount,
      transcript: transcript.slice(-6000),
    }));
  } catch (error) {
    process.stderr.write(error && error.stack ? error.stack : String(error));
    process.exitCode = 1;
  }
});
