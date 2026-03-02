"""
app.py - Streamlit 主应用
Cosmetic Compliance AI - AI 化妆品成分合规性分析助手

运行方式：streamlit run app.py
"""

import streamlit as st
from datetime import datetime

from scraper import web_scraper, parse_ingredient_text, validate_ingredients
from cache import (
    check_cache, cache_result, generate_product_id,
    save_query_history, get_query_history, get_cache_stats, clear_cache
)
from analyzer import analyze_product, report_to_dict

# ─────────────────────────────────────────────
# 页面配置
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="化妆品成分合规性分析助手",
    page_icon="🧴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# 全局样式
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* 主色调 */
:root {
    --primary: #FF6B9D;
    --safe: #28a745;
    --caution: #ffc107;
    --concern: #dc3545;
    --unknown: #6c757d;
}

/* 卡片样式 */
.metric-card {
    background: linear-gradient(135deg, #fff5f8, #fff);
    border: 1px solid #ffe0ec;
    border-radius: 12px;
    padding: 18px 22px;
    margin: 8px 0;
    box-shadow: 0 2px 8px rgba(255,107,157,0.08);
}

/* 成分标签 */
.ingredient-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 13px;
    margin: 3px;
    font-weight: 500;
}
.badge-safe { background: #d4edda; color: #155724; }
.badge-caution { background: #fff3cd; color: #856404; }
.badge-concern { background: #f8d7da; color: #721c24; }
.badge-unknown { background: #e9ecef; color: #495057; }

/* 报告区块 */
.report-section {
    background: #fff;
    border-radius: 10px;
    padding: 16px 20px;
    margin: 10px 0;
    border-left: 4px solid var(--primary);
}

/* 合规性徽章 */
.compliance-ok   { color: #28a745; font-weight: bold; }
.compliance-warn { color: #ffc107; font-weight: bold; }
.compliance-bad  { color: #dc3545; font-weight: bold; }

/* 标题渐变 */
.gradient-title {
    background: linear-gradient(90deg, #FF6B9D, #C770CF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.2em;
    font-weight: 800;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────

SAFETY_EMOJI = {
    "safe":             ("🟢", "安全", "#28a745"),
    "caution":          ("🟡", "需关注", "#ffc107"),
    "moderate_concern": ("🟠", "中度关注", "#fd7e14"),
    "concern":          ("🔴", "高风险", "#dc3545"),
    "prohibited":       ("⛔", "禁用", "#721c24"),
    "unknown":          ("⚪", "未知", "#6c757d"),
}

COMPLIANCE_ICON = {
    "compliant":  "✅ 合规",
    "restricted": "⚠️ 限制使用",
    "prohibited": "🚫 含禁用成分",
}


def safety_color(level: str) -> str:
    return SAFETY_EMOJI.get(level, ("⚪", "未知", "#6c757d"))[2]


def render_score_bar(score: float, max_score: float = 10) -> str:
    """渲染评分进度条 HTML"""
    pct = int(score / max_score * 100)
    color = "#28a745" if score >= 8 else ("#ffc107" if score >= 6 else "#dc3545")
    return f"""
    <div style="background:#e9ecef;border-radius:8px;height:12px;width:100%;">
        <div style="background:{color};width:{pct}%;height:12px;border-radius:8px;
                    transition:width 0.5s;"></div>
    </div>
    <small style="color:{color};font-weight:600;">{score}/10</small>
    """


def get_badge_class(level: str) -> str:
    mapping = {
        "safe": "badge-safe",
        "caution": "badge-caution",
        "moderate_concern": "badge-concern",
        "concern": "badge-concern",
        "prohibited": "badge-concern",
    }
    return mapping.get(level, "badge-unknown")


# ─────────────────────────────────────────────
# 侧边栏
# ─────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🧴 导航")
        st.markdown("---")

        # 缓存状态
        stats = get_cache_stats()
        st.markdown("### 📦 缓存状态")
        col1, col2 = st.columns(2)
        col1.metric("有效缓存", stats["valid_entries"])
        col2.metric("大小(KB)", stats["cache_size_kb"])

        if st.button("🗑️ 清除所有缓存", use_container_width=True):
            n = clear_cache()
            st.success(f"已清除 {n} 条缓存")

        st.markdown("---")

        # 查询历史
        st.markdown("### 🕐 最近查询")
        history = get_query_history(limit=8)
        if history:
            for h in history:
                brand = h.get("brand", "?")
                product = h.get("product", "?")
                queried_at = h.get("queried_at", "")
                try:
                    dt = datetime.fromisoformat(queried_at)
                    time_str = dt.strftime("%m/%d %H:%M")
                except ValueError:
                    time_str = ""
                st.markdown(f"- `{brand}` · {product} <small>{time_str}</small>",
                            unsafe_allow_html=True)
        else:
            st.caption("暂无查询历史")

        st.markdown("---")
        st.markdown("### 📖 关于")
        st.markdown("""
**Cosmetic Compliance AI** v1.0  
数据来源：
- 🇺🇸 FDA Cosmetics Regulations  
- 🇨🇳 化妆品安全技术规范(2015)  
- 📊 本地成分安全数据库

[GitHub 仓库](https://github.com) | 
[问题反馈](https://github.com/issues)
        """)


# ─────────────────────────────────────────────
# 主界面：产品输入
# ─────────────────────────────────────────────

def render_input_section() -> dict | None:
    """渲染用户输入区域，返回产品信息字典或 None"""

    st.markdown('<p class="gradient-title">化妆品成分合规性分析助手</p>', unsafe_allow_html=True)
    st.markdown("##### *透明度不仅是营销——更是科学*")

    with st.expander("💡 为什么成分表很重要？", expanded=False):
        st.markdown("""
化妆品成分表揭示了产品的科学配方。通过分析成分，我们可以：
- 🔍 **评估安全性**：识别潜在有害或致敏成分
- ✅ **检查合规性**：对照 FDA 和中国 GB 标准
- 💆 **匹配肤质**：了解哪些成分适合您的皮肤类型
- 📊 **量化风险**：获得直观的安全评分

本工具将帮助您读懂复杂的成分标签，做出更明智的护肤选择。
        """)

    st.markdown("---")

    # 输入方式选择
    input_method = st.radio(
        "**选择产品信息输入方式：**",
        ["🔍 手动输入品牌和产品名称", "📝 直接粘贴成分表", "📋 示例演示"],
        horizontal=True,
    )

    product_info = {}

    if "手动输入" in input_method:
        col1, col2 = st.columns(2)
        with col1:
            brand = st.text_input(
                "🏷️ 品牌名称",
                placeholder="例如：欧莱雅 / L'Oréal",
                help="支持中英文品牌名"
            )
        with col2:
            product = st.text_input(
                "📦 产品名称",
                placeholder="例如：小黑瓶精华",
                help="请输入具体产品型号"
            )

        if brand and product:
            product_info = {
                "brand": brand,
                "product": product,
                "input_method": "manual",
                "ingredients": None,
            }

    elif "直接粘贴" in input_method:
        col1, col2 = st.columns(2)
        with col1:
            brand = st.text_input("🏷️ 品牌名称（选填）", placeholder="例如：自有品牌")
        with col2:
            product = st.text_input("📦 产品名称（选填）", placeholder="例如：保湿面霜")

        raw_text = st.text_area(
            "📋 粘贴产品成分表（INCI或中文均可，逗号/换行分隔）",
            height=150,
            placeholder="例如：Water, Glycerin, Niacinamide, Sodium Hyaluronate, Phenoxyethanol...",
            help="从产品外包装或品牌官网复制成分全表"
        )

        if raw_text.strip():
            parsed = parse_ingredient_text(raw_text)
            validation = validate_ingredients(parsed)
            if validation["valid"]:
                st.success(f"✅ {validation['message']}")
                product_info = {
                    "brand": brand or "未知品牌",
                    "product": product or "自定义产品",
                    "input_method": "paste",
                    "ingredients": parsed,
                }
            else:
                st.error(f"❌ {validation['message']}")

    else:  # 示例演示
        st.markdown("**选择示例产品体验分析效果：**")
        demo_options = {
            "欧莱雅 · 小黑瓶精华": ("欧莱雅", "小黑瓶精华"),
            "雅诗兰黛 · 小棕瓶精华": ("雅诗兰黛", "小棕瓶"),
            "珀莱雅 · 双抗精华": ("珀莱雅", "双抗精华"),
            "完美日记 · 粉底液": ("完美日记", "粉底液"),
            "薇诺娜 · 舒缓保湿霜": ("薇诺娜", "舒缓保湿霜"),
        }
        demo_choice = st.selectbox("选择示例产品", list(demo_options.keys()))
        brand, product = demo_options[demo_choice]
        product_info = {
            "brand": brand,
            "product": product,
            "input_method": "manual",
            "ingredients": None,
        }
        st.info(f"📌 已选择示例：**{demo_choice}**，点击下方按钮开始分析")

    return product_info if product_info else None


# ─────────────────────────────────────────────
# 结果展示
# ─────────────────────────────────────────────

def render_overview(report: dict):
    """渲染总览卡片"""
    score = report["overall_safety_score"]
    level = report["overall_safety_level"]
    emoji, label, color = SAFETY_EMOJI.get(level, ("⚪", "未知", "#6c757d"))

    st.markdown("### 📊 分析总览")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:14px;color:#888;">综合安全评分</div>
            <div style="font-size:2.2em;font-weight:800;color:{color};">{score}</div>
            <div style="font-size:13px;">/10 分</div>
            {render_score_bar(score)}
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:14px;color:#888;">安全等级</div>
            <div style="font-size:2em;font-weight:800;color:{color};">{emoji}</div>
            <div style="font-size:14px;font-weight:600;color:{color};">{label}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        flag_count = len(report["flagged_ingredients"])
        flag_color = "#dc3545" if flag_count > 0 else "#28a745"
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:14px;color:#888;">风险成分</div>
            <div style="font-size:2.2em;font-weight:800;color:{flag_color};">{flag_count}</div>
            <div style="font-size:13px;">/ {report['total_ingredients']} 种</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        fda_c = report["fda_compliance"]
        gb_c  = report["gb_compliance"]
        fda_icon = COMPLIANCE_ICON.get(fda_c, fda_c)
        gb_icon  = COMPLIANCE_ICON.get(gb_c, gb_c)
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:14px;color:#888;">合规状态</div>
            <div style="font-size:13px;margin-top:6px;">🇺🇸 FDA: {fda_icon}</div>
            <div style="font-size:13px;margin-top:4px;">🇨🇳 GB: {gb_icon}</div>
        </div>
        """, unsafe_allow_html=True)


def render_flagged_ingredients(report: dict):
    """渲染风险成分详情"""
    flagged = report["flagged_ingredients"]
    if not flagged:
        st.success("🎉 未发现需要特别关注的风险成分！")
        return

    st.markdown(f"### ⚠️ 需关注成分（{len(flagged)} 种）")
    for item in flagged:
        level = item.get("safety_level", "unknown")
        emoji = SAFETY_EMOJI.get(level, ("⚪", "未知", "#6c757d"))[0]
        color = safety_color(level)

        with st.expander(
            f"{emoji} **{item['inci_name']}** "
            f"{'（' + item['cn_name'] + '）' if item.get('cn_name') else ''} "
            f"— 安全评分 {item.get('safety_score', '?')}/10",
            expanded=False
        ):
            col1, col2 = st.columns([2, 1])
            with col1:
                if item.get("description"):
                    st.markdown(f"📌 **描述：** {item['description']}")
                if item.get("function"):
                    st.markdown(f"🔬 **功能：** {', '.join(item['function'])}")
                if item.get("concerns"):
                    st.markdown("⚠️ **注意事项：**")
                    for concern in item["concerns"]:
                        st.markdown(f"  - {concern}")
            with col2:
                st.markdown(f"**FDA状态：** `{item.get('fda_status', 'not_listed')}`")
                st.markdown(f"**GB状态：** `{item.get('gb_status', 'not_listed')}`")
                if item.get("ewg_score"):
                    st.markdown(f"**EWG评分：** {item['ewg_score']}/10")
                st.markdown(render_score_bar(item.get("safety_score", 5)), unsafe_allow_html=True)


def render_all_ingredients(report: dict):
    """渲染全部成分列表（可搜索）"""
    st.markdown(f"### 🔬 成分全表（{report['total_ingredients']} 种）")

    search = st.text_input("🔍 搜索成分", placeholder="输入成分名称过滤...", key="ingredient_search")

    analyses = report["ingredient_analyses"]
    if search:
        analyses = [a for a in analyses if search.lower() in a["inci_name"].lower()
                    or search.lower() in a.get("cn_name", "").lower()]

    # 表格头
    header_cols = st.columns([3, 2, 1.5, 1.5, 2, 3])
    headers = ["INCI 名称", "中文名", "安全评分", "安全等级", "功能", "注意事项"]
    for col, h in zip(header_cols, headers):
        col.markdown(f"**{h}**")
    st.markdown("---")

    for item in analyses:
        level = item.get("safety_level", "unknown")
        emoji, label, color = SAFETY_EMOJI.get(level, ("⚪", "未知", "#6c757d"))
        badge_class = get_badge_class(level)

        row_cols = st.columns([3, 2, 1.5, 1.5, 2, 3])
        row_cols[0].markdown(f"**{item['inci_name']}**")
        row_cols[1].markdown(item.get("cn_name", "-"))
        row_cols[2].markdown(f"**{item.get('safety_score', '?')}**/10")
        row_cols[3].markdown(
            f"<span class='ingredient-badge {badge_class}'>{emoji} {label}</span>",
            unsafe_allow_html=True
        )
        funcs = item.get("function", [])
        row_cols[4].markdown(", ".join(funcs[:2]) if funcs else "-")
        concerns = item.get("concerns", [])
        row_cols[5].markdown(
            f"<small style='color:#888;'>{concerns[0][:50] + '...' if concerns and len(concerns[0]) > 50 else (concerns[0] if concerns else '-')}</small>",
            unsafe_allow_html=True
        )


def render_skin_suitability(report: dict):
    """渲染肤质适用性雷达图（使用进度条模拟）"""
    st.markdown("### 💆 肤质适用性")
    suitability = report.get("skin_suitability", {})

    cols = st.columns(len(suitability))
    for col, (skin_type, data) in zip(cols, suitability.items()):
        score = data.get("score", 5)
        label = data.get("label", "一般")
        color = "#28a745" if label == "适合" else ("#ffc107" if label == "一般" else "#dc3545")
        col.markdown(f"""
        <div style="text-align:center;padding:12px 8px;background:#f8f9fa;
                    border-radius:10px;border:1px solid #e9ecef;">
            <div style="font-size:13px;color:#666;margin-bottom:6px;">{skin_type}</div>
            <div style="font-size:1.6em;font-weight:700;color:{color};">{score}</div>
            <div style="font-size:12px;color:{color};font-weight:600;">{label}</div>
        </div>
        """, unsafe_allow_html=True)


def render_recommendations(report: dict):
    """渲染建议列表"""
    st.markdown("### 💊 专业建议")
    recommendations = report.get("recommendations", [])
    if recommendations:
        for rec in recommendations:
            st.markdown(f"> {rec}")
    else:
        st.info("暂无特殊建议，该产品成分整体安全性良好。")


def render_highlights(report: dict):
    """渲染优质成分亮点"""
    highlights = report.get("safe_highlights", [])
    if not highlights:
        return
    st.markdown("### ✨ 优质成分亮点")
    badges_html = " ".join(
        f"<span class='ingredient-badge badge-safe'>✅ {h}</span>"
        for h in highlights
    )
    st.markdown(badges_html, unsafe_allow_html=True)


def render_report(report: dict):
    """渲染完整分析报告"""
    brand = report.get("brand", "")
    product = report.get("product_name", "")

    st.markdown(f"## 📋 分析报告：{brand} · {product}")
    st.caption(report.get("summary", ""))
    st.markdown("---")

    # 总览
    render_overview(report)

    # 标签页
    tab1, tab2, tab3, tab4 = st.tabs(
        ["⚠️ 风险成分", "🔬 成分全表", "💆 肤质适用", "💊 建议"]
    )

    with tab1:
        render_flagged_ingredients(report)
        render_highlights(report)

    with tab2:
        render_all_ingredients(report)

    with tab3:
        render_skin_suitability(report)

    with tab4:
        render_recommendations(report)

    # 导出
    st.markdown("---")
    col1, col2 = st.columns([1, 5])
    with col1:
        import json
        export_data = json.dumps(report, ensure_ascii=False, indent=2)
        st.download_button(
            "📥 导出 JSON 报告",
            data=export_data,
            file_name=f"{brand}_{product}_report.json",
            mime="application/json",
            use_container_width=True
        )


# ─────────────────────────────────────────────
# 主逻辑
# ─────────────────────────────────────────────

def get_product_info(product_info: dict) -> dict:
    """
    核心数据获取与分析逻辑

    1. 检查缓存
    2. 爬虫获取（或使用用户粘贴的成分）
    3. AI 分析
    4. 存入缓存 & 历史
    """
    brand   = product_info.get("brand", "未知品牌")
    product = product_info.get("product", "未知产品")

    # 生成产品 ID
    product_id = generate_product_id(brand, product)

    # 检查缓存（粘贴模式跳过缓存检查）
    if product_info.get("input_method") != "paste":
        cached = check_cache(product_id)
        if cached:
            cached["_from_cache"] = True
            return cached

    # 获取成分列表
    if product_info.get("input_method") == "paste" and product_info.get("ingredients"):
        ingredients = product_info["ingredients"]
        source = "user_input"
    else:
        ingredients = web_scraper(brand, product)
        source = "web_scraper"

    # 分析
    report_obj = analyze_product(brand, product, ingredients)
    report_dict = report_to_dict(report_obj)
    report_dict["_source"] = source
    report_dict["_from_cache"] = False

    # 缓存 & 历史
    cache_result(product_id, report_dict)
    save_query_history(product_id, brand, product, source, report_dict)

    return report_dict


def main():
    render_sidebar()

    # 输入区
    product_info = render_input_section()

    # 分析按钮
    st.markdown("")
    btn_disabled = product_info is None
    if st.button(
        "🚀 开始分析",
        type="primary",
        disabled=btn_disabled,
        use_container_width=False,
        key="analyze_btn"
    ):
        if product_info:
            with st.spinner("⏳ 正在分析成分，请稍候..."):
                try:
                    result = get_product_info(product_info)

                    if result.get("_from_cache"):
                        st.info("⚡ 结果来自缓存（响应更快）")
                    else:
                        st.success(
                            f"✅ 分析完成！数据来源：{result.get('_source', 'N/A')}"
                        )

                    render_report(result)

                except Exception as e:
                    st.error(f"❌ 分析过程中出现错误：{str(e)}")
                    st.info("请检查输入信息是否正确，或稍后重试。")
                    with st.expander("错误详情"):
                        import traceback
                        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
