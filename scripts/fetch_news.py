
#!/usr/bin/env python3
"""
김명길의 보험 인사이트
Google News RSS -> publisher URL -> article text -> news.json
"""

import json
import hashlib
import logging
import re
import time

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import trafilatura
from googlenewsdecoder import gnewsdecoder


# ==========================================
# 설정
# ==========================================

ROOT = Path(__file__).resolve().parents[1]

SOURCES_FILE = ROOT / "sources.json"
OUT = ROOT / "data" / "news.json"

MAX_PER_FEED = 20

# Google URL 해석 및 본문 수집 대상 기사 수
MAX_ARTICLES_TO_PROCESS = 40

# 내부 화면에 저장할 본문 발췌 최대 길이
MAX_CONTENT_LENGTH = 1500

# Google 과다 요청 방지
DECODE_INTERVAL = 1.0

RSS_TIMEOUT = 25
ARTICLE_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; "
        "MyeonggilInsuranceInsight/2.0)"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)


# ==========================================
# 공통 함수
# ==========================================

def clean(value):
    if not value:
        return ""

    value = re.sub(r"<[^>]+>", " ", str(value))
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def parse_date(value):
    try:
        return parsedate_to_datetime(
            value
        ).astimezone(timezone.utc).isoformat()
    except Exception:
        return ""


def valid_url(url):
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
        )
    except Exception:
        return False


def domain_of(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


# ==========================================
# 1. Google News RSS 수집
# ==========================================

def fetch_feed(feed):

    rss_url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(feed["query"])
        + "&hl=ko&gl=KR&ceid=KR:ko"
    )

    req = Request(rss_url, headers=HEADERS)

    with urlopen(req, timeout=RSS_TIMEOUT) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)

    articles = []

    for item in root.findall(".//item")[:MAX_PER_FEED]:

        title = clean(item.findtext("title"))
        google_url = clean(item.findtext("link"))
        summary = clean(item.findtext("description"))

        published_at = parse_date(
            item.findtext("pubDate")
        )

        source_element = item.find("source")

        source = clean(
            source_element.text
            if source_element is not None
            else ""
        )

        if not title or not valid_url(google_url):
            continue

        article_id = hashlib.sha1(
            (title + google_url).encode("utf-8")
        ).hexdigest()[:16]

        articles.append({
            "id": article_id,
            "category": feed["category"],
            "title": title,
            "summary": summary[:500],

            # 앱 내부 상세 화면에서 읽을 내용
            "content": "",

            # 수집 상태
            "content_status": "pending",

            # 원래 Google 뉴스 주소 보존
            "google_news_url": google_url,

            # 실제 언론사 주소
            "url": google_url,
            "publisher_url": "",

            "source": source,
            "domain": "news.google.com",

            "published_at": published_at,
            "content_fetched_at": ""
        })

    return articles


# ==========================================
# 2. Google News URL -> 언론사 URL
# ==========================================

def resolve_publisher_url(article):

    google_url = article.get("google_news_url", "")

    if not google_url:
        return ""

    # 이미 Google 주소가 아닌 경우 그대로 사용
    if "news.google.com" not in urlparse(google_url).netloc:
        return google_url

    try:

        result = gnewsdecoder(
            google_url,
            interval=None,
            timeout=15
        )

        if (
            isinstance(result, dict)
            and result.get("success")
        ):

            publisher_url = result.get("decoded_url", "")

            if valid_url(publisher_url):

                article["url"] = publisher_url
                article["publisher_url"] = publisher_url
                article["domain"] = domain_of(publisher_url)

                logging.info(
                    "URL 해석 성공: %s",
                    article["domain"]
                )

                return publisher_url

        message = (
            result.get("message", "URL 해석 실패")
            if isinstance(result, dict)
            else "알 수 없는 응답"
        )

        logging.warning(
            "Google URL 해석 실패: %s",
            str(message)[:150]
        )

    except Exception as exc:

        logging.warning(
            "URL 해석 오류: %s",
            str(exc)[:150]
        )

    # 실패하더라도 Google 원본 링크는 보존
    article["content_status"] = "url_decode_failed"

    return ""


# ==========================================
# 3. 언론사 기사 본문 추출
# ==========================================

def extract_article(article, publisher_url):

    if not publisher_url:
        return article

    try:

        downloaded = trafilatura.fetch_url(
            publisher_url
        )

        if not downloaded:

            article["content_status"] = "download_failed"
            return article

        extracted = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            include_links=False,
            favor_precision=True,
            deduplicate=True
        )

        if not extracted:

            article["content_status"] = "no_article_text"
            return article

        extracted = clean(extracted)

        if len(extracted) < 100:

            article["content_status"] = "text_too_short"
            return article

        # 전문 전체를 저장하지 않고 일부 발췌만 보관
        article["content"] = extracted[:MAX_CONTENT_LENGTH]

        article["content_status"] = "success"

        article["content_fetched_at"] = (
            datetime.now(timezone.utc).isoformat()
        )

        # RSS 요약이 비어 있으면 본문 첫 부분을 요약으로 활용
        if not article.get("summary"):

            article["summary"] = extracted[:300]

        logging.info(
            "본문 추출 성공: %s",
            article.get("title", "")[:60]
        )

    except Exception as exc:

        article["content_status"] = "extraction_failed"

        logging.warning(
            "본문 추출 실패: %s / %s",
            article.get("title", "")[:50],
            str(exc)[:120]
        )

    return article


# ==========================================
# 4. URL 해석 + 본문 수집
# ==========================================

def process_articles(articles):

    targets = articles[:MAX_ARTICLES_TO_PROCESS]

    logging.info(
        "본문 수집 대상: %d개",
        len(targets)
    )

    for index, article in enumerate(targets, start=1):

        logging.info(
            "[%d/%d] %s",
            index,
            len(targets),
            article.get("title", "")[:60]
        )

        publisher_url = resolve_publisher_url(article)

        if publisher_url:

            extract_article(
                article,
                publisher_url
            )

        # Google 요청 간격
        if index < len(targets):
            time.sleep(DECODE_INTERVAL)

    # 처리하지 않은 나머지 기사
    for article in articles[MAX_ARTICLES_TO_PROCESS:]:

        article["content_status"] = "not_attempted"

    return articles


# ==========================================
# 5. 기존 기사와 중복 제거
# ==========================================

def load_previous_articles():

    if not OUT.exists():
        return {}

    try:

        data = json.loads(
            OUT.read_text(encoding="utf-8")
        )

        return {
            article["id"]: article
            for article in data.get("articles", [])
            if article.get("id")
        }

    except Exception as exc:

        logging.warning(
            "이전 뉴스 데이터 읽기 실패: %s",
            str(exc)
        )

        return {}


def preserve_previous_content(articles, previous):

    for article in articles:

        old = previous.get(article["id"])

        if not old:
            continue

        # 이미 성공한 기사라면 기존 본문을 재사용
        if (
            old.get("content_status") == "success"
            and old.get("content")
        ):

            article["content"] = old["content"]
            article["content_status"] = "success"

            article["publisher_url"] = (
                old.get("publisher_url")
                or old.get("url")
                or ""
            )

            article["url"] = (
                old.get("url")
                or article["url"]
            )

            article["domain"] = (
                old.get("domain")
                or article["domain"]
            )

            article["content_fetched_at"] = (
                old.get("content_fetched_at", "")
            )


# ==========================================
# 6. 전체 실행
# ==========================================

def main():

    if not SOURCES_FILE.exists():

        raise FileNotFoundError(
            "sources.json 파일을 찾을 수 없습니다."
        )

    sources = json.loads(
        SOURCES_FILE.read_text(encoding="utf-8")
    )

    previous = load_previous_articles()

    collected = {}
    errors = []

    # RSS 수집
    logging.info("Google News RSS 수집 시작")

    for feed in sources:

        try:

            for article in fetch_feed(feed):

                collected[article["id"]] = article

            logging.info(
                "RSS 성공: %s",
                feed["name"]
            )

        except Exception as exc:

            errors.append(
                f'{feed.get("name", "Unknown")}: {str(exc)[:100]}'
            )

            logging.warning(
                "RSS 실패: %s / %s",
                feed.get("name", "Unknown"),
                str(exc)[:100]
            )

        time.sleep(0.3)

    articles = sorted(
        collected.values(),
        key=lambda a: a.get("published_at", ""),
        reverse=True
    )

    logging.info(
        "RSS 기사 총 %d개",
        len(articles)
    )

    # 기존에 성공한 본문은 다시 요청하지 않음
    preserve_previous_content(articles, previous)

    # 본문이 없는 기사만 대상으로 수집
    pending = [
        a for a in articles
        if a.get("content_status") != "success"
    ]

    articles = process_articles(pending) + [
        a for a in articles
        if a.get("content_status") == "success"
    ]

    # 최신순 재정렬
    articles.sort(
        key=lambda a: a.get("published_at", ""),
        reverse=True
    )

    # 통계
    success = sum(
        a.get("content_status") == "success"
        for a in articles
    )

    decode_failed = sum(
        a.get("content_status") == "url_decode_failed"
        for a in articles
    )

    other_failed = sum(
        a.get("content_status") in (
            "download_failed",
            "no_article_text",
            "text_too_short",
            "extraction_failed"
        )
        for a in articles
    )

    # JSON 저장
    payload = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_articles": len(articles),

        "content_stats": {
            "success": success,
            "url_decode_failed": decode_failed,
            "other_failed": other_failed
        },

        "articles": articles,

        "notice": (
            "일부 RSS 수집에 실패했습니다: "
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

    logging.info("================================")
    logging.info("뉴스 수집 완료")
    logging.info("전체 기사: %d", len(articles))
    logging.info("본문 수집 성공: %d", success)
    logging.info("URL 해석 실패: %d", decode_failed)
    logging.info("본문 추출 실패: %d", other_failed)
    logging.info("저장 위치: %s", OUT)
    logging.info("================================")


if __name__ == "__main__":
    main()
