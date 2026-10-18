"""site.json과 content/*.html로 index.html, works/*.html, viewer.html을 만든다.

실행: py -I tools/build.py   (저장소 루트에서)
"""
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600'
         '&amp;family=Instrument+Serif:ital@0;1&amp;family=Noto+Serif+KR:wght@400;500;600&amp;display=swap" rel="stylesheet">')
PDFJS = '<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>'
ARROW_L = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>'
ARROW_R = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>'


def e(s):
    return html.escape(str(s), quote=True)


def head(title, desc, base, extra=""):
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="theme-color" content="#1e1d1b">
{FONTS}
<link rel="stylesheet" href="{base}assets/css/site.css">
{extra}
</head>
"""


def footer(site):
    o = site["owner"]
    return f"""<footer class="site-footer">
<div class="site-footer__about" id="about"><span class="label">About</span>{e(site["about"])}</div>
<div id="contact"><span class="label">Contact</span><a href="mailto:{e(o["email"])}">{e(o["email"])}</a></div>
</footer>"""


def type_cover(w, cls="cover cover--type"):
    return (f'<div class="{cls}"><span class="cover__no">{e(w["no"])}</span>'
            f'<div class="cover__foot"><span class="cover__title">{e(w["title"])}</span>'
            f'<span class="label">{e(w["typeShort"])}</span></div></div>')


def cover_html(w, base):
    if w.get("cover"):
        return f'<img class="cover" src="{base}{e(w["cover"])}" alt="{e(w.get("coverAlt", ""))}" loading="lazy">'
    return type_cover(w)


def work_href(w):
    return f'works/{w["slug"]}.html'


def pdf_viewer(doc, base, extra_attrs=""):
    src = base + doc["file"]
    return f"""<div class="pdfv" data-pdfv data-src="{e(src)}" tabindex="-1" {extra_attrs}>
<button class="pdfv__btn pdfv__prev" type="button" aria-label="이전 쪽" disabled>{ARROW_L}</button>
<figure class="pdfv__fig">
<div class="pdfv__stage" role="img" aria-label="{e(doc["title"])}"><span class="pdfv__status">문서를 불러오는 중…</span></div>
<figcaption class="pdfv__cap"><span>{e(doc["title"])}</span><span><span class="pdfv__now now">01</span> / <span class="pdfv__total">{int(doc.get("pages", 0)):02d}</span></span></figcaption>
</figure>
<button class="pdfv__btn pdfv__next" type="button" aria-label="다음 쪽">{ARROW_R}</button>
</div>
<noscript><p><a href="{e(src)}">PDF 열기</a></p></noscript>"""


def resolve_covers(site):
    """작품 표지가 비어 있으면 첫 문서의 표지 이미지를 쓴다."""
    for w in site["works"]:
        if not w.get("cover"):
            for d in w.get("docs", []):
                c = f'assets/img/covers/{d["id"]}.jpg'
                if (ROOT / c).exists():
                    w["cover"] = c
                    w.setdefault("coverAlt", d["title"] + " 표지")
                    break


def build_index(site):
    works = site["works"]
    o = site["owner"]
    base = ""
    data = [{
        "no": w["no"], "title": w["title"], "en": w["en"], "type": w["type"], "typeShort": w["typeShort"],
        "role": w["role"], "summary": w["summary"], "href": work_href(w),
        "cover": (w["cover"] if w.get("cover") else ""), "coverAlt": w.get("coverAlt", ""),
    } for w in works]
    rows = "\n".join(
        f'<a class="row{" is-active" if i == 0 else ""}" data-i="{i}" href="{work_href(w)}">'
        f'<span class="row__no">{e(w["no"])}</span><span class="row__title">{e(w["title"])}</span>'
        f'<span class="row__type">{e(w["typeShort"])}</span><span class="row__role">{e(w["role"])}</span>'
        f'<span class="row__year">{e(w["year"])}</span></a>' for i, w in enumerate(works))
    first = works[0]
    pv_img_hidden = "" if first.get("cover") else " hidden"
    pv_type_hidden = " hidden" if first.get("cover") else ""
    # 표지 보기 = 모든 문서를 표지로 진열한 서가. 거르기는 문서가 속한 작품의 분류로 한다.
    shelf = [(w, d) for w in works for d in w.get("docs", [])]
    cats = site["categories"]
    chips = ['<button class="chip" type="button" data-filter="all" aria-pressed="true">전체 {}</button>'.format(len(shelf))]
    for k, label in cats:
        n = sum(1 for w, _ in shelf if w["cat"] == k)
        if n:
            chips.append(f'<button class="chip" type="button" data-filter="{e(k)}" aria-pressed="false">{e(label)} {n}</button>')
    cards = []
    for w, d in shelf:
        cimg = f'assets/img/covers/{d["id"]}.jpg'
        cover = (f'<img class="cover" src="{e(cimg)}" alt="{e(d["title"])} 표지" loading="lazy">'
                 if (ROOT / cimg).exists() else type_cover(w))
        meta2 = " · ".join(x for x in [d.get("attribution", ""), d.get("note", "")] if x)
        cards.append(f"""<article class="card" data-cat="{e(w["cat"])}">
<a href="viewer.html?doc={e(d["id"])}" tabindex="-1" aria-hidden="true">{cover}</a>
<div class="card__meta"><span>{e(w["no"])} · {e(w["typeShort"])}</span><span>PDF · {int(d.get("pages", 0))}쪽</span></div>
<h3 class="card__title"><a href="viewer.html?doc={e(d["id"])}">{e(d["title"])}</a></h3>
<p class="card__role">{e(w["title"])}{(" — " + e(meta2)) if meta2 else ""}</p>
<div class="card__links"><a href="viewer.html?doc={e(d["id"])}">읽기 →</a><a href="{work_href(w)}">작품 설명 →</a></div>
</article>""")
    page = head(f'{o["ko"]} · {o["en"]} — 포트폴리오', site["description"], base) + f"""<body>
<header class="site-header">
<div class="site-header__id">{e(o["ko"])} · {e(o["en"])}<br>{e(site["tagline"])}</div>
<a class="site-header__logo" href="index.html">{e(o["en"])}</a>
<nav class="site-nav" aria-label="주 메뉴">
<a href="about.html">About</a><a href="#contact">Contact</a>
<div class="toggle" role="group" aria-label="보기 방식">
<button type="button" data-set-view="list" aria-pressed="true">목록</button>
<button type="button" data-set-view="shelf" aria-pressed="false">표지</button>
</div>
</nav>
</header>
<main>
<div class="index" data-view="list">
<section class="index__list" aria-label="작품 목록">
<h1 class="index__lede">{site["lede"]}</h1>
<div class="rows-scroll"><div class="rows">
<div class="rows__head" aria-hidden="true"><span>No.</span><span>Title</span><span>Type</span><span>Role</span><span class="row__year">Year</span></div>
{rows}
</div></div>
</section>
<aside class="index__preview" aria-label="선택한 작품 미리보기" data-preview>
<img class="cover" data-pv-img src="{e(first.get("cover", ""))}" alt="{e(first.get("coverAlt", ""))}"{pv_img_hidden}>
<div class="cover cover--type" data-pv-type{pv_type_hidden}><span class="cover__no" data-pv-no>{e(first["no"])}</span><div class="cover__foot"><span class="cover__title" data-pv-ctitle>{e(first["title"])}</span><span class="label" data-pv-ctype>{e(first["typeShort"])}</span></div></div>
<div class="preview__text">
<h2 class="preview__title" data-pv-title>{e(first["title"])}</h2>
<p class="preview__en" data-pv-en>{e(first["en"])}</p>
<p class="label" data-pv-meta>{e(first["type"])} / {e(first["role"])}</p>
<p class="preview__summary" data-pv-summary>{e(first["summary"])}</p>
<a class="btn-line" data-pv-link href="{work_href(first)}">자세히 보기 <span aria-hidden="true">→</span></a>
</div>
</aside>
</div>
<div class="shelf" data-view="shelf" hidden>
<div class="shelf__bar">
<p class="index__lede" style="margin:0">The shelf — <strong><span data-shown>{len(shelf)}</span> documents</strong></p>
<div class="shelf__filters" role="group" aria-label="종류로 거르기">{"".join(chips)}</div>
</div>
<div class="shelf__grid">
{"".join(cards)}
</div>
</div>
</main>
{footer(site)}
<script id="works-data" type="application/json">{json.dumps(data, ensure_ascii=False)}</script>
<script src="assets/js/index.js"></script>
</body>
</html>
"""
    (ROOT / "index.html").write_text(page, encoding="utf-8", newline="\n")


def build_work(site, i):
    works = site["works"]
    w = works[i]
    d = w["detail"]
    o = site["owner"]
    base = "../"
    n = len(works)
    byline = "\n".join(f'<div><dt>{e(k)}</dt><dd>{v}</dd></div>' for k, v in d["byline"])
    title_cls = "detail-head__title detail-head__title--en" if d.get("titleStyle") == "en" else "detail-head__title"
    sub_cls = "detail-head__sub detail-head__sub--ko" if d.get("subStyle") == "ko" else "detail-head__sub"
    docs = w.get("docs", [])
    imgs = w.get("images", [])
    media_imgs = [x for x in imgs if x.get("use") == "media"]
    gallery = [x for x in imgs if x.get("use") == "gallery"]
    media = ""
    if media_imgs:
        m = media_imgs[0]
        media = (f'<section class="media"><figure style="margin:0"><img class="media__img" src="{base}{e(m["path"])}" alt="{e(m["alt"])}">'
                 + (f'<figcaption class="pdfv__cap"><span>{e(m["alt"])}</span></figcaption>' if m.get("alt") else "")
                 + "</figure>" + (d.get("media_after", "")) + "</section>")
    elif docs:
        media = f'<section class="media" aria-label="문서 넘겨 보기">{pdf_viewer(docs[0], base)}</section>'
    elif d.get("media"):
        media = f'<section class="media">{d["media"]}</section>'
    body = (TOOLS / "content" / f'{w.get("content", w["slug"])}.html').read_text(encoding="utf-8")
    quote = f'<blockquote class="quote">{e(d["quote"])}</blockquote>' if d.get("quote") else ""
    gal = ""
    if gallery:
        gal = ('<section class="docs-list" aria-label="이미지"><p class="label" style="margin:0 0 18px">Gallery</p>'
               '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px">'
               + "".join(f'<img src="{base}{e(x["path"])}" alt="{e(x["alt"])}" loading="lazy" style="width:100%;aspect-ratio:16/9;object-fit:cover">' for x in gallery)
               + "</div></section>")
    doclist = ""
    if docs:
        items = "\n".join(
            f'<div class="doc-row"><span><span class="doc-row__t">{e(x["title"])}</span>'
            f'<span class="doc-row__m">PDF · {int(x.get("pages", 0))}쪽'
            f'{(" · " + e(x["attribution"])) if x.get("attribution") else ""}{(" · " + e(x["note"])) if x.get("note") else ""}</span></span>'
            f'<span class="doc-row__a"><a href="{base}viewer.html?doc={e(x["id"])}">보기</a><a href="{base}{e(x["file"])}" download>받기</a></span></div>'
            for x in docs)
        doclist = f'<section class="docs-list" aria-label="문서"><p class="label" style="margin:0 0 18px">Documents · {len(docs)}</p>{items}</section>'
    doclist = gal + doclist
    prev_w = works[i - 1] if i > 0 else None
    next_w = works[i + 1] if i < n - 1 else None
    prev_a = (f'<a href="{e(prev_w["slug"])}.html"><span class="label">← {e(prev_w["no"])}</span><span>{e(prev_w["title"])}</span></a>'
              if prev_w else f'<a href="{base}index.html"><span class="label">← Index</span><span>전체 목록</span></a>')
    next_a = (f'<a href="{e(next_w["slug"])}.html"><span class="label">{e(next_w["no"])} →</span><span>{e(next_w["title"])}</span></a>'
              if next_w else f'<a href="{base}index.html"><span class="label">Index →</span><span>전체 목록</span></a>')
    extra = PDFJS if docs else ""
    page = head(f'{w["title"]} — {o["ko"]} 포트폴리오', w["summary"], base, extra) + f"""<body>
<header class="site-header">
<a class="back-link" href="{base}index.html"><span aria-hidden="true">←</span> Index</a>
<a class="site-header__logo" href="{base}index.html">{e(o["en"])}</a>
<span class="pager-count">{e(w["no"])} / {n:02d}</span>
</header>
<main>
<article class="detail-head">
<p class="detail-head__eyebrow"><span class="accent">▸ {e(w["no"])}</span> · {e(d["eyebrow"])}</p>
<h1 class="{title_cls}">{d["title"]}</h1>
<p class="{sub_cls}">{d["sub"]}</p>
<dl class="byline">
{byline}
</dl>
</article>
{media}
<article class="prose">
{body}
{quote}
</article>
{doclist}
<nav class="next-nav" aria-label="이전·다음 작업">{prev_a}{next_a}</nav>
</main>
{footer(site)}
{'<script src="' + base + 'assets/js/pdfviewer.js"></script>' if docs else ''}
</body>
</html>
"""
    out = ROOT / "works" / f'{w["slug"]}.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8", newline="\n")


def build_about(site):
    """교육·수상·자격을 한 쪽에 모은 About 페이지."""
    o = site["owner"]
    pr = site["profile"]
    base = ""

    def wlink(slug, label):
        return f'<a href="works/{e(slug)}.html">{e(label)} →</a>'

    edu = "\n".join(
        f'<div class="doc-row"><span><span class="doc-row__m">{e(x["when"])}</span>'
        f'<span class="doc-row__t">{e(x["what"])}</span><span class="doc-row__m">{e(x["detail"])}</span></span>'
        f'<span class="doc-row__a">{"".join(wlink(s, l) for s, l in x.get("links", []))}</span></div>' for x in pr["education"])
    awards = []
    for x in pr["awards"]:
        acts = []
        if x.get("link"):
            acts.append(wlink(*x["link"]))
        if x.get("doc"):
            acts.append(f'<a href="viewer.html?doc={e(x["doc"])}">상장 보기 →</a>')
        awards.append(f'<div class="doc-row"><span><span class="doc-row__m">{e(x["when"])} · {e(x["by"])}</span>'
                      f'<span class="doc-row__t">{e(x["what"])}</span><span class="doc-row__m">{e(x["detail"])}</span></span>'
                      f'<span class="doc-row__a">{"".join(acts)}</span></div>')
    certs = "\n".join(f'<div class="doc-row"><span class="doc-row__t">{e(x["what"])}</span><span class="doc-row__m">{e(x["when"])}</span></div>'
                      for x in pr["certs"])
    page = head(f'About — {o["ko"]} 포트폴리오', f'{o["ko"]}({o["en"]})의 교육·수상·자격', base) + f"""<body>
<header class="site-header">
<a class="back-link" href="index.html"><span aria-hidden="true">←</span> Index</a>
<a class="site-header__logo" href="index.html">{e(o["en"])}</a>
<span class="pager-count">About</span>
</header>
<main>
<article class="detail-head">
<p class="detail-head__eyebrow"><span class="accent">▸</span> About · {e(o["ko"])} · {e(o["en"])}</p>
<h1 class="detail-head__title detail-head__title--en">About</h1>
<p class="detail-head__sub detail-head__sub--ko">{e(pr["intro"])}</p>
</article>
<section class="docs-list" aria-label="교육"><p class="label" style="margin:0 0 18px">Education</p>{edu}</section>
<section class="docs-list" aria-label="수상"><p class="label" style="margin:0 0 18px">Awards · {len(pr["awards"])}</p>{"".join(awards)}</section>
<section class="docs-list" aria-label="자격·어학"><p class="label" style="margin:0 0 18px">Certifications · Languages</p>{certs}</section>
<section class="docs-list" aria-label="연락처" style="padding-bottom:96px"><p class="label" style="margin:0 0 18px">Contact</p>
<div class="doc-row"><span class="doc-row__t">Email</span><span class="doc-row__a"><a href="mailto:{e(o["email"])}">{e(o["email"])}</a></span></div></section>
</main>
{footer(site)}
</body>
</html>
"""
    (ROOT / "about.html").write_text(page, encoding="utf-8", newline="\n")


def build_viewer(site):
    o = site["owner"]
    reg = {}
    for w in site["works"]:
        for d in w.get("docs", []):
            reg[d["id"]] = {"title": d["title"], "file": d["file"], "pages": d.get("pages", 0),
                            "meta": w["type"], "back": work_href(w), "note": d.get("note", "")}
    first_id = next(iter(reg)) if reg else ""
    first = reg.get(first_id, {"title": "", "file": "", "pages": 0, "meta": "", "back": "index.html", "note": ""})
    page = head(f'문서 보기 — {o["ko"]} 포트폴리오', "포트폴리오 문서 뷰어", "", PDFJS) + f"""<body class="viewer-page">
<header class="viewer-bar">
<a class="back-link" data-back href="{e(first["back"])}"><span aria-hidden="true">←</span> 닫기</a>
<div class="viewer-bar__title"><strong data-title>{e(first["title"])}</strong><span class="label" data-meta>{e(first["meta"])}</span></div>
<a class="back-link" data-download href="{e(first["file"])}" download>PDF 받기</a>
</header>
<main class="viewer-main">
{pdf_viewer({"title": first["title"], "file": first["file"], "pages": first["pages"]}, "", 'data-follow-url data-global-keys')}
</main>
<p class="label" style="text-align:center;margin:0 0 20px" data-note>{e(first["note"])}</p>
<script id="docs-data" type="application/json">{json.dumps(reg, ensure_ascii=False)}</script>
<script>
(function () {{
  var reg = JSON.parse(document.getElementById('docs-data').textContent);
  var id = new URLSearchParams(location.search).get('doc');
  var d = reg[id];
  if (!d) return;
  var v = document.querySelector('[data-pdfv]');
  v.setAttribute('data-src', d.file);
  v.querySelector('.pdfv__stage').setAttribute('aria-label', d.title);
  v.querySelector('.pdfv__cap span').textContent = d.title;
  document.querySelector('[data-title]').textContent = d.title;
  document.querySelector('[data-meta]').textContent = d.meta;
  document.querySelector('[data-note]').textContent = d.note;
  document.querySelector('[data-back]').href = d.back;
  document.querySelector('[data-download]').href = d.file;
  document.title = d.title + ' — 문서 보기';
}})();
</script>
<script src="assets/js/pdfviewer.js"></script>
</body>
</html>
"""
    (ROOT / "viewer.html").write_text(page, encoding="utf-8", newline="\n")


def main():
    site = json.loads((TOOLS / "site.json").read_text(encoding="utf-8"))
    resolve_covers(site)
    build_index(site)
    for i in range(len(site["works"])):
        build_work(site, i)
    build_viewer(site)
    build_about(site)
    print("built:", 3 + len(site["works"]), "pages")


if __name__ == "__main__":
    sys.exit(main())
