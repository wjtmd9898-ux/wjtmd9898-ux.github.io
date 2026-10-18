"""site.json과 content/*.html로 index.html(첫 화면), works.html(작업 목록·서가), works/*.html, viewer.html을 만든다.

실행: py tools/build.py   (저장소 루트에서)
- 첫 화면 전시용 작은 표지(assets/img/thumbs/)는 Pillow가 있으면 새로 만든다. 없으면 이미 있는 파일을 쓴다.
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


THUMB_H = 600  # 전시 표지 높이(px). 화면에서는 최대 300px로 보이니 2배 밀도다.


def jpeg_size(p):
    """JPEG 파일의 (가로, 세로). Pillow 없이 SOF 표지만 읽는다."""
    b = p.read_bytes()
    i = 2
    while i + 9 < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
        if m == 0xFF or 0xD0 <= m <= 0xD9 or m == 0x01:
            i += 1 if m == 0xFF else 2
            continue
        i += 2 + int.from_bytes(b[i + 2:i + 4], "big")
    raise ValueError(f"JPEG 크기를 못 읽음: {p}")


def make_thumbs(site):
    """문서 표지를 높이 THUMB_H로 줄인 전시용 사본을 만들고, 문서마다 썸네일 경로와 비율을 붙인다."""
    try:
        from PIL import Image
    except ImportError:
        Image = None
    out = ROOT / "assets" / "img" / "thumbs"
    out.mkdir(parents=True, exist_ok=True)
    for w in site["works"]:
        for d in w.get("docs", []):
            src = ROOT / "assets" / "img" / "covers" / f'{d["id"]}.jpg'
            dst = out / f'{d["id"]}.jpg'
            if not src.exists():
                continue
            if Image and (not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime):
                with Image.open(src) as im:
                    im = im.convert("RGB")
                    im.thumbnail((THUMB_H * 4, THUMB_H), Image.LANCZOS)
                    im.save(dst, "JPEG", quality=80, optimize=True, progressive=True)
            if dst.exists():
                tw, th = jpeg_size(dst)
                d["thumb"] = f'assets/img/thumbs/{d["id"]}.jpg'
                d["thumbW"], d["thumbH"] = tw, th


def build_works(site):
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
    page = head(f'Works — {o["ko"]} 포트폴리오', site["description"], base) + f"""<body>
<header class="site-header">
<div class="site-header__id">{e(o["ko"])} · {e(o["en"])}<br>{e(site["tagline"])}</div>
<a class="site-header__logo" href="index.html">{e(o["en"])}</a>
<nav class="site-nav" aria-label="주 메뉴">
<a href="index.html">About</a><a href="#contact">Contact</a>
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
    (ROOT / "works.html").write_text(page, encoding="utf-8", newline="\n")


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
              if prev_w else f'<a href="{base}works.html"><span class="label">← Works</span><span>전체 목록</span></a>')
    next_a = (f'<a href="{e(next_w["slug"])}.html"><span class="label">{e(next_w["no"])} →</span><span>{e(next_w["title"])}</span></a>'
              if next_w else f'<a href="{base}works.html"><span class="label">Works →</span><span>전체 목록</span></a>')
    extra = PDFJS if docs else ""
    page = head(f'{w["title"]} — {o["ko"]} 포트폴리오', w["summary"], base, extra) + f"""<body>
<header class="site-header">
<a class="back-link" href="{base}works.html"><span aria-hidden="true">←</span> Works</a>
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


def build_home(site):
    """첫 화면: 소개 한 문장 → 문서 표지 전시(가로로 흐름) → 교육·수상·자격을 넓은 화면에서 옆으로 펼친 프로필."""
    o = site["owner"]
    pr = site["profile"]
    works = site["works"]
    base = ""
    shelf = [(w, d) for w in works for d in w.get("docs", []) if d.get("thumb")]
    n_docs = sum(len(w.get("docs", [])) for w in works)

    def wlink(slug, label):
        return f'<a href="works/{e(slug)}.html">{e(label)} →</a>'

    # 전시: 같은 묶음을 두 번 이어 붙이고 트랙을 -50%만큼 흘려 끊김 없이 돈다. 두 번째 묶음은 보조기기와 탭 순서에서 뺀다.
    # 링크 글자(분류·제목)가 문서를 이미 말하니 표지 그림의 alt는 비운다.
    def ex_items(hidden):
        out = []
        for k, (w, d) in enumerate(shelf):
            r = d["thumbW"] / d["thumbH"]
            tab = ' tabindex="-1"' if hidden else ""
            load = "eager" if (k < 6 and not hidden) else "lazy"
            out.append(
                f'<li class="ex-item" style="--r:{r:.4f}"><a href="viewer.html?doc={e(d["id"])}"{tab}>'
                f'<img src="{e(d["thumb"])}" width="{d["thumbW"]}" height="{d["thumbH"]}" alt="" loading="{load}" decoding="async">'
                f'<span class="ex-item__meta">{e(w["no"])} · {e(w["typeShort"])}</span>'
                f'<span class="ex-item__t">{e(d["title"])}</span></a></li>')
        return "".join(out)

    # 흐르는 속도를 대략 초당 45px로 맞춘다(넓은 화면 표지 높이 300px 기준).
    set_w = sum(300 * d["thumbW"] / d["thumbH"] + 32 for _, d in shelf)
    dur = max(60, round(set_w / 45))

    def item(when, what, detail="", links=""):
        return (f'<div class="pf"><span class="pf__when">{e(when)}</span><span class="pf__what">{e(what)}</span>'
                + (f'<span class="pf__detail">{e(detail)}</span>' if detail else "")
                + (f'<span class="pf__links">{links}</span>' if links else "") + "</div>")

    edu = "".join(item(x["when"], x["what"], x["detail"], "".join(wlink(s, l) for s, l in x.get("links", []))) for x in pr["education"])
    awards = []
    for x in pr["awards"]:
        acts = [wlink(*x["link"])] if x.get("link") else []
        if x.get("doc"):
            acts.append(f'<a href="viewer.html?doc={e(x["doc"])}">상장 보기 →</a>')
        awards.append(item(f'{x["when"]} · {x["by"]}', x["what"], x["detail"], "".join(acts)))
    certs = "".join(item(x["when"], x["what"]) for x in pr["certs"])

    page = head(f'{o["ko"]} · {o["en"]} — 포트폴리오', site["description"], base) + f"""<body>
<header class="site-header">
<div class="site-header__id">{e(o["ko"])} · {e(o["en"])}<br>{e(site["tagline"])}</div>
<a class="site-header__logo" href="index.html">{e(o["en"])}</a>
<nav class="site-nav" aria-label="주 메뉴">
<a href="works.html#list">Works</a><a href="works.html#shelf">Shelf</a><a href="#contact">Contact</a>
</nav>
</header>
<main>
<section class="hero" aria-labelledby="hero-title">
<div class="hero__main">
<p class="hero__eyebrow"><span class="accent">▸</span> {e(o["ko"])} · {e(o["en"])} — {e(site["tagline"].split(" — ")[0])}</p>
<h1 class="hero__title" id="hero-title">{pr["headline"]}</h1>
<div class="hero__actions">
<a class="btn-solid" href="works.html#list">작업 보기 <span aria-hidden="true">→</span></a>
<a class="btn-line" href="works.html#shelf">문서 서가 <span aria-hidden="true">→</span></a>
</div>
</div>
<dl class="hero__stats">
<div><dt>Works</dt><dd>{len(works)}</dd></div>
<div><dt>Documents</dt><dd>{n_docs}</dd></div>
<div><dt>Awards</dt><dd>{len(pr["awards"])}</dd></div>
</dl>
</section>
<section class="exhibit" aria-label="문서 표지 전시">
<div class="exhibit__bar">
<p class="label">Exhibition — {len(shelf)} documents · 표지를 누르면 바로 읽습니다</p>
<button class="exhibit__toggle" type="button" data-marquee-toggle>멈춤</button>
</div>
<div class="marquee" data-marquee style="--dur:{dur}s">
<div class="marquee__track">
<ul class="marquee__set">{ex_items(False)}</ul>
<ul class="marquee__set" aria-hidden="true">{ex_items(True)}</ul>
</div>
</div>
</section>
<section class="profile" id="profile" aria-label="프로필">
<div class="profile__col"><h2 class="label">Education</h2>{edu}</div>
<div class="profile__col"><h2 class="label">Awards · {len(pr["awards"])}</h2>{"".join(awards)}</div>
<div class="profile__col"><h2 class="label">Certifications · Languages</h2>{certs}
<h2 class="label profile__sub">Contact</h2>{item("Email", o["email"], links=f'<a href="mailto:{e(o["email"])}">메일 보내기 →</a>')}</div>
</section>
</main>
{footer(site)}
<script src="assets/js/home.js"></script>
</body>
</html>
"""
    (ROOT / "index.html").write_text(page, encoding="utf-8", newline="\n")
    # 예전 주소(about.html)로 들어오면 첫 화면의 프로필로 보낸다.
    (ROOT / "about.html").write_text(
        '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><title>About — 허승 포트폴리오</title>'
        '<link rel="canonical" href="index.html#profile"><meta http-equiv="refresh" content="0; url=index.html#profile">'
        '</head><body style="background:#1e1d1b;color:#ece8df"><p><a href="index.html#profile" style="color:#c8a772">첫 화면으로 이동</a></p></body></html>\n',
        encoding="utf-8", newline="\n")


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
    make_thumbs(site)
    build_home(site)
    build_works(site)
    for i in range(len(site["works"])):
        build_work(site, i)
    build_viewer(site)
    print("built:", 3 + len(site["works"]), "pages + about.html redirect")


if __name__ == "__main__":
    sys.exit(main())
