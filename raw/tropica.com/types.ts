export interface PlantDetailProperty {
    /** 水草类型 */
    type: string;
    /** 水草产地 */
    origin: string;
    /** 生长速率 */
    growth_rate: string;
    /** 水草高度 */
    height: string;
    /** 光照需求 */
    light_requirement: string;
    /** CO2需求 */
    co2_requirement: string;
}

export interface PlantListRawItem {
    /** 水草名称 */
    name: string;
    /** 水草类型 */
    type: string;
    /** 产品编码 */
    product_code: string;
    /** 描述 */
    descriptions: string[];
    /** 主图信息 */
    cover: string;
    /** 详情页路由 */
    detail_path: string;
}

export interface PlantDetailItem {
    /** 水草名称 */
    name: string;
    /** 产品编码 */
    product_code: string;
    /** 水草属性 */
    properties: PlantDetailProperty;
    /** 水草介绍 */
    introduction: string;
    /** 水草图鉴 */
    illustration: string;
    /** 详情图片 */
    images: string[];
    /** 哪些造景使用了这个水草，记录水草造景名称标识 */
    layouts: string[];
}

export interface PlantDetailMeta {
    /** 水草属性说明 */
    property_description: Record<keyof PlantDetailProperty, string>;
}

export interface PlantListJson {
    /** 水草列表 */
    list: PlantListRawItem[];
}

export interface PlantDetailListJson {
    /** 水草详情列表 */
    detail_list: PlantDetailItem[];
    /** 元信息 */
    meta: PlantDetailMeta;
}

/** Tropica 对造景难度的分级 */
export type LayoutDifficulty = "Easy" | "Medium" | "Advanced";

export interface LayoutTechnique {
    /** 水族箱型号或尺寸；原站未提供时为空字符串 */
    aquarium: string;
    /** 水族箱容积；保留原站单位和格式 */
    volume: string;
    /** 灯具及光照配置 */
    light: string;
    /** 底床 */
    substrate: string;
    /** 底砂 */
    gravel: string;
    /** 石材、沉木等装饰材料 */
    decoration: string;
    /** 过滤配置 */
    filter: string;
    /** CO2 配置 */
    co2: string;
    /** 每周施肥配置 */
    fertiliser_weekly: string;
    /** 每周维护时长 */
    maintenance_hours_per_week: string;
}

export interface LayoutPlantItem {
    /** 植物在种植示意图中的位置标识，如 A、1；原站未提供时为空字符串 */
    position: string;
    /** 水草名称 */
    name: string;
    /** 产品编码，可从植物图片资源路径获取 */
    product_code: string;
    /** 使用数量 */
    quantity: number;
}

export interface LayoutDetailItem {
    /** 造景页面 ID，取自详情页路由末段 */
    layout_id: string;
    /** 造景资源编号，如 L127 */
    layout_code: string;
    /** 详情页路由 */
    detail_path: string;
    /** 造景名称 */
    name: string;
    /** 造景作者，可能有多人或机构；原站未署名时为空数组 */
    designers: string[];
    /** 造景难度 */
    difficulty: LayoutDifficulty;
    /** 设备与日常维护配置 */
    technique: LayoutTechnique;
    /** 造景介绍，按原页面段落保存 */
    descriptions: string[];
    /** 造景画廊图片，首张为主图 */
    images: string[];
    /** 植物种植位置示意图；原站未提供时为空字符串 */
    planting_plan: string;
    /** 原站可下载的造景指南 PDF */
    pdf: string;
    /** 造景使用的水草及数量 */
    plants: LayoutPlantItem[];
}

export interface LayoutDetailListJson {
    /** 造景详情列表 */
    detail_list: LayoutDetailItem[];
}
