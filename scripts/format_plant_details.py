#!/usr/bin/env python3
"""Build translated Tropica plant details from the raw detail data."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DETAIL_PATH = ROOT / "raw" / "tropica.com" / "plant-detail-list.json"
FORMATTED_LIST_PATH = ROOT / "formatted" / "plant-list.json"
OUTPUT_PATH = ROOT / "formatted" / "plant-detail-list.json"
TRANSLATION_CACHE_PATH = ROOT / "scripts" / "detail-introduction-translations.json"

ORIGIN_CN = {
    "": "",
    "Africa": "非洲",
    "Asia": "亚洲",
    "Australia": "澳大利亚",
    "Cosmopolitan": "世界广布",
    "Cultivar": "栽培品种",
    "Europe/Asia": "欧洲／亚洲",
    "North America": "北美洲",
    "South America": "南美洲",
}

PROPERTY_DESCRIPTION_CN = {
    "type": "",
    "origin": "水草最常见的国家或洲。栽培品种是在人工环境中出现或选育而成的。",
    "growth_rate": "与其他水草相比，该水草的生长速度。",
    "height": "水草入缸两个月后的平均高度（厘米）。",
    "light_requirement": "水草的平均或中等光照需求约为 0.5 W/L。",
    "co2_requirement": "中等 CO₂ 需求为 6-14 mg/L，高需求约为 15-25 mg/L。",
    "type_cn": "",
    "origin_cn": "水草最常见的国家或洲。栽培品种是在人工环境中出现或选育而成的。",
}

GENUS_CN = {
    "Alternanthera": "血心兰",
    "Anubias": "水榕",
    "Bolbitis": "黑木蕨",
    "Bucephalandra": "辣椒榕",
    "Cryptocoryne": "椒草",
    "Echinodorus": "皇冠草",
    "Microsorum": "铁皇冠",
}

INTRODUCTION_OVERRIDES_BY_NAME = {
    "Alternanthera reineckii 'Mini'": "迷你血心兰采用密封杯组织培养，是常见血心兰的小型品种。它株型紧凑、生长较慢，适合小型水族箱，也可在大型造景中作前景草。通过定期修剪可形成约 5-10 厘米高的红紫色草坪。较强光照并补充 CO₂，有助于水草生长和发色。",
    "Anubias barteri ’Coin Leaf’": "金钱榕是水榕的栽培品种，叶片近圆形，直径约 4-6 厘米，呈深绿色。它生长缓慢并横向匍匐，弱光下也能正常生长，养护要求不高。可固定在石材或沉木上；若种入底床，根茎必须露出，否则容易腐烂。",
    "Anubias barteri var. nana ’Kirin’": "麒麟小榕是水榕的栽培品种，深绿色卵形叶片长约 3-4 厘米，叶缘有明显波浪。它生长缓慢，适应弱光，适合固定在沉木或石材上。种入底床时不要埋住根茎，以免腐烂。",
    "Anubias barteri var. nana ’Pinto’": "平托小榕是水榕的斑叶栽培品种，叶片长约 3-6 厘米，带有白色、浅绿色和深绿色斑纹；斑纹会随环境变化，有时也会长出全绿叶。适当提高光照可使白斑更明显，但光照过强容易损伤叶片并诱发藻类。它生长缓慢，适合固定在石材或沉木上，根茎不能埋入底床。",
    "Bacopa salzmannii 'Purple'": "紫虎耳原产南美洲湿地，叶片呈紫色和绿色。中高强度光照更有利于紫色发色，适合放在中景或后景。富含养分的底床、定期施肥和补充 CO₂ 有助于维持生长与色彩。生长速度中等，可通过茎段扦插繁殖。",
    "Bacopa monnieri 'Compact'": "迷你小对叶是 Bacopa monnieri 的紧凑型栽培品种，光照良好时株型接近匍匐。剪去向上直立生长的枝条，可促使它长出更多侧枝，保持低矮紧凑；它在其他水草的阴影下也能生长。适合用作稍高的铺地草，或种在中景、前景。不补充 CO₂ 或光照较弱时，植株会更直立，株型也会变得松散。",
    "Bucephalandra sordidula 'Blue'": "蓝色辣椒榕原产婆罗洲河岸，叶片在光线下会呈现蓝色光泽。它生长缓慢，养护要求不高，低到中等光照即可生长；较强光照可让色泽更明显。适合固定在沉木或石材上，用作前景或中景。",
    "Ceratopteris thalictroides": "水蕨广布于热带地区，株高约 15-30 厘米，株幅约 10-20 厘米。它通常生长较快，必要时可补充 CO₂ 促进生长。在小型开放式水族箱中，叶片可以伸出水面并形成水上叶。细密分枝的叶片观赏性较好，也能与其他叶形形成对比。光照充足时，水蕨会快速吸收大量养分，帮助抑制藻类，因此很适合作为小型水族箱的开缸草。",
    "Heteranthera zosterifolia": "罗丝草原产南美洲，容易长出侧枝，很快就能形成茂密株丛。茎高约 30-50 厘米，株幅约 6-12 厘米，叶片背面常会变黑。强光下生长旺盛，需要及时修剪，避免下层叶片因遮光而衰弱。茎节经常长出水生根，可剪下枝条重新栽种。开放式水族箱中，若让部分枝条沿水面生长，还可能开出小型蓝花。",
    "Lobelia cardinalis 'Mini'": "水草偶尔会出现不同于原有株型的变异，迷你罗贝里便是其中一例。它由普通罗贝里的生产苗中出现的变异株选育而来，浅绿色叶片排列得更紧密，植株也明显更小，因此得名“Mini”。它株型低矮、紧凑，即使不修剪也容易分枝，很少长出普通罗贝里常见的细长直立枝。剪下的枝条可直接插入底床繁殖。光照良好并补充 CO₂ 时株型最紧凑，但缺少这些条件也能正常生长。",
    "Hygrophila odora": "香水蓑衣生长较快，叶片鲜绿，容易形成浓密株丛，适合中景或后景。它对水质和光照的适应范围较广，中等光照即可正常生长。定期修剪可保持紧凑株型，新鲜绿色也能与红色或深色水草形成对比。",
    "Hygrophila polysperma 'White'": "白青叶是在丹麦 Tropica 温室选育的品种。水上叶为浅绿色，有时带有细小突起；转为水下生长后，叶片会呈现浅绿色和白色斑纹。它直立生长、容易分枝，定期修剪可使株型更紧凑。生长速度较慢，适应范围较广；充足光照能让白斑更清楚，但仍需避免过强光照。适合中景或后景。",
    "Hygrophila serpyllum": "匍匐水蓑衣株型低矮紧凑，叶片鲜绿，可用于前景或中景，并逐渐铺展成草坪。它在中等光照下生长良好，对水质的适应范围较广，生长速度容易控制。偶尔修剪即可维持低矮、浓密的状态。",
    "Eleocharis pusilla 'Mini'": "迷你牛毛毡采用密封杯组织培养。它的株型比常见的迷你牛毛毡更低矮，由美国水草玩家 Thomas Barr 提供给 Tropica。将植株分成小丛并分散栽种，短时间内即可形成致密草坪。充足光照有助于维持低矮株型；叶片仅长约 3-5 厘米，日常修剪较少，适合迷你水族箱。",
    "Microsorum pteropus nano wood": "这款产品将细叶铁皇冠预先固定在迷你沉木上，可直接放入水族箱。细长拱形的叶片从沉木上展开，适合小型造景。它在低到中等光照下即可生长，无需额外补充 CO₂，生长缓慢，日常养护和修剪都很少。",
    "Riccardia chamedryfolia": "珊瑚莫丝现为 Tropica 1-2-Grow! 系列产品。它属于叶苔类，枝体细密，外形近似珊瑚，适合固定在石材或沉木上，也可铺成低矮草坪。它适应低到中等光照和多种水质，生长缓慢，修剪需求较少，能够形成紧密的小丛。",
    "Sagittaria subulata 'Needle Leaf'": "针叶水兰可能是迷你水兰的一个变种，叶片狭长，长约 15-30 厘米，宽仅数毫米。它容易养护，中等光照下即可生长，无需额外补充 CO₂；强光下叶片可能略带橙色。植株直立，适合作为自然风格的后景草，并可通过走茎繁殖。",
    "Selaginella uncinata": "翠云草是一种匍匐生长的卷柏类植物，茎叶密集，叶片带有蓝绿色光泽，适合潮湿的雨林缸或沼泽缸。它可以覆盖底床和造景素材，成活后生长较快，也可能蔓延到邻近植物上，可通过定期修剪控制范围。",
    "Solenostoma tetragonum 'Pearl Moss'": "珍珠莫丝是产自婆罗洲的叶苔类植物。小而圆的半透明叶片会形成深绿色、垫状的紧密株丛。它生长缓慢，可自然附着在石材和沉木上，适合迷你水族箱或大型造景中的细节位置，也可与辣椒榕等耐阴水草搭配。稳定的环境、均衡施肥和补充 CO₂ 有利于生长；状态良好时，密集叶片间会出现珍珠状氧气泡。",
    "Spirodela polyrrhiza": "紫萍是漂浮在水面的浮水植物，小而圆的绿色叶状体可为鱼类遮阴并提供躲藏处。它在低到中等光照下都能快速生长，通过吸收水中养分抑制藻类并改善水质。需要定期捞除过密植株，避免遮挡下层水草的光照。",
}

INTRODUCTION_OVERRIDES_BY_PRODUCT_CODE = {
    "000C ST": "Cladophora aegagropila 并不是真正的水草，而是直径约 3-10 厘米的球状藻体。水波推动会使它逐渐形成球形；放入水族箱后需定期翻面，才能保持形状。它也可以分成小块，之后重新长成球状，或固定在沉木和石材上铺展开来。日本部分地区对其实施保护。",
    "000D MP": "本产品包含 3 个采用透气吸塑包装的海藻球。Cladophora aegagropila 并不是真正的水草，而是直径约 3-10 厘米的球状藻体。水波推动会使它逐渐形成球形；放入水族箱后需定期翻面，才能保持形状。它也可以分成小块，之后重新长成球状，或固定在沉木和石材上铺展开来。日本部分地区对其实施保护。",
    "000E POR": "Cladophora aegagropila 并不是真正的水草，而是直径约 2-10 厘米的球状藻体。水波推动会使它逐渐形成球形；放入水族箱后需定期翻面，才能保持形状。它也可以分成小块，之后重新长成球状，或固定在沉木和石材上铺展开来。日本部分地区对其实施保护。",
    "053H TC": "喷泉太阳采用密封杯组织培养。它由水草玩家在泰国靠近缅甸边境的地区发现，当地称其为“Downoi”，意为“小星星”。植株高和宽均约 5-10 厘米，株型紧凑，鲜绿色叶片明显卷曲。光照良好、底床养分充足时，它会长出许多带小根的侧芽，很快铺成前景草坪。",
    "053H YLS": "本产品为附生在熔岩石上的喷泉太阳。它由水草玩家在泰国靠近缅甸边境的地区发现，当地称其为“Downoi”，意为“小星星”。植株高和宽均约 5-10 厘米，株型紧凑，鲜绿色叶片明显卷曲。光照良好、底床养分充足时，它会长出许多带小根的侧芽，很快铺成前景草坪。",
    "053H": "喷泉太阳由水草玩家在泰国靠近缅甸边境的地区发现，当地称其为“Downoi”，意为“小星星”。植株高和宽均约 5-10 厘米，株型紧凑，鲜绿色叶片明显卷曲。光照良好、底床养分充足时，它会长出许多带小根的侧芽，很快铺成前景草坪。",
    "003B POR": "垂泪莫丝据认为原产中国，由 Oriental Aquarium Plants 推广。它是肉质的下垂型莫丝，高约 1-3 厘米，鲜绿色枝条呈泪滴状。适合固定在沉木或树根上，下垂的生长姿态可增强造景的纵深与层次。它养护要求不高、生长较快，需要经常用剪刀修剪来保持株型。",
    "003B TC": "垂泪莫丝采用密封杯组织培养。据认为它原产中国，由 Oriental Aquarium Plants 推广。它是肉质的下垂型莫丝，高约 1-3 厘米，鲜绿色枝条呈泪滴状。适合固定在沉木或树根上，下垂的生长姿态可增强造景的纵深与层次。它养护要求不高、生长较快，需要经常用剪刀修剪来保持株型。",
    "023D CLP": "豹纹血心兰是生长旺盛的栽培品种，粉红色叶片配有浅色叶脉。它株型紧凑，茎不如其他血心兰粗壮。修剪得当时适合种在中景，甚至可作前景草。与其他血心兰一样，良好光照、充足肥料和补充 CO₂ 都有助于生长与发色。",
    "109 TC": "绿温蒂椒草采用密封杯组织培养。叶片呈鲜绿色，株高会随缸内条件变化，约为 10-30 厘米，莲座丛宽约 8-15 厘米。在开阔处种植时，叶片几乎贴着底床展开。和大多数斯里兰卡椒草一样，它也能适应硬水。养护简单，对环境的适应范围很广，在大型水草的遮阴下仍可正常生长。",
    "074D": "红钻皇冠草是在乌克兰出现的栽培品种，可能由 Echinodorus horemanni 'Red' 与 Echinodorus 'Barthii' 杂交而来。剑形叶片呈宝石红色，长约 15-25 厘米；莲座丛宽约 20-30 厘米，株型比许多皇冠草更适中，即使在小型水族箱中也适合作为单株焦点。提高底床养分可使生长更旺盛，良好光照则有利于红色叶片的形成。",
    "072B XL": "大型玫瑰皇冠草母株种植在 9 厘米方盆中。它是 Echinodorus horemanii 'Red' 与 Echinodorus horizontalis 的杂交品种，1986 年由 Hans Barth 在德绍首次培育。株高约 25-40 厘米，莲座丛宽约 15-25 厘米。新长出的水下叶呈粉红色，初期带有红褐色斑点。富含养分的底床有助于生长，其他养护要求不高，适合新手。",
    "072B": "玫瑰皇冠草是 Echinodorus horemanii 'Red' 与 Echinodorus horizontalis 的杂交品种，1986 年由 Hans Barth 在德绍首次培育。株高约 25-40 厘米，莲座丛宽约 15-25 厘米。新长出的水下叶呈粉红色，初期带有红褐色斑点。富含养分的底床有助于生长，其他养护要求不高，适合新手。",
    "072A CLP": "红香瓜草适合在大型水族箱中单株种植。株高约 25-50 厘米，莲座丛宽约 20-30 厘米；新叶呈深红色，老叶会逐渐转为深绿色。较强光照和充足的微量元素有利于发色，富含养分的底床和补充 CO₂ 可促进生长。植株会遮挡下方水草，需要适时修剪。这个品种过去曾以“Double Red”的名称销售。",
    "072A XL": "大型红香瓜草母株种植在 9 厘米方盆中，适合在大型水族箱中单株种植。株高约 25-50 厘米，莲座丛宽约 20-30 厘米；新叶呈深红色，老叶会逐渐转为深绿色。较强光照和充足的微量元素有利于发色，富含养分的底床和补充 CO₂ 可促进生长。植株会遮挡下方水草，需要适时修剪。这个品种过去曾以“Double Red”的名称销售。",
    "072A": "红香瓜草适合在大型水族箱中单株种植。株高约 25-50 厘米，莲座丛宽约 20-30 厘米；新叶呈深红色，老叶会逐渐转为深绿色。较强光照和充足的微量元素有利于发色，富含养分的底床和补充 CO₂ 可促进生长。植株会遮挡下方水草，需要适时修剪。这个品种过去曾以“Double Red”的名称销售。",
    "051A YWS": "本产品将羽裂水蓑衣与莫丝固定在红树林沉木上。羽裂水蓑衣原产印度，叶面呈带斑纹的棕色，叶背为鲜明的酒红色。摘除顶芽可促使植株长出横向侧枝，保持紧凑株型；侧枝也容易附着在沉木和石材上。它生长速度中等，茎高约 15-40 厘米，株幅约 10-20 厘米。小丛种植并搭配简洁背景时色彩更醒目，较强光照有助于维持紧凑株型。",
    "051A TC": "羽裂水蓑衣采用密封杯组织培养。它原产印度，叶面呈带斑纹的棕色，叶背为鲜明的酒红色。摘除顶芽可促使植株长出横向侧枝，保持紧凑株型；侧枝也容易附着在沉木和石材上。它生长速度中等，茎高约 15-40 厘米，株幅约 10-20 厘米。小丛种植并搭配简洁背景时色彩更醒目，较强光照有助于维持紧凑株型。",
    "051A": "羽裂水蓑衣原产印度，叶面呈带斑纹的棕色，叶背为鲜明的酒红色。摘除顶芽可促使植株长出横向侧枝，保持紧凑株型；侧枝也容易附着在沉木和石材上。它生长速度中等，茎高约 15-40 厘米，株幅约 10-20 厘米。小丛种植并搭配简洁背景时色彩更醒目，较强光照有助于维持紧凑株型。",
    "509 YCS": "本产品将羽裂水蓑衣与可持续椰壳洞穴组合在一起，兼顾造景和躲藏空间。羽裂水蓑衣原产印度，叶面呈带斑纹的棕色，叶背为鲜明的酒红色。它生长速度中等，茎高约 15-40 厘米，株幅约 10-20 厘米。小丛种植并搭配简洁背景时色彩更醒目；修剪茎枝可促使株丛变得更茂密。",
    "032D TC": "血红宫廷采用密封杯组织培养，是红宫廷中红色最浓的变种。与浅绿色水草搭配可衬托它鲜艳的红色。它容易栽培，在光照和养分相对较低时也能生长；若要达到最佳发色，则需要充足光照并补充 CO₂。茎直立或略呈弧形，分枝较多，定期修剪可改善茎间的光照和水流。",
    "035D": "绿丁香是超红水丁香的变种，株型和养护需求与亲本相同，是容易养护且表现稳定的有茎草。单根茎宽约 2-4 厘米，高约 10-30 厘米以上。它容易长出侧枝，修剪可促进分枝，使株丛更加浓密；剪下的枝条重新栽种后会很快生根。将超红水丁香和绿丁香混种，红色与浅绿色可以相互衬托。",
    "147 TC": "红小白菜在普通水族箱条件下就会呈现红色；提高光照并保证养分充足后，叶色会更加浓艳，适合作为中景或后景的点缀。水下叶小而圆，形似嫩菠菜叶，因此有时被误称为 Samolus parviflorus 'Red'；真正的 Samolus parviflorus 为绿色，叶形虽相近，但并非同一种水草。定期修剪可使红小白菜保持直立紧凑，剪下的枝条也容易重新栽种。稳定环境和均衡养分有利于发色。水族用途之外，Lysimachia parvifolia 也曾作为抗炎草药用于传统中医。",
    "023D": "豹纹血心兰为 5 厘米盆栽水草。这个生长旺盛的栽培品种拥有鲜艳的粉红色叶片和浅色叶脉，株型紧凑，茎不如其他血心兰粗壮。修剪得当时适合种在中景，甚至可作前景草。与其他血心兰一样，良好光照、充足肥料和补充 CO₂ 都有助于生长与发色。",
    "110B TC": "宽叶波浪椒草采用密封杯组织培养，是斯里兰卡河流中野生分布的红色型 Cryptocoryne undulata。它容易养护，能适应差异较大的缸内环境，株型也会随条件改变。光照和养分较少时，植株较高，叶片呈绿褐色，生长缓慢；提高光照和养分并补充 CO₂ 后，生长会明显加快，叶片更短并呈红褐色。",
    "109D TC": "宓大屋温蒂椒草采用密封杯组织培养，只见于斯里兰卡的 Mi Oya 河。红褐色叶片略带锤纹，长约 20-35 厘米，莲座丛宽约 15-30 厘米。许多椒草可以适应高温环境；这种椒草在野外就生长于水温超过 30 摄氏度的溪流中。",
    "072D TC": "蕊妮皇冠草采用密封杯组织培养，是较为知名的红色皇冠草栽培品种，也是其中株型较小的一种。株高约 15-40 厘米，莲座丛宽约 15-25 厘米，新叶呈红褐色至深甜菜红色。它养护要求不高，适合小型水族箱；若要获得最佳发色，需要充足光照和养分。",
    "067A TC": "针叶皇冠草旧称 Echinodorus tenellus 'Green'。这种小型莲座型水草在光照良好、底床养分充足时，容易形成约 5-10 厘米高的草坪。即使在强光下，这个品种仍会保持鲜绿色，不像普通 Helanthium tenellum 那样偏红。它是容易养护、要求不高的前景草。",
    "052A": "肋脉水蓑衣原产南美洲，茎长约 25-60 厘米，叶片长约 10 厘米。水下叶较窄，排列紧密；市售植株通常以水上叶形态培育，叶片较圆，节间也更长。这个品种过去使用 Hygrophila corymbosa 'Angustifolia' 这一名称。",
    "103 CLP": "美波莉椒草原产印度，外形接近中型宽叶椒草，在水族箱中的用法也与椒草相似，但需要充足光照才能正常发色。叶片宽约 4-8 厘米、长约 6-12 厘米，因此整株横向开展。叶色可从带亮紫色的灰绿色变化到红紫色，同一片叶上也可能同时出现多种颜色；新叶呈浅粉色。",
    "103": "美波莉椒草原产印度，外形接近中型宽叶椒草，在水族箱中的用法也与椒草相似，但需要充足光照才能正常发色。叶片宽约 4-8 厘米、长约 6-12 厘米，因此整株横向开展。叶色可从带亮紫色的灰绿色变化到红紫色，同一片叶上也可能同时出现多种颜色；新叶呈浅粉色。",
    "037E TC": "圭亚那羽毛采用密封杯组织培养，即使在很强的光照下也能保持鲜绿色。单根茎的株幅仅约 2-3 厘米（1 英寸），但很容易分枝，能够迅速形成浓密株丛。需要经常修剪，保证株丛内部的光照和水流。它生长速度适中，适合迷你水族箱。",
    "037C TC": "古巴锯齿草采用密封杯组织培养，是株高约 10-40 厘米、株幅约 5-10 厘米的有茎草。杯中植株带有锯齿叶，转入水族箱并经过适应期后，会长出细长、带细齿的针形叶。光照良好时叶片呈铜色，与其他水草形成鲜明对比。Proserpinaca palustris 的形态会因产地而异，Tropica 的这个品种发现于古巴青年岛；在美国通常称为“mermaid weed”。",
    "003G TC": "松茸莫丝采用密封杯组织培养，原产亚洲，高约 2-10 厘米。它常被形容为圣诞莫丝的“大哥”，整体更粗壮，能长出大量深绿色分枝。固定在垂直表面时，分枝形态最容易展现；也可将小丛间隔栽入底床，形成草坪效果。它生长较快，极弱光照下也能正常生长。",
    "003A POR": "圣诞莫丝原产巴西，高约 1-3 厘米。其侧枝结构不同于普通 Vesicularia dubyana，外形近似冷杉枝条，因此得名“圣诞莫丝”。它比普通爪哇莫丝要求更高、生长更慢，容易附着在树根和石材上；在水中铺展开后，需要定期修剪来保持株型。另可参见 Taxiphyllum barbieri。",
    "003A YWS": "圣诞莫丝原产巴西，高约 1-3 厘米。其侧枝结构不同于普通 Vesicularia dubyana，外形近似冷杉枝条，因此也叫“圣诞树莫丝”。它比普通爪哇莫丝要求更高、生长更慢，容易附着在树根和石材上；在水中铺展开后，需要定期修剪来保持株型。另可参见 Taxiphyllum barbieri。",
    "101G": "咖啡榕是 Anubias barteri 的矮生栽培品种，株高约 15-25 厘米，匍匐根茎长约 10-15 厘米或更长。叶片在叶脉之间明显隆起，新叶呈红褐色，独特的叶形和色彩适合大小不同的水族箱。它常在水下开花，但不会在水下结籽。和其他水榕一样，咖啡榕生长非常缓慢，也不容易被食草鱼啃食。",
    "139 CLP": "黑山辣椒榕生长缓慢、容易养护，适合较弱光照。它在自然环境中附生于河流和溪流里的石材或沉木上，用法和养护方式与水榕相近。不修剪也容易分枝并形成浓密株丛。绿色叶片宽约 2 厘米、长约 5 厘米，叶缘呈波浪状，水上叶会出现细小白点。栽种时不要掩埋匍匐根茎，否则植株会腐烂。",
    "139 TC": "黑山辣椒榕生长缓慢、容易养护，适合较弱光照。它在自然环境中附生于河流和溪流里的石材或沉木上，用法和养护方式与水榕相近。不修剪也容易分枝并形成浓密株丛。绿色叶片宽约 2 厘米、长约 5 厘米，叶缘呈波浪状，水上叶会出现细小白点。栽种时不要掩埋匍匐根茎，否则植株会腐烂。",
    "139 YLS": "本产品为附生在熔岩石上的黑山辣椒榕。它生长缓慢、容易养护，适合较弱光照；在自然环境中也附生于河流和溪流里的石材或沉木上，用法和养护方式与水榕相近。不修剪也容易分枝并形成浓密株丛。绿色叶片宽约 2 厘米、长约 5 厘米，叶缘呈波浪状，水上叶会出现细小白点。栽种时不要掩埋匍匐根茎，否则植株会腐烂。",
    "139": "黑山辣椒榕为 5 厘米盆栽水草。它生长缓慢、容易养护，适合较弱光照；在自然环境中附生于河流和溪流里的石材或沉木上，用法和养护方式与水榕相近。不修剪也容易分枝并形成浓密株丛。绿色叶片宽约 2 厘米、长约 5 厘米，叶缘呈波浪状，水上叶会出现细小白点。栽种时不要掩埋匍匐根茎，否则植株会腐烂。",
    "139C TC": "针叶辣椒榕来自亚洲，生长和养护方式与非洲水榕有不少相似之处。它比 'diabolica' 和 'pygmaeae' 两类辣椒榕的要求稍高，但仍然容易栽培；适量补充 CO₂ 并提高一些光照会更有利。水上叶绿色、细长且略带波浪，表面散布细小白点，叶宽不足 0.5 厘米、长约 1-2 厘米。根茎新生部位呈红色，整体生长缓慢。栽种时不要掩埋匍匐根茎，否则植株会腐烂。",
    "139A": "本产品为盆栽红辣椒榕。辣椒榕的形态和养护方式与水榕相近，在自然环境中通常附生于水边或水中的石材、沉木上。红辣椒榕适合较弱光照，容易栽培。叶片呈深绿色或皮革红色，水下叶散布细小白点，有时带淡淡的金属蓝色；叶宽约 2-4 厘米、长约 4-6 厘米，叶缘通常呈波浪状。栽种时不要掩埋匍匐根茎，否则植株会腐烂。",
    "125 TC": "缎带椒草（Cryptocoryne crispatula var. balansae）采用密封杯组织培养，原产泰国南部石灰岩山区，当地水质可能很硬。它要求不高，但更喜欢养分充足的底床和良好光照。和许多椒草一样，入缸后需要先适应环境，之后才会明显生长。叶片长约 20-60 厘米，单个莲座丛宽约 15-20 厘米，适合种在后景，让长叶沿水面舒展。叶色可能为全绿或栗红色。",
    "125": "缎带椒草（Cryptocoryne crispatula var. balansae）原产泰国南部石灰岩山区，当地水质可能很硬。和许多椒草一样，入缸后需要先适应环境，之后才会明显生长。叶片长约 20-60 厘米，单个莲座丛宽约 15-20 厘米。",
    "033 CLP": "红宫廷原产东南亚，株高约 15-30 厘米，株幅约 2-3 厘米，水下叶细长。它比其他宫廷草更容易养护，但需要良好光照才能长出红叶。植株容易分枝并形成紧凑株丛，因此下层叶片也容易被遮光，需要经常修剪。其拉丁学名有“圆叶”之意，但仅水上叶呈圆形。也曾使用 Rotala indica 这一名称。",
    "033 MP": "红宫廷种植在椰纤维迷你盆中，并采用透气吸塑包装，可直接放入水族箱继续生长。它原产东南亚，株高约 15-30 厘米，株幅约 2-3 厘米，水下叶细长。它比其他宫廷草更容易养护，但需要良好光照才能长出红叶。植株容易分枝并形成紧凑株丛，因此下层叶片也容易被遮光，需要经常修剪。其拉丁学名有“圆叶”之意，但仅水上叶呈圆形。",
    "033 PCS": "红宫廷为盆栽水草，采用透气吸塑包装。它原产东南亚，株高约 15-30 厘米，株幅约 2-3 厘米，水下叶细长。它比其他宫廷草更容易养护，但需要良好光照才能长出红叶。植株容易分枝并形成紧凑株丛，因此下层叶片也容易被遮光，需要经常修剪。其拉丁学名有“圆叶”之意，但仅水上叶呈圆形。",
    "033": "红宫廷原产东南亚，株高约 15-30 厘米，株幅约 2-3 厘米，水下叶细长。它比其他宫廷草更容易养护，但需要良好光照才能长出红叶。植株容易分枝并形成紧凑株丛，因此下层叶片也容易被遮光，需要经常修剪。其拉丁学名有“圆叶”之意，但仅水上叶呈圆形。也曾使用 Rotala indica 这一名称。",
    "107 CLP": "威利斯椒草原产斯里兰卡，过去常被误称为 Cryptocoryne nevillii，但后者实际上并未用于水族栽培。它和许多椒草一样，种下后的第一个月生长不明显，适应后会长出大量走茎并形成紧密株丛。株高约 7-20 厘米，单个莲座丛宽约 7-15 厘米。",
    "091A": "越南谷精的鲜绿色叶片细长而尖，在基部组成莲座丛，外形近似松针。它需要中等光照，补充 CO₂ 有利于生长；适合富含养分的底床以及偏软、微酸性的水质。定期施肥和日常养护可避免缺素，维持健康生长。",
    "035B CLP": "超红水丁香是一种广布型有茎草，比常见的红轮水丁香更容易发红，株型也更小。单根茎宽约 2-4 厘米、高约 10-30 厘米。它容易长出侧枝，修剪可促进分枝，使株丛更加浓密；剪下的枝条重新栽种后会很快生根。光照充足并补充 CO₂ 时，植株生长更好，红色也更浓。",
    "035B": "超红水丁香是一种广布型有茎草，比常见的红轮水丁香更容易发红，株型也更小。单根茎宽约 2-4 厘米、高约 10-30 厘米。它容易长出侧枝，修剪可促进分枝，使株丛更加浓密；剪下的枝条重新栽种后会很快生根。光照充足并补充 CO₂ 时，植株生长更好，红色也更浓。",
    "019": "虎斑睡莲原产西非，叶色从绿色到红褐色不等，并带有数量不一的紫色斑点，株高约 20-80 厘米。长出浮叶前会先形成大量水下叶；若不希望出现浮叶，可修剪根和叶。开放式水族箱更便于观赏其芳香花朵，富含养分的底床有助于生长。市面上常见红色型和绿色型，适合在大型水族箱中单株种植。",
    "410 TC": "百里香莫丝适用于雨林缸，与常见莫丝相比叶片较大，株丛茂密且富有质感，外形接近北美物种 Plagiomnium cuspidatum。鲜绿色叶片半透明，叶缘呈波浪状，在高湿环境中状态较好。与细叶莫丝或热带植物搭配时，较大的叶片能形成明显对比。可用于铺设柔软草坪、覆盖造景素材，或营造林地氛围，适合雨林缸和沼泽缸。",
    "032 TC": "红蝴蝶 'Japan' 观赏性很强，但养护难度较高；这个变种相对容易栽培，发色也更好。它需要很强的光照才能呈现红色，补充 CO₂ 和使用软水同样是良好生长的重要条件。修剪时可在离底床 5-10 厘米处剪下最长的茎，再重新成丛栽种。",
    "032C TC": "H'ra 宫廷采用密封杯组织培养，叶片较窄，生长姿态偏下垂或匍匐。它可能是红宫廷的一个变种，外形与绿宫廷很相似。较强光照、充足液肥和补充 CO₂ 可促使植株主要沿水平方向生长，并呈现浓郁的暖橙色，可形成密集的橙色中景草垫，甚至用作橙色前景草坪。",
    "003H TC": "火焰莫丝采用密封杯组织培养，因独特株型得名。深绿色枝条紧密直立，并带柔和起伏，整体形似篝火，高约 5-15 厘米。它横向扩展较慢，适合固定在水平表面；也可绑在小石块上，或成小束固定在树根、沉木上。",
    "053F TC": "德干刺蕊草原产印度，过去称为直立百叶。它会形成紧凑的鲜绿色针叶状茎丛，株高约 15-40 厘米，株幅约 1-3 厘米，适合作为后景草；无论小丛还是大丛种植，都能成为视觉焦点。较强光照有助于长时间保持紧凑株型。它生长速度中等、根系发达，需要经常修剪，剪下的枝条重新栽种后很容易继续生长。",
    "053F": "德干刺蕊草原产印度，过去称为直立百叶。它会形成紧凑的鲜绿色针叶状茎丛，株高约 15-40 厘米，株幅约 1-3 厘米，适合作为后景草；无论小丛还是大丛种植，都能成为视觉焦点。较强光照有助于长时间保持紧凑株型。它生长速度中等、根系发达，需要经常修剪，剪下的枝条重新栽种后很容易继续生长。",
    "044A PCS": "迷你小对叶为盆栽水草，采用透气吸塑包装。它是 Bacopa monnieri 的紧凑型栽培品种，光照良好时株型接近匍匐。剪去向上直立生长的枝条，可促使它长出更多侧枝，保持低矮紧凑；它在其他水草的阴影下也能生长。适合用作稍高的铺地草，或种在中景、前景。不补充 CO₂ 或光照较弱时，植株会更直立，株型也会变得松散。",
}

TEXT_REPLACEMENTS = (
    ("活的水草放在盆里，装在透气的吸塑包装里走。", "盆栽水草，采用透气吸塑包装。"),
    ("盆栽的活水草，装在透气的泡罩包装中带走。", "盆栽水草，采用透气吸塑包装。"),
    ("闭杯组织培养的水族植物", "采用密封杯组织培养的水草"),
    ("闭杯组织培养的水草", "采用密封杯组织培养的水草"),
    ("水族馆植物", "水草"),
    ("水族植物", "水草"),
    ("水生植物", "水草"),
    ("水族馆", "水族箱"),
    ("坦克", "水族箱"),
    ("水箱", "水族箱"),
    ("前景植物", "前景草"),
    ("中景植物", "中景草"),
    ("背景植物", "后景草"),
    ("地被植物", "铺地草"),
    ("岩石和木材", "石材和沉木"),
    ("岩石或木材", "石材或沉木"),
    ("木材和岩石", "沉木和石材"),
    ("木材或岩石", "沉木或石材"),
    ("岩石和木头", "石材和沉木"),
    ("岩石或木头", "石材或沉木"),
    ("木头和岩石", "沉木和石材"),
    ("木头或岩石", "沉木或石材"),
    ("根和石头", "沉木和石材"),
    ("根和岩石", "沉木和石材"),
    ("石头和树根", "石材和沉木"),
    ("岩石和树根", "石材和沉木"),
    ("石头", "石材"),
    ("岩石", "石材"),
    ("木头", "沉木"),
    ("木材", "沉木"),
    ("浮木", "沉木"),
    ("树根", "沉木"),
    ("基质", "底床"),
    ("纳米水族箱", "迷你水族箱"),
    ("纳米水箱", "迷你水族箱"),
    ("Nano Cubes", "迷你方缸"),
    ("苔藓", "莫丝"),
    ("地毯", "草坪"),
    ("跑步者", "走茎"),
    ("流纹", "走茎"),
    ("每个玫瑰花", "每个莲座丛"),
    ("玫瑰花状", "莲座状"),
    ("玫瑰状", "莲座状"),
    ("砍伐", "修剪"),
    ("工厂", "水草"),
    ("发酵剂植物", "入门水草"),
    ("茎植物", "有茎草"),
    ("培养形式", "栽培品种"),
    ("锚上", "配重环中"),
    ("取下锚", "取下配重环"),
    ("一束茎或幼苗聚集在配重环中。", "成束茎草或幼苗由配重环固定。"),
    ("取下配重环并分裂成单独的植物。", "取下配重环，将植株逐一分开。"),
    ("根很快就会发育，植物开始生长。", "植株很快会长出新根并恢复生长。"),
    ("底部底床", "底床"),
    ("种植在底部", "种入底床"),
    ("重新种植在底部", "重新种入底床"),
    ("蔓延到底部", "沿底床蔓延"),
    ("营养丰富的底部", "富含养分的底床"),
    ("底层", "底床"),
    ("营养物质", "养分"),
    ("营养素", "养分"),
    ("水参数", "水质参数"),
    ("水族造景师", "造景玩家"),
    ("水族爱好者", "水草玩家"),
    ("水生花园", "水草造景"),
    ("水生天堂", "水草造景"),
    ("低维护", "养护省心"),
    ("有吸引力的", "观赏性较好的"),
    ("美观、致密的外观", "紧凑浓密的株型"),
    ("紧凑且有吸引力的生长", "紧凑的株型"),
    ("紧凑且有吸引力的增长", "紧凑的株型"),
    ("低矮且紧密的生长", "低矮紧凑的株型"),
    ("生长速度一般为平均", "生长速度中等"),
    ("增长率是平均水平", "生长速度中等"),
    ("隐花藻", "椒草"),
    ("匍匐茎、根茎", "匍匐根茎"),
    ("印度美女", "这种水草"),
    ("完美搭配", "搭配效果较好"),
    ("随意彻底修剪一组植物", "可对成丛植株进行重剪"),
    ("并且你的植物会变得更厚", "使株丛更加浓密"),
    ("光照条件的减少", "光照较弱"),
    ("植物会变得更加垂直生长并且不那么紧凑", "植株会更直立，株型也会变得松散"),
    ("稍高一点的草坪", "稍高的铺地草"),
    ("水族箱中部或前面", "水族箱中景或前景"),
    ("制作草坪", "形成草坪"),
    ("发挥最佳性能", "达到最佳状态"),
    ("茁壮成长", "生长良好"),
    ("整体外观", "整体状态"),
    ("主要优点", "主要特点："),
    ("爪哇蕨", "铁皇冠"),
    ("爪哇苔藓", "爪哇莫丝"),
    ("圣诞苔藓", "圣诞莫丝"),
    ("台湾苔藓", "台湾莫丝"),
    ("垂枝苔藓", "垂泪莫丝"),
    ("二氧化碳", "CO₂"),
    ("光强度", "光照强度"),
    ("没有CO₂添加", "未添加 CO₂"),
    ("添加CO₂", "添加 CO₂"),
    ("特别适合", "适合"),
    ("非常适合", "适合"),
    ("完美适合", "适合"),
    ("绝佳选择", "合适的选择"),
    ("理想选择", "合适的选择"),
    ("最为美丽", "观赏效果最好"),
    ("极其美丽的", "观赏性较强的"),
    ("非常美丽的", "观赏性较强的"),
    ("美丽的", ""),
    ("漂亮且", ""),
    ("脱颖而出", "较为醒目"),
    ("令人惊叹的", "观赏性很强的"),
    ("迷人的", "颇具观赏性的"),
    ("充满活力的", "鲜艳的"),
    ("自愿分枝", "容易分枝"),
    ("自愿形成", "容易形成"),
    ("愿意产生", "容易长出"),
)


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_translation_payload(payload: object) -> str:
    if isinstance(payload, list) and payload and isinstance(payload[0], str):
        return payload[0]
    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        return "".join(
            part[0]
            for part in payload[0]
            if isinstance(part, list) and part and isinstance(part[0], str)
        )
    raise ValueError(f"unexpected translation response: {payload!r}")


def placeholder(index: int) -> str:
    """Return visually distinct letter-only tokens that translators preserve."""
    letters = ""
    value = index
    while True:
        value, remainder = divmod(value, 26)
        letters = chr(ord("A") + remainder) + letters
        if value == 0:
            break
        value -= 1
    return f"ZXQKEEP{letters}QXZ"


def protect_terms(
    text: str,
    phrase_translations: dict[str, str],
    name_translations: dict[str, list[str]],
    genera: set[str],
) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}

    for name in sorted(name_translations, key=len, reverse=True):
        if name in text:
            token = placeholder(len(replacements))
            text = text.replace(name, token)
            replacements[token] = name_translations[name][0]

    matched_phrases = [
        phrase
        for phrase in sorted(phrase_translations, key=len, reverse=True)
        if phrase in text
    ]
    for phrase in matched_phrases:
        token = placeholder(len(replacements))
        text = text.replace(phrase, token)
        replacements[token] = phrase_translations[phrase]

    for genus in sorted(genera, key=len, reverse=True):
        if re.search(rf"\b{re.escape(genus)}\b", text):
            token = placeholder(len(replacements))
            text = re.sub(rf"\b{re.escape(genus)}\b", token, text)
            replacements[token] = genus
    return text, replacements


def request_translation(text: str) -> str:
    endpoints = (
        (
            "https://clients5.google.com/translate_a/t",
            {"client": "dict-chrome-ex", "sl": "en", "tl": "zh-CN", "q": text},
        ),
        (
            "https://translate.googleapis.com/translate_a/single",
            {
                "client": "dict-chrome-ex",
                "sl": "en",
                "tl": "zh-CN",
                "dt": "t",
                "q": text,
            },
        ),
    )
    last_error: Exception | None = None
    for attempt in range(4):
        for endpoint, params in endpoints:
            url = endpoint + "?" + urllib.parse.urlencode(params)
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                return parse_translation_payload(payload)
            except Exception as error:
                last_error = error
        if attempt < 3:
            time.sleep(1.5 * (2**attempt))
    raise RuntimeError(f"translation failed: {last_error}")


def translate_introduction(
    source: str,
    phrase_translations: dict[str, str],
    name_translations: dict[str, list[str]],
    genera: set[str],
) -> str:
    if not source:
        return ""
    protected, replacements = protect_terms(
        source, phrase_translations, name_translations, genera
    )
    translated = request_translation(protected)
    translated = re.sub(r"[\u200b-\u200d\ufeff]", "", translated)
    for token, replacement in replacements.items():
        if token not in translated:
            raise ValueError(f"translation lost protected token {token}")
        translated = translated.replace(token, replacement)
    return translated


def build_translation_cache(
    introductions: list[str],
    phrase_translations: dict[str, str],
    name_translations: dict[str, list[str]],
    genera: set[str],
    workers: int,
    refresh: bool,
) -> dict[str, str]:
    if TRANSLATION_CACHE_PATH.exists() and not refresh:
        cache = json.loads(TRANSLATION_CACHE_PATH.read_text(encoding="utf-8"))
    else:
        cache = {}
    cache[""] = ""
    missing = [text for text in introductions if text not in cache]

    for offset in range(0, len(missing), workers):
        batch = missing[offset : offset + workers]
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    translate_introduction,
                    text,
                    phrase_translations,
                    name_translations,
                    genera,
                ): text
                for text in batch
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    cache[source] = future.result()
                except Exception as error:
                    failures.append(f"{source[:80]!r}: {error}")
        atomic_write_json(TRANSLATION_CACHE_PATH, cache)
        completed = min(offset + len(batch), len(missing))
        if completed % 25 == 0 or completed == len(missing):
            print(f"translated {completed}/{len(missing)} introductions")
        if failures:
            raise RuntimeError("translation failures:\n" + "\n".join(failures))
        time.sleep(0.25)
    return cache


def naturalize_translation(
    translated: str,
    name_translations: dict[str, list[str]],
    name: str,
    product_code: str,
) -> str:
    if product_code in INTRODUCTION_OVERRIDES_BY_PRODUCT_CODE:
        return INTRODUCTION_OVERRIDES_BY_PRODUCT_CODE[product_code]
    if name in INTRODUCTION_OVERRIDES_BY_NAME:
        return INTRODUCTION_OVERRIDES_BY_NAME[name]

    text = translated
    for name in sorted(name_translations, key=len, reverse=True):
        text = text.replace(name, name_translations[name][0])
    for genus, chinese in GENUS_CN.items():
        text = re.sub(rf"\b{re.escape(genus)}\b(?!\s+[a-z])", chinese, text)
    for old, new in TEXT_REPLACEMENTS:
        text = text.replace(old, new)

    text = text.replace("CO2", "CO₂").replace("CO 2", "CO₂")
    text = re.sub(r"([\u4e00-\u9fff]{2,12})（\1）", r"\1", text)
    text = text.replace("0,5", "0.5")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s+([，。；：！？、）】])", r"\1", text)
    text = re.sub(r"([，。；：！？、])\s+", r"\1", text)
    text = re.sub(r"([（【])\s+", r"\1", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*(?:至|到)\s*(\d+(?:\.\d+)?)\s*厘米", r"\1-\2 厘米", text)
    text = re.sub(r"(?<=\d)\s*(厘米|毫米|米|升|毫克|英寸|摄氏度)", r" \1", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])(?=[A-Za-z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z])(?=[\u4e00-\u9fff])", " ", text)
    text = re.sub(r"(\d+)“", r"\1 英寸", text)
    text = text.replace(" - ", "，")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--refresh-translations", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 5:
        parser.error("--workers must be between 1 and 5")

    raw_payload = json.loads(RAW_DETAIL_PATH.read_text(encoding="utf-8"))
    formatted_list = json.loads(FORMATTED_LIST_PATH.read_text(encoding="utf-8"))["list"]
    raw_details = raw_payload["detail_list"]

    formatted_by_key = {
        (item["name"], item["product_code"]): item for item in formatted_list
    }
    detail_keys = {(item["name"], item["product_code"]) for item in raw_details}
    if detail_keys != set(formatted_by_key):
        missing = sorted(detail_keys - set(formatted_by_key))
        extra = sorted(set(formatted_by_key) - detail_keys)
        raise ValueError(f"plant list mismatch; missing={missing}, extra={extra}")

    name_translations: dict[str, list[str]] = {}
    phrase_translations: dict[str, str] = {}
    for item in formatted_list:
        name_translations.setdefault(item["name"], item["name_cns"])
        phrase_translations.update(zip(item["descriptions"], item["descriptions_cn"]))
    genera = {item["name"].split()[0] for item in raw_details}
    introductions = list(dict.fromkeys(item["introduction"] for item in raw_details))
    translations = build_translation_cache(
        introductions,
        phrase_translations,
        name_translations,
        genera,
        workers=args.workers,
        refresh=args.refresh_translations,
    )

    # Keep downloaded image paths when regenerating translated detail data.
    existing_local_assets: dict[tuple[str, str], tuple[str, list[str]]] = {}
    if OUTPUT_PATH.exists():
        existing_payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        for existing_item in existing_payload.get("detail_list", []):
            key = (
                existing_item.get("name", ""),
                existing_item.get("product_code", ""),
            )
            existing_local_assets[key] = (
                existing_item.get("local_illustration", ""),
                list(existing_item.get("local_images", [])),
            )

    formatted_details = []
    for detail in raw_details:
        list_item = formatted_by_key[(detail["name"], detail["product_code"])]
        properties = dict(detail["properties"])
        origin = properties["origin"]
        if origin not in ORIGIN_CN:
            raise ValueError(f"unknown origin {origin!r}")
        properties["type_cn"] = list_item["type_cn"]
        properties["origin_cn"] = ORIGIN_CN[origin]
        local_illustration, local_images = existing_local_assets.get(
            (detail["name"], detail["product_code"]), ("", [])
        )
        if local_images and len(local_images) != len(detail["images"]):
            raise ValueError(
                f"local image count mismatch for {detail['product_code']}: "
                f"{len(local_images)} != {len(detail['images'])}"
            )
        formatted_details.append(
            {
                "name": detail["name"],
                "name_cns": list_item["name_cns"],
                "product_code": detail["product_code"],
                "properties": properties,
                "introduction": detail["introduction"],
                "introduction_cn": naturalize_translation(
                    translations[detail["introduction"]],
                    name_translations,
                    detail["name"],
                    detail["product_code"],
                ),
                "illustration": detail["illustration"],
                "images": detail["images"],
                "layouts": detail["layouts"],
                "local_illustration": local_illustration,
                "local_images": local_images,
            }
        )

    payload = {
        "detail_list": formatted_details,
        "meta": {
            "property_description": raw_payload["meta"]["property_description"],
            "property_description_cn": PROPERTY_DESCRIPTION_CN,
        },
    }
    atomic_write_json(OUTPUT_PATH, payload)
    print(f"wrote {len(formatted_details)} translated details to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
