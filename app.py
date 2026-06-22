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
    label_damage_profile,
    label_position,
    label_role,
    label_team_slot,
    load_characters,
    recommend_for_box,
    recommend_teammates_for_core,
    translate_reason,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "characters.json"

UI_TEXT = {
    "zh": {
        "page_title": "碧蓝档案推图配队推荐器",
        "subtitle": "选择一个或多个核心角色，查看适合普通推图的新手向队友推荐和规则解释。",
        "library_caption": "当前本地角色库共 {count} 名角色；名单来自 GameKee，结构化站位和技能资料来自 SchaleDB。",
        "language": "语言 / Language",
        "filters": "筛选",
        "select_core": "选择核心角色",
        "select_core_help": "可以选择 1 个或多个你想放进队伍的角色，系统会围绕这个组合推荐队友。",
        "top_n": "每组推荐数量",
        "my_box": "我的 Box",
        "box_toggle": "只推荐我拥有的角色",
        "import_box": "导入 Box JSON",
        "owned_characters": "已拥有角色",
        "owned_count": "已选择 {owned} / {total} 名角色",
        "export_box": "导出 my_box.json",
        "clear_box": "清空 Box",
        "import_success": "已导入 {count} 名拥有角色",
        "import_error": "导入失败：JSON 格式不正确",
        "select_at_least_one": "请先在侧栏选择至少一个核心角色。",
        "core_characters": "核心角色",
        "box_recommendations": "你的 Box 可用推荐",
        "box_empty": "先在侧栏“我的 Box”里选择你拥有的角色，再开启差异化推荐。",
        "missing_core": "这些核心角色不在你的 Box 中：{names}；这里仍会围绕它们推荐你已拥有的队友。",
        "no_owned_recs": "你的 Box 中暂时没有可推荐的队友。",
        "ideal_recs": "查看全角色理想推荐",
        "recommendations": "推荐队友",
        "role_plan_title": "队伍职责检查",
        "target_structure": "目标骨架",
        "covered": "已覆盖",
        "missing": "优先补位",
        "none": "暂无",
        "all_covered": "基础职责已覆盖，下面会继续按适配度推荐更多队友",
        "slot_badge": "补位：{slot}",
        "rank": "推荐 {rank}",
        "score": "适配 {score} 分",
        "overall_rating": "综合评分 {rating}",
        "reason_title": "推荐理由",
        "striker_title": "前排上场（Striker）",
        "striker_caption": "会占用 4 个上场学生位，通常承担输出、坦克、治疗或场上辅助职责。",
        "special_title": "后排支援（Special）",
        "special_caption": "位于 2 个支援学生位，通常提供治疗、增益、减益、召唤或功能支援。",
        "no_group_recs": "当前规则下这一组暂无推荐角色。",
        "unknown_position": "位置待补充",
        "missing_ideal_covered": "你的 Box 已覆盖当前理想推荐中的关键队友。",
        "missing_ideal_title": "缺少的理想队友",
        "box_substitutions": "Box 内替代建议",
        "missing_substitution": "缺少 **{missing}** 时，可以先用 **{alternative}**：{reason}",
        "selected_core_count": "已选择 {count} 个核心角色",
        "rating_none": "暂无评分",
        "ex_cost_missing": "待补充",
        "skill_summary": "技能摘要",
        "skill_note": "",
        "stats_role": "定位",
        "stats_position": "队伍位",
        "stats_battle_position": "战斗站位",
        "stats_attack": "攻击",
        "stats_armor": "护甲",
        "stats_ex_cost": "EX 费用",
        "stats_damage_profile": "出伤类型",
        "stats_rating": "GameKee 评分",
        "box_note": "由碧蓝档案配队推荐器导出，可重新导入到我的 Box。",
    },
    "en": {
        "page_title": "Blue Archive General Stage Team Recommender",
        "subtitle": "Select one or more core units to get beginner-friendly teammate recommendations for general stages.",
        "library_caption": "Local roster: {count} students. Names come from GameKee; structured positions and skill data come from SchaleDB.",
        "language": "Language / 语言",
        "filters": "Filters",
        "select_core": "Core units",
        "select_core_help": "Choose one or more units you want to build around. The app recommends teammates around that core.",
        "top_n": "Recommendations per group",
        "my_box": "My Box",
        "box_toggle": "Only recommend owned units",
        "import_box": "Import Box JSON",
        "owned_characters": "Owned units",
        "owned_count": "Selected {owned} / {total} units",
        "export_box": "Export my_box.json",
        "clear_box": "Clear Box",
        "import_success": "Imported {count} owned units",
        "import_error": "Import failed: invalid JSON",
        "select_at_least_one": "Please select at least one core unit in the sidebar.",
        "core_characters": "Core Units",
        "box_recommendations": "Recommendations From Your Box",
        "box_empty": "Select owned units in the sidebar's My Box section before enabling box-based recommendations.",
        "missing_core": "These core units are not in your Box: {names}. The app will still recommend owned teammates around them.",
        "no_owned_recs": "No usable recommendations were found in your Box yet.",
        "ideal_recs": "View ideal recommendations from all units",
        "recommendations": "Recommended Teammates",
        "role_plan_title": "Team Role Check",
        "target_structure": "Target structure",
        "covered": "Covered",
        "missing": "Priority gaps",
        "none": "None",
        "all_covered": "Core duties are covered; more teammates are ranked by synergy below.",
        "slot_badge": "Fills: {slot}",
        "rank": "Recommendation {rank}",
        "score": "Synergy {score}",
        "overall_rating": "Overall rating {rating}",
        "reason_title": "Why recommended",
        "striker_title": "Striker",
        "striker_caption": "Uses one of the 4 active field slots, usually for damage, tanking, healing, or field support.",
        "special_title": "Special",
        "special_caption": "Uses one of the 2 backline support slots, usually for healing, buffs, debuffs, summons, or utility.",
        "no_group_recs": "No recommendations in this group under the current rules.",
        "unknown_position": "Position TBD",
        "missing_ideal_covered": "Your Box already covers the key units from the current ideal recommendations.",
        "missing_ideal_title": "Missing ideal teammates",
        "box_substitutions": "Box substitutions",
        "missing_substitution": "If you are missing **{missing}**, you can use **{alternative}** for now: {reason}",
        "selected_core_count": "{count} core units selected",
        "rating_none": "No rating",
        "ex_cost_missing": "TBD",
        "skill_summary": "Skill Summary",
        "skill_note": "Skill text is currently shown in Chinese because the local dataset uses Chinese skill summaries.",
        "stats_role": "Role",
        "stats_position": "Squad slot",
        "stats_battle_position": "Battle position",
        "stats_attack": "Attack type",
        "stats_armor": "Armor type",
        "stats_ex_cost": "EX cost",
        "stats_damage_profile": "Damage profile",
        "stats_rating": "GameKee rating",
        "box_note": "Exported by the Blue Archive team recommender. You can import it back into My Box.",
    },
}


def ui(lang: str, key: str, **kwargs: object) -> str:
    """读取当前语言的界面文案。"""
    text = UI_TEXT.get(lang, UI_TEXT["zh"]).get(key, UI_TEXT["zh"].get(key, key))
    return text.format(**kwargs)


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


def build_box_json(owned_names: list[str], lang: str) -> bytes:
    """生成可下载的 Box JSON 文件内容。"""
    payload = {
        "owned_names": owned_names,
        "note": ui(lang, "box_note"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def render_tag_list(tags: list[str], lang: str) -> None:
    """用简单的胶囊标签展示角色技能关键词。"""
    tag_html = "".join(f"<span class='tag'>{tag}</span>" for tag in format_tags(tags, lang))
    st.markdown(f"<div class='tag-row'>{tag_html}</div>", unsafe_allow_html=True)


def format_gamekee_rating(character: dict, lang: str) -> str:
    """返回 GameKee 角色评测里的综合评分。"""
    rating = (character.get("ratings") or {}).get("gamekee_overall") or {}
    return rating.get("overall") or ui(lang, "rating_none")


def render_character_panel(character: dict, lang: str) -> None:
    """展示当前选择角色的核心信息。"""
    st.markdown(f"### {character['name']}")

    ex_cost = character.get("ex_cost") or ui(lang, "ex_cost_missing")
    stats = [
        (ui(lang, "stats_role"), label_role(character["role"], lang)),
        (ui(lang, "stats_position"), label_position(character["position"], lang)),
        (ui(lang, "stats_battle_position"), label_battle_position(character.get("battle_position", "unknown"), lang)),
        (ui(lang, "stats_attack"), label_attack_type(character["attack_type"], lang)),
        (ui(lang, "stats_armor"), label_armor_type(character["armor_type"], lang)),
        (ui(lang, "stats_ex_cost"), str(ex_cost)),
        (ui(lang, "stats_damage_profile"), label_damage_profile(character, lang)),
        (ui(lang, "stats_rating"), format_gamekee_rating(character, lang)),
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
    render_tag_list(character["tags"], lang)

    with st.expander(ui(lang, "skill_summary"), expanded=False):
        if ui(lang, "skill_note"):
            st.caption(ui(lang, "skill_note"))
        for skill_name, description in character["skills"].items():
            st.markdown(f"**{skill_name.upper()}**：{description}")


def render_core_character_panels(selected_characters: list[dict], lang: str) -> None:
    """展示一个或多个玩家想围绕配队的核心角色。"""
    if len(selected_characters) == 1:
        render_character_panel(selected_characters[0], lang)
        return

    st.caption(ui(lang, "selected_core_count", count=len(selected_characters)))
    for index, character in enumerate(selected_characters):
        with st.expander(character["name"], expanded=index == 0):
            render_character_panel(character, lang)


def render_team_role_plan(role_plan: dict, lang: str) -> None:
    """展示当前核心角色已经覆盖和仍需要补齐的队伍职责。"""
    separator = "、" if lang == "zh" else ", "
    colon = "：" if lang == "zh" else ": "
    target_labels = separator.join(label_team_slot(slot["role"], lang) for slot in role_plan["target"])
    covered_labels = separator.join(label_team_slot(slot["role"], lang) for slot in role_plan["covered"]) or ui(lang, "none")
    missing_labels = separator.join(label_team_slot(slot["role"], lang) for slot in role_plan["missing"])
    missing_text = missing_labels or ui(lang, "all_covered")

    st.markdown(
        f"""
        <div class="role-plan">
            <div class="role-plan-title">{ui(lang, "role_plan_title")}</div>
            <div>{ui(lang, "target_structure")}{colon}{target_labels}</div>
            <div>{ui(lang, "covered")}{colon}{covered_labels}</div>
            <div>{ui(lang, "missing")}{colon}{missing_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_recommendation_card(item: dict, rank: int, lang: str) -> None:
    """展示一个推荐队友卡片。"""
    character = item["character"]
    score = item["score"]
    reasons = item["reasons"]
    slot_badge = ""
    if item.get("slot_role") or item.get("slot_label"):
        slot_label = label_team_slot(item.get("slot_role", ""), lang) if item.get("slot_role") else item["slot_label"]
        slot_badge = f"<span class='slot-badge'>{ui(lang, 'slot_badge', slot=slot_label)}</span>"
    rank_row = f'<div class="rank-row"><span class="rank">{ui(lang, "rank", rank=rank)}</span>{slot_badge}</div>'
    ex_cost = character.get("ex_cost") or ui(lang, "ex_cost_missing")

    st.markdown(
        "\n".join(
            [
                '<section class="recommend-card">',
                '<div class="card-header">',
                "<div>",
                rank_row,
                f"<h3>{character['name']}</h3>",
                "</div>",
                f'<div class="score">{ui(lang, "score", score=score)}</div>',
                "</div>",
                '<div class="meta">',
                f"<span>{label_role(character['role'], lang)}</span>",
                f"<span>{label_position(character['position'], lang)}</span>",
                f"<span>{label_battle_position(character.get('battle_position', 'unknown'), lang)}</span>",
                f"<span>{label_attack_type(character['attack_type'], lang)}</span>",
                f"<span>EX {ex_cost}</span>",
                f"<span>{ui(lang, 'overall_rating', rating=format_gamekee_rating(character, lang))}</span>",
                "</div>",
                "</section>",
            ]
        ),
        unsafe_allow_html=True,
    )

    render_tag_list(character["tags"], lang)
    st.markdown(f"**{ui(lang, 'reason_title')}**")
    for reason in reasons[:5]:
        st.markdown(f"- {translate_reason(reason, lang)}")


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
    lang: str,
) -> None:
    """分前排上场位和后排支援位展示推荐结果。"""
    groups = split_recommendations_by_position(recommendations)
    group_configs = [
        ("striker", ui(lang, "striker_title"), ui(lang, "striker_caption")),
        ("special", ui(lang, "special_title"), ui(lang, "special_caption")),
    ]

    for group_key, title, caption in group_configs:
        st.markdown(f"<div class='group-title'>{title}</div>", unsafe_allow_html=True)
        st.caption(caption)
        items = groups.get(group_key, [])[:limit_per_group]
        if not items:
            st.info(ui(lang, "no_group_recs"))
            continue
        for index, item in enumerate(items, start=1):
            render_recommendation_card(item, index, lang)

    unknown_items = groups.get("unknown", [])[:limit_per_group]
    if unknown_items:
        st.markdown(f"<div class='group-title'>{ui(lang, 'unknown_position')}</div>", unsafe_allow_html=True)
        for index, item in enumerate(unknown_items, start=1):
            render_recommendation_card(item, index, lang)


def render_compact_grouped_list(recommendations: list[dict], lang: str) -> None:
    """在折叠区内用紧凑列表展示分组后的理想推荐。"""
    groups = split_recommendations_by_position(recommendations)
    for group_key, title in [
        ("striker", ui(lang, "striker_title")),
        ("special", ui(lang, "special_title")),
    ]:
        items = groups.get(group_key, [])
        if not items:
            continue
        st.markdown(f"**{title}**")
        for index, item in enumerate(items, start=1):
            character = item["character"]
            if lang == "en":
                detail = (
                    f"({label_role(character['role'], lang)}, "
                    f"{label_battle_position(character.get('battle_position', 'unknown'), lang)}, "
                    f"{ui(lang, 'overall_rating', rating=format_gamekee_rating(character, lang))}, "
                    f"{ui(lang, 'score', score=item['score'])})"
                )
            else:
                detail = (
                    f"（{label_role(character['role'], lang)}，"
                    f"{label_battle_position(character.get('battle_position', 'unknown'), lang)}，"
                    f"综合评分 {format_gamekee_rating(character, lang)}，"
                    f"{item['score']} 分）"
                )
            st.markdown(f"{index}. **{character['name']}** {detail}")


def render_missing_summary(box_result: dict, lang: str) -> None:
    """展示理想推荐里玩家当前缺少的角色。"""
    missing = box_result["missing"]
    substitutions = box_result["substitutions"]

    if not missing:
        st.success(ui(lang, "missing_ideal_covered"))
        return

    st.markdown(f"**{ui(lang, 'missing_ideal_title')}**")
    missing_names = []
    for item in missing:
        slot_text = ""
        if item.get("slot_role") or item.get("slot_label"):
            slot_label = label_team_slot(item.get("slot_role", ""), lang) if item.get("slot_role") else item["slot_label"]
            slot_text = f"{ui(lang, 'slot_badge', slot=slot_label)}, " if lang == "en" else f"补{slot_label}，"
        if lang == "en":
            missing_names.append(
                f"{item['character']['name']} ({slot_text}"
                f"{label_role(item['character']['role'], lang)}, {ui(lang, 'score', score=item['score'])})"
            )
        else:
            missing_names.append(
                f"{item['character']['name']}（"
                f"{slot_text}{label_role(item['character']['role'], lang)}，{item['score']} 分）"
            )
    st.markdown(("、" if lang == "zh" else "; ").join(missing_names))

    if substitutions:
        st.markdown(f"**{ui(lang, 'box_substitutions')}**")
        for item in substitutions:
            missing_character = item["missing"]["character"]
            alternative_character = item["alternative"]["character"]
            st.markdown(
                "- "
                + ui(
                    lang,
                    "missing_substitution",
                    missing=missing_character["name"],
                    alternative=alternative_character["name"],
                    reason=translate_reason(item["reason"], lang),
                )
            )


def main() -> None:
    st.set_page_config(
        page_title="Blue Archive Team Recommender / 碧蓝档案推图配队推荐器",
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

    with st.sidebar:
        language_choice = st.selectbox(
            "语言 / Language",
            ["中文", "English"],
            index=0,
        )
    lang = "en" if language_choice == "English" else "zh"

    st.markdown(f"<div class='app-title'>{ui(lang, 'page_title')}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='app-subtitle'>{ui(lang, 'subtitle')}</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        ui(lang, "library_caption", count=len(characters))
    )

    with st.sidebar:
        st.header(ui(lang, "filters"))
        if "selected_names" not in st.session_state:
            st.session_state["selected_names"] = [character_names[0]]
        else:
            st.session_state["selected_names"] = [
                name
                for name in st.session_state["selected_names"]
                if name in character_names
            ]

        selected_names = st.multiselect(
            ui(lang, "select_core"),
            character_names,
            key="selected_names",
            help=ui(lang, "select_core_help"),
        )
        top_n = st.slider(ui(lang, "top_n"), min_value=3, max_value=8, value=5)

        st.divider()
        st.header(ui(lang, "my_box"))
        use_box_mode = st.toggle(ui(lang, "box_toggle"), value=False)

        uploaded_box = st.file_uploader(ui(lang, "import_box"), type=["json"])
        if uploaded_box is not None:
            uploaded_bytes = uploaded_box.getvalue()
            signature = hashlib.sha256(uploaded_bytes).hexdigest()
            if st.session_state.get("box_import_signature") != signature:
                try:
                    imported_data = json.loads(uploaded_bytes.decode("utf-8"))
                    imported_names = normalize_box_names(imported_data, character_names)
                    st.session_state["owned_names"] = imported_names
                    st.session_state["box_import_signature"] = signature
                    st.success(ui(lang, "import_success", count=len(imported_names)))
                except json.JSONDecodeError:
                    st.error(ui(lang, "import_error"))

        owned_names = st.multiselect(
            ui(lang, "owned_characters"),
            character_names,
            key="owned_names",
        )
        st.caption(ui(lang, "owned_count", owned=len(owned_names), total=len(character_names)))
        st.download_button(
            ui(lang, "export_box"),
            data=build_box_json(owned_names, lang),
            file_name="my_box.json",
            mime="application/json",
            disabled=not owned_names,
        )
        st.button(ui(lang, "clear_box"), on_click=clear_owned_box, disabled=not owned_names)

    if not selected_names:
        st.info(ui(lang, "select_at_least_one"))
        return

    character_by_name = {character["name"]: character for character in characters}
    selected_characters = [character_by_name[name] for name in selected_names]
    role_plan = build_team_role_plan(selected_characters)

    left, right = st.columns([0.95, 1.35], gap="large")

    with left:
        st.subheader(ui(lang, "core_characters"))
        render_core_character_panels(selected_characters, lang)

    with right:
        if use_box_mode:
            st.subheader(ui(lang, "box_recommendations"))
            render_team_role_plan(role_plan, lang)
            owned_name_set = set(owned_names)
            if not owned_names:
                st.info(ui(lang, "box_empty"))
                return

            missing_core_names = [
                name for name in selected_names if name not in owned_name_set
            ]
            if missing_core_names:
                st.warning(
                    ui(
                        lang,
                        "missing_core",
                        names=("、" if lang == "zh" else ", ").join(missing_core_names),
                    )
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
                render_recommendation_groups(owned_recommendations, top_n, lang)
            else:
                st.warning(ui(lang, "no_owned_recs"))

            st.divider()
            render_missing_summary(box_result, lang)

            with st.expander(ui(lang, "ideal_recs"), expanded=False):
                all_recommendations = recommend_teammates_for_core(
                    selected_names,
                    characters,
                    top_n=len(characters),
                )
                render_compact_grouped_list(all_recommendations[: top_n * 2], lang)
        else:
            st.subheader(ui(lang, "recommendations"))
            render_team_role_plan(role_plan, lang)
            recommendations = recommend_teammates_for_core(
                selected_names,
                characters,
                top_n=len(characters),
            )
            render_recommendation_groups(recommendations, top_n, lang)


if __name__ == "__main__":
    main()
