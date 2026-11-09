# -*- coding: utf-8 -*-
"""본문이 그림(포스터)뿐인 공지의 글자를 읽어내는 OCR (선택 기능).

테서랙트(tesseract)가 설치돼 있을 때만 동작하고, 없으면 조용히 건너뜀.
GitHub Actions 에서는 워크플로가 자동으로 설치하므로 거기서는 항상 동작함.
윈도우에서 쓰려면: https://github.com/UB-Mannheim/tesseract/wiki 에서 설치 + 한국어(kor) 선택.
"""
import io
import logging

from . import fetch

log = logging.getLogger("gnu.ocr")
_available = None
MAX_IMAGES = 3
MAX_CHARS = 3000


def available():
    global _available
    if _available is not None:
        return _available
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages(config="") if hasattr(pytesseract, "get_languages") else []
        _available = (not langs) or ("kor" in langs)
        if not _available:
            log.info("테서랙트에 한국어(kor) 데이터가 없어 OCR 을 건너뜀")
    except Exception:
        _available = False
        log.info("OCR 사용 안 함 (tesseract 미설치) — GitHub 자동 수집에서는 동작함")
    return _available


def read_pil(pil_images):
    """이미 내려받은 PIL 이미지 목록 → 인식한 글자 (없으면 '')"""
    if not available() or not pil_images:
        return ""
    import pytesseract
    texts = []
    for im in pil_images[:MAX_IMAGES]:
        try:
            g = im.convert("L")
            if g.width > 1800:
                g = g.resize((1800, int(g.height * 1800 / g.width)))
            txt = pytesseract.image_to_string(g, lang="kor+eng", config="--psm 6")
        except Exception as e:
            log.warning("OCR 실패: %s", e)
            continue
        txt = "\n".join(ln.strip() for ln in txt.splitlines() if len(ln.strip()) >= 2)
        if len(txt) >= 20:
            texts.append(txt)
    return "\n\n".join(texts)[:MAX_CHARS]


def read_images(images):
    """이미지 URL 목록 → 인식한 글자 (없으면 '')"""
    if not available() or not images:
        return ""
    import pytesseract
    from PIL import Image
    texts = []
    for img in images[:MAX_IMAGES]:
        data = fetch.get_bytes(img["src"])
        if not data:
            continue
        try:
            im = Image.open(io.BytesIO(data))
            im = im.convert("L")
            if im.width > 1800:
                im = im.resize((1800, int(im.height * 1800 / im.width)))
            txt = pytesseract.image_to_string(im, lang="kor+eng", config="--psm 6")
        except Exception as e:
            log.warning("OCR 실패 %s: %s", img["src"][-40:], e)
            continue
        txt = "\n".join(ln.strip() for ln in txt.splitlines() if len(ln.strip()) >= 2)
        if len(txt) >= 20:
            texts.append(txt)
    out = "\n\n".join(texts)[:MAX_CHARS]
    return out
