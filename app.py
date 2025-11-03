# ─────────────────────────────────────────────────────────
# Tkinter: 파이썬 기본 GUI                                   # 앱의 목적/범주 설명
# ─────────────────────────────────────────────────────────
# 간단한 ToDo 관리 + 프리젠테이션 타이머 + 실시간 '성과 리포트' 대시보드를 제공하는 Tkinter 데스크톱 앱이다.
# 또한 ChatGPT 탭 UI를 개선(말풍선/스크롤/멀티라인 입력/모델 콤보박스)하고, 모델 목록을 API로 새로고침할 수 있게 했다.

from dataclasses import dataclass  # dataclass 데코레이터로 생성자/표현 등 보일러플레이트 자동 생성
from datetime import date, datetime, timedelta  # 날짜(date), 날짜시간(datetime), 기간(timedelta)
from pathlib import Path  # 운영체제 무관한 경로 처리
import time  # 단조 증가 시계(time.monotonic) 사용 → 시스템 시간 변경 영향을 안 받는 타이머
import math  # 올림/내림, 보간 계산 등에 사용
import sqlite3 as sql  # 내장 SQLite DB로 간단 영속화(파일 1개)
import tkinter as tk  # Tkinter 기본 위젯
from tkinter import ttk, messagebox  # ttk(현대식 스킨), messagebox(모달 알림/확인)
import json  # New OpenAI API 요청/응답의 JSON 직렬화/역직렬화에 사용
import threading  # New 네트워크 호출을 백그라운드 스레드에서 실행해 UI 멈춤 방지
from urllib import request as urlrequest, error as urlerror  # New 추가 의존성 없이 HTTP 호출(urllib)
import traceback  # New 예외 시 디버그를 돕는 스택 출력(필요 시 로그 용도)
import random  # New 컨페티/말풍선 ID 등 랜덤 값에 사용(경미하게 사용)

# ─────────────────────────────────────────────────────────
# 상수/포맷/공용 패딩                                         # 상수/공용 값 묶음
# ─────────────────────────────────────────────────────────
DATE_FMT = "%Y-%m-%d"  # 날짜 문자열 형식(예: 2025-09-16) — DB/표시 포맷을 통일해 파싱오류를 줄임
STATUS_ICON = {0: "☐", 1: "⏳", 2: "✔"}  # 상태코드→아이콘 매핑(미완/진행/완료)
STATUS_TEXT = {0: "미완료", 1: "진행중", 2: "완료"}  # 상태코드→읽을 수 있는 텍스트
PAD6 = {"padx": 10, "pady": 6}  # grid/pack 공통 여백 프리셋(6)
PAD8 = {"padx": 10, "pady": 8}  # 공통 여백 프리셋(8)

# ChatGPT 탭에서 사용할 OpenAI API 엔드포인트/기본 모델 상수
OPENAI_URL_MODELS = "https://api.openai.com/v1/models"  # API 키 검증/모델 목록 조회 엔드포인트
OPENAI_URL_CHAT = "https://api.openai.com/v1/chat/completions"  # 대화 생성 엔드포인트(표준 Chat Completions)
CHAT_MODEL_DEFAULT = "gpt-4o-mini"  # 기본 모델명(콤보박스 기본값)

# ChatGPT 탭의 추천 기본 모델 목록(오프라인 상황 대비) — 필요 시 새로고침으로 대체 가능
DEFAULT_MODEL_CANDIDATES = [
    "gpt-4o-mini",      # 경량 고성능(기본)
    "gpt-4o",           # 멀티모달 고성능
    "gpt-4.1-mini",     # 최신 경량(예시)
    "gpt-4.1",          # 최신 고성능(예시)
    "gpt-4-turbo",      # Turbo 계열(예시)
    "gpt-3.5-turbo",    # 구세대 호환(예시)
]

# ─────────────────────────────────────────────────────────
# DB 경로 고정(스크립트 폴더) + 대화형 환경 폴백             # 실행 환경 차이에 따른 DB 경로 보정
# ─────────────────────────────────────────────────────────
try:
    DB_PATH = str(Path(__file__).with_name("todo.db"))  # 스크립트 파일과 같은 폴더에 todo.db 생성/사용
except NameError:
    DB_PATH = "todo.db"  # __file__이 없는 인터프리터/노트북 환경에서는 현재 작업 폴더에 저장

# ─────────────────────────────────────────────────────────
# 유틸: 날짜 파싱 / 창 중앙 배치 / HTTP 요청                 # 자주 쓰는 헬퍼 함수 모음
# ─────────────────────────────────────────────────────────
def parse_date(s: str) -> datetime:
    """날짜 문자열(YYYY-MM-DD)을 datetime 객체로 변환."""
    return datetime.strptime(s, DATE_FMT)  # 형식 불일치 시 ValueError 발생 → 호출부에서 UX 메시지 처리

def center_over(parent: tk.Tk, win: tk.Toplevel) -> None:
    """부모창 기준으로 자식창을 화면 중앙에 배치(화면 밖으로 나가지 않게 보정 포함)."""
    parent.update_idletasks()  # 부모 레이아웃/위치 정보 최신화
    win.update_idletasks()     # 자식 레이아웃/크기 정보 최신화
    px, py = parent.winfo_rootx(), parent.winfo_rooty()     # 부모 좌상단의 화면 절대좌표
    pw, ph = parent.winfo_width(), parent.winfo_height()    # 부모 폭/높이
    ww, wh = win.winfo_width(), win.winfo_height()          # 자식 폭/높이
    x = max(0, min(px + (pw - ww) // 2, win.winfo_screenwidth() - ww))  # 계산된 X 좌표 클램프
    y = max(0, min(py + (ph - wh) // 2, win.winfo_screenheight() - wh))  # 계산된 Y 좌표 클램프
    win.geometry(f"+{x}+{y}")  # 크기는 유지하고 위치만 이동

# ─────────────────────────────────────────────────────────
# HTTP 유틸(urllib): 외부 의존성 없이 GET/POST 호출           # OpenAI API 호출을 표준 라이브러리로 처리
# ─────────────────────────────────────────────────────────
def _http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> tuple[int, str]:
    """단순 GET 요청을 보내고 (상태코드, 텍스트)를 반환한다."""
    req = urlrequest.Request(url, method="GET", headers=headers or {})  # GET Request 객체 생성
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # 타임아웃과 함께 전송
            code = getattr(resp, "status", resp.getcode())  # 상태코드 추출(구현 호환)
            text = resp.read().decode("utf-8", "ignore")  # 본문을 문자열로 디코드
            return code, text  # 정상 응답 반환
    except urlerror.HTTPError as e:  # HTTP 오류(4xx/5xx)
        return e.code, e.read().decode("utf-8", "ignore")  # 오류 본문 포함
    except Exception as e:  # 네트워크/기타 예외
        return 0, f"{e}"  # 0 코드는 로컬 예외 의미

def _http_post(url: str, headers: dict[str, str] | None = None, data: dict | None = None, timeout: int = 30) -> tuple[int, str]:
    """단순 POST(JSON) 요청을 보내고 (상태코드, 텍스트)를 반환한다."""
    body = json.dumps(data or {}).encode("utf-8")  # JSON 직렬화 후 바이트로 인코딩
    hdrs = {"Content-Type": "application/json"}  # JSON 본문 헤더 기본값
    if headers:  # 추가 헤더 병합
        hdrs.update(headers)  # 사용자 헤더 덮어쓰기
    req = urlrequest.Request(url, data=body, method="POST", headers=hdrs)  # POST Request 준비
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # 타임아웃과 함께 전송
            code = getattr(resp, "status", resp.getcode())  # 상태코드 획득
            text = resp.read().decode("utf-8", "ignore")  # 본문 디코드
            return code, text  # 정상 응답 반환
    except urlerror.HTTPError as e:  # HTTP 오류(4xx/5xx)
        return e.code, e.read().decode("utf-8", "ignore")  # 오류 본문 포함
    except Exception as e:  # 네트워크/기타 예외
        return 0, f"{e}"  # 0 코드는 로컬 예외 의미

# ─────────────────────────────────────────────────────────
# 데이터 모델                                                 # 도메인 모델 정의
# ─────────────────────────────────────────────────────────
@dataclass
class Todo:
    """할 일 1건을 표현하는 데이터 모델."""
    title: str  # 제목
    start: str  # 시작일(YYYY-MM-DD)
    end: str    # 종료일(YYYY-MM-DD)
    desc: str = ""   # 상세 설명(옵션)
    status: int = 0  # 상태 코드(0=미완,1=진행,2=완료)

    def cycle(self) -> None:
        """상태를 다음 단계로 순환(0→1→2→0)."""
        self.status = (self.status + 1) % 3  # 한 번 호출 시 상태가 다음으로

    def display(self, today: date | None = None) -> str:
        """리스트박스에 표시할 1줄 요약 문자열을 생성(D-DAY 태그 포함)."""
        icon = STATUS_ICON.get(self.status, "☐")  # 상태에 맞는 아이콘
        try:
            d_end = datetime.strptime(self.end, DATE_FMT).date()  # 종료일 파싱
        except Exception:
            return f"{icon} {self.start} ~ {self.end} | {self.title}"  # 파싱 실패 시 안전 폴백
        today = today or date.today()  # today 미지정 시 시스템 오늘 날짜
        delta = (d_end - today).days   # 종료일까지 남은 일수
        if delta < 0:
            tag = "⛔ 지남"            # 마감 초과
        elif delta == 0:
            tag = "⚠️ D-DAY"          # 마감 당일
        elif delta <= 3:
            tag = f"⏰ D-{delta}"      # 3일 이내 임박
        else:
            tag = f"D-{delta}"         # 일반 D-N
        return f"{icon} [{tag}] {self.start} ~ {self.end} | {self.title}"  # 최종 표시 문자열

# ─────────────────────────────────────────────────────────
# DB 연동                                                     # 영속화 레이어
# ─────────────────────────────────────────────────────────
def _db() -> sql.Connection:
    """SQLite 연결을 열어 반환(컨텍스트 매니저와 함께 사용)."""
    return sql.connect(DB_PATH)  # 연결 열고 반환

def init_db() -> None:
    """앱 최초 실행 시 todos 테이블 생성(존재하면 무시)."""
    with _db() as con:  # 연결 컨텍스트
        con.execute("""
            CREATE TABLE IF NOT EXISTS todos(
                id     INTEGER PRIMARY KEY AUTOINCREMENT,  -- 내부 PK
                title  TEXT NOT NULL,                      -- 제목
                start  TEXT NOT NULL,                      -- 시작일(YYYY-MM-DD)
                end    TEXT NOT NULL,                      -- 종료일(YYYY-MM-DD)
                memo   TEXT DEFAULT '',                    -- 상세설명(예약어 피하려고 'memo' 사용)
                status INTEGER NOT NULL CHECK(status IN (0,1,2)) -- 상태코드 제약
            )
        """)  # 테이블 스키마 생성

def load_all() -> list[Todo]:
    """DB의 모든 항목을 읽어 메모리(list[Todo])로 반환."""
    init_db()  # 테이블 존재 보장
    with _db() as con:  # 연결 컨텍스트
        rows = con.execute(
            "SELECT title, start, end, memo, status FROM todos ORDER BY id"  # 입력 순 정렬
        ).fetchall()  # 모든 행 조회
    return [Todo(title, start, end, memo, status) for (title, start, end, memo, status) in rows]  # 행→모델 변환

def save_all(items: list[Todo]) -> None:
    """현재 메모리 리스트 상태를 DB에 전량 반영(덮어쓰기 방식)."""
    with _db() as con:  # 트랜잭션 컨텍스트
        con.execute("DELETE FROM todos")  # 기존 전량 삭제
        con.executemany(
            "INSERT INTO todos(title, start, end, memo, status) VALUES(?,?,?,?,?)",
            [(t.title, t.start, t.end, t.desc, t.status) for t in items],
        )  # 일괄 삽입

# ─────────────────────────────────────────────────────────
# 할 일 추가/편집 팝업(모달)                                  # 입력/편집 UX
# ─────────────────────────────────────────────────────────
class TodoDialog(tk.Toplevel):
    """할 일 추가/편집을 위한 모달 대화상자."""

    def __init__(self, parent: tk.Tk, title: str, prefill: str = "", item: Todo | None = None):
        """부모창, 타이틀, 제목 기본값(prefill), 편집 대상(item)을 받아 팝업을 구성."""
        super().__init__(parent)  # 부모 루트에 부착된 Toplevel 생성
        self.result: Todo | None = None              # 저장 성공 시 회수할 결과
        self._orig_status = item.status if item else 0  # 편집이면 기존 상태 유지

        self.title(title)       # 창 타이틀
        self.transient(parent)  # 부모창 위에 표시
        self.resizable(False, False)  # 크기 고정
        self.grab_set()         # 모달(닫을 때까지 다른 창 포커스 차단)

        pad = PAD6  # 공용 여백 프리셋
        today_str = date.today().isoformat()  # 오늘 날짜 문자열

        # 제목 필드
        ttk.Label(self, text="제목").grid(row=0, column=0, sticky="w", **pad)  # 제목 라벨
        self.ent_title = ttk.Entry(self, width=38)  # 제목 입력
        self.ent_title.grid(row=0, column=1, sticky="w", **pad)  # 배치
        self.ent_title.insert(0, prefill or (item.title if item else ""))  # prefill 우선

        # 시작일
        ttk.Label(self, text="시작일 (YYYY-MM-DD)").grid(row=1, column=0, sticky="w", **pad)  # 라벨
        self.ent_start = ttk.Entry(self, width=20)  # 입력
        self.ent_start.grid(row=1, column=1, sticky="w", **pad)  # 배치
        self.ent_start.insert(0, item.start if item else today_str)  # 기본: 오늘

        # 종료일
        ttk.Label(self, text="종료일 (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", **pad)  # 라벨
        self.ent_end = ttk.Entry(self, width=20)  # 입력
        self.ent_end.grid(row=2, column=1, sticky="w", **pad)  # 배치
        self.ent_end.insert(0, item.end if item else today_str)  # 기본: 오늘

        # 상세 설명(멀티라인)
        ttk.Label(self, text="상세설명").grid(row=3, column=0, sticky="nw", **pad)  # 라벨
        self.txt_desc = tk.Text(self, width=40, height=6)  # 멀티라인 입력
        self.txt_desc.grid(row=3, column=1, **pad)  # 배치
        if item:  # 편집 모드
            self.txt_desc.insert("1.0", item.desc)  # 기존 설명 채움

        # 저장/취소 버튼 행
        btns = ttk.Frame(self)  # 버튼 컨테이너
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=10)  # 오른쪽 정렬
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="right", padx=6)  # 취소
        ttk.Button(btns, text="저장", command=self._on_save).pack(side="right")  # 저장

        # 팝업 배치/포커스
        self.update_idletasks()     # 내부 위젯 크기 계산 갱신
        center_over(parent, self)   # 부모 기준 중앙 배치
        self.ent_title.focus_set()  # 첫 입력 포커스

    def _on_save(self) -> None:
        """입력 검증 후 self.result에 Todo를 세팅하고 팝업을 닫는다."""
        title = self.ent_title.get().strip()  # 제목
        start = self.ent_start.get().strip()  # 시작일
        end   = self.ent_end.get().strip()    # 종료일
        desc  = self.txt_desc.get("1.0", "end").strip()  # 상세설명

        if not title:  # 제목 필수
            messagebox.showwarning("확인", "제목을 입력하세요.", parent=self)
            self.ent_title.focus_set()
            return

        try:
            d1 = parse_date(start)  # 시작일 파싱
        except Exception:
            messagebox.showerror("날짜 오류", "시작일 형식이 잘못되었습니다.\n예: 2025-09-16", parent=self)
            self.ent_start.focus_set()
            return

        try:
            d2 = parse_date(end)  # 종료일 파싱
        except Exception:
            messagebox.showerror("날짜 오류", "종료일 형식이 잘못되었습니다.\n예: 2025-09-18", parent=self)
            self.ent_end.focus_set()
            return

        if d2 < d1:  # 논리 검증
            messagebox.showerror("날짜 오류", "종료일은 시작일보다 빠를 수 없습니다.", parent=self)
            self.ent_end.focus_set()
            return

        self.result = Todo(title=title, start=start, end=end, desc=desc, status=self._orig_status)  # 결과 구성
        self.destroy()  # 팝업 닫기

# ─────────────────────────────────────────────────────────
# 메인 앱(노트북 탭: 할 일 / 타이머 / 리포트 / ChatGPT)       # 최상위 윈도우/탭 구조
# ─────────────────────────────────────────────────────────
class TodoApp(tk.Tk):
    """최상위 윈도우: 탭 컨테이너 + 각 탭 로직을 포함."""

    def __init__(self) -> None:
        """창 생성/크기/탭 구성/DB 로드/초기 렌더링까지 한 번에 수행."""
        super().__init__()  # Tk 루트 초기화
        self.title("갓생살기")  # 창 타이틀 설정
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()  # 스크린 크기
        x, y = (sw - 620) // 2, (sh - 430) // 2  # 창 중앙 좌표(조금 넓힘: chat UI 공간 확보)
        self.geometry(f"620x430+{x}+{y}")  # 고정 크기 지정

        self.protocol("WM_DELETE_WINDOW", self._on_close)  # 닫기 이벤트 바인딩

        # 애플리케이션 상태(메모리)
        self.todos: list[Todo] = []  # 할 일 리스트

        # ── 타이머 상태(모노토닉 기반) ──
        self._timer_after_id: str | None = None  # 타이머 틱 루프 ID(after_cancel용)
        self._blink_after_id: str | None = None  # 타임업 깜박임 루프 ID
        self.timer_running: bool = False  # 타이머 동작 여부
        self.timer_total_sec: int = 0     # 총 타이머 시간(초)
        self.timer_warn_sec: int = 30     # 경고 시작 임계(초)
        self.timer_end_mono: float = 0.0  # 단조 시계 기준 종료 목표 시각
        self.timer_remain_sec: int = 0    # 남은 시간(초)
        self._blink_on: bool = False      # 깜박임 토글 상태

        # ── 리포트 루프/마일스톤 상태 ──
        self._report_after_id: str | None = None  # 리포트 자동 갱신 루프 ID
        self._last_rate: float = 0.0              # 이전 완료율
        self._report_booted: bool = False         # 첫 갱신 여부

        # ── ChatGPT 탭 상태 ──
        self._api_key: str = ""  # 사용자가 입력/검증한 OpenAI API 키(메모리 보관·디스크 저장 안 함)
        self.api_key_valid: bool = False  # 키 검증 성공 여부
        self.chat_messages: list[dict] = []  # Chat Completions에 전달할 대화 히스토리
        self._chat_busy: bool = False  # 현재 응답 대기 중인지 여부
        self._key_thread: threading.Thread | None = None  # 키 검증 백그라운드 스레드
        self._chat_thread: threading.Thread | None = None  # 채팅 백그라운드 스레드
        self._typing_anim_after_id: str | None = None  # 타이핑 표시 애니메이션 after ID
        self._model_options: list[str] = DEFAULT_MODEL_CANDIDATES.copy()  # 콤보박스 모델 목록(초기값)
        self._bubble_seq: int = 0  # 말풍선 식별용 증가 시퀀스(옵션)

        # 탭 컨테이너
        nb = ttk.Notebook(self)  # 노트북 위젯 생성
        nb.pack(expand=True, fill="both", padx=10, pady=10)  # 배치

        # 탭 프레임
        self.tab_todo   = ttk.Frame(nb)  # 할 일 탭
        self.tab_timer  = ttk.Frame(nb)  # 타이머 탭
        self.tab_report = ttk.Frame(nb)  # 리포트 탭
        self.tab_chat   = ttk.Frame(nb)  # ChatGPT 탭

        # 탭 추가
        nb.add(self.tab_todo, text="할 일")
        nb.add(self.tab_timer, text="타이머")
        nb.add(self.tab_report, text="리포트")
        nb.add(self.tab_chat, text="ChatGPT")

        # 각 탭 UI 구성
        self._build_todo_tab()    # 할 일 탭 구성
        self._build_timer_tab()   # 타이머 탭 구성
        self._build_report_tab()  # 리포트 탭 구성
        self._build_chat_tab()    # ChatGPT 탭 구성(말풍선/모델 콤보박스)

        # DB → 메모리 → UI 초기 렌더
        init_db()           # 테이블 보장
        self.todos = load_all()  # DB에서 로드
        self.refresh_list() # 리스트/리포트 초기 렌더

    # ─────────────────────────────────────────────────────────
    # [할 일] 탭 UI                                            # ToDo 탭 구성
    # ─────────────────────────────────────────────────────────
    def _build_todo_tab(self) -> None:
        """할 일 탭의 입력/버튼/리스트 UI를 구성."""
        top = ttk.Frame(self.tab_todo)  # 상단 입력/버튼 컨테이너
        top.pack(fill="x", padx=10, pady=10)  # 배치

        self.quick_entry = ttk.Entry(top)  # 제목 한 줄 입력 위젯
        self.quick_entry.pack(side="left", fill="x", expand=True)
        self.quick_entry.focus()  # 시작 시 포커스
        self.quick_entry.bind("<Return>", lambda e: self.add_todo())  # Enter→추가

        ttk.Button(top, text="추가",   command=self.add_todo).pack(side="left", padx=6)  # 추가
        ttk.Button(top, text="편집",   command=self.edit_selected).pack(side="left", padx=6)  # 편집
        ttk.Button(top, text="삭제",   command=self.delete_selected).pack(side="left", padx=6)  # 삭제
        ttk.Button(top, text="상태전환 (☐→⏳→✔)", command=self.cycle_status_selected).pack(side="left", padx=6)  # 상태순환

        mid = ttk.Frame(self.tab_todo)  # 리스트/스크롤 컨테이너
        mid.pack(fill="both", expand=True, padx=10, pady=5)

        self.listbox = tk.Listbox(mid, height=10, selectmode="extended")  # 다중 선택 가능
        self.listbox.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)  # 세로 스크롤바
        scroll.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)  # 리스트↔스크롤 연동

        # 단축키 바인딩
        self.listbox.bind("<Delete>", lambda e: self.delete_selected())  # Del: 삭제
        self.listbox.bind("<space>",  self._on_space_toggle)             # Space: 상태 토글
        self.listbox.bind("<Double-Button-1>", self.show_details)        # 더블클릭: 상세 보기

    # ─────────────────────────────────────────────────────────
    # [타이머] 탭 UI                                            # 발표 타이머 UI
    # ─────────────────────────────────────────────────────────
    def _build_timer_tab(self) -> None:
        """발표 타이머 입력/컨트롤/피드백 UI 구성."""
        top = ttk.Frame(self.tab_timer)  # 상단 입력/컨트롤 컨테이너
        top.pack(fill="x", **PAD8)

        ttk.Label(top, text="발표 시간(분)").pack(side="left")  # 분 입력 라벨
        self.ent_minutes = ttk.Entry(top, width=6)  # 분 입력
        self.ent_minutes.pack(side="left", padx=(4, 12))
        self.ent_minutes.insert(0, "5")  # 기본 5분

        ttk.Label(top, text="경고 임계(초)").pack(side="left")  # 경고 임계 라벨
        self.ent_warn = ttk.Entry(top, width=6)  # 경고 임계
        self.ent_warn.pack(side="left", padx=(4, 12))
        self.ent_warn.insert(0, "30")  # 기본 30초

        self.btn_start = ttk.Button(top, text="시작",     command=self.start_timer)  # 시작
        self.btn_pause = ttk.Button(top, text="일시정지", command=self.pause_resume_timer, state="disabled")  # 일시정지
        self.btn_reset = ttk.Button(top, text="초기화",   command=self.reset_timer,       state="disabled")  # 초기화
        self.btn_start.pack(side="left", padx=4)
        self.btn_pause.pack(side="left", padx=4)
        self.btn_reset.pack(side="left", padx=4)

        mid = ttk.Frame(self.tab_timer)  # 중앙 표시 영역
        mid.pack(expand=True, fill="both", **PAD8)
        self.lbl_timer = tk.Label(mid, text="00:00", font=("Helvetica", 36, "bold"))  # 남은 시간 라벨
        self.lbl_timer.pack(pady=10)
        self.pb_timer  = ttk.Progressbar(mid, orient="horizontal", mode="determinate", length=360)  # 진행률 바
        self.pb_timer.pack(fill="x", padx=20, pady=10)

        bottom = ttk.Frame(self.tab_timer)  # 하단 프레임
        bottom.pack(fill="x", **PAD8)
        ttk.Label(
            bottom,
            text="Tip) 남은 시간이 임계값 이하로 떨어지면 주황색, 0이 되면 빨간색으로 깜박이며 종료를 알립니다."
        ).pack(anchor="w")

    # ─────────────────────────────────────────────────────────
    # [리포트] 탭 UI (텍스트 KPI + 도넛 + 스택바 + 주간 히트맵)  # 대시보드 구성
    # ─────────────────────────────────────────────────────────
    def _build_report_tab(self) -> None:
        """리포트 탭의 KPI 텍스트/간단 시각화 위젯을 구성."""
        frm = ttk.Frame(self.tab_report)  # 루트 컨테이너
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        ttk.Label(frm, text="📊 주간 성과 리포트", font=("Helvetica", 14, "bold")
                 ).pack(anchor="w", pady=(0, 8))  # 제목

        top = ttk.Frame(frm)  # 상단 행 컨테이너
        top.pack(fill="x")

        self.cnv_ring = tk.Canvas(top, width=160, height=160, highlightthickness=0)  # 도넛 캔버스
        self.cnv_ring.pack(side="left", padx=(0, 16))

        right = ttk.Frame(top)  # 우측 KPI 묶음
        right.pack(side="left", fill="both", expand=True)
        self.lbl_rate   = ttk.Label(right, text="완료율 0.0%", font=("Helvetica", 12, "bold"))  # 완료율 라벨
        self.lbl_rate.pack(anchor="w", pady=(4, 6))

        self.var_avg    = tk.StringVar(value="평균 기간: 0.0일")  # 평균 기간
        self.var_soon   = tk.StringVar(value="마감 임박: 0건")    # 임박 건수
        self.var_over   = tk.StringVar(value="지남: 0건")        # 지남 건수
        self.var_counts = tk.StringVar(value="상태 구성: 미완 0 · 진행 0 · 완료 0")  # 상태 구성

        ttk.Label(right, textvariable=self.var_avg   ).pack(anchor="w")
        ttk.Label(right, textvariable=self.var_soon  ).pack(anchor="w")
        ttk.Label(right, textvariable=self.var_over  ).pack(anchor="w")
        ttk.Label(right, textvariable=self.var_counts).pack(anchor="w", pady=(2, 0))

        self.cnv_stack = tk.Canvas(frm, height=22, highlightthickness=0)  # 스택바 캔버스
        self.cnv_stack.pack(fill="x", pady=(10, 6))

        self.cnv_heat = tk.Canvas(frm, height=56, highlightthickness=0)  # 히트맵 캔버스
        self.cnv_heat.pack(fill="x")

        ttk.Label(frm, text="※ 5초마다 자동 갱신 · 리스트 변경 시 즉시 반영", foreground="#666"
                 ).pack(anchor="w", pady=(8, 0))  # 안내

    # ─────────────────────────────────────────────────────────
    # [ChatGPT] 탭 UI — ***개선 포인트***                      # 말풍선/모델 콤보박스/멀티라인 입력
    # ─────────────────────────────────────────────────────────
    def _build_chat_tab(self) -> None:
        """ChatGPT 탭의 키 입력/검증 + 모델 선택 + 대화(말풍선) UI를 구성."""
        # 전체 루트 프레임(탭 내부 컨테이너)
        root = ttk.Frame(self.tab_chat)  # 루트 프레임
        root.pack(fill="both", expand=True, padx=10, pady=10)  # 여백/채움

        # ── 상단: API 키 입력/표시/검증 ──
        row1 = ttk.Frame(root)  # 상단 설정 행
        row1.pack(fill="x", pady=(0, 6))
        ttk.Label(row1, text="OpenAI API 키").pack(side="left")  # 키 라벨

        self.ent_api_key = ttk.Entry(row1, width=38, show="*")  # 키 입력(마스킹)
        self.ent_api_key.pack(side="left", padx=(6, 6))

        self.var_show_key = tk.BooleanVar(value=False)  # '표시' 토글 상태
        chk = ttk.Checkbutton(row1, text="표시", variable=self.var_show_key, command=self._toggle_key_visibility)  # 표시 토글
        chk.pack(side="left", padx=(0, 6))

        self.btn_key_check = ttk.Button(row1, text="검증", command=self.validate_api_key)  # 키 검증 버튼
        self.btn_key_check.pack(side="left")

        # ── 두 번째 행: 모델 선택 + 상태 라벨 + 모델 새로고침 ──
        row2 = ttk.Frame(root)  # 두 번째 설정 행
        row2.pack(fill="x", pady=(4, 6))
        ttk.Label(row2, text="모델").pack(side="left")  # 모델 라벨

        # 모델 콤보박스(드롭다운) — 기본 후보 목록으로 초기화
        self.cmb_model = ttk.Combobox(row2, width=20, state="readonly", values=self._model_options)  # 콤보박스
        self.cmb_model.pack(side="left", padx=(6, 8))  # 배치
        self.cmb_model.set(CHAT_MODEL_DEFAULT)  # 기본 선택 세팅

        # 모델 새로고침 버튼 — /v1/models를 호출해 콤보박스를 최신화
        self.btn_model_refresh = ttk.Button(row2, text="모델 새로고침", command=lambda: self._refresh_model_list(silent=False))
        self.btn_model_refresh.pack(side="left", padx=(0, 10))  # 배치

        # 현재 키 상태 라벨
        self.lbl_key_status = ttk.Label(row2, text="🔒 키 미검증", foreground="#666")  # 상태 라벨
        self.lbl_key_status.pack(side="left")  # 배치

        # ── 중앙: 대화 로그(말풍선) + 스크롤 ──
        # 말풍선 UI는 Canvas + 내부 Frame(창 윈도우)을 사용해 부드러운 스크롤을 제공한다.
        chat_area = ttk.Frame(root)  # 대화 영역 컨테이너
        chat_area.pack(fill="both", expand=True, pady=(6, 6))  # 배치

        self.chat_canvas = tk.Canvas(chat_area, highlightthickness=0, bg="#f7f9fc")  # 스크롤 캔버스(연한 배경)
        self.chat_canvas.pack(side="left", fill="both", expand=True)  # 캔버스 확장 배치

        self.chat_scroll = ttk.Scrollbar(chat_area, orient="vertical", command=self.chat_canvas.yview)  # 스크롤바
        self.chat_scroll.pack(side="left", fill="y")  # 스크롤바 배치
        self.chat_canvas.configure(yscrollcommand=self.chat_scroll.set)  # 스크롤 연동

        # 캔버스 안에 실제 말풍선을 담을 내부 프레임 생성(윈도우 아이템 사용)
        self.bubble_frame = ttk.Frame(self.chat_canvas)  # 말풍선들이 들어갈 프레임
        self.bubble_window = self.chat_canvas.create_window((0, 0), window=self.bubble_frame, anchor="nw")  # 좌상단 고정

        # 크기 변경/스크롤버그 방지를 위한 바인딩 — 프레임/캔버스 크기 동기화
        self.bubble_frame.bind("<Configure>", lambda e: self._on_bubble_frame_configure())  # 프레임 크기→스크롤영역 갱신
        self.chat_canvas.bind("<Configure>", lambda e: self._on_chat_canvas_configure())    # 캔버스 크기→프레임 폭 맞춤

        # 마우스 휠로 스크롤(Windows/Mac/Linux 간 이벤트 상이 → 공용 처리)
        self.chat_canvas.bind_all("<MouseWheel>", self._on_mousewheel)  # Windows/일부
        self.chat_canvas.bind_all("<Button-4>",  self._on_mousewheel)   # Linux up
        self.chat_canvas.bind_all("<Button-5>",  self._on_mousewheel)   # Linux down

        # 초기 안내 말풍선 출력(사용법)
        self._append_chat_preamble_bubble()  # 안내 버블

        # ── 하단: 멀티라인 입력 + 전송/초기화 ──
        row3 = ttk.Frame(root)  # 하단 입력 행
        row3.pack(fill="x")  # 배치

        # 멀티라인 입력(Text): Shift+Enter=줄바꿈, Enter=전송
        self.txt_input = tk.Text(row3, height=3, wrap="word")  # 멀티라인 입력 박스
        self.txt_input.pack(side="left", fill="x", expand=True, padx=(0, 6))  # 확장
        self.txt_input.bind("<Return>", self._on_input_return)         # Enter→전송
        self.txt_input.bind("<Shift-Return>", lambda e: None)          # Shift+Enter→기본 동작(줄바꿈)
        self._install_placeholder(self.txt_input, "메시지를 입력하세요...")  # 플레이스홀더 설치

        # 전송/초기화 버튼
        self.btn_send = ttk.Button(row3, text="전송", command=self.send_chat, state="disabled")  # 전송(키 유효 시 활성)
        self.btn_send.pack(side="left", padx=(0, 6))
        self.btn_clear = ttk.Button(row3, text="초기화", command=self.clear_chat, state="disabled")  # 대화 초기화
        self.btn_clear.pack(side="left")

        # 상태 표시 라벨(진행중/대기) + 타이핑 애니메이션 점(...)
        self.var_chat_status = tk.StringVar(value="상태: 대기중")  # 상태 텍스트
        self.lbl_chat_status = ttk.Label(root, textvariable=self.var_chat_status, foreground="#666")  # 상태 라벨
        self.lbl_chat_status.pack(anchor="w", pady=(6, 0))  # 배치

    # ─────────────────────────────────────────────────────────
    # 공통 동작: 선택/리스트 갱신/저장                           # 공통 헬퍼
    # ─────────────────────────────────────────────────────────
    def _selected_indices(self) -> tuple[int, ...] | None:
        """리스트박스에서 사용자가 선택한 항목 인덱스 튜플을 반환(없으면 경고 후 None)."""
        sel = self.listbox.curselection()  # 선택 인덱스들
        if not sel:
            messagebox.showwarning("확인", "항목을 선택하세요.", parent=self)
            return None
        return sel

    def refresh_list(self) -> None:
        """현재 self.todos를 리스트박스에 반영하고, 리포트도 함께 갱신."""
        self.listbox.delete(0, tk.END)  # 기존 삭제
        if self.todos:
            self.listbox.insert(tk.END, *[t.display() for t in self.todos])  # 1줄 요약 문자열 삽입
        self.refresh_report()  # 리포트 갱신

    def _save(self) -> None:
        """현재 메모리 리스트(self.todos)를 DB에 저장(덮어쓰기 방식)."""
        save_all(self.todos)  # 덮어쓰기 저장

    # ─────────────────────────────────────────────────────────
    # 사용자 액션: 추가/편집/삭제/상태전환/상세보기               # CRUD/토글/뷰
    # ─────────────────────────────────────────────────────────
    def add_todo(self) -> None:
        """새 할 일을 추가(빠른입력칸 내용으로 제목 prefill)."""
        prefill = self.quick_entry.get().strip()  # prefill 추출
        dlg = TodoDialog(self, "할 일 추가", prefill=prefill)  # 추가 팝업
        self.wait_window(dlg)  # 모달 대기
        if dlg.result:         # 저장됨
            self.todos.append(dlg.result)  # 리스트 추가
            self._save()                   # 저장
            self.refresh_list()            # UI 갱신

    def edit_selected(self) -> None:
        """선택한 첫 항목을 편집 팝업으로 열고 저장 시 교체."""
        sel = self._selected_indices()  # 선택 확인
        if not sel:
            return
        idx = sel[0]  # 첫 선택
        dlg = TodoDialog(self, "할 일 편집", item=self.todos[idx])  # 편집 모달
        self.wait_window(dlg)  # 대기
        if dlg.result:  # 저장됨
            self.todos[idx] = dlg.result  # 교체
            self._save()                  # 저장
            self.refresh_list()           # 갱신

    def delete_selected(self) -> None:
        """선택된 여러 항목을 삭제(뒤에서부터 지워 인덱스 당김 문제 방지)."""
        sel = self._selected_indices()  # 선택 확인
        if not sel:
            return
        if not messagebox.askyesno("삭제 확인", f"선택한 {len(sel)}개 항목을 정말 삭제할까요?", parent=self):
            return
        for i in reversed(sel):  # 뒤에서부터 삭제
            del self.todos[i]
        self._save()       # 저장
        self.refresh_list()  # 갱신

    def cycle_status_selected(self) -> None:
        """선택된 모든 항목의 상태를 0→1→2→0 순환."""
        sel = self._selected_indices()
        if not sel:
            return
        for i in sel:
            self.todos[i].cycle()
        self._save()
        self.refresh_list()

    def _on_space_toggle(self, _e) -> str:
        """스페이스바로 상태 순환(리스트박스 기본 스페이스 동작은 차단)."""
        self.cycle_status_selected()  # 상태 전환
        return "break"  # 기본 동작 차단

    def show_details(self, _e=None) -> None:
        """선택된 첫 항목의 상세 정보(읽기 전용) 팝업을 표시."""
        sel = self._selected_indices()
        if not sel:
            return
        t = self.todos[sel[0]]  # 대상
        icon = STATUS_ICON.get(t.status, "☐")  # 상태 아이콘
        msg = (
            f"제목: {t.title}\n"
            f"기간: {t.start} ~ {t.end}\n"
            f"상태: {icon} {STATUS_TEXT.get(t.status,'')}\n\n"
            f"상세설명:\n{t.desc or '(없음)'}"
        )  # 상세 메시지
        messagebox.showinfo("할 일 상세", msg, parent=self)  # 정보 팝업

    # ─────────────────────────────────────────────────────────
    # 타이머 로직(모노토닉 기반, 드리프트 최소화)                 # 타이머 엔진
    # ─────────────────────────────────────────────────────────
    def _format_sec(self, s: int) -> str:
        """정수 초를 'MM:SS' 형식 문자열로 변환(음수 방지/0 패딩 포함)."""
        s = max(0, int(s))  # 음수 방지 및 정수화
        m, ss = divmod(s, 60)  # 분/초 분리
        return f"{m:02d}:{ss:02d}"  # 2자리 0패딩

    def _set_timer_controls_running(self, running: bool) -> None:
        """타이머 실행 여부에 따라 버튼/입력 상태를 전환(오조작 방지)."""
        if running:
            self.btn_start.config(state="disabled")  # 시작 비활성
            self.btn_pause.config(state="normal", text="일시정지")  # 일시정지 활성
            self.btn_reset.config(state="normal")  # 초기화 활성
            self.ent_minutes.config(state="disabled")  # 분 입력 잠금
            self.ent_warn.config(state="disabled")  # 경고 입력 잠금
        else:
            self.btn_start.config(state="normal")  # 시작 활성
            self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 비활성
            self.btn_reset.config(state="disabled")  # 초기화 비활성
            self.ent_minutes.config(state="normal")  # 분 입력 허용
            self.ent_warn.config(state="normal")  # 경고 입력 허용

    def _stop_tick_loop(self) -> None:
        """예약된 타이머 틱(after) 루프를 안전하게 취소."""
        if self._timer_after_id is not None:
            try:
                self.after_cancel(self._timer_after_id)  # 예약 취소
            except Exception:
                pass  # 이미 만료된 경우 무시
            self._timer_after_id = None  # 상태 클리어

    def _stop_blink(self) -> None:
        """타임업 깜박임 루프를 중지하고 글자색을 원래대로 복원."""
        if self._blink_after_id is not None:
            try:
                self.after_cancel(self._blink_after_id)  # 예약 취소
            except Exception:
                pass
            self._blink_after_id = None
        self._blink_on = False  # 토글 리셋
        self.lbl_timer.config(fg="black")  # 글자색 복원

    def _start_blink(self) -> None:
        """타임업 시 빨강/검정을 교대로 깜박이며 종료를 강하게 알림."""
        self._blink_on = not self._blink_on  # 토글
        self.lbl_timer.config(fg=("red" if self._blink_on else "black"))  # 색상 토글
        self._blink_after_id = self.after(450, self._start_blink)  # 0.45초 간격

    def start_timer(self) -> None:
        """입력값 검증 후 타이머를 시작하고 주기 틱 루프를 가동."""
        self._stop_tick_loop()  # 기존 루프 중단
        self._stop_blink()  # 깜박 중단
        try:
            minutes = float(self.ent_minutes.get().strip())  # 분 입력 파싱
        except Exception:
            messagebox.showerror("입력 오류", "발표 시간(분)을 숫자로 입력하세요. 예: 5 또는 7.5", parent=self)
            self.ent_minutes.focus_set()
            return
        if minutes <= 0:
            messagebox.showerror("입력 오류", "발표 시간(분)은 0보다 커야 합니다.", parent=self)
            self.ent_minutes.focus_set()
            return
        try:
            warn = int(self.ent_warn.get().strip())  # 임계 파싱
        except Exception:
            messagebox.showerror("입력 오류", "경고 임계(초)를 정수로 입력하세요. 예: 30", parent=self)
            self.ent_warn.focus_set()
            return
        if warn < 1:
            messagebox.showerror("입력 오류", "경고 임계(초)는 1초 이상이어야 합니다.", parent=self)
            self.ent_warn.focus_set()
            return

        total_sec = int(round(minutes * 60))  # 총 초
        self.timer_total_sec = total_sec  # 저장
        self.timer_warn_sec  = min(warn, max(1, total_sec - 1))  # 총시간 이상 방지
        self.timer_running   = True  # 실행 상태
        self.timer_end_mono  = time.monotonic() + self.timer_total_sec  # 목표 시각
        self.timer_remain_sec = self.timer_total_sec  # 남은 시간 초기화

        self.lbl_timer.config(text=self._format_sec(self.timer_remain_sec), fg="black")  # 라벨 초기화
        self.pb_timer.config(maximum=self.timer_total_sec, value=0)  # 진행 바 초기화
        self._set_timer_controls_running(True)  # 컨트롤 전환

        self._tick_update()  # 틱 루프 시작

    def pause_resume_timer(self) -> None:
        """일시정지/계속 토글 — 남은 시간을 저장/복구하여 정확도 유지."""
        if not self.timer_running:
            if self.timer_remain_sec <= 0:  # 이미 완료면 무시
                return
            self.timer_end_mono = time.monotonic() + self.timer_remain_sec  # 목표 재설정
            self.timer_running = True  # 재개
            self.btn_pause.config(text="일시정지")  # 라벨 변경
            self._tick_update()  # 루프 재가동
            return
        now_mono = time.monotonic()  # 현재 시각
        remain = max(0, int(math.ceil(self.timer_end_mono - now_mono)))  # 남은 초
        self.timer_remain_sec = remain  # 상태 반영
        self.timer_running = False  # 정지
        self.btn_pause.config(text="계속")  # 라벨 변경
        self._stop_tick_loop()  # 루프 중지

    def reset_timer(self) -> None:
        """타이머를 완전히 초기 상태로 되돌림(루프/깜박임 포함)."""
        self.timer_running = False  # 정지
        self.timer_total_sec = 0  # 총 시간 리셋
        self.timer_remain_sec = 0  # 남은 시간 리셋
        self.timer_end_mono = 0.0  # 목표 시각 리셋
        self._stop_tick_loop()  # 루프 중지
        self._stop_blink()  # 깜박 중지
        self.lbl_timer.config(text="00:00", fg="black")  # 라벨 리셋
        self.pb_timer.config(maximum=1, value=0)  # 바 리셋
        self._set_timer_controls_running(False)  # 컨트롤 비활성화

    def _on_time_up(self) -> None:
        """남은 시간이 0이 되었을 때 타임업 처리(소리+색+깜박으로 강한 신호)."""
        self.timer_running = False  # 정지
        self._stop_tick_loop()  # 루프 중지
        self.lbl_timer.config(text="00:00", fg="red")  # 빨간색 0초
        self.pb_timer.config(value=self.timer_total_sec)  # 진행 바 끝까지
        try:
            self.bell()  # 시스템 벨
        except Exception:
            pass
        self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 버튼 비활성화
        self._start_blink()  # 깜박임 시작

    def _tick_update(self) -> None:
        """200ms 간격으로 남은 시간을 갱신하고, 경고/진행률/종료를 처리."""
        if not self.timer_running:
            return
        now_mono = time.monotonic()  # 현재 시각
        remain = int(max(0, math.ceil(self.timer_end_mono - now_mono)))  # 남은 초(올림)
        self.timer_remain_sec = remain  # 상태 반영
        self.lbl_timer.config(text=self._format_sec(remain))  # 라벨 갱신
        if remain == 0:
            self._on_time_up()  # 타임업
            return
        elif remain <= self.timer_warn_sec:
            self.lbl_timer.config(fg="orange")  # 경고색
        else:
            self.lbl_timer.config(fg="black")  # 정상색
        done = self.timer_total_sec - remain  # 경과 초
        self.pb_timer.config(value=done)  # 진행 바 갱신
        self._timer_after_id = self.after(200, self._tick_update)  # 다음 틱 예약

    # ─────────────────────────────────────────────────────────
    # 리포트 로직(집계/시각화/오토루프/컨페티)                    # 대시보드 엔진
    # ─────────────────────────────────────────────────────────
    def _stop_report_loop(self) -> None:
        """리포트 자동 갱신(after) 예약이 있으면 취소하여 중복 루프를 방지."""
        if self._report_after_id:
            try:
                self.after_cancel(self._report_after_id)
            except Exception:
                pass
            self._report_after_id = None

    def calc_report_stats(self) -> dict:
        """self.todos를 집계해 리포트용 요약 지표를 계산."""
        total = len(self.todos)  # 총 개수
        if total == 0:  # 비어있을 때
            return {"rate": 0.0, "avg_days": 0.0, "soon": 0, "overdue": 0,
                    "counts": (0, 0, 0), "week_bins": [0]*7}  # 기본 구조
        cnt0 = sum(1 for t in self.todos if t.status == 0)  # 미완
        cnt1 = sum(1 for t in self.todos if t.status == 1)  # 진행
        cnt2 = sum(1 for t in self.todos if t.status == 2)  # 완료
        rate = round(cnt2 / total * 100, 1)  # 완료율 %

        today = date.today()  # 오늘
        start_week = today - timedelta(days=today.weekday())  # 이번 주 월요일
        soon = 0       # 3일 이내 마감
        overdue = 0    # 마감 초과
        durations: list[int] = []  # 기간 리스트
        week_bins = [0]*7          # 월(0)~일(6)

        for t in self.todos:
            try:
                d1 = parse_date(t.start).date()  # 시작일
                d2 = parse_date(t.end).date()    # 종료일
            except Exception:
                continue  # 잘못된 날짜는 스킵
            if d2 >= d1:
                durations.append((d2 - d1).days)  # 기간 추가
            delta = (d2 - today).days  # 잔여 일수
            if t.status != 2 and 0 <= delta <= 3:
                soon += 1  # 임박++
            if t.status != 2 and delta < 0:
                overdue += 1  # 지남++
            off = (d2 - start_week).days  # 이번주 offset
            if 0 <= off < 7:
                week_bins[off] += 1  # 해당 요일++

        avg_days = round(sum(durations)/len(durations), 1) if durations else 0.0  # 평균 기간
        return {"rate": rate, "avg_days": avg_days, "soon": soon, "overdue": overdue,
                "counts": (cnt0, cnt1, cnt2), "week_bins": week_bins}  # 결과

    def refresh_report(self) -> None:
        """리포트 텍스트/KPI와 시각화를 갱신하고, 5초 후 다시 자신을 예약."""
        self._stop_report_loop()  # 중복 루프 방지
        s = self.calc_report_stats()  # 집계

        self.lbl_rate.config(text=f"완료율 {s['rate']:.1f}%")  # 완료율
        self.var_avg.set (f"평균 기간: {s['avg_days']}일")     # 평균 기간
        self.var_soon.set(f"마감 임박: {s['soon']}건")         # 임박
        self.var_over.set(f"지남: {s['overdue']}건")          # 지남
        c0, c1, c2 = s["counts"]  # 상태 구성
        self.var_counts.set(f"상태 구성: 미완 {c0} · 진행 {c1} · 완료 {c2}")  # 상태 구성 문자열

        col = self._rate_color(s["rate"])  # 색상 결정
        self.lbl_rate.config(foreground=col)  # 레이블 색

        self._animate_ring_to(s["rate"])   # 도넛 애니메이션
        self._draw_stack(s["counts"])      # 스택바
        self._draw_heat(s["week_bins"])    # 히트맵

        prev = self._last_rate  # 이전 완료율
        if self._report_booted and any(prev < m <= s['rate'] for m in (50, 80, 100)):  # 마일스톤 돌파
            self._burst_confetti(duration=800)  # 컨페티
        self._report_booted = True  # 첫 갱신 이후
        self._last_rate = s["rate"]  # 현재 저장

        self._report_after_id = self.after(5000, self.refresh_report)  # 5초 후 자동 갱신

    # ─────────────────────────────────────────────────────────
    # 색상/도넛/스택바/히트맵/컨페티 드로잉 유틸                 # 시각화 유틸
    # ─────────────────────────────────────────────────────────
    def _rate_color(self, rate: float) -> str:
        """완료율(%)에 따른 시그널 색을 반환: <50 빨강, <80 주황, 그 외 초록."""
        return "#e53935" if rate < 50 else "#fb8c00" if rate < 80 else "#43a047"  # 삼항

    def _draw_ring(self, rate: float) -> None:
        """완료율(0~100)을 도넛 형태로 그린다(베이스 링+진행 아크+중앙 퍼센트)."""
        c = self.cnv_ring  # 캔버스
        c.delete("all")  # 초기화
        cx, cy, r, th = 80, 80, 70, 14  # 중심/반지름/두께
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#e6e6e6", width=th)  # 바탕 링
        col = self._rate_color(rate)  # 진행 색
        extent = 360 * (rate / 100)  # 각도
        c.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-extent,
                     style="arc", width=th, outline=col)  # 진행 아크
        c.create_text(cx, cy, text=f"{rate:.1f}%", font=("Helvetica", 16, "bold"))  # 퍼센트 텍스트

    def _animate_ring_to(self, target: float) -> None:
        """완료율 변화량에 따라 도넛을 부드럽게 보간 렌더(아주 작으면 즉시 반영)."""
        start = getattr(self, "_ring_anim_start", self._last_rate)  # 시작값
        if abs(target - start) < 0.2:  # 미세 변화는 즉시
            self._draw_ring(target)
            self._ring_anim_start = target
            return
        steps = max(8, int(abs(target - start) // 2))  # 변화폭 비례 스텝수
        def step(i=0):
            val = start + (target - start) * i / steps  # 선형 보간
            self._draw_ring(val)
            if i < steps:
                self.after(16, step, i + 1)  # 60fps 근사
            else:
                self._ring_anim_start = target  # 종료 상태 저장
        step()  # 시작

    def _draw_stack(self, counts: tuple[int, int, int]) -> None:
        """상태 구성(미완/진행/완료)을 가로 스택바로 시각화."""
        c = self.cnv_stack  # 캔버스
        c.delete("all")  # 초기화
        w = c.winfo_width() or 400  # 폭(초기 보정)
        h = 22  # 높이
        total = max(1, sum(counts))  # 0 분모 방지
        colors = ["#90a4ae", "#fb8c00", "#43a047"]  # 미완/진행/완료 색
        x = 0  # 누적 X
        for n, col in zip(counts, colors):
            seg = int(w * n / total)  # 구간 길이
            c.create_rectangle(x, 0, x + seg, h, fill=col, width=0)  # 구간 박스
            x += seg  # 다음 시작점
        c.create_rectangle(0, 0, w, h, outline="#d0d0d0")  # 외곽선

    def _draw_heat(self, bins: list[int]) -> None:
        """이번 주(월~일) 마감 건수를 연녹→진녹 그라데이션으로 히트맵 표시."""
        c = self.cnv_heat  # 캔버스
        c.delete("all")  # 초기화
        w = c.winfo_width() or 420  # 폭
        h = 56  # 높이
        cell = w // 7  # 칸 폭
        pad = 4  # 내부 패딩
        days = ["월", "화", "수", "목", "금", "토", "일"]  # 요일
        mx = max(bins) or 1  # 최대값(0 방지)
        def blend(a: str, b: str, t: float) -> str:
            """hex 색상 a→b 사이를 t(0~1)로 보간하여 hex로 반환."""
            ah, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
            bh, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
            ih, ig, ib = int(ah + (bh - ah) * t), int(ag + (bg - ag) * t), int(ab + (bb - ab) * t)
            return f"#{ih:02x}{ig:02x}{ib:02x}"
        for i, v in enumerate(bins):
            x0, x1 = i * cell + pad, (i + 1) * cell - pad
            y0, y1 = pad, h - 18
            col = blend("#e8f5e9", "#1b5e20", v / mx)  # 연녹→진녹
            c.create_rectangle(x0, y0, x1, y1, fill=col, outline="#cfd8dc")  # 칸
            c.create_text((x0 + x1) // 2, h - 8, text=days[i], font=("Helvetica", 9))  # 요일 라벨

    def _burst_confetti(self, n: int = 28, duration: int = 800) -> None:
        """도넛 캔버스 위에서만 0.8초간 컨페티를 떨어뜨려 시각적 보상을 제공."""
        c = self.cnv_ring  # 캔버스
        import time as _t  # 지역 임포트
        W = c.winfo_width() or 160  # 폭
        parts = []  # 파편 ID 리스트
        pal = ["#43a047", "#1e88e5", "#fdd835", "#e53935", "#8e24aa"]  # 팔레트
        for _ in range(n):
            x = random.randint(0, max(8, W - 8))  # 시작 X
            y = -random.randint(0, 40)  # 시작 Y(상단 바깥)
            s = random.randint(4, 8)  # 지름
            col = random.choice(pal)  # 색
            parts.append(c.create_oval(x, y, x + s, y + s, fill=col, width=0))  # 원 파편
        t0 = _t.monotonic()  # 시작 시각
        def tick():
            dt = (_t.monotonic() - t0) * 1000.0  # 경과(ms)
            for p in parts:
                c.move(p, 0, 6)  # 아래로 낙하
            if dt < duration:
                c.after(16, tick)  # 60fps 근사
            else:
                for p in parts:
                    c.delete(p)  # 삭제
        tick()  # 시작

    # ─────────────────────────────────────────────────────────
    # ChatGPT 탭: 새 UI 동작 메서드(말풍선/모델/입력)              # 핵심 개선 포인트
    # ─────────────────────────────────────────────────────────
    def _toggle_key_visibility(self) -> None:
        """'표시' 체크박스 상태에 따라 API 키 입력란의 마스킹을 토글한다."""
        self.ent_api_key.config(show="" if self.var_show_key.get() else "*")  # 체크되면 평문, 아니면 *

    def validate_api_key(self) -> None:
        """입력된 OpenAI API 키를 백그라운드에서 검증한다."""
        key = self.ent_api_key.get().strip()  # 입력 키
        if not key:
            messagebox.showwarning("확인", "API 키를 입력하세요.", parent=self)
            self.ent_api_key.focus_set()
            return
        self.btn_key_check.config(state="disabled")  # 중복 클릭 방지
        self.lbl_key_status.config(text="⏳ 키 검증중...", foreground="#fb8c00")  # 상태
        self.var_chat_status.set("상태: 키 검증중...")  # 상태 라벨

        def worker():
            hdr = {"Authorization": f"Bearer {key}"}  # 인증 헤더
            code, text = _http_get(OPENAI_URL_MODELS, headers=hdr, timeout=15)  # 모델 목록 GET
            self.after(0, self._on_key_validation_result, key, code, text)  # 결과 처리 예약

        self._key_thread = threading.Thread(target=worker, daemon=True)  # 데몬 스레드
        self._key_thread.start()  # 시작

    def _on_key_validation_result(self, key: str, code: int, text: str) -> None:
        """/v1/models 응답 코드에 따라 키 유효성을 갱신하고 UI를 정리."""
        self.btn_key_check.config(state="normal")  # 검증 버튼 복원
        if code == 200:  # 성공
            self._api_key = key  # 키 저장(메모리)
            self.api_key_valid = True  # 유효
            self.lbl_key_status.config(text="🔓 키 유효", foreground="#43a047")  # 초록
            self.var_chat_status.set("상태: 준비 완료(키 유효)")  # 상태
            self.btn_send.config(state="normal")  # 전송 활성
            self.btn_clear.config(state="normal")  # 초기화 활성
            if not self.chat_messages:  # 최초 시스템 메시지
                self.chat_messages = [{"role": "system", "content": "당신은 친절한 한국어 비서입니다. 사용자 질문에 간결하고 정확하게 답하세요."}]
            self.txt_input.focus_set()  # 입력 포커스
            # 키 유효 시 한 번 모델 목록 자동 새로고침 시도(실패해도 조용히 무시)
            self._refresh_model_list(silent=True)  # 자동 새로고침
        elif code == 401:  # 인증 실패
            self.api_key_valid = False
            self.lbl_key_status.config(text="🔒 키 무효(401)", foreground="#e53935")
            self.var_chat_status.set("상태: 키 무효(401 Unauthorized)")
            messagebox.showerror("검증 실패", "API 키가 올바르지 않습니다(401). 다시 확인하세요.", parent=self)
            self.btn_send.config(state="disabled")
            self.btn_clear.config(state="disabled")
        elif code == 429:  # 한도/속도 제한
            # 429는 유효한 키일 가능성이 높으므로 '유효'로 처리하되 경고
            self._api_key = key
            self.api_key_valid = True
            self.lbl_key_status.config(text="🔓 키 유효(제한 429)", foreground="#fb8c00")
            self.var_chat_status.set("상태: 키 유효(하지만 한도/속도 제한 429)")
            self.btn_send.config(state="normal")
            self.btn_clear.config(state="normal")
            messagebox.showwarning("주의", "키는 유효하지만 현재 한도/속도 제한 상태(429)입니다.", parent=self)
            # 제한 중에도 모델 목록 조회가 아예 불가할 수 있으니 자동 새로고침은 생략
        elif code == 0:  # 로컬 예외(오프라인 등)
            self.api_key_valid = False
            self.lbl_key_status.config(text="⚠️ 네트워크 오류", foreground="#e53935")
            self.var_chat_status.set(f"상태: 네트워크 오류 - {text}")
            messagebox.showerror("네트워크 오류", f"요청 실패: {text}", parent=self)
        else:  # 그 외 상태코드
            self.api_key_valid = False
            self.lbl_key_status.config(text=f"⚠️ 검증 실패({code})", foreground="#e53935")
            self.var_chat_status.set(f"상태: 검증 실패({code})")
            try:
                err = json.loads(text).get("error", {}).get("message", text)  # 에러 메시지 추출
            except Exception:
                err = text
            messagebox.showerror("검증 실패", f"응답 코드: {code}\n{err}", parent=self)

    def _refresh_model_list(self, silent: bool = False) -> None:
        """/v1/models에서 접근 가능한 모델 목록을 읽어 콤보박스를 최신화(키 필요)."""
        if not self.api_key_valid or not self._api_key:  # 키 없음/무효
            if not silent:
                messagebox.showwarning("확인", "먼저 API 키를 검증하세요.", parent=self)
            return
        self.btn_model_refresh.config(state="disabled")  # 버튼 잠금
        prev_status = self.var_chat_status.get()  # 기존 상태 저장
        self.var_chat_status.set("상태: 모델 목록 새로고침 중...")  # 상태 표시

        def worker():
            try:
                code, text = _http_get(OPENAI_URL_MODELS, headers={"Authorization": f"Bearer {self._api_key}"}, timeout=20)
            except Exception as e:
                code, text = 0, f"{e}"
            self.after(0, self._on_model_refresh_result, code, text, silent, prev_status)

        threading.Thread(target=worker, daemon=True).start()  # 백그라운드 실행

    def _on_model_refresh_result(self, code: int, text: str, silent: bool, prev_status: str) -> None:
        """모델 목록 새로고침 결과 처리: 성공 시 콤보박스 갱신, 실패 시 기존 유지."""
        self.btn_model_refresh.config(state="normal")  # 버튼 복원
        if code == 200:
            try:
                data = json.loads(text)  # JSON 파싱
                items = data.get("data", [])  # 모델 리스트
                # 모델 ID만 추출, 문자열 정렬(가독성), 중복 제거
                ids = sorted({it.get("id", "") for it in items if isinstance(it, dict) and it.get("id")})
                # 너무 긴 목록이면 채팅 관련 대표 키워드가 포함된 것만 간단 필터(느슨)
                prefer = [m for m in ids if any(k in m for k in ("gpt", "o3", "o1"))] or ids
                # 빈 배열 방지: 최소한 DEFAULT_MODEL_CANDIDATES는 포함
                merged = list(dict.fromkeys(prefer + DEFAULT_MODEL_CANDIDATES))  # 순서 보존 중복 제거
                self._model_options = merged  # 내부 목록 저장
                self.cmb_model.config(values=self._model_options)  # 콤보박스 갱신
                # 현재 선택이 목록에 없으면 기본값으로 리셋
                if self.cmb_model.get() not in self._model_options:
                    self.cmb_model.set(CHAT_MODEL_DEFAULT)
                # 상태 업데이트
                self.var_chat_status.set(f"상태: 모델 {len(self._model_options)}개 로드 완료")
                if not silent:
                    messagebox.showinfo("완료", f"모델 목록을 새로고침했습니다. ({len(self._model_options)}개)", parent=self)
            except Exception:
                # 파싱 실패 시 조용히 복구
                self.var_chat_status.set("상태: 모델 목록 파싱 실패(서버 응답 형식 변경)")
                if not silent:
                    messagebox.showwarning("주의", "모델 목록 파싱에 실패했습니다.", parent=self)
        else:
            # 실패: 상태 복구, 사용자 알림(사일런트가 아니면)
            self.var_chat_status.set(prev_status)
            if not silent:
                try:
                    err = json.loads(text).get("error", {}).get("message", text)
                except Exception:
                    err = text
                messagebox.showerror("실패", f"모델 목록 새로고침 실패 ({code})\n{err}", parent=self)

    def _append_chat_preamble_bubble(self) -> None:
        """대화 영역에 초기 안내 말풍선을 1회 출력."""
        guide = (
            "💬 ChatGPT 탭 사용법\n"
            "1) 상단에 OpenAI API 키를 입력 후 [검증]을 누르세요.\n"
            "2) '🔓 키 유효'가 뜨면 메시지를 입력하고 Enter로 전송하세요.\n"
            "   (Shift+Enter: 줄바꿈)\n"
            "3) 우측 상단 [모델 새로고침]으로 사용 가능한 모델 목록을 불러올 수 있습니다."
        )  # 안내 텍스트
        self._add_chat_bubble(role="assistant", text=guide)  # 어시스턴트 말풍선으로 안내 표시

    def _install_placeholder(self, widget: tk.Text, placeholder: str) -> None:
        """멀티라인 입력 Text 위젯에 플레이스홀더를 구현."""
        # 내부 상태를 위젯에 속성으로 보관(간단 처리)
        widget._placeholder_text = placeholder  # 플레이스홀더 텍스트 저장
        widget._placeholder_active = True       # 현재 플레이스홀더 표시 여부
        widget.insert("1.0", placeholder)       # 초기 삽입
        widget.config(fg="#999")                # 연한 회색
        # 포커스 인: 플레이스홀더면 지우기
        def on_focus_in(_e):
            if getattr(widget, "_placeholder_active", False):
                widget.delete("1.0", "end")
                widget.config(fg="black")
                widget._placeholder_active = False
        # 포커스 아웃: 비어있으면 플레이스홀더 복구
        def on_focus_out(_e):
            if widget.get("1.0", "end").strip() == "":
                widget._placeholder_active = True
                widget.delete("1.0", "end")
                widget.insert("1.0", placeholder)
                widget.config(fg="#999")
        widget.bind("<FocusIn>", on_focus_in)
        widget.bind("<FocusOut>", on_focus_out)

    def _on_input_return(self, e) -> str:
        """입력창에서 Enter를 누르면 전송, Shift+Enter는 줄바꿈."""
        # Shift가 눌려있으면 기본 동작(줄바꿈)을 허용
        if (e.state & 0x0001) != 0:  # Shift bit (플랫폼별 차이가 있어도 보통 0x1)
            return  # None 반환 → 기본 동작
        # 그 외 Enter는 전송
        self.send_chat()  # 전송
        return "break"  # 기본 줄바꿈 방지

    def _on_bubble_frame_configure(self) -> None:
        """말풍선 프레임 크기가 바뀔 때 캔버스 스크롤영역을 갱신하고 하단으로 스크롤."""
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))  # 스크롤 영역 갱신
        self._scroll_to_end()  # 항상 최신 메시지로 스크롤

    def _on_chat_canvas_configure(self) -> None:
        """캔버스 크기가 바뀌면 내부 프레임의 폭을 캔버스 폭에 맞춘다."""
        try:
            self.chat_canvas.itemconfig(self.bubble_window, width=self.chat_canvas.winfo_width())  # 폭 동기화
        except Exception:
            pass

    def _on_mousewheel(self, event) -> None:
        """운영체제별 마우스 휠 이벤트를 처리해 스크롤."""
        # Windows/Mac(Delta), Linux(Button-4/5) 케이스를 모두 지원
        if event.num == 4:  # Linux up
            self.chat_canvas.yview_scroll(-3, "units")
        elif event.num == 5:  # Linux down
            self.chat_canvas.yview_scroll(3, "units")
        else:  # Windows/Mac
            delta = -1 if event.delta > 0 else 1  # 위/아래 방향
            self.chat_canvas.yview_scroll(delta * 3, "units")

    def _scroll_to_end(self) -> None:
        """대화 영역을 하단(최신 메시지)으로 스크롤."""
        self.chat_canvas.update_idletasks()  # 레이아웃 반영
        self.chat_canvas.yview_moveto(1.0)   # 맨 아래로 이동

    def _add_chat_bubble(self, role: str, text: str) -> None:
        """말풍선 형태로 메시지를 추가하고 자동 스크롤."""
        # 말풍선 전체 행 컨테이너(좌우 정렬을 위해 컬럼 2개 레이아웃 사용)
        row = ttk.Frame(self.bubble_frame)  # 한 줄 컨테이너
        row.pack(fill="x", anchor="w", pady=4)  # 위아래 여백

        # 말풍선 스타일 결정: role=user면 오른쪽 정렬+파랑톤, assistant면 왼쪽 정렬+연녹톤
        is_user = (role == "user")  # 사용자 여부
        # 아바타(이모지) 라벨
        avatar = "👤" if is_user else "🤖"  # 아이콘
        ico = ttk.Label(row, text=avatar)  # 아바타 라벨
        if is_user:
            ico.pack(side="right", padx=(6, 0))  # 사용자: 오른쪽
        else:
            ico.pack(side="left", padx=(0, 6))   # 어시스턴트: 왼쪽

        # 말풍선 본체(캔버스 대신 프레임+라벨로 단순 구현)
        bubble_bg = "#e3f2fd" if is_user else "#f1f8e9"  # 배경색(연파랑/연녹)
        bubble_fg = "#0d47a1" if is_user else "#1b5e20"  # 글자색(딥블루/딥그린)
        bubble_wrap = max(280, min(480, self.chat_canvas.winfo_width() - 120))  # 말풍선 최대 폭(창 크기에 따라)
        bubble = tk.Frame(row, bg=bubble_bg, bd=0, highlightthickness=0)  # 말풍선 컨테이너
        # 정렬: 사용자=오른쪽, 어시스턴트=왼쪽
        if is_user:
            bubble.pack(side="right", padx=(6, 2))  # 오른쪽 정렬
        else:
            bubble.pack(side="left", padx=(2, 6))   # 왼쪽 정렬

        # 텍스트 라벨(말풍선 내부) — wraplength로 자동 줄바꿈
        lbl = tk.Label(bubble, text=text, bg=bubble_bg, fg="black", justify="left",
                       wraplength=bubble_wrap, anchor="w")  # 본문 라벨
        lbl.pack(padx=10, pady=8)  # 내부 패딩

        # 하단 메타(시각/복사 버튼 등)
        meta = tk.Frame(bubble, bg=bubble_bg)  # 메타 정보 컨테이너
        meta.pack(fill="x", padx=8, pady=(0, 6))  # 배치
        tm = datetime.now().strftime("%H:%M:%S")  # 시각
        tk.Label(meta, text=tm, bg=bubble_bg, fg=bubble_fg).pack(side="left")  # 시각 라벨
        if not is_user:
            # 어시스턴트 말풍선에는 '복사' 버튼 제공
            def copy_to_clipboard(txt=text):
                try:
                    self.clipboard_clear()
                    self.clipboard_append(txt)
                    self.var_chat_status.set("상태: 복사 완료")
                except Exception:
                    self.var_chat_status.set("상태: 클립보드 접근 실패")
            ttk.Button(meta, text="복사", command=copy_to_clipboard).pack(side="right")  # 복사 버튼

        # 스크롤영역 및 하단 이동 반영
        self._on_bubble_frame_configure()  # 스크롤영역 갱신 및 스크롤

    def append_chat(self, who: str, text: str) -> None:
        """대화 로그에 말풍선 1건을 추가(역호환용 래퍼: who=user/assistant)."""
        role = "user" if who == "user" else "assistant"  # 역할 정규화
        self._add_chat_bubble(role=role, text=text)  # 말풍선 추가

    def clear_chat(self) -> None:
        """대화 히스토리와 말풍선을 모두 초기화한다."""
        self.chat_messages = [{"role": "system", "content": "당신은 친절한 한국어 비서입니다. 사용자 질문에 간결하고 정확하게 답하세요."}]  # 시스템 메시지
        # 기존 말풍선 제거: bubble_frame 자식 모두 파괴
        for child in list(self.bubble_frame.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        # 안내 말풍선 재출력
        self._append_chat_preamble_bubble()
        self.var_chat_status.set("상태: 대화 초기화 완료")  # 상태 업데이트

    def _start_typing_anim(self) -> None:
        """어시스턴트 응답 대기 중 점(...) 애니메이션을 상태 라벨에 표시."""
        base = "상태: 응답 생성중"
        dots = ["", ".", "..", "..."]  # 점 상태
        idx = 0  # 인덱스 클로저 변수
        def tick():
            nonlocal idx
            self.var_chat_status.set(base + dots[idx % len(dots)])  # 상태 라벨 갱신
            idx += 1
            self._typing_anim_after_id = self.after(500, tick)  # 0.5초마다 갱신
        self._stop_typing_anim()  # 중복 방지
        tick()  # 시작

    def _stop_typing_anim(self) -> None:
        """타이핑 애니메이션을 중지하고 after 예약을 해제."""
        if self._typing_anim_after_id:
            try:
                self.after_cancel(self._typing_anim_after_id)
            except Exception:
                pass
            self._typing_anim_after_id = None

    def send_chat(self) -> None:
        """현재 입력칸의 메시지를 Chat Completions로 보내고 응답을 표시."""
        if not self.api_key_valid:
            messagebox.showwarning("확인", "먼저 API 키를 검증하세요.", parent=self)
            return
        if self._chat_busy:  # 중복 전송 방지
            return
        # 플레이스홀더가 활성 상태면 빈 메시지로 간주
        user_text = self.txt_input.get("1.0", "end").strip()
        if getattr(self.txt_input, "_placeholder_active", False):
            user_text = ""
        if not user_text:
            self.txt_input.focus_set()
            return

        # UI 선반영: 사용자 말풍선 출력 + 입력칸 비우기/잠금
        self.append_chat("user", user_text)  # 사용자 버블
        self.txt_input.delete("1.0", "end")  # 입력 삭제
        self.txt_input.config(state="disabled")  # 입력 잠금
        self.btn_send.config(state="disabled")  # 전송 잠금
        self._chat_busy = True  # 바쁜 상태
        self._start_typing_anim()  # 타이핑 애니 시작

        # 히스토리 복사본 생성(스레드 전달용)
        msgs = (self.chat_messages + [{"role": "user", "content": user_text}]).copy()  # 히스토리 + 사용자

        # 선택된 모델명 읽기(없으면 기본값)
        model_name = self.cmb_model.get().strip() or CHAT_MODEL_DEFAULT  # 콤보박스 선택
        temperature = 0.7  # 간단히 고정(필요 시 슬라이더 추가 가능)

        def worker(payload_messages: list[dict], model: str, temp: float) -> None:
            """백그라운드에서 Chat Completions 호출."""
            headers = {"Authorization": f"Bearer {self._api_key}"}  # 인증
            data = {"model": model, "messages": payload_messages, "temperature": temp}  # 요청 본문
            try:
                code, text = _http_post(OPENAI_URL_CHAT, headers=headers, data=data, timeout=60)  # POST 호출
            except Exception as e:
                code, text = 0, f"{e}"
            self.after(0, self._on_chat_result, payload_messages, code, text)  # 결과 처리 예약

        self._chat_thread = threading.Thread(target=worker, args=(msgs, model_name, temperature), daemon=True)  # 데몬 스레드
        self._chat_thread.start()  # 시작

    def _on_chat_result(self, payload_messages: list[dict], code: int, text: str) -> None:
        """Chat Completions 응답(성공/실패)을 UI와 히스토리에 반영."""
        self._stop_typing_anim()  # 타이핑 애니 정지
        try:
            if code == 200:
                data = json.loads(text)  # JSON 파싱
                choice = (data.get("choices") or [{}])[0]  # 첫 choice
                msg = (choice.get("message") or {}).get("content", "").strip()  # 어시스턴트 응답 텍스트
                if not msg:
                    raise ValueError("빈 응답을 받았습니다.")  # 강제 예외
                # 히스토리 업데이트(사용자/어시스턴트)
                self.chat_messages = payload_messages + [{"role": "assistant", "content": msg}]  # 새로운 히스토리
                self.append_chat("assistant", msg)  # 어시스턴트 말풍선 출력
                self.var_chat_status.set("상태: 완료")  # 상태 업데이트
            else:
                try:
                    err_msg = json.loads(text).get("error", {}).get("message", text)  # 에러 메시지 추출
                except Exception:
                    err_msg = text  # 파싱 실패 시 원문
                self.append_chat("assistant", f"(오류 {code}) {err_msg}")  # 오류 메시지 버블
                self.var_chat_status.set(f"상태: 오류 {code}")  # 상태 갱신
        except Exception as e:
            # 예외 발생 시 트레이스백을 로그로 출력(콘솔), UI에는 간단 안내
            print("[_on_chat_result] Exception:", e)
            traceback.print_exc()
            self.append_chat("assistant", f"(예외) {e}")  # 예외 메시지 버블
            self.var_chat_status.set("상태: 예외 발생")
        finally:
            # UI 잠금 해제/버튼 복원
            self._chat_busy = False
            self.txt_input.config(state="normal")  # 입력 복원
            if self.api_key_valid:
                self.btn_send.config(state="normal")  # 전송 활성화
                self.btn_clear.config(state="normal")  # 초기화 활성화
            self.txt_input.focus_set()  # 포커스 복원

    # ─────────────────────────────────────────────────────────
    # 종료 처리(안전 정리)                                      # 종료 시퀀스
    # ─────────────────────────────────────────────────────────
    def _on_close(self) -> None:
        """예약된 after 루프(타이머/깜박/리포트/타이핑)를 모두 취소하고 창을 닫는다."""
        # 타이머 관련 정리
        self._stop_tick_loop()   # 타이머 루프 정지
        self._stop_blink()       # 깜박임 루프 정지
        # 리포트 자동 갱신 정리
        self._stop_report_loop() # 리포트 루프 정지
        # 타이핑 애니 정리
        self._stop_typing_anim() # 타이핑 점 애니 중지
        # 백그라운드 스레드는 데몬으로 생성했기 때문에 프로세스 종료를 막지 않는다.
        self.destroy()  # 창 파괴(프로세스 종료)

# ─────────────────────────────────────────────────────────
# 실행 엔트리포인트                                           # main guard
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":  # 이 파일을 직접 실행할 때만 아래 코드 실행
    app = TodoApp()   # 최상위 앱 인스턴스 생성
    app.mainloop()    # Tk 이벤트 루프 시작(사용자 인터랙션 처리)
