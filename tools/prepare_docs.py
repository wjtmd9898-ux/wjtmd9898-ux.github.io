"""원본 문서를 공개용 PDF로 만든다: (PPTX/DOCX면 PDF로 변환) → 개인정보 가리기 → 표지 이미지 → 점검.

docs.json 항목 예:
  {"id": "brown-dust-2", "src": "C:/.../브라운더스트2 분석서_허승.pdf",
   "auto": true,                      # 전화·이메일·학번·주민번호 패턴을 찾아 가린다
   "terms": ["홍길동"],                 # 추가로 가릴 글자(팀원 실명 등)
   "rects": [{"page": 1, "rect": [734, 464, 926, 520]}],   # 좌표로 가릴 곳(pt)
   "drop_pages": [],                  # 빼고 올릴 쪽(1부터)
   "cover_page": 1}
  태그 구조(/ActualText·/Alt)와 XMP 속성은 기본으로 지운다. 가린 글자가 거기에 원문으로 남기 때문이다.
  꼭 남겨야 하면 "keep_tags": true (그때는 점검의 hidden-* 결과를 직접 확인할 것).

실행: py -I tools/prepare_docs.py            (전부)
      py -I tools/prepare_docs.py brown-dust-2 (하나만)
원본 파일은 읽기만 한다. 결과는 docs/<id>.pdf, assets/img/covers/<id>.jpg, tools/build/docs_report.json.
"""
import json
import pathlib
import re
import subprocess
import sys

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
WORK = TOOLS / "build"
OUT_DOCS = ROOT / "docs"
OUT_COVERS = ROOT / "assets" / "img" / "covers"

PATTERNS = {
    "phone": re.compile(r"01[016789][-. ]?\d{3,4}[-. ]?\d{4}"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "student_id": re.compile(r"(?<!\d)20\d{8}(?!\d)"),
    "rrn": re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)"),
}


def convert(src: pathlib.Path) -> pathlib.Path:
    """Office로 PPTX/DOCX를 PDF로 바꾼다. 결과는 tools/build/converted/ 아래."""
    out_dir = WORK / "converted"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (src.stem + ".pdf")
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    ext = src.suffix.lower()
    if ext in (".pptx", ".ppt"):
        ps = (f"$a=New-Object -ComObject PowerPoint.Application; "
              f"$p=$a.Presentations.Open('{src}', $true, $false, $false); "
              f"$p.SaveAs('{out}', 32); $p.Close(); $a.Quit()")
    elif ext in (".docx", ".doc"):
        ps = (f"$a=New-Object -ComObject Word.Application; $a.Visible=$false; $a.DisplayAlerts=0; "
              f"$d=$a.Documents.Open('{src}', $false, $true); "
              f"$d.ExportAsFixedFormat('{out}', 17); $d.Close($false); $a.Quit()")
    else:
        raise ValueError(f"변환할 수 없는 형식: {src}")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], check=True, timeout=600)
    return out


def find_pii(text):
    hits = []
    for kind, rx in PATTERNS.items():
        for m in rx.finditer(text):
            hits.append((kind, m.group(0)))
    return hits


# PDF 객체 속 숨은 글자: 태그의 /ActualText·/Alt, 주석·양식의 /T·/TU·/Contents, 속성 칸.
HIDDEN_RX = re.compile(r"/(ActualText|Alt|E|T|TU|Contents|Subject|Keywords)(?![A-Za-z])\s*"
                       r"(<[0-9A-Fa-f\s]*>|\((?:[^()\\]|\\.)*\))")


def strip_hidden(doc):
    """가린 글자가 태그 구조나 XMP 속성에 그대로 남지 않도록 지운다.

    PowerPoint·Word로 내보낸 PDF는 화면 글자와 따로 구조 트리(/ActualText)에 원문을 한 번 더 담는다.
    가리기는 화면 글자만 지우므로, 구조 트리를 두면 이메일·전화번호가 파일 안에 남는다.
    """
    cat = doc.pdf_catalog()
    for key in ("StructTreeRoot", "MarkInfo"):
        doc.xref_set_key(cat, key, "null")
    for page in doc:
        doc.xref_set_key(page.xref, "StructParents", "null")
    doc.del_xml_metadata()


def hidden_strings(doc):
    """결과 PDF의 모든 객체에서 숨은 글자를 꺼낸다(웹 주소는 뺀다)."""
    found = []
    for x in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(x)
        except Exception:
            continue
        for m in HIDDEN_RX.finditer(obj):
            v = m.group(2)
            if v.startswith("<"):
                h = re.sub(r"\s", "", v[1:-1])
                try:
                    b = bytes.fromhex(h + "0" * (len(h) % 2))
                except ValueError:
                    continue
                s = b[2:].decode("utf-16-be", "replace") if b[:2] == b"\xfe\xff" else b.decode("latin-1")
            else:
                s = v[1:-1]
            if not s.startswith("http"):
                found.append(s)
    return found


def open_source(item):
    """src 하나 또는 srcs 여러 개(순서대로 이어 붙임)를 PDF 문서로 연다."""
    srcs = item.get("srcs") or [item["src"]]
    doc = None
    for s in srcs:
        p = pathlib.Path(s)
        part = pymupdf.open(p if p.suffix.lower() == ".pdf" else convert(p))
        if doc is None:
            doc = part
        else:
            doc.insert_pdf(part)
    return doc


def prepare(item):
    doc = open_source(item)
    if item.get("remove_links"):
        for page in doc:
            for ln in list(page.get_links()):
                page.delete_link(ln)
    drop = sorted({p - 1 for p in item.get("drop_pages", [])}, reverse=True)
    for p in drop:
        doc.delete_page(p)
    masked = []
    terms = list(item.get("terms", []))
    for pno, page in enumerate(doc, start=1):
        # 줄 단위로 본다. 번호가 여러 조각(span)으로 나뉘어 있어도 그 줄 전체를 가린다.
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(sp["text"] for sp in line["spans"])
                hit = any(t in text for t in terms)
                if item.get("auto", True) and find_pii(text):
                    hit = True
                if hit:
                    page.add_redact_annot(pymupdf.Rect(line["bbox"]), fill=(1, 1, 1))
                    masked.append({"page": pno, "kind": "line"})
        for rr in item.get("rects", []):
            if rr["page"] == pno:
                page.add_redact_annot(pymupdf.Rect(rr["rect"]), fill=tuple(rr.get("fill", (1, 1, 1))))
                masked.append({"page": pno, "kind": "rect"})
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)
    comp = item.get("compress")
    if comp and hasattr(doc, "rewrite_images"):
        # 큰 이미지 PDF(스캔·이미지로만 된 발표본)를 웹용으로 줄인다.
        doc.rewrite_images(dpi_threshold=comp.get("dpi", 150) + 10, dpi_target=comp.get("dpi", 150),
                           quality=comp.get("quality", 75))
    if not item.get("keep_tags"):
        strip_hidden(doc)
    doc.set_metadata({"title": item.get("title", ""), "author": "Seung Huh"})
    OUT_DOCS.mkdir(parents=True, exist_ok=True)
    out = OUT_DOCS / f'{item["id"]}.pdf'
    doc.save(out, garbage=4, deflate=True, clean=True)
    pages = doc.page_count

    cp = item.get("cover_page", 1) - 1
    pg = doc[cp]
    zoom = 1600 / pg.rect.width
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    OUT_COVERS.mkdir(parents=True, exist_ok=True)
    cover = OUT_COVERS / f'{item["id"]}.jpg'
    pix.save(cover, jpg_quality=82)
    doc.close()

    # 점검: 결과 PDF를 다시 열어 남은 개인정보 패턴과 가릴 글자를 찾는다.
    chk = pymupdf.open(out)
    left = []
    for pno, page in enumerate(chk, start=1):
        t = page.get_text()
        for kind, s in find_pii(t):
            left.append({"page": pno, "kind": kind})
        for s in terms:
            if s in t:
                left.append({"page": pno, "kind": "term"})
    for s in hidden_strings(chk):
        for kind, _ in find_pii(s):
            left.append({"page": 0, "kind": "hidden-" + kind})
        if any(t in s for t in terms):
            left.append({"page": 0, "kind": "hidden-term"})
    meta = chk.metadata
    chk.close()
    return {"id": item["id"], "pages": pages, "masked": len(masked), "left": left,
            "size_mb": round(out.stat().st_size / 1048576, 2), "meta_author": meta.get("author", "")}


def load_items():
    """tools/docs.json과 tools/docs.d/*.json(묶음별 파일)을 합친다."""
    items = json.loads((TOOLS / "docs.json").read_text(encoding="utf-8"))
    for f in sorted((TOOLS / "docs.d").glob("*.json")):
        items += json.loads(f.read_text(encoding="utf-8"))
    return items


def main(argv):
    items = load_items()
    if argv:
        items = [x for x in items if x["id"] in argv]
    WORK.mkdir(exist_ok=True)
    report = [prepare(x) for x in items]
    (WORK / "docs_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in report:
        flag = "OK" if not r["left"] else f"남음 {len(r['left'])}"
        print(f'{r["id"]}: {r["pages"]}쪽 {r["size_mb"]}MB 가림 {r["masked"]} 점검 {flag}')


if __name__ == "__main__":
    main(sys.argv[1:])
