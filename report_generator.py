"""
report_generator.py - AI 分析报告生成模块
Cosmetic Compliance AI - 第三步

调用 Claude LLM 将成分分析数据转化为专业、易懂的自然语言合规性报告。
支持 Anthropic Claude API，无 API Key 时优雅降级并给出配置提示。
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Prompt 设计
# ─────────────────────────────────────────────

def generate_report_prompt(analysis_result: dict) -> str:
    """
    根据分析结果构建专业报告生成 Prompt

    Args:
        analysis_result: 来自 analyzer.report_to_dict() 的字典
    Returns:
        格式化的 Prompt 字符串
    """
    brand         = analysis_result.get("brand", "未知品牌")
    product_name  = analysis_result.get("product_name", "未知产品")
    overall_score = analysis_result.get("overall_safety_score", 5.0)
    overall_level = analysis_result.get("overall_safety_level", "unknown")
    fda_status    = analysis_result.get("fda_compliance", "unknown")
    gb_status     = analysis_result.get("gb_compliance", "unknown")
    highlights    = analysis_result.get("safe_highlights", [])

    level_map = {
        "safe":             "安全",
        "caution":          "需关注",
        "moderate_concern": "中度关注",
        "concern":          "高风险",
    }

    # 安全成分（前10个，排除风险成分）
    safe_ings = [
        ing for ing in analysis_result.get("ingredient_analyses", [])
        if not ing.get("is_flagged", False)
    ]
    safe_names = [
        f"{i['inci_name']}{'（' + i['cn_name'] + '）' if i.get('cn_name') else ''}"
        for i in safe_ings[:10]
    ]

    # 风险成分详情
    risk_ings = analysis_result.get("flagged_ingredients", [])
    risk_lines = []
    for ing in risk_ings:
        name     = ing["inci_name"]
        cn       = f"（{ing['cn_name']}）" if ing.get("cn_name") else ""
        score    = ing.get("safety_score", "?")
        concerns = ing.get("concerns", [])
        fda_s    = ing.get("fda_status", "not_listed")
        gb_s     = ing.get("gb_status", "not_listed")
        line     = f"- **{name}{cn}**：安全评分 {score}/10，FDA={fda_s}，GB={gb_s}"
        if concerns:
            line += f"\n  注意：{'; '.join(concerns[:3])}"
        risk_lines.append(line)

    # 肤质信息
    skin_lines = [
        f"{skin}：{data.get('score', '?')}分（{data.get('label', '?')}）"
        for skin, data in analysis_result.get("skin_suitability", {}).items()
    ]

    prompt = f"""你是一位资深化妆品配方师兼合规专家，拥有10年以上化工背景和皮肤科学经验。\
请根据以下成分分析数据，为消费者撰写一份专业、易懂的合规性分析报告。

---
## 📦 产品信息
- 品牌：{brand}
- 产品：{product_name}
- 综合安全评分：{overall_score}/10（{level_map.get(overall_level, overall_level)}）
- FDA 合规状态：{fda_status}
- 中国 GB 合规状态：{gb_status}

## ✅ 主要安全成分
{', '.join(safe_names) if safe_names else '暂无数据'}

## ⭐ 功效亮点成分
{', '.join(highlights) if highlights else '暂无'}

## ⚠️ 需关注成分
{chr(10).join(risk_lines) if risk_lines else '✅ 未发现风险成分'}

## 💆 肤质适用性评分
{', '.join(skin_lines)}

---
## 报告格式要求

请严格按以下 Markdown 结构输出，总字数控制在 450 字以内：

### 🏷️ 总体评价
（1-2句话，概括产品整体安全性和配方风格）

### ⭐ 成分亮点解析
（重点介绍2-3个优质功效成分，说明其化学原理和护肤机制，体现专业性）

### ⚠️ 风险成分详解
（针对每个风险成分，从化工安全角度说明潜在危害机制和具体使用建议；\
若无风险成分，写"本产品未发现需特别警示的成分"）

### 💆 肤质使用指南
（基于成分组合特点，针对2-3种肤质给出差异化使用建议）

### 📋 合规性小结
（简述 FDA 和中国法规合规情况；若有限制成分，指出关注点）

写作要求：
- 语言专业但通俗，避免过度堆砌术语
- 对风险成分客观评估，不夸大也不淡化
- 整体基调积极、帮助性强
- 适当引用化学机制或皮肤科学原理以增加可信度
"""
    return prompt


# ─────────────────────────────────────────────
# AI 报告生成（主函数）
# ─────────────────────────────────────────────

def generate_compliance_report(
    analysis_result: dict,
    api_key: Optional[str] = None,
) -> dict:
    """
    调用 Claude LLM 生成自然语言合规性报告

    Args:
        analysis_result: report_to_dict() 返回的分析结果字典
        api_key:         Anthropic API Key（为空则读取环境变量 ANTHROPIC_API_KEY）
    Returns:
        {
            product_info:    {"brand": ..., "product_name": ...},
            report_content:  "Markdown 格式报告正文",
            generated_at:    ISO 时间字符串,
            version:         "1.0",
            success:         True/False,
            model:           使用的模型名称（成功时）,
            tokens_used:     {"input": N, "output": N}（成功时）,
            error:           错误信息（失败时）,
        }
    """
    brand        = analysis_result.get("brand", "未知品牌")
    product_name = analysis_result.get("product_name", "未知产品")
    base_info    = {"brand": brand, "product_name": product_name}

    # ── 获取 API Key ──
    key = (api_key or os.getenv("ANTHROPIC_API_KEY", "")).strip()

    if not key:
        logger.warning("[ReportGenerator] ANTHROPIC_API_KEY 未设置，跳过 AI 报告生成")
        return {
            "product_info": base_info,
            "report_content": (
                "> ⚙️ **AI 深度分析未启用**\n\n"
                "请在项目根目录创建 `.env` 文件并添加：\n\n"
                "```\nANTHROPIC_API_KEY=your_api_key_here\n```\n\n"
                "配置完成后重启 Streamlit 应用，即可启用 Claude AI 深度分析功能。\n\n"
                "获取 API Key：[Anthropic Console](https://console.anthropic.com)"
            ),
            "generated_at": datetime.now().isoformat(),
            "version":      "1.0",
            "success":      False,
            "error":        "ANTHROPIC_API_KEY not set",
        }

    # ── 调用 Claude API ──
    try:
        import anthropic  # noqa: PLC0415

        client = anthropic.Anthropic(api_key=key)
        prompt = generate_report_prompt(analysis_result)

        logger.info(f"[ReportGenerator] 调用 Claude API：{brand} · {product_name}")

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        report_content = message.content[0].text

        logger.info(
            f"[ReportGenerator] 报告生成成功，"
            f"tokens: in={message.usage.input_tokens} out={message.usage.output_tokens}"
        )

        return {
            "product_info":   base_info,
            "report_content": report_content,
            "generated_at":   datetime.now().isoformat(),
            "version":        "1.0",
            "success":        True,
            "model":          "claude-sonnet-4-6",
            "tokens_used": {
                "input":  message.usage.input_tokens,
                "output": message.usage.output_tokens,
            },
        }

    except ImportError:
        msg = "anthropic 包未安装。请运行：`pip install anthropic`，然后重启应用。"
        logger.error(f"[ReportGenerator] {msg}")
        return {
            "product_info":   base_info,
            "report_content": f"> ❌ **依赖缺失**\n\n{msg}",
            "generated_at":   datetime.now().isoformat(),
            "version":        "1.0",
            "success":        False,
            "error":          msg,
        }

    except Exception as exc:  # noqa: BLE001
        logger.error(f"[ReportGenerator] AI 报告生成异常: {exc}")
        return {
            "product_info":   base_info,
            "report_content": f"> ❌ **AI 报告生成失败**\n\n错误信息：`{exc}`",
            "generated_at":   datetime.now().isoformat(),
            "version":        "1.0",
            "success":        False,
            "error":          str(exc),
        }


# ─────────────────────────────────────────────
# 规则引擎：单成分风险评估（无需 API Key）
# ─────────────────────────────────────────────

def generate_risk_assessment(
    ingredient_name: str,
    safety_score: int,
    concerns: list,
    fda_status: str = "not_listed",
    gb_status: str  = "not_listed",
) -> dict:
    """
    基于化工规则引擎对单个成分生成风险评估（不依赖 LLM）

    Args:
        ingredient_name: INCI 成分名称
        safety_score:    安全评分 (1-10)
        concerns:        已知注意事项列表
        fda_status:      FDA 合规状态字符串
        gb_status:       GB 合规状态字符串
    Returns:
        {ingredient, risk_level, risk_label, reason, recommendation, concerns}
    """
    RISK_LABELS = {"low": "低风险", "medium": "中风险", "high": "高风险"}

    # 法规状态优先
    if fda_status == "prohibited" or gb_status == "prohibited":
        risk_level     = "high"
        reason         = f"该成分已被监管机构明确禁用（FDA: {fda_status}，GB: {gb_status}）。"
        recommendation = "强烈建议避免使用，或联系品牌方确认成分合规性。"

    elif fda_status == "restricted" or gb_status == "restricted":
        risk_level     = "medium"
        reason         = (
            concerns[0] if concerns
            else f"该成分属受限成分（FDA: {fda_status}，GB: {gb_status}），需控制使用浓度。"
        )
        recommendation = "请确认产品成分浓度符合法规上限，敏感肌及孕妇请谨慎使用。"

    elif safety_score >= 8:
        risk_level     = "low"
        reason         = "该成分在推荐浓度下安全性良好，符合国际化妆品安全标准。"
        recommendation = "正常使用安全，无需特殊注意。"

    elif safety_score >= 5:
        risk_level     = "medium"
        reason         = concerns[0] if concerns else "该成分存在一定使用限制，请关注浓度及适用人群。"
        recommendation = "敏感肌建议进行48小时贴肤测试；孕妇及婴幼儿请谨慎使用。"

    else:
        risk_level     = "high"
        reason         = concerns[0] if concerns else "该成分风险评分较低，多国法规对其有严格限制。"
        recommendation = "建议避免使用，或在皮肤科医生指导下谨慎选用。"

    return {
        "ingredient":     ingredient_name,
        "risk_level":     risk_level,
        "risk_label":     RISK_LABELS[risk_level],
        "reason":         reason,
        "recommendation": recommendation,
        "concerns":       concerns,
    }
