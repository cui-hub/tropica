import { access, readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const dist = path.join(root, 'dist');
const required = [
  'index.html',
  'plants/index.html',
  'layouts/index.html',
  'favorites/index.html',
  'plants/000c-st/index.html',
  'layouts/l131/index.html'
];

for (const file of required) await access(path.join(dist, file));

async function sizeOf(directory) {
  let total = 0;
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    total += entry.isDirectory() ? await sizeOf(target) : (await stat(target)).size;
  }
  return total;
}

const bytes = await sizeOf(dist);
const megabytes = bytes / 1024 / 1024;
if (megabytes >= 1024) throw new Error(`Build is ${megabytes.toFixed(1)} MB and exceeds the Pages 1 GB limit.`);

async function collect(directory, extension) {
  const results = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) results.push(...await collect(target, extension));
    else if (entry.name.endsWith(extension)) results.push(target);
  }
  return results;
}

const pages = await collect(dist, '.html');
if (pages.length !== 411) throw new Error(`Expected 411 HTML pages, found ${pages.length}.`);

const referencedImages = new Set();
for (const page of pages) {
  const html = await readFile(page, 'utf8');
  if (html.includes('./assets/images/')) throw new Error(`Unprocessed image path found in ${path.relative(dist, page)}.`);
  for (const match of html.matchAll(/generated\/images\/v1\/([a-f0-9]+\.webp)/g)) referencedImages.add(match[1]);
}
for (const image of referencedImages) await access(path.join(dist, 'generated', 'images', 'v1', image));

console.log(`Validated static build: ${pages.length} pages, ${referencedImages.size} referenced images, ${megabytes.toFixed(1)} MB total.`);
