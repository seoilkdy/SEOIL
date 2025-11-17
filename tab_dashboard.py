# tab_dashboard.py  --------------------------------------------------
# '대시보드' 탭과 그 안의 하위 탭 3개(학사공지, 학사일정, 취업정보)를 담당하는 모듈이다.

from __future__ import annotations  # 앞으로 나올 타입 이름을 문자열로 미리 참조할 수 있게 해주는 옵션

from dataclasses import dataclass  # dataclass 데코레이터를 사용해 간단한 데이터 모델 클래스를 만들기 위해 import
from datetime import date, datetime  # 학사일정(날짜 범위)와 공지 날짜 파싱에 사용할 date, datetime 타입 import
from urllib.parse import urljoin  # HTML 링크의 상대경로 href를 절대 URL로 바꾸기 위해 urljoin 함수 import
import tkinter as tk  # Tkinter 기본 위젯(tk.Tk, tk.Frame 등)을 사용하기 위해 import
from tkinter import ttk  # ttk(테마가 적용된 현대식 위젯: Notebook, Treeview 등)를 사용하기 위해 import
import re  # HTML 문자열에서 필요한 부분을 정규식으로 파싱하기 위해 re 모듈 import

from core import _http_get  # core.py 에 정의된 HTTP GET 유틸리티 함수를 재사용하기 위해 import


# ─────────────────────────────────────────────
# 1) URL 상수
# ─────────────────────────────────────────────

# 서일대 채용정보 게시판 URL (원본 코드에서 가져온 그대로, 인코딩된 쿼리 스트링 포함)
NOTICE_LIST_URL = (
    "https://www.seoil.ac.kr/seoil/595/subview.do?"  # 기본 URL
    "enc=Zm5jdDF8QEB8JTJGYmJzJTJGc2VvaWwlMkY3MCUyRmFydGNsTGlzdC5kbyUzRnBhZ2UlM0Qx"
    "JTI2c3JjaENvbHVtbiUzRCUyNnNyY2hXcmQlM0QlMjZiYnNDbFNlcSUzRCUyNmJic09wZW5XcmRT"
    "ZXElM0QlMjZyZ3NCZ25kZVN0ciUzRCUyNnJnc0VuZGRlU3RyJTNEJTI2aXNWaWV3TWluZSUzRGZh"
    "bHNlJTI2cGFzc3dvcmQlM0QlMjZjc3JmVG9rZW4lM0RhZDYzZmY0ZS0yMjBlLTQwMTYtYmEyNi04"
    "ODcxNGMzNzg2NTclMjY%3D"
)  # 실제 페이지가 사용하는 복잡한 파라미터까지 포함한 전체 URL

# 소프트웨어공학과 학사공지 게시판 URL(서일대 사이트 내 전용 경로)
HAKSA_LIST_URL = "https://www.seoil.ac.kr/software/1726/subview.do"

# 서일대 학사일정 페이지 URL(달력+리스트 방식으로 학사일정을 보여주는 페이지)
HAKSA_URL = "https://www.seoil.ac.kr/seoil/554/subview.do"


# ─────────────────────────────────────────────
# 2) 데이터 모델
# ─────────────────────────────────────────────

@dataclass  # 아래 클래스를 dataclass 로 선언해 __init__/__repr__ 등 기본 메서드를 자동 생성
class JobNotice:
    """채용정보/일반공지 게시글 1건을 표현하는 데이터 모델."""
    id: str         # 이 객체를 프론트단에서 구분하기 위한 내부 ID(실제 게시판 번호는 아님)
    title: str      # 게시글 제목
    date: str       # 게시글 날짜(문자열 "YYYY-MM-DD" 형식으로 저장)
    category: str   # "채용정보" 또는 "일반공지"(상단 고정 공지에 사용)
    url: str        # 해당 게시글 상세 페이지를 가리키는 절대 URL


@dataclass  # 학사공지 게시글 1건을 표현하는 dataclass
class HaksaNotice:
    """소프트웨어공학과 학사공지 1건을 표현하는 데이터 모델."""
    id: str         # 내부에서 사용할 ID (예: "haksa-0" 형태)
    title: str      # 학사공지 제목
    date: str       # 날짜(문자열 "YYYY-MM-DD")
    writer: str     # 작성자 이름(또는 부서명)
    category: str   # "학사공지" (필요시 나중에 카테고리를 확장할 수도 있음)
    url: str        # 상세 보기 페이지 절대 URL


@dataclass  # 학사일정(캘린더에 표시되는 일정) 1건을 표현하는 dataclass
class AcadEvent:
    """학사일정 1건 (기간 + 내용)을 표현하는 데이터 모델."""
    start: date     # 일정 시작일 (datetime.date 객체)
    end: date       # 일정 종료일 (datetime.date 객체)
    title: str      # 일정 내용(간단 설명)
    raw_range: str  # HTML 상에 표시된 원본 범위 문자열 (예: "11 .17 ~ .11 .17")


# ─────────────────────────────────────────────
# 3) 채용정보: HTTP + 파서
# ─────────────────────────────────────────────

def fetch_job_notice_list() -> list[JobNotice]:
    """
    서일대 채용정보 게시판에서 HTML을 가져와,
    JobNotice 리스트 형태로 파싱해 반환하는 함수.
    """
    code, html = _http_get(NOTICE_LIST_URL, timeout=10)  # core._http_get 으로 GET 요청 후 (상태코드,본문) 받기
    if code != 200:  # HTTP 200(정상)이 아니면
        print("채용정보 HTTP 오류:", code)  # 콘솔에 에러 코드 출력(디버깅용)
        return []  # 실패 시 빈 리스트 반환

    return _parse_job_html_to_notices(html)  # 정상적인 경우 HTML 본문을 파서 함수에 넘겨 JobNotice 리스트로 변환


def _parse_job_html_to_notices(html: str) -> list[JobNotice]:
    """
    서일대 '대학생활 - 채용정보' 메인 게시판 전용 파서.
    - caption 이 '대학생활 - 채용정보' 인 board-table horizon1 테이블의 tbody 부분만 파싱한다.
    - 각 tr에서 제목/링크/날짜/고정공지 여부를 추출해 JobNotice 리스트로 만든다.
    """
    notices: list[JobNotice] = []  # 파싱 결과를 담을 JobNotice 리스트

    # caption 이 '대학생활 - 채용정보' 인 테이블을 찾고, 그 중 <tbody> ... </tbody> 구간만 추출하는 정규식
    m_table = re.search(
        r'<table[^>]+class="[^"]*board-table[^"]*horizon1[^"]*"[^>]*>'  # board-table horizon1 클래스 가진 테이블 시작
        r'(?:(?!</table>).)*?<caption>\s*대학생활\s*-\s*채용정보\s*</caption>'  # caption 내용이 '대학생활 - 채용정보' 인지 확인
        r'(?:(?!</table>).)*?<tbody>(.*?)</tbody>',  # 그 테이블 안에서 tbody 내용만 캡처
        html,  # 전체 HTML 문자열
        re.IGNORECASE | re.DOTALL,  # 대소문자 무시 + 개행 포함 전체 매칭 옵션
    )
    if not m_table:  # 원하는 테이블을 찾지 못한 경우
        return []  # 빈 리스트 반환

    tbody = m_table.group(1)  # 그룹 1로 캡처된 tbody 내부 HTML만 가져오기

    # tbody 안에서 모든 <tr ...> ... </tr> 블록을 추출하는 정규식 패턴 준비
    row_pattern = re.compile(r"(<tr[^>]*>.*?</tr>)", re.IGNORECASE | re.DOTALL)
    rows = row_pattern.findall(tbody)  # tbody 안에 있는 각 tr 블록 문자열 리스트

    for i, row in enumerate(rows):  # 인덱스(i)와 함께 각 행(row)을 순회
        # 제목/링크 추출: td-subject 셀 안의 <a href> <strong>제목</strong> 구조를 찾는다.
        subj_m = re.search(
            r'<td[^>]*class="td-subject"[^>]*>.*?'  # class="td-subject" 인 td 시작
            r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>.*?'  # a 태그의 href 속성 캡처
            r"<strong>(?P<title>.*?)</strong>.*?</a>",  # strong 안에 제목 텍스트 캡처
            row,  # 현재 tr 블록
            re.IGNORECASE | re.DOTALL,
        )
        if not subj_m:  # 제목/링크 패턴이 안 맞으면
            continue     # 해당 행은 스킵

        href = subj_m.group("href").strip()  # 상대경로 형태의 href 문자열(공백 제거)
        raw_title = subj_m.group("title")    # strong 안에 들어있던 원본 HTML 문자열
        # strong 안의 태그(<span> 등)를 제거하고 텍스트만 깔끔하게 추출
        title = re.sub(r"<.*?>", "", raw_title, flags=re.DOTALL).strip()
        if not title:  # 제목이 비어있으면
            continue   # 스킵

        # 날짜 추출: td-date 셀 안의 문자열에서 "YYYY.MM.DD" 형식만 파싱
        date_cell_m = re.search(
            r'<td[^>]*class="td-date"[^>]*>(.*?)</td>',  # td-date 클래스 가진 td의 내용 전체 캡처
            row,  # 현재 tr 블록
            re.IGNORECASE | re.DOTALL,
        )
        if not date_cell_m:  # 날짜 셀을 찾지 못하면
            continue         # 스킵
        # 날짜 셀 내부에 다른 태그가 있을 수 있으므로 전체 태그 제거 후 문자열만 취함
        raw_date = re.sub(r"<.*?>", "", date_cell_m.group(1), flags=re.DOTALL).strip()
        # "YYYY.MM.DD" 형식(예: 2025.11.18)과 매칭
        mdate = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", raw_date)
        if not mdate:  # 형식이 다르면
            continue   # 스킵

        y, mm, dd = mdate.groups()     # 연도, 월, 일을 문자열로 각각 추출
        date_str = f"{y}-{mm}-{dd}"    # "YYYY-MM-DD" 형식으로 변환

        # href(상대경로)를 NOTICE_LIST_URL 기준으로 절대 URL로 합치기
        full_url = urljoin(NOTICE_LIST_URL, href)

        # tr 의 class 값에 notice 가 포함되면 상단 고정 공지로 판단
        category = "일반공지" if re.search(r'class="[^"]*\bnotice\b', row) else "채용정보"

        # JobNotice 인스턴스 생성 후 결과 리스트에 추가
        notices.append(
            JobNotice(
                id=f"job-{i}",  # 간단히 인덱스 기반 ID 부여
                title=title,    # 파싱한 제목
                date=date_str,  # "YYYY-MM-DD" 날짜 문자열
                category=category,  # "일반공지" 또는 "채용정보"
                url=full_url,       # 절대 URL
            )
        )

        if len(notices) >= 30:  # 최대 30개까지만
            break               # 루프 종료

    return notices  # 최종 JobNotice 리스트 반환


# ─────────────────────────────────────────────
# 4) 학사공지: HTTP + 파서
# ─────────────────────────────────────────────

def fetch_haksa_list() -> list[HaksaNotice]:
    """
    소프트웨어공학과 학사공지 게시판에서 HTML을 가져와,
    HaksaNotice 리스트로 파싱해 반환하는 함수.
    """
    code, html = _http_get(HAKSA_LIST_URL, timeout=10)  # 학사공지 URL로 HTTP GET
    if code != 200:  # 상태코드가 200이 아니면
        print("학사공지 HTTP 오류:", code)  # 에러 로그 출력
        return []  # 빈 리스트 반환

    return _parse_html_to_haksa_notices(html)  # 정상인 경우 파서를 통해 HaksaNotice 리스트로 변환


def _parse_html_to_haksa_notices(html: str) -> list[HaksaNotice]:
    """
    소프트웨어공학과 '서일소식>학사공지' 메인 게시판 전용 파서.
    - caption 이 '서일소식>학사공지' 인 board-table horizon1 테이블의 tbody 를 찾는다.
    - 각 tr 에서 제목/작성자/날짜/상세 URL을 추출해 HaksaNotice 리스트를 만든다.
    """
    notices: list[HaksaNotice] = []  # 결과 리스트

    # caption 이 '서일소식>학사공지' 인 테이블의 tbody 부분만 추출하는 정규식
    m_table = re.search(
        r'<table[^>]+class="[^"]*board-table[^"]*horizon1[^"]*"[^>]*>'  # board-table horizon1 테이블 시작
        r'(?:(?!</table>).)*?<caption>\s*서일소식>학사공지\s*</caption>'  # caption 내용이 정확히 '서일소식>학사공지' 인 경우
        r'(?:(?!</table>).)*?<tbody>(.*?)</tbody>',  # tbody 내부를 그룹 1로 캡처
        html,  # 전체 HTML
        re.IGNORECASE | re.DOTALL,
    )
    if not m_table:  # 매칭되는 테이블이 없으면
        return []    # 빈 리스트 반환

    tbody = m_table.group(1)  # tbody 내용만 추출

    # tbody 안의 각 tr 블록 추출
    row_pattern = re.compile(r"(<tr[^>]*>.*?</tr>)", re.IGNORECASE | re.DOTALL)
    rows = row_pattern.findall(tbody)  # 각 tr 문자열 리스트

    for i, row in enumerate(rows):  # (인덱스, tr 문자열) 반복
        # 제목/링크: td-subject 안의 a[href] > strong 구조 파싱
        subj_m = re.search(
            r'<td[^>]*class="td-subject"[^>]*>.*?'  # td-subject 셀 시작
            r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>.*?'  # a 태그의 href 캡처
            r"<strong>(?P<title>.*?)</strong>.*?</a>",  # strong 안의 제목 캡처
            row,
            re.IGNORECASE | re.DOTALL,
        )
        if not subj_m:  # 패턴에 맞지 않으면
            continue    # 스킵

        href = subj_m.group("href").strip()  # 상대경로 href 문자열
        raw_title = subj_m.group("title")    # strong 안의 원본 HTML
        # 제목에서 태그 제거 후 텍스트만 추출
        title = re.sub(r"<.*?>", "", raw_title, flags=re.DOTALL).strip()
        if not title:  # 제목이 비어있으면
            continue   # 스킵

        # 작성자: td-write 셀에서 텍스트 추출
        writer_m = re.search(
            r'<td[^>]*class="td-write"[^>]*>(.*?)</td>',  # td-write 셀 내용 전체
            row,
            re.IGNORECASE | re.DOTALL,
        )
        if writer_m:
            # td-write 내부의 태그를 제거하고 작성자 텍스트만 얻기
            raw_writer = re.sub(r"<.*?>", "", writer_m.group(1), flags=re.DOTALL).strip()
        else:
            raw_writer = ""  # 작성자가 명시되지 않은 경우 빈 문자열 사용

        # 날짜: td-date 셀 안에서 "YYYY.MM.DD" 형식 추출
        date_cell_m = re.search(
            r'<td[^>]*class="td-date"[^>]*>(.*?)</td>',
            row,
            re.IGNORECASE | re.DOTALL,
        )
        if not date_cell_m:  # 날짜 셀을 찾지 못하면
            continue         # 스킵

        raw_date = re.sub(r"<.*?>", "", date_cell_m.group(1), flags=re.DOTALL).strip()
        mdate = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", raw_date)  # "YYYY.MM.DD" 형식 확인
        if not mdate:
            continue  # 형식이 다르면 스킵

        y, mm, dd = mdate.groups()       # 연/월/일 분리
        date_str = f"{y}-{mm}-{dd}"      # "YYYY-MM-DD" 형식으로 재조합

        full_url = urljoin(HAKSA_LIST_URL, href)  # 상대경로를 학사공지 URL 기준 절대 URL로 변환

        # HaksaNotice 인스턴스를 생성하여 결과 리스트에 추가
        notices.append(
            HaksaNotice(
                id=f"haksa-{i}",        # "haksa-인덱스" 형태 내부 ID
                title=title,            # 공지 제목
                date=date_str,          # 공지 날짜 문자열
                writer=raw_writer,      # 작성자
                category="학사공지",    # 카테고리는 고정값
                url=full_url,           # 상세 페이지 URL
            )
        )

        if len(notices) >= 30:  # 최대 30개까지만 파싱
            break

    return notices  # 학사공지 리스트 반환


# ─────────────────────────────────────────────
# 5) 학사일정: HTTP + 파서
# ─────────────────────────────────────────────

def fetch_academic_events() -> tuple[int, int, list[AcadEvent]]:
    """
    학사일정 페이지에서 현재 표시된 연/월과,
    그 달에 해당하는 학사일정 목록을 파싱해 (year, month, [AcadEvent ...]) 형태로 반환한다.
    """
    code, html = _http_get(HAKSA_URL, timeout=10)  # 학사일정 페이지에 HTTP GET 요청
    if code != 200:  # 실패 시
        print("학사일정 HTTP 오류:", code)  # 에러 코드 출력
        today = date.today()  # 오늘 날짜 기준
        return today.year, today.month, []  # 현재 연/월과 빈 이벤트 리스트를 반환

    return _parse_schedule_html(html)  # 정상 HTML 을 파서에 넘겨 (연,월,이벤트 리스트) 반환


def _parse_schedule_html(html: str) -> tuple[int, int, list[AcadEvent]]:
    """학사일정 페이지 HTML을 파싱해 (연, 월, AcadEvent 리스트)를 반환하는 내부 함수."""
    events: list[AcadEvent] = []  # 결과로 반환할 학사일정 이벤트 리스트

    # hidden input 에 들어있는 연도(year) 값 파싱
    m_year = re.search(r'id="year"\s+value="(\d{4})"', html)
    # hidden input 에 들어있는 월(month) 값 파싱
    m_month = re.search(r'id="month"\s+value="(\d{1,2})"', html)
    year = int(m_year.group(1)) if m_year else date.today().year  # 없으면 오늘 연도 사용
    month_hint = int(m_month.group(1)) if m_month else date.today().month  # 없으면 오늘 월 사용

    # calendarWrap 내부의 list 영역(텍스트 형태로 일정이 나열된 구간)만 추출
    m_list = re.search(
        r'<div class="calendarWrap">.*?<div class="list">(.*?)</div>\s*</div>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not m_list:  # 해당 구조를 찾지 못하면
        return year, month_hint, []  # 연/월만 반환하고 이벤트는 빈 리스트

    list_html = m_list.group(1)  # list 부분의 HTML만 분리

    # 각 li 블록을 개별 일정으로 보고 파싱
    li_pattern = re.compile(r"<li>(.*?)</li>", re.IGNORECASE | re.DOTALL)
    for li_html in li_pattern.findall(list_html):  # li 하나하나 순회
        # strong 태그 안에 날짜 범위 텍스트(예: "11 .17 ~ .11 .17")가 들어있음
        m_strong = re.search(
            r"<strong>(.*?)</strong>",
            li_html,
            re.IGNORECASE | re.DOTALL,
        )
        if not m_strong:  # strong 이 없으면 정상 일정 형식이 아니므로 스킵
            continue
        # strong 안 텍스트에서 과도한 공백을 정리한 원본 범위 문자열
        raw_range = re.sub(r"\s+", " ", m_strong.group(1)).strip()

        # strong 뒤에 오는 나머지 부분에서 <br>은 개행으로 바꾸고, 나머지 태그는 제거하여 설명 텍스트만 추출
        after = li_html[m_strong.end():]  # strong 태그 이후 문자열
        after = re.sub(r"<br\s*/?>", "\n", after, flags=re.IGNORECASE)  # <br> → 줄바꿈
        desc = re.sub(r"<.*?>", "", after, flags=re.DOTALL).strip()     # 나머지 HTML 태그 제거
        if not desc:  # 설명이 비어 있으면
            desc = "(내용 없음)"  # 기본 문자열 사용

        # raw_range 에서 숫자만 추출 (월, 일 정보): 예) ["11", "17", "11", "20"] 또는 ["17", "29"]
        nums = re.findall(r"\d+", raw_range)
        if len(nums) == 4:
            sm, sd, em, ed = map(int, nums)  # 시작월, 시작일, 종료월, 종료일
        elif len(nums) == 2:
            # 예: "11 .17 ~ .29" 처럼 뒤쪽 월이 생략된 경우, 같은 달로 가정
            sm = em = month_hint
            sd, ed = map(int, nums)
        else:
            # 그 외 애매한 형식이면 이 달의 단일 날짜로 취급
            sm = em = month_hint
            sd = ed = int(nums[0]) if nums else 1

        try:
            start = date(year, sm, sd)  # 시작 날짜 date 객체 생성
            end = date(year, em, ed)    # 종료 날짜 date 객체 생성
        except ValueError:
            # 날짜가 유효하지 않으면(예: 2월 30일 등) 해당 일정은 스킵
            continue

        # AcadEvent 인스턴스를 만들어 리스트에 추가
        events.append(
            AcadEvent(
                start=start,      # 시작일
                end=end,          # 종료일
                title=desc,       # 일정 내용
                raw_range=raw_range,  # 원본 범위 문자열
            )
        )

    # 시작일 기준으로 오름차순 정렬(가장 빠른 일정이 먼저 오도록)
    events.sort(key=lambda ev: ev.start)
    return year, month_hint, events  # 연도, 월, 이벤트 리스트를 함께 반환


# ─────────────────────────────────────────────
# 6) Tkinter 프레임들 (3개 서브 탭 + 대시보드 탭)
# ─────────────────────────────────────────────

class DashboardJobsFrame(ttk.Frame):
    """채용정보/일반 공지 목록을 보여주는 하위 탭 프레임."""

    def __init__(self, master: tk.Misc) -> None:
        """
        master: 상위 Notebook 또는 Frame
        - 생성 시 즉시 UI를 만들고, 서버에서 채용정보를 한 번 불러온다.
        """
        super().__init__(master)  # ttk.Frame 기본 초기화
        self.notices: list[JobNotice] = []  # 현재 Treeview에 표시할 JobNotice 리스트 저장 공간
        self._build_ui()  # 위젯(라벨, 버튼, Treeview 등) 구성
        self._refresh_notices()  # 시작할 때 한 번 서버에서 목록 불러오기

    def _build_ui(self) -> None:
        """채용정보 상단 URL 표시/새로고침 버튼 + 중앙 Treeview + 하단 상태바를 구성한다."""
        top = ttk.Frame(self)  # 상단 라인(라벨 + URL + 버튼)용 Frame
        top.pack(fill="x", padx=10, pady=8)  # 좌우 채우기 + 여백

        ttk.Label(top, text="채용정보 URL:").pack(side="left")  # "채용정보 URL:" 라벨을 왼쪽에 배치
        self.lbl_url = ttk.Label(top, text=NOTICE_LIST_URL, foreground="#1565c0")  # 실제 URL 표시 라벨(파란색 계열)
        self.lbl_url.pack(side="left", padx=(4, 10))  # URL 라벨 오른쪽에 약간의 여백

        # "새로고침" 버튼: 클릭 시 _refresh_notices 메서드 호출
        self.btn_refresh = ttk.Button(top, text="새로고침", command=self._refresh_notices)
        self.btn_refresh.pack(side="right")  # 오른쪽 끝으로 배치

        mid = ttk.Frame(self)  # 중앙 영역(Frame) - Treeview + Scrollbar
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))  # 남는 공간 대부분 차지

        columns = ("date", "title", "cat")  # Treeview 컬럼 ID 튜플
        # 채용정보 목록을 표시할 Treeview 생성 (헤더만 보이도록 show="headings")
        self.tree = ttk.Treeview(
            mid,
            columns=columns,
            show="headings",
            height=12,
        )
        self.tree.pack(side="left", fill="both", expand=True)  # 중앙에 채우기

        # 각 컬럼 헤더 텍스트 설정
        self.tree.heading("date", text="날짜")
        self.tree.heading("title", text="제목")
        self.tree.heading("cat", text="분류")

        # 각 컬럼 폭과 정렬 설정
        self.tree.column("date", width=90, anchor="center")
        self.tree.column("title", width=460, anchor="w")
        self.tree.column("cat", width=90, anchor="center")

        # 세로 스크롤바 생성 후 Treeview에 연결
        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        scroll.pack(side="left", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        bottom = ttk.Frame(self)  # 하단 상태/설명 영역
        bottom.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Label(
            bottom,
            text="정렬 기준: 최신순 (채용정보), 고정공지 우선 표시",  # 정렬/표시 기준 설명
            foreground="#555",
        ).pack(anchor="w")

        self.var_status = tk.StringVar(value="준비됨.")  # 현재 상태 텍스트를 담을 StringVar
        ttk.Label(bottom, textvariable=self.var_status).pack(anchor="w")  # 상태 라벨(불러오는 중, 총 몇 건 등)

    def _refresh_notices(self) -> None:
        """채용정보 목록을 서버에서 다시 가져와 Treeview 에 반영한다."""
        self.btn_refresh.config(state="disabled")  # 중복 클릭을 막기 위해 버튼 비활성화
        self.var_status.set("불러오는 중...")       # 상태 텍스트를 "불러오는 중..."으로 변경
        self.update_idletasks()                    # UI를 즉시 갱신해 사용자가 상태 변화를 보게 함

        notices = fetch_job_notice_list()          # 실제 HTTP 요청 + HTML 파싱으로 JobNotice 리스트 획득

        # 고정 공지(일반공지로 표시되는 notice 클래스가 붙은 것)와 실제 채용정보를 분리
        pinned = [n for n in notices if n.category == "일반공지"]  # 상단 고정 공지들
        jobs = [n for n in notices if n.category != "일반공지"]   # 그 외 채용정보 글들

        # 채용글(jobs)을 날짜 기준 내림차순(최신 글이 위로) 정렬하기 위한 헬퍼 함수
        def parse_dt(n: JobNotice) -> datetime:
            try:
                return datetime.strptime(n.date, "%Y-%m-%d")  # "YYYY-MM-DD" → datetime
            except Exception:
                return datetime.min  # 파싱 실패 시 가장 오래된 날짜로 취급

        jobs.sort(key=parse_dt, reverse=True)  # 최신 글이 맨 위로 오도록 정렬

        # 최종 순서: 고정 공지들 먼저, 그 다음 최신순 채용 글들
        self.notices = pinned + jobs

        # 기존 Treeview 행들을 모두 제거
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 새로 받은 공지들을 Treeview 에 한 줄씩 삽입
        for n in self.notices:
            if n.category == "일반공지":  # 고정 공지이면
                title_display = f"📌 {n.title}"  # 제목 앞에 핀 아이콘 붙이기
                cat_display = "📌 고정공지"       # 분류에도 고정공지 표시
            else:
                title_display = n.title      # 일반 채용정보 제목 그대로 사용
                cat_display = "채용정보"    # 분류 텍스트

            self.tree.insert(
                "",
                "end",
                values=(n.date, title_display, cat_display),  # 날짜 / 표시 제목 / 분류 텍스트
            )

        self.var_status.set(f"총 {len(self.notices)}건 불러옴.")  # 불러온 총 건수 표시
        self.btn_refresh.config(state="normal")  # 새로고침 버튼 다시 활성화


class DashboardHaksaFrame(ttk.Frame):
    """학사공지 목록을 보여주는 하위 탭 프레임."""

    def __init__(self, master: tk.Misc) -> None:
        """
        master: 상위 Notebook 또는 Frame
        - 생성 시 학사공지 게시판 파싱 후 목록을 Treeview에 표시한다.
        """
        super().__init__(master)  # ttk.Frame 기본 초기화
        self.notices: list[HaksaNotice] = []  # 현재 로드된 학사공지 리스트
        self._build_ui()  # 학사공지 UI 구성
        self._refresh_notices()  # 시작 시 한 번 서버에서 데이터 로드

    def _build_ui(self) -> None:
        """학사공지 리스트를 표시하는 UI 구성."""
        top = ttk.Frame(self)  # 상단 URL/버튼 영역
        top.pack(fill="x", padx=10, pady=8)

        ttk.Label(top, text="학사공지 URL:").pack(side="left")  # "학사공지 URL:" 라벨
        self.lbl_url = ttk.Label(top, text=HAKSA_LIST_URL, foreground="#1565c0")  # 실제 URL 표시 라벨
        self.lbl_url.pack(side="left", padx=(4, 10))

        self.btn_refresh = ttk.Button(top, text="새로고침", command=self._refresh_notices)  # 새로고침 버튼
        self.btn_refresh.pack(side="right")

        mid = ttk.Frame(self)  # 중앙 Treeview 영역
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("date", "title", "writer")  # 날짜/제목/작성자 컬럼

        self.tree = ttk.Treeview(
            mid,
            columns=columns,
            show="headings",
            height=14,
        )
        self.tree.pack(side="left", fill="both", expand=True)

        # 컬럼 헤더 텍스트 설정
        self.tree.heading("date", text="날짜")
        self.tree.heading("title", text="제목")
        self.tree.heading("writer", text="작성자")

        # 컬럼 폭/정렬 설정
        self.tree.column("date", width=90, anchor="center")
        self.tree.column("title", width=550, anchor="w")
        self.tree.column("writer", width=80, anchor="center")

        # 세로 스크롤바 연결
        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        scroll.pack(side="left", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        bottom = ttk.Frame(self)  # 하단 상태/설명 영역
        bottom.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Label(
            bottom,
            text="정렬 기준: 게시판 순서(번호 내림차순, 최신 글이 위쪽)",  # 게시판 기본 정렬 기준 설명
            foreground="#555",
        ).pack(anchor="w")

        self.var_status = tk.StringVar(value="준비됨.")  # 상태 문자열 값
        ttk.Label(bottom, textvariable=self.var_status).pack(anchor="w")  # 상태 라벨 표시

    def _refresh_notices(self) -> None:
        """학사공지 목록을 서버에서 다시 가져와 Treeview 에 반영한다."""
        self.btn_refresh.config(state="disabled")  # 새로고침 중복 클릭 방지
        self.var_status.set("불러오는 중...")      # 상태 텍스트 변경
        self.update_idletasks()                    # UI 즉시 업데이트

        self.notices = fetch_haksa_list()         # 실제 HTTP + HTML 파싱으로 HaksaNotice 리스트 얻기

        # 기존 Treeview 행 제거
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 공지들을 날짜/제목/작성자 순으로 삽입
        for n in self.notices:
            self.tree.insert("", "end", values=(n.date, n.title, n.writer))

        self.var_status.set(f"총 {len(self.notices)}건 불러옴.")  # 총 개수 출력
        self.btn_refresh.config(state="normal")  # 새로고침 버튼 재활성화


class DashboardAcadFrame(ttk.Frame):
    """해당 달의 학사일정을 보여주는 하위 탭 프레임."""

    def __init__(self, master: tk.Misc) -> None:
        """
        master: 상위 Notebook 또는 Frame
        - 생성 시 학사일정 페이지를 파싱해 이달의 일정 리스트를 표시한다.
        """
        super().__init__(master)  # ttk.Frame 기본 초기화

        self.year: int | None = None   # 현재 표시 중인 연도(학사일정 페이지 기준)
        self.month: int | None = None  # 현재 표시 중인 월
        self.events: list[AcadEvent] = []  # 파싱된 학사일정 목록

        self.var_title = tk.StringVar(value="📅 이달의 학사일정")  # 상단 제목(연/월 반영 전 기본값)

        self._build_ui()     # 위젯 구성
        self._refresh_events()  # 시작 시 학사일정 한 번 불러오기

    def _build_ui(self) -> None:
        """학사일정 리스트를 표시하는 UI 구성."""
        top = ttk.Frame(self)  # 상단 제목/URL/버튼 영역
        top.pack(fill="x", padx=10, pady=8)

        # 상단 제목 라벨(예: "📅 2025년 11월 학사일정")
        ttk.Label(
            top,
            textvariable=self.var_title,       # StringVar 를 바인딩해 동적으로 변경
            font=("Helvetica", 13, "bold"),
            foreground="#1565c0",
        ).pack(anchor="w", pady=(0, 6))

        url_line = ttk.Frame(top)  # URL/버튼을 한 줄에 배치하기 위한 Frame
        url_line.pack(fill="x")

        ttk.Label(url_line, text="학사일정 URL:").pack(side="left")  # 라벨 텍스트
        ttk.Label(url_line, text=HAKSA_URL, foreground="#1565c0").pack(
            side="left",
            padx=(4, 10),
        )  # 실제 학사일정 URL 텍스트 라벨

        # "새로고침" 버튼: 클릭 시 _refresh_events 호출
        self.btn_refresh = ttk.Button(
            url_line,
            text="새로고침",
            command=self._refresh_events,
        )
        self.btn_refresh.pack(side="right")

        mid = ttk.Frame(self)  # 중앙 Treeview 영역
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("range", "title")  # 기간과 내용 컬럼 ID

        self.tree = ttk.Treeview(
            mid,
            columns=columns,
            show="headings",
            height=14,
        )
        self.tree.pack(side="left", fill="both", expand=True)

        # 컬럼 헤더 설정
        self.tree.heading("range", text="기간")
        self.tree.heading("title", text="내용")

        # 컬럼 폭/정렬 설정
        self.tree.column("range", width=150, anchor="center")
        self.tree.column("title", width=600, anchor="w")

        # 세로 스크롤바 연결
        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        scroll.pack(side="left", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        bottom = ttk.Frame(self)  # 하단 상태/설명 영역
        bottom.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Label(
            bottom,
            text="정렬 기준: 시작일 오름차순 (해당 달의 학사일정)",  # 정렬 기준 설명
            foreground="#555",
        ).pack(anchor="w")

        self.var_status = tk.StringVar(value="준비됨.")  # 현재 상태(불러오는 중, 총 건수 등)를 위한 StringVar
        ttk.Label(bottom, textvariable=self.var_status).pack(anchor="w")  # 상태 라벨 표시

    def _refresh_events(self) -> None:
        """학사일정을 서버에서 다시 가져와 Treeview 에 반영한다."""
        self.btn_refresh.config(state="disabled")  # 새로고침 버튼 비활성화
        self.var_status.set("불러오는 중...")      # 상태 텍스트 업데이트
        self.update_idletasks()                    # UI 즉시 반영

        year, month, events = fetch_academic_events()  # (연도,월,이벤트 리스트) 파싱
        self.year, self.month, self.events = year, month, events  # 내부 상태에 저장

        if self.year and self.month:  # 연도/월 값이 유효하면
            self.var_title.set(f"📅 {self.year}년 {self.month}월 학사일정")  # 상단 제목에 반영

        # 기존 Treeview 행 제거
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 새로 받은 학사일정들을 Treeview 에 삽입
        for ev in self.events:
            if ev.start == ev.end:  # 단일 날짜 일정이면
                rng = ev.start.strftime("%Y-%m-%d")  # 시작일만 표시
            else:  # 범위 일정이면 "YYYY-MM-DD ~ YYYY-MM-DD" 형식으로 표시
                rng = f"{ev.start:%Y-%m-%d} ~ {ev.end:%Y-%m-%d}"
            self.tree.insert("", "end", values=(rng, ev.title))

        self.var_status.set(f"총 {len(self.events)}건 불러옴.")  # 총 일정 건수 표시
        self.btn_refresh.config(state="normal")  # 새로고침 버튼 다시 활성화


class DashboardTab(ttk.Frame):
    """
    '대시보드' 탭 본체 프레임.
    - 내부에 Notebook 을 하나 더 두어
      '학사공지' / '학사일정' / '취업정보' 세 개의 하위 탭을 제공한다.
    """

    def __init__(self, master: tk.Misc) -> None:
        """
        master: 상위 Notebook (MainApp 에서 생성한 최상위 Notebook)
        """
        super().__init__(master)  # ttk.Frame 기본 초기화
        self._build_ui()          # 내부 Notebook + 하위 탭 구성

    def _build_ui(self) -> None:
        """내부 Notebook 과 3개 서브 탭(학사공지/학사일정/취업정보)을 생성하고 배치한다."""
        nb = ttk.Notebook(self)  # 대시보드 전용 서브 Notebook 생성
        nb.pack(expand=True, fill="both", padx=10, pady=10)  # 전체 공간을 채우도록 배치

        # 각 서브 탭에 들어갈 Frame 인스턴스 생성
        frm_haksa = DashboardHaksaFrame(nb)  # '학사공지' 탭 내용
        frm_acad = DashboardAcadFrame(nb)    # '학사일정' 탭 내용
        frm_jobs = DashboardJobsFrame(nb)    # '취업정보' 탭 내용

        # Notebook 에 하위 탭으로 추가 (순서: 학사공지 → 학사일정 → 취업정보)
        nb.add(frm_haksa, text="학사공지")
        nb.add(frm_acad, text="학사일정")
        nb.add(frm_jobs, text="취업정보")
