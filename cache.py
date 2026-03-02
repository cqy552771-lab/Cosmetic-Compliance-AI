"""
cache.py - 缓存管理模块
Cosmetic Compliance AI

负责产品信息的本地缓存存储与读取，使用 JSON 文件持久化缓存，SQLite 用于历史查询记录。
"""

import json
import os
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_FILE = CACHE_DIR / "product_cache.json"
DB_FILE = DATA_DIR / "history.db"

CACHE_EXPIRY_HOURS = 24  # 缓存有效期（小时）

# 确保目录存在
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# JSON 文件缓存
# ─────────────────────────────────────────────

def _load_cache() -> dict:
    """加载 JSON 缓存文件"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    """保存 JSON 缓存文件"""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def generate_product_id(brand: str, product: str) -> str:
    """
    根据品牌和产品名生成唯一标识符（MD5哈希）
    
    Args:
        brand: 品牌名称
        product: 产品名称
    Returns:
        产品唯一ID（字符串）
    """
    raw = f"{brand.strip().lower()}_{product.strip().lower()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def check_cache(product_id: str) -> dict | None:
    """
    检查本地缓存中是否有对应产品的有效数据

    Args:
        product_id: 产品唯一标识符
    Returns:
        缓存的产品数据字典，若不存在或已过期则返回 None
    """
    cache = _load_cache()
    entry = cache.get(product_id)
    if not entry:
        return None

    # 检查缓存是否过期
    try:
        cached_time = datetime.fromisoformat(entry.get("cached_at", ""))
        if datetime.now() - cached_time > timedelta(hours=CACHE_EXPIRY_HOURS):
            # 过期，删除条目
            del cache[product_id]
            _save_cache(cache)
            return None
    except ValueError:
        return None

    return entry.get("data")


def cache_result(product_id: str, data: dict) -> None:
    """
    将产品分析结果写入本地缓存

    Args:
        product_id: 产品唯一标识符
        data: 需要缓存的结果字典
    """
    cache = _load_cache()
    cache[product_id] = {
        "cached_at": datetime.now().isoformat(),
        "data": data
    }
    _save_cache(cache)


def clear_cache(product_id: str | None = None) -> int:
    """
    清除缓存

    Args:
        product_id: 若指定则只清除该产品缓存；否则清除全部
    Returns:
        清除的条目数量
    """
    cache = _load_cache()
    if product_id:
        if product_id in cache:
            del cache[product_id]
            _save_cache(cache)
            return 1
        return 0
    else:
        count = len(cache)
        _save_cache({})
        return count


def get_cache_stats() -> dict:
    """
    获取缓存状态统计信息

    Returns:
        包含缓存数量、大小等信息的字典
    """
    cache = _load_cache()
    size_bytes = CACHE_FILE.stat().st_size if CACHE_FILE.exists() else 0
    valid_count = 0
    expired_count = 0

    for entry in cache.values():
        try:
            cached_time = datetime.fromisoformat(entry.get("cached_at", ""))
            if datetime.now() - cached_time <= timedelta(hours=CACHE_EXPIRY_HOURS):
                valid_count += 1
            else:
                expired_count += 1
        except ValueError:
            expired_count += 1

    return {
        "total_entries": len(cache),
        "valid_entries": valid_count,
        "expired_entries": expired_count,
        "cache_size_kb": round(size_bytes / 1024, 2),
        "cache_expiry_hours": CACHE_EXPIRY_HOURS,
    }


# ─────────────────────────────────────────────
# SQLite 查询历史记录
# ─────────────────────────────────────────────

def _init_db() -> None:
    """初始化 SQLite 数据库表结构"""
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  TEXT NOT NULL,
            brand       TEXT,
            product     TEXT,
            queried_at  TEXT NOT NULL,
            source      TEXT,
            result_json TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_query_history(product_id: str, brand: str, product: str,
                       source: str, result: dict) -> None:
    """
    将一次查询记录写入 SQLite 历史库

    Args:
        product_id: 产品唯一ID
        brand: 品牌
        product: 产品名
        source: 数据来源（web_scraper / cache / manual）
        result: 完整分析结果字典
    """
    _init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO query_history (product_id, brand, product, queried_at, source, result_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        product_id,
        brand,
        product,
        datetime.now().isoformat(),
        source,
        json.dumps(result, ensure_ascii=False)
    ))
    conn.commit()
    conn.close()


def get_query_history(limit: int = 20) -> list[dict]:
    """
    获取最近的查询历史

    Args:
        limit: 返回条目上限
    Returns:
        历史查询记录列表
    """
    _init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT brand, product, queried_at, source
        FROM query_history
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"brand": r[0], "product": r[1], "queried_at": r[2], "source": r[3]}
        for r in rows
    ]
