import {
    LayoutDetailItem,
    LayoutTechnique,
    PlantDetailItem,
    PlantDetailMeta,
    PlantDetailProperty,
    PlantListRawItem,
} from '../raw/tropica.com/types';

export interface PlantListFormattedItem extends PlantListRawItem {
    /** 水草名称 */
    name_cns: string[];
    /** 水草类型 */
    type_cn: string;
    /** 描述 */
    descriptions_cn: string[];
    /** 主图本地路径，相对于当前 JSON 文件，如 ./assets/images/xxx.png */
    local_cover: string;
}

export interface PlantDetailPropertyFormatted extends PlantDetailProperty {
    /** 水草类型 */
    type_cn: string;
    /** 水草产地 */
    origin_cn: string;
}


export interface PlantDetailFormattedItem extends PlantDetailItem {
    /** 水草名称 */
    name_cns: string[];
    /** 水草属性 */
    properties: PlantDetailPropertyFormatted;
    /** 水草介绍 */
    introduction_cn: string;
    /** 水草图鉴本地路径，如 ./assets/images/xxx.png；无图鉴时为空字符串 */
    local_illustration: string;
    /** 详情图片本地路径，以 ./assets/images/ 开头，与 images 按索引一一对应 */
    local_images: string[];
}

export interface PlantDetailMetaFormatted extends PlantDetailMeta {
    /** 水草属性说明 */
    property_description_cn: Record<keyof PlantDetailPropertyFormatted, string>;
}

/** Tropica 造景难度对应的中文分级 */
export type LayoutDifficultyCn = "简单" | "中等" | "困难";

/** 与 LayoutTechnique 字段一一对应的中文技术参数 */
export type LayoutTechniqueCn = Record<keyof LayoutTechnique, string>;

export interface LayoutDetailFormattedItem extends LayoutDetailItem {
    /** 造景名称的中文译名 */
    name_cn: string;
    /** 造景难度的中文分级 */
    difficulty_cn: LayoutDifficultyCn;
    /** 设备、材料和维护参数的中文说明 */
    technique_cn: LayoutTechniqueCn;
    /** 造景介绍的中文翻译，与 descriptions 按索引一一对应 */
    descriptions_cn: string[];
    /** 造景图片本地路径，以 ./assets/images/ 开头，与 images 按索引一一对应 */
    local_images: string[];
    /** 种植位置示意图本地路径，以 ./assets/images/ 开头；原站未提供时为空字符串 */
    local_planting_plan: string;
}



interface PlantListFormatted {
    /** 水草列表 */
    list: PlantListFormattedItem[];
}

interface PlantDetailListFormatted {
    /** 水草详情列表 */
    detail_list: PlantDetailFormattedItem[];
    /** 元信息 */
    meta: PlantDetailMetaFormatted;
}

export interface LayoutDetailListFormatted {
    /** 格式化后的造景详情列表 */
    detail_list: LayoutDetailFormattedItem[];
}
