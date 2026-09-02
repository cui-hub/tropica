#!/usr/bin/env python3
"""Build the curated Chinese plant list from Tropica raw data.

Plant names are deliberately maintained as an explicit, human-reviewed map.
Descriptions are translated into a local cache and then lightly normalised for
consistent, natural aquarium terminology.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "raw" / "tropica.com" / "plant-list.json"
OUTPUT_PATH = ROOT / "formatted" / "plant-list.json"
TRANSLATION_CACHE_PATH = ROOT / "scripts" / "description-translations.json"


# The first entry is the most common mainland-China aquarium-trade name. Later
# entries retain established formal, Taiwan/Hong Kong, or alternative trade names.
NAME_CNS: dict[str, list[str]] = {
    "Aegagropila linnaei": ["海藻球", "球藻", "绿球藻", "毬藻"],
    "Alternanthera reineckii 'Mini'": ["迷你血心兰"],
    "Alternanthera reineckii 'Pink'": ["粉红血心兰", "丹麦红玫瑰", "丹麦大红玫瑰"],
    "Alternanthera reineckii 'Rosanervig'": ["豹纹血心兰", "粉脉血心兰"],
    "Ammannia crassicaulis": ["粗茎水苋"],
    "Anubias barteri ’Coin Leaf’": ["金钱榕", "圆叶小榕"],
    "Anubias barteri caladiifolia": ["卡拉迪榕", "圆叶水榕"],
    "Anubias barteri 'Mini Coin'": ["迷你金钱榕"],
    "Anubias barteri 'Mini Coin' on stone": ["石附迷你金钱榕", "迷你金钱榕（石上）"],
    "Anubias barteri nana": ["小水榕", "小榕"],
    "Anubias barteri 'Petite'": ["袖珍小榕", "迷你小榕", "袖珍榕"],
    "Anubias barteri sp.": ["芭特榕", "大水榕", "巴榕"],
    "Anubias barteri var. barteri": ["大水榕", "芭特榕", "大榕"],
    "Anubias barteri var. caladiifolia": ["卡拉迪榕", "圆叶水榕"],
    "Anubias barteri var. 'Coffeifolia'": ["咖啡榕", "咖啡水榕"],
    "Anubias barteri var. glabra": ["格拉布拉水榕", "光滑水榕"],
    "Anubias barteri var. nana": ["小水榕", "小榕"],
    "Anubias barteri var. nana ’Kirin’": ["麒麟小榕", "波叶小榕"],
    "Anubias barteri var. nana ’Pinto’": ["平托小榕", "斑叶小榕"],
    "Anubias barteri var. nana 'Large'": ["大叶小榕", "大型小榕"],
    "Anubias gracilis": ["三角榕", "秀丽榕"],
    "Aponogeton boivinianus": ["气泡草", "气泡王"],
    "Aponogeton longiplumulosus": ["大卷浪草"],
    "Aponogeton madagascariensis": ["网草", "网眼草", "马达加斯加网草", "广叶网草"],
    "Aponogeton ulvaceus": ["大浪草"],
    "Bacopa australis": ["澳洲虎耳", "南方虎耳"],
    "Bacopa caroliniana": ["虎耳草", "普通虎耳", "卡罗莱纳过长沙"],
    "Bacopa monnieri 'Compact'": ["迷你小对叶", "紧凑小对叶"],
    "Bacopa salzmannii 'Purple'": ["紫虎耳", "紫色萨尔茨曼虎耳"],
    "Blyxa japonica": ["日本箦藻", "箦藻", "日本水筛", "水筛"],
    "Bolbitis heudelotii": ["黑木蕨", "黑木实蕨"],
    "Bucephalandra diabolica 'Kedagang'": ["柯达岗辣椒榕", "柯达嘎辣椒榕", "柯达冈辣椒榕"],
    "Bucephalandra diabolica' Kedagang'": ["柯达岗辣椒榕", "柯达嘎辣椒榕", "柯达冈辣椒榕"],
    "Bucephalandra pygmaea 'Bukit Kelam'": ["黑山辣椒榕", "辛唐辣椒榕"],
    "Bucephalandra sordidula 'Blue'": ["蓝色辣椒榕", "蓝辣椒榕"],
    "Bucephalandra sp. 'Needle Leaf'": ["针叶辣椒榕"],
    "Bucephalandra sp. 'Red'": ["红辣椒榕"],
    "Cabomba aquatica": ["黄花穗莼", "黄菊花草", "黄菊", "罗汉茜"],
    "Cardamine lyrata": ["苹果草", "水田碎米荠"],
    "Ceratophyllum demersum": ["金鱼藻", "松藻", "鱼草"],
    "Ceratopteris thalictroides": ["水蕨", "水芹菜", "细叶水芹"],
    "Crinum calamistratum": ["小喷泉草", "龙鞭草"],
    "Crinum thaianum": ["泰国水蒜", "泰国水仙", "大喷泉草"],
    "Cryptocoryne albida 'Brown'": ["棕色阿尔比达椒草", "褐色白隐棒花"],
    "Cryptocoryne beckettii 'Petchii'": ["贝克椒草", "佩奇椒草", "培茜椒草"],
    "Cryptocoryne crispatula": ["缎带椒草", "旋苞隐棒花", "沙滩草"],
    "Cryptocoryne nurii": ["虎斑椒草", "努莉椒草"],
    "Cryptocoryne parva": ["迷你椒草", "帕夫椒草"],
    "Cryptocoryne spiralis 'Red'": ["红螺旋椒草", "红旋叶椒草"],
    "Cryptocoryne undulata 'Broad Leaf'": ["宽叶波浪椒草", "宽叶浪琴椒草"],
    "Cryptocoryne usteriana": ["气泡椒草", "皱叶椒草", "乌斯特椒草"],
    "Cryptocoryne wendtii 'Green'": ["绿温蒂椒草", "绿伟蒂椒草"],
    "Cryptocoryne wendtii 'Mi Oya'": ["宓大屋温蒂椒草", "米河温蒂椒草", "红温蒂椒草"],
    "Cryptocoryne wendtii 'Tropica'": ["特罗皮卡温蒂椒草", "Tropica温蒂椒草"],
    "Cryptocoryne x willisii": ["威利斯椒草", "伟莉椒草", "小椒草"],
    "Cyperus helferi": ["喷泉莎草", "赫氏莎草"],
    "Echinodorus 'Aquartica'": ["阿夸提卡皇冠草", "水晶皇冠草"],
    "Echinodorus cordifolius 'Fluitans'": ["漂浮象耳皇冠", "浮叶象耳皇冠"],
    "Echinodorus grisebachii 'Bleherae'": ["亚马逊皇冠草", "大皇冠草", "布莱赫皇冠草"],
    "Echinodorus grisebachii 'Tropica'": ["新卵圆皇冠草", "Tropica皇冠草"],
    "Echinodorus 'Ozelot'": ["豹纹皇冠草", "丹尼尔象耳皇冠"],
    "Echinodorus 'Ozelot Green'": ["绿豹纹皇冠草"],
    "Echinodorus 'Red Diamond'": ["红钻皇冠草", "血钻石皇冠"],
    "Echinodorus 'Reni'": ["蕊妮皇冠草", "雷尼皇冠草"],
    "Echinodorus 'Rosé'": ["玫瑰皇冠草"],
    "Echinodorus x barthii": ["红香瓜草", "巴特皇冠草"],
    "Egeria densa": ["水蕴草", "蜈蚣草", "阿根廷蜈蚣草", "埃格草"],
    "Eleocharis acicularis": ["牛毛毡", "牛毛草", "猫毛草"],
    "Eleocharis montevidensis": ["长牛毛", "高牛毛毡", "蒙特维多牛毛毡"],
    "Eleocharis parvula": ["迷你牛毛毡", "短型牛毛", "牛毛毡"],
    "Eleocharis pusilla 'Mini'": ["迷你牛毛毡", "迷你矮牛毛"],
    "Eriocaulon cinereum": ["小谷精草", "白药谷精草", "灰绿谷精草"],
    "Eriocaulon sp. 'Vietnam'": ["越南谷精", "越南古精"],
    "Fissidens fontanus": ["美国凤尾苔", "美凤", "凤尾苔"],
    "Glossostigma elatinoides": ["矮珍珠", "短珍珠"],
    "Gratiola viscidula": ["黏性水八角", "粘性水八角"],
    "Helanthium bolivianum 'Quadricostatus'": ["四肋皇冠草", "宽叶链剑草"],
    "Helanthium tenellum 'Green'": ["针叶皇冠草", "绿针叶皇冠"],
    "Heteranthera zosterifolia": ["罗丝草", "小艾克草", "水星草"],
    "Hottonia palustris": ["帕鹿雪花草", "帕鹿雪花", "沼泽雪花草", "欧洲雪花草"],
    "Hydrocotyle tripartita": ["三裂天胡荽", "日本天胡荽", "日本珍珠草"],
    "Hydrocotyle verticillata": ["铜钱草", "香菇草", "圆币草", "南美天胡荽"],
    "Hygrophila corymbosa": ["大柳", "伞花水蓑衣", "刻脉水蓑衣"],
    "Hygrophila corymbosa 'Compact'": ["矮柳", "矮生大柳"],
    "Hygrophila corymbosa 'Siamensis 53B'": ["泰国水蓑衣53B", "暹罗大柳53B"],
    "Hygrophila corymbosa 'Stricta'": ["中柳", "琵琶草", "樱桃叶"],
    "Hygrophila costata": ["肋脉水蓑衣", "湖柳"],
    "Hygrophila difformis": ["水罗兰", "异叶水蓑衣", "大叶菊"],
    "Hygrophila lancea 'Araguaia'": ["阿拉瓜亚", "阿拉瓜亚水蓑衣"],
    "Hygrophila odora": ["香水蓑衣", "奥多拉水蓑衣"],
    "Hygrophila odora ’Difformis’": ["羽叶香水蓑衣", "奥多拉异叶型"],
    "Hygrophila pinnatifida & moss": ["羽裂水蓑衣配莫丝", "圣甲虫配莫丝"],
    "Hygrophila pinnatifida": ["羽裂水蓑衣", "雨裂水蓑衣", "锯齿艳柳", "圣甲虫"],
    "Hygrophila polysperma": ["青叶草", "小狮子草", "红丝青叶", "多子水蓑衣"],
    "Hygrophila polysperma 'Rosanervig'": ["红丝青叶", "豹纹青叶", "金丝青叶"],
    "Hygrophila polysperma 'White'": ["白青叶", "白化青叶草"],
    "Hygrophila serpyllum": ["匍匐水蓑衣", "百里香水蓑衣"],
    "Juncus repens": ["爬地灯心草", "匍匐灯心草"],
    "Lagenandra meeboldii 'Red'": ["美波莉椒草", "红色印度芭蕉草"],
    "Leptodictyum riparium": ["柔枝莫丝", "薄网藓", "云维莫丝"],
    "Lilaeopsis brasiliensis": ["南美尖叶草皮", "南美草皮", "巴西水毯草", "南美针叶"],
    "Limnobium laevigatum": ["南美沼萍", "美洲水鳖", "圆心萍", "苹果莲"],
    "Limnophila aquatica": ["大宝塔", "大宝塔草"],
    "Limnophila hippuridoides": ["红宝塔", "紫红石龙尾"],
    "Limnophila sessiliflora": ["小宝塔", "宝塔草", "石龙尾", "菊藻"],
    "Lindernia rotundifolia": ["瓜子草", "圆叶母草"],
    "Littorella uniflora": ["仙人掌草皮", "BIO仙人掌"],
    "Lobelia cardinalis": ["罗贝里", "红花半边莲", "红花山梗菜"],
    "Lobelia cardinalis 'Mini'": ["迷你罗贝里", "小罗贝力"],
    "Ludwigia glandulosa": ["大红叶", "大红叶水龙"],
    "Ludwigia palustris 'Green'": ["绿丁香", "绿水丁香"],
    "Ludwigia palustris 'Super Red'": ["超红水丁香", "超级红丁香"],
    "Ludwigia repens 'Rubin'": ["鲁宾叶底红", "丹麦红玫瑰"],
    "Lysimachia parvifolia ‘Red’": ["红小白菜", "极乐鸟", "拟小叶珍珠菜"],
    "Marsilea hirsuta": ["澳洲田字草", "毛柄田字草"],
    "Marsilea minuta": ["小田字草", "田字草", "南国田字草", "南国蘋"],
    "Mayaca fluviatilis": ["绿苔草", "河流松尾"],
    "Micranthemum callitrichoides ´Cuba´": ["迷你矮珍珠", "古巴珍珠"],
    "Micranthemum callitrichoides 'Cuba'": ["迷你矮珍珠", "古巴珍珠"],
    "Micranthemum glomeratum": ["日本珍珠草", "珍珠草"],
    "Micranthemum tweediei 'Monte Carlo'": ["趴地珍珠", "新大珍珠草", "蒙特卡洛珍珠草"],
    "Micranthemum umbrosum": ["大珍珠草", "小星星"],
    "Microsorum - Anubias 'Duet'": ["铁皇冠水榕组合", "铁皇冠—水榕双拼"],
    "Microsorum pteropus": ["铁皇冠", "有翅星蕨", "三叉叶星蕨"],
    "Microsorum pteropus nano wood": ["沉木附迷你铁皇冠", "迷你铁皇冠沉木"],
    "Microsorum pteropus 'Narrow'": ["细叶铁皇冠", "窄叶铁皇冠"],
    "Microsorum pteropus 'Trident'": ["三叉铁皇冠", "十字铁皇冠"],
    "Microsorum pteropus 'Windeløv'": ["鹿角铁皇冠", "温蒂洛铁皇冠"],
    "Microsorum sp.": ["铁皇冠属水草", "星蕨"],
    "Monosolenium tenerum": ["珊瑚莫丝", "大鹿角苔", "叉叶苔"],
    "Murdannia keisak": ["水竹叶", "疣草", "竹叶草"],
    "Myriophyllum mattogrossense": ["雪花羽毛", "马托格罗索狐尾藻"],
    "Myriophyllum sp. 'Guyana'": ["圭亚那羽毛", "迷你绿羽毛"],
    "Najas guadalupensis 'Guppy Grass'": ["小竹节", "孔雀鱼草", "瓜达卢佩小茨藻"],
    "Nymphaea lotus": ["虎斑睡莲", "齿叶睡莲"],
    "Nymphoides hydrophylla 'Taiwan'": ["台湾水莲", "龙骨瓣莕菜", "野莲"],
    "Phyllanthus fluitans": ["红毛丹浮萍", "红浮萍"],
    "Plagiomnium sp. 'Thyme Moss'": ["百里香莫丝", "木生百里香藓"],
    "Pogostemon deccanensis": ["德干刺蕊草", "德干百叶"],
    "Pogostemon helferi": ["喷泉太阳", "亨氏刺蕊草"],
    "Pogostemon quadrifolius": ["四叶刺蕊草", "四叶百叶"],
    "Pogostemon stellatus": ["百叶草", "大百叶", "水虎尾"],
    "Proserpinaca palustris 'Cuba'": ["古巴锯齿草", "锯齿草"],
    "Ranunculus inundatus": ["鹿角矮珍珠", "深裂毛茛", "大河毛茛"],
    "Riccardia chamedryfolia": ["珊瑚莫丝", "珊瑚苔"],
    "Riccia fluitans": ["鹿角苔", "叉钱苔"],
    "Rotala indica 'Bonsai'": ["印度小圆叶", "迷你小圆叶", "小圆叶盆景"],
    "Rotala macrandra": ["红蝴蝶"],
    "Rotala rotundifolia": ["红宫廷", "小圆叶", "圆叶节节菜"],
    "Rotala rotundifolia 'Blood Red'": ["血红宫廷", "丹麦血红宫廷", "血宫廷"],
    "Rotala rotundifolia 'Green'": ["绿宫廷", "绿小圆叶", "雪花圆叶"],
    "Rotala rotundifolia 'H'ra'": ["赫拉宫廷", "越南赫拉", "H'ra宫廷"],
    "Rotala wallichii": ["红松尾", "瓦氏水猪母乳"],
    "Sagittaria subulata": ["迷你水兰", "小水兰", "泽泻兰", "细叶慈姑"],
    "Sagittaria subulata 'Needle Leaf'": ["针叶水兰", "线叶迷你水兰"],
    "Salvinia minima": ["小槐叶萍", "迷你槐叶萍"],
    "Schismatoglottis prietoi": ["普列托水榕芋", "水生裂叶芋"],
    "Selaginella uncinata": ["翠云草", "蓝地柏", "蓝草"],
    "Shinnersia rivularis 'Weiss-Grün'": ["白绿菊", "白绿菊花草"],
    "Solenostoma tetragonum 'Pearl Moss'": ["珍珠莫丝", "四棱叶苔"],
    "Spirodela polyrrhiza": ["紫萍", "紫背浮萍", "水萍"],
    "Staurogyne repens": ["矮生叉柱花", "匍匐叉柱花"],
    "Taxiphyllum alternans 'Taiwan Moss'": ["台湾莫丝", "同叶藓", "互生叶鳞叶藓"],
    "Taxiphyllum barbieri 'Bogor Moss'": ["爪哇莫丝", "博哥莫丝"],
    "Taxiphyllum sp. ’Flame Moss’": ["火焰莫丝", "火燄莫丝"],
    "Taxiphyllum sp. 'Spiky Moss'": ["松茸莫丝", "尖叶莫丝", "Spiky莫丝"],
    "Utricularia graminifolia": ["挖耳草", "禾叶挖耳草", "乌拉草皮"],
    "Vallisneria americana 'Natans'": ["小水兰", "苦草", "娜坦丝水兰"],
    "Vallisneria 'Gigantea'": ["大水兰", "巨型水兰"],
    "Vallisneria spiralis 'Tiger'": ["虎纹水兰", "虎斑水兰"],
    "Vesicularia ferriei 'Weeping Moss'": ["垂泪莫丝", "垂枝莫丝", "眼泪莫丝"],
    "Vesicularia montagnei 'Christmas Moss'": ["圣诞莫丝", "南美正三角莫丝", "明叶藓"],
}


TYPE_CN = {
    "Stem": "有茎草",
    "Rhizomatous": "根茎类水草",
    "Rosulate": "莲座型水草",
    "Moss": "莫丝类",
    "Carpeting": "前景铺地草",
    "Bulb/onion": "球根类水草",
    "Stolon": "走茎型水草",
    "Floating plant": "浮水植物",
    "Floating-leaved": "浮叶型水草",
}


NAME_TYPE_OVERRIDE = {
    # Tropica classifies different product forms inconsistently; the plant is
    # best described in Chinese aquarium usage by its actual growth form.
    "Nymphoides hydrophylla 'Taiwan'": "Floating-leaved",
}


DESCRIPTION_OVERRIDES = {
    "Also known as ‘Marimo’": "又名“Marimo（马里莫／毬藻）”",
    "Intensely pink red leaves": "叶片呈浓艳的粉红至红色",
    "A rich deep green color": "浓郁的深绿色",
    "New unique mini Anubias": "全新而独特的迷你水榕",
    "Lava rock with self-attached Anubias": "已附生水榕的熔岩石",
    "Mangrove wood with self-attached Anubias": "已附生水榕的红树林沉木",
    "Mangrove wood with suction cup and self-attached Anubias": "带吸盘、已附生水榕的红树林沉木",
    "One of the smallest Anubias": "最小型的水榕之一",
    "Large mangrove wood with two self-attached Anubias": "大型红树林沉木，上面已附生两株水榕",
    "Inspired by an Asian dragon": "叶形设计灵感来自亚洲龙",
    "Mangrove wood with self-attached Bolbitis": "已附生黑木蕨的红树林沉木",
    "Lava rock with self-attached Bucephalandra": "已附生辣椒榕的熔岩石",
    "Lava rock with self-attached Cryptocorynes": "已附生椒草的熔岩石",
    "Versatile Placement: Midground or background": "位置灵活，适合中景或后景",
    "Endures bad light conditions but growth will become more vertical": "耐受较弱光照，但光线不足时会更偏直立生长",
    "Easy to attach to a hardscape of choice": "容易固定在喜欢的造景素材上",
    "Low Maintenance: Easy for beginners.": "养护省心，新手也容易上手",
    "Versatile Placement: Attach to hardscape.": "位置灵活，可附着在造景素材上",
    "Very easy and undemanding beginner’s plant": "非常好养且要求不高，适合新手",
    "Used to be called Cryptocoryne nevillii": "旧名为 Cryptocoryne nevillii",
    "Previously named Echinodorus ’paniculatus’": "旧名为 Echinodorus ’paniculatus’",
    "Previously named Echinodorus quadricostatus": "旧名为 Echinodorus quadricostatus",
    "Easy to Maintain": "容易养护",
    "Very safe and easy carpeting plant": "稳定易养的铺地草",
    "Compact Growth Potential": "可形成紧凑株型",
    "To be attached to rocks and wood pieces": "需固定在石材或沉木上",
    "Compact variant of Hygrophila corymbosa": "大柳的紧凑型品种",
    "Easy not demanding beginner plant": "好养且要求不高，适合新手",
    "Easy Care: Minimal maintenance needed.": "养护省心，只需少量打理",
    "Mangrove wood with moss and self-attached Hygrophila pinnatifida": "红树林沉木搭配莫丝和已附生的羽裂水蓑衣",
    "Easy to propagate by simply planting a \"tot\" somewhere else": "将分出的小株另行栽种即可轻松繁殖",
    "Grows easily on rocks and roots": "在石材和沉木上都容易生长",
    "Easy and undemanding carpeting plant": "易养且要求不高的铺地草",
    "Easy and fast-growing": "容易养护，生长迅速",
    "May be used in terrariums": "也可用于雨林缸",
    "Large mangrove wood with self-attached Microsorum and Anubias": "大型红树林沉木，上面已附生铁皇冠和水榕",
    "Known also as Java fern": "也叫铁皇冠",
    "Lava rock with self-attached Microsorum": "已附生铁皇冠的熔岩石",
    "Mangrove wood with self-attached Microsorum": "已附生铁皇冠的红树林沉木",
    "Mangrove wood with two self-attached Microsorums": "红树林沉木，上面已附生两株铁皇冠",
    "Ready to Use Pre-attached to nano wood": "已预先固定在迷你沉木上，可直接使用",
    "The leaves are smaller and narrower than those of the classic Java fern": "叶片比普通铁皇冠更小、更窄",
    "Mangrove wood with suction cup and self-attached Microsorum": "带吸盘、已附生铁皇冠的红树林沉木",
    "Grows more horizontally than the other Microsorum": "比其他铁皇冠更偏横向生长",
    "Large mangrove wood with two self-attached Microsorums": "大型红树林沉木，上面已附生两株铁皇冠",
    "Large mangrove wood with suction cups and self-attached plants": "带吸盘的大型红树林沉木，上面已附生水草",
    "Easy to trim and maintain": "易于修剪和养护",
    "Lava rock with self-attached Pogostemon helferi": "已附生喷泉太阳的熔岩石",
    "Suitable for both large aquariums and Nano Cubes": "大型水族箱和迷你方缸都适用",
    "Versatile Placement: Perfect for hardscape.": "位置灵活，非常适合搭配造景素材",
    "Requires perfect conditions to thrive": "需要理想的环境条件才能长好",
    "Can resemble Anubias": "外形与水榕有些相似",
    "Common name “Oak leaf” due to the leaf form": "因叶形得名“橡叶草”",
    "Common name: Mini Taiwan Moss": "常用名：迷你台湾莫丝",
    "Commonly named Java moss": "俗称爪哇莫丝",
    "Common name ‘Flame Moss’": "常用名：火焰莫丝",
    "Common name: Spiky Moss": "常用名：尖叶莫丝（Spiky Moss）",
    "Unique, but demanding foreground plant": "独特的前景草，但对养护条件要求较高",
    "Commonly named ‘Weeping moss’": "俗称垂泪莫丝",
    "Commonly named ’Christmas moss’": "俗称圣诞莫丝",
}


def polish_description(source: str, translated: str) -> str:
    if source in DESCRIPTION_OVERRIDES:
        return DESCRIPTION_OVERRIDES[source]
    replacements = (
        ("Cryptocorynes", "椒草"), ("Cryptocoryne", "椒草"),
        ("Bucephalandra", "辣椒榕"), ("Anubias", "水榕"),
        ("Microsorums", "铁皇冠"), ("Microsorum", "铁皇冠"),
        ("Echinodorus", "皇冠草"), ("Bolbitis", "黑木蕨"),
        ("Java fern", "铁皇冠"), ("Java moss", "爪哇莫丝"),
    )
    for old, new in replacements:
        translated = translated.replace(old, new)
    return translated


# Used only when all products sharing the same display name omit an English type.
GENUS_TYPE = {
    "Aegagropila": "Moss", "Alternanthera": "Stem", "Ammannia": "Stem",
    "Anubias": "Rhizomatous", "Aponogeton": "Bulb/onion", "Bacopa": "Stem",
    "Blyxa": "Rosulate", "Bolbitis": "Rhizomatous", "Bucephalandra": "Rhizomatous",
    "Cabomba": "Stem", "Cardamine": "Stem", "Ceratophyllum": "Stem",
    "Ceratopteris": "Rosulate", "Crinum": "Bulb/onion", "Cryptocoryne": "Rosulate",
    "Cyperus": "Rosulate", "Echinodorus": "Rosulate", "Egeria": "Stem",
    "Eleocharis": "Carpeting", "Eriocaulon": "Rosulate", "Fissidens": "Moss",
    "Glossostigma": "Carpeting", "Gratiola": "Stem", "Helanthium": "Stolon",
    "Heteranthera": "Stem", "Hottonia": "Stem", "Hydrocotyle": "Stem",
    "Hygrophila": "Stem", "Juncus": "Stem", "Lagenandra": "Rhizomatous",
    "Leptodictyum": "Moss", "Lilaeopsis": "Stolon", "Limnobium": "Floating plant",
    "Limnophila": "Stem", "Lindernia": "Stem", "Littorella": "Rosulate",
    "Lobelia": "Stem", "Ludwigia": "Stem", "Lysimachia": "Stem",
    "Marsilea": "Carpeting", "Mayaca": "Stem", "Micranthemum": "Carpeting",
    "Microsorum": "Rhizomatous", "Monosolenium": "Moss", "Murdannia": "Stem",
    "Myriophyllum": "Stem", "Najas": "Stem", "Nymphaea": "Bulb/onion",
    "Nymphoides": "Rosulate", "Phyllanthus": "Floating plant", "Plagiomnium": "Moss",
    "Pogostemon": "Stem", "Proserpinaca": "Stem", "Ranunculus": "Stolon",
    "Riccardia": "Moss", "Riccia": "Moss", "Rotala": "Stem",
    "Sagittaria": "Stolon", "Salvinia": "Floating plant", "Schismatoglottis": "Rhizomatous",
    "Selaginella": "Rhizomatous", "Shinnersia": "Stem", "Solenostoma": "Moss",
    "Spirodela": "Floating plant", "Staurogyne": "Stem", "Taxiphyllum": "Moss",
    "Utricularia": "Carpeting", "Vallisneria": "Stolon", "Vesicularia": "Moss",
}


def google_translate(text: str) -> str:
    params = urllib.parse.urlencode({
        "client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": text,
    })
    url = "https://translate.googleapis.com/translate_a/single?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in payload[0] if part[0])


def naturalize(text: str) -> str:
    replacements = {
        "易于成长": "容易养护", "容易生长的植物": "容易养护的水草",
        "易于生长": "容易养护", "不苛刻": "养护要求不高",
        "要求不高": "养护要求不高", "初学者": "新手",
        "水族馆": "水族箱", "坦克": "水族箱", "切断": "剪下",
        "岩石和木头": "石材或沉木", "岩石或木头": "石材或沉木",
        "木头或石头": "沉木或石材", "木材和岩石": "沉木和石材",
        "附着在": "固定在", "牲畜": "缸内生物", "鱼苗": "幼鱼",
        "眼睛捕手": "视觉焦点", "引人注目的人": "视觉焦点",
        "孤立植物": "单株主景草", "单生植物": "单株主景草",
        "休眠期": "休眠阶段", "最佳使用": "更适合用于",
        "中间地带": "中景", "背景地带": "后景", "前景地带": "前景",
        "营养素": "养分", "营养": "养分", "石灰质水": "硬度过高的水质",
        "白垩水": "硬度过高的水质", "枝条": "侧枝", "芽": "新芽",
        "叶神经": "叶脉", "神经": "叶脉", "颜色": "色彩",
        "繁殖": "繁殖", "水参数": "水质参数", "硬景观": "造景素材",
        "底层": "底床", "底部层": "底床", "水族箱底部": "缸底",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", "", text).strip("。；; ")
    return text


def build_translation_cache(items: list[dict]) -> dict[str, str]:
    if TRANSLATION_CACHE_PATH.exists():
        cache = json.loads(TRANSLATION_CACHE_PATH.read_text(encoding="utf-8"))
    else:
        cache = {}
    descriptions = list(dict.fromkeys(d for item in items for d in item["descriptions"]))
    missing = [d for d in descriptions if d not in cache]
    for index, source in enumerate(missing, 1):
        for attempt in range(3):
            try:
                cache[source] = naturalize(google_translate(source))
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
        if index % 20 == 0 or index == len(missing):
            print(f"translated {index}/{len(missing)} missing descriptions")
            TRANSLATION_CACHE_PATH.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        time.sleep(0.05)
    return cache


def resolve_types(items: list[dict]) -> dict[str, str]:
    by_name: dict[str, set[str]] = defaultdict(set)
    for item in items:
        if item["type"]:
            by_name[item["name"]].add(item["type"])
    resolved = {}
    for name in {item["name"] for item in items}:
        if name in NAME_TYPE_OVERRIDE:
            resolved[name] = NAME_TYPE_OVERRIDE[name]
            continue
        known = by_name[name]
        if len(known) == 1:
            resolved[name] = next(iter(known))
        elif not known:
            resolved[name] = GENUS_TYPE[name.split()[0]]
        else:
            raise ValueError(f"Conflicting types for {name}: {sorted(known)}")
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-translations", action="store_true")
    args = parser.parse_args()

    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    items = raw["list"]
    names = {item["name"] for item in items}
    missing_names = sorted(names - NAME_CNS.keys())
    extra_names = sorted(NAME_CNS.keys() - names)
    if missing_names or extra_names:
        raise ValueError(f"name map mismatch; missing={missing_names}, extra={extra_names}")
    if args.refresh_translations and TRANSLATION_CACHE_PATH.exists():
        TRANSLATION_CACHE_PATH.unlink()
    translations = build_translation_cache(items)
    resolved_types = resolve_types(items)

    # Keep downloaded cover paths when regenerating the formatted data.
    existing_local_covers: dict[tuple[str, str, str], str] = {}
    if OUTPUT_PATH.exists():
        existing_output = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        for existing_item in existing_output.get("list", []):
            local_cover = existing_item.get("local_cover")
            if local_cover:
                key = (
                    existing_item.get("name", ""),
                    existing_item.get("product_code", ""),
                    existing_item.get("cover", ""),
                )
                existing_local_covers[key] = local_cover

    formatted = []
    for item in items:
        source_type = resolved_types[item["name"]]
        cover_key = (item["name"], item["product_code"], item["cover"])
        formatted.append({
            "name": item["name"],
            "name_cns": NAME_CNS[item["name"]],
            "type": item["type"],
            "type_cn": TYPE_CN[source_type],
            "product_code": item["product_code"],
            "descriptions": item["descriptions"],
            "descriptions_cn": [polish_description(d, translations[d]) for d in item["descriptions"]],
            "cover": item["cover"],
            "local_cover": existing_local_covers.get(cover_key, ""),
            "detail_path": item["detail_path"],
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"list": formatted}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(formatted)} items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
