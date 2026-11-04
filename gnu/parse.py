# -*- coding: utf-8 -*-
"""경상국립대 게시판(na/ntt 계열) 목록·상세 페이지 파싱.

학교 사이트 HTML 구조가 바뀌어도 최대한 버티도록 여러 단계의 추측(fallback)을 둡니다.
파싱이 안 되면 crawl.py 를 --debug 로 실행해 debug/ 폴더에 저장된 HTML 을 확인하세요.
"""
import re
import logging
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup, NavigableString

log = logging.getLogger("gnu.parse")

DATE_RE = re.compile(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})")
DATE2_RE = re.compile(r"\b(\d{2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\b")
NTTSN_RE = re.compile(r"nttSn\s*[=:]\s*['\"]?(\d+)", re.I)
NTTSN_INPUT_RE = re.compile(r"name\s*=\s*['\"]nttSn['\"][^>]*value\s*=\s*['\"](\d+)", re.I)
NTTSN_PATH_RE = re.compile(r"nttSn/(\d+)", re.I)
CHROME_MARKS = ("전체메뉴", "정보를 확인할 수 있습니다", "홈으로 이동", "본문으로 바로가기", "메인메뉴 바로가기")
NTTSN_ATTR_RE = re.compile(r"data-(?:ntt-?sn|id|param)\s*=\s*['\"]?(\d{3,})", re.I)
ONCLICK_NUM_RE = re.compile(r"\(\s*['\"]?(\d{4,})['\"]?\s*[,)]")
NEW_MARK_RE = re.compile(r"(새로운\s*글|새\s*글|NEW|new|신규)\s*$")
VIEWS_RE = re.compile(r"조회\s*수?\s*[:：]?\s*([\d,]+)")


def soup_of(html):
    return BeautifulSoup(html, "html.parser")


def clean(text):
    if text is None:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def parse_date(text):
    """'2026.11.02', '2026-11-2', '26.11.02' 같은 문자열 → 'YYYY-MM-DD'. 못 찾으면 None."""
    if not text:
        return None
    m = DATE_RE.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = DATE2_RE.search(text)
        if not m:
            return None
        y, mo, d = 2000 + int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def parse_int(text):
    if not text:
        return None
    m = re.search(r"[\d,]+", text)
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 목록 페이지
# ---------------------------------------------------------------------------

def _find_board_table(soup):
    best, best_score = None, 0
    for table in soup.find_all("table"):
        heads = [clean(th.get_text()) for th in table.find_all("th")]
        head_text = " ".join(heads)
        score = 0
        if "제목" in head_text:
            score += 2
        if "등록일" in head_text or "날짜" in head_text or "작성일" in head_text:
            score += 1
        if "번호" in head_text:
            score += 1
        rows = table.find_all("tr")
        if len(rows) >= 2:
            score += 1
        if score > best_score:
            best, best_score = table, score
    return best if best_score >= 3 else None


def _column_index(heads, *names):
    for i, h in enumerate(heads):
        for n in names:
            if n in h:
                return i
    return None


def _extract_ntt_sn(row_html):
    for rx in (NTTSN_RE, NTTSN_ATTR_RE, NTTSN_INPUT_RE, NTTSN_PATH_RE):
        m = rx.search(row_html)
        if m:
            return m.group(1)
    # onclick="fn_view('9134921')" 같은 형태
    for attr_m in re.finditer(r"onclick\s*=\s*\"([^\"]*)\"|onclick\s*=\s*'([^']*)'", row_html, re.I):
        onclick = attr_m.group(1) or attr_m.group(2) or ""
        m = ONCLICK_NUM_RE.search(onclick)
        if m:
            return m.group(1)
    return None


def _strip_new_mark(title):
    title = re.sub(r"\s+", " ", title or "").strip()
    t = NEW_MARK_RE.sub("", title).strip()
    return t or title


def page_status(html):
    """목록 페이지 상태: 'login'(로그인 필요) / 'empty'(글 없음) / 'ok'"""
    if "잘못된 접속 정보" in html or ("loginPage.do" in html and len(html) < 2000):
        return "login"
    if "등록된 게시물이 없습니다" in html:
        return "empty"
    return "ok"


def _row_from_container(el, a, board_url):
    """li/div 한 칸(사진형·에피소드형 목록)에서 글 정보 뽑기"""
    title = ""
    for sel in [".lst_tit", ".tit", ".subject", ".title", "strong"]:
        t = el.select_one(sel)
        if t and clean(t.get_text()):
            title = clean(t.get_text())
            break
    if not title:
        title = clean(a.get("title") or "") or clean(a.get_text())
    title = _strip_new_mark(title)
    if not title or title in ("자세히보기", "더보기"):
        return None
    ntt_sn = _extract_ntt_sn(str(a)) or _extract_ntt_sn(str(el))
    text = clean(el.get_text(" "))
    date = None
    d = el.select_one(".date, .day, .regdate, .reg_date, [class*='date']")
    if d:
        date = parse_date(d.get_text())
    if not date:
        m = re.search(r"(등록일|작성일|게시일)\s*[:：]?\s*(\d{4}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2})", text)
        if m:
            date = parse_date(m.group(2))
    dept = ""
    w = el.select_one(".name, .writer, .dept, .nm, .author")
    if w:
        dept = clean(w.get_text())[:60]
    views = None
    m = re.search(r"조회\s*수?\s*[:：]?\s*([\d,]+)", text)
    if m:
        views = parse_int(m.group(1))
    detail_url = None
    href = a.get("href") or ""
    if "selectNttInfo" in href:
        detail_url = urljoin(board_url, href)
    elif ntt_sn:
        detail_url = build_detail_url(board_url, ntt_sn)
    return {"ntt_sn": ntt_sn, "title": title, "dept": dept, "date": date, "views": views, "detail_url": detail_url}


def parse_list(html, board_url):
    """목록 페이지 → (rows, pager)
    rows  : [{ntt_sn, title, dept, date, views, detail_url}]
    pager : {page_param, size_param, size_options, total, form_action} (모르면 None 값)
    """
    soup = soup_of(html)
    rows = []
    table = _find_board_table(soup)
    if table is not None:
        heads = [clean(th.get_text()) for th in table.find_all("th")]
        i_title = _column_index(heads, "제목")
        i_dept = _column_index(heads, "부서", "작성자", "담당", "글쓴이")
        i_date = _column_index(heads, "등록일", "날짜", "작성일", "일자")
        i_views = _column_index(heads, "조회")
        body = table.find("tbody") or table
        for tr in body.find_all("tr"):
            tds = tr.find_all("td")
            if not tds or (len(tds) == 1 and "없습니다" in tds[0].get_text()):
                continue
            row_html = str(tr)
            title_td = None
            if i_title is not None and i_title < len(tds):
                title_td = tds[i_title]
            else:
                for td in tds:
                    if td.find("a"):
                        title_td = td
                        break
            if title_td is None:
                continue
            link = title_td.find("a")
            title = clean(link.get("title") or "") if link and link.get("title") else ""
            if not title:
                title = clean(link.get_text()) if link else clean(title_td.get_text())
            title = _strip_new_mark(title)
            if not title:
                continue
            ntt_sn = _extract_ntt_sn(str(link)) if link else None
            if not ntt_sn:
                ntt_sn = _extract_ntt_sn(row_html)
            dept = clean(tds[i_dept].get_text()) if i_dept is not None and i_dept < len(tds) else ""
            date = parse_date(tds[i_date].get_text()) if i_date is not None and i_date < len(tds) else None
            if date is None:
                date = parse_date(clean(tr.get_text(" ")))
            views = parse_int(tds[i_views].get_text()) if i_views is not None and i_views < len(tds) else None
            detail_url = None
            if link and link.get("href") and "selectNttInfo" in link.get("href"):
                detail_url = urljoin(board_url, link.get("href"))
            elif ntt_sn:
                detail_url = build_detail_url(board_url, ntt_sn)
            rows.append({"ntt_sn": ntt_sn, "title": title, "dept": dept, "date": date,
                         "views": views, "detail_url": detail_url})

    if not rows:
        # 사진형(photo_list) / 에피소드형 / 그 밖의 li 목록: 글 링크(a.selectNttInfo, data-param, nttInfoBtn)
        anchors = soup.select("a.selectNttInfo, a.nttInfoBtn, a[data-nm='nttSn'], a[href*='selectNttInfo']")
        seen = set()
        for a in anchors:
            el = a.find_parent(["li", "tr", "article"]) or a.find_parent("div") or a
            key = id(el)
            if key in seen:
                continue
            seen.add(key)
            row = _row_from_container(el, a, board_url)
            if row:
                rows.append(row)

    pager = _detect_pager(soup, board_url)
    return rows, pager


def _detect_pager(soup, board_url):
    info = {"page_param": None, "size_param": None, "size_options": [], "total": None, "form_action": None}
    # 전체 N건
    m = re.search(r"전체\s*([\d,]+)\s*건", soup.get_text(" "))
    if m:
        info["total"] = parse_int(m.group(1))
    # 페이지 크기 select (10/20/30/40/50)
    for sel in soup.find_all("select"):
        values = [o.get("value", "").strip() for o in sel.find_all("option")]
        if {"10", "20", "30"} <= set(values) and sel.get("name"):
            info["size_param"] = sel.get("name")
            info["size_options"] = [v for v in values if v.isdigit()]
            form = sel.find_parent("form")
            if form is not None and form.get("action"):
                info["form_action"] = urljoin(board_url, form.get("action"))
            break
    # 페이지 번호 hidden input
    for inp in soup.find_all("input", attrs={"type": "hidden"}):
        name = inp.get("name") or ""
        if re.search(r"(currPage|pageIndex|pageNo|page)", name, re.I) and "size" not in name.lower() and "unit" not in name.lower():
            info["page_param"] = name
            break
    if info["page_param"] is None:
        # 페이지 링크 href 에서 추측
        for a in soup.find_all("a", href=True):
            m = re.search(r"[?&](currPage|pageIndex|pageNo|page)=\d+", a["href"], re.I)
            if m:
                info["page_param"] = m.group(1)
                break
    return info


def build_detail_url(board_url, ntt_sn):
    """목록 주소(selectNttList.do?mi=..&bbsId=..) → 상세 주소."""
    p = urlparse(board_url)
    q = parse_qs(p.query)
    keep = {k: v[0] for k, v in q.items() if k in ("mi", "bbsId")}
    keep["nttSn"] = str(ntt_sn)
    path = p.path.replace("selectNttList.do", "selectNttInfo.do")
    return urlunparse((p.scheme, p.netloc, path, "", urlencode(keep), ""))


def build_list_url(board_url, pager, page=1, size=None):
    p = urlparse(board_url)
    q = {k: v[0] for k, v in parse_qs(p.query).items()}
    if pager.get("page_param") and page > 1:
        q[pager["page_param"]] = str(page)
    if pager.get("size_param") and size:
        q[pager["size_param"]] = str(size)
    return urlunparse((p.scheme, p.netloc, p.path, "", urlencode(q), ""))


# ---------------------------------------------------------------------------
# 상세 페이지
# ---------------------------------------------------------------------------

# 경상국립대 CMS 에서 실제로 확인된 본문 상자 (있으면 내용이 짧아도 그대로 믿음)
AUTHORITATIVE_BODY = [".bbsV_cont", ".BD_table tr.cont td", "tr.cont td", ".ep_view_wrap .txt_wrap", ".txt_wrap"]
BODY_SELECTORS = [
    ".bbs_content", ".bbs-content", ".bbsContent", ".view_cont", ".view-cont", ".view_con", ".viewCon",
    ".ntt_cn", ".nttCn", "#nttCn", ".board_view_con", ".board-view-con", ".bbs_view_con",
    ".view_content", ".view-content", ".cont_area", ".content_view", ".substance", ".article_body",
    ".bbs_view", ".board_view", ".view", "article", ".content", ".cont",
]
META_LABELS = {
    "등록일": "date", "작성일": "date", "게시일": "date", "날짜": "date",
    "부서": "dept", "작성자": "author", "담당부서": "dept", "담당자": "author", "소속": "dept", "작성부서": "dept",
    "조회": "views", "조회수": "views",
    "연락처": "contact", "전화번호": "contact", "전화": "contact",
    "일정": "schedule", "행사일시": "schedule", "행사일정": "schedule",
    "첨부파일": "attachments", "첨부": "attachments",
}


def _label_key(text):
    t = clean(text).replace(":", "").replace("：", "").strip()
    for k, v in META_LABELS.items():
        if t == k or t.startswith(k):
            return v
    return None


def _remove_noise(root):
    for sel in ["script", "style", "noscript", "iframe", "header", "footer", "nav",
                "[class*='skip']", "[class*='gnb']", "[class*='lnb']", "[class*='snb']",
                "[id*='header']", "[id*='footer']", "[class*='footer']", "[class*='header']",
                "[class*='prev']", "[class*='next']", "[class*='share']", "[class*='sns']",
                "[class*='btn']", "[class*='button']", "[class*='pagination']", "[class*='paging']"]:
        for el in root.select(sel):
            el.decompose()


def _text_with_breaks(el):
    for br in el.find_all("br"):
        br.replace_with("\n")
    for p in el.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "table"]):
        p.insert_before("\n")
        p.insert_after("\n")
    text = el.get_text()
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    out, blank = [], 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank <= 1:
                out.append("")
            continue
        blank = 0
        out.append(ln)
    return "\n".join(out).strip()


def _find_body(soup):
    for sel in AUTHORITATIVE_BODY:
        el = soup.select_one(sel)
        if el is not None:
            return el
    for sel in BODY_SELECTORS:
        for el in soup.select(sel):
            txt = clean(el.get_text(" "))
            if len(txt) >= 20 or el.find("img") is not None:
                return el
    # fallback: 전체 본문 텍스트의 절반 이상을 담은 가장 작은 요소
    main = soup.find("main") or soup.body or soup
    total = len(clean(main.get_text(" ")))
    if total == 0:
        return None
    best = None
    for el in main.find_all(["div", "td", "section", "article"]):
        n = len(clean(el.get_text(" ")))
        if n >= total * 0.5:
            if best is None or n < len(clean(best.get_text(" "))):
                best = el
    return best


def parse_detail(html, page_url):
    """상세 페이지 → {title, date, dept, author, views, contact, schedule, body, attachments}"""
    soup = soup_of(html)
    out = {"title": None, "date": None, "dept": None, "author": None, "views": None,
           "contact": None, "schedule": None, "body": "", "attachments": [], "images": []}

    # 메타 정보 (th/dt → td/dd)
    for lab in soup.find_all(["th", "dt"]):
        key = _label_key(lab.get_text())
        if not key:
            continue
        val_el = lab.find_next_sibling(["td", "dd"])
        if val_el is None:
            continue
        val = clean(val_el.get_text(" "))
        if key == "date":
            out["date"] = out["date"] or parse_date(val)
        elif key == "views":
            out["views"] = out["views"] if out["views"] is not None else parse_int(val)
        elif key in ("dept", "author", "contact", "schedule"):
            if not out[key] and val:
                out[key] = val[:200]
    # ul.bbsV_data > li > strong(라벨) 텍스트(값)  /  ul.ep_info_lst > li > i.xi-*(아이콘) 텍스트
    for li in soup.select("ul.bbsV_data li, ul.ep_info_lst li, .bbs_info li, .view_info li"):
        lab = li.find(["strong", "em", "b", "span"])
        icon = li.find("i")
        key = None
        if lab and _label_key(lab.get_text()):
            key = _label_key(lab.get_text())
            val = clean(li.get_text(" ").replace(lab.get_text(), "", 1))
        elif icon is not None:
            cls = " ".join(icon.get("class") or [])
            key = "author" if "user" in cls else "date" if "calendar" in cls else "views" if "eye" in cls else None
            val = clean(li.get_text(" "))
        else:
            continue
        if not key or not val:
            continue
        if key == "date":
            out["date"] = out["date"] or parse_date(val)
        elif key == "views":
            out["views"] = out["views"] if out["views"] is not None else parse_int(val)
        elif key in ("dept", "author", "contact", "schedule") and not out[key]:
            out[key] = val[:200]
    # 텍스트 정규식 보조
    page_text = soup.get_text(" ")
    if out["views"] is None:
        m = VIEWS_RE.search(page_text)
        if m:
            out["views"] = parse_int(m.group(1))
    if out["date"] is None:
        m = re.search(r"(등록일|작성일|게시일)\s*[:：]?\s*(\d{4}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2})", page_text)
        if m:
            out["date"] = parse_date(m.group(2))

    # 제목
    for sel in [".BD_table th.title", ".bbs_ViewA h3", ".ep_view_wrap .tit", ".bbs_tit", ".bbs_title", ".view_tit", ".view_title", ".ntt_sj", ".nttSj", ".tit", ".subject", "h3", "h2", "h4"]:
        el = soup.select_one(sel)
        if el and clean(el.get_text()):
            out["title"] = clean(el.get_text())[:300]
            break

    # 첨부파일
    seen = set()
    for a in soup.select('a[href*="nttFileDownload"], a[href*="FileDown"], a[href*="fileDown"], a[href*="download"]'):
        href = urljoin(page_url, a.get("href", ""))
        if href in seen or "javascript" in href:
            continue
        name = clean(a.get_text(" "))
        name = re.sub(r"\(?\s*다운로드\s*[:：]?\s*[\d,]+\s*회?\s*\)?", "", name).strip()
        name = re.sub(r"^(첨부파일|파일)\s*[:：]?\s*", "", name).strip()
        if not name or name in ("바로보기", "미리보기", "새창"):
            if name in ("바로보기", "미리보기", "새창"):
                continue
            name = "첨부파일"
        seen.add(href)
        out["attachments"].append({"name": name[:200], "url": href})

    # 본문
    body_el = _find_body(soup)
    if body_el is not None:
        # 본문 안 이미지 (포스터처럼 글 내용이 그림인 경우)
        img_srcs = []
        for img in body_el.find_all("img"):
            img_srcs.append((img.get("src") or img.get("data-src") or "", clean(img.get("alt") or "")))
        for m in re.finditer(r"photoView\([^)]*?['\"]([^'\"]+)['\"]\s*\)", str(body_el)):
            img_srcs.append((m.group(1), ""))
        for m in re.finditer(r"background-image\s*:\s*url\(['\"]?([^'\")]+)", str(body_el)):
            img_srcs.append((m.group(1), ""))
        seen_img = set()
        for src, alt in img_srcs:
            if not src or src.startswith("data:"):
                continue
            low = src.lower()
            if any(x in low for x in ["/images/", "icon", "logo", "btn_", "bullet", "blank.gif", "spacer", "noimg"]):
                continue
            if src in seen_img:
                continue
            seen_img.add(src)
            out["images"].append({"src": urljoin(page_url, src), "alt": alt[:200]})
            if len(out["images"]) >= 10:
                break
        for img in []:  # (이전 코드 호환용 — 아래 블록은 더 이상 실행되지 않음)
            src = img.get("src") or ""
            low = src.lower()
            if any(x in low for x in ["/images/", "icon", "logo", "btn_", "bullet", "blank.gif", "spacer"]):
                continue
            try:
                w = int(str(img.get("width") or "999").rstrip("px"))
                h = int(str(img.get("height") or "999").rstrip("px"))
            except ValueError:
                w = h = 999
            if w < 60 or h < 60:
                continue
            out["images"].append({"src": urljoin(page_url, src), "alt": clean(img.get("alt") or "")[:200]})
            if len(out["images"]) >= 10:
                break
        # 메타 표·첨부 목록이 본문 안에 섞여 있으면 제거
        for lab in body_el.find_all(["th", "dt"]):
            if _label_key(lab.get_text()):
                row = lab.find_parent(["tr", "dl", "li"])
                (row or lab).decompose()
        for a in body_el.select('a[href*="nttFileDownload"]'):
            row = a.find_parent(["li", "tr", "p", "dd"])
            (row or a).decompose()
        _remove_noise(body_el)
        out["body"] = _text_with_breaks(body_el)[:8000]
    # 페이지 껍데기(메뉴·안내문)가 본문으로 잡혔으면 버림
    if any(mark in out["body"] for mark in CHROME_MARKS):
        out["body_suspicious"] = True
        lines = [ln for ln in out["body"].splitlines() if ln.strip() and not any(m in ln for m in CHROME_MARKS)]
        kept = "\n".join(lines).strip()
        out["body"] = kept if len(kept) >= 80 else ""
    if len(out["body"]) < 40 and out["images"]:
        alts = [i["alt"] for i in out["images"] if i["alt"]]
        if alts:
            out["body"] = (out["body"] + "\n" + "\n".join("[이미지] " + a for a in alts)).strip()
    return out
