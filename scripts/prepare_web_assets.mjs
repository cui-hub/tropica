import { createHash } from 'node:crypto';
import { mkdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import sharp from 'sharp';

const root = process.cwd();
const formattedDir = path.join(root, 'formatted');
const outputDir = path.join(root, 'public', 'generated', 'images', 'v1');
const concurrency = Math.max(2, Math.min(8, Number(process.env.IMAGE_CONCURRENCY) || 6));

const readJson = async (file) => JSON.parse(await readFile(path.join(formattedDir, file), 'utf8'));
const [plantList, plantDetails, layoutDetails] = await Promise.all([
  readJson('plant-list.json'),
  readJson('plant-detail-list.json'),
  readJson('layout-detail-list.json')
]);

const jobs = new Map();

function add(localPath, width, quality) {
  if (!localPath) return;
  const relative = localPath.replace(/^\.\//, '');
  const current = jobs.get(relative);
  if (!current || width > current.width) jobs.set(relative, { relative, width, quality });
}

for (const plant of plantList.list) add(plant.local_cover, 560, 78);
for (const plant of plantDetails.detail_list) {
  add(plant.local_illustration, 900, 80);
  for (const image of plant.local_images) add(image, 1280, 76);
}
for (const layout of layoutDetails.detail_list) {
  add(layout.local_planting_plan, 1200, 82);
  for (const image of layout.local_images) add(image, 1440, 76);
}

await mkdir(outputDir, { recursive: true });

const assetName = (relative) => `${createHash('sha256').update(relative).digest('hex').slice(0, 20)}.webp`;
let completed = 0;
let skipped = 0;
const queue = [...jobs.values()];

async function processImage(job) {
  const source = path.join(formattedDir, job.relative);
  const output = path.join(outputDir, assetName(job.relative));
  try {
    const [sourceStat, outputStat] = await Promise.all([stat(source), stat(output)]);
    if (outputStat.mtimeMs >= sourceStat.mtimeMs) {
      skipped += 1;
      return;
    }
  } catch {
    // The output is missing and will be generated below.
  }

  await sharp(source, { failOn: 'warning' })
    .rotate()
    .resize({ width: job.width, withoutEnlargement: true, fit: 'inside' })
    .webp({ quality: job.quality, effort: 4, smartSubsample: true })
    .toFile(output);
}

async function worker() {
  while (queue.length) {
    const job = queue.shift();
    await processImage(job);
    completed += 1;
    if (completed % 200 === 0) console.log(`Prepared ${completed}/${jobs.size} images`);
  }
}

await Promise.all(Array.from({ length: concurrency }, () => worker()));
console.log(`Prepared ${jobs.size} web images (${skipped} cached) in ${path.relative(root, outputDir)}`);
