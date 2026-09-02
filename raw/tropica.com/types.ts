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

interface PlantListJson {
    /** 水草列表 */
    list: PlantListRawItem[];
    list_CN: PlantListRawItem[];
}
