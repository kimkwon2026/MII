
const CATEGORIES = [
  ["policy", "정책·제도"],
  ["industry", "보험업계 뉴스"],
  ["insurer", "보험사 뉴스"],
  ["product", "보험상품·보장"],
  ["claim", "보험금·분쟁"],
  ["healthcare", "건강보험·의료제도"],
  ["disease", "질병·건강정보"],
  ["medical", "의료기술·치료"],
  ["hospital", "대학병원 뉴스"],
  ["general", "기타 건강·보험"]
];

const $ = s => document.querySelector(s);

let articles = [];
let activeCategory = "all";
let activeFilter = "all";
let activeSection = "home";

let saved = new Set(
  JSON.parse(localStorage.getItem("mi-saved") || "[]")
);

const INSURANCE_CATEGORIES = [
  "policy", "industry", "insurer",
  "product", "claim", "healthcare"
];

const HEALTH_CATEGORIES = [
  "disease", "medical", "general"
];

const esc = s => String(s ?? "").replace(
  /[&<>"']/g,
  c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[c])
);

const dateLabel = v => {
  if (!v) return "날짜 미상";
  const d = new Date(v);
  return isNaN(d)
    ? "날짜 미상"
    : new Intl.DateTimeFormat("ko-KR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit"
      }).format(d);
};

const catName = id =>
  CATEGORIES.find(c => c[0] === id)?.[1] || "기타";

function getSectionName() {
  const names = {
    home: "오늘의 핵심 뉴스 TOP 10",
    insurance: "보험 인사이트",
    health: "건강 인사이트",
    hospital: "대학병원 뉴스",
    saved: "내 스크랩"
  };
  return names[activeSection] || "오늘의 뉴스";
}

// 카테고리 메뉴
function renderNav() {
  const nav = $("#categoryNav");
  if (!nav) return;

  nav.innerHTML = CATEGORIES.map(c => `
    <button
      class="nav-item ${activeCategory === c[0] ? "active" : ""}"
      data-category="${c[0]}"
    >${c[1]}</button>
  `).join("");

  nav.querySelectorAll("[data-category]").forEach(b => {
    b.onclick = () => {
      activeSection = "category";
      activeCategory = b.dataset.category;
      activeFilter = "all";
      render();
    };
  });
}

// 뉴스 중요도 점수
function score(a) {
  const age = Date.now() -
    new Date(a.published_at || 0).getTime();

  const recency = Number.isFinite(age)
    ? Math.max(0, 30 - age / 86400000)
    : 0;

  const important =
    /(개정|변경|발표|허가|신약|치료|암|보험금|실손|건강보험|분쟁|연구)/i
      .test(a.title || "") ? 8 : 0;

  return recency + important;
}

// 하단 메뉴 콘텐츠 전환
function changeSection(section) {
  activeSection = section;
  activeCategory = "all";
  activeFilter = section === "saved" ? "saved" : "all";

  render();

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}

// 하단 메뉴 연결
function setupBottomNav() {
  document.querySelectorAll(".bottom-link").forEach(b => {
    b.onclick = () => {
      const value = (
        b.dataset.jump ||
        b.dataset.page ||
        b.dataset.tab ||
        b.textContent
      ).toLowerCase().trim();

      let section = "home";

      if (
        value.includes("saved") ||
        value.includes("scrap") ||
        value.includes("스크랩")
      ) {
        section = "saved";
      } else if (
        value.includes("insurance") ||
        value.includes("보험")
      ) {
        section = "insurance";
      } else if (
        value.includes("health") ||
        value.includes("건강")
      ) {
        section = "health";
      } else if (
        value.includes("hospital") ||
        value.includes("병원")
      ) {
        section = "hospital";
      } else if (
        value.includes("home") ||
        value.includes("홈")
      ) {
        section = "home";
      }

      changeSection(section);

      document.querySelectorAll(".bottom-link")
        .forEach(x => x.classList.remove("active"));

      b.classList.add("active");
    };
  });
}

// 화면 렌더링
function render() {
  const searchInput = $("#searchInput");
  const sortSelect = $("#sortSelect");

  const q = searchInput
    ? searchInput.value.trim().toLowerCase()
    : "";

  const now = Date.now();

  let list = articles.filter(a => {
    const categoryMatch =
      activeCategory === "all" ||
      a.category === activeCategory;

    let sectionMatch = true;

    if (activeSection === "insurance") {
      sectionMatch =
        INSURANCE_CATEGORIES.includes(a.category);
    }

    if (activeSection === "health") {
      sectionMatch =
        HEALTH_CATEGORIES.includes(a.category);
    }

    if (activeSection === "hospital") {
      sectionMatch = a.category === "hospital";
    }

    const searchMatch = [
      a.title,
      a.summary,
      a.source
    ].join(" ").toLowerCase().includes(q);

    return categoryMatch && sectionMatch && searchMatch;
  });

  // 스크랩 필터
  if (activeFilter === "saved") {
    list = list.filter(a => saved.has(a.id));
  }

  // 기간 필터
  else if (["7", "30"].includes(activeFilter)) {
    list = list.filter(a =>
      a.published_at &&
      now - new Date(a.published_at).getTime()
        <= Number(activeFilter) * 86400000
    );
  }

  // 정렬
  const sortOrder = sortSelect?.value === "old" ? 1 : -1;

  list.sort((a, b) =>
    sortOrder * (
      new Date(a.published_at || 0) -
      new Date(b.published_at || 0)
    )
  );

  // 제목과 설명
  if ($("#feedTitle")) {
    if (activeSection === "saved") {
      $("#feedTitle").textContent = "내 스크랩";
    } else if (activeSection !== "category") {
      $("#feedTitle").textContent = getSectionName();
    } else {
      $("#feedTitle").textContent = catName(activeCategory);
    }
  }

  if ($("#feedSubtitle")) {
    const subtitles = {
      home: "최신성과 주요 키워드를 기준으로 선정한 오늘의 브리핑입니다.",
      insurance: "보험정책, 보험사, 상품 및 보험금 관련 소식입니다.",
      health: "질병, 건강정보, 의료기술 관련 최신 소식입니다.",
      hospital: "대학병원과 의료기관의 주요 소식입니다.",
      saved: "관심 있는 뉴스로 저장한 기사입니다."
    };

    $("#feedSubtitle").textContent =
      activeSection === "category"
        ? "선택한 분야의 최신 정보입니다."
        : subtitles[activeSection] || "";
  }

  // 결과 개수
  if ($("#resultCount")) {
    $("#resultCount").textContent =
      `${list.length} ARTICLES`;
  }

  // 홈에서는 핵심 뉴스 10개
  let shown = list;

  if (
    activeSection === "home" &&
    activeCategory === "all" &&
    activeFilter === "all" &&
    !q
  ) {
    shown = list
      .slice()
      .sort((a, b) => score(b) - score(a))
      .slice(0, 10);
  }

  // 기사 목록
  const articleList = $("#articleList");

  if (articleList) {
    articleList.innerHTML = shown.map(a => `
      <article class="article">
        <div>
          <div class="article-top">
            <span class="tag">${esc(catName(a.category))}</span>
            <span class="source-name">${esc(a.source || "출처 미상")}</span>
            <span class="article-date">${dateLabel(a.published_at)}</span>
          </div>

          <h3>${esc(a.title)}</h3>

          <p>${esc(
            a.summary ||
            "원문에서 자세한 내용을 확인할 수 있습니다."
          )}</p>

          <div class="article-bottom">
            <a
              class="read-link"
              href="${esc(a.url)}"
              target="_blank"
              rel="noopener noreferrer"
            >원문 읽기 ↗</a>

            <span class="article-domain">
              ${esc(a.domain || "")}
            </span>
          </div>
        </div>

        <button
          class="save-btn ${saved.has(a.id) ? "saved" : ""}"
          data-save="${esc(a.id)}"
          aria-label="스크랩"
        >${saved.has(a.id) ? "★" : "☆"}</button>
      </article>
    `).join("");

    // 스크랩 버튼
    articleList.querySelectorAll("[data-save]").forEach(b => {
      b.onclick = () => {
        const id = b.dataset.save;

        if (saved.has(id)) {
          saved.delete(id);
        } else {
          saved.add(id);
        }

        localStorage.setItem(
          "mi-saved",
          JSON.stringify([...saved])
        );

        render();
      };
    });
  }

  // 검색 결과 없음
  if ($("#emptyState")) {
    $("#emptyState").hidden = shown.length > 0;
  }

  // 통계
  if ($("#totalCount")) {
    $("#totalCount").textContent = articles.length;
  }

  if ($("#savedCount")) {
    $("#savedCount").textContent = saved.size;
  }

  const today = new Date().toISOString().slice(0, 10);

  if ($("#todayCount")) {
    $("#todayCount").textContent =
      articles.filter(a =>
        (a.published_at || "").slice(0, 10) === today
      ).length;
  }

  // 카테고리 선택 표시
  document.querySelectorAll("[data-category]").forEach(b => {
    b.classList.toggle(
      "active",
      activeSection === "category" &&
      b.dataset.category === activeCategory
    );
  });

  // 기간 필터 표시
  document.querySelectorAll("[data-filter]").forEach(b => {
    b.classList.toggle(
      "active",
      b.dataset.filter === activeFilter
    );
  });
}

// 뉴스 데이터 불러오기
async function load() {
  try {
    const response = await fetch(
      `data/news.json?v=${Date.now()}`,
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error("뉴스 파일을 불러올 수 없습니다.");
    }

    const data = await response.json();

    articles = Array.isArray(data.articles)
      ? data.articles
      : [];

    if ($("#updatedAt")) {
      $("#updatedAt").textContent =
        data.updated_at
          ? `수집 ${dateLabel(data.updated_at)}`
          : "수집 대기";
    }

    if ($("#notice")) {
      if (data.notice) {
        $("#notice").textContent = data.notice;
        $("#notice").hidden = false;
      } else {
        $("#notice").hidden = true;
      }
    }

  } catch (error) {
    articles = [];

    if ($("#notice")) {
      $("#notice").textContent =
        "뉴스 데이터를 불러오지 못했습니다. GitHub Pages 배포와 data/news.json을 확인해 주세요.";

      $("#notice").hidden = false;
    }

    console.error(error);
  }

  if ($("#todayLabel")) {
    $("#todayLabel").textContent =
      new Intl.DateTimeFormat("ko-KR", {
        year: "numeric",
        month: "long",
        day: "numeric",
        weekday: "long"
      }).format(new Date());
  }

  if ($("#year")) {
    $("#year").textContent = new Date().getFullYear();
  }

  renderNav();
  render();
}

// 초기 이벤트 연결
function initialize() {
  // 하단 메뉴
  setupBottomNav();

  // 기간 필터
  document.querySelectorAll("[data-filter]").forEach(b => {
    b.onclick = () => {
      activeFilter = b.dataset.filter;
      render();
    };
  });

  // 검색
  if ($("#searchInput")) {
    $("#searchInput").oninput = render;
  }

  // 정렬
  if ($("#sortSelect")) {
    $("#sortSelect").onchange = render;
  }

  // 새로고침
  if ($("#refreshBtn")) {
    $("#refreshBtn").onclick = load;
  }

  // 데이터 로드
  load();
}

initialize();
