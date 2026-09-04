import { access, readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const dist = path.join(root, 'dist');
const required = [
  'index.html',
  'google2a938afbb215b6a9.html',
  'robots.txt',
  'sitemap-index.xml',
  'sitemap-0.xml',
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

const pages = (await collect(dist, '.html')).filter((file) => !/^google[a-z0-9]+\.html$/.test(path.basename(file)));
if (pages.length !== 411) throw new Error(`Expected 411 HTML pages, found ${pages.length}.`);

// Validate deployment URLs when the build supplies an explicit site and base path.
const expectedSite = process.env.SITE_URL && process.env.BASE_PATH
  ? new URL(`${process.env.BASE_PATH.replace(/\/$/, '')}/`, process.env.SITE_URL)
  : null;

const referencedImages = new Set();
for (const page of pages) {
  const html = await readFile(page, 'utf8');
  if (html.includes('./assets/images/')) throw new Error(`Unprocessed image path found in ${path.relative(dist, page)}.`);
  if (!html.includes('rel="canonical"')) throw new Error(`Canonical link missing in ${path.relative(dist, page)}.`);
  if (!html.includes('property="og:title"')) throw new Error(`Open Graph metadata missing in ${path.relative(dist, page)}.`);
  if (!html.includes('application/ld+json')) throw new Error(`JSON-LD missing in ${path.relative(dist, page)}.`);
  if (expectedSite) {
    const route = path.relative(dist, page).split(path.sep).join('/').replace(/index\.html$/, '');
    const canonical = new URL(route, expectedSite).href;
    if (!html.includes(`rel="canonical" href="${canonical}"`)) {
      throw new Error(`Incorrect canonical URL in ${path.relative(dist, page)}: expected ${canonical}.`);
    }
  }
  for (const match of html.matchAll(/generated\/images\/v1\/([a-f0-9]+\.webp)/g)) referencedImages.add(match[1]);
}
for (const image of referencedImages) await access(path.join(dist, 'generated', 'images', 'v1', image));

if (expectedSite) {
  const robots = await readFile(path.join(dist, 'robots.txt'), 'utf8');
  if (!robots.includes(`Sitemap: ${new URL('sitemap-index.xml', expectedSite).href}`)) {
    throw new Error('robots.txt references the wrong sitemap URL.');
  }
  for (const filename of ['sitemap-index.xml', 'sitemap-0.xml']) {
    const xml = await readFile(path.join(dist, filename), 'utf8');
    const urls = [...xml.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]);
    if (!urls.length || urls.some((url) => !url.startsWith(expectedSite.href))) {
      throw new Error(`${filename} references the wrong site URL.`);
    }
  }
}

console.log(`Validated static build: ${pages.length} pages, ${referencedImages.size} referenced images, ${megabytes.toFixed(1)} MB total.`);
