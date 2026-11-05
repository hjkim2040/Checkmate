#!/usr/bin/env python3
"""
DOCX → 벡터스토어용 JSON 변환기
(단일 파일 또는 폴더 전체 일괄 처리)

사용 예시
────────
# 단일 파일
python docx_to_json.py 근로기준법.docx 근로기준법.json

# 폴더 안 DOCX 전부 → 같은 폴더에 JSON 생성
python docx_to__json.py ./laws --batch

# 폴더 안 DOCX 전부 → 별도 출력 폴더에 JSON 생성
python docx_to_json.py ./laws --batch --out-dir ./json_out
"""

import argparse
import json
import re
from pathlib import Path

from docx import Document


# ──────────────────────────────────────────────
# 1. 유틸
# ──────────────────────────────────────────────
ARTICLE_RE = re.compile(r"^제\s*\d+[가-힣·\d]*\s*조(?:\s*의\s*\d+)?")

def extract_title(header: str) -> str:
    m = re.search(
        r"제\s*\d+[가-힣·\d]*\s*조(?:\s*의\s*\d+)?\s*\(([^)]+)\)",
        header,
    )
    return m.group(1).strip() if m else ""


def parse_docx(path: Path):
    doc = Document(path)
    current, articles = None, []

    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        if ARTICLE_RE.match(txt):
            if current:
                articles.append(current)
            current = {"header": txt}
        elif current:
            current["header"] += " " + txt

    if current:
        articles.append(current)
    return articles


def convert_articles(articles, law_name, entry_type):
    converted = []
    for art in articles:
        header = art["header"]
        m_num = re.match(r"(제\s*\d+[가-힣·\d]*\s*조(?:\s*의\s*\d+)?)", header)
        article_number = m_num.group(1).replace(" ", "") if m_num else ""
        converted.append(
            {
                "content": header,
                "title": extract_title(header),
                "type": entry_type,
                "law_name": law_name,
                "article_number": article_number,
            }
        )
    return converted


def convert_single(docx_path: Path, out_path: Path, entry_type: str):
    law_name = docx_path.parent.name
    arts = parse_docx(docx_path)
    data = convert_articles(arts, law_name, entry_type)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ {docx_path.name}: {len(data):,}개 조문 → {out_path.name}")


# ──────────────────────────────────────────────
# 2. CLI
# ──────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="DOCX 파일 또는 폴더 경로")
    ap.add_argument("output", nargs="?", help="단일 파일 모드일 때 출력 JSON 경로")
    ap.add_argument("--batch", action="store_true",
                    help="폴더 내 모든 DOCX를 일괄 변환")
    ap.add_argument("--out-dir", default=None,
                    help="--batch 모드: 출력 JSON 저장 폴더 (없으면 src 폴더)")
    ap.add_argument("--law-name", default="근로기준법")
    ap.add_argument("--type", default="법률조문")
    args = ap.parse_args()

    src_path = Path(args.src).expanduser().resolve()

    # ── (A) 폴더 일괄 모드 ─────────────────────────
    if args.batch:
        if not src_path.is_dir():
            ap.error("--batch 옵션은 폴더 경로에서만 사용할 수 있습니다.")

        out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else src_path
        out_dir.mkdir(parents=True, exist_ok=True)

        docx_files = list(src_path.rglob("*.docx"))
        if not docx_files:
            print("⚠️  폴더에 DOCX 파일이 없습니다.")
            return

        for docx in docx_files:
            out_path = out_dir / f"{docx.stem}.json"
            convert_single(docx, out_path, args.type)

    # ── (B) 단일 파일 모드 ─────────────────────────
    else:
        if not src_path.is_file() or src_path.suffix.lower() != ".docx":
            ap.error("단일 파일 모드에서는 .docx 파일 경로를 src로 지정하세요.")
        if not args.output:
            ap.error("단일 파일 모드에서는 <output.json> 인자를 추가하세요.")

        out_path = Path(args.output).expanduser().resolve()
        convert_single(src_path, out_path, args.type)


if __name__ == "__main__":
    main()
