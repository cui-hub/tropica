import { PlantListRawItem, PlantDetailItem, PlantDetailProperty, PlantDetailMeta } from '../raw/tropica.com/types';

export interface PlantListFormattedItem extends PlantListRawItem {
    /** 水草名称 */
    name_cns: string[];
    /** 水草类型 */
    type_cn: string;
    /** 描述 */
    descriptions_cn: string[];
    /** 主图本地路径 */
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
}

export interface PlantDetailMetaFormatted extends PlantDetailMeta {
    /** 水草属性说明 */
    property_description_cn: Record<keyof PlantDetailPropertyFormatted, string>;
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