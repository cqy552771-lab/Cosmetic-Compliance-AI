"""
tests/test_cache.py - 缓存模块单元测试
"""
import sys
import os
import tempfile
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch
from pathlib import Path

# 使用临时目录进行缓存测试
import cache as cache_module


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path):
    """每个测试使用独立的临时缓存目录"""
    tmp_cache_dir = tmp_path / "cache"
    tmp_cache_dir.mkdir()
    tmp_cache_file = tmp_cache_dir / "product_cache.json"
    tmp_db_file = tmp_path / "history.db"

    with patch.object(cache_module, "CACHE_DIR", tmp_cache_dir), \
         patch.object(cache_module, "CACHE_FILE", tmp_cache_file), \
         patch.object(cache_module, "DB_FILE", tmp_db_file):
        yield


class TestGenerateProductId:
    def test_basic(self):
        pid = cache_module.generate_product_id("欧莱雅", "小黑瓶精华")
        assert isinstance(pid, str)
        assert len(pid) == 12

    def test_deterministic(self):
        pid1 = cache_module.generate_product_id("Brand", "Product")
        pid2 = cache_module.generate_product_id("Brand", "Product")
        assert pid1 == pid2

    def test_different_products_different_ids(self):
        pid1 = cache_module.generate_product_id("Brand", "Product A")
        pid2 = cache_module.generate_product_id("Brand", "Product B")
        assert pid1 != pid2

    def test_strips_whitespace(self):
        pid1 = cache_module.generate_product_id("Brand", "Product")
        pid2 = cache_module.generate_product_id("  Brand  ", "  Product  ")
        assert pid1 == pid2

    def test_case_insensitive(self):
        pid1 = cache_module.generate_product_id("BRAND", "PRODUCT")
        pid2 = cache_module.generate_product_id("brand", "product")
        assert pid1 == pid2


class TestCacheOperations:
    def test_cache_miss_returns_none(self):
        result = cache_module.check_cache("nonexistent_id")
        assert result is None

    def test_cache_store_and_retrieve(self):
        pid = "test_product_001"
        data = {"brand": "Test", "product": "Cream", "safety_score": 9.0}
        cache_module.cache_result(pid, data)
        cached = cache_module.check_cache(pid)
        assert cached is not None
        assert cached["brand"] == "Test"
        assert cached["safety_score"] == 9.0

    def test_clear_specific_cache(self):
        pid = "test_product_002"
        data = {"brand": "Test"}
        cache_module.cache_result(pid, data)
        removed = cache_module.clear_cache(pid)
        assert removed == 1
        assert cache_module.check_cache(pid) is None

    def test_clear_all_cache(self):
        cache_module.cache_result("pid_001", {"data": 1})
        cache_module.cache_result("pid_002", {"data": 2})
        removed = cache_module.clear_cache()
        assert removed == 2

    def test_clear_nonexistent_returns_zero(self):
        removed = cache_module.clear_cache("does_not_exist")
        assert removed == 0


class TestCacheStats:
    def test_empty_stats(self):
        stats = cache_module.get_cache_stats()
        assert stats["total_entries"] == 0
        assert stats["valid_entries"] == 0
        assert stats["expired_entries"] == 0

    def test_stats_after_adding(self):
        cache_module.cache_result("test_001", {"brand": "A"})
        cache_module.cache_result("test_002", {"brand": "B"})
        stats = cache_module.get_cache_stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2

    def test_stats_expiry_hours(self):
        stats = cache_module.get_cache_stats()
        assert stats["cache_expiry_hours"] == cache_module.CACHE_EXPIRY_HOURS


class TestQueryHistory:
    def test_save_and_retrieve_history(self):
        cache_module.save_query_history(
            "pid_001", "Brand", "Product", "web_scraper", {"score": 8}
        )
        history = cache_module.get_query_history(limit=10)
        assert len(history) >= 1
        assert history[0]["brand"] == "Brand"
        assert history[0]["product"] == "Product"

    def test_history_limit(self):
        for i in range(15):
            cache_module.save_query_history(
                f"pid_{i:03d}", f"Brand{i}", f"Product{i}", "test", {}
            )
        history = cache_module.get_query_history(limit=5)
        assert len(history) == 5

    def test_history_order_latest_first(self):
        cache_module.save_query_history("pid_a", "BrandA", "ProductA", "test", {})
        cache_module.save_query_history("pid_b", "BrandB", "ProductB", "test", {})
        history = cache_module.get_query_history(limit=10)
        assert history[0]["brand"] == "BrandB"  # 最新的在前
