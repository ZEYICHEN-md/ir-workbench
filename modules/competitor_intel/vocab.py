"""受控词表：公司名单与主题。

## 为什么键一律 ASCII

公司键与主题键都会作为命令行参数出现。PowerShell 默认用 GBK 传参，中文参数会**静默**
变成乱码（ADR 0007）——不是报错，是查出来空结果然后你以为库里没这条。所以键用 ASCII
slug，中文只做显示标签。

## 为什么公司分两处存

ADR 0002 §2 把名单分三层，分层依据是「要不要建独立档案」：

| 层 | 待遇 | 存在哪 | 改动成本 |
|---|---|---|---|
| **建档层** 8 家 | 每期必扫，各自档案 | 本文件（代码） | 须走决策 |
| **索引层** 8 家 | 打标签可检索，不建档 | 本文件（代码） | 须走决策 |
| **其他桶** | 只存不维护 | `data/intel/companies.json`（数据） | `intel add` 自动登记 |

前两层进代码是因为「名单变更要走决策而非随手加」（ADR 0002 后果节）。其他桶进数据是因为
不让它自动登记就会卡住入库——而入库被卡住的后果是这条情报根本不进库，比标签不够精确坏得多。

检索承诺也因此分层：前两层的标签是完整的（每期必扫或必标），其他桶只承诺「存了就能查到」。

## 主题为什么必须严格受控

ADR 0002 §2 的场景 2（季报定位研究）要按主题横切比较所有 peers。自由标签会让
「Booking 在分发上做了什么」和「Expedia 在流量入口上做了什么」变成两个查不到彼此的桶，
横切就失效了。所以未登记主题一律拒绝，宁可让人先加词表。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Tier = Literal["profiled", "indexed", "other"]

TIER_ZH: dict[str, str] = {
    "profiled": "建档层",
    "indexed": "索引层",
    "other": "其他桶",
}


@dataclass(frozen=True)
class Company:
    key: str
    zh: str
    tier: Tier
    #: 归一用的别名。写条目时给的是别名也能落到同一个键上。
    aliases: tuple[str, ...] = ()


#: 建档层 8 家（ADR 0002 §2）。飞猪与豆包·抖音不在 Appendix 覆盖内，
#: 但作为新出现的分发入口纳入建档层。
PROFILED: tuple[Company, ...] = (
    Company("ABNB", "Airbnb", "profiled", ("airbnb", "爱彼迎")),
    Company("BKNG", "Booking Holdings", "profiled",
            ("booking", "booking.com", "booking holdings", "缤客")),
    Company("EXPE", "Expedia Group", "profiled", ("expedia", "expedia group")),
    Company("TCOM", "Trip.com Group / 携程", "profiled",
            ("trip.com", "trip.com group", "携程", "ctrip")),
    Company("MEITUAN", "美团", "profiled", ("meituan", "美团旅行", "美团酒旅")),
    Company("TCEL", "同程旅行", "profiled", ("同程", "同程旅行", "tongcheng", "0780")),
    Company("FLIGGY", "飞猪", "profiled", ("飞猪", "阿里旅行")),
    Company("DOUBAO", "豆包·抖音", "profiled",
            ("豆包", "抖音", "douyin", "抖音生活服务", "字节", "bytedance", "字节跳动")),
)

#: 索引层 8 家（ADR 0002 §2，对齐 Q2 Appendix 实际覆盖）。
INDEXED: tuple[Company, ...] = (
    Company("MMYT", "MakeMyTrip", "indexed", ("makemytrip", "mmt")),
    Company("TRIP", "Tripadvisor", "indexed", ("tripadvisor", "猫途鹰", "viator")),
    Company("TUNIU", "途牛", "indexed", ("途牛", "tuniu")),
    Company("HTHT", "华住", "indexed", ("华住", "huazhu", "h world")),
    Company("ATAT", "亚朵", "indexed", ("亚朵", "atour")),
    Company("MAR", "万豪", "indexed", ("万豪", "marriott", "marriott bonvoy")),
    Company("HLT", "希尔顿", "indexed", ("希尔顿", "hilton")),
    Company("IHG", "洲际", "indexed", ("洲际", "intercontinental")),
)

#: ⚠️ **Ticker 词表写死，防歧义**（ADR 0002 §2）：
#: `TRIP` = Tripadvisor；`TCOM` = Trip.com / 携程。**禁止用 `Trip` 缩写任一方。**
#:
#: 比对**区分大小写**：全大写 `TRIP` 是 Tripadvisor 的正式键，合法；
#: 而 `Trip` / `trip` 这种当公司名写的形式两边都像，一律拒绝。
#: 这个区分不是吹毛求疵——不区分的话，自动打标出来的 `TRIP` 键会被自己的防歧义规则拒掉。
AMBIGUOUS: dict[str, str] = {
    "trip": "「Trip」既像 Tripadvisor 又像 Trip.com，禁止用它指代任何一方。"
            "Tripadvisor 写 TRIP（全大写），携程写 TCOM。",
}


@dataclass(frozen=True)
class Topic:
    key: str
    zh: str
    #: 词表初版给的举例范围，帮助打标时判断边界（ADR 0002 §7）。
    scope: str


#: 主题受控词表初版（ADR 0002 §7）。增删要显式改这里，不许 Agent 自由造词。
TOPICS: tuple[Topic, ...] = (
    Topic("distribution", "分发与流量入口", "AI 入口 / 内容平台 / 比价 / SEO-AEO"),
    Topic("supply", "供给与品类扩张", "体验 / 租车 / 机票 / 短租"),
    Topic("b2b", "B2B 与企业差旅", "企业差旅平台、协议价、B2B 分销"),
    Topic("loyalty", "忠诚度与会员", "会员体系、互认、联名卡"),
    Topic("unit-economics", "费率佣金与业主商户经济", "佣金费率、加盟费、业主与商户利润"),
    Topic("ai-stack", "AI 产品与技术底座", "AI 助手、agentic 预订、内部效率、技术平台"),
    Topic("ma-capital", "并购投资与资本配置", "收购、投资、回购、分拆"),
    Topic("org", "组织与人事", "高管任命、组织架构调整、裁员"),
    Topic("financials", "财务表现与指引", "季度业绩、指引、盈利路径"),
    Topic("policy-macro", "政策监管与宏观", "监管处罚、签证政策、宏观需求、地缘冲突"),
)

TOPIC_BY_KEY: dict[str, Topic] = {t.key: t for t in TOPICS}

#: 其他桶的**别名种子**。这些不是第四层——待遇仍是「只存不维护」（不建档、不承诺每期扫）。
#: 在代码里写下它们只为一件事：**让自动打标认得出来，且别名不飘。**
#:
#: 不种的后果实测过：四期精选 39 条里有 19 条一个公司标签都没有，因为主角是 Google、
#: Accor、TUI、GetYourGuide 这些不在前两层的公司。它们仍然进不了档案，但至少
#: 「查 Accor」和主题横切里能出现，而不是彻底查不到。
#:
#: 加一家进这里不需要走决策（它不改变覆盖承诺）；把一家从这里提到索引层要走决策。
OTHERS_SEED: tuple[Company, ...] = (
    Company("GOOGLE", "Google", "other", ("google", "谷歌", "alphabet")),
    Company("ACCOR", "Accor", "other", ("accor", "雅高")),
    Company("TUI", "TUI", "other", ("tui",)),
    Company("GETYOURGUIDE", "GetYourGuide", "other", ("getyourguide", "get your guide")),
    Company("WYNDHAM", "Wyndham", "other", ("wyndham", "温德姆")),
    Company("HYATT", "Hyatt", "other", ("hyatt", "凯悦")),
    Company("CARTRAWLER", "CarTrawler", "other", ("cartrawler",)),
    Company("AGODA", "Agoda", "other", ("agoda",)),
    Company("PRICELINE", "Priceline", "other", ("priceline",)),
    Company("AMEXGBT", "Amex GBT", "other", ("amex gbt", "gbt", "american express global business travel")),
    Company("CONCUR", "SAP Concur", "other", ("concur", "sap concur")),
    Company("ENGINE", "Engine", "other", ("engine",)),
    Company("LAYLA", "Layla", "other", ("layla",)),
    Company("TREEBO", "Treebo", "other", ("treebo",)),
    Company("ALLEGIANT", "Allegiant", "other", ("allegiant",)),
    Company("SOUTHWEST", "西南航空", "other", ("southwest", "西南航空")),
    Company("AAL", "美国航空", "other", ("american airlines", "美国航空")),
    Company("JAL", "日本航空", "other", ("japan airlines", "日航", "日本航空")),
    Company("AIRINDIA", "Air India", "other", ("air india",)),
    Company("INDIGO", "IndiGo", "other", ("indigo",)),
)

_CONTROLLED: tuple[Company, ...] = PROFILED + INDEXED
#: 前两层受控，其他桶种子也按键索引（tier 仍是 other）。
COMPANY_BY_KEY: dict[str, Company] = {c.key: c for c in (*_CONTROLLED, *OTHERS_SEED)}

PROFILED_KEYS: tuple[str, ...] = tuple(c.key for c in PROFILED)
INDEXED_KEYS: tuple[str, ...] = tuple(c.key for c in INDEXED)

#: 别名 → 键。全部小写比对。
_ALIAS: dict[str, str] = {}
for _c in (*_CONTROLLED, *OTHERS_SEED):
    _ALIAS[_c.key.lower()] = _c.key
    _ALIAS[_c.zh.lower()] = _c.key
    for _a in _c.aliases:
        _ALIAS[_a.lower()] = _c.key


class VocabError(ValueError):
    """词表拒绝。消息里必须写清「要继续该改哪儿」。"""


def resolve_company(name: str) -> str | None:
    """别名 → 已知键。完全不认识就返回 None（交给其他桶登记）。"""
    probe = (name or "").strip()
    if not probe:
        raise VocabError("公司名为空。")
    # 正式键（全大写）优先，且要在防歧义之前判——`TRIP` 是 Tripadvisor 的合法键，
    # 只有小写/混写的 `trip` 才是那个两边都像的写法。
    if probe in COMPANY_BY_KEY:
        return probe
    low = probe.lower()
    if low in AMBIGUOUS:
        raise VocabError(AMBIGUOUS[low])
    return _ALIAS.get(low)


def normalize_other(name: str) -> str:
    """其他桶的键：大写 + 空格连字符归一。

    目的只有一个——别让 `GetYourGuide` / `getyourguide` / `Get Your Guide` 变成三条。
    """
    probe = (name or "").strip()
    if not probe:
        raise VocabError("公司名为空。")
    key = probe.upper()
    for ch in " ·.":
        key = key.replace(ch, "-")
    while "--" in key:
        key = key.replace("--", "-")
    return key.strip("-")


def resolve_topic(name: str) -> str:
    """主题键校验。未登记一律拒绝，并把可选值摆出来。"""
    probe = (name or "").strip().lower()
    if probe in TOPIC_BY_KEY:
        return probe
    options = "、".join(f"{t.key}（{t.zh}）" for t in TOPICS)
    raise VocabError(
        f"主题 {name!r} 不在受控词表里。可选：{options}。\n"
        "确实需要新主题，要先改 modules/competitor_intel/vocab.py 的 TOPICS "
        "并在 ADR 0002 §7 记一笔——不许临场造词，否则跨公司横切就失效了。"
    )


def tier_of(key: str, registry: dict[str, str] | None = None) -> Tier:
    company = COMPANY_BY_KEY.get(key)
    if company:
        return company.tier
    if registry and key in registry:
        return "other"
    return "other"


def label(key: str, registry: dict[str, str] | None = None) -> str:
    """给人看的公司名。其他桶回落到登记时的原名。"""
    company = COMPANY_BY_KEY.get(key)
    if company:
        return company.zh
    if registry:
        return registry.get(key, key)
    return key
