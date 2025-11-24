# tab_dashboard.py  --------------------------------------------------
# '대시보드' 탭을 담당하는 모듈입니다.
# 이 탭은 내부에 또 다른 Notebook을 포함하여 '학사공지', '학사일정', '취업정보' 
# 세 가지 하위 탭을 제공하며, 학교 홈페이지에서 데이터를 크롤링하여 보여줍니다.

from __future__ import annotations  # 파이썬 3.7+에서 타입 힌트를 문자열처럼 처리하여 순환 참조 문제를 방지합니다.

from dataclasses import dataclass  # 데이터 클래스 정의를 간소화하기 위해 사용합니다.
from datetime import date, datetime  # 날짜 및 시간 처리를 위해 사용합니다.
from urllib.parse import urljoin  # 상대 경로 URL을 절대 경로로 변환하기 위해 사용합니다.
import tkinter as tk  # Tkinter 기본 위젯 기능을 가져옵니다.
from tkinter import ttk  # ttk 스타일 위젯을 가져옵니다.
import re  # 정규 표현식을 사용하여 HTML 파싱을 수행합니다.

from core import _http_get  # core.py에서 HTTP GET 요청 유틸리티를 가져옵니다.


# ─────────────────────────────────────────────
# 1. 크롤링 대상 URL 상수 정의
# ─────────────────────────────────────────────

# 채용정보/일반공지 목록 페이지 URL (암호화된 파라미터 포함)
NOTICE_LIST_URL = (
    "https://www.seoil.ac.kr/seoil/595/subview.do?"
    "enc=Zm5jdDF8QEB8JTJGYmJzJTJGc2VvaWwlMkY3MCUyRmFydGNsTGlzdC5kbyUzRnBhZ2UlM0Qx"
    "JTI2c3JjaENvbHVtbiUzRCUyNnNyY2hXcmQlM0QlMjZiYnNDbFNlcSUzRCUyNmJic09wZW5XcmRT"
    "ZXElM0QlMjZyZ3NCZ25kZVN0ciUzRCUyNnJnc0VuZGRlU3RyJTNEJTI2aXNWaWV3TWluZSUzRGZh"
    "bHNlJTI2cGFzc3dvcmQlM0QlMjZjc3JmVG9rZW4lM0RhZDYzZmY0ZS0yMjBlLTQwMTYtYmEyNi04"
    "ODcxNGMzNzg2NTclMjY%3D"
)
# 학사공지 목록 페이지 URL
HAKSA_LIST_URL = "https://www.seoil.ac.kr/software/1726/subview.do"
# 학사일정 페이지 URL
HAKSA_URL = "https://www.seoil.ac.kr/seoil/554/subview.do"


# ─────────────────────────────────────────────
# 2. 데이터 모델 (Dataclasses)
# ─────────────────────────────────────────────

@dataclass
class JobNotice:
    """채용정보 및 일반공지 항목을 저장하는 데이터 클래스입니다."""
    id: str       # 고유 식별자 (내부용)
    title: str    # 공지 제목
    date: str     # 작성일 (YYYY-MM-DD)
    category: str # 분류 (일반공지/채용정보 등)
    url: str      # 상세 페이지 URL

@dataclass
class HaksaNotice:
    """학사공지 항목을 저장하는 데이터 클래스입니다."""
    id: str       # 고유 식별자
    title: str    # 공지 제목
    date: str     # 작성일
    writer: str   # 작성자 (부서명 등)
    category: str # 분류 (학사공지 고정)
    url: str      # 상세 페이지 URL

@dataclass
class AcadEvent:
    """학사일정 이벤트를 저장하는 데이터 클래스입니다."""
    start: date   # 시작 날짜
    end: date     # 종료 날짜
    title: str    # 일정 내용
    raw_range: str # 원본 날짜 범위 문자열


# ─────────────────────────────────────────────
# 3. 채용정보 크롤링: HTTP 요청 및 파싱
# ─────────────────────────────────────────────

def fetch_job_notice_list() -> list[JobNotice]:
    """
    채용정보 페이지에서 HTML을 가져와 파싱한 후 JobNotice 리스트를 반환합니다.
    """
    code, html = _http_get(NOTICE_LIST_URL, timeout=10)  # HTTP GET 요청 (타임아웃 10초)
    if code != 200:  # 요청 실패 시
        print("채용정보 HTTP 오류:", code)
        return []  # 빈 리스트 반환
    return _parse_job_html_to_notices(html)  # HTML 파싱 함수 호출

def _parse_job_html_to_notices(html: str) -> list[JobNotice]:
    """
    채용정보 HTML에서 정규표현식을 사용하여 공지사항 목록을 추출합니다.
    """
    notices: list[JobNotice] = []
    
    # 테이블 본문(tbody) 추출을 위한 정규식
    m_table = re.search(
        r'<table[^>]+class="[^"]*board-table[^"]*horizon1[^"]*"[^>]*>'
        r'(?:(?!</table>).)*?<caption>\s*대학생활\s*-\s*채용정보\s*</caption>'
        r'(?:(?!</table>).)*?<tbody>(.*?)</tbody>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not m_table:
        return []  # 테이블을 찾지 못하면 빈 리스트 반환

    tbody = m_table.group(1)  # tbody 내용만 추출
    row_pattern = re.compile(r"(<tr[^>]*>.*?</tr>)", re.IGNORECASE | re.DOTALL)  # 행(tr) 추출 패턴
    rows = row_pattern.findall(tbody)  # 모든 행을 리스트로 찾음

    for i, row in enumerate(rows):
        # 제목 및 링크 추출
        subj_m = re.search(
            r'<td[^>]*class="td-subject"[^>]*>.*?'
            r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>.*?'
            r"<strong>(?P<title>.*?)</strong>.*?</a>",
            row,
            re.IGNORECASE | re.DOTALL,
        )
        if not subj_m:
            continue  # 제목을 찾지 못하면 건너뜀

        href = subj_m.group("href").strip()  # 링크 주소
        raw_title = subj_m.group("title")  # 제목 원본
        title = re.sub(r"<.*?>", "", raw_title, flags=re.DOTALL).strip()  # 태그 제거 및 공백 정리
        if not title:
            continue

        # 날짜 추출
        date_cell_m = re.search(
            r'<td[^>]*class="td-date"[^>]*>(.*?)</td>',
            row,
            re.IGNORECASE | re.DOTALL,
        )
        if not date_cell_m:
            continue
        raw_date = re.sub(r"<.*?>", "", date_cell_m.group(1), flags=re.DOTALL).strip()
        mdate = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", raw_date)  # YYYY.MM.DD 형식 매칭
        if not mdate:
            continue

        y, mm, dd = mdate.groups()
        date_str = f"{y}-{mm}-{dd}"  # YYYY-MM-DD 형식으로 변환
        full_url = urljoin(NOTICE_LIST_URL, href)  # 절대 URL 생성
        
        # 공지 분류 확인 (class에 'notice'가 있으면 일반공지, 아니면 채용정보)
        category = "일반공지" if re.search(r'class="[^"]*\bnotice\b', row) else "채용정보"

        # JobNotice 객체 생성 및 리스트 추가
        notices.append(
            JobNotice(
                id=f"job-{i}",
                title=title,
                date=date_str,
                category=category,
                url=full_url,
            )
        )
        if len(notices) >= 30:  # 최대 30개까지만 수집
            break

    return notices


# ─────────────────────────────────────────────
# 4. 학사공지 크롤링: HTTP 요청 및 파싱
# ─────────────────────────────────────────────

def fetch_haksa_list() -> list[HaksaNotice]:
    """
    학사공지 페이지에서 HTML을 가져와 파싱한 후 HaksaNotice 리스트를 반환합니다.
    """
    code, html = _http_get(HAKSA_LIST_URL, timeout=10)
    if code != 200:
        print("학사공지 HTTP 오류:", code)
        return []
    return _parse_html_to_haksa_notices(html)

def _parse_html_to_haksa_notices(html: str) -> list[HaksaNotice]:
    """
    학사공지 HTML을 파싱하여 공지사항 목록을 추출합니다.
    """
    notices: list[HaksaNotice] = []
    
    # 테이블 추출 정규식
    m_table = re.search(
        r'<table[^>]+class="[^"]*board-table[^"]*horizon1[^"]*"[^>]*>'
        r'(?:(?!</table>).)*?<caption>\s*서일소식>학사공지\s*</caption>'
        r'(?:(?!</table>).)*?<tbody>(.*?)</tbody>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not m_table:
        return []

    tbody = m_table.group(1)
    row_pattern = re.compile(r"(<tr[^>]*>.*?</tr>)", re.IGNORECASE | re.DOTALL)
    rows = row_pattern.findall(tbody)

    for i, row in enumerate(rows):
        # 제목 및 링크 추출
        subj_m = re.search(
            r'<td[^>]*class="td-subject"[^>]*>.*?'
            r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>.*?'
            r"<strong>(?P<title>.*?)</strong>.*?</a>",
            row,
            re.IGNORECASE | re.DOTALL,
        )
        if not subj_m:
            continue

        href = subj_m.group("href").strip()
        raw_title = subj_m.group("title")
        title = re.sub(r"<.*?>", "", raw_title, flags=re.DOTALL).strip()
        if not title:
            continue

        # 작성자 추출
        writer_m = re.search(
            r'<td[^>]*class="td-write"[^>]*>(.*?)</td>',
            row,
            re.IGNORECASE | re.DOTALL,
        )
        raw_writer = re.sub(r"<.*?>", "", writer_m.group(1), flags=re.DOTALL).strip() if writer_m else ""

        # 날짜 추출
        date_cell_m = re.search(
            r'<td[^>]*class="td-date"[^>]*>(.*?)</td>',
            row,
            re.IGNORECASE | re.DOTALL,
        )
        if not date_cell_m:
            continue

        raw_date = re.sub(r"<.*?>", "", date_cell_m.group(1), flags=re.DOTALL).strip()
        mdate = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", raw_date)
        if not mdate:
            continue

        y, mm, dd = mdate.groups()
        date_str = f"{y}-{mm}-{dd}"
        full_url = urljoin(HAKSA_LIST_URL, href)

        # HaksaNotice 객체 생성 및 추가
        notices.append(
            HaksaNotice(
                id=f"haksa-{i}",
                title=title,
                date=date_str,
                writer=raw_writer,
                category="학사공지",
                url=full_url,
            )
        )
        if len(notices) >= 30:
            break

    return notices


# ─────────────────────────────────────────────
# 5. 학사일정 크롤링: HTTP 요청 및 파싱
# ─────────────────────────────────────────────

def fetch_academic_events() -> tuple[int, int, list[AcadEvent]]:
    """
    학사일정 페이지에서 데이터를 가져와 연도, 월, 이벤트 리스트를 반환합니다.
    """
    code, html = _http_get(HAKSA_URL, timeout=10)
    if code != 200:
        print("학사일정 HTTP 오류:", code)
        today = date.today()
        return today.year, today.month, []  # 오류 시 현재 연월과 빈 리스트 반환
    return _parse_schedule_html(html)

def fetch_academic_events_for_month(year: int, month: int) -> list[AcadEvent]:
    """
    특정 년/월의 학사일정을 POST 요청으로 가져옵니다.
    
    Args:
        year: 조회할 연도 (예: 2025)
        month: 조회할 월 (1-12)
        
    Returns:
        해당 월의 학사일정 리스트
    """
    from urllib import request as urlrequest, error as urlerror, parse as urlparse
    
    # POST 요청 URL
    url = "https://www.seoil.ac.kr/schdulmanage/seoil/7/monthSchdul.do"
    
    # Form data 준비
    form_data = {
        'kind': '',
        'year': str(year),
        'month': str(month)
    }
    
    # URL-encoded form data로 변환
    data = urlparse.urlencode(form_data).encode('utf-8')
    
    try:
        # POST 요청 생성
        req = urlrequest.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        # 요청 전송 및 응답 받기
        with urlrequest.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', 'ignore')
            
        # HTML 파싱
        _, _, events = _parse_schedule_html(html)
        return events
        
    except urlerror.HTTPError as e:
        print(f"학사일정 HTTP 오류 ({year}년 {month}월): {e.code}")
        return []
    except Exception as e:
        print(f"학사일정 요청 오류 ({year}년 {month}월): {e}")
        return []

def _parse_schedule_html(html: str) -> tuple[int, int, list[AcadEvent]]:

    """
    학사일정 HTML을 파싱하여 현재 표시된 연/월 정보와 일정 목록을 추출합니다.
    """
    events: list[AcadEvent] = []
    
    # 현재 페이지의 연도/월 정보 추출 (hidden input 값 등에서)
    m_year = re.search(r'id="year"\s+value="(\d{4})"', html)
    m_month = re.search(r'id="month"\s+value="(\d{1,2})"', html)
    year = int(m_year.group(1)) if m_year else date.today().year
    month_hint = int(m_month.group(1)) if m_month else date.today().month

    # 일정 목록 영역 추출
    m_list = re.search(
        r'<div class="calendarWrap">.*?<div class="list">(.*?)</div>\s*</div>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not m_list:
        return year, month_hint, []

    list_html = m_list.group(1)
    li_pattern = re.compile(r"<li>(.*?)</li>", re.IGNORECASE | re.DOTALL)
    for li_html in li_pattern.findall(list_html):
        # 날짜 범위 추출 (strong 태그)
        m_strong = re.search(r"<strong>(.*?)</strong>", li_html, re.IGNORECASE | re.DOTALL)
        if not m_strong:
            continue
        raw_range = re.sub(r"\s+", " ", m_strong.group(1)).strip()

        # 일정 내용 추출 (strong 태그 이후 내용)
        after = li_html[m_strong.end():]
        after = re.sub(r"<br\s*/?>", "\n", after, flags=re.IGNORECASE)  # br 태그를 줄바꿈으로
        desc = re.sub(r"<.*?>", "", after, flags=re.DOTALL).strip()  # 나머지 태그 제거
        if not desc:
            desc = "(내용 없음)"

        # 날짜 파싱 로직 (다양한 형식을 처리)
        nums = re.findall(r"\d+", raw_range)
        if len(nums) == 4:  # MM.DD ~ MM.DD 형식
            sm, sd, em, ed = map(int, nums)
        elif len(nums) == 2:  # DD ~ DD 형식 (같은 달)
            sm = em = month_hint
            sd, ed = map(int, nums)
        else:  # DD 형식 (하루)
            sm = em = month_hint
            sd = ed = int(nums[0]) if nums else 1

        try:
            start = date(year, sm, sd)
            end = date(year, em, ed)
        except ValueError:
            continue  # 날짜 형식이 유효하지 않으면 건너뜀

        events.append(AcadEvent(start=start, end=end, title=desc, raw_range=raw_range))

    events.sort(key=lambda ev: ev.start)  # 시작일 순으로 정렬
    return year, month_hint, events


# ─────────────────────────────────────────────
# 6. UI 스타일 설정 (대시보드 전용)
# ─────────────────────────────────────────────

def configure_dashboard_style():
    """
    대시보드 탭에서 사용할 전용 스타일을 설정합니다.
    'Soft Modern' 테마를 기반으로 Segoe UI 폰트와 부드러운 색상을 사용합니다.
    """
    style = ttk.Style()
    
    # --- 색상 팔레트 ---
    ACCENT_COLOR = "#3F51B5"        # 인디고 (강조색)
    ACCENT_LIGHT = "#E8EAF6"        # 연한 인디고
    
    BG_COLOR = "#F5F7FA"            # 배경색
    CARD_BG = "#FFFFFF"             # 카드 배경색
    BORDER_COLOR = "#E0E0E0"        # 테두리 색상
    
    TEXT_MAIN = "#263238"           # 본문 텍스트
    TEXT_SUB = "#546E7A"            # 보조 텍스트
    
    BTN_BG = "#E3F2FD"              # 버튼 배경
    BTN_HOVER = "#BBDEFB"           # 버튼 호버
    BTN_TEXT = "#1565C0"            # 버튼 텍스트

    HEADER_BG = "#FAFAFA"           # 헤더 배경
    
    # --- 폰트 정의 ---
    FONT_TITLE = ("Segoe UI", 14, "bold")
    FONT_HEADER = ("Segoe UI", 11, "bold")
    FONT_BODY = ("Segoe UI", 10)
    FONT_SMALL = ("Segoe UI", 9)
    
    # --- Treeview 스타일 ---
    style.configure(
        "Dashboard.Treeview",
        font=FONT_BODY,
        rowheight=38,               # 행 높이를 넉넉하게
        background="white",
        fieldbackground="white",
        foreground=TEXT_MAIN,
        borderwidth=0,
    )
    style.configure(
        "Dashboard.Treeview.Heading",
        font=FONT_HEADER,
        background=HEADER_BG,
        foreground=TEXT_MAIN,
        relief="flat",
        padding=(0, 10)
    )
    style.map(
        "Dashboard.Treeview",
        background=[("selected", ACCENT_LIGHT)],
        foreground=[("selected", "black")],
    )
    
    # --- 프레임 스타일 ---
    style.configure("TFrame", background=BG_COLOR)
    
    # 카드 스타일 (흰 배경, 테두리 없음)
    style.configure(
        "Card.TFrame", 
        background=CARD_BG,
        relief="flat",
        borderwidth=0
    )
    
    # 강조색 띠 스타일
    style.configure("Accent.TFrame", background=ACCENT_COLOR)
    
    # --- 라벨 스타일 ---
    style.configure(
        "CardTitle.TLabel",
        font=FONT_TITLE,
        foreground=ACCENT_COLOR,
        background=CARD_BG,
        padding=(0, 0, 0, 8)
    )
    style.configure(
        "CardBody.TLabel",
        font=FONT_BODY,
        foreground=TEXT_MAIN,
        background=CARD_BG
    )
    style.configure(
        "CardInfo.TLabel",
        font=FONT_SMALL,
        foreground=TEXT_SUB,
        background=CARD_BG
    )
    
    # --- 버튼 스타일 ---
    style.configure(
        "Action.TButton",
        font=("Segoe UI", 10, "bold"),
        foreground=BTN_TEXT,
        background=BTN_BG,
        padding=6,
        relief="flat"
    )
    style.map(
        "Action.TButton",
        foreground=[("active", "#0D47A1")],
        background=[("active", BTN_HOVER)]
    )


# ─────────────────────────────────────────────
# 7. 하위 탭 프레임 클래스들
# ─────────────────────────────────────────────

class DashboardJobsFrame(ttk.Frame):
    """채용정보 및 일반 공지 목록을 보여주는 하위 탭 프레임입니다."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Card.TFrame")
        self.notices: list[JobNotice] = []  # 공지 목록 데이터
        self._build_ui()  # UI 구성
        self._refresh_notices()  # 초기 데이터 로드

    def _build_ui(self) -> None:
        """채용정보 탭의 UI를 구성합니다."""
        self.configure(style="TFrame")  # 전체 배경 설정
        
        # 카드 컨테이너
        card_frame = ttk.Frame(self, style="Card.TFrame", padding=0)
        card_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # 상단 강조 띠
        accent_strip = ttk.Frame(card_frame, style="Accent.TFrame", height=4)
        accent_strip.pack(fill="x", side="top")
        
        # 내부 컨텐츠 프레임
        inner_frame = ttk.Frame(card_frame, style="Card.TFrame", padding=20)
        inner_frame.pack(fill="both", expand=True)

        # 1. 헤더 영역 (제목 및 새로고침 버튼)
        header = ttk.Frame(inner_frame, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 15))

        ttk.Label(header, text="소프트웨어공학과 취업정보", style="CardTitle.TLabel").pack(side="left")
        
        btn_frame = ttk.Frame(header, style="Card.TFrame")
        btn_frame.pack(side="right")
        
        self.btn_refresh = ttk.Button(
            btn_frame, 
            text="🔄 새로고침", 
            style="Action.TButton",
            command=self._refresh_notices
        )
        self.btn_refresh.pack(side="left")

        # 2. URL 정보 표시
        url_frame = ttk.Frame(inner_frame, style="Card.TFrame")
        url_frame.pack(fill="x", pady=(0, 15))
        
        ttk.Label(url_frame, text="출처:", style="CardInfo.TLabel").pack(side="left")
        self.lbl_url = ttk.Label(
            url_frame, 
            text=NOTICE_LIST_URL, 
            style="CardInfo.TLabel", 
            foreground="#3F51B5", # 링크 색상
            cursor="hand2"
        )
        self.lbl_url.pack(side="left", padx=5)

        # 3. 리스트 영역 (Treeview)
        list_frame = ttk.Frame(inner_frame, style="Card.TFrame")
        list_frame.pack(fill="both", expand=True)

        columns = ("date", "cat", "title")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            style="Dashboard.Treeview",
            height=15,
        )
        
        # 스크롤바
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # 컬럼 설정
        self.tree.heading("date", text="날짜")
        self.tree.heading("cat", text="분류")
        self.tree.heading("title", text="제목")

        self.tree.column("date", width=120, anchor="center")
        self.tree.column("cat", width=100, anchor="center")
        self.tree.column("title", width=500, anchor="w")
        
        # 더블클릭 이벤트: 상세보기 팝업
        self.tree.bind("<Double-Button-1>", self._on_item_double_click)

        # 4. 하단 상태바
        bottom = ttk.Frame(inner_frame, style="Card.TFrame")
        bottom.pack(fill="x", pady=(15, 0))

        self.var_status = tk.StringVar(value="준비됨.")
        ttk.Label(bottom, textvariable=self.var_status, style="CardInfo.TLabel").pack(side="right")
        ttk.Label(
            bottom,
            text="📌 고정공지는 상단에 우선 표시됩니다.",
            style="CardInfo.TLabel"
        ).pack(side="left")

    def _refresh_notices(self) -> None:
        """데이터를 새로고침하고 리스트를 갱신합니다."""
        self.btn_refresh.config(state="disabled")  # 버튼 비활성화
        self.var_status.set("데이터를 불러오는 중입니다...")
        self.update_idletasks()

        notices = fetch_job_notice_list()  # 크롤링 수행

        # 고정공지(일반공지)와 채용정보 분리 및 정렬
        pinned = [n for n in notices if n.category == "일반공지"]
        jobs = [n for n in notices if n.category != "일반공지"]

        def parse_dt(n: JobNotice) -> datetime:
            try:
                return datetime.strptime(n.date, "%Y-%m-%d")
            except Exception:
                return datetime.min

        jobs.sort(key=parse_dt, reverse=True)  # 최신순 정렬
        self.notices = pinned + jobs  # 고정공지를 상단에 배치

        # 기존 항목 삭제
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 새 항목 추가
        for i, n in enumerate(self.notices):
            tag = "even" if i % 2 == 0 else "odd"
            if n.category == "일반공지":
                title_display = f"📌 {n.title}"
                cat_display = "공지"
            else:
                title_display = n.title
                cat_display = "채용"

            self.tree.insert(
                "",
                "end",
                values=(n.date, cat_display, title_display),
                tags=(tag,)
            )

        # 줄무늬 스타일 적용
        self.tree.tag_configure("odd", background="#f9f9f9")
        self.tree.tag_configure("even", background="white")

        self.var_status.set(f"총 {len(self.notices)}건 업데이트 완료 ({datetime.now().strftime('%H:%M:%S')})")
        self.btn_refresh.config(state="normal")  # 버튼 활성화

    def _on_item_double_click(self, event) -> None:
        """
        Treeview 항목 더블클릭 시 호출됩니다.
        선택된 공지사항을 브라우저에서 직접 엽니다.
        """
        # 선택된 항목 가져오기
        selection = self.tree.selection()
        if not selection:
            return
        
        # 선택된 항목의 인덱스 가져오기
        item_id = selection[0]
        item_index = self.tree.index(item_id)
        
        if 0 <= item_index < len(self.notices):
            notice = self.notices[item_index]
            
            # 브라우저에서 바로 열기
            import webbrowser
            webbrowser.open(notice.url)


class DashboardHaksaFrame(ttk.Frame):
    """학사공지 목록을 보여주는 하위 탭 프레임입니다."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Card.TFrame")
        self.notices: list[HaksaNotice] = []
        self._build_ui()
        self._refresh_notices()

    def _build_ui(self) -> None:
        """학사공지 탭의 UI를 구성합니다."""
        self.configure(style="TFrame")
        
        card_frame = ttk.Frame(self, style="Card.TFrame", padding=0)
        card_frame.pack(fill="both", expand=True, padx=15, pady=15)

        ttk.Frame(card_frame, style="Accent.TFrame", height=4).pack(fill="x", side="top")
        
        inner_frame = ttk.Frame(card_frame, style="Card.TFrame", padding=20)
        inner_frame.pack(fill="both", expand=True)

        # 헤더
        header = ttk.Frame(inner_frame, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 15))
        ttk.Label(header, text="서일대학교 학사공지", style="CardTitle.TLabel").pack(side="left")
        
        self.btn_refresh = ttk.Button(
            header, 
            text="🔄 새로고침", 
            style="Action.TButton",
            command=self._refresh_notices
        )
        self.btn_refresh.pack(side="right")

        # URL
        url_frame = ttk.Frame(inner_frame, style="Card.TFrame")
        url_frame.pack(fill="x", pady=(0, 15))
        ttk.Label(url_frame, text="출처:", style="CardInfo.TLabel").pack(side="left")
        ttk.Label(
            url_frame, 
            text=HAKSA_LIST_URL, 
            style="CardInfo.TLabel", 
            foreground="#3F51B5"
        ).pack(side="left", padx=5)

        # 리스트
        list_frame = ttk.Frame(inner_frame, style="Card.TFrame")
        list_frame.pack(fill="both", expand=True)

        columns = ("date", "writer", "title")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            style="Dashboard.Treeview",
            height=15,
        )
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.tree.heading("date", text="날짜")
        self.tree.heading("writer", text="작성자")
        self.tree.heading("title", text="제목")

        self.tree.column("date", width=120, anchor="center")
        self.tree.column("writer", width=100, anchor="center")
        self.tree.column("title", width=500, anchor="w")
        
        # 더블클릭 이벤트: 상세보기 팝업
        self.tree.bind("<Double-Button-1>", self._on_item_double_click)

        # 상태바
        bottom = ttk.Frame(inner_frame, style="Card.TFrame")
        bottom.pack(fill="x", pady=(15, 0))
        self.var_status = tk.StringVar(value="준비됨.")
        ttk.Label(bottom, textvariable=self.var_status, style="CardInfo.TLabel").pack(side="right")

    def _refresh_notices(self) -> None:
        """학사공지 데이터를 새로고침합니다."""
        self.btn_refresh.config(state="disabled")
        self.var_status.set("데이터를 불러오는 중입니다...")
        self.update_idletasks()

        self.notices = fetch_haksa_list()

        for item in self.tree.get_children():
            self.tree.delete(item)

        for i, n in enumerate(self.notices):
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", values=(n.date, n.writer, n.title), tags=(tag,))

        self.tree.tag_configure("odd", background="#f9f9f9")
        self.tree.tag_configure("even", background="white")

        self.var_status.set(f"총 {len(self.notices)}건 업데이트 완료 ({datetime.now().strftime('%H:%M:%S')})")
        self.btn_refresh.config(state="normal")

    def _on_item_double_click(self, event) -> None:
        """
        Treeview 항목 더블클릭 시 호출됩니다.
        선택된 학사공지를 브라우저에서 직접 엽니다.
        """
        # 선택된 항목 가져오기
        selection = self.tree.selection()
        if not selection:
            return
        
        # 선택된 항목의 인덱스 가져오기
        item_id = selection[0]
        item_index = self.tree.index(item_id)
        
        if 0 <= item_index < len(self.notices):
            notice = self.notices[item_index]
            
            # 브라우저에서 바로 열기
            import webbrowser
            webbrowser.open(notice.url)


class DashboardAcadFrame(ttk.Frame):
    """캘린더 기반 학사일정을 보여주는 하위 탭 프레임입니다."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Card.TFrame")
        
        # 현재 표시 중인 년/월
        today = date.today()
        self.current_year = today.year
        self.current_month = today.month
        
        # 선택된 날짜 (필터링용)
        self.selected_date: date | None = None
        
        # 전체 일정 데이터
        self.events: list[AcadEvent] = []
        
        # 캘린더 그리드 (날짜 라벨들을 저장)
        self.day_labels: list[tk.Label] = []
        
        self._build_ui()
        self._load_month(self.current_year, self.current_month)

    def _build_ui(self) -> None:
        """학사일정 탭의 UI를 구성합니다 (좌: 캘린더, 우: 일정 리스트)."""
        self.configure(style="TFrame")
        
        # 메인 컨테이너
        main_container = ttk.Frame(self, style="TFrame", padding=15)
        main_container.pack(fill="both", expand=True)
        
        # 좌우 분할 (캘린더 45%, 리스트 55%)
        left_frame = ttk.Frame(main_container, style="Card.TFrame")
        left_frame.pack(side="left", fill="both", expand=False, padx=(0, 15))
        left_frame.configure(width=480)
        
        right_frame = ttk.Frame(main_container, style="Card.TFrame", padding=0)
        right_frame.pack(side="right", fill="both", expand=True)
        
        # === 좌측: 캘린더 영역 ===
        self._build_calendar(left_frame)
        
        # === 우측: 일정 리스트 영역 ===
        self._build_event_list(right_frame)

    def _build_calendar(self, parent: ttk.Frame) -> None:
        """캘린더 영역을 구성합니다."""
        # 강조색 띠
        ttk.Frame(parent, style="Accent.TFrame", height=4).pack(fill="x", side="top")
        
        inner = ttk.Frame(parent, style="Card.TFrame", padding=15)
        inner.pack(fill="both", expand=True)
        
        # 제목
        ttk.Label(inner, text="📅 학사일정 캘린더", style="CardTitle.TLabel").pack(pady=(0, 15))
        
        # 년도 네비게이션
        year_nav = ttk.Frame(inner, style="Card.TFrame")
        year_nav.pack(fill="x", pady=(0, 10))
        
        ttk.Button(
            year_nav, text="◀", width=3, style="Action.TButton",
            command=self._prev_year
        ).pack(side="left")
        
        self.year_label = ttk.Label(
            year_nav, text="2025년", style="CardBody.TLabel",
            font=("Segoe UI", 12, "bold"), foreground="#3F51B5"
        )
        self.year_label.pack(side="left", expand=True)
        
        ttk.Button(
            year_nav, text="▶", width=3, style="Action.TButton",
            command=self._next_year
        ).pack(side="right")
        
        # 월 네비게이션
        month_nav = ttk.Frame(inner, style="Card.TFrame")
        month_nav.pack(fill="x", pady=(0, 15))
        
        ttk.Button(
            month_nav, text="◀", width=3, style="Action.TButton",
            command=self._prev_month
        ).pack(side="left")
        
        self.month_label = ttk.Label(
            month_nav, text="10월", style="CardBody.TLabel",
            font=("Segoe UI", 11, "bold")
        )
        self.month_label.pack(side="left", expand=True)
        
        ttk.Button(
            month_nav, text="▶", width=3, style="Action.TButton",
            command=self._next_month
        ).pack(side="right")
        
        # 캘린더 그리드
        cal_grid = tk.Frame(inner, bg="white", relief="solid", borderwidth=1)
        cal_grid.pack(fill="both", expand=True)
        
        # 요일 헤더
        days_of_week = ["일", "월", "화", "수", "목", "금", "토"]
        for col, day in enumerate(days_of_week):
            color = "#D32F2F" if col == 0 else ("#1976D2" if col == 6 else "#424242")
            lbl = tk.Label(
                cal_grid, text=day, font=("Segoe UI", 9, "bold"),
                fg=color, bg="#F5F5F5", relief="solid", borderwidth=1
            )
            lbl.grid(row=0, column=col, sticky="nsew", padx=1, pady=1)
        
        # 날짜 그리드 (6주 x 7일) - Frame 구조로 변경
        self.day_cells = []  # Frame 저장
        self.day_labels = []  # 날짜 Label 저장
        self.day_indicators = []  # 색상 인디케이터 Frame 저장
        
        for row in range(1, 7):  # 1-6행
            for col in range(7):  # 0-6열
                # 날짜 셀 Frame
                cell_frame = tk.Frame(
                    cal_grid, bg="white", relief="flat",
                    cursor="hand2"
                )
                cell_frame.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
                
                # 날짜 숫자 Label (상단)
                date_label = tk.Label(
                    cell_frame, text="", font=("Segoe UI", 11),
                    bg="white", fg="#424242", anchor="n", height=2
                )
                date_label.pack(side="top", fill="both", expand=True, pady=(4, 0))
                
                # 색상 인디케이터 Frame (하단)
                indicator_frame = tk.Frame(cell_frame, bg="white", height=10)
                indicator_frame.pack(side="bottom", fill="x", pady=(0, 4))
                
                # 클릭 이벤트 바인딩
                cell_frame.bind("<Button-1>", self._on_date_click)
                date_label.bind("<Button-1>", self._on_date_click)
                indicator_frame.bind("<Button-1>", self._on_date_click)
                
                self.day_cells.append(cell_frame)
                self.day_labels.append(date_label)
                self.day_indicators.append(indicator_frame)
        
        # 그리드 가중치 설정 (균등 분배) + 최소 크기
        for col in range(7):
            cal_grid.grid_columnconfigure(col, weight=1, minsize=60)
        for row in range(7):
            cal_grid.grid_rowconfigure(row, weight=1, minsize=45)

    def _build_event_list(self, parent: ttk.Frame) -> None:
        """일정 리스트 영역을 구성합니다."""
        # 강조색 띠
        ttk.Frame(parent, style="Accent.TFrame", height=4).pack(fill="x", side="top")
        
        inner = ttk.Frame(parent, style="Card.TFrame", padding=20)
        inner.pack(fill="both", expand=True)
        
        # 헤더
        header = ttk.Frame(inner, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 15))
        
        self.list_title = ttk.Label(
            header, text="학사일정 목록", style="CardTitle.TLabel"
        )
        self.list_title.pack(side="left")
        
        ttk.Button(
            header, text="🔄 새로고침", style="Action.TButton",
            command=lambda: self._load_month(self.current_year, self.current_month)
        ).pack(side="right")
        
        # 리스트
        list_frame = ttk.Frame(inner, style="Card.TFrame")
        list_frame.pack(fill="both", expand=True)
        
        columns = ("range", "title")
        self.tree = ttk.Treeview(
            list_frame, columns=columns, show="headings",
            style="Dashboard.Treeview", height=18
        )
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        self.tree.heading("range", text="기간")
        self.tree.heading("title", text="내용")
        self.tree.column("range", width=180, anchor="center")
        self.tree.column("title", width=400, anchor="w")
        
        # 상태바
        bottom = ttk.Frame(inner, style="Card.TFrame")
        bottom.pack(fill="x", pady=(15, 0))
        self.var_status = tk.StringVar(value="준비됨.")
        ttk.Label(bottom, textvariable=self.var_status, style="CardInfo.TLabel").pack(side="right")

    def _load_month(self, year: int, month: int) -> None:
        """특정 년/월의 데이터를 로드하고 UI를 업데이트합니다."""
        self.current_year = year
        self.current_month = month
        self.selected_date = None
        
        # UI 업데이트
        self.year_label.config(text=f"{year}년")
        self.month_label.config(text=f"{month}월")
        self.list_title.config(text=f"{year}년 {month}월 학사일정")
        self.var_status.set("데이터를 불러오는 중...")
        self.update_idletasks()
        
        # 데이터 가져오기
        self.events = fetch_academic_events_for_month(year, month)
        
        # 캘린더 그리드 업데이트
        self._update_calendar()
        
        # 리스트 업데이트
        self._update_event_list()
        
        self.var_status.set(f"총 {len(self.events)}건 ({datetime.now().strftime('%H:%M:%S')})")

    def _update_calendar(self) -> None:
        """캘린더 그리드를 현재 년/월에 맞게 업데이트합니다."""
        import calendar
        
        # 일정별 색상 팔레트 (구분하기 쉬운 색상들)
        COLOR_PALETTE = [
            "#EF5350",  # 빨강
            "#42A5F5",  # 파랑
            "#66BB6A",  # 초록
            "#FFA726",  # 주황
            "#AB47BC",  # 보라
            "#26A69A",  # 청록
            "#FFCA28",  # 노랑
            "#EC407A",  # 핑크
        ]
        
        # 해당 월의 첫날과 마지막날 정보
        year, month = self.current_year, self.current_month
        first_day = date(year, month, 1)
        last_day_num = calendar.monthrange(year, month)[1]
        first_weekday = first_day.weekday()  # 0=월, 6=일
        start_offset = (first_weekday + 1) % 7  # 일요일 시작으로 변환 (0=일)
        
        # 오늘 날짜
        today = date.today()
        
        # 날짜별로 어떤 일정들이 있는지 매핑 (날짜 -> [(색상인덱스, 이벤트객체), ...])
        date_to_events: dict[date, list[tuple[int, AcadEvent]]] = {}
        for event_idx, ev in enumerate(self.events):
            # 각 일정에 색상 인디케이터용 인덱스 할당 (순환)
            color_idx = event_idx % len(COLOR_PALETTE)
            
            # 일정의 시작일부터 종료일까지 모든 날짜에 이 이벤트를 매핑합니다.
            # 이를 통해 달력의 각 날짜 셀마다 해당 날짜에 포함된 일정들을 쉽게 찾을 수 있습니다.
            delta = (ev.end - ev.start).days
            for i in range(delta + 1):
                current_date = ev.start + __import__('datetime').timedelta(days=i)
                if current_date not in date_to_events:
                    date_to_events[current_date] = []
                date_to_events[current_date].append((color_idx, ev))
        
        # 그리드 업데이트
        day_num = 1
        for idx in range(len(self.day_cells)):
            cell_frame = self.day_cells[idx]
            date_label = self.day_labels[idx]
            indicator_frame = self.day_indicators[idx]
            
            if idx < start_offset or day_num > last_day_num:
                # 빈 셀
                cell_frame.config(bg="white", relief="flat")
                date_label.config(text="", bg="white", fg="#424242")
                cell_frame.day_info = None
                # 인디케이터 지우기
                for widget in indicator_frame.winfo_children():
                    widget.destroy()
            else:
                # 날짜 셀
                current_date = date(year, month, day_num)
                cell_frame.day_info = current_date
                
                # 기본 스타일
                bg_color = "white"
                fg_color = "#424242"
                relief = "flat"
                borderwidth = 0
                
                # 일요일/토요일 색상
                col = idx % 7
                if col == 0:  # 일요일
                    fg_color = "#D32F2F"
                elif col == 6:  # 토요일
                    fg_color = "#1976D2"
                
                # 오늘 날짜
                if current_date == today:
                    relief = "solid"
                    borderwidth = 2
                
                # 날짜 숫자 표시
                date_label.config(text=str(day_num), bg=bg_color, fg=fg_color)
                
                # 인디케이터 업데이트
                # 기존 인디케이터 제거
                for widget in indicator_frame.winfo_children():
                    widget.destroy()
                
                # 해당 날짜의 일정들 가져오기
                events_on_date = date_to_events.get(current_date, [])
                
                if events_on_date:
                    # 일정이 있는 경우 - 색상 점 표시 (최대 3개)
                    indicator_frame.config(bg=bg_color)
                    
                    for i, (color_idx, _) in enumerate(events_on_date[:3]):
                        color = COLOR_PALETTE[color_idx]
                        # 작은 색상 점 (Frame으로 표시)
                        dot = tk.Frame(
                            indicator_frame, bg=color,
                            width=6, height=6, relief="flat"
                        )
                        dot.pack(side="left", padx=1)
                        dot.pack_propagate(False)
                else:
                    # 일정 없음
                    indicator_frame.config(bg=bg_color)
                
                # 셀 프레임 스타일 적용
                cell_frame.config(bg=bg_color, relief=relief, borderwidth=borderwidth)
                
                day_num += 1
    
    def _lighten_color(self, hex_color: str, factor: float = 0.7) -> str:
        """16진수 색상을 밝게 만듭니다."""
        # #RRGGBB -> (R, G, B)
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        # 흰색에 가깝게 (factor가 클수록 진함, 작을수록 밝음)
        r = int(r + (255 - r) * (1 - factor))
        g = int(g + (255 - g) * (1 - factor))
        b = int(b + (255 - b) * (1 - factor))
        
        return f'#{r:02x}{g:02x}{b:02x}'


    def _update_event_list(self, filter_date: date | None = None) -> None:
        """일정 리스트를 업데이트합니다 (필터링 옵션)."""
        # 트리 초기화
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 필터링
        if filter_date:
            # 특정 날짜의 일정만
            filtered = [
                ev for ev in self.events
                if ev.start <= filter_date <= ev.end
            ]
            self.list_title.config(text=f"{filter_date.strftime('%Y년 %m월 %d일')} 일정")
        else:
            # 전체 일정
            filtered = self.events
            self.list_title.config(text=f"{self.current_year}년 {self.current_month}월 학사일정")
        
        # 리스트 채우기
        for i, ev in enumerate(filtered):
            tag = "even" if i % 2 == 0 else "odd"
            if ev.start == ev.end:
                rng = ev.start.strftime("%Y-%m-%d")
            else:
                rng = f"{ev.start:%Y-%m-%d} ~ {ev.end:%Y-%m-%d}"
            self.tree.insert("", "end", values=(rng, ev.title), tags=(tag,))
        
        self.tree.tag_configure("odd", background="#f9f9f9")
        self.tree.tag_configure("even", background="white")
        
        self.var_status.set(f"{len(filtered)}건 표시 중")

    def _on_date_click(self, event) -> None:
        """캘린더의 날짜 클릭 이벤트 핸들러."""
        widget = event.widget
        
        # 클릭된 위젯이 cell_frame인지, 그 자식인지 확인
        if widget in self.day_cells:
            cell_frame = widget
        elif widget.master in self.day_cells:
            cell_frame = widget.master
        else:
            return  # 유효하지 않은 클릭
        
        if not hasattr(cell_frame, 'day_info') or cell_frame.day_info is None:
            return  # 빈 셀 클릭
        
        clicked_date = cell_frame.day_info
        
        # 선택 토글
        if self.selected_date == clicked_date:
            # 선택 해제
            self.selected_date = None
            self._update_calendar()
            self._update_event_list()
        else:
            # 새로 선택
            self.selected_date = clicked_date
            
            # 비주얼 피드백
            self._update_calendar()
            
            # 선택된 날짜 강조
            for idx, frame in enumerate(self.day_cells):
                if hasattr(frame, 'day_info') and frame.day_info == clicked_date:
                    frame.config(bg="#3F51B5")
                    self.day_labels[idx].config(bg="#3F51B5", fg="white", font=("Segoe UI", 10, "bold"))
                    self.day_indicators[idx].config(bg="#3F51B5")
            
            # 리스트 필터링
            self._update_event_list(clicked_date)

    def _prev_year(self) -> None:
        """이전 년도로 이동."""
        self._load_month(self.current_year - 1, self.current_month)

    def _next_year(self) -> None:
        """다음 년도로 이동."""
        self._load_month(self.current_year + 1, self.current_month)

    def _prev_month(self) -> None:
        """이전 달로 이동."""
        if self.current_month == 1:
            self._load_month(self.current_year - 1, 12)
        else:
            self._load_month(self.current_year, self.current_month - 1)

    def _next_month(self) -> None:
        """다음 달로 이동."""
        if self.current_month == 12:
            self._load_month(self.current_year + 1, 1)
        else:
            self._load_month(self.current_year, self.current_month + 1)



# ─────────────────────────────────────────────
# 7. 게시글 상세 내용 파싱 및 팝업 다이얼로그
# ─────────────────────────────────────────────

def fetch_notice_detail(url: str) -> dict | None:
    """
    게시글 상세 페이지의 HTML을 가져와 파싱합니다.
    
    Args:
        url: 게시글 상세 페이지 URL
        
    Returns:
        dict with keys: title, writer, date, views, content, attachments (리스트)
        실패 시 None 반환
    """
    # HTTP GET 요청
    code, html = _http_get(url, timeout=10)
    if code != 200:
        print(f"상세 페이지 HTTP 오류: {code}")
        return None
    
    detail = {}
    
    # 제목 추출: <h2 class="view-title">...</h2>
    m_title = re.search(r'<h2\s+class="view-title"[^>]*>(.*?)</h2>', html, re.DOTALL | re.IGNORECASE)
    if m_title:
        raw_title = m_title.group(1).strip()
        detail['title'] = re.sub(r'<.*?>', '', raw_title, flags=re.DOTALL).strip()
    else:
        detail['title'] = "(제목 없음)"
    
    # 작성자 추출: <dl class="writer"> ... <dd>...</dd>
    m_writer = re.search(r'<dl\s+class="writer"[^>]*>.*?<dd[^>]*>(.*?)</dd>', html, re.DOTALL | re.IGNORECASE)
    if m_writer:
        raw_writer = m_writer.group(1).strip()
        detail['writer'] = re.sub(r'<.*?>', '', raw_writer, flags=re.DOTALL).strip()
    else:
        detail['writer'] = "(작성자 미상)"
    
    # 작성일 추출: <dl class="write"> ... <dd><span>...</span>...</dd>
    m_date = re.search(r'<dl\s+class="write"[^>]*>.*?<dd[^>]*>(.*?)</dd>', html, re.DOTALL | re.IGNORECASE)
    if m_date:
        raw_date = m_date.group(1).strip()
        date_clean = re.sub(r'<.*?>', '', raw_date, flags=re.DOTALL).strip()
        detail['date'] = date_clean
    else:
        detail['date'] = ""
    
    # 조회수 추출: <dl class="count"> ... <dd>...</dd>
    m_views = re.search(r'<dl\s+class="count"[^>]*>.*?<dd[^>]*>(.*?)</dd>', html, re.DOTALL | re.IGNORECASE)
    if m_views:
        raw_views = m_views.group(1).strip()
        detail['views'] = re.sub(r'<.*?>', '', raw_views, flags=re.DOTALL).strip()
    else:
        detail['views'] = "0"
    
    # 본문 내용 추출: <div class="view-con">...</div>
    m_content = re.search(r'<div\s+class="view-con"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
    if m_content:
        # HTML 태그를 제거하고 텍스트만 추출 (간단한 방식)
        raw_content = m_content.group(1).strip()
        # <img> 태그는 [이미지] 로 표시
        raw_content = re.sub(r'<img[^>]*>', '[이미지]', raw_content, flags=re.IGNORECASE)
        # 나머지 태그 제거
        content_text = re.sub(r'<.*?>', '', raw_content, flags=re.DOTALL)
        # 연속된 공백/줄바꿈 정리
        content_text = re.sub(r'\s+', ' ', content_text).strip()
        detail['content'] = content_text if content_text else "(내용 없음)"
    else:
        detail['content'] = "(내용 없음)"
    
    # 첨부파일 추출: <div class="view-file"> 내의 링크들
    detail['attachments'] = []
    m_file_section = re.search(r'<div\s+class="view-file"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
    if m_file_section:
        file_html = m_file_section.group(1)
        # <a href="...">파일명</a> 패턴 찾기
        file_links = re.findall(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', file_html, re.DOTALL | re.IGNORECASE)
        for href, name_html in file_links:
            # 파일명에서 HTML 태그 제거
            file_name = re.sub(r'<.*?>', '', name_html, flags=re.DOTALL).strip()
            if file_name and href:
                # 상대 경로를 절대 경로로 변환
                full_url = urljoin(url, href)
                detail['attachments'].append({
                    'name': file_name,
                    'url': full_url
                })
    
    return detail


class NoticeDetailDialog(tk.Toplevel):
    """
    게시글 요약 정보를 표시하고 전체 내용은 브라우저에서 열도록 하는 다이얼로그입니다.
    HTML 렌더링, 이미지 표시, 첨부파일 다운로드를 위해 브라우저를 사용합니다.
    """
    
    def __init__(self, parent: tk.Misc, detail: dict, url: str) -> None:
        """
        Args:
            parent: 부모 위젯
            detail: fetch_notice_detail()이 반환한 dict
            url: 원본 게시글 URL
        """
        super().__init__(parent)
        self.detail = detail
        self.url = url
        
        # 창 설정
        self.title("게시글 상세보기")
        self.geometry("600x400")
        self.resizable(True, True)
        
        # 창을 화면 중앙에 배치
        from core import center_window
        center_window(self, 600, 400)
        
        # UI 구성
        self._build_ui()
        
        # 자동으로 브라우저 열기
        self.after(100, lambda: self._open_url(self.url))
        
        # 모달 창으로 설정
        self.transient(parent)
        self.grab_set()
    
    def _build_ui(self) -> None:
        """팝업 창의 UI를 구성합니다."""
        # 전체 배경 프레임
        main_frame = ttk.Frame(self, style="TFrame", padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # 제목 영역
        title_label = ttk.Label(
            main_frame,
            text=self.detail.get('title', '(제목 없음)'),
            style="CardTitle.TLabel",
            font=("Segoe UI", 16, "bold"),
            foreground="#3F51B5",
            wraplength=550
        )
        title_label.pack(fill="x", pady=(0, 15))
        
        # 메타 정보 카드
        meta_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=15)
        meta_frame.pack(fill="x", pady=(0, 20))
        
        # 강조색 띠
        ttk.Frame(meta_frame, style="Accent.TFrame", height=3).pack(fill="x", side="top")
        
        # 메타 정보 내용
        meta_inner = ttk.Frame(meta_frame, style="Card.TFrame")
        meta_inner.pack(fill="x", padx=10, pady=10)
        
        info_lines = [
            f"작성자: {self.detail.get('writer', '-')}",
            f"작성일: {self.detail.get('date', '-')}",
            f"조회수: {self.detail.get('views', '0')}"
        ]
        
        for line in info_lines:
            ttk.Label(
                meta_inner,
                text=line,
                style="CardInfo.TLabel",
                font=("Segoe UI", 10)
            ).pack(anchor="w", pady=2)
        
        # 첨부파일 정보 (있는 경우)
        attachments = self.detail.get('attachments', [])
        if attachments:
            attach_label = ttk.Label(
                main_frame, 
                text=f"📎 첨부파일: {len(attachments)}개",
                style="CardBody.TLabel",
                font=("Segoe UI", 11, "bold")
            )
            attach_label.pack(fill="x", pady=(10, 5))
        
        # 안내 메시지
        info_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=20)
        info_frame.pack(fill="both", expand=True, pady=(20, 10))
        
        ttk.Label(
            info_frame,
            text="📄 전체 내용 보기",
            style="CardBody.TLabel",
            font=("Segoe UI", 12, "bold"),
            foreground="#3F51B5"
        ).pack(pady=(0, 10))
        
        ttk.Label(
            info_frame,
            text="본문 내용, 이미지, 첨부파일을 제대로 보시려면\n브라우저에서 확인하세요.",
           style="CardInfo.TLabel",
            font=("Segoe UI", 10),
            justify="center"
        ).pack(pady=(0, 15))
        
        # 브라우저에서 열기 버튼
        btn_open = ttk.Button(
            info_frame,
            text="🌐 브라우저에서 열기",
            style="Action.TButton",
            command=lambda: self._open_url(self.url)
        )
        btn_open.pack(pady=5)
        
        # 닫기 버튼
        btn_close = ttk.Button(
            main_frame,
            text="닫기",
            style="Action.TButton",
            command=self.destroy
        )
        btn_close.pack(pady=(10, 0))
    
    def _open_url(self, url: str) -> None:
        """브라우저에서 URL을 엽니다."""
        import webbrowser
        webbrowser.open(url)



# ─────────────────────────────────────────────
# 8. 대시보드 메인 탭 클래스
# ─────────────────────────────────────────────

class DashboardTab(ttk.Frame):
    """
    '대시보드' 탭의 본체 프레임입니다.
    내부에 Notebook을 하나 더 두어 3개의 하위 탭(학사공지, 학사일정, 취업정보)을 관리합니다.
    """

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        configure_dashboard_style()  # 대시보드 전용 스타일 초기화
        self._build_ui()  # UI 구성

    def _build_ui(self) -> None:
        """대시보드 탭의 전체 UI를 구성합니다."""
        # 메인 컨테이너
        main_container = ttk.Frame(self)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # 하위 탭을 위한 Notebook 생성
        nb = ttk.Notebook(main_container)
        nb.pack(expand=True, fill="both")

        # 각 하위 탭 프레임 생성
        frm_haksa = DashboardHaksaFrame(nb)
        frm_acad = DashboardAcadFrame(nb)
        frm_jobs = DashboardJobsFrame(nb)

        # Notebook에 탭 추가
        nb.add(frm_haksa, text="  학사공지  ")
        nb.add(frm_jobs, text="  취업정보  ")
        nb.add(frm_acad, text="  학사일정  ")
