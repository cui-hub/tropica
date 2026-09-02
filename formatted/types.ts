import { PlantListRawItem } from '../raw/tropica.com/types';

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


interface PlantListFormatted {
    /** 水草列表 */
    list: PlantListFormattedItem[];
}