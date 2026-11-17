
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
김명길의 보험 인사이트
Google News RSS 수집 및 기사 발췌 정보 저장

기능
1. Google News RSS 수집
2. 언론사 페이지에서 공개 메타 설명 및 짧은 기사 발췌 수집
3. 수집 실패 시 RSS 요약 사용
4. data/news.json 생성
5. 일부 기사 수집 실패에도 전체 작업 유지
"""

import json
import hashlib
import re
import time
import html

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


# =====================================
# 기본 설정
# =====================================

ROOT = Path(__file__).resolve().parents[1]

SOURCES = json.loads(
    (ROOT / "sources.json").read_text(encoding="utf-8")
)

OUT = ROOT / "data" / "news.json"

MAX_PER_FEED = 20

# 피드별 실제 언론사 페이지 접속 시도 개수
MAX_ARTICLE_FETCH_PER_FEED = 8

# 내부 화면에 저장할 최대 발췌 길이
MAX_CONTENT_CHARS = 700

# 네트워크 대기 시간
REQUEST_TIMEOUT = 12

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; MyeonggilInsuranceInsight/1.0; "
        "+https://github.com/kimkwon2026/MII)"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7"
}


# =====================================
# 공통 텍스트 정리
# =====================================

def clean(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def limit_text(value, length=MAX_CONTENT_CHARS):
    value = clean(value)

    if len(value) > length:
        value = value[:length].rsplit(" ", 1)[0] + "…"

    return value


# =====================================
# 날짜 변환
# =====================================

def parse_date(value):
    try:
        return (
            parsedate_to_datetime(value)
            .astimezone(timezone.utc)
            .isoformat()
        )
    except Exception:
        return ""


# =====================================
# HTML 기사 정보 추출기
# =====================================

class ArticleParser(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.meta = {}
        self.paragraphs = []

        self.current_paragraph = []
        self.in_paragraph = False

        self.skip_depth = 0

        self.skip_tags = {
            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "footer",
            "header",
            "aside"
        }

    def handle_starttag(self, tag, attrs):

        attrs = dict(attrs)

        # 메타 설명 수집
        if tag == "meta":

            name = (
                attrs.get("property")
                or attrs.get("name")
                or attrs.get("itemprop")
                or ""
            ).lower()

            content = clean(attrs.get("content", ""))

            if name and content:
                self.meta[name] = content

        # 불필요한 영역 제외
        if tag in self.skip_tags:
            self.skip_depth += 1

        if tag == "p" and self.skip_depth == 0:
            self.in_paragraph = True
            self.current_paragraph = []

    def handle_endtag(self, tag):

        if tag in self.skip_tags and self.skip_depth > 0:
            self.skip_depth -= 1

        if tag == "p" and self.in_paragraph:

            paragraph = clean(
                " ".join(self.current_paragraph)
            )

            if len(paragraph) >= 35:
                self.paragraphs.append(paragraph)

            self.current_paragraph = []
            self.in_paragraph = False

    def handle_data(self, data):

        if self.skip_depth > 0:
            return

        if self.in_paragraph:
            self.current_paragraph.append(data)


# =====================================
# 언론사 페이지 접속 및 발췌 수집
# =====================================

def fetch_article_excerpt(url):

    if not url:
        return "", url

    try:

        req = Request(
            url,
            headers=HEADERS
        )

        with urlopen(
            req,
            timeout=REQUEST_TIMEOUT
        ) as response:

            final_url = response.geturl()

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            # HTML이 아닌 파일은 제외
            if "html" not in content_type:
                return "", final_url

            raw = response.read(1024 * 1024)

            charset = response.headers.get_content_charset()

            if charset:
                try:
                    page = raw.decode(
                        charset,
                        errors="replace"
                    )
                except Exception:
                    page = raw.decode(
                        "utf-8",
                        errors="replace"
                    )
            else:
                page = raw.decode(
                    "utf-8",
                    errors="replace"
                )

        parser = ArticleParser()
        parser.feed(page)

        # 메타 설명 우선순위
        description = (
            parser.meta.get("og:description")
            or parser.meta.get("description")
            or parser.meta.get("twitter:description")
            or parser.meta.get("dc.description")
            or ""
        )

        # 메타 설명이 없는 경우 첫 문단 활용
        if not description:

            description = " ".join(
                parser.paragraphs[:3]
            )

        excerpt = limit_text(description)

        return excerpt, final_url

    except Exception as exc:

        print(
            f"  ARTICLE WARN: "
            f"{url[:100]} : {exc}"
        )

        return "", url


# =====================================
# Google News RSS 수집
# =====================================

def fetch(feed):

    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(feed["query"])
        + "&hl=ko&gl=KR&ceid=KR:ko"
    )

    req = Request(
        url,
        headers=HEADERS
    )

    with urlopen(
        req,
        timeout=REQUEST_TIMEOUT
    ) as response:

        xml = response.read()

    root = ET.fromstring(xml)

    items = []

    for item in root.findall(".//item")[:MAX_PER_FEED]:

        title = clean(
            item.findtext("title")
        )

        link = clean(
            item.findtext("link")
        )

        desc = clean(
            item.findtext("description")
        )

        pub = parse_date(
            item.findtext("pubDate")
        )

        source_el = item.find("source")

        source = clean(
            source_el.text
            if source_el is not None
            else ""
        )

        if not title or not link:
            continue

        uid = hashlib.sha1(
            (title + link).encode("utf-8")
        ).hexdigest()[:16]

        domain = (
            urlparse(link)
            .netloc
            .replace("www.", "")
        )

        items.append({
            "id": uid,
            "category": feed["category"],
            "title": title,
            "summary": desc[:500],
            "content": "",
            "content_type": "",
            "source": source or domain,
            "domain": domain,
            "url": link,
            "published_at": pub
        })

    return items


# =====================================
# 개별 기사 정보 보강
# =====================================

def enrich_articles(items):

    fetched_count = 0

    for index, article in enumerate(items):

        if fetched_count >= MAX_ARTICLE_FETCH_PER_FEED:
            break

        print(
            f"  ARTICLE "
            f"{fetched_count + 1}/"
            f"{MAX_ARTICLE_FETCH_PER_FEED}: "
            f"{article['title'][:60]}"
        )

        excerpt, final_url = fetch_article_excerpt(
            article["url"]
        )

        fetched_count += 1

        if excerpt:

            article["content"] = excerpt

            article["content_type"] = (
                "publisher_excerpt"
            )

            article["content_source"] = (
                "publisher_page"
            )

            print("  OK: 기사 발췌 수집")

        else:

            # 원문 수집 실패 시 RSS 요약 유지
            article["content"] = ""

            article["content_type"] = ""

            article["content_source"] = "rss"

            print("  INFO: RSS 요약 사용")

        # 최종 접속 URL 기준 도메인 보정
        try:

            final_domain = (
                urlparse(final_url)
                .netloc
                .replace("www.", "")
            )

            if final_domain:
                article["domain"] = final_domain

        except Exception:
            pass

        time.sleep(0.3)

    return items


# =====================================
# 전체 뉴스 수집
# =====================================

def main():

    collected = {}
    errors = []

    print("=" * 50)
    print("김명길의 보험 인사이트 뉴스 수집 시작")
    print("=" * 50)

    for feed in SOURCES:

        try:

            items = fetch(feed)

            # 먼저 RSS 기사 전체 저장
            for item in items:
                collected[item["id"]] = item

            print(
                f"OK: {feed['name']} "
                f"RSS {len(items)}건"
            )

            # 기사 일부에 대해 발췌 수집 시도
            enrich_articles(items)

            # 보강된 기사로 교체
            for item in items:
                collected[item["id"]] = item

        except Exception as exc:

            errors.append(
                f"{feed['name']}: {exc}"
            )

            print(
                f"WARN: {feed['name']}: {exc}"
            )

        time.sleep(0.4)

    # =================================
    # 날짜순 정렬
    # =================================

    articles = sorted(
        collected.values(),
        key=lambda x: x.get(
            "published_at", ""
        ),
        reverse=True
    )

    # =================================
    # JSON 저장
    # =================================

    payload = {

        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "articles": articles,

        "notice": (
            "일부 피드 수집에 실패했습니다: "
            + " / ".join(errors[:3])
        ) if errors else "",

        "article_fetch": {
            "enabled": True,
            "max_articles_per_feed": (
                MAX_ARTICLE_FETCH_PER_FEED
            ),
            "max_content_chars": (
                MAX_CONTENT_CHARS
            ),
            "content_policy": (
                "공개 메타 설명 및 짧은 발췌만 저장"
            )
        }
    }

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    # =================================
    # 결과 출력
    # =================================

    excerpt_count = sum(
        1 for a in articles
        if a.get("content")
    )

    print()
    print("=" * 50)
    print("뉴스 수집 완료")
    print("=" * 50)

    print(
        f"전체 기사: {len(articles)}건"
    )

    print(
        f"발췌 수집: {excerpt_count}건"
    )

    print(
        f"RSS 요약 사용: "
        f"{len(articles) - excerpt_count}건"
    )

    print(
        f"저장 위치: {OUT}"
    )

    if errors:
        print(
            f"수집 실패 피드: {len(errors)}개"
        )

    print("=" * 50)


if __name__ == "__main__":
    main()
