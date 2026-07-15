import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sourceFile = path.resolve(__dirname, '../../experiments/baseline_v1/generated/baseline_evaluation.json');
const destDir = path.resolve(__dirname, '../public/data');
const destFile = path.join(destDir, 'baseline_evaluation.json');

console.log('Syncing baseline evaluation data...');

if (!fs.existsSync(sourceFile)) {
  console.error(`Error: Source file does not exist at ${sourceFile}`);
  console.error('Have you run Step 2.9 (build_baseline_evaluation.py)?');
  process.exit(1);
}

try {
  const content = fs.readFileSync(sourceFile, 'utf8');
  const data = JSON.parse(content);

  // Validation
  if (data.schema_version !== "1.0") {
    throw new Error(`Invalid schema_version: ${data.schema_version}. Expected "1.0".`);
  }

  if (!Array.isArray(data.questions) || data.questions.length !== 8) {
    throw new Error(`Invalid questions count: ${data.questions?.length}. Expected 8.`);
  }

  if (!Array.isArray(data.stories) || data.stories.length !== 12) {
    throw new Error(`Invalid stories count: ${data.stories?.length}. Expected 12.`);
  }

  if (!Array.isArray(data.chunks) || data.chunks.length !== 909) {
    throw new Error(`Invalid chunks count: ${data.chunks?.length}. Expected 909.`);
  }

  for (const q of data.questions) {
    if (!Array.isArray(q.retrieved_chunks) || q.retrieved_chunks.length !== 10) {
      throw new Error(`Invalid retrieved_chunks count for question ${q.question_id}: ${q.retrieved_chunks?.length}. Expected 10.`);
    }
  }

  // Ensure destination directory exists
  if (!fs.existsSync(destDir)) {
    fs.mkdirSync(destDir, { recursive: true });
  }

  // Copy file
  fs.writeFileSync(destFile, content, 'utf8');
  console.log(`Successfully synced data to ${destFile}`);
} catch (error) {
  console.error('Validation or sync failed:', error.message);
  process.exit(1);
}
