"""采集 B 站《碧蓝档案》推图配队资料，并区分普通推图与总力战凹分。

这个脚本只做“资料候选采集”，不会直接改推荐算法。
B 站搜索接口有时会触发验证码；遇到这种情况时，可以用 --seed-url
手动传入已找到的专栏或视频链接，让脚本至少完成页面标题和分类标记。
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = PROJECT_DIR / "data" / "bilibili_push_guides.json"
BILIBILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"

DEFAULT_KEYWORDS = [
    "碧蓝档案 推图 配队",
    "蔚蓝档案 主线 推图 阵容",
    "蔚蓝档案 开荒 配队 萌新",
]

PUSH_MAP_KEYWORDS = {
    "推图",
    "主线",
    "普通图",
    "开荒",
    "萌新",
    "新手",
    "低星",
    "低练",
    "平民",
    "清杂",
    "三星",
    "属性克制",
}

RAID_SCORE_KEYWORDS = {
    "总力战",
    "大决战",
    "制约解除",
    "战术考试",
    "合同火力",
    "凹分",
    "凹轴",
    "一档",
    "二档",
    "作业",
    "刀",
    "torment",
    "tm",
    "ins",
    "insane",
}


def fetch_text(url: str, timeout: int = 20) -> str:
    """请求网页文本；失败时抛出异常，由调用方记录。"""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_html(text: str) -> str:
    """去掉 HTML 标签和实体，便于做关键词判断。"""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def clean_title(text: str) -> str:
    """清理 B 站搜索结果标题里的高亮标签。"""
    return strip_html(text).replace("\u200b", "").strip()


def make_excerpt(text: str, max_length: int = 120) -> str:
    """保存到研究 JSON 时只保留短摘要，避免把整段网页简介塞进仓库。"""
    text = strip_html(text)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def keyword_hits(text: str, keywords: set[str]) -> list[str]:
    """返回文本命中的关键词，保持输出稳定。"""
    lower_text = text.lower()
    return sorted(keyword for keyword in keywords if keyword.lower() in lower_text)


def classify_guide(title: str, description: str = "") -> dict[str, Any]:
    """按标题和摘要粗分资料类型。

    push_map：普通推图、开荒、主线配队。
    raid_score_chasing：总力战、大决战等高难凹分内容。
    mixed_or_unknown：信号不足或两边都有，需要人工确认。
    """
    text = f"{title} {description}"
    push_hits = keyword_hits(text, PUSH_MAP_KEYWORDS)
    raid_hits = keyword_hits(text, RAID_SCORE_KEYWORDS)

    if raid_hits and push_hits:
        classification = "mixed_or_unknown"
    elif raid_hits:
        classification = "raid_score_chasing"
    elif push_hits:
        classification = "push_map"
    else:
        classification = "mixed_or_unknown"

    return {
        "classification": classification,
        "push_signals": push_hits,
        "raid_signals": raid_hits,
    }


def bilibili_search(keyword: str, search_type: str, page: int) -> list[dict[str, Any]]:
    """调用 B 站搜索接口，返回原始候选条目。

    如果命中验证码或接口格式变化，会返回空列表并把原因写到 stderr。
    """
    query = urllib.parse.urlencode(
        {
            "search_type": search_type,
            "keyword": keyword,
            "page": page,
        }
    )
    url = f"{BILIBILI_SEARCH_API}?{query}"
    try:
        text = fetch_text(url)
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"搜索失败: {keyword} / {search_type}: {error}", file=sys.stderr)
        return []

    if "验证码" in text or "risk-captcha" in text or not text.lstrip().startswith("{"):
        print(f"B 站搜索触发验证或返回非 JSON: {keyword} / {search_type}", file=sys.stderr)
        return []

    payload = json.loads(text)
    return payload.get("data", {}).get("result", []) or []


def normalize_search_item(raw_item: dict[str, Any], keyword: str, search_type: str) -> dict[str, Any]:
    """把 B 站搜索结果整理成稳定 JSON 结构。"""
    title = clean_title(str(raw_item.get("title") or ""))
    description = strip_html(str(raw_item.get("description") or raw_item.get("desc") or ""))
    url = raw_item.get("arcurl") or raw_item.get("url") or raw_item.get("goto_url") or ""
    if url and url.startswith("//"):
        url = f"https:{url}"

    item = {
        "title": title,
        "url": url,
        "description": make_excerpt(description),
        "author": raw_item.get("author") or raw_item.get("uname") or "",
        "source_type": search_type,
        "matched_keyword": keyword,
    }
    item.update(classify_guide(title, description))
    return item


def parse_seed_url(url: str) -> dict[str, Any]:
    """从手动提供的 B 站链接中提取标题和描述。"""
    try:
        text = fetch_text(url)
    except (urllib.error.URLError, TimeoutError) as error:
        return {
            "title": "",
            "url": url,
            "description": "",
            "source_type": "seed_url",
            "classification": "fetch_failed",
            "error": str(error),
            "push_signals": [],
            "raid_signals": [],
        }

    title_match = re.search(r"<title>(.*?)</title>", text, flags=re.I | re.S)
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        text,
        flags=re.I | re.S,
    )
    title = strip_html(title_match.group(1)) if title_match else ""
    description = strip_html(desc_match.group(1)) if desc_match else ""

    item = {
        "title": title,
        "url": url,
        "description": make_excerpt(description),
        "source_type": "seed_url",
        "matched_keyword": "",
    }
    item.update(classify_guide(title, description))
    return item


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 URL 和标题去重。"""
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = (item.get("url", ""), item.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", action="append", help="额外搜索关键词，可重复传入")
    parser.add_argument("--pages", type=int, default=1, help="每个关键词抓取页数")
    parser.add_argument("--seed-url", action="append", default=[], help="手动补充的 B 站视频或专栏 URL")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    keywords = DEFAULT_KEYWORDS + (args.keyword or [])
    items: list[dict[str, Any]] = []
    for keyword in keywords:
        for page in range(1, args.pages + 1):
            for search_type in ("video", "article"):
                for raw_item in bilibili_search(keyword, search_type, page):
                    items.append(normalize_search_item(raw_item, keyword, search_type))

    for seed_url in args.seed_url:
        items.append(parse_seed_url(seed_url))

    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "note": "B 站资料仅作为推图规则研究候选；推图与总力战分类需要人工复核后再进入推荐规则。",
        "keywords": keywords,
        "items": dedupe_items(items),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {args.output}")


if __name__ == "__main__":
    main()
