const fs = require('fs');
const path = require('path');

const buildId = new Date().toISOString();
const publicDir = path.join(__dirname, '..', 'public');
const outputPath = path.join(publicDir, 'build-id.txt');

fs.writeFileSync(outputPath, `${buildId}\n`, 'utf8');
