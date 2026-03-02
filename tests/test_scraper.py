"""
tests/test_scraper.py - 爬虫模块单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from scraper import (
    web_scraper, parse_ingredient_text,
    validate_ingredients, _normalize_key, MOCK_PRODUCTS
)


class TestNormalizeKey:
    def test_basic(self):
        key = _normalize_key("欧莱雅", "小黑瓶精华")
        assert key == "欧莱雅_小黑瓶精华"

    def test_strip_spaces(self):
        key = _normalize_key("  Brand  ", "  Product  ")
        assert "  " not in key

    def test_lowercase(self):
        key = _normalize_key("L'Oreal", "Revitalift")
        assert key == key.lower()


class TestWebScraper:
    def test_known_product_returns_list(self):
        ingredients = web_scraper("欧莱雅", "小黑瓶精华")
        assert isinstance(ingredients, list)
        assert len(ingredients) > 0

    def test_known_product_contains_water(self):
        ingredients = web_scraper("欧莱雅", "小黑瓶精华")
        assert "Water" in ingredients

    def test_unknown_product_returns_default(self):
        ingredients = web_scraper("UnknownBrand999", "UnknownProduct999")
        assert isinstance(ingredients, list)
        assert len(ingredients) >= 1
        # 应该返回默认成分
        assert ingredients == MOCK_PRODUCTS["default"]

    def test_demo_product_loreal(self):
        ingredients = web_scraper("loreal", "revitalift")
        assert len(ingredients) > 3

    def test_returns_list_of_strings(self):
        ingredients = web_scraper("完美日记", "粉底液")
        assert all(isinstance(i, str) for i in ingredients)


class TestParseIngredientText:
    def test_comma_separated(self):
        text = "Water, Glycerin, Niacinamide"
        result = parse_ingredient_text(text)
        assert result == ["Water", "Glycerin", "Niacinamide"]

    def test_newline_separated(self):
        text = "Water\nGlycerin\nNiacinamide"
        result = parse_ingredient_text(text)
        assert result == ["Water", "Glycerin", "Niacinamide"]

    def test_mixed_separators(self):
        text = "Water, Glycerin\nNiacinamide; Phenoxyethanol"
        result = parse_ingredient_text(text)
        assert "Water" in result
        assert "Glycerin" in result
        assert "Niacinamide" in result

    def test_strips_whitespace(self):
        text = "  Water  ,  Glycerin  "
        result = parse_ingredient_text(text)
        assert "Water" in result
        assert "Glycerin" in result

    def test_strips_bullet_points(self):
        text = "• Water\n• Glycerin\n· Niacinamide"
        result = parse_ingredient_text(text)
        assert "Water" in result
        assert "Glycerin" in result

    def test_empty_string(self):
        result = parse_ingredient_text("")
        assert result == []

    def test_real_world_ingredient_list(self):
        text = """Water, Glycerin, Dimethicone, Niacinamide,
Sodium Hyaluronate, Adenosine, Tocopherol,
Carbomer, Phenoxyethanol, Fragrance"""
        result = parse_ingredient_text(text)
        assert len(result) == 10
        assert "Niacinamide" in result


class TestValidateIngredients:
    def test_valid_list(self):
        result = validate_ingredients(["Water", "Glycerin", "Niacinamide"])
        assert result["valid"] is True

    def test_empty_list(self):
        result = validate_ingredients([])
        assert result["valid"] is False

    def test_single_ingredient(self):
        result = validate_ingredients(["Water"])
        assert result["valid"] is False

    def test_large_list(self):
        big_list = [f"Ingredient_{i}" for i in range(120)]
        result = validate_ingredients(big_list)
        assert result["valid"] is True
        assert "120" in result["message"]
