"""
PTAB PDF → Markdown 변환.

pdfminer.six로 텍스트 레이어를 추출하고 PTAB 문서 구조에 맞는
섹션화 Markdown으로 변환합니다. 이미지 기반(스캔) PDF는 OCR이
필요하다고 알려주되, 직접 수행하지는 않습니다.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# 페이지당 이 값보다 적으면 텍스트 레이어 없음으로 판단
_MIN_CHARS_PER_PAGE = 50

# 워터마크/페이지 라벨 패턴: "ExhibitName \nParty v Party \nIPR2021-XXXXX \nPage N of M"
_PAGE_LABEL_RE = re.compile(
    r'^.{0,80}\bpage\s+\d+\s+of\s+\d+\s*$',
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class PdfParseResult:
    markdown: str
    needs_ocr: bool
    # OCR이 필요한 페이지 번호 목록 (1-based)
    ocr_pages: list[int] = field(default_factory=list)
    # 전체 페이지 수
    total_pages: int = 0
    # YAML 프론트매터에 들어간 메타데이터
    metadata: dict = field(default_factory=dict)


def parse_pdf(pdf_path: str) -> PdfParseResult:
    """
    PDF를 읽어 PTAB 마크다운으로 변환합니다.

    텍스트 레이어가 있는 페이지는 pdfminer로 추출하고,
    텍스트가 거의 없는 페이지(이미지 기반)는 ocr_pages에 기록합니다.

    Returns:
        PdfParseResult — markdown 본문과 OCR 필요 여부 포함.
    """
    try:
        import pypdf
        from pdfminer.high_level import extract_text
    except ImportError as e:
        raise ImportError(
            f"PDF 파싱에 필요한 패키지가 없습니다: {e}\n"
            "설치: pip install pdfminer.six pypdf"
        ) from e

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {pdf_path}")

    # 페이지별 텍스트 추출 (pypdf로 개별 페이지 확인)
    reader = pypdf.PdfReader(str(path))
    total_pages = len(reader.pages)
    per_page_texts: list[str] = [p.extract_text() or "" for p in reader.pages]

    # OCR이 필요한 페이지 감지
    # - 텍스트 50자 미만: 이미지 기반
    # - (cid:XX) 패턴: 커스텀 폰트 인코딩 실패 (텍스트는 있지만 읽을 수 없음)
    # - 워터마크/페이지 라벨만 있는 페이지: 실제 텍스트 없음
    ocr_pages = [
        i + 1
        for i, t in enumerate(per_page_texts)
        if len(t.strip()) < _MIN_CHARS_PER_PAGE
        or _is_cid_encoded(t)
        or _is_label_only(t)
    ]
    needs_ocr = len(ocr_pages) > 0

    # 메타데이터 추출 (첫 페이지 기반)
    first_page = per_page_texts[0] if per_page_texts else ""
    metadata = _extract_metadata(first_page, path.name, total_pages)
    if needs_ocr:
        metadata["ocr_required"] = True
        metadata["ocr_pages_count"] = len(ocr_pages)

    # 마크다운 본문 생성
    # 전체가 이미지 기반인 경우: pdfminer 결과가 노이즈(워터마크 라벨만)이므로
    # 페이지별 pypdf 텍스트를 사용하고 이미지 페이지는 명시적 안내로 대체
    all_image = len(ocr_pages) == total_pages
    if all_image:
        md_body = _build_image_only_body(per_page_texts, ocr_pages, total_pages)
    else:
        # 일부만 이미지: pdfminer 전체 추출 사용 (레이아웃 품질 우선)
        full_text = extract_text(str(path))
        # pdfminer 결과도 CID 인코딩 실패인 경우 전체를 이미지 기반으로 처리
        if _is_cid_encoded(full_text):
            ocr_pages = list(range(1, total_pages + 1))
            needs_ocr = True
            metadata["ocr_required"] = True
            metadata["ocr_pages_count"] = total_pages
            md_body = _build_image_only_body(per_page_texts, ocr_pages, total_pages)
        else:
            md_body = _to_ptab_markdown(full_text, ocr_pages=set(ocr_pages))

    markdown = _build_frontmatter(metadata) + md_body

    return PdfParseResult(
        markdown=markdown,
        needs_ocr=needs_ocr,
        ocr_pages=ocr_pages,
        total_pages=total_pages,
        metadata=metadata,
    )


# ── 내부 함수 ─────────────────────────────────────────────────────────────────


def _is_cid_encoded(text: str) -> bool:
    """PDF 커스텀 폰트 인코딩 실패 감지: (cid:N) 시퀀스가 많으면 텍스트 레이어 사용 불가."""
    return text.count("(cid:") > 3


def _is_label_only(text: str) -> bool:
    """페이지 라벨/워터마크만 있는 페이지 감지.

    "ExhibitName \nParty v Party \nIPR2021-XXXXX \nPage N of M" 패턴처럼
    120자 미만이고 'Page N of M'으로 끝나면 실제 콘텐츠가 없는 것으로 판단.
    """
    clean = text.strip().replace("\x0c", "")
    if len(clean) > 150:
        return False
    return bool(_PAGE_LABEL_RE.match(clean))


def _extract_metadata(first_page_text: str, filename: str, total_pages: int) -> dict:
    """첫 페이지 텍스트에서 trial number, patent, 날짜를 추출합니다."""
    trial_m = re.search(r'(IPR|PGR|CBM|DER)\d{4}-\d{5}', first_page_text)
    patent_m = re.search(r'Patent ([\d,]+ B\d)', first_page_text)
    date_m = re.search(r'Date:\s*(\w+ \d+, \d{4})', first_page_text)

    # 문서 유형 추론 (파일명 기반 fallback)
    doc_type = _infer_doc_type(first_page_text, filename)

    return {
        "trial_number": trial_m.group(0) if trial_m else "",
        "patent": patent_m.group(1) if patent_m else "",
        "document_type": doc_type,
        "date": date_m.group(1) if date_m else "",
        "pages": total_pages,
        "source_file": filename,
    }


def _infer_doc_type(text: str, filename: str) -> str:
    """본문/파일명에서 문서 유형을 추론합니다."""
    text_upper = text.upper()
    filename_upper = filename.upper()
    combined = text_upper + " " + filename_upper

    if "FINAL WRITTEN DECISION" in combined:
        return "Final Written Decision"
    if "INSTITUTION DECISION" in combined or "INSTITUTION OF INTER PARTES" in combined:
        return "Institution Decision"
    if "PETITION" in combined and "PETITIONER" not in combined[:50]:
        return "Petition"
    if "PATENT OWNER" in combined and "RESPONSE" in combined:
        return "Patent Owner Response"
    if "PETITIONER" in combined and "REPLY" in combined:
        return "Petitioner Reply"
    if "ORDER" in combined:
        return "Order"
    if "EXHIBIT" in combined or "EX." in combined:
        return "Exhibit"
    return "Document"


def _build_frontmatter(meta: dict) -> str:
    """YAML 프론트매터 블록을 생성합니다."""
    lines = ["---"]
    if meta.get("trial_number"):
        lines.append(f"trial_number: {meta['trial_number']}")
    if meta.get("patent"):
        lines.append(f"patent: \"{meta['patent']}\"")
    if meta.get("document_type"):
        lines.append(f"document_type: {meta['document_type']}")
    if meta.get("date"):
        lines.append(f"date: {meta['date']}")
    lines.append(f"pages: {meta['pages']}")
    if meta.get("ocr_required"):
        lines.append("ocr_required: true")
        lines.append(f"ocr_pages_count: {meta['ocr_pages_count']}")
    if meta.get("source_file"):
        lines.append(f"source_file: {meta['source_file']}")
    lines.append("---\n\n")
    return "\n".join(lines)


def _build_image_only_body(
    per_page_texts: list[str],
    ocr_pages: list[int],
    total_pages: int,
) -> str:
    """
    전체 이미지 기반 PDF의 마크다운 본문을 생성합니다.

    pdfminer의 전체 추출 결과는 각 페이지의 워터마크 라벨만
    \x0c 구분자로 이어붙인 노이즈이므로 사용하지 않습니다.
    대신 페이지별 pypdf 텍스트를 기반으로 명시적 OCR 안내를 생성합니다.
    """
    ocr_set = set(ocr_pages)
    lines: list[str] = [
        "> **[Image-based PDF — OCR Required]**",
        f"> All {total_pages} pages contain scanned images. No text layer is available.",
        "> Open the source PDF directly or use OCR to read the content.",
        "",
    ]

    # 페이지별 워터마크/라벨이 있으면 표시, 없으면 빈 안내
    for i, text in enumerate(per_page_texts):
        page_num = i + 1
        label = text.strip().replace("\n", " ").replace("\x0c", "").strip()
        if page_num in ocr_set:
            if label and len(label) < 80:
                lines.append(f"<!-- Page {page_num}: {label} — image, OCR required -->")
            else:
                lines.append(f"<!-- Page {page_num}: image, OCR required -->")
        else:
            lines.append(f"<!-- Page {page_num}: {label} -->")

    return "\n".join(lines)


def _to_ptab_markdown(text: str, ocr_pages: set[int] | None = None) -> str:
    """
    pdfminer 추출 텍스트를 PTAB 섹션 구조에 맞는 마크다운으로 변환합니다.

    변환 규칙:
    - 로마 숫자 주요 섹션 (I. INTRODUCTION …)  → ## 헤더
    - 알파벳 서브섹션 (A. RELATED MATTERS …)   → ### 헤더
    - JUDGMENT / ORDER / CONCLUSION 키워드      → ## 헤더
    - 나머지 줄                                 → 원문 그대로

    pdfminer는 페이지 구분자로 \x0c(form feed)를 사용하므로
    \n과 함께 분리 기준으로 처리합니다.
    """
    # \x0c를 \n으로 교체한 뒤 분리 — form feed가 임베딩된 경우도 처리
    normalized = text.replace("\x0c", "\n")
    lines = normalized.split("\n")
    out: list[str] = []
    prev_blank = False

    for line in lines:
        raw = line.rstrip()
        s = raw.strip()

        # 빈 줄
        if not s:
            if not prev_blank:
                out.append("")
            prev_blank = True
            continue
        prev_blank = False

        # 로마 숫자 주요 섹션: "I.  INTRODUCTION", "II.  MOTION TO AMEND"
        # 조건: 80자 이하, 숫자+점+공백2개+대문자로 시작
        if re.match(r'^[IVX]+\.\s{2,}[A-Z]', s) and len(s) <= 80:
            out.append(f"\n## {s}")

        # 알파벳 서브섹션: "A.  RELATED MATTERS", "B.  APPLICABLE LAW"
        # 조건: 80자 이하, 공백2개+대문자 2개 이상 연속
        elif re.match(r'^[A-Z]\.\s{2,}[A-Z]{2}', s) and len(s) <= 80:
            out.append(f"\n### {s}")

        # 단독 키워드 헤더 (JUDGMENT, ORDER, CONCLUSION 등)
        elif s in {"JUDGMENT", "ORDER", "CONCLUSION", "ORDERED", "DECISION"}:
            out.append(f"\n## {s}")

        # 나머지: 원문 그대로
        else:
            out.append(raw)

    md = "\n".join(out)
    # 연속 빈 줄 3개 이상 → 2개로 정리
    md = re.sub(r'\n{4,}', '\n\n\n', md)
    return md


def save_markdown(result: PdfParseResult, out_path: str) -> str:
    """마크다운을 파일로 저장하고 절대 경로를 반환합니다."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(result.markdown, encoding="utf-8")
    return str(p.resolve())


def default_output_path(pdf_path: str) -> str:
    """PDF 경로에서 기본 .md 출력 경로를 생성합니다 (같은 디렉터리, 확장자만 변경)."""
    p = Path(pdf_path)
    return str(p.with_suffix(".md"))
