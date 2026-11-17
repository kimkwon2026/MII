
#!/usr/bin/env python3
"""
Fetch Google News RSS feeds and enrich articles with publicly accessible
publisher descriptions and limited article excerpts.

Output: data/news.json

No third-party Python packages required.
"""

import json
import hashlib
import re
import time
import html
import logging

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


# ==========================================
# 기본 설정
# ==========================================

ROOT = Path(__file__).resolve().parents[1]

SOURCES_FILE = ROOT / "sources.json"
OUT = ROOT / "data" / "news.json"

MAX_PER_FEED = 20

# 본문을 가져올 최신 기사 수
MAX_CONTENT_FETCH = 100

# 기사 본문에 저장할 최대 글자 수
MAX_CONTENT_LENGTH = 1200

# 동시에 접속할 언론사 페이지 수
MAX_WORKERS = 6

RSS_TIMEOUT = 25
ARTICLE_TIMEOUT = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; MyeonggilInsuranceInsight/2.0; "
        "+https://github.com/kimkwon2026/MII)"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)


# ==========================================
# 텍스트 정리
# ==========================================

def clean(value):
    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def parse_date(value):
    try:
        return parsedate_to_datetime(
            value
        ).astimezone(timezone.utc).isoformat()

    except Exception:
        return ""


def safe_domain(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")

    except Exception:
        return ""


# ==========================================
# RSS 수집
# ==========================================

def fetch(feed):

    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(feed["query"])
        + "&hl=ko&gl=KR&ceid=KR:ko"
    )

    req = Request(url, headers=HEADERS)

    with urlopen(req, timeout=RSS_TIMEOUT) as response:
        xml = response.read()

    root = ET.fromstring(xml)

    items = []

    for item in root.findall(".//item")[:MAX_PER_FEED]:

        title = clean(item.findtext("title"))
        link = clean(item.findtext("link"))
        desc = clean(item.findtext("description"))

        pub = parse_date(item.findtext("pubDate"))

        source_el = item.find("source")

        source = clean(
            source_el.text if source_el is not None else ""
        )

        if not title or not link:
            continue

        if not link.startswith(("http://", "https://")):
            continue

        uid = hashlib.sha1(
            (title + link).encode("utf-8")
        ).hexdigest()[:16]

        domain = safe_domain(link)

        items.append({
            "id": uid,
            "category": feed["category"],
            "title": title,
            "summary": desc[:500],
            "content": "",
            "content_status": "pending",
            "content_source": "",
            "content_fetched_at": "",
            "source": source or domain,
            "domain": domain,
            "url": link,
            "publisher_url": "",
            "published_at": pub
        })

    return items


# ==========================================
# 언론사 페이지 HTML 분석
# ==========================================

class ArticleParser(HTMLParser):

    SKIP_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "footer",
        "header",
        "aside",
        "form"
    }

    def __init__(self):

        super().__init__(convert_charrefs=True)

        self.meta = {}

        self.paragraphs = []

        self.current_paragraph = []

        self.skip_depth = 0

        self.in_paragraph = False

    def handle_starttag(self, tag, attrs):

        attrs = dict(attrs)

        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth:
            return

        if tag == "meta":

            name = (
                attrs.get("property")
                or attrs.get("name")
                or ""
            ).lower()

            content = clean(attrs.get("content", ""))

            if name and content:
                self.meta[name] = content

        elif tag == "p":

            self.in_paragraph = True
            self.current_paragraph = []

    def handle_endtag(self, tag):

        if tag in self.SKIP_TAGS:

            if self.skip_depth:
                self.skip_depth -= 1

            return

        if self.skip_depth:
            return

        if tag == "p" and self.in_paragraph:

            text = clean(
                " ".join(self.current_paragraph)
            )

            if len(text) >= 35:
                self.paragraphs.append(text)

            self.current_paragraph = []
            self.in_paragraph = False

    def handle_data(self, data):

        if self.skip_depth:
            return

        if self.in_paragraph:
            text = clean(data)

            if text:
                self.current_paragraph.append(text)


# ==========================================
# 언론사 기사 내용 수집
# ==========================================

def fetch_article_content(article):

    url = article.get("url", "")

    if not url.startswith(("http://", "https://")):
        return article

    try:

        req = Request(url, headers=HEADERS)

        with urlopen(
            req,
            timeout=ARTICLE_TIMEOUT
        ) as response:

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if "html" not in content_type:
                article["content_status"] = "unavailable"
                return article

            # 너무 큰 페이지는 읽지 않음
            raw_html = response.read(2_000_000)

            publisher_url = response.geturl()

        page = raw_html.decode(
            "utf-8",
            errors="replace"
        )

        parser = ArticleParser()
        parser.feed(page)

        meta = parser.meta

        # 언론사가 제공하는 공식 설명
        page_description = (
            meta.get("og:description")
            or meta.get("twitter:description")
            or meta.get("description")
            or ""
        )

        page_description = clean(page_description)

        # 기사 본문 문단 추출
        paragraphs = []

        seen = set()

        for paragraph in parser.paragraphs:

            paragraph = clean(paragraph)

            if not paragraph:
                continue

            if paragraph in seen:
                continue

            seen.add(paragraph)

            # 광고 및 일반 메뉴 문구 제외
            if len(paragraph) < 35:
                continue

            if re.search(
                r"구독하기|로그인|회원가입|"
                r"무단전재|저작권자|기자 구독",
                paragraph
            ):
                continue

            paragraphs.append(paragraph)

        # 본문 일부만 저장
        # 기사 전문을 무단 복제하지 않도록 길이 제한

        excerpt = " ".join(paragraphs)

        excerpt = clean(excerpt)

        excerpt = excerpt[:MAX_CONTENT_LENGTH]

        # 본문 수집 성공 여부
        if excerpt:

            article["content"] = excerpt

            article["content_status"] = "success"

            article["content_source"] = "publisher_page"

        else:

            article["content_status"] = "summary_only"

        # RSS보다 구체적인 설명이 있으면 요약 교체
        if (
            page_description
            and len(page_description) > 30
        ):

            article["summary"] = page_description[:500]

        article["publisher_url"] = publisher_url

        article["domain"] = (
            safe_domain(publisher_url)
            or article["domain"]
        )

        article["content_fetched_at"] = (
            datetime.now(timezone.utc).isoformat()
        )

    except Exception as exc:

        logging.warning(
            "본문 수집 실패: %s / %s",
            article.get("title", "")[:50],
            str(exc)[:120]
        )

        article["content_status"] = "unavailable"

    return article


# ==========================================
# 본문 수집 병렬 처리
# ==========================================

def enrich_articles(articles):

    targets = articles[:MAX_CONTENT_FETCH]

    logging.info(
        "본문 수집 시작: %d개 기사",
        len(targets)
    )

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(
                fetch_article_content,
                article
            ): article
            for article in targets
        }

        completed = 0

        for future in as_completed(futures):

            article = futures[future]

            try:

                result = future.result()

                article.update(result)

            except Exception as exc:

                article["content_status"] = "unavailable"

                logging.warning(
                    "처리 오류: %s",
                    str(exc)[:120]
                )

            completed += 1

            if completed % 10 == 0:

                logging.info(
                    "본문 수집 진행: %d / %d",
                    completed,
                    len(targets)
                )

    # 본문 수집 대상이 아니었던 기사
    # 기존 RSS 요약은 그대로 유지

    for article in articles[MAX_CONTENT_FETCH:]:

        article["content_status"] = "not_attempted"

    return articles


# ==========================================
# 전체 실행
# ==========================================

def main():

    if not SOURCES_FILE.exists():

        raise FileNotFoundError(
            "sources.json 파일을 찾을 수 없습니다."
        )

    SOURCES = json.loads(
        SOURCES_FILE.read_text(encoding="utf-8")
    )

    collected = {}
    errors = []

    # 1. RSS 수집

    logging.info("Google 뉴스 RSS 수집 시작")

    for feed in SOURCES:

        try:

            for item in fetch(feed):

                collected[item["id"]] = item

            logging.info(
                "RSS 수집 성공: %s",
                feed["name"]
            )

        except Exception as exc:

            errors.append(
                f'{feed["name"]}: {str(exc)[:100]}'
            )

            logging.warning(
                "RSS 수집 실패: %s / %s",
                feed["name"],
                str(exc)[:100]
            )

        time.sleep(0.3)

    # 최신순 정렬

    articles = sorted(
        collected.values(),
        key=lambda x: x.get("published_at", ""),
        reverse=True
    )

    logging.info(
        "RSS 수집 완료: 총 %d개 기사",
        len(articles)
    )

    # 2. 언론사 페이지 본문 일부 수집

    articles = enrich_articles(articles)

    # 3. 수집 통계

    success_count = sum(
        1 for a in articles
        if a.get("content_status") == "success"
    )

    unavailable_count = sum(
        1 for a in articles
        if a.get("content_status") == "unavailable"
    )

    summary_count = sum(
        1 for a in articles
        if a.get("content_status") in (
            "summary_only",
            "not_attempted"
        )
    )

    # 4. JSON 저장

    payload = {

        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_articles": len(articles),

        "content_stats": {
            "success": success_count,
            "summary_only": summary_count,
            "unavailable": unavailable_count
        },

        "articles": articles,

        "notice": (
            "일부 RSS 피드 수집에 실패했습니다: "
            + " / ".join(errors[:3])
        ) if errors else ""
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

    logging.info("--------------------------------")
    logging.info("뉴스 수집 및 저장 완료")
    logging.info("전체 기사: %d", len(articles))
    logging.info("본문 수집 성공: %d", success_count)
    logging.info("요약만 제공: %d", summary_count)
    logging.info("본문 수집 실패: %d", unavailable_count)
    logging.info("저장 위치: %s", OUT)
    logging.info("--------------------------------")


if __name__ == "__main__":
    main()
