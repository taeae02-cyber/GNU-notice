# -*- coding: utf-8 -*-
"""
본문 이미지(포스터 등)를 우리 저장소에 복사해 두는 모듈.

왜: 학교 서버 이미지는 외부 사이트에서 불러올 때 막히거나 느릴 수 있어서,
    수집할 때 한 번 내려받아 docs/data/img/ 에 작게 저장해 두고 사이트는 그걸 보여줌.
크기: 가로 최대 1200px, JPEG 품질 82 → 보통 60~150KB.
"""
import io
import logging

from . import fetch, store

log = logging.getLogger("gnu.images")

IMG_DIR = store.DATA / "img"
MAX_IMAGES = 4          # 글 하나당 최대 저장 장수
MAX_WIDTH = 1200
MIN_SIZE = 120          # 이보다 작은 그림(아이콘·구분선)은 저장 안 함
JPEG_QUALITY = 82


def _to_jpeg(im):
    from PIL import Image
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        src = im.convert("RGBA")
        bg.paste(src, mask=src.split()[-1])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    if im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, max(1, int(im.height * MAX_WIDTH / im.width))))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return out.getvalue(), im


def fetch_and_store(notice_id, images):
    """
    images: parse_detail 이 준 [{"src":..., "alt":...}, ...]
    반환: (local 경로가 채워진 images, PIL 이미지 목록[OCR용])
    저장 실패한 항목은 "local": None 으로 표시해 다음 실행에서 다시 시도하지 않음.
    """
    if not images:
        return images, []
    try:
        from PIL import Image
    except ImportError:
        log.info("pillow 가 없어 이미지를 저장하지 않음")
        return images, []
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    pil_list = []
    for i, img in enumerate(images):
        if i >= MAX_IMAGES:
            img["local"] = None
            continue
        if "local" in img:          # 이미 시도한 항목 (성공이든 실패든) 은 건너뜀
            continue
        img["local"] = None
        data = fetch.get_bytes(img["src"])
        if not data:
            continue
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
            if im.width < MIN_SIZE or im.height < MIN_SIZE:
                continue
            jpg, im2 = _to_jpeg(im)
        except Exception as e:
            log.warning("이미지 변환 실패 %s: %s", img["src"][-50:], e)
            continue
        name = f"{notice_id}-{i}.jpg"
        (IMG_DIR / name).write_bytes(jpg)
        img["local"] = f"data/img/{name}"
        img["w"], img["h"] = im2.width, im2.height
        pil_list.append(im2)
    return images, pil_list


def remove_for(notice_id):
    """글이 지워질 때 딸린 이미지도 삭제."""
    if not IMG_DIR.exists():
        return
    for f in IMG_DIR.glob(f"{notice_id}-*.jpg"):
        try:
            f.unlink()
        except OSError:
            pass


def prune(valid_ids):
    """저장소에 남아 있지만 주인 글이 없는 이미지 정리."""
    if not IMG_DIR.exists():
        return 0
    removed = 0
    for f in IMG_DIR.glob("*.jpg"):
        nid = f.name.rsplit("-", 1)[0]
        if nid not in valid_ids:
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
    return removed
