import type { APIRoute } from 'astro';
import { sitePath } from '@/lib/catalog';

export const GET: APIRoute = ({ site }) => {
  const sitemapUrl = new URL(sitePath('sitemap-index.xml'), site);
  const body = [
    'User-agent: *',
    'Allow: /',
    '',
    `Sitemap: ${sitemapUrl.href}`,
    ''
  ].join('\n');

  return new Response(body, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' }
  });
};
