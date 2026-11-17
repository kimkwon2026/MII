#!/usr/bin/env python3
"""Fetch Google News RSS search feeds and write normalized data/news.json.
RSS search is used as an initial source aggregator. Always follow the linked publisher page.
"""
import json, hashlib, re, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "news.json"
MAX_PER_FEED = 20
HEADERS = {"User-Agent": "MyeonggilInsuranceInsight/1.0 (RSS reader)"}

def clean(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", value).strip()

def parse_date(value):
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except Exception:
        return ""

def fetch(feed):
    url = "https://news.google.com/rss/search?q=" + quote_plus(feed["query"]) + "&hl=ko&gl=KR&ceid=KR:ko"
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=25) as response:
        xml = response.read()
    root = ET.fromstring(xml)
    items = []
    for item in root.findall(".//item")[:MAX_PER_FEED]:
        title = clean(item.findtext("title"))
        link = clean(item.findtext("link"))
        desc = clean(item.findtext("description"))
        pub = parse_date(item.findtext("pubDate"))
        source_el = item.find("source")
        source = clean(source_el.text if source_el is not None else "")
        if not title or not link:
            continue
        # Google News links are retained as supplied; they lead to the publisher article.
        uid = hashlib.sha1((title + link).encode("utf-8")).hexdigest()[:16]
        domain = urlparse(link).netloc.replace("www.", "")
        items.append({
            "id": uid, "category": feed["category"], "title": title,
            "summary": desc[:500], "source": source or domain,
            "domain": domain, "url": link, "published_at": pub
        })
    return items

def main():
    collected, errors = {}, []
    for feed in SOURCES:
        try:
            for item in fetch(feed):
                collected[item["id"]] = item
            print(f"OK: {feed['name']}")
        except Exception as exc:
            errors.append(f"{feed['name']}: {exc}")
            print(f"WARN: {feed['name']}: {exc}")
        time.sleep(0.4)
    articles = sorted(collected.values(), key=lambda x: x.get("published_at",""), reverse=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": articles,
        "notice": ("일부 피드 수집에 실패했습니다: " + " / ".join(errors[:3])) if errors else ""
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(articles)} articles to {OUT}")

if __name__ == "__main__":
    main()
