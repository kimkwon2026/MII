const CATEGORIES = [
  ["policy","정책·제도","보험업법, 금융당국, 제도 개정"],
  ["industry","보험업계 뉴스","보험시장, 손해율, 업계 동향"],
  ["insurer","보험사 뉴스","주요 생명·손해보험사 소식"],
  ["product","보험상품·보장","신상품, 특약, 약관, 보장"],
  ["claim","보험금·분쟁","보험금 지급, 민원, 분쟁조정"],
  ["healthcare","건강보험·의료제도","건강보험, 실손, 비급여"],
  ["disease","질병·건강정보","암, 심뇌혈관, 만성질환"],
  ["medical","의료기술·치료","신약, 수술, 임상, 치료기술"],
  ["hospital","대학병원 뉴스","주요 상급종합병원 연구·소식"],
  ["general","기타 건강·보험","관련 주요 뉴스"]
];
const $ = s => document.querySelector(s);
let articles = [], activeCategory = "all", activeFilter = "all";
let saved = new Set(JSON.parse(localStorage.getItem("mi-saved") || "[]"));
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function dateLabel(value) {
  if (!value) return "날짜 미상";
  const d = new Date(value);
  return isNaN(d) ? "날짜 미상" : new Intl.DateTimeFormat("ko-KR",{year:"numeric",month:"2-digit",day:"2-digit"}).format(d);
}
function categoryName(id){return CATEGORIES.find(c=>c[0]===id)?.[1] || "기타";}
function renderNav(){
  const html = CATEGORIES.map(c=>`<button class="nav-item ${activeCategory===c[0]?"active":""}" data-category="${c[0]}"><span>·</span>${c[1]}</button>`).join("");
  $("#categoryNav").innerHTML=html;
  document.querySelectorAll("[data-category]").forEach(b=>b.addEventListener("click",()=>{activeCategory=b.dataset.category;activeFilter="all";syncControls();render();}));
}
function syncControls(){
  document.querySelectorAll("[data-category]").forEach(b=>b.classList.toggle("active",b.dataset.category===activeCategory));
  document.querySelectorAll("[data-filter]").forEach(b=>b.classList.toggle("active",b.dataset.filter===activeFilter));
  const c=CATEGORIES.find(x=>x[0]===activeCategory);
  $("#feedTitle").textContent=activeCategory==="all"?"전체 브리핑":c[1];
  $("#feedSubtitle").textContent=activeCategory==="all"?"보험과 건강 분야의 주요 소식을 모았습니다.":c[2];
}
function render(){
  syncControls();
  const q=$("#searchInput").value.trim().toLowerCase();
  const now=Date.now();
  let list=articles.filter(a=>{
    const cat=activeCategory==="all"||a.category===activeCategory;
    const text=[a.title,a.summary,a.source,a.category].join(" ").toLowerCase().includes(q);
    let time=true;
    if(activeFilter==="saved") time=saved.has(a.id);
    else if(activeFilter!=="all" && a.published_at){time=now-new Date(a.published_at).getTime()<=Number(activeFilter)*86400000;}
    return cat&&text&&time;
  });
  list.sort((a,b)=>(new Date(b.published_at||0)-new Date(a.published_at||0))*(($("#sortSelect").value==="old")?-1:1));
  $("#resultCount").textContent=`${list.length} ARTICLES`;
  $("#articleList").innerHTML=list.map(a=>`
    <article class="article">
      <div>
        <div class="article-top"><span class="tag">${esc(categoryName(a.category))}</span><span class="source-name">${esc(a.source||"출처 미상")}</span><span class="article-date">${dateLabel(a.published_at)}</span></div>
        <h3>${esc(a.title)}</h3>
        <p>${esc(a.summary||"원문에서 자세한 내용을 확인할 수 있습니다.")}</p>
        <div class="article-bottom"><a class="read-link" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">원문 읽기 ↗</a><span class="article-domain">${esc(a.domain||"")}</span></div>
      </div>
      <button class="save-btn ${saved.has(a.id)?"saved":""}" data-save="${esc(a.id)}" title="스크랩" aria-label="스크랩">${saved.has(a.id)?"★":"☆"}</button>
    </article>`).join("");
  $("#emptyState").hidden=list.length!==0;
  $("#totalCount").textContent=articles.length;
  $("#allBadge").textContent=articles.length;
  $("#savedCount").textContent=saved.size;
  document.querySelectorAll("[data-save]").forEach(b=>b.addEventListener("click",()=>toggleSave(b.dataset.save)));
}
function toggleSave(id){if(saved.has(id))saved.delete(id);else saved.add(id);localStorage.setItem("mi-saved",JSON.stringify([...saved]));render();}
async function load(){
  $("#notice").hidden=true;
  try{
    const r=await fetch(`data/news.json?v=${Date.now()}`,{cache:"no-store"});
    if(!r.ok)throw new Error("뉴스 데이터 파일을 불러오지 못했습니다.");
    const data=await r.json();articles=Array.isArray(data.articles)?data.articles:[];
    $("#updatedAt").textContent=data.updated_at?`마지막 수집 ${dateLabel(data.updated_at)}`:"뉴스 데이터 준비 완료";
    if(!articles.length)$("#notice").textContent="아직 수집된 기사가 없습니다. GitHub Actions 실행 후 다시 확인해 주세요.";
    else if(data.notice)$("#notice").textContent=data.notice;
    $("#notice").hidden=!$("#notice").textContent;
  }catch(e){
    articles=[];
    $("#notice").textContent="뉴스 데이터를 불러오지 못했습니다. data/news.json 파일과 GitHub Pages 배포 상태를 확인해 주세요.";
    $("#notice").hidden=false;
    $("#updatedAt").textContent="데이터 연결 확인 필요";
  }
  $("#todayLabel").textContent=new Intl.DateTimeFormat("ko-KR",{year:"numeric",month:"long",day:"numeric",weekday:"long"}).format(new Date());
  $("#year").textContent=new Date().getFullYear();
  renderNav();render();
}
document.querySelectorAll("[data-filter]").forEach(b=>b.addEventListener("click",()=>{activeFilter=b.dataset.filter;render();}));
$("#searchInput").addEventListener("input",render);
$("#sortSelect").addEventListener("change",render);
$("#refreshBtn").addEventListener("click",load);
load();
