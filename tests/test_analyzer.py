"""
tests/test_analyzer.py - 分析模块单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from analyzer import (
    analyze_product, report_to_dict,
    analyze_single_ingredient, KnowledgeBase
)


@pytest.fixture
def kb():
    return KnowledgeBase.get()


@pytest.fixture
def sample_ingredients():
    return [
        "Water", "Glycerin", "Niacinamide",
        "Sodium Hyaluronate", "Phenoxyethanol",
        "Methylparaben", "Fragrance"
    ]


class TestAnalyzeSingleIngredient:
    def test_known_safe_ingredient(self, kb):
        result = analyze_single_ingredient("Water", kb)
        assert result.inci_name == "Water"
        assert result.safety_score >= 8
        assert result.safety_level == "safe"
        assert not result.is_flagged

    def test_known_concern_ingredient(self, kb):
        result = analyze_single_ingredient("Fragrance", kb)
        assert result.inci_name == "Fragrance"
        assert result.safety_level in ("moderate_concern", "concern", "caution")
        assert result.is_flagged

    def test_unknown_ingredient(self, kb):
        result = analyze_single_ingredient("XYZ_Unknown_Ingredient_9999", kb)
        assert result.safety_level == "unknown"
        assert result.safety_score == 5

    def test_paraben_flagged(self, kb):
        result = analyze_single_ingredient("Methylparaben", kb)
        assert result.is_flagged

    def test_safe_ingredient_not_flagged(self, kb):
        result = analyze_single_ingredient("Glycerin", kb)
        assert not result.is_flagged


class TestAnalyzeProduct:
    def test_basic_report_structure(self, sample_ingredients):
        report = analyze_product("Test Brand", "Test Product", sample_ingredients)
        assert report.brand == "Test Brand"
        assert report.product_name == "Test Product"
        assert report.total_ingredients == len(sample_ingredients)
        assert 0 <= report.overall_safety_score <= 10
        assert report.overall_safety_level in (
            "safe", "caution", "moderate_concern", "concern"
        )

    def test_flagged_ingredients_detected(self, sample_ingredients):
        report = analyze_product("Test Brand", "Test Product", sample_ingredients)
        flagged_names = [a.inci_name for a in report.flagged_ingredients]
        # Fragrance 和 Methylparaben 应该被标记
        assert "Fragrance" in flagged_names or "Methylparaben" in flagged_names

    def test_safe_product_high_score(self):
        safe_ingredients = [
            "Water", "Glycerin", "Sodium Hyaluronate",
            "Tocopherol", "Adenosine", "Centella Asiatica Extract"
        ]
        report = analyze_product("Safe Brand", "Safe Product", safe_ingredients)
        assert report.overall_safety_score >= 7.0
        assert len(report.flagged_ingredients) == 0

    def test_compliance_check(self):
        # 含有苯甲酸钠（与维C组合有风险）
        ingredients = ["Water", "Sodium Benzoate", "Vitamin C"]
        report = analyze_product("Brand", "Product", ingredients)
        assert report.fda_compliance in ("compliant", "restricted", "prohibited")
        assert report.gb_compliance in ("compliant", "restricted", "prohibited")

    def test_recommendations_generated(self, sample_ingredients):
        report = analyze_product("Test Brand", "Test Product", sample_ingredients)
        assert len(report.recommendations) > 0

    def test_skin_suitability_all_types(self, sample_ingredients):
        report = analyze_product("Test Brand", "Test Product", sample_ingredients)
        assert len(report.skin_suitability) == 7  # 7种肤质
        for skin, data in report.skin_suitability.items():
            assert "score" in data
            assert "label" in data

    def test_report_to_dict(self, sample_ingredients):
        report = analyze_product("Test Brand", "Test Product", sample_ingredients)
        d = report_to_dict(report)
        assert isinstance(d, dict)
        assert "brand" in d
        assert "ingredient_analyses" in d
        assert "flagged_ingredients" in d
        assert "overall_safety_score" in d

    def test_empty_ingredients(self):
        report = analyze_product("Brand", "Product", [])
        assert report.total_ingredients == 0
        assert report.overall_safety_score == 5.0


class TestEdgeCases:
    def test_ingredient_with_special_chars(self, kb):
        result = analyze_single_ingredient("Bifida Ferment Lysate", kb)
        assert result.inci_name == "Bifida Ferment Lysate"

    def test_case_insensitive_lookup(self, kb):
        r1 = analyze_single_ingredient("Water", kb)
        r2 = analyze_single_ingredient("water", kb)
        assert r1.safety_score == r2.safety_score

    def test_large_ingredient_list(self):
        ingredients = ["Water", "Glycerin"] * 30  # 60 种成分
        report = analyze_product("Brand", "Product", ingredients)
        assert report.total_ingredients == 60
