"""Streamlit 页面入口。

运行方式：
    streamlit run app.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import streamlit as st

from recommender import (
    build_team_role_plan,
    format_tags,
    label_armor_type,
    label_attack_type,
    label_battle_position,
    label_position,
    label_role,
    load_characters,
    recommend_for_box,
    recommend_teammates_for_core,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "characters.json"


@st.cache_data
def get_characters(data_mtime: float) -> list[dict]:
    """读取角色数据，并用 Streamlit 缓存避免每次交互都重新读文件。"""
    # data_mtime 用来让 Streamlit 在 JSON 文件更新后自动刷新缓存。
    return load_characters(DATA_PATH)


def clear_owned_box() -> None:
    """清空玩家手动维护的 Box。"""
    st.session_state["owned_names"] = []


def normalize_box_names(raw_data: object, valid_names: list[str]) -> list[str]:
    """从导入的 JSON 中提取角色名称，并过滤掉角色库不存在的名字。"""
    imported_names: list[str] = []

    if isinstance(raw_data, list):
        imported_names = [str(name) for name in raw_data]

    if isinstance(raw_data, dict):
        for key in ["owned_names", "owned", "characters", "box"]:
            value = raw_data.get(key)
            if isinstance(value, list):
                imported_names = [str(name) for name in value]
                break
            if isinstance(value, dict):
                imported_names = [
                    str(name)
                    for name, enabled in value.items()
                    if enabled
                ]
                break

    valid_name_set = set(valid_names)
    return [name for name in valid_names if name in set(imported_names) & valid_name_set]


def build_box_json(owned_names: list[str]) -> bytes:
    """生成可下载的 Box JSON 文件内容。"""
    payload = {
        "owned_names": owned_names,
        "note": "由碧蓝档案配队推荐器导出，可重新导入到我的 Box。",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def render_tag_list(tags: list[str]) -> None:
    """用简单的胶囊标签展示角色技能关键词。"""
    tag_html = "".join(f"<span class='tag'>{tag}</span>" for tag in format_tags(tags))
    st.markdown(f"<div class='tag-row'>{tag_html}</div>", unsafe_allow_html=True)


def format_gamekee_rating(character: dict) -> str:
    """返回 GameKee 角色评测里的综合评分。"""
    rating = (character.get("ratings") or {}).get("gamekee_overall") or {}
    return rating.get("overall") or "暂无评分"


def render_character_panel(character: dict) -> None:
    """展示当前选择角色的核心信息。"""
    st.markdown(f"### {character['name']}")

    ex_cost = character.get("ex_cost") or "待补充"
    stats = [
        ("定位", label_role(character["role"])),
        ("队伍位", label_position(character["position"])),
        ("战斗站位", label_battle_position(character.get("battle_position", "unknown"))),
        ("攻击", label_attack_type(character["attack_type"])),
        ("护甲", label_armor_type(character["armor_type"])),
        ("EX 费用", str(ex_cost)),
        ("GameKee 评分", format_gamekee_rating(character)),
    ]
    for row_start in range(0, len(stats), 2):
        columns = st.columns(2)
        for column, (label, value) in zip(columns, stats[row_start : row_start + 2]):
            with column:
                st.caption(label)
                st.markdown(f"**{value}**")

    source = character.get("source") or {}
    if source:
        source_parts = [
            source.get("rarity") or "",
            source.get("weapon_type") or "",
            source.get("school") or "",
        ]
        st.caption(" / ".join(part for part in source_parts if part))
    render_tag_list(character["tags"])

    with st.expander("技能摘要", expanded=False):
        for skill_name, description in character["skills"].items():
            st.markdown(f"**{skill_name.upper()}**：{description}")


def render_core_character_panels(selected_characters: list[dict]) -> None:
    """展示一个或多个玩家想围绕配队的核心角色。"""
    if len(selected_characters) == 1:
        render_character_panel(selected_characters[0])
        return

    st.caption(f"已选择 {len(selected_characters)} 个核心角色")
    for index, character in enumerate(selected_characters):
        with st.expander(character["name"], expanded=index == 0):
            render_character_panel(character)


def render_team_role_plan(role_plan: dict) -> None:
    """展示当前核心角色已经覆盖和仍需要补齐的队伍职责。"""
    target_labels = "、".join(slot["label"] for slot in role_plan["target"])
    covered_labels = "、".join(slot["label"] for slot in role_plan["covered"]) or "暂无"
    missing_labels = "、".join(slot["label"] for slot in role_plan["missing"])
    missing_text = missing_labels or "基础职责已覆盖，下面会继续按适配度推荐更多队友"

    st.markdown(
        f"""
        <div class="role-plan">
            <div class="role-plan-title">队伍职责检查</div>
            <div>目标骨架：{target_labels}</div>
            <div>已覆盖：{covered_labels}</div>
            <div>优先补位：{missing_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_recommendation_card(item: dict, rank: int) -> None:
    """展示一个推荐队友卡片。"""
    character = item["character"]
    score = item["score"]
    reasons = item["reasons"]
    slot_badge = ""
    if item.get("slot_label"):
        slot_badge = f"<span class='slot-badge'>补位：{item['slot_label']}</span>"
    rank_row = f'<div class="rank-row"><span class="rank">推荐 {rank}</span>{slot_badge}</div>'
    ex_cost = character.get("ex_cost") or "待补充"

    st.markdown(
        "\n".join(
            [
                '<section class="recommend-card">',
                '<div class="card-header">',
                "<div>",
                rank_row,
                f"<h3>{character['name']}</h3>",
                "</div>",
                f'<div class="score">适配 {score} 分</div>',
                "</div>",
                '<div class="meta">',
                f"<span>{label_role(character['role'])}</span>",
                f"<span>{label_position(character['position'])}</span>",
                f"<span>{label_battle_position(character.get('battle_position', 'unknown'))}</span>",
                f"<span>{label_attack_type(character['attack_type'])}</span>",
                f"<span>EX {ex_cost}</span>",
                f"<span>综合评分 {format_gamekee_rating(character)}</span>",
                "</div>",
                "</section>",
            ]
        ),
        unsafe_allow_html=True,
    )

    render_tag_list(character["tags"])
    st.markdown("**推荐理由**")
    for reason in reasons[:5]:
        st.markdown(f"- {reason}")


def split_recommendations_by_position(
    recommendations: list[dict],
) -> dict[str, list[dict]]:
    """把推荐结果按 Striker / Special 分组。"""
    groups = {"striker": [], "special": [], "unknown": []}
    for item in recommendations:
        position = item["character"].get("position", "unknown")
        group_key = position if position in groups else "unknown"
        groups[group_key].append(item)
    return groups


def render_recommendation_groups(
    recommendations: list[dict],
    limit_per_group: int,
) -> None:
    """分前排上场位和后排支援位展示推荐结果。"""
    groups = split_recommendations_by_position(recommendations)
    group_configs = [
        ("striker", "前排上场（Striker）", "会占用 4 个上场学生位，通常承担输出、坦克、治疗或场上辅助职责。"),
        ("special", "后排支援（Special）", "位于 2 个支援学生位，通常提供治疗、增益、减益、召唤或功能支援。"),
    ]

    for group_key, title, caption in group_configs:
        st.markdown(f"<div class='group-title'>{title}</div>", unsafe_allow_html=True)
        st.caption(caption)
        items = groups.get(group_key, [])[:limit_per_group]
        if not items:
            st.info("当前规则下这一组暂无推荐角色。")
            continue
        for index, item in enumerate(items, start=1):
            render_recommendation_card(item, index)

    unknown_items = groups.get("unknown", [])[:limit_per_group]
    if unknown_items:
        st.markdown("<div class='group-title'>位置待补充</div>", unsafe_allow_html=True)
        for index, item in enumerate(unknown_items, start=1):
            render_recommendation_card(item, index)


def render_compact_grouped_list(recommendations: list[dict]) -> None:
    """在折叠区内用紧凑列表展示分组后的理想推荐。"""
    groups = split_recommendations_by_position(recommendations)
    for group_key, title in [
        ("striker", "前排上场（Striker）"),
        ("special", "后排支援（Special）"),
    ]:
        items = groups.get(group_key, [])
        if not items:
            continue
        st.markdown(f"**{title}**")
        for index, item in enumerate(items, start=1):
            character = item["character"]
            st.markdown(
                f"{index}. **{character['name']}** "
                f"（{label_role(character['role'])}，"
                f"{label_battle_position(character.get('battle_position', 'unknown'))}，"
                f"综合评分 {format_gamekee_rating(character)}，"
                f"{item['score']} 分）"
            )


def render_missing_summary(box_result: dict) -> None:
    """展示理想推荐里玩家当前缺少的角色。"""
    missing = box_result["missing"]
    substitutions = box_result["substitutions"]

    if not missing:
        st.success("你的 Box 已覆盖当前理想推荐中的关键队友。")
        return

    st.markdown("**缺少的理想队友**")
    missing_names = [
        f"{item['character']['name']}（"
        f"{'补' + item['slot_label'] + '，' if item.get('slot_label') else ''}"
        f"{label_role(item['character']['role'])}，{item['score']} 分）"
        for item in missing
    ]
    st.markdown("、".join(missing_names))

    if substitutions:
        st.markdown("**Box 内替代建议**")
        for item in substitutions:
            missing_character = item["missing"]["character"]
            alternative_character = item["alternative"]["character"]
            st.markdown(
                f"- 缺少 **{missing_character['name']}** 时，可以先用 "
                f"**{alternative_character['name']}**：{item['reason']}"
            )


def main() -> None:
    st.set_page_config(
        page_title="碧蓝档案配队推荐器",
        page_icon="🎯",
        layout="wide",
    )

    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2rem;
                max-width: 1120px;
            }
            .app-title {
                font-size: 2.15rem;
                font-weight: 760;
                margin-bottom: 0.2rem;
                letter-spacing: 0;
            }
            .app-subtitle {
                color: #52606d;
                font-size: 1rem;
                margin-bottom: 1.35rem;
            }
            .tag-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
                margin: 0.45rem 0 1rem 0;
            }
            .tag {
                display: inline-flex;
                align-items: center;
                min-height: 1.7rem;
                padding: 0.18rem 0.58rem;
                border-radius: 999px;
                border: 1px solid #d8dee8;
                background: #f7f9fc;
                color: #334155;
                font-size: 0.82rem;
                line-height: 1.2;
                white-space: nowrap;
            }
            .recommend-card {
                border: 1px solid #d9e2ec;
                border-radius: 8px;
                padding: 1rem 1.05rem 0.9rem 1.05rem;
                margin-top: 1rem;
                background: #ffffff;
            }
            .role-plan {
                border-left: 4px solid #0f766e;
                background: #f0fdfa;
                padding: 0.8rem 0.95rem;
                margin: 0.35rem 0 0.8rem 0;
                color: #134e4a;
                line-height: 1.65;
            }
            .role-plan-title {
                font-weight: 760;
                margin-bottom: 0.2rem;
            }
            .group-title {
                margin-top: 1.35rem;
                font-size: 1.2rem;
                font-weight: 720;
                letter-spacing: 0;
            }
            .card-header {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 1rem;
            }
            .rank {
                color: #64748b;
                font-size: 0.82rem;
            }
            .rank-row {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: 0.45rem;
                margin-bottom: 0.16rem;
            }
            .slot-badge {
                display: inline-flex;
                align-items: center;
                min-height: 1.35rem;
                padding: 0.08rem 0.45rem;
                border-radius: 999px;
                background: #ccfbf1;
                color: #115e59;
                font-size: 0.78rem;
                font-weight: 700;
            }
            .recommend-card h3 {
                margin: 0;
                font-size: 1.28rem;
                letter-spacing: 0;
            }
            .score {
                min-width: 5.8rem;
                text-align: center;
                border-radius: 8px;
                padding: 0.45rem 0.65rem;
                background: #0f766e;
                color: white;
                font-weight: 700;
            }
            .meta {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.7rem;
                color: #475569;
                font-size: 0.92rem;
            }
            .meta span {
                padding-right: 0.55rem;
                border-right: 1px solid #cbd5e1;
            }
            .meta span:last-child {
                border-right: none;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    characters = get_characters(DATA_PATH.stat().st_mtime)
    character_names = [character["name"] for character in characters]
    if "owned_names" not in st.session_state:
        st.session_state["owned_names"] = []

    st.markdown("<div class='app-title'>碧蓝档案配队推荐器</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='app-subtitle'>选择一个或多个核心角色，查看适合的新手向队友推荐和规则解释。</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"当前本地角色库共 {len(characters)} 名角色；名单来自 GameKee，结构化站位和技能资料来自 SchaleDB。"
    )

    with st.sidebar:
        st.header("筛选")
        if "selected_names" not in st.session_state:
            st.session_state["selected_names"] = [character_names[0]]
        else:
            st.session_state["selected_names"] = [
                name
                for name in st.session_state["selected_names"]
                if name in character_names
            ]

        selected_names = st.multiselect(
            "选择核心角色",
            character_names,
            key="selected_names",
            help="可以选择 1 个或多个你想放进队伍的角色，系统会围绕这个组合推荐队友。",
        )
        top_n = st.slider("每组推荐数量", min_value=3, max_value=8, value=5)

        st.divider()
        st.header("我的 Box")
        use_box_mode = st.toggle("只推荐我拥有的角色", value=False)

        uploaded_box = st.file_uploader("导入 Box JSON", type=["json"])
        if uploaded_box is not None:
            uploaded_bytes = uploaded_box.getvalue()
            signature = hashlib.sha256(uploaded_bytes).hexdigest()
            if st.session_state.get("box_import_signature") != signature:
                try:
                    imported_data = json.loads(uploaded_bytes.decode("utf-8"))
                    imported_names = normalize_box_names(imported_data, character_names)
                    st.session_state["owned_names"] = imported_names
                    st.session_state["box_import_signature"] = signature
                    st.success(f"已导入 {len(imported_names)} 名拥有角色")
                except json.JSONDecodeError:
                    st.error("导入失败：JSON 格式不正确")

        owned_names = st.multiselect(
            "已拥有角色",
            character_names,
            key="owned_names",
        )
        st.caption(f"已选择 {len(owned_names)} / {len(character_names)} 名角色")
        st.download_button(
            "导出 my_box.json",
            data=build_box_json(owned_names),
            file_name="my_box.json",
            mime="application/json",
            disabled=not owned_names,
        )
        st.button("清空 Box", on_click=clear_owned_box, disabled=not owned_names)

    if not selected_names:
        st.info("请先在侧栏选择至少一个核心角色。")
        return

    character_by_name = {character["name"]: character for character in characters}
    selected_characters = [character_by_name[name] for name in selected_names]
    role_plan = build_team_role_plan(selected_characters)

    left, right = st.columns([0.95, 1.35], gap="large")

    with left:
        st.subheader("核心角色")
        render_core_character_panels(selected_characters)

    with right:
        if use_box_mode:
            st.subheader("你的 Box 可用推荐")
            render_team_role_plan(role_plan)
            owned_name_set = set(owned_names)
            if not owned_names:
                st.info("先在侧栏“我的 Box”里选择你拥有的角色，再开启差异化推荐。")
                return

            missing_core_names = [
                name for name in selected_names if name not in owned_name_set
            ]
            if missing_core_names:
                st.warning(
                    "这些核心角色不在你的 Box 中："
                    f"{'、'.join(missing_core_names)}；这里仍会围绕它们推荐你已拥有的队友。"
                )

            box_result = recommend_for_box(
                selected_names,
                characters,
                owned_name_set,
                top_n=top_n,
            )
            owned_recommendations = recommend_teammates_for_core(
                selected_names,
                characters,
                top_n=len(characters),
                allowed_names=owned_name_set,
            )

            if owned_recommendations:
                render_recommendation_groups(owned_recommendations, top_n)
            else:
                st.warning("你的 Box 中暂时没有可推荐的队友。")

            st.divider()
            render_missing_summary(box_result)

            with st.expander("查看全角色理想推荐", expanded=False):
                all_recommendations = recommend_teammates_for_core(
                    selected_names,
                    characters,
                    top_n=len(characters),
                )
                render_compact_grouped_list(all_recommendations[: top_n * 2])
        else:
            st.subheader("推荐队友")
            render_team_role_plan(role_plan)
            recommendations = recommend_teammates_for_core(
                selected_names,
                characters,
                top_n=len(characters),
            )
            render_recommendation_groups(recommendations, top_n)


if __name__ == "__main__":
    main()
