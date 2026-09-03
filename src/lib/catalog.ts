import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

export interface PlantProperties {
  type: string;
  origin: string;
  growth_rate: string;
  height: string;
  light_requirement: string;
  co2_requirement: string;
  type_cn: string;
  origin_cn: string;
}

export interface PlantListItem {
  name: string;
  name_cns: string[];
  type: string;
  type_cn: string;
  product_code: string;
  descriptions: string[];
  descriptions_cn: string[];
  cover: string;
  local_cover: string;
  detail_path: string;
}

export interface PlantDetailItem {
  name: string;
  name_cns: string[];
  product_code: string;
  properties: PlantProperties;
  introduction: string;
  introduction_cn: string;
  illustration: string;
  images: string[];
  layouts: string[];
  local_illustration: string;
  local_images: string[];
}

export interface LayoutPlantItem {
  position: string;
  name: string;
  product_code: string;
  quantity: number;
}

export interface LayoutDetailItem {
  layout_id: string;
  layout_code: string;
  detail_path: string;
  name: string;
  name_cn: string;
  designers: string[];
  difficulty: string;
  difficulty_cn: string;
  technique: Record<string, string>;
  technique_cn: Record<string, string>;
  descriptions: string[];
  descriptions_cn: string[];
  images: string[];
  local_images: string[];
  planting_plan: string;
  local_planting_plan: string;
  pdf: string;
  plants: LayoutPlantItem[];
}

const formattedUrl = new URL('../../formatted/', import.meta.url);
const readJson = <T>(file: string): T => JSON.parse(readFileSync(new URL(file, formattedUrl), 'utf8')) as T;

const listPayload = readJson<{ list: PlantListItem[] }>('plant-list.json');
const detailPayload = readJson<{ detail_list: PlantDetailItem[] }>('plant-detail-list.json');
const layoutPayload = readJson<{ detail_list: LayoutDetailItem[] }>('layout-detail-list.json');

export const plantList = listPayload.list;
export const plantDetails = detailPayload.detail_list;
export const layoutDetails = layoutPayload.detail_list;
export const plantListByCode = new Map(plantList.map((plant) => [plant.product_code, plant]));
export const plantDetailByCode = new Map(plantDetails.map((plant) => [plant.product_code, plant]));

export function plantSlug(productCode: string) {
  return productCode.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

export function layoutSlug(layoutCode: string) {
  return layoutCode.toLowerCase();
}

export function sitePath(target = '') {
  const base = (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
  return `${base}${target.replace(/^\//, '')}`;
}

export function imagePath(localPath: string) {
  if (!localPath) return '';
  const relative = localPath.replace(/^\.\//, '');
  const name = `${createHash('sha256').update(relative).digest('hex').slice(0, 20)}.webp`;
  return sitePath(`generated/images/v1/${name}`);
}

export const requirementLabel: Record<string, string> = {
  Low: '低',
  Medium: '中',
  High: '高'
};

export const growthLabel: Record<string, string> = {
  Slow: '慢',
  Medium: '中等',
  High: '快'
};

export const techniqueLabels: Record<string, string> = {
  aquarium: '水族箱',
  volume: '容积',
  light: '灯具',
  substrate: '底床',
  gravel: '底砂',
  decoration: '造景材料',
  filter: '过滤',
  co2: 'CO₂',
  fertiliser_weekly: '每周施肥',
  maintenance_hours_per_week: '每周维护'
};

export function chineseName(plant: Pick<PlantListItem | PlantDetailItem, 'name_cns' | 'name'>) {
  return plant.name_cns[0] || plant.name;
}

export function plantSearchText(plant: PlantListItem, detail?: PlantDetailItem) {
  return [
    plant.name,
    ...plant.name_cns,
    plant.product_code,
    plant.type_cn,
    detail?.properties.origin_cn || '',
    ...(plant.descriptions_cn || [])
  ].join(' ').toLowerCase();
}

export const layoutsByPlantCode = new Map<string, LayoutDetailItem[]>();
for (const layout of layoutDetails) {
  for (const plant of layout.plants) {
    const related = layoutsByPlantCode.get(plant.product_code) || [];
    related.push(layout);
    layoutsByPlantCode.set(plant.product_code, related);
  }
}

export const featuredPlantCodes = ['101H', '008', '003 TC', '067A TC', '106 TC', '025 TC'];
export const featuredPlants = featuredPlantCodes
  .map((code) => plantListByCode.get(code))
  .filter((plant): plant is PlantListItem => Boolean(plant));

export const featuredLayoutCodes = ['L131', 'L130', 'L129', 'L120', 'L117', 'L123'];
export const featuredLayouts = featuredLayoutCodes
  .map((code) => layoutDetails.find((layout) => layout.layout_code === code))
  .filter((layout): layout is LayoutDetailItem => Boolean(layout));
