# -*- coding: utf-8 -*-
"""HTTP 요청 담당. 요청 사이에 쉬고, 실패하면 두 번까지 다시 시도."""
import time
import logging
import requests

from . import config

log = logging.getLogger("gnu.fetch")

_session = requests.Session()
_session.headers.update({
    "User-Agent": config.USER_AGENT,
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
})
_last_request_at = 0.0


def _wait():
    global _last_request_at
    gap = time.monotonic() - _last_request_at
    if gap < config.REQUEST_DELAY:
        time.sleep(config.REQUEST_DELAY - gap)
    _last_request_at = time.monotonic()


def get(url, params=None, retries=2):
    """GET 요청. 성공하면 (text, final_url), 실패하면 (None, url)."""
    for attempt in range(retries + 1):
        _wait()
        try:
            r = _session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
            if r.status_code == 200:
                if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
                    r.encoding = r.apparent_encoding or "utf-8"
                return r.text, r.url
            log.warning("HTTP %s: %s", r.status_code, r.url)
        except requests.RequestException as e:
            log.warning("요청 실패 (%s/%s): %s - %s", attempt + 1, retries + 1, url, e)
        time.sleep(2 * (attempt + 1))
    return None, url


def post(url, data=None, retries=2):
    """POST 요청 (페이지 이동이 폼 전송 방식인 게시판용)."""
    for attempt in range(retries + 1):
        _wait()
        try:
            r = _session.post(url, data=data, timeout=config.REQUEST_TIMEOUT)
            if r.status_code == 200:
                if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
                    r.encoding = r.apparent_encoding or "utf-8"
                return r.text, r.url
            log.warning("HTTP %s: %s", r.status_code, r.url)
        except requests.RequestException as e:
            log.warning("요청 실패 (%s/%s): %s - %s", attempt + 1, retries + 1, url, e)
        time.sleep(2 * (attempt + 1))
    return None, url


def get_bytes(url, max_bytes=6_000_000):
    """이미지 등 바이너리 다운로드. 너무 크면 None."""
    _wait()
    try:
        r = _session.get(url, timeout=config.REQUEST_TIMEOUT, stream=True)
        if r.status_code != 200:
            return None
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf.extend(chunk)
            if len(buf) > max_bytes:
                return None
        return bytes(buf)
    except requests.RequestException as e:
        log.warning("다운로드 실패: %s - %s", url, e)
        return None
