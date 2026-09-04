# Aqualore

基于现有 Tropica 格式化数据生成的水草百科与造景灵感静态网站。站点使用 Astro，在构建阶段生成 288 个水草详情页和 119 个造景详情页；搜索、筛选和收藏在浏览器端完成。

## 本地开发

需要 Node.js 20 或更高版本。

```bash
npm install
npm run dev
```

首次启动会将 `formatted/assets/images` 中的图片转换为 WebP 并写入被 Git 忽略的 `public/generated`。后续运行会复用缓存，只处理更新过的图片。

## 构建与校验

```bash
npm run build
npm run verify
```

构建产物位于 `dist`，包含页面、脚本、样式和压缩后的图片，不依赖外部对象存储或 CDN。

## 发布

仓库内包含以下两种持续部署配置：

- GitHub Pages：`.github/workflows/deploy.yml`
- GitLab Pages：`.gitlab-ci.yml`

GitHub 仓库需要在 `Settings → Pages → Build and deployment` 中选择 **GitHub Actions**。推送到 `main` 后会自动构建并发布。

正式站点为 `https://www.aqualore.cn/`，根域名 `aqualore.cn` 跳转到主站。GitHub Actions 构建固定使用 `SITE_URL=https://www.aqualore.cn` 和 `BASE_PATH=/`，并校验生成页面的 canonical、robots.txt 和 sitemap 地址。

GitHub 仓库的 `Settings → Pages → Custom domain` 应设置为 `www.aqualore.cn`。当前使用自定义 Actions 部署，域名绑定由 Pages 设置管理，不依赖 `CNAME` 文件。DNS 记录为 `www CNAME cui-hub.github.io`，以及根域名 `@` 的两条 A 记录：`185.199.108.153`、`185.199.109.153`（DNSPod 免费版同主机、同线路限两条）。若未来使用支持四条记录的 DNS 套餐，可补上 GitHub 官方另外两个地址 `185.199.110.153` 和 `185.199.111.153`。证书就绪后启用 **Enforce HTTPS**。

本地按正式域名校验：

```bash
SITE_URL=https://www.aqualore.cn BASE_PATH=/ npm run verify
```

如需自定义构建地址，可设置：

- `SITE_URL`：站点域名，例如 `https://plants.example.com`
- `BASE_PATH`：部署子路径；自定义域名一般设置为 `/`

## 数据更新

网站在构建时直接读取：

- `formatted/plant-list.json`
- `formatted/plant-detail-list.json`
- `formatted/layout-detail-list.json`
- `formatted/assets/images`

更新格式化数据并重新构建即可刷新站点。图片 URL 由源路径稳定生成，数据中的植物与造景通过 `product_code` 建立关系。

## 素材说明

原始数据、文本和图片来源于 Tropica Aquarium Plants。公开发布前，请确认使用场景符合其版权要求并保留必要署名。
