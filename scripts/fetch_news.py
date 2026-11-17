
#!/usr/bin/env python3
"""
김명길의 보험 인사이트
Google News RSS -> publisher URL -> article text -> news.json
"""

import json
import hashlib
import html
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
MAX_ARTICLES_TO_PROCESS = 40
MAX_CONTENT_LENGTH = 1500

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
    """HTML 태그와 엔티티를 정리하는 일반 텍스트 함수."""

    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def clean_article_text(value):
    """기사 본문의 문단 구분을 보존한다."""

    if not value:
        return ""

    value = html.unescape(str(value))

    paragraphs = re.split(
        r"\n\s*\n",
        value
    )

    cleaned = []

    for paragraph in paragraphs:
        paragraph = re.sub(
            r"[ \t]+",
            " ",
            paragraph
        ).strip()

        if paragraph:
            cleaned.append(paragraph)

    return "\n\n".join(cleaned)


def normalize_text(value):
    """중복 기사 판정을 위한 제목 정규화."""

    value = html.unescape(str(value or ""))

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        "",
        value
    )

    return value.casefold()


def make_article_id(title, source):
    """제목과 언론사 기준으로 고유 ID 생성."""

    normalized_title = normalize_text(title)
    normalized_source = normalize_text(source)

    fingerprint = (
        normalized_title
        + "|"
        + normalized_source
    )

    return hashlib.sha1(
        fingerprint.encode("utf-8")
    ).hexdigest()[:16]


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
        return (
            urlparse(url)
            .netloc
            .lower()
            .replace("www.", "")
        )

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

    req = Request(
        rss_url,
        headers=HEADERS
    )

    with urlopen(
        req,
        timeout=RSS_TIMEOUT
    ) as response:

        xml_data = response.read()

    root = ET.fromstring(xml_data)

    articles = []

    for item in root.findall(".//item")[:MAX_PER_FEED]:

        title = clean(
            item.findtext("title")
        )

        google_url = clean(
            item.findtext("link")
        )

        summary = clean(
            item.findtext("description")
        )

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

        article_id = make_article_id(
            title,
            source
        )

        articles.append({

            "id": article_id,

            "category": feed["category"],

            "title": title,

            "summary": summary[:500],

            "content": "",

            "content_status": "pending",

            "google_news_url": google_url,

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

    google_url = article.get(
        "google_news_url",
        ""
    )

    if not google_url:
        return ""

    if "news.google.com" not in urlparse(
        google_url
    ).netloc:

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

            publisher_url = result.get(
                "decoded_url",
                ""
            )

            if valid_url(publisher_url):

                article["url"] = publisher_url

                article["publisher_url"] = publisher_url

                article["domain"] = domain_of(
                    publisher_url
                )

                logging.info(
                    "URL 해석 성공: %s",
                    article["domain"]
                )

                return publisher_url

        message = (
            result.get(
                "message",
                "URL 해석 실패"
            )
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

        extracted = clean_article_text(
            extracted
        )

        if len(extracted) < 100:

            article["content_status"] = "text_too_short"

            return article

        # 전문 전체가 아닌 일부 발췌만 저장
        article["content"] = (
            extracted[:MAX_CONTENT_LENGTH]
        )

        article["content_status"] = "success"

        article["content_fetched_at"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        # RSS 요약이 없으면 본문 앞부분 활용
        if not article.get("summary"):

            article["summary"] = clean(
                extracted[:300]
            )

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

    for index, article in enumerate(
        targets,
        start=1
    ):

        logging.info(
            "[%d/%d] %s",
            index,
            len(targets),
            article.get("title", "")[:60]
        )

        publisher_url = resolve_publisher_url(
            article
        )

        if publisher_url:

            extract_article(
                article,
                publisher_url
            )

        if index < len(targets):

            time.sleep(DECODE_INTERVAL)

    # 처리하지 않은 나머지 기사
    for article in articles[MAX_ARTICLES_TO_PROCESS:]:

        article["content_status"] = "not_attempted"

    return articles


# ==========================================
# 5. 기존 기사와 본문 재사용
# ==========================================

def load_previous_articles():

    if not OUT.exists():
        return {}

    try:

        data = json.loads(
            OUT.read_text(
                encoding="utf-8"
            )
        )

        return {
            article["id"]: article
            for article in data.get(
                "articles",
                []
            )
            if article.get("id")
        }

    except Exception as exc:

        logging.warning(
            "이전 뉴스 데이터 읽기 실패: %s",
            str(exc)
        )

        return {}


def preserve_previous_content(
    articles,
    previous
):

    for article in articles:

        old = previous.get(
            article["id"]
        )

        if not old:
            continue

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
# 6. 중복 기사 제거
# ==========================================

def remove_duplicates(articles):

    unique = {}

    for article in articles:

        article_id = article.get("id")

        if not article_id:
            continue

        if article_id not in unique:

            unique[article_id] = article

        else:

            existing = unique[article_id]

            # 기존 기사에 본문이 없고
            # 중복 기사에 본문이 있으면 본문 보존
            if (
                not existing.get("content")
                and article.get("content")
            ):

                existing["content"] = article["content"]

                existing["content_status"] = article.get(
                    "content_status",
                    "success"
                )

                existing["content_fetched_at"] = article.get(
                    "content_fetched_at",
                    ""
                )

            # 요약이 더 충실한 쪽을 사용
            if len(article.get("summary", "")) > len(
                existing.get("summary", "")
            ):

                existing["summary"] = article["summary"]

    result = list(unique.values())

    logging.info(
        "중복 제거: %d개 -> %d개",
        len(articles),
        len(result)
    )

    return result


# ==========================================
# 7. 전체 실행
# ==========================================

def main():

    if not SOURCES_FILE.exists():

        raise FileNotFoundError(
            "sources.json 파일을 찾을 수 없습니다."
        )

    sources = json.loads(
        SOURCES_FILE.read_text(
            encoding="utf-8"
        )
    )

    previous = load_previous_articles()

    collected = {}
    errors = []

    # RSS 수집
    logging.info(
        "Google News RSS 수집 시작"
    )

    for feed in sources:

        try:

            for article in fetch_feed(feed):

                article_id = article["id"]

                if article_id not in collected:

                    collected[article_id] = article

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
        key=lambda a: a.get(
            "published_at",
            ""
        ),
        reverse=True
    )

    logging.info(
        "RSS 기사 총 %d개",
        len(articles)
    )

    # 이전에 성공한 본문 재사용
    preserve_previous_content(
        articles,
        previous
    )

    # 본문이 없는 기사만 수집
    pending = [
        article
        for article in articles
        if article.get("content_status") != "success"
    ]

    processed = process_articles(
        pending
    )

    # 기존 성공 기사 + 새로 처리한 기사
    successful_ids = {
        article["id"]
        for article in processed
    }

    final_articles = [
        article
        for article in articles
        if article["id"] not in successful_ids
    ] + processed

    # 최종 중복 제거
    final_articles = remove_duplicates(
        final_articles
    )

    # 최신순 정렬
    final_articles.sort(
        key=lambda a: a.get(
            "published_at",
            ""
        ),
        reverse=True
    )

    # 통계
    success = sum(
        article.get("content_status") == "success"
        for article in final_articles
    )

    decode_failed = sum(
        article.get("content_status") == "url_decode_failed"
        for article in final_articles
    )

    other_failed = sum(
        article.get("content_status") in (
            "download_failed",
            "no_article_text",
            "text_too_short",
            "extraction_failed"
        )
        for article in final_articles
    )

    # JSON 저장
    payload = {

        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_articles": len(final_articles),

        "content_stats": {

            "success": success,

            "url_decode_failed": decode_failed,

            "other_failed": other_failed

        },

        "articles": final_articles,

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

    logging.info(
        "================================"
    )

    logging.info(
        "뉴스 수집 완료"
    )

    logging.info(
        "전체 기사: %d",
        len(final_articles)
    )

    logging.info(
        "본문 수집 성공: %d",
        success
    )

    logging.info(
        "URL 해석 실패: %d",
        decode_failed
    )

    logging.info(
        "본문 추출 실패: %d",
        other_failed
    )

    logging.info(
        "저장 위치: %s",
        OUT
    )

    logging.info(
        "================================"
    )


if __name__ == "__main__":
    main()
