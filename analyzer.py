"""
analyzer.py - AI 成分分析与合规性评估模块
Cosmetic Compliance AI

基于本地知识库（FDA / GB 2760）和成分安全性数据库，对化妆品成分进行
安全评分、合规性检查，并生成专业分析报告。
支持可选接入 OpenAI LLM 进行深度分析。
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────
# 日志
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 数据路径
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

INGREDIENTS_DB_PATH = DATA_DIR / "ingredients_db.json"
FDA_RESTRICTED_PATH = DATA_DIR / "fda_restricted.json"
GB_RESTRICTED_PATH  = DATA_DIR / "gb_restricted.json"


# ─────────────────────────────────────────────
# 数据类
# ─────────────────────────────────────────────

@dataclass
class IngredientAnalysis:
    """单个成分的分析结果"""
    inci_name: str
    cn_name: str = ""
    function: list[str] = field(default_factory=list)
    safety_score: int = 5          # 1-10，越高越安全
    safety_level: str = "unknown"  # safe / caution / moderate_concern / concern / prohibited
    ewg_score: int = 0             # EWG评分 1-10，越低越安全
    description: str = ""
    concerns: list[str] = field(default_factory=list)
    fda_status: str = "not_listed"  # not_listed / restricted / prohibited
    gb_status: str = "not_listed"
    suitable_skin: list[str] = field(default_factory=list)
    is_flagged: bool = False


@dataclass
class ComplianceReport:
    """完整合规性报告"""
    brand: str
    product_name: str
    total_ingredients: int
    overall_safety_score: float = 5.0      # 综合安全评分 0-10
    overall_safety_level: str = "unknown"  # safe / caution / concern / prohibited
    fda_compliance: str = "compliant"      # compliant / restricted / prohibited
    gb_compliance: str = "compliant"
    ingredient_analyses: list[IngredientAnalysis] = field(default_factory=list)
    flagged_ingredients: list[IngredientAnalysis] = field(default_factory=list)
    safe_highlights: list[str] = field(default_factory=list)  # 优质成分亮点
    recommendations: list[str] = field(default_factory=list)
    skin_suitability: dict = field(default_factory=dict)      # 各肤质适用性
    summary: str = ""


# ─────────────────────────────────────────────
# 数据库加载
# ─────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    """安全加载 JSON 文件"""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"加载文件失败 {path}: {e}")
    return {}


class KnowledgeBase:
    """知识库单例，缓存所有数据库内容"""
    _instance: Optional["KnowledgeBase"] = None

    def __init__(self):
        raw_db = _load_json(INGREDIENTS_DB_PATH)
        self.ingredients: dict[str, dict] = {
            item["inci_name"].lower(): item
            for item in raw_db.get("ingredients", [])
        }
        raw_fda = _load_json(FDA_RESTRICTED_PATH)
        self.fda_restricted: list[dict] = raw_fda.get("restricted_ingredients", [])

        raw_gb = _load_json(GB_RESTRICTED_PATH)
        self.gb_restricted: list[dict] = raw_gb.get("restricted_ingredients", [])

        logger.info(f"[KnowledgeBase] 成分库: {len(self.ingredients)} 条, "
                    f"FDA限制: {len(self.fda_restricted)} 条, "
                    f"GB限制: {len(self.gb_restricted)} 条")

    @classmethod
    def get(cls) -> "KnowledgeBase":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# ─────────────────────────────────────────────
# 核心分析逻辑
# ─────────────────────────────────────────────

def _check_fda_status(inci_name: str, kb: KnowledgeBase) -> str:
    """检查成分的 FDA 合规状态"""
    name_lower = inci_name.lower()
    for item in kb.fda_restricted:
        item_inci = item.get("inci", "").lower()
        item_name = item.get("name", "").lower()
        if name_lower in item_inci or name_lower in item_name or \
           item_inci in name_lower or item_name in name_lower:
            return item.get("status", "restricted")
    return "not_listed"


def _check_gb_status(inci_name: str, kb: KnowledgeBase) -> str:
    """检查成分的 GB 2760 / 中国法规合规状态"""
    name_lower = inci_name.lower()
    for item in kb.gb_restricted:
        en_name = item.get("name_en", "").lower()
        cn_name = item.get("name", "").lower()
        if name_lower in en_name or name_lower in cn_name or \
           en_name in name_lower:
            return item.get("status", "restricted")
    return "not_listed"


def analyze_single_ingredient(inci_name: str, kb: KnowledgeBase) -> IngredientAnalysis:
    """
    分析单个成分

    Args:
        inci_name: INCI成分名称
        kb: 知识库实例
    Returns:
        IngredientAnalysis 对象
    """
    result = IngredientAnalysis(inci_name=inci_name)

    # 从本地知识库查找
    db_entry = kb.ingredients.get(inci_name.lower())
    if db_entry:
        result.cn_name       = db_entry.get("cn_name", "")
        result.function      = db_entry.get("function", [])
        result.safety_score  = db_entry.get("safety_score", 5)
        result.safety_level  = db_entry.get("safety_level", "unknown")
        result.ewg_score     = db_entry.get("ewg_score", 0)
        result.description   = db_entry.get("description", "")
        result.concerns      = db_entry.get("concerns", [])
        result.suitable_skin = db_entry.get("suitable_skin", [])
    else:
        # 未知成分使用默认评分
        result.safety_score  = 5
        result.safety_level  = "unknown"
        result.description   = "本地数据库中未收录该成分，建议进一步查询。"

    # 合规检查
    result.fda_status = _check_fda_status(inci_name, kb)
    result.gb_status  = _check_gb_status(inci_name, kb)

    # 标记风险成分
    if (result.fda_status in ("prohibited", "restricted") or
        result.gb_status in ("prohibited", "restricted") or
        result.safety_level in ("concern", "moderate_concern") or
        result.safety_score <= 4):
        result.is_flagged = True

    return result


SKIN_TYPES = ["all", "dry", "oily", "combination", "sensitive", "acne-prone", "aging"]

def _compute_skin_suitability(analyses: list[IngredientAnalysis]) -> dict:
    """根据成分分析结果计算各肤质的适用性评分"""
    skin_scores: dict[str, list[float]] = {s: [] for s in SKIN_TYPES}

    for analysis in analyses:
        suitable = analysis.suitable_skin
        if "all" in suitable:
            for s in SKIN_TYPES:
                skin_scores[s].append(analysis.safety_score)
        else:
            for s in suitable:
                if s in skin_scores:
                    skin_scores[s].append(analysis.safety_score)
            # 不在适用范围的肤质略微扣分
            for s in SKIN_TYPES:
                if s not in suitable and "all" not in suitable:
                    if skin_scores[s]:
                        skin_scores[s].append(max(1, analysis.safety_score - 2))

    result = {}
    label_map = {
        "all": "通用",
        "dry": "干性肌",
        "oily": "油性肌",
        "combination": "混合肌",
        "sensitive": "敏感肌",
        "acne-prone": "痘痘肌",
        "aging": "抗衰/熟龄肌"
    }
    for s, scores in skin_scores.items():
        avg = round(sum(scores) / len(scores), 1) if scores else 5.0
        level = "适合" if avg >= 7 else ("一般" if avg >= 5 else "谨慎")
        result[label_map[s]] = {"score": avg, "label": level}

    return result


def _generate_recommendations(report: ComplianceReport) -> list[str]:
    """根据报告生成个性化建议"""
    recs = []
    flagged_names = [a.inci_name for a in report.flagged_ingredients]

    if report.overall_safety_score >= 8:
        recs.append("✅ 该产品成分整体安全评分优秀，适合日常使用。")
    elif report.overall_safety_score >= 6:
        recs.append("⚠️ 该产品有少量需关注成分，建议敏感肌用户先做贴肤测试。")
    else:
        recs.append("🚨 该产品存在多个高风险成分，建议谨慎选购，参考专业皮肤科建议。")

    # 合规警告
    if report.fda_compliance == "prohibited":
        recs.append("🚫 该产品含有 FDA 明确禁用成分，在美国市场销售可能违规。")
    elif report.fda_compliance == "restricted":
        recs.append("⚠️ 该产品含有 FDA 限制性成分，请确认使用浓度符合法规要求。")

    if report.gb_compliance == "prohibited":
        recs.append("🚫 该产品含有中国法规（化妆品安全技术规范）明确禁用成分。")
    elif report.gb_compliance == "restricted":
        recs.append("⚠️ 该产品含有中国限制性成分，请核查使用浓度合规性。")

    # 成分特定建议
    if "Alcohol Denat." in flagged_names or "Alcohol" in flagged_names:
        recs.append("💧 含有酒精成分，干性皮肤或皮肤屏障受损者请谨慎使用。")
    if any("paraben" in n.lower() for n in flagged_names):
        recs.append("🧪 含有尼泊金酯类防腐剂，有内分泌干扰嫌疑，孕妇及婴幼儿建议回避。")
    if any("fragrance" in n.lower() or "parfum" in n.lower() for n in flagged_names):
        recs.append("🌸 含有香精成分，敏感皮肤或香精过敏人群请避免使用。")
    if "Retinol" in flagged_names:
        recs.append("🤰 含有视黄醇（Retinol），孕妇请避免使用，建议晚间使用并配合防晒。")
    if "Salicylic Acid" in flagged_names:
        recs.append("☀️ 含有水杨酸，有光敏感性，白天使用后务必做好防晒措施。")
    if "Sodium Benzoate" in flagged_names:
        recs.append("⚗️ 含有苯甲酸钠防腐剂，若同时含有维C，高温下存在苯的生成风险。")

    return recs


HIGHLIGHT_INGREDIENTS = {
    "Niacinamide", "Sodium Hyaluronate", "Hyaluronic Acid",
    "Retinol", "Vitamin C", "Adenosine", "Centella Asiatica Extract",
    "Bifida Ferment Lysate", "Tocopherol", "Zinc Oxide", "Titanium Dioxide",
    "Salicylic Acid"
}


def analyze_product(
    brand: str,
    product_name: str,
    ingredients: list[str]
) -> ComplianceReport:
    """
    对化妆品进行完整合规性分析

    Args:
        brand:         品牌名称
        product_name:  产品名称
        ingredients:   INCI成分名称列表
    Returns:
        ComplianceReport 完整分析报告
    """
    kb = KnowledgeBase.get()
    report = ComplianceReport(
        brand=brand,
        product_name=product_name,
        total_ingredients=len(ingredients)
    )

    analyses: list[IngredientAnalysis] = []
    for ing in ingredients:
        analysis = analyze_single_ingredient(ing.strip(), kb)
        analyses.append(analysis)

    report.ingredient_analyses = analyses

    # 标记风险成分
    report.flagged_ingredients = [a for a in analyses if a.is_flagged]

    # 亮点成分
    report.safe_highlights = [
        a.inci_name for a in analyses
        if a.inci_name in HIGHLIGHT_INGREDIENTS and not a.is_flagged
    ]

    # 综合安全评分（加权平均，前5位成分权重更高）
    scores = [a.safety_score for a in analyses if a.safety_score > 0]
    if scores:
        weighted = scores[:5] * 2 + scores[5:]  # 前5个成分双倍权重
        report.overall_safety_score = round(sum(weighted) / len(weighted), 2)
    else:
        report.overall_safety_score = 5.0

    # 综合安全等级
    if report.overall_safety_score >= 8:
        report.overall_safety_level = "safe"
    elif report.overall_safety_score >= 6:
        report.overall_safety_level = "caution"
    elif report.overall_safety_score >= 4:
        report.overall_safety_level = "moderate_concern"
    else:
        report.overall_safety_level = "concern"

    # 合规性汇总
    fda_statuses = [a.fda_status for a in analyses]
    gb_statuses  = [a.gb_status for a in analyses]

    if "prohibited" in fda_statuses:
        report.fda_compliance = "prohibited"
    elif "restricted" in fda_statuses:
        report.fda_compliance = "restricted"
    else:
        report.fda_compliance = "compliant"

    if "prohibited" in gb_statuses:
        report.gb_compliance = "prohibited"
    elif "restricted" in gb_statuses:
        report.gb_compliance = "restricted"
    else:
        report.gb_compliance = "compliant"

    # 肤质适用性
    report.skin_suitability = _compute_skin_suitability(analyses)

    # 建议
    report.recommendations = _generate_recommendations(report)

    # 摘要文字
    flag_count = len(report.flagged_ingredients)
    total = report.total_ingredients
    score = report.overall_safety_score
    report.summary = (
        f"{brand} · {product_name} 共检测到 {total} 种成分，"
        f"综合安全评分 {score}/10，"
        f"其中 {flag_count} 种成分需关注。"
        f"FDA合规状态：{report.fda_compliance}，"
        f"中国法规合规状态：{report.gb_compliance}。"
    )

    return report


def report_to_dict(report: ComplianceReport) -> dict:
    """将 ComplianceReport 转换为可序列化的字典（用于缓存/显示）"""
    def analysis_to_dict(a: IngredientAnalysis) -> dict:
        return {
            "inci_name": a.inci_name,
            "cn_name": a.cn_name,
            "function": a.function,
            "safety_score": a.safety_score,
            "safety_level": a.safety_level,
            "ewg_score": a.ewg_score,
            "description": a.description,
            "concerns": a.concerns,
            "fda_status": a.fda_status,
            "gb_status": a.gb_status,
            "suitable_skin": a.suitable_skin,
            "is_flagged": a.is_flagged,
        }

    return {
        "brand": report.brand,
        "product_name": report.product_name,
        "total_ingredients": report.total_ingredients,
        "overall_safety_score": report.overall_safety_score,
        "overall_safety_level": report.overall_safety_level,
        "fda_compliance": report.fda_compliance,
        "gb_compliance": report.gb_compliance,
        "ingredient_analyses": [analysis_to_dict(a) for a in report.ingredient_analyses],
        "flagged_ingredients": [analysis_to_dict(a) for a in report.flagged_ingredients],
        "safe_highlights": report.safe_highlights,
        "recommendations": report.recommendations,
        "skin_suitability": report.skin_suitability,
        "summary": report.summary,
    }
