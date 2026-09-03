import { defineConfig } from 'astro/config';

const [owner = '', repository = ''] = (process.env.GITHUB_REPOSITORY || '').split('/');
const isGitHubPages = Boolean(process.env.GITHUB_ACTIONS && owner && repository);
const gitLabPagesUrl = process.env.CI_PAGES_URL ? new URL(process.env.CI_PAGES_URL) : null;
const gitLabBase = gitLabPagesUrl
  ? (gitLabPagesUrl.pathname && gitLabPagesUrl.pathname !== '/' ? gitLabPagesUrl.pathname : '/')
  : null;

export default defineConfig({
  output: 'static',
  site: process.env.SITE_URL || gitLabPagesUrl?.origin || (isGitHubPages ? `https://${owner}.github.io` : 'http://localhost:4321'),
  base: process.env.BASE_PATH || gitLabBase || (isGitHubPages ? `/${repository}` : '/'),
  trailingSlash: 'always',
  build: {
    assets: '_assets'
  }
});
