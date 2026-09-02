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
