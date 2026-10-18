"""마크다운(노션 fetch 결과나 저장소의 .md)을 읽기 좋은 A4 PDF로 만든다. Edge headless로 인쇄한다.

실행: py tools/md_to_pdf.py <입력.md> <출력.pdf> --title "제목" [--byline "작성: 허승 · 2026.03"] [--note "팀원 실명은 가렸습니다"]
- 입력 마크다운 안의 HTML(<table>, <details> 등)은 그대로 둔다. 노션의 <callout>은 상자로 바꾼다.
- 이미지는 입력 파일 기준 상대 경로의 로컬 파일만 넣는다. 원격 주소는 [이미지] 표시로 바꾼다.
- 중간 HTML은 tools/build/md/ 아래에 남는다(gitignore 대상).
"""
import argparse
import html
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = ROOT / "tools" / "build" / "md"
EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"

CSS = """
@page { size: A4; margin: 18mm 18mm 20mm; }
body { font-family: 'IBM Plex Sans KR', 'Malgun Gothic', sans-serif; font-size: 10.5pt; line-height: 1.7; color: #1e1d1b; }
.doc-head { border-bottom: 1px solid #1e1d1b; padding-bottom: 10mm; margin-bottom: 8mm; }
.doc-head .kicker { font-size: 8pt; letter-spacing: .14em; text-transform: uppercase; color: #6e6a62; }
.doc-head h1 { font-family: 'Noto Serif KR', serif; font-weight: 500; font-size: 24pt; line-height: 1.3; margin: 4mm 0 2mm; }
.doc-head .byline { font-size: 9pt; color: #4a4741; }
.doc-head .note { font-size: 8.5pt; color: #8c877d; margin-top: 2mm; }
h1, h2, h3, h4 { font-family: 'Noto Serif KR', serif; font-weight: 600; line-height: 1.4; page-break-after: avoid; }
h1 { font-size: 17pt; } h2 { font-size: 14pt; margin-top: 8mm; } h3 { font-size: 12pt; margin-top: 6mm; } h4 { font-size: 11pt; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 9pt; page-break-inside: auto; }
td, th { border: 1px solid #cfcac0; padding: 1.6mm 2.2mm; vertical-align: top; }
tr:first-child td { background: #f1eee7; font-weight: 600; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f1eee7; padding: 0 1mm; }
pre { background: #f1eee7; padding: 3mm; white-space: pre-wrap; font-size: 8.5pt; }
blockquote, .callout { margin: 3mm 0; padding: 2mm 4mm; border-left: 2px solid #c8a772; background: #faf8f3; }
img { max-width: 100%; }
.img-missing { display: inline-block; padding: 2mm 3mm; border: 1px dashed #b5afa4; color: #8c877d; font-size: 8.5pt; }
ul, ol { padding-left: 6mm; } li { margin: .6mm 0; }
hr { border: 0; border-top: 1px solid #cfcac0; margin: 6mm 0; }
details > summary { font-weight: 600; }
"""

FONTS = ('<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;600'
         '&family=Noto+Serif+KR:wght@500;600&display=swap" rel="stylesheet">')


def inline(s, base):
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!~|>])", r"\1", s)
    s = re.sub(r"`([^`]+)`", lambda m: "<code>" + html.escape(m.group(1)) + "</code>", s)

    def img(m):
        alt, src = m.group(1), m.group(2)
        if re.match(r"^(https?:|notion-file|attachment:)", src):
            return f'<span class="img-missing">[이미지{": " + html.escape(alt) if alt else ""}]</span>'
        p = (base / src).resolve()
        return f'<img src="{p.as_uri()}" alt="{html.escape(alt)}">' if p.exists() else '<span class="img-missing">[이미지]</span>'

    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)", img, s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", s)
    s = re.sub(r"<mention-[a-z]+[^>]*>([^<]*)</mention-[a-z]+>", r"\1", s)
    s = re.sub(r"<mention-[a-z]+[^>]*/>", "", s)
    return s


def md_to_html(md, base):
    out, para, stack, quote, table = [], [], [], [], []
    in_code = False

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para), base) + "</p>")
            para.clear()

    def close_lists(level=0):
        while len(stack) > level:
            out.append(f"</{stack.pop()}>")

    def flush_quote():
        if quote:
            out.append("<blockquote>" + "<br>".join(inline(q, base) for q in quote) + "</blockquote>")
            quote.clear()

    def flush_table():
        if table:
            rows = [r for r in table if not re.match(r"^\|?\s*:?-{2,}", r.replace("|", "", 1).strip() or "x")]
            cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            out.append("<table>" + "".join("<tr>" + "".join(f"<td>{inline(c, base)}</td>" for c in cells(r)) + "</tr>" for r in rows) + "</table>")
            table.clear()

    for raw in md.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            flush(); close_lists(); flush_quote(); flush_table()
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(raw)); continue
        s = line.strip()
        if s.startswith("|"):
            flush(); close_lists(); flush_quote(); table.append(s); continue
        flush_table()
        if s.startswith(">"):
            flush(); close_lists()
            q = s.lstrip(">").strip()
            if q:
                quote.append(q)
            continue
        flush_quote()
        if not s:
            flush(); close_lists(); continue
        m = re.match(r"^(#{1,6})\s+(.*)", s)
        if m:
            flush(); close_lists()
            n = min(len(m.group(1)) + 1, 4)
            out.append(f"<h{n}>{inline(m.group(2), base)}</h{n}>"); continue
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)", line.replace("\t", "  "))
        if m:
            flush()
            level = len(m.group(1)) // 2 + 1
            kind = "ol" if m.group(2)[0].isdigit() else "ul"
            while len(stack) < level:
                stack.append(kind); out.append(f"<{kind}>")
            close_lists(level)
            text = re.sub(r"^\[( |x)\]\s*", lambda c: "☑ " if c.group(1) == "x" else "☐ ", m.group(3))
            out.append(f"<li>{inline(text, base)}</li>"); continue
        if re.match(r"^(-{3,}|\*{3,})$", s):
            flush(); close_lists(); out.append("<hr>"); continue
        if s.startswith("<"):
            flush(); close_lists()
            s2 = re.sub(r"<callout[^>]*>", '<div class="callout">', s).replace("</callout>", "</div>")
            s2 = s2.replace("<empty-block/>", "")
            out.append(inline(s2, base)); continue
        para.append(s)
    flush(); close_lists(); flush_quote(); flush_table()
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--title", required=True)
    ap.add_argument("--kicker", default="Seung Huh — Portfolio Document")
    ap.add_argument("--byline", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    src = pathlib.Path(a.src)
    body = md_to_html(src.read_text(encoding="utf-8"), src.parent)
    head = (f'<div class="doc-head"><div class="kicker">{html.escape(a.kicker)}</div><h1>{html.escape(a.title)}</h1>'
            + (f'<div class="byline">{html.escape(a.byline)}</div>' if a.byline else "")
            + (f'<div class="note">{html.escape(a.note)}</div>' if a.note else "") + "</div>")
    doc = f'<!doctype html><html lang="ko"><head><meta charset="utf-8">{FONTS}<style>{CSS}</style></head><body>{head}{body}</body></html>'
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = WORK / (pathlib.Path(a.out).stem + ".html")
    tmp.write_text(doc, encoding="utf-8")
    out = pathlib.Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([EDGE, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=15000",
                    f"--print-to-pdf={out}", tmp.resolve().as_uri()], check=True, timeout=180,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("pdf:", out, round(out.stat().st_size / 1048576, 2), "MB")


if __name__ == "__main__":
    main()
