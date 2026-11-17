const CATEGORIES=[["policy","정책·제도"],["industry","보험업계 뉴스"],["insurer","보험사 뉴스"],["product","보험상품·보장"],["claim","보험금·분쟁"],["healthcare","건강보험·의료제도"],["disease","질병·건강정보"],["medical","의료기술·치료"],["hospital","대학병원 뉴스"],["general","기타 건강·보험"]];
const $=s=>document.querySelector(s);let articles=[],activeCategory="all",activeFilter="all";let saved=new Set(JSON.parse(localStorage.getItem("mi-saved")||"[]"));
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const dateLabel=v=>{if(!v)return"날짜 미상";let d=new Date(v);return isNaN(d)?"날짜 미상":new Intl.DateTimeFormat("ko-KR",{year:"numeric",month:"2-digit",day:"2-digit"}).format(d)};
const catName=id=>CATEGORIES.find(c=>c[0]===id)?.[1]||"기타";
function renderNav(){$("#categoryNav").innerHTML=CATEGORIES.map(c=>`<button class="nav-item ${activeCategory===c[0]?"active":""}" data-category="${c[0]}">${c[1]}</button>`).join("");document.querySelectorAll("[data-category]").forEach(b=>b.onclick=()=>{activeCategory=b.dataset.category;activeFilter="all";render()});}
function score(a){let age=Date.now()-new Date(a.published_at||0).getTime();let recency=Number.isFinite(age)?Math.max(0,30-age/86400000):0;let important=/(개정|변경|발표|허가|신약|치료|암|보험금|실손|건강보험|분쟁|연구)/i.test(a.title)?8:0;return recency+important;}
function render(){
 document.querySelectorAll("[data-category]").forEach(b=>b.classList.toggle("active",b.dataset.category===activeCategory));
 document.querySelectorAll("[data-filter]").forEach(b=>b.classList.toggle("active",b.dataset.filter===activeFilter));
 let q=$("#searchInput").value.trim().toLowerCase(),now=Date.now();
 let list=articles.filter(a=>(activeCategory==="all"||a.category===activeCategory)&&[a.title,a.summary,a.source].join(" ").toLowerCase().includes(q));
 if(activeFilter==="saved")list=list.filter(a=>saved.has(a.id));
 else if(["7","30"].includes(activeFilter))list=list.filter(a=>a.published_at&&now-new Date(a.published_at).getTime()<=Number(activeFilter)*86400000);
 list.sort((a,b)=>($("#sortSelect").value==="old"?1:-1)*(new Date(a.published_at||0)-new Date(b.published_at||0)));
 $("#feedTitle").textContent=activeFilter==="saved"?"내 스크랩":activeCategory==="all"?"오늘의 핵심 뉴스 TOP 10":catName(activeCategory);
 $("#feedSubtitle").textContent=activeCategory==="all"?"최신성과 주요 키워드를 기준으로 선정한 브리핑입니다.": "선택한 분야의 최신 정보입니다.";
 $("#resultCount").textContent=`${list.length} ARTICLES`;
 let shown=activeCategory==="all"&&activeFilter==="all"&&!q?list.slice().sort((a,b)=>score(b)-score(a)).slice(0,10):list;
 $("#articleList").innerHTML=shown.map(a=>`<article class="article"><div><div class="article-top"><span class="tag">${esc(catName(a.category))}</span><span class="source-name">${esc(a.source||"출처 미상")}</span><span class="article-date">${dateLabel(a.published_at)}</span></div><h3>${esc(a.title)}</h3><p>${esc(a.summary||"원문에서 자세한 내용을 확인할 수 있습니다.")}</p><div class="article-bottom"><a class="read-link" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">원문 읽기 ↗</a><span class="article-domain">${esc(a.domain||"")}</span></div></div><button class="save-btn ${saved.has(a.id)?"saved":""}" data-save="${esc(a.id)}" aria-label="스크랩">${saved.has(a.id)?"★":"☆"}</button></article>`).join("");
 $("#emptyState").hidden=shown.length>0;$("#totalCount").textContent=articles.length;$("#savedCount").textContent=saved.size;
 let today=new Date().toISOString().slice(0,10);$("#todayCount").textContent=articles.filter(a=>(a.published_at||"").slice(0,10)===today).length;
 document.querySelectorAll("[data-save]").forEach(b=>b.onclick=()=>{let id=b.dataset.save;saved.has(id)?saved.delete(id):saved.add(id);localStorage.setItem("mi-saved",JSON.stringify([...saved]));render()});
}
async function load(){try{let r=await fetch(`data/news.json?v=${Date.now()}`,{cache:"no-store"});if(!r.ok)throw Error();let d=await r.json();articles=Array.isArray(d.articles)?d.articles:[];$("#updatedAt").textContent=d.updated_at?`수집 ${dateLabel(d.updated_at)}`:"수집 대기";if(d.notice){$("#notice").textContent=d.notice;$("#notice").hidden=false}else $("#notice").hidden=true;}catch(e){articles=[];$("#notice").textContent="뉴스 데이터를 불러오지 못했습니다. GitHub Pages 배포와 data/news.json을 확인해 주세요.";$("#notice").hidden=false;}
 $("#todayLabel").textContent=new Intl.DateTimeFormat("ko-KR",{year:"numeric",month:"long",day:"numeric",weekday:"long"}).format(new Date());$("#year").textContent=new Date().getFullYear();renderNav();render();}
document.querySelectorAll("[data-filter]").forEach(b=>b.onclick=()=>{activeFilter=b.dataset.filter;render()});$("#searchInput").oninput=render;$("#sortSelect").onchange=render;$("#refreshBtn").onclick=load;
document.querySelectorAll("[data-jump]").forEach(b=>b.onclick=()=>{let v=b.dataset.jump;if(v==="saved"){activeFilter="saved";activeCategory="all"}else if(v==="insurance"){activeCategory="industry";activeFilter="all"}else if(v==="health"){activeCategory="disease";activeFilter="all"}else if(v==="hospital"){activeCategory="hospital";activeFilter="all"}render();});

document.querySelectorAll(".bottom-link").forEach(b=>b.onclick=()=>{
  const v=b.dataset.jump;

  document.querySelectorAll(".bottom-link").forEach(x=>x.classList.remove("active"));
  b.classList.add("active");

  activeFilter="all";
  activeCategory="all";

  if(v==="saved"){
    activeFilter="saved";
  }else if(v==="insurance"){
    activeCategory="industry";
  }else if(v==="health"){
    activeCategory="disease";
  }else if(v==="hospital"){
    activeCategory="hospital";
  }

  render();

  window.scrollTo({top:0,behavior:"smooth"});
});

load();
