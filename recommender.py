"""《碧蓝档案》新手配队推荐逻辑。

第一版 MVP 使用规则打分，而不是机器学习。
这样做的好处是：规则透明、容易解释，也方便新手理解为什么某些角色适合放在一起。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# 角色定位的中文显示名称。数据里保留英文 key，方便程序判断。
ROLE_LABELS = {
    "main_dps": "主输出",
    "sub_dps": "副输出",
    "support": "辅助",
    "healer": "治疗",
    "tank": "坦克",
}


POSITION_LABELS = {
    "striker": "Striker 前排上场",
    "special": "Special 后排支援",
    "unknown": "待补充",
}


BATTLE_POSITION_LABELS = {
    "front": "前排",
    "middle": "中排",
    "back": "后排",
    "unknown": "待补充",
}


ATTACK_TYPE_LABELS = {
    "explosive": "爆发",
    "piercing": "贯通",
    "mystic": "神秘",
    "sonic": "振动",
    "unknown": "待补充",
}


ARMOR_TYPE_LABELS = {
    "light": "轻装甲",
    "heavy": "重装甲",
    "special": "特殊装甲",
    "elastic": "弹力装甲",
    "composite": "复合装甲",
    "unknown": "待补充",
}


# 标签的中文说明，用于页面展示和推荐理由生成。
TAG_LABELS = {
    "atk_buff": "攻击提升",
    "crit_buff": "暴击提升",
    "defense_down": "防御降低",
    "attack_down": "攻击降低",
    "cost_recovery": "费用恢复",
    "cost_reduction": "费用降低",
    "aoe_damage": "范围伤害",
    "single_target_damage": "单体伤害",
    "shield": "护盾",
    "healing": "治疗",
    "crowd_control": "控制",
    "high_cost": "高费用",
    "fragile": "较脆",
    "burst_damage": "爆发输出",
    "low_cost": "低费用",
    "single_target_buff": "单体强化",
    "aoe_buff": "范围强化",
    "reposition": "位移调整",
    "self_healing": "自我回复",
    "frontline": "前排承伤",
    "taunt": "嘲讽",
    "damage": "输出",
    "support_utility": "辅助功能",
    "source_gamekee": "GameKee 数据",
}


SUPPORT_TAG_REASON = {
    "atk_buff": "能提供攻击力提升，让输出角色的伤害上限更高。",
    "crit_buff": "能强化暴击表现，适合搭配需要爆发窗口的输出角色。",
    "defense_down": "能降低敌方防御，让队伍整体输出更容易打满。",
    "attack_down": "能降低敌方攻击力，适合提高队伍在高压场景里的容错率。",
    "cost_recovery": "能改善费用循环，让高费用或频繁释放 EX 的角色更顺手。",
    "cost_reduction": "能降低 EX 费用压力，帮助核心技能更快进入循环。",
    "healing": "能提供治疗，提高脆皮或前排角色的容错率。",
    "shield": "能提供护盾，降低关键角色被击倒的风险。",
    "crowd_control": "能控制敌人，为输出角色争取更稳定的输出时间。",
    "support_utility": "能承担辅助功能，适合补足输出角色以外的队伍职责。",
}


# 新手向推荐先按“队伍职责”补齐一个基础骨架。
# 这里的“副 C”按半辅输出理解：最好既能给主 C 提供对口增益，
# 又能补一点输出、破防或清杂能力，而不是单纯塞第二个纯输出。
TEAM_SLOT_ORDER = ["tank", "main_dps", "sub_dps", "support", "healer"]
TEAM_SLOT_LABELS = {
    "tank": "坦克",
    "main_dps": "主 C",
    "sub_dps": "副 C",
    "support": "辅助",
    "healer": "治疗",
}
TEAM_SLOT_ACCEPTS = {
    "tank": {"tank"},
    "main_dps": {"main_dps", "sub_dps"},
    "support": {"support"},
    "healer": {"healer"},
}
TEAM_SLOT_HELP = {
    "tank": "吸收前排压力，让输出和辅助有更稳定的站场环境。",
    "main_dps": "提供队伍主要伤害来源，避免功能位齐全但伤害不足。",
    "sub_dps": "给主 C 提供对口增益，同时补一点输出、破防或清杂能力。",
    "support": "提供增益、减益或费用循环，让核心角色更容易打出价值。",
    "healer": "提供回复或容错，降低新手配队在高压关卡里的翻车率。",
}
ROLE_COMPLETENESS_BONUS = 4
SUB_DPS_ENABLER_TAGS = {
    "atk_buff",
    "crit_buff",
    "defense_down",
    "cost_recovery",
    "cost_reduction",
    "single_target_buff",
    "aoe_buff",
}
SUB_DPS_OUTPUT_TAGS = {
    "damage",
    "single_target_damage",
    "aoe_damage",
    "burst_damage",
    "defense_down",
}
ALLY_TARGET_PATTERNS = ("我方", "除自身外", "前锋学生", "后援学生", "召唤物")
SUSTAINED_DAMAGE_PATTERNS = (
    "普通攻击时",
    "自身攻击时",
    "每进行",
    "弹匣弹药耗尽",
    "立即换弹",
    "攻击速度增加",
    "开火间隔",
    "追加伤害",
)
SUSTAINED_EX_MODE_PATTERNS = (
    "强化：普通攻击",
    "普通攻击倍率",
    "全自动射击",
    "精密瞄准",
    "指定射击姿势",
    "无视每",
    "开火间隔",
)


def load_characters(json_path: str | Path) -> list[dict[str, Any]]:
    """从本地 JSON 文件读取角色数据。"""
    path = Path(json_path)
    with path.open("r", encoding="utf-8") as file:
        characters = json.load(file)

    # 简单校验必需字段。MVP 不做复杂 schema，只保证核心字段存在。
    required_fields = {
        "name",
        "role",
        "position",
        "attack_type",
        "armor_type",
        "ex_cost",
        "skills",
        "tags",
    }
    for character in characters:
        missing_fields = required_fields - set(character)
        if missing_fields:
            name = character.get("name", "未命名角色")
            raise ValueError(f"{name} 缺少字段: {', '.join(sorted(missing_fields))}")

    return characters


def find_character(characters: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """根据角色名称查找角色。"""
    for character in characters:
        if character["name"] == name:
            return character
    raise ValueError(f"找不到角色: {name}")


def find_characters(
    characters: list[dict[str, Any]],
    names: list[str],
) -> list[dict[str, Any]]:
    """根据多个角色名称查找角色，并保持用户选择顺序。"""
    return [find_character(characters, name) for name in names]


def get_skill_text(character: dict[str, Any], skill_name: str) -> str:
    """读取指定技能文本，缺失时返回空字符串。"""
    return str(character.get("skills", {}).get(skill_name, "") or "")


def get_all_skill_text(character: dict[str, Any]) -> str:
    """把角色全部技能文本合并，便于做规则判断。"""
    return " ".join(str(text) for text in character.get("skills", {}).values())


def contains_any(text: str, patterns: tuple[str, ...] | set[str]) -> bool:
    """判断文本是否包含任意一个关键词。"""
    return any(pattern in text for pattern in patterns)


def extract_durations(text: str) -> list[float]:
    """从技能文本中提取“持续 X 秒”的时间。"""
    return [float(value) for value in re.findall(r"持续(\d+(?:\.\d+)?)秒", text)]


def max_duration(text: str) -> float:
    """返回文本中最长持续时间，缺失时为 0。"""
    durations = extract_durations(text)
    return max(durations) if durations else 0


def extract_damage_multipliers(text: str) -> list[float]:
    """粗略提取“造成自身攻击力 X%”一类伤害倍率。"""
    multipliers = []
    for match in re.finditer(r"造成[^\n。；;]{0,100}?自身攻击力(\d+(?:\.\d+)?)%", text):
        multipliers.append(float(match.group(1)))
    return multipliers


def max_damage_multiplier(text: str) -> float:
    """返回文本中最高的攻击力伤害倍率。"""
    multipliers = extract_damage_multipliers(text)
    return max(multipliers) if multipliers else 0


def is_ally_effect_text(text: str) -> bool:
    """判断技能文本是否明显作用于我方队友，而不是纯自我强化。"""
    return contains_any(text, ALLY_TARGET_PATTERNS)


def ally_skill_texts(character: dict[str, Any]) -> list[str]:
    """返回所有作用于我方队友的技能文本片段。"""
    return [
        str(text)
        for text in character.get("skills", {}).values()
        if is_ally_effect_text(str(text))
    ]


def ally_text_has(character: dict[str, Any], *keywords: str) -> bool:
    """判断候选角色是否有作用于我方的指定关键词组合。"""
    return any(all(keyword in text for keyword in keywords) for text in ally_skill_texts(character))


def ally_text_max_duration(character: dict[str, Any], *keywords: str) -> float:
    """找到包含指定关键词的我方技能里最长的持续时间。"""
    durations = [
        max_duration(text)
        for text in ally_skill_texts(character)
        if all(keyword in text for keyword in keywords)
    ]
    return max(durations) if durations else 0


def classify_damage_profile(character: dict[str, Any]) -> dict[str, Any]:
    """根据技能文本判断输出核心更偏 EX 爆发还是普攻/小技能持续输出。"""
    if character.get("role") not in {"main_dps", "sub_dps"}:
        return {
            "style": "utility",
            "label": "功能位",
            "ex_score": 0,
            "sustained_score": 0,
            "reasons": ["非主要输出定位。"],
        }

    tags = set(character.get("tags", []))
    ex_cost = character.get("ex_cost") or 0
    ex_text = get_skill_text(character, "ex")
    normal_text = get_skill_text(character, "normal")
    passive_text = get_skill_text(character, "passive")
    sub_text = get_skill_text(character, "sub")
    non_ex_text = " ".join([normal_text, passive_text, sub_text])
    all_text = get_all_skill_text(character)
    ex_multiplier = max_damage_multiplier(ex_text)
    normal_multiplier = max_damage_multiplier(non_ex_text)

    ex_score = 0
    sustained_score = 0
    reasons: list[str] = []

    if "造成" in ex_text:
        ex_score += 1
    if ex_multiplier >= 700:
        ex_score += 3
        reasons.append(f"EX 技能最高倍率约 {ex_multiplier:g}%，有明显爆发伤害。")
    elif ex_multiplier >= 500:
        ex_score += 2
        reasons.append(f"EX 技能倍率约 {ex_multiplier:g}%，偏向用 EX 打关键伤害。")
    elif ex_multiplier >= 300:
        ex_score += 1

    if ex_cost >= 5:
        ex_score += 2
        reasons.append("EX 费用偏高，通常需要围绕关键释放窗口配队。")
    elif ex_cost <= 3:
        sustained_score += 1

    if "high_cost" in tags:
        ex_score += 1
    if "burst_damage" in tags:
        ex_score += 1
    if "EnhanceExDamageRate" in all_text or "EX技能类型伤害" in all_text:
        ex_score += 3
        reasons.append("技能文本里出现 EX 伤害强化，说明 EX 伤害权重较高。")

    if contains_any(non_ex_text, SUSTAINED_DAMAGE_PATTERNS):
        sustained_score += 3
        reasons.append("普通技能/子技能会围绕普攻、换弹、攻击速度或追加伤害持续触发。")
    if contains_any(ex_text, SUSTAINED_EX_MODE_PATTERNS):
        sustained_score += 3
        reasons.append("EX 技能更像启动普攻强化模式，而不是单次爆发。")
    if normal_multiplier >= 300:
        sustained_score += 2
        reasons.append(f"普通技能倍率约 {normal_multiplier:g}%，小技能出伤占比不低。")
    elif normal_multiplier >= 180:
        sustained_score += 1
    if "攻击速度增加" in all_text and is_ally_effect_text(all_text) is False:
        sustained_score += 1

    if sustained_score >= ex_score + 2:
        style = "sustained"
        label = "普攻/小技能持续输出型"
    elif ex_score >= sustained_score + 1:
        style = "ex_burst"
        label = "EX 爆发型"
    else:
        style = "mixed"
        label = "混合输出型"

    return {
        "style": style,
        "label": label,
        "ex_score": ex_score,
        "sustained_score": sustained_score,
        "reasons": reasons or ["技能文本里 EX 与持续输出倾向接近，暂按混合输出处理。"],
    }


def label_damage_profile(character: dict[str, Any]) -> str:
    """返回角色出伤类型的中文显示。"""
    profile = classify_damage_profile(character)
    return profile["label"]


def score_ex_burst_support(
    selected: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[int, list[str]]:
    """给 EX 爆发型主 C 匹配短窗口、费用和 EX 相关辅助。"""
    score = 0
    reasons: list[str] = []
    candidate_tags = set(candidate.get("tags", []))
    all_text = get_all_skill_text(candidate)

    if "cost_reduction" in candidate_tags or "CostChange减少" in all_text:
        score += 4
        reasons.append("所选主 C 偏 EX 爆发，候选角色能降低 EX 费用，能更快打出关键技能。")

    if "cost_recovery" in candidate_tags or "费用恢复力增加" in all_text:
        score += 2
        reasons.append("EX 爆发型主 C 吃技能循环，候选角色能提高费用恢复，帮助更快回到爆发窗口。")

    if ally_text_has(candidate, "攻击力增加"):
        duration = ally_text_max_duration(candidate, "攻击力增加")
        if duration and duration <= 20:
            score += 4
            reasons.append(f"候选角色有约 {duration:g} 秒攻击力增益，适合覆盖 EX 爆发窗口。")
        else:
            score += 2
            reasons.append("候选角色能给我方提供攻击力提升，可以抬高 EX 伤害上限。")

    if ally_text_has(candidate, "暴击值增加", "暴击伤害增加"):
        score += 3
        reasons.append("候选角色能同时提高暴击率和暴击伤害，适合在 EX 爆发前套给主 C。")
    elif ally_text_has(candidate, "暴击伤害增加"):
        score += 2
        reasons.append("候选角色能提高暴击伤害，适合配合高倍率 EX 打爆发。")

    if "EnhanceExDamageRate" in all_text or ("EX技能" in all_text and "伤害" in all_text and "增加" in all_text):
        score += 4
        reasons.append("候选角色技能文本带有 EX 伤害强化，能直接服务 EX 型主 C。")

    if "defense_down" in candidate_tags:
        score += 2
        reasons.append("候选角色能降低敌方防御，适合在 EX 爆发前铺垫。")

    if "shield" in candidate_tags and (
        {"cost_reduction", "crit_buff", "atk_buff"} & candidate_tags
    ):
        score += 1
        reasons.append("候选角色还带护盾或保护能力，可以让主 C 在爆发前后更稳定。")

    return score, reasons


def score_sustained_support(
    selected: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[int, list[str]]:
    """给普攻/小技能型主 C 匹配长时间暴击、攻速和持续增益。"""
    score = 0
    reasons: list[str] = []
    candidate_tags = set(candidate.get("tags", []))

    if ally_text_has(candidate, "攻击速度增加"):
        duration = ally_text_max_duration(candidate, "攻击速度增加")
        score += 4
        if duration:
            reasons.append(f"所选主 C 偏普攻/小技能输出，候选角色能提供约 {duration:g} 秒攻击速度提升，覆盖持续输出窗口。")
        else:
            reasons.append("所选主 C 偏普攻/小技能输出，候选角色能提供攻击速度提升，能增加持续出伤频率。")

    crit_window_duration = max(
        ally_text_max_duration(candidate, "暴击值增加", "暴击伤害增加"),
        ally_text_max_duration(candidate, "暴击伤害增加"),
    )
    if ally_text_has(candidate, "暴击值增加", "暴击伤害增加"):
        score += 4
        if crit_window_duration:
            reasons.append(f"候选角色能在约 {crit_window_duration:g} 秒内同时提高暴击率和暴击伤害，适合持续输出主 C 吃完整增益。")
        else:
            reasons.append("候选角色能同时提高暴击率和暴击伤害，适合普攻/小技能型主 C 持续输出。")
    elif ally_text_has(candidate, "暴击伤害增加"):
        score += 2
        reasons.append("候选角色能提供暴击伤害增益，适合本身攻击频率较高的持续输出角色。")

    if ally_text_has(candidate, "攻击力增加"):
        duration = ally_text_max_duration(candidate, "攻击力增加")
        if duration >= 25:
            score += 3
            reasons.append(f"候选角色有约 {duration:g} 秒攻击力增益，更适合覆盖普攻/小技能的持续输出时间。")
        else:
            score += 1

    if "defense_down" in candidate_tags and contains_any(
        get_skill_text(selected, "normal") + get_skill_text(selected, "sub"),
        SUSTAINED_DAMAGE_PATTERNS,
    ):
        score += 2
        reasons.append("所选主 C 的普通技能/子技能会持续出伤，防御降低能让这些多段伤害更稳定受益。")

    if "cost_reduction" in candidate_tags:
        score += 1
        reasons.append("候选角色能降低费用压力，但对持续输出主 C 来说优先级低于攻速和长时间暴击增益。")

    return score, reasons


def score_pair(
    selected: dict[str, Any], candidate: dict[str, Any]
) -> tuple[int, list[str]]:
    """计算“已选择角色”和“候选队友”的适配分数。

    返回值包含两部分：
    1. score：整数分数，越高代表越推荐。
    2. reasons：中文解释列表，用来告诉新手为什么这样配。
    """
    score = 0
    reasons: list[str] = []

    selected_tags = set(selected["tags"])
    candidate_tags = set(candidate["tags"])

    # 先分析主 C 的出伤方式，再匹配不同类型的辅助。
    if selected["role"] in {"main_dps", "sub_dps"}:
        damage_profile = classify_damage_profile(selected)
        if damage_profile["style"] == "ex_burst":
            profile_score, profile_reasons = score_ex_burst_support(selected, candidate)
            score += profile_score
            reasons.extend(profile_reasons)
        elif damage_profile["style"] == "sustained":
            profile_score, profile_reasons = score_sustained_support(selected, candidate)
            score += profile_score
            reasons.extend(profile_reasons)
        else:
            ex_score, ex_reasons = score_ex_burst_support(selected, candidate)
            sustained_score, sustained_reasons = score_sustained_support(selected, candidate)
            if ex_score >= sustained_score:
                score += ex_score
                reasons.extend(ex_reasons)
            else:
                score += sustained_score
                reasons.extend(sustained_reasons)

    # 规则 1：主输出很吃攻击力提升。
    if selected["role"] == "main_dps" and "atk_buff" in candidate_tags:
        score += 2
        reasons.append("所选角色是主输出，候选角色能提供攻击提升，可以直接放大核心伤害。")

    # 规则 1.1：完整名录里的很多角色还没有细分技能标签，因此先用职业做保守推荐。
    if selected["role"] == "main_dps" and candidate["role"] == "support":
        score += 1
        reasons.append("所选角色偏输出，候选角色是辅助定位，通常适合补足增益、减益或功能性。")

    if selected["role"] == "main_dps" and candidate["role"] == "healer":
        score += 1
        reasons.append("输出角色需要稳定站场，治疗定位可以提高队伍容错率。")

    if selected["role"] != "tank" and candidate["role"] == "tank":
        score += 1
        reasons.append("候选角色是坦克定位，可以承担前排压力，让其他角色更安全地输出或辅助。")

    if selected["role"] in {"support", "healer", "tank"} and candidate["role"] == "main_dps":
        score += 2
        reasons.append("所选角色偏功能位，候选角色是输出定位，可以补足队伍的伤害来源。")

    # 规则 2：主输出也常常需要暴击相关强化来提高爆发上限。
    if selected["role"] == "main_dps" and "crit_buff" in candidate_tags:
        score += 3
        reasons.append("所选角色是主输出，候选角色能提供暴击强化，适合配合爆发输出窗口。")

    # 规则 3：高费用角色需要费用恢复或费用降低来改善技能循环。
    if "high_cost" in selected_tags:
        if "cost_reduction" in candidate_tags:
            score += 3
            reasons.append("所选角色 EX 费用较高，候选角色能降低费用压力，让关键技能更容易释放。")
        if "cost_recovery" in candidate_tags:
            score += 3
            reasons.append("所选角色 EX 费用较高，候选角色能提高费用恢复，帮助队伍更快进入技能循环。")

    # 规则 4：较脆角色需要治疗或护盾提高容错率。
    if "fragile" in selected_tags:
        if "healing" in candidate_tags:
            score += 2
            reasons.append("所选角色生存压力较大，候选角色能治疗队友，提高站场稳定性。")
        if "shield" in candidate_tags:
            score += 2
            reasons.append("所选角色生存压力较大，候选角色能提供护盾，降低被击倒风险。")

    # 规则 5：爆发输出配合防御降低，能让短时间伤害更集中。
    if "burst_damage" in selected_tags and "defense_down" in candidate_tags:
        score += 2
        reasons.append("所选角色有爆发输出标签，候选角色能降低敌方防御，适合爆发前铺垫。")

    # 规则 6：单体输出和防御降低也很适合打 Boss。
    if "single_target_damage" in selected_tags and "defense_down" in candidate_tags:
        score += 1
        reasons.append("所选角色偏单体输出，候选角色的防御降低能帮助打 Boss 或精英敌人。")

    # 规则 8：Striker 输出搭配 Special 辅助，队伍位置更自然。
    if selected["position"] == "striker" and candidate["position"] == "special":
        if candidate["role"] in {"support", "healer"}:
            score += 1
            reasons.append("候选角色位于 Special 位，不会占用前排输出位置，适合作为后排辅助。")

    # 规则 9：如果两个角色都是高费用，技能循环可能变慢。
    if "high_cost" in selected_tags and "high_cost" in candidate_tags:
        score -= 1
        reasons.append("两名角色都偏高费用，实际组队时需要注意 EX 技能循环。")

    # 规则 10：非辅助角色定位重复时轻微扣分，避免队伍功能过度重叠。
    if selected["role"] == candidate["role"] and candidate["role"] != "support":
        score -= 1
        role_label = ROLE_LABELS.get(candidate["role"], candidate["role"])
        reasons.append(f"两名角色都属于{role_label}，功能有一定重叠，因此略微扣分。")

    # 即使某些辅助标签没有触发加分，也补充自然语言解释，帮助新手读懂技能价值。
    for tag, reason in SUPPORT_TAG_REASON.items():
        if tag in candidate_tags and reason not in reasons:
            reasons.append(reason)

    if not reasons:
        reasons.append("两名角色没有明显冲突，但当前规则没有发现特别强的技能联动。")

    return score, reasons


def normalize_selected_names(selected_names: str | list[str]) -> list[str]:
    """把单个角色名或多个角色名统一整理成列表。"""
    if isinstance(selected_names, str):
        return [selected_names]
    return list(dict.fromkeys(selected_names))


def build_core_reasons(
    selected_characters: list[dict[str, Any]],
    candidate: dict[str, Any],
) -> tuple[int, list[str]]:
    """计算候选角色与多个核心角色的总分和合并解释。

    多选时，每个候选角色会分别和所有核心角色打分。
    分数会相加；如果它能同时服务多个核心角色，会得到少量额外奖励。
    """
    total_score = 0
    positive_match_count = 0
    reasons: list[str] = []
    fallback_reasons: list[str] = []

    for selected in selected_characters:
        pair_score, pair_reasons = score_pair(selected, candidate)
        total_score += pair_score

        if pair_score > 0:
            positive_match_count += 1
            for reason in pair_reasons[:2]:
                reasons.append(f"与 **{selected['name']}**：{reason}")
        elif not fallback_reasons and pair_reasons:
            fallback_reasons.append(f"与 **{selected['name']}**：{pair_reasons[0]}")

    if len(selected_characters) > 1 and positive_match_count >= 2:
        total_score += positive_match_count
        reasons.insert(
            0,
            f"候选角色能同时适配 {positive_match_count} 个核心角色，适合放进这个组合里补功能。",
        )

    # 避免同一条通用辅助说明重复刷屏。
    deduped_reasons = list(dict.fromkeys(reasons))
    if not deduped_reasons:
        deduped_reasons = fallback_reasons or ["候选角色与当前核心角色组合没有明显冲突。"]

    return total_score, deduped_reasons


def find_main_dps_context(
    team_context: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """从当前已确定队伍里找出需要被服务的主 C。"""
    return [
        character
        for character in team_context
        if character.get("role") in {"main_dps", "sub_dps"}
    ]


def score_sub_dps_fit(
    candidate: dict[str, Any],
    team_context: list[dict[str, Any]],
) -> int:
    """判断候选角色是否适合当“半辅输出”副 C。

    副 C 不只是第二个输出，而是最好能服务主 C：
    攻击/暴击增益、防御降低、费用循环等算“对口增益”；
    自身输出、单体/范围伤害或破防算“第二输出能力”。
    """
    candidate_tags = set(candidate.get("tags", []))
    main_dps_characters = find_main_dps_context(team_context)
    candidate_role = candidate.get("role")

    if candidate_role == "sub_dps":
        return 8
    if candidate_role not in {"main_dps", "support"}:
        return 0

    has_enabler = bool(candidate_tags & SUB_DPS_ENABLER_TAGS)
    has_output = (
        candidate_role == "main_dps"
        or bool(candidate_tags & SUB_DPS_OUTPUT_TAGS)
    )
    if not has_enabler or not has_output:
        return 0

    score = 2
    if candidate_role == "support":
        score += 2
    if candidate_role == "main_dps":
        score += 1

    for main_dps in main_dps_characters:
        main_tags = set(main_dps.get("tags", []))
        if "atk_buff" in candidate_tags:
            score += 2
        if "crit_buff" in candidate_tags:
            score += 2
        if "defense_down" in candidate_tags and (
            main_tags & {"burst_damage", "single_target_damage"}
        ):
            score += 2
        if "high_cost" in main_tags and (
            candidate_tags & {"cost_recovery", "cost_reduction"}
        ):
            score += 2

    return score


def candidate_fits_team_slot(
    candidate: dict[str, Any],
    slot_role: str,
    team_context: list[dict[str, Any]] | None = None,
) -> bool:
    """判断候选角色是否能填补某个队伍职责。"""
    if slot_role == "sub_dps":
        return score_sub_dps_fit(candidate, team_context or []) > 0

    return candidate.get("role") in TEAM_SLOT_ACCEPTS.get(slot_role, set())


def build_team_role_plan(selected_characters: list[dict[str, Any]]) -> dict[str, Any]:
    """根据已选择角色，判断基础队伍骨架还缺哪些职责。

    MVP 的目标不是还原所有高难轴，而是给新手一个稳定的默认思路：
    队伍里尽量有坦克、主 C、副 C、辅助、治疗。玩家已经选择的角色会先占位，
    剩下的缺口会成为推荐页优先补齐的职责。
    """
    selected_roles = [character.get("role") for character in selected_characters]
    primary_main_dps = next(
        (
            character
            for character in selected_characters
            if character.get("role") in {"main_dps", "sub_dps"}
        ),
        None,
    )
    sub_dps_covered = "sub_dps" in selected_roles
    if primary_main_dps:
        sub_dps_covered = sub_dps_covered or any(
            character is not primary_main_dps
            and candidate_fits_team_slot(character, "sub_dps", [primary_main_dps])
            for character in selected_characters
        )

    covered_slots = {
        "tank": "tank" in selected_roles,
        "main_dps": "main_dps" in selected_roles,
        "sub_dps": sub_dps_covered,
        "support": "support" in selected_roles,
        "healer": "healer" in selected_roles,
    }

    covered = [
        {
            "role": slot_role,
            "label": TEAM_SLOT_LABELS[slot_role],
            "help": TEAM_SLOT_HELP[slot_role],
        }
        for slot_role in TEAM_SLOT_ORDER
        if covered_slots[slot_role]
    ]
    missing = [
        {
            "role": slot_role,
            "label": TEAM_SLOT_LABELS[slot_role],
            "help": TEAM_SLOT_HELP[slot_role],
        }
        for slot_role in TEAM_SLOT_ORDER
        if not covered_slots[slot_role]
    ]

    return {
        "target": [
            {
                "role": slot_role,
                "label": TEAM_SLOT_LABELS[slot_role],
                "help": TEAM_SLOT_HELP[slot_role],
            }
            for slot_role in TEAM_SLOT_ORDER
        ],
        "covered": covered,
        "missing": missing,
    }


def describe_sub_dps_value(
    candidate: dict[str, Any],
    team_context: list[dict[str, Any]],
) -> str:
    """说明副 C 候选的对口增益和补输出能力。"""
    candidate_tags = set(candidate.get("tags", []))
    enabler_labels = format_tags(sorted(candidate_tags & SUB_DPS_ENABLER_TAGS))[:3]
    output_labels = format_tags(sorted(candidate_tags & SUB_DPS_OUTPUT_TAGS))[:3]
    main_dps_names = [
        character["name"] for character in find_main_dps_context(team_context)
    ]

    target_text = (
        f"围绕 {'、'.join(main_dps_names)}"
        if main_dps_names
        else "围绕主 C"
    )
    enabler_text = "、".join(enabler_labels) if enabler_labels else "进攻辅助"

    if candidate.get("role") == "main_dps":
        output_text = "自身也是输出定位"
    elif output_labels:
        output_text = f"还带有{'、'.join(output_labels)}能力"
    else:
        output_text = "还能补一点输出或破防职责"

    return (
        f"队伍当前缺少“副 C”位；这里按半辅输出处理，{candidate['name']}适合"
        f"{target_text}提供{enabler_text}，并且{output_text}。"
    )


def explain_team_slot_pick(
    candidate: dict[str, Any],
    slot: dict[str, str],
    team_context: list[dict[str, Any]] | None = None,
) -> str:
    """生成“为什么这个角色能补这个职责”的说明。"""
    slot_role = slot["role"]
    slot_label = slot["label"]
    base_reason = TEAM_SLOT_HELP[slot_role]

    if slot_role == "sub_dps":
        return describe_sub_dps_value(candidate, team_context or [])

    return f"队伍当前缺少“{slot_label}”位，候选角色可以补齐这个关键职责：{base_reason}"


def recommendation_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    """推荐结果排序：分数优先，其次低费用角色更适合新手循环。"""
    return (
        item["score"],
        -(item["character"].get("ex_cost") or 0),
        item["character"]["name"],
    )


def slot_candidate_sort_key(
    item: dict[str, Any],
    slot_role: str,
    team_context: list[dict[str, Any]],
) -> tuple[int, int, int, str]:
    """某个职责缺口内部的排序。

    副 C 会额外看半辅输出适配度，避免纯输出角色挤掉更适合服务主 C 的角色。
    """
    candidate = item["character"]
    role_fit_score = 0
    if slot_role == "sub_dps":
        role_fit_score = score_sub_dps_fit(candidate, team_context)

    return (
        role_fit_score,
        item["score"],
        -(candidate.get("ex_cost") or 0),
        candidate["name"],
    )


def apply_team_role_priorities(
    selected_characters: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """把缺失职责的最佳候选提前，保证推荐结果先补队伍骨架。"""
    role_plan = build_team_role_plan(selected_characters)
    missing_slots = role_plan["missing"]
    if not missing_slots:
        return sorted(recommendations, key=recommendation_sort_key, reverse=True)

    sorted_recommendations = sorted(
        recommendations,
        key=recommendation_sort_key,
        reverse=True,
    )
    prioritized: list[dict[str, Any]] = []
    used_names: set[str] = set()
    team_context = selected_characters.copy()

    for slot in missing_slots:
        slot_role = slot["role"]
        eligible_items = [
            item
            for item in sorted_recommendations
            if item["character"]["name"] not in used_names
            and candidate_fits_team_slot(item["character"], slot_role, team_context)
        ]
        if not eligible_items:
            continue

        best_item = sorted(
            eligible_items,
            key=lambda item: slot_candidate_sort_key(item, slot_role, team_context),
            reverse=True,
        )[0]
        candidate = best_item["character"]
        slot_reason = explain_team_slot_pick(candidate, slot, team_context)
        role_fit_bonus = 0
        if slot_role == "sub_dps":
            role_fit_bonus = min(score_sub_dps_fit(candidate, team_context), 4)
        prioritized.append(
            {
                **best_item,
                "score": best_item["score"] + ROLE_COMPLETENESS_BONUS + role_fit_bonus,
                "slot_role": slot_role,
                "slot_label": slot["label"],
                "reasons": [slot_reason, *best_item["reasons"]],
            }
        )
        used_names.add(candidate["name"])
        team_context.append(candidate)

    remaining = [
        item
        for item in sorted_recommendations
        if item["character"]["name"] not in used_names
    ]
    return prioritized + remaining


def recommend_teammates_for_core(
    selected_names: list[str],
    characters: list[dict[str, Any]],
    top_n: int = 5,
    allowed_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    """围绕多个核心角色推荐队友。

    selected_names 是玩家想优先放进队伍的角色列表。
    候选队友不会包含这些核心角色本身。
    """
    selected_names = normalize_selected_names(selected_names)
    if not selected_names:
        return []

    selected_characters = find_characters(characters, selected_names)
    selected_name_set = set(selected_names)
    recommendations: list[dict[str, Any]] = []

    for candidate in characters:
        if candidate["name"] in selected_name_set:
            continue
        if allowed_names is not None and candidate["name"] not in allowed_names:
            continue

        score, reasons = build_core_reasons(selected_characters, candidate)
        recommendations.append(
            {
                "character": candidate,
                "score": score,
                "reasons": reasons,
            }
        )

    recommendations = apply_team_role_priorities(
        selected_characters,
        recommendations,
    )

    return recommendations[:top_n]


def recommend_teammates(
    selected_name: str,
    characters: list[dict[str, Any]],
    top_n: int = 5,
    allowed_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    """为指定角色推荐分数最高的队友。

    allowed_names 用于“我的 Box”模式：传入玩家拥有角色集合后，
    推荐结果只会从这些角色里产生。
    """
    return recommend_teammates_for_core(
        [selected_name],
        characters,
        top_n=top_n,
        allowed_names=allowed_names,
    )


def recommend_for_box(
    selected_names: str | list[str],
    characters: list[dict[str, Any]],
    owned_names: set[str],
    top_n: int = 5,
) -> dict[str, Any]:
    """同时生成理想推荐、Box 内推荐和缺失替代说明。"""
    normalized_selected_names = normalize_selected_names(selected_names)
    all_recommendations = recommend_teammates_for_core(
        normalized_selected_names,
        characters,
        top_n=len(characters),
    )
    ideal_recommendations = all_recommendations[:top_n]
    owned_recommendations = [
        item
        for item in all_recommendations
        if item["character"]["name"] in owned_names
    ][:top_n]
    missing_ideal = [
        item
        for item in ideal_recommendations
        if item["character"]["name"] not in owned_names
    ]

    substitutions = []
    used_alternatives: set[str] = set()
    for missing in missing_ideal:
        alternative = find_box_alternative(
            missing,
            owned_recommendations,
            used_alternatives,
        )
        if alternative:
            used_alternatives.add(alternative["character"]["name"])
            substitutions.append(
                {
                    "missing": missing,
                    "alternative": alternative,
                    "reason": explain_box_alternative(missing, alternative),
                }
            )

    return {
        "ideal": ideal_recommendations,
        "owned": owned_recommendations,
        "missing": missing_ideal,
        "substitutions": substitutions,
    }


def find_box_alternative(
    missing: dict[str, Any],
    owned_recommendations: list[dict[str, Any]],
    used_alternatives: set[str],
) -> dict[str, Any] | None:
    """为缺少的理想队友寻找一个 Box 内替代角色。"""
    missing_character = missing["character"]
    missing_tags = set(missing_character.get("tags", []))

    # 优先找定位相同或标签有交集的角色，这样替代理由更自然。
    for item in owned_recommendations:
        candidate = item["character"]
        if candidate["name"] in used_alternatives:
            continue
        missing_slot_role = missing.get("slot_role")
        if missing_slot_role and candidate_fits_team_slot(candidate, missing_slot_role):
            return item
        candidate_tags = set(candidate.get("tags", []))
        same_role = candidate["role"] == missing_character["role"]
        has_tag_overlap = bool(missing_tags & candidate_tags)
        if same_role or has_tag_overlap:
            return item

    for item in owned_recommendations:
        if item["character"]["name"] not in used_alternatives:
            return item

    return None


def explain_box_alternative(
    missing: dict[str, Any],
    alternative: dict[str, Any],
) -> str:
    """生成“缺少某角色时，为什么可以先用另一个角色”的解释。"""
    missing_character = missing["character"]
    alternative_character = alternative["character"]
    missing_tags = set(missing_character.get("tags", []))
    alternative_tags = set(alternative_character.get("tags", []))
    shared_tags = missing_tags & alternative_tags

    missing_slot_role = missing.get("slot_role")
    if missing_slot_role and candidate_fits_team_slot(alternative_character, missing_slot_role):
        slot_label = TEAM_SLOT_LABELS.get(missing_slot_role, "对应")
        return f"它同样可以承担{slot_label}职责，可以先补齐队伍骨架。"

    if alternative_character["role"] == missing_character["role"]:
        role_label = label_role(alternative_character["role"])
        return f"两者同属{role_label}定位，可以先承担相近的队伍职责。"

    if shared_tags:
        tag_labels = "、".join(format_tags(sorted(shared_tags))[:3])
        return f"两者都带有{tag_labels}标签，可以先覆盖一部分关键功能。"

    return "这是你当前 Box 中综合分数较高的可用队友，适合先作为过渡选择。"


def format_tags(tags: list[str]) -> list[str]:
    """把内部标签 key 转成中文标签。"""
    return [TAG_LABELS.get(tag, tag) for tag in tags]


def label_role(role: str) -> str:
    """返回角色定位的中文显示。"""
    return ROLE_LABELS.get(role, role)


def label_position(position: str) -> str:
    """返回队伍位置的显示名称。"""
    return POSITION_LABELS.get(position, position)


def label_battle_position(battle_position: str) -> str:
    """返回战斗站位的中文显示。"""
    return BATTLE_POSITION_LABELS.get(battle_position, battle_position)


def label_attack_type(attack_type: str) -> str:
    """返回攻击类型的中文显示。"""
    return ATTACK_TYPE_LABELS.get(attack_type, attack_type)


def label_armor_type(armor_type: str) -> str:
    """返回护甲类型的中文显示。"""
    return ARMOR_TYPE_LABELS.get(armor_type, armor_type)
