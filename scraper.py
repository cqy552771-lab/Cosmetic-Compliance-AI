"""
scraper.py - 网络爬虫模块
Cosmetic Compliance AI

从公开数据源（如 INCIDecoder、CosDNA、INCI 标准网站等）爬取化妆品成分信息。
支持降级策略：爬虫失败时，返回模拟数据或提示用户手动输入成分。
"""

import re
import time
import logging
import requests
from typing import Optional
from urllib.parse import quote_plus

# ─────────────────────────────────────────────
# 日志配置
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 请求头（模拟真实浏览器）
# ─────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REQUEST_TIMEOUT = 10  # 秒
MAX_RETRIES = 2

# ─────────────────────────────────────────────
# 模拟数据库（开发 / 测试 / 降级使用）
# ─────────────────────────────────────────────
MOCK_PRODUCTS: dict[str, list[str]] = {
    "loreal_revitalift": [
        "Water", "Glycerin", "Dimethicone", "Niacinamide",
        "Sodium Hyaluronate", "Adenosine", "Tocopherol",
        "Carbomer", "Phenoxyethanol", "Fragrance"
    ],
    "olay_regenerist": [
        "Water", "Glycerin", "Niacinamide", "Dimethicone",
        "Sodium Hyaluronate", "Vitamin C", "Retinol",
        "Tocopherol", "Phenoxyethanol", "Methylparaben"
    ],
    "skii_facial_treatment_essence": [
        "Galactomyces Ferment Filtrate", "Water", "Butylene Glycol",
        "Niacinamide", "Sodium Benzoate", "Methylparaben",
        "Sorbic Acid"
    ],
    "la_mer_crème_de_la_mer": [
        "Water", "Seaweed Extract", "Mineral Oil", "Petrolatum",
        "Glycerin", "Isohexadecane", "Beeswax",
        "Tocopherol", "Fragrance", "Phenoxyethanol"
    ],
    "neutrogena_hydro_boost": [
        "Water", "Dimethicone", "Glycerin", "Dimethicone_Crosspolymer",
        "Sodium Hyaluronate", "Phenoxyethanol",
        "Methylparaben", "Carbomer"
    ],
    "欧莱雅_小黑瓶精华": [
        "Water", "Bifida Ferment Lysate", "Glycerin",
        "Alcohol Denat.", "Adenosine", "Niacinamide",
        "Sodium Hyaluronate", "Tocopherol",
        "Phenoxyethanol", "Carbomer"
    ],
    "雅诗兰黛_小棕瓶": [
        "Water", "Bifida Ferment Lysate", "Glycerin",
        "Sodium Hyaluronate", "Adenosine", "Tocopherol",
        "Centella Asiatica Extract", "Niacinamide",
        "Phenoxyethanol", "Fragrance"
    ],
    "完美日记_粉底液": [
        "Water", "Cyclopentasiloxane", "Titanium Dioxide",
        "Dimethicone", "Glycerin", "Niacinamide",
        "Sodium Benzoate", "Methylparaben", "Fragrance"
    ],
    "珀莱雅_双抗精华": [
        "Water", "Niacinamide", "Vitamin C",
        "Sodium Hyaluronate", "Adenosine",
        "Centella Asiatica Extract", "Tocopherol",
        "Carbomer", "Phenoxyethanol"
    ],
    "薇诺娜_舒缓保湿霜": [
        "Water", "Glycerin", "Ceramide NP",
        "Sodium Hyaluronate", "Centella Asiatica Extract",
        "Dimethicone", "Carbomer", "Phenoxyethanol"
    ],
    "default": [
        "Water", "Glycerin", "Sodium Hyaluronate",
        "Niacinamide", "Dimethicone", "Tocopherol",
        "Carbomer", "Phenoxyethanol"
    ]
}


# ─────────────────────────────────────────────
# 核心爬虫逻辑
# ─────────────────────────────────────────────

def _normalize_key(brand: str, product: str) -> str:
    """将品牌+产品名标准化为字典键"""
    combined = f"{brand.strip()}_{product.strip()}"
    return combined.lower().replace(" ", "_")


def _fetch_from_incidecoder(brand: str, product: str) -> Optional[list[str]]:
    """
    尝试从 INCIDecoder 获取产品成分列表
    （INCIDecoder 不提供官方 API，此处为示范性实现）
    """
    try:
        query = f"{brand} {product}"
        url = f"https://incidecoder.com/search?q={quote_plus(query)}"
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        # 简单文本解析（实际需要 BeautifulSoup 深度解析）
        # 此处仅检测页面是否可访问，成分解析作为扩展
        if response.status_code == 200 and "ingredients" in response.text.lower():
            logger.info(f"[INCIDecoder] 成功获取页面，但需进一步解析成分")
            # 真实解析需要 BeautifulSoup；此处返回 None 触发降级
            return None
    except requests.RequestException as e:
        logger.warning(f"[INCIDecoder] 请求失败: {e}")
    return None


def _fetch_from_cosdna(brand: str, product: str) -> Optional[list[str]]:
    """
    尝试从 CosDNA 获取产品成分
    （模拟接口，实际使用需遵守网站 robots.txt）
    """
    try:
        query = f"{brand} {product}"
        url = f"https://www.cosdna.com/chi/cosmetic_search.php?q={quote_plus(query)}"
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        if response.status_code == 200:
            logger.info(f"[CosDNA] 页面请求成功，成分解析需进一步开发")
            return None
    except requests.RequestException as e:
        logger.warning(f"[CosDNA] 请求失败: {e}")
    return None


def web_scraper(brand: str, product: str) -> list[str]:
    """
    核心爬虫函数：按优先级尝试多个数据源，最终降级至模拟数据

    数据源优先级：
      1. INCIDecoder
      2. CosDNA
      3. 本地模拟数据库（降级）

    Args:
        brand:   品牌名称（中英文均可）
        product: 产品名称
    Returns:
        成分名称列表（INCI 格式）
    """
    logger.info(f"[Scraper] 开始爬取: {brand} - {product}")

    # 策略 1: INCIDecoder
    ingredients = _fetch_from_incidecoder(brand, product)
    if ingredients:
        logger.info("[Scraper] 来源: INCIDecoder")
        return ingredients

    time.sleep(0.5)  # 礼貌延迟

    # 策略 2: CosDNA
    ingredients = _fetch_from_cosdna(brand, product)
    if ingredients:
        logger.info("[Scraper] 来源: CosDNA")
        return ingredients

    # 策略 3: 本地模拟数据库（降级）
    key = _normalize_key(brand, product)
    ingredients = MOCK_PRODUCTS.get(key)
    if ingredients:
        logger.info(f"[Scraper] 来源: 本地模拟数据库 (key={key})")
        return ingredients

    # 最终降级：返回通用默认成分
    logger.warning(f"[Scraper] 未找到匹配数据，返回默认成分列表")
    return MOCK_PRODUCTS["default"]


def parse_ingredient_text(raw_text: str) -> list[str]:
    """
    解析用户手动输入的成分文本，拆分为列表

    支持格式：
      - 逗号分隔: "Water, Glycerin, Niacinamide"
      - 换行分隔: "Water\nGlycerin\nNiacinamide"
      - 混合格式

    Args:
        raw_text: 原始成分字符串
    Returns:
        清洗后的成分名称列表
    """
    # 按逗号或换行分割
    parts = re.split(r"[,\n;]+", raw_text)
    ingredients = []
    for part in parts:
        clean = part.strip().strip("·•-*").strip()
        if clean and len(clean) > 1:
            ingredients.append(clean)
    return ingredients


def validate_ingredients(ingredients: list[str]) -> dict:
    """
    基础成分列表验证

    Args:
        ingredients: 成分列表
    Returns:
        验证结果字典
    """
    if not ingredients:
        return {"valid": False, "message": "成分列表为空"}
    if len(ingredients) < 2:
        return {"valid": False, "message": "成分数量异常（少于2项）"}
    if len(ingredients) > 100:
        return {"valid": True, "message": f"成分数量较多（{len(ingredients)}项），可能包含重复"}
    return {"valid": True, "message": f"成功解析 {len(ingredients)} 种成分"}
