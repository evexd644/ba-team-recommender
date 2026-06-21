"""从 GameKee 名录和 SchaleDB 资料生成本地角色数据。

这个脚本用于 MVP 阶段的“半自动更新”：
1. 从 GameKee 的《碧蓝档案》图鉴接口读取当前角色列表。
2. 从 SchaleDB 的结构化数据读取站位、攻击类型、护甲、EX 费用和技能文本。
3. 合并两个来源，并自动推断推荐算法需要用到的技能标签。

说明：
GameKee 是本项目的完整名单来源；SchaleDB 提供更适合程序读取的结构化角色数据。
如果两个来源的译名不同，会通过 SCHALE_ALIASES 做名称对齐。
"""

from __future__ import annotations

import html
import json
import re
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_DIR / "data" / "characters.json"
GAMEKEE_API_URL = "https://www.gamekee.com/v1/entry/tj-list"
GAMEKEE_STUDENT_PAGE = "https://www.gamekee.com/ba/second/23941"
SCHALEDB_STUDENTS_URL = "https://schaledb.com/data/zh/students.min.json"
SCHALEDB_STUDENT_PAGE = "https://schaledb.com/student"


GAMEKEE_ROLE_MAP = {
    "输出": "main_dps",
    "辅助": "support",
    "治疗": "healer",
    "坦克": "tank",
    "T.S": "support",
}


SCHALE_ROLE_MAP = {
    "DamageDealer": "main_dps",
    "Supporter": "support",
    "Healer": "healer",
    "Tanker": "tank",
    "Vehicle": "support",
}


SQUAD_TYPE_MAP = {
    "Main": "striker",
    "Support": "special",
}


BATTLE_POSITION_MAP = {
    "Front": "front",
    "Middle": "middle",
    "Back": "back",
}


ATTACK_TYPE_MAP = {
    "Explosion": "explosive",
    "Pierce": "piercing",
    "Mystic": "mystic",
    "Sonic": "sonic",
}


ARMOR_TYPE_MAP = {
    "LightArmor": "light",
    "HeavyArmor": "heavy",
    "Unarmed": "special",
    "ElasticArmor": "elastic",
    "CompositeArmor": "composite",
}


ROLE_TAGS = {
    "main_dps": ["damage"],
    "support": ["support_utility"],
    "healer": ["healing"],
    "tank": ["frontline"],
}


SKILL_KEY_LABELS = {
    "Ex": "ex",
    "Public": "normal",
    "Passive": "passive",
    "ExtraPassive": "sub",
}


STAT_LABELS = {
    "ATK": "攻击力",
    "DEF": "防御力",
    "HIT": "命中值",
    "Dodge": "回避值",
    "CriticalChance": "暴击值",
    "CriticalDamage": "暴击伤害",
    "CostRegen": "费用恢复力",
    "HealPower": "治愈力",
    "AttackSpeed": "攻击速度",
    "MaxHP": "最大生命值",
    "OppressionPower": "压制力",
    "OppressionResist": "压制抵抗",
}


# GameKee 与 SchaleDB 的简中译名有少量差异。值可以是 SchaleDB 名称，
# 也可以用 path: 前缀指定 SchaleDB 的 PathName，适合区分同名不同形态。
SCHALE_ALIASES = {
    "朱莉": "茱莉",
    "绘梨香": "绘里香",
    "濑名（私服）": "濑名（便服）",
    "淳子": "纯子",
    "淳子（正月）": "纯子（正月）",
    "朱莉（打工）": "茱莉（打工）",
    "梅露": "芽瑠",
    "绮良良": "绮罗罗",
    "优香（体操服）": "优香（运动服）",
    "妮露": "尼露",
    "妮露（兔女郎）": "尼露（兔女郎）",
    "妮露（制服）": "尼露（制服）",
    "朱音": "茜",
    "朱音（兔女郎）": "茜（兔女郎）",
    "朱音（制服）": "茜（制服）",
    "柯伊": "凯伊",
    "晴奈（体操服）": "晴奈（运动服）",
    "真纪（野营）": "真纪（露营）",
    "晴（野营）": "晴（露营）",
    "小玉（野营）": "小玉（露营）",
    "莱伊": "丽",
    "莲见（体操服）": "莲见（运动服）",
    "玛丽（体操服）": "玛丽（运动服）",
    "芹娜（圣诞）": "芹娜（圣诞节）",
    "花绘": "花江",
    "花绘（圣诞）": "花江（圣诞节）",
    "星野（临战·防御型）": "path:hoshino_battle_tank",
    "星野（临战·攻击型）": "path:hoshino_battle_dealer",
    "白子*恐怖": "白子＊恐怖",
    "妮娅": "尼娅",
    "紫": "紫草",
    "紫（泳装）": "紫草（泳装）",
    "南": "弥奈",
    "纱绫（私服）": "纱绫（便服）",
    "巴": "智惠",
    "巴（旗袍）": "智惠（旗袍）",
    "玛丽娜": "玛利娜",
    "玛丽娜（旗袍）": "玛利娜（旗袍）",
    "实梨": "实里",
    "康娜": "环奈",
    "康娜（泳装）": "环奈（泳装）",
    "鹿江": "庚",
    "蕾娜": "丽奈",
}


# 旧版示例数据中用过的名称。重新生成时只用它们保留人工整理的标签。
CURATED_OVERRIDE_ALIASES = {
    "芹娜": "芹奈",
    "星野（泳装）": "水着星野",
}


def fetch_json(url: str, headers: dict[str, str], timeout: int = 30) -> Any:
    """请求 JSON 数据并返回 Python 对象。"""
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_gamekee_roster() -> list[dict[str, Any]]:
    """请求 GameKee 图鉴列表接口。"""
    payload = fetch_json(
        GAMEKEE_API_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "game-alias": "ba",
            "Lang": "zh-cn",
        },
    )

    if payload.get("code") != 0:
        raise RuntimeError(f"GameKee 接口返回异常: {payload}")

    return [row["ba"] for row in payload["data"] if row.get("ba")]


def fetch_schaledb_students() -> list[dict[str, Any]]:
    """请求 SchaleDB 的结构化学生数据。"""
    payload = fetch_json(
        SCHALEDB_STUDENTS_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": SCHALEDB_STUDENT_PAGE,
            "Accept": "application/json",
        },
    )
    if isinstance(payload, dict):
        return list(payload.values())
    return payload


def is_real_student(row: dict[str, Any]) -> bool:
    """过滤模板、测试和占位符条目。"""
    name = (row.get("name") or "").strip()
    role_name = row.get("zy") or ""
    if not name:
        return False
    blocked_words = ["模板", "模版", "测试"]
    if any(word in name for word in blocked_words):
        return False
    if "占位符" in role_name:
        return False
    return True


def normalize_name(name: str) -> str:
    """把角色名标准化，减少括号、空格、星号等写法差异。"""
    replacements = {
        "(": "（",
        ")": "）",
        " ": "",
        "　": "",
        "·": "",
        "・": "",
        "*": "＊",
        "★": "",
        "圣诞节": "圣诞",
        "便服": "私服",
        "运动服": "体操服",
        "露营": "野营",
    }
    normalized = name.strip()
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized


def build_schale_indexes(students: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """构建 SchaleDB 角色索引，便于按名称或 PathName 查找。"""
    by_name: dict[str, dict[str, Any]] = {}
    by_path: dict[str, dict[str, Any]] = {}

    for student in students:
        name_key = normalize_name(student["Name"])
        # 星野临战有两个同名形态，不能只靠名称索引覆盖。
        if name_key not in by_name:
            by_name[name_key] = student
        by_path[student["PathName"]] = student

    return {"by_name": by_name, "by_path": by_path}


def find_schale_student(
    gamekee_name: str,
    indexes: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    """用 GameKee 名称在 SchaleDB 中寻找同一个角色。"""
    alias = SCHALE_ALIASES.get(gamekee_name) or SCHALE_ALIASES.get(
        normalize_name(gamekee_name)
    )
    if alias and alias.startswith("path:"):
        path_name = alias.removeprefix("path:")
        return indexes["by_path"].get(path_name), f"alias:{alias}"

    lookup_name = alias or gamekee_name
    student = indexes["by_name"].get(normalize_name(lookup_name))
    if student:
        return student, "alias" if alias else "name"

    return None, "missing"


def load_existing_overrides() -> dict[str, dict[str, Any]]:
    """读取已有 characters.json，用作人工整理标签的覆盖层。"""
    if not DATA_PATH.exists():
        return {}

    with DATA_PATH.open("r", encoding="utf-8") as file:
        characters = json.load(file)

    return {character["name"]: character for character in characters}


def first_ex_cost(student: dict[str, Any] | None) -> int:
    """读取 EX 技能 1 级费用；没有资料时返回 0。"""
    if not student:
        return 0
    cost_values = (
        student.get("Skills", {})
        .get("Ex", {})
        .get("Cost", [])
    )
    if not cost_values:
        return 0
    return int(cost_values[0])


def flatten_numbers(value: Any) -> list[float]:
    """把效果数值展开成一维数字列表，用于判断增益或减益。"""
    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, list):
        numbers: list[float] = []
        for item in value:
            numbers.extend(flatten_numbers(item))
        return numbers
    return []


def is_negative_effect(effect: dict[str, Any]) -> bool:
    """判断一个技能效果是否偏负面，例如降低防御或降低费用。"""
    numbers = flatten_numbers(effect.get("Value")) + flatten_numbers(effect.get("Scale"))
    return bool(numbers) and any(number < 0 for number in numbers)


def target_has(effect: dict[str, Any], keyword: str) -> bool:
    """检查技能效果目标里是否包含 Ally、Enemy、Self 等关键词。"""
    target = effect.get("Target")
    if isinstance(target, str):
        return keyword in target
    if isinstance(target, list):
        return any(keyword in str(item) for item in target)
    return False


def is_ally_effect(effect: dict[str, Any]) -> bool:
    """判断技能效果是否能作用到队友，而不是只作用于自身。"""
    return target_has(effect, "Ally")


def is_enemy_effect(effect: dict[str, Any]) -> bool:
    """判断技能效果是否作用于敌方。"""
    return target_has(effect, "Enemy")


def collect_skill_effects(student: dict[str, Any]) -> list[tuple[str, dict[str, Any], str]]:
    """收集主要技能效果，附带技能键和原始描述。"""
    effects: list[tuple[str, dict[str, Any], str]] = []
    for skill_key in SKILL_KEY_LABELS:
        skill = student.get("Skills", {}).get(skill_key)
        if not isinstance(skill, dict):
            continue
        desc = skill.get("Desc") or ""
        for effect in skill.get("Effects", []) or []:
            effects.append((skill_key, effect, desc))
    return effects


def infer_tags(student: dict[str, Any], role: str, ex_cost: int) -> list[str]:
    """根据 SchaleDB 技能效果自动推断推荐系统需要的标签。"""
    tags = set(ROLE_TAGS.get(role, ["support_utility"]))

    if ex_cost >= 5:
        tags.add("high_cost")
    elif 0 < ex_cost <= 2:
        tags.add("low_cost")

    skills = student.get("Skills", {})
    ex_skill = skills.get("Ex", {})
    ex_desc = ex_skill.get("Desc") or ""
    ex_effects = ex_skill.get("Effects", []) or []
    has_ex_damage = any(effect.get("Type") == "Damage" for effect in ex_effects)

    if has_ex_damage:
        if (
            ex_skill.get("Radius")
            or "范围" in ex_desc
            or "圆形" in ex_desc
            or "扇形" in ex_desc
            or "直线" in ex_desc
        ):
            tags.add("aoe_damage")
        if "1名敌方" in ex_desc or "对1名" in ex_desc:
            tags.add("single_target_damage")
        if role == "main_dps" and ex_cost >= 3:
            tags.add("burst_damage")

    for skill_key, effect, desc in collect_skill_effects(student):
        effect_type = effect.get("Type")
        stat = effect.get("Stat") or ""
        negative = is_negative_effect(effect)
        ally_effect = is_ally_effect(effect)
        enemy_effect = is_enemy_effect(effect)

        if effect_type == "Heal":
            if target_has(effect, "Self") and not ally_effect:
                tags.add("self_healing")
            else:
                tags.add("healing")

        if effect_type == "Shield":
            tags.add("shield")

        if effect_type in {"CrowdControl", "Knockback"}:
            tags.add("crowd_control")

        if effect_type == "CostChange":
            tags.add("cost_reduction")

        if "位移" in desc or effect.get("Reposition"):
            tags.add("reposition")

        if "嘲讽" in desc or "挑衅" in desc:
            tags.add("taunt")
            tags.add("crowd_control")

        if "眩晕" in desc or "恐惧" in desc or "混乱" in desc:
            tags.add("crowd_control")

        if "护盾" in desc:
            tags.add("shield")

        if "RegenCost" in stat or "CostRegen" in desc or "费用恢复" in desc:
            if not negative:
                tags.add("cost_recovery")

        if effect_type != "Buff":
            continue

        if stat.startswith("AttackPower"):
            if ally_effect and not negative:
                tags.add("atk_buff")
            if enemy_effect or negative:
                tags.add("attack_down")

        if stat.startswith("CriticalPoint") or stat.startswith("CriticalDamage"):
            if ally_effect and not negative:
                tags.add("crit_buff")

        if stat.startswith("DefensePower"):
            if enemy_effect or negative:
                tags.add("defense_down")

    return sorted(tags)


def replace_parameter_placeholders(desc: str, parameters: list[Any]) -> str:
    """把 SchaleDB 的 <?1> 占位符替换成技能 1 级数值。"""
    result = desc
    for index, values in enumerate(parameters, start=1):
        value = values[0] if isinstance(values, list) and values else values
        result = result.replace(f"<?{index}>", str(value))
    return result


def replace_markup(match: re.Match[str]) -> str:
    """把 SchaleDB 技能文本里的标签转换成适合页面展示的中文。"""
    token = match.group(1)
    if token.startswith("/"):
        return ""
    if token in {"b", "i"}:
        return ""
    if token.startswith("b:") or token.startswith("d:"):
        stat_key = token.split(":", 1)[1]
        return STAT_LABELS.get(stat_key, stat_key)
    if token.startswith("s:"):
        form_name = re.search(r"='([^']+)'", token)
        return form_name.group(1) if form_name else ""
    return ""


def clean_skill_text(desc: str, parameters: list[Any]) -> str:
    """清理技能描述里的 HTML、换行和 SchaleDB 标记。"""
    text = html.unescape(desc or "")
    text = replace_parameter_placeholders(text, parameters)
    text = text.replace("\xa0", " ")
    text = re.sub(r"<([^>]+)>", replace_markup, text)
    text = re.sub(r"<\?\d+>", "数值", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_skills(student: dict[str, Any] | None) -> dict[str, str]:
    """生成页面展示用的技能摘要。"""
    if not student:
        return {"source": "暂无结构化技能资料。"}

    skills: dict[str, str] = {}
    for source_key, output_key in SKILL_KEY_LABELS.items():
        skill = student.get("Skills", {}).get(source_key)
        if not isinstance(skill, dict):
            continue
        name = skill.get("Name") or source_key
        desc = clean_skill_text(skill.get("Desc") or "", skill.get("Parameters") or [])
        skills[output_key] = f"{name}：{desc}" if desc else name

    return skills or {"source": "暂无结构化技能资料。"}


def build_gamekee_source(row: dict[str, Any]) -> dict[str, Any]:
    """整理 GameKee 来源字段。"""
    return {
        "url": GAMEKEE_STUDENT_PAGE,
        "content_id": row.get("content_id"),
        "raw_role": row.get("zy") or "",
        "rarity": row.get("level") or "",
        "weapon_type": row.get("wq") or "",
        "school": row.get("xy") or "",
        "club": row.get("st") or "",
        "terrain": {
            "street": row.get("sj") or "",
            "outdoor": row.get("sw") or "",
            "indoor": row.get("sn") or "",
        },
        "icon": row.get("icon") or "",
        "image": row.get("image") or "",
    }


def build_schale_source(
    student: dict[str, Any],
    match_method: str,
) -> dict[str, Any]:
    """整理 SchaleDB 来源字段。"""
    return {
        "url": f"{SCHALEDB_STUDENT_PAGE}/{student['PathName']}",
        "id": student.get("Id"),
        "name": student.get("Name"),
        "path_name": student.get("PathName"),
        "match_method": match_method,
        "raw_squad_type": student.get("SquadType"),
        "raw_position": student.get("Position"),
        "raw_tactic_role": student.get("TacticRole"),
        "raw_attack_type": student.get("BulletType"),
        "raw_armor_type": student.get("ArmorType"),
    }


def build_stats(student: dict[str, Any] | None, row: dict[str, Any]) -> dict[str, Any]:
    """整理角色基础数值，便于后续扩展筛选和页面展示。"""
    if not student:
        return {
            "base_star": row.get("level") or "",
            "weapon_type": row.get("wq") or "",
            "school": row.get("xy") or "",
            "club": row.get("st") or "",
        }

    return {
        "base_star": student.get("StarGrade"),
        "weapon_type": student.get("WeaponType"),
        "range": student.get("Range"),
        "school": student.get("School"),
        "club": student.get("Club"),
        "school_year": student.get("SchoolYear"),
        "age": student.get("CharacterAge"),
        "birthday": student.get("Birthday"),
        "height": student.get("CharHeightMetric"),
        "street_adaptation": student.get("StreetBattleAdaptation"),
        "outdoor_adaptation": student.get("OutdoorBattleAdaptation"),
        "indoor_adaptation": student.get("IndoorBattleAdaptation"),
        "max_hp_100": student.get("MaxHP100"),
        "attack_power_100": student.get("AttackPower100"),
        "defense_power_100": student.get("DefensePower100"),
        "heal_power_100": student.get("HealPower100"),
    }


def merge_tags(auto_tags: list[str], override: dict[str, Any] | None) -> list[str]:
    """合并自动标签和人工标签，避免重新抓取时丢掉人工整理成果。"""
    tags = set(auto_tags)
    if override:
        tags.update(override.get("tags", []))
    return sorted(tags)


def build_ratings(row: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    """保留或读取 GameKee 角色评测里的综合评分。"""
    if override and override.get("ratings"):
        return override["ratings"]

    raw_rating = (row.get("jspf") or "").strip()
    if not raw_rating:
        return {}

    return {
        "gamekee_overall": {
            "overall": raw_rating,
            "score": None,
            "tier": None,
            "updated_at": "",
            "source_status": "from_gamekee_roster",
            "url": f"{GAMEKEE_STUDENT_PAGE}",
        }
    }


def build_character(
    row: dict[str, Any],
    student: dict[str, Any] | None,
    match_method: str,
    override: dict[str, Any] | None,
) -> dict[str, Any]:
    """把 GameKee 行和 SchaleDB 学生资料合并成 App 使用的数据结构。"""
    raw_gamekee_role = row.get("zy") or ""

    if student:
        role = SCHALE_ROLE_MAP.get(student.get("TacticRole"), "support")
        position = SQUAD_TYPE_MAP.get(student.get("SquadType"), "unknown")
        battle_position = BATTLE_POSITION_MAP.get(student.get("Position"), "unknown")
        attack_type = ATTACK_TYPE_MAP.get(student.get("BulletType"), "unknown")
        armor_type = ARMOR_TYPE_MAP.get(student.get("ArmorType"), "unknown")
        ex_cost = first_ex_cost(student)
        auto_tags = infer_tags(student, role, ex_cost)
        skills = build_skills(student)
    else:
        role = GAMEKEE_ROLE_MAP.get(raw_gamekee_role, "support")
        position = "unknown"
        battle_position = "unknown"
        attack_type = "unknown"
        armor_type = "unknown"
        ex_cost = 0
        auto_tags = ROLE_TAGS.get(role, ["support_utility"]).copy()
        skills = {
            "source": "来自 GameKee 图鉴列表；技能文本与 EX 费用待结构化补充。",
            "profile": (
                f"{row.get('level') or '未知星级'} / "
                f"{raw_gamekee_role or '未知职业'} / "
                f"{row.get('wq') or '未知武器'} / "
                f"{row.get('xy') or '未知学院'}"
            ),
        }

    gamekee_source = build_gamekee_source(row)
    source = {
        "name": "GameKee + SchaleDB" if student else "GameKee",
        "data_complete": bool(student),
        "rarity": gamekee_source["rarity"] or (
            f"{student.get('StarGrade')}星" if student and student.get("StarGrade") else ""
        ),
        "weapon_type": (student or {}).get("WeaponType") or gamekee_source["weapon_type"],
        "school": gamekee_source["school"] or (student or {}).get("School") or "",
        "club": gamekee_source["club"] or (student or {}).get("Club") or "",
        "gamekee": gamekee_source,
    }

    if student:
        source["schaledb"] = build_schale_source(student, match_method)

    if override:
        source["curated_tags_preserved"] = True

    return {
        "name": row["name"],
        "role": role,
        "position": position,
        "battle_position": battle_position,
        "attack_type": attack_type,
        "armor_type": armor_type,
        "ex_cost": ex_cost,
        "skills": skills,
        "tags": merge_tags(auto_tags, override),
        "ratings": build_ratings(row, override),
        "stats": build_stats(student, row),
        "source": source,
    }


def main() -> None:
    existing_overrides = load_existing_overrides()
    gamekee_rows = [row for row in fetch_gamekee_roster() if is_real_student(row)]
    schale_students = fetch_schaledb_students()
    schale_indexes = build_schale_indexes(schale_students)

    characters = []
    missing_matches = []
    for row in gamekee_rows:
        student, match_method = find_schale_student(row["name"], schale_indexes)
        if not student:
            missing_matches.append(row["name"])

        override_name = CURATED_OVERRIDE_ALIASES.get(row["name"], row["name"])
        override = existing_overrides.get(row["name"]) or existing_overrides.get(override_name)
        characters.append(build_character(row, student, match_method, override))

    # GameKee 返回顺序基本按图鉴维护顺序；这里按 sort 再按名称稳定排序，方便 diff。
    characters.sort(
        key=lambda character: (
            next(
                row.get("sort", 999999)
                for row in gamekee_rows
                if row.get("name") == character["name"]
            ),
            character["name"],
        )
    )

    with DATA_PATH.open("w", encoding="utf-8") as file:
        json.dump(characters, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(f"已生成 {len(characters)} 名角色到 {DATA_PATH}")
    if missing_matches:
        print("以下角色未匹配到 SchaleDB 结构化数据：")
        for name in missing_matches:
            print(f"- {name}")
    else:
        print("全部 GameKee 角色均已匹配 SchaleDB 结构化数据。")


if __name__ == "__main__":
    main()
