# ─────────────────────────────────────────────────────────
# Tkinter: 파이썬 기본 GUI                                   # 앱의 목적/범주 설명
# ─────────────────────────────────────────────────────────
# 간단한 ToDo 관리 + 프리젠테이션 타이머 + 실시간 '성과 리포트' 대시보드를 제공하는 Tkinter 데스크톱 앱이다.  # 기능 개요
# 또한 이 버전부터는 ChatGPT 탭을 제거하고, 보이지 않는 AI 도우미가 각 탭의 데이터를 읽어 자동 추천/질문 응답을 제공한다.  # 동작 변화 설명

from dataclasses import dataclass  # dataclass 데코레이터로 생성자/표현 등 보일러플레이트 자동 생성
from datetime import date, datetime, timedelta  # 날짜(date), 날짜시간(datetime), 기간(timedelta)
from pathlib import Path  # 운영체제 무관한 경로 처리
import time  # 단조 증가 시계(time.monotonic) 사용 → 시스템 시간 변경 영향을 안 받는 타이머
import math  # 올림/내림, 보간 계산 등에 사용
import sqlite3 as sql  # 내장 SQLite DB로 간단 영속화(파일 1개)
import tkinter as tk  # Tkinter 기본 위젯
from tkinter import ttk, messagebox  # ttk(현대식 스킨), messagebox(모달 알림/확인)
import json  # OpenAI API 요청/응답의 JSON 직렬화/역직렬화에 사용
import threading  # 네트워크 호출을 백그라운드 스레드에서 실행해 UI 멈춤 방지
from urllib import request as urlrequest, error as urlerror  # 추가 의존성 없이 HTTP 호출(urllib)
import traceback  # 예외 시 디버그를 돕는 스택 출력(필요 시 로그 용도)
import random  # 컨페티/랜덤 ID 등 경미하게 사용
import os  # New 환경변수 접근을 위한 모듈(키를 환경변수로도 받기 위함)

# ─────────────────────────────────────────────────────────
# 상수/포맷/공용 패딩                                         # 상수/공용 값 묶음
# ─────────────────────────────────────────────────────────
DATE_FMT = "%Y-%m-%d"  # 날짜 문자열 형식(예: 2025-09-16) — DB/표시 포맷을 통일해 파싱오류를 줄임
STATUS_ICON = {0: "☐", 1: "⏳", 2: "✔"}  # 상태코드→아이콘 매핑(미완/진행/완료)
STATUS_TEXT = {0: "미완료", 1: "진행중", 2: "완료"}  # 상태코드→읽을 수 있는 텍스트
PAD6 = {"padx": 10, "pady": 6}  # grid/pack 공통 여백 프리셋(6)
PAD8 = {"padx": 10, "pady": 8}  # 공통 여백 프리셋(8)

OPENAI_URL_CHAT = "https://api.openai.com/v1/chat/completions"  # New AI 도우미가 사용할 Chat Completions 엔드포인트
ASSIST_MODEL_DEFAULT = "gpt-4o-mini"  # New 빠르고 저렴한 고성능 경량 모델
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "realkey")  # New 실제 키 또는 환경변수
ASSIST_TIMEOUT = 40  # New 도우미 호출 타임아웃(초)

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
    """날짜 문자열(YYYY-MM-DD)을 datetime 객체로 변환."""  # 문서화 설명
    return datetime.strptime(s, DATE_FMT)  # 형식 불일치 시 ValueError 발생 → 호출부에서 UX 메시지 처리

def center_over(parent: tk.Tk, win: tk.Toplevel) -> None:
    """부모창 기준으로 자식창을 화면 중앙에 배치(화면 밖으로 나가지 않게 보정 포함)."""  # 배치 유틸
    parent.update_idletasks()  # 부모 레이아웃/위치 정보 최신화
    win.update_idletasks()     # 자식 레이아웃/크기 정보 최신화
    px, py = parent.winfo_rootx(), parent.winfo_rooty()     # 부모 좌상단의 화면 절대좌표
    pw, ph = parent.winfo_width(), parent.winfo_height()    # 부모 폭/높이
    ww, wh = win.winfo_width(), win.winfo_height()          # 자식 폭/높이
    x = max(0, min(px + (pw - ww) // 2, win.winfo_screenwidth() - ww))  # 계산된 X 좌표 클램프
    y = max(0, min(py + (ph - wh) // 2, win.winfo_screenheight() - wh))  # 계산된 Y 좌표 클램프
    win.geometry(f"+{x}+{y}")  # 크기는 유지하고 위치만 이동

def _http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> tuple[int, str]:
    """단순 GET 요청을 보내고 (상태코드, 텍스트)를 반환한다."""  # GET 유틸
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
    """단순 POST(JSON) 요청을 보내고 (상태코드, 텍스트)를 반환한다."""  # POST 유틸
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
    """할 일 1건을 표현하는 데이터 모델."""  # 설계 개요
    title: str  # 제목
    start: str  # 시작일(YYYY-MM-DD)
    end: str    # 종료일(YYYY-MM-DD)
    desc: str = ""   # 상세 설명(옵션)
    status: int = 0  # 상태 코드(0=미완,1=진행,2=완료)

    def cycle(self) -> None:
        """상태를 다음 단계로 순환(0→1→2→0)."""  # 메서드 설명
        self.status = (self.status + 1) % 3  # 한 번 호출 시 상태가 다음으로

    def display(self, today: date | None = None) -> str:
        """리스트박스에 표시할 1줄 요약 문자열을 생성(D-DAY 태그 포함)."""  # 표시 문자열
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
    """SQLite 연결을 열어 반환(컨텍스트 매니저와 함께 사용)."""  # 커넥션 유틸
    return sql.connect(DB_PATH)  # 연결 열고 반환

def init_db() -> None:
    """앱 최초 실행 시 todos 테이블 생성(존재하면 무시)."""  # 초기 스키마 생성
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
    """DB의 모든 항목을 읽어 메모리(list[Todo])로 반환."""  # 조회 함수
    init_db()  # 테이블 존재 보장
    with _db() as con:  # 연결 컨텍스트
        rows = con.execute(
            "SELECT title, start, end, memo, status FROM todos ORDER BY id"  # 입력 순 정렬
        ).fetchall()  # 모든 행 조회
    return [Todo(title, start, end, memo, status) for (title, start, end, memo, status) in rows]  # 행→모델 변환

def save_all(items: list[Todo]) -> None:
    """현재 메모리 리스트 상태를 DB에 전량 반영(덮어쓰기 방식)."""  # 저장 함수
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
    """할 일 추가/편집을 위한 모달 대화상자."""  # 팝업 클래스

    def __init__(self, parent: tk.Tk, title: str, prefill: str = "", item: Todo | None = None):
        """부모창, 타이틀, 제목 기본값(prefill), 편집 대상(item)을 받아 팝업을 구성."""  # 생성자 설명
        super().__init__(parent)  # 부모 루트에 부착된 Toplevel 생성
        self.result: Todo | None = None              # 저장 성공 시 회수할 결과
        self._orig_status = item.status if item else 0  # 편집이면 기존 상태 유지

        self.title(title)       # 창 타이틀
        self.transient(parent)  # 부모창 위에 표시
        self.resizable(False, False)  # 크기 고정
        self.grab_set()         # 모달(닫을 때까지 다른 창 포커스 차단)

        pad = PAD6  # 공용 여백 프리셋
        today_str = date.today().isoformat()  # 오늘 날짜 문자열

        ttk.Label(self, text="제목").grid(row=0, column=0, sticky="w", **pad)  # 제목 라벨
        self.ent_title = ttk.Entry(self, width=38)  # 제목 입력
        self.ent_title.grid(row=0, column=1, sticky="w", **pad)  # 배치
        self.ent_title.insert(0, prefill or (item.title if item else ""))  # prefill 우선

        ttk.Label(self, text="시작일 (YYYY-MM-DD)").grid(row=1, column=0, sticky="w", **pad)  # 라벨
        self.ent_start = ttk.Entry(self, width=20)  # 입력
        self.ent_start.grid(row=1, column=1, sticky="w", **pad)  # 배치
        self.ent_start.insert(0, item.start if item else today_str)  # 기본: 오늘

        ttk.Label(self, text="종료일 (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", **pad)  # 라벨
        self.ent_end = ttk.Entry(self, width=20)  # 입력
        self.ent_end.grid(row=2, column=1, sticky="w", **pad)  # 배치
        self.ent_end.insert(0, item.end if item else today_str)  # 기본: 오늘

        ttk.Label(self, text="상세설명").grid(row=3, column=0, sticky="nw", **pad)  # 라벨
        self.txt_desc = tk.Text(self, width=40, height=6)  # 멀티라인 입력
        self.txt_desc.grid(row=3, column=1, **pad)  # 배치
        if item:  # 편집 모드
            self.txt_desc.insert("1.0", item.desc)  # 기존 설명 채움

        btns = ttk.Frame(self)  # 버튼 컨테이너
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=10)  # 오른쪽 정렬
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="right", padx=6)  # 취소
        ttk.Button(btns, text="저장", command=self._on_save).pack(side="right")  # 저장

        self.update_idletasks()     # 내부 위젯 크기 계산 갱신
        center_over(parent, self)   # 부모 기준 중앙 배치
        self.ent_title.focus_set()  # 첫 입력 포커스

    def _on_save(self) -> None:
        """입력 검증 후 self.result에 Todo를 세팅하고 팝업을 닫는다."""  # 저장 로직
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
# 메인 앱(노트북 탭: 할 일 / 타이머 / 리포트)                 # 최상위 윈도우/탭 구조
# ─────────────────────────────────────────────────────────
class TodoApp(tk.Tk):
    """최상위 윈도우: 탭 컨테이너 + 각 탭 로직 + AI 도우미."""  # 앱 루트 클래스

    def __init__(self) -> None:
        """창 생성/크기/탭 구성/DB 로드/초기 렌더링 + AI 도우미 준비."""  # 생성자 설명
        super().__init__()  # Tk 루트 초기화
        self.title("갓생살기")  # 창 타이틀 설정
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()  # 스크린 크기
        x, y = (sw - 620) // 2, (sh - 460) // 2  # 창 중앙 좌표(세로 약간 확장)
        self.geometry(f"620x460+{x}+{y}")  # 고정 크기 지정

        self.protocol("WM_DELETE_WINDOW", self._on_close)  # 닫기 이벤트 바인딩

        self.todos: list[Todo] = []  # 할 일 리스트

        self._timer_after_id: str | None = None  # 타이머 틱 루프 ID(after_cancel용)
        self._blink_after_id: str | None = None  # 타임업 깜박임 루프 ID
        self.timer_running: bool = False  # 타이머 동작 여부
        self.timer_total_sec: int = 0     # 총 타이머 시간(초)
        self.timer_warn_sec: int = 30     # 경고 시작 임계(초)
        self.timer_end_mono: float = 0.0  # 단조 시계 기준 종료 목표 시각
        self.timer_remain_sec: int = 0    # 남은 시간(초)
        self._blink_on: bool = False      # 깜박임 토글 상태

        self._report_after_id: str | None = None  # 리포트 자동 갱신 루프 ID
        self._last_rate: float = 0.0              # 이전 완료율
        self._report_booted: bool = False         # 첫 갱신 여부
        self._week_detail_cache: list[dict] | None = None  # New 히트맵 주간 상세(요일별 작업 목록) 캐시
        self._heat_cells: list[tuple[int, tuple[int,int,int,int]]] = []  # New 클릭 좌표→요일 인덱스 매핑용

        # New AI 도우미 상태/스레드
        self._assist_busy: bool = False  # New 중복 호출 방지 플래그
        self._assist_thread: threading.Thread | None = None  # New 네트워크 호출 스레드 저장
        self._assistant_last_tip: str = ""  # New ToDo 탭 상단 라벨에 표시
        self._assistant_popup: tk.Toplevel | None = None  # New 팝업 재사용/토글
        self.assist_enabled: bool = bool(OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_OPENAI_API_KEY")  # New 도우미 사용 가능성

        nb = ttk.Notebook(self)  # 노트북 위젯 생성
        nb.pack(expand=True, fill="both", padx=10, pady=10)  # 배치

        self.tab_todo   = ttk.Frame(nb)  # 할 일 탭
        self.tab_timer  = ttk.Frame(nb)  # 타이머 탭
        self.tab_report = ttk.Frame(nb)  # 리포트 탭

        nb.add(self.tab_todo, text="할 일")  # 탭 추가
        nb.add(self.tab_timer, text="타이머")  # 탭 추가
        nb.add(self.tab_report, text="리포트")  # 탭 추가

        self._build_todo_tab()    # 할 일 탭 구성
        self._build_timer_tab()   # 타이머 탭 구성
        self._build_report_tab()  # 리포트 탭 구성

        self._build_assistant_dock()  # New 전역 도우미 접근점 설치

        init_db()           # 테이블 보장
        self.todos = load_all()  # DB에서 로드
        self.refresh_list() # 리스트/리포트 초기 렌더

        self.after(700, self._ai_refresh_todo_tip)  # New 앱 시작 직후 ToDo 컨텍스트 자동 추천 예약

    # ─────────────────────────────────────────────────────────
    # [할 일] 탭 UI                                            # ToDo 탭 구성
    # ─────────────────────────────────────────────────────────
    def _build_todo_tab(self) -> None:
        """할 일 탭의 입력/버튼/리스트 UI + AI 추천 라벨을 구성."""  # 메서드 설명
        top = ttk.Frame(self.tab_todo)  # 상단 입력/버튼 컨테이너
        top.pack(fill="x", padx=10, pady=10)  # 배치

        self.quick_entry = ttk.Entry(top)  # 제목 한 줄 입력 위젯
        self.quick_entry.pack(side="left", fill="x", expand=True)  # 확장 배치
        self.quick_entry.focus()  # 시작 시 포커스
        self.quick_entry.bind("<Return>", lambda e: self.add_todo())  # Enter→추가

        ttk.Button(top, text="추가",   command=self.add_todo).pack(side="left", padx=6)  # 추가
        ttk.Button(top, text="편집",   command=self.edit_selected).pack(side="left", padx=6)  # 편집
        ttk.Button(top, text="삭제",   command=self.delete_selected).pack(side="left", padx=6)  # 삭제
        ttk.Button(top, text="상태전환 (☐→⏳→✔)", command=self.cycle_status_selected).pack(side="left", padx=6)  # 상태순환

        mid = ttk.Frame(self.tab_todo)  # 리스트/스크롤 컨테이너
        mid.pack(fill="both", expand=True, padx=10, pady=5)  # 배치

        self.listbox = tk.Listbox(mid, height=10, selectmode="extended")  # 다중 선택 가능
        self.listbox.pack(side="left", fill="both", expand=True)  # 배치

        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)  # 세로 스크롤바
        scroll.pack(side="left", fill="y")  # 배치
        self.listbox.config(yscrollcommand=scroll.set)  # 리스트↔스크롤 연동

        self.listbox.bind("<Delete>", lambda e: self.delete_selected())  # Del: 삭제
        self.listbox.bind("<space>",  self._on_space_toggle)             # Space: 상태 토글
        self.listbox.bind("<Double-Button-1>", self.show_details)        # 더블클릭: 상세 보기

        bottom = ttk.Frame(self.tab_todo)  # New 추천 표시/갱신 컨테이너
        bottom.pack(fill="x", padx=10, pady=(0, 8))  # New 배치
        self.lbl_ai_tip = tk.Label(bottom, text="(AI 추천이 여기에 표시됩니다)", anchor="w", justify="left", fg="#1b5e20", wraplength=560)  # New 추천 라벨
        self.lbl_ai_tip.pack(side="left", fill="x", expand=True)  # New 배치
        self.btn_ai_tip_refresh = ttk.Button(bottom, text="AI 추천 새로고침", command=self._ai_refresh_todo_tip)  # New 수동 갱신 버튼
        self.btn_ai_tip_refresh.pack(side="right", padx=(8, 10))  # New 기본 오른쪽 여백(나중에 자동 보정)
        self._todo_bottom = bottom  # New ToDo 하단 프레임 참조(자동 보정용)

    # ─────────────────────────────────────────────────────────
    # [타이머] 탭 UI                                            # 발표 타이머 UI
    # ─────────────────────────────────────────────────────────
    def _build_timer_tab(self) -> None:
        """발표 타이머 입력/컨트롤/피드백 UI 구성."""  # 메서드 설명
        top = ttk.Frame(self.tab_timer)  # 상단 입력/컨트롤 컨테이너
        top.pack(fill="x", **PAD8)  # 배치

        ttk.Label(top, text="발표 시간(분)").pack(side="left")  # 분 입력 라벨
        self.ent_minutes = ttk.Entry(top, width=6)  # 분 입력
        self.ent_minutes.pack(side="left", padx=(4, 12))  # 배치
        self.ent_minutes.insert(0, "5")  # 기본 5분

        ttk.Label(top, text="경고 임계(초)").pack(side="left")  # 경고 임계 라벨
        self.ent_warn = ttk.Entry(top, width=6)  # 경고 임계
        self.ent_warn.pack(side="left", padx=(4, 12))  # 배치
        self.ent_warn.insert(0, "30")  # 기본 30초

        self.btn_start = ttk.Button(top, text="시작",     command=self.start_timer)  # 시작
        self.btn_pause = ttk.Button(top, text="일시정지", command=self.pause_resume_timer, state="disabled")  # 일시정지
        self.btn_reset = ttk.Button(top, text="초기화",   command=self.reset_timer,       state="disabled")  # 초기화
        self.btn_start.pack(side="left", padx=4)  # 배치
        self.btn_pause.pack(side="left", padx=4)  # 배치
        self.btn_reset.pack(side="left", padx=4)  # 배치

        mid = ttk.Frame(self.tab_timer)  # 중앙 표시 영역
        mid.pack(expand=True, fill="both", **PAD8)  # 배치
        self.lbl_timer = tk.Label(mid, text="00:00", font=("Helvetica", 36, "bold"))  # 남은 시간 라벨
        self.lbl_timer.pack(pady=10)  # 배치
        self.pb_timer  = ttk.Progressbar(mid, orient="horizontal", mode="determinate", length=360)  # 진행률 바
        self.pb_timer.pack(fill="x", padx=20, pady=10)  # 배치

        bottom = ttk.Frame(self.tab_timer)  # 하단 프레임
        bottom.pack(fill="x", **PAD8)  # 배치
        ttk.Label(
            bottom,
            text="Tip) 남은 시간이 임계값 이하로 떨어지면 주황색, 0이 되면 빨간색으로 깜박이며 종료를 알립니다."
        ).pack(anchor="w")  # 안내 라벨

        self.var_timer_tip = tk.StringVar(value="")  # New 타이머 조언 텍스트
        self.lbl_timer_tip = ttk.Label(self.tab_timer, textvariable=self.var_timer_tip, foreground="#1e88e5")  # New 표시 라벨
        self.lbl_timer_tip.pack(anchor="w", padx=12, pady=(0, 10))  # New 배치

    # ─────────────────────────────────────────────────────────
    # [리포트] 탭 UI (텍스트 KPI + 도넛 + 스택바 + 주간 히트맵)  # 대시보드 구성
    # ─────────────────────────────────────────────────────────
    def _build_report_tab(self) -> None:
        """리포트 탭의 KPI 텍스트/간단 시각화 위젯을 구성."""  # 메서드 설명
        frm = ttk.Frame(self.tab_report)  # 루트 컨테이너
        frm.pack(fill="both", expand=True, padx=12, pady=12)  # 배치

        ttk.Label(frm, text="📊 주간 성과 리포트", font=("Helvetica", 14, "bold")
                 ).pack(anchor="w", pady=(0, 8))  # 제목

        top = ttk.Frame(frm)  # 상단 행 컨테이너
        top.pack(fill="x")  # 배치

        self.cnv_ring = tk.Canvas(top, width=160, height=160, highlightthickness=0)  # 도넛 캔버스
        self.cnv_ring.pack(side="left", padx=(0, 16))  # 배치

        right = ttk.Frame(top)  # 우측 KPI 묶음
        right.pack(side="left", fill="both", expand=True)  # 배치
        self.lbl_rate   = ttk.Label(right, text="완료율 0.0%", font=("Helvetica", 12, "bold"))  # 완료율 라벨
        self.lbl_rate.pack(anchor="w", pady=(4, 6))  # 배치

        self.var_avg    = tk.StringVar(value="평균 기간: 0.0일")  # 평균 기간
        self.var_soon   = tk.StringVar(value="마감 임박: 0건")    # 임박 건수
        self.var_over   = tk.StringVar(value="지남: 0건")        # 지남 건수
        self.var_counts = tk.StringVar(value="상태 구성: 미완 0 · 진행 0 · 완료 0")  # 상태 구성

        ttk.Label(right, textvariable=self.var_avg   ).pack(anchor="w")  # 배치
        ttk.Label(right, textvariable=self.var_soon  ).pack(anchor="w")  # 배치
        ttk.Label(right, textvariable=self.var_over  ).pack(anchor="w")  # 배치
        ttk.Label(right, textvariable=self.var_counts).pack(anchor="w", pady=(2, 0))  # 배치

        self.cnv_stack = tk.Canvas(frm, height=22, highlightthickness=0)  # 스택바 캔버스
        self.cnv_stack.pack(fill="x", pady=(10, 6))  # 배치

        # New 히트맵의 집계 기간(월~일) 라벨을 히트맵 바로 위에 배치
        self.var_week_range = tk.StringVar(value="")  # New 집계 범위 텍스트 상태(예: 2025-09-15 ~ 2025-09-21)
        ttk.Label(frm, textvariable=self.var_week_range, foreground="#555").pack(anchor="w", pady=(0, 4))  # New 라벨 표시

        self.cnv_heat = tk.Canvas(frm, height=70, highlightthickness=0, cursor="hand2")  # 히트맵 캔버스(조금 키움)
        self.cnv_heat.pack(fill="x")  # 배치
        self.cnv_heat.bind("<Button-1>", self._on_heat_click)  # New 클릭: 하이라이트
        self.cnv_heat.bind("<Double-Button-1>", self._on_heat_dblclick)  # New 더블클릭: 상세 팝업

        ttk.Label(frm, text="※ 5초마다 자동 갱신 · 리스트 변경 시 즉시 반영", foreground="#666"
                 ).pack(anchor="w", pady=(8, 0))  # 안내

    # ─────────────────────────────────────────────────────────
    # 전역 '미니 도우미' 도크/팝업                              # 숨은 AI 접근 UI
    # ─────────────────────────────────────────────────────────
    def _build_assistant_dock(self) -> None:
        """우하단에 '✨ 도우미' 부동 버튼을 만들고 Ctrl+K로 토글한다."""  # New 설명
        dock = ttk.Frame(self)  # New 도크 프레임
        dock.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")  # New 우하단 모서리 부착
        self.btn_assist = ttk.Button(dock, text="✨ 도우미", command=self._toggle_assistant_popup)  # New 토글 버튼
        self.btn_assist.pack()  # New 배치
        self.update_idletasks()  # New 레이아웃 강제 반영(실제 픽셀 크기 파악)
        self._assist_btn_w = self.btn_assist.winfo_width()  # New 버튼 폭(px)
        self._assist_btn_h = self.btn_assist.winfo_height()  # New 버튼 높이(px)
        self._reflow_for_dock()  # New ToDo 하단 새로고침 버튼과 겹치지 않도록 초기 보정
        self.bind("<Configure>", lambda e: self._reflow_for_dock())  # New 창 크기/스케일 변경 시 재보정
        self.bind_all("<Control-k>", lambda e: self._toggle_assistant_popup())  # New 단축키(Ctrl+K) 토글

    def _reflow_for_dock(self) -> None:
        """도우미 버튼과 겹치지 않도록 ToDo 새로고침 버튼의 오른쪽 여백을 자동 보정한다."""  # New
        try:
            self.update_idletasks()  # New 최신 크기 반영
            dock_w = (self.btn_assist.winfo_width() if hasattr(self, "btn_assist") else 80) or 80  # New 도우미 폭
            right_pad = max(10, dock_w + 18)  # New 버튼 폭 + 여유
            if hasattr(self, "btn_ai_tip_refresh"):
                self.btn_ai_tip_refresh.pack_configure(padx=(8, right_pad))  # New 동적 보정
        except Exception:
            pass  # New 위젯 타이밍 이슈 시 무시

    def _toggle_assistant_popup(self) -> None:
        """미니 도우미 팝업을 토글한다(없으면 생성, 있으면 닫기)."""  # New 설명
        # New 기존 코드의 클래스 메서드 호출 방식 대신 인스턴스 메서드로 안정화
        if self._assistant_popup and self._assistant_popup.winfo_exists():  # New 팝업 존재 확인
            self._assistant_popup.destroy()  # New 닫기
            self._assistant_popup = None  # New 리셋
            return  # New 종료
        pop = tk.Toplevel(self)  # New 최상위 팝업 생성
        pop.title("✨ 도우미")  # New 제목
        pop.resizable(False, False)  # New 크기 고정
        pop.transient(self)  # New 부모 앞 표시
        self._assistant_popup = pop  # New 핸들 저장

        frm = ttk.Frame(pop)  # New 루트 프레임
        frm.pack(fill="both", expand=True, padx=10, pady=10)  # New 배치
        ttk.Label(frm, text="현재 탭 컨텍스트를 바탕으로 질문하거나, '컨텍스트 분석'으로 바로 제안을 받아보세요."
                 ).pack(anchor="w", pady=(0, 6))  # New 안내
        self.txt_ask = tk.Text(frm, width=46, height=4, wrap="word")  # New 질문 입력
        self.txt_ask.pack(fill="x")  # New 배치

        row = ttk.Frame(frm)  # New 버튼 컨테이너
        row.pack(fill="x", pady=(6, 0))  # New 배치
        ttk.Button(row, text="컨텍스트 분석", command=self._assistant_analyze_context).pack(side="left")  # New 자동분석
        ttk.Button(row, text="보내기", command=self._assistant_send_prompt).pack(side="right")  # New 사용자 질문

        self.txt_ans = tk.Text(frm, width=46, height=10, wrap="word", state="disabled")  # New 응답 표시
        self.txt_ans.pack(fill="both", expand=True, pady=(8, 0))  # New 배치
        center_over(self, pop)  # New 부모 기준 중앙 배치

    def _assistant_append_text(self, text: str) -> None:
        """팝업 응답 영역에 텍스트를 추가한다."""  # New 설명
        if not (self._assistant_popup and self._assistant_popup.winfo_exists()):  # New 팝업 유효성
            return  # New 없으면 무시
        self.txt_ans.config(state="normal")  # New 편집 가능 전환
        self.txt_ans.insert("end", text + "\n")  # New 텍스트 추가
        self.txt_ans.see("end")  # New 스크롤 하단
        self.txt_ans.config(state="disabled")  # New 다시 잠금

    def _assistant_send_prompt(self) -> None:
        """사용자 입력 프롬프트를 현재 탭 컨텍스트와 결합해 질의한다."""  # New 설명
        prompt = self.txt_ask.get("1.0", "end").strip()  # New 입력 읽기
        if not prompt:  # New 공란 방지
            messagebox.showwarning("확인", "질문을 입력하세요.", parent=self._assistant_popup)  # New 경고
            return  # New 종료
        ctx = self._compose_context_for_active_tab()  # New 현재 탭 요약
        user_prompt = f"다음 컨텍스트를 참고하여 한국어로 간단하고 실용적인 조언을 주세요.\n\n컨텍스트(JSON):\n{ctx}\n\n질문:\n{prompt}"  # New 사용자 질문 결합
        self._assistant_call_async(user_prompt, purpose="popup")  # New 비동기 호출

    def _assistant_analyze_context(self) -> None:
        """사용자 질문 없이 현재 탭 컨텍스트만으로 구체적 제안을 생성."""  # New 설명
        ctx = self._compose_context_for_active_tab()  # New 요약
        prompt = (
            "다음 컨텍스트를 바탕으로 '바로 실행할 3가지 제안'과 '근거'를 한국어 목록으로 요약하세요. "
            "가능하면 작업 이름을 직접 언급하고, 마감 임박/지남/진행중 우선순위를 반영하세요.\n\n"
            f"{ctx}"
        )  # New 프롬프트
        self._assistant_call_async(prompt, purpose="popup")  # New 호출

    # ─────────────────────────────────────────────────────────
    # 공통 동작: 선택/리스트 갱신/저장                           # 공통 헬퍼
    # ─────────────────────────────────────────────────────────
    def _selected_indices(self) -> tuple[int, ...] | None:
        """리스트박스에서 사용자가 선택한 항목 인덱스 튜플을 반환(없으면 경고 후 None)."""  # 메서드 설명
        sel = self.listbox.curselection()  # 선택 인덱스들
        if not sel:
            messagebox.showwarning("확인", "항목을 선택하세요.", parent=self)
            return None
        return sel

    def refresh_list(self) -> None:
        """현재 self.todos를 리스트박스에 반영하고, 리포트도 함께 갱신."""  # 리스트/리포트 동기화
        self.listbox.delete(0, tk.END)  # 기존 삭제
        if self.todos:
            self.listbox.insert(tk.END, *[t.display() for t in self.todos])  # 1줄 요약 문자열 삽입
        self.refresh_report()  # 리포트 갱신
        self.after(250, self._ai_refresh_todo_tip)  # New 목록 변경 후 가벼운 자동 추천 큐잉

    def _save(self) -> None:
        """현재 메모리 리스트(self.todos)를 DB에 저장(덮어쓰기 방식)."""  # 저장 호출
        save_all(self.todos)  # 덮어쓰기 저장

    # ─────────────────────────────────────────────────────────
    # 사용자 액션: 추가/편집/삭제/상태전환/상세보기               # CRUD/토글/뷰
    # ─────────────────────────────────────────────────────────
    def add_todo(self) -> None:
        """새 할 일을 추가(빠른입력칸 내용으로 제목 prefill)."""  # 추가 동작
        prefill = self.quick_entry.get().strip()  # prefill 추출
        dlg = TodoDialog(self, "할 일 추가", prefill=prefill)  # 추가 팝업
        self.wait_window(dlg)  # 모달 대기
        if dlg.result:         # 저장됨
            self.todos.append(dlg.result)  # 리스트 추가
            self._save()                   # 저장
            self.refresh_list()            # UI 갱신

    def edit_selected(self) -> None:
        """선택한 첫 항목을 편집 팝업으로 열고 저장 시 교체."""  # 편집 동작
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
        """선택된 여러 항목을 삭제(뒤에서부터 지워 인덱스 당김 문제 방지)."""  # 삭제 동작
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
        """선택된 모든 항목의 상태를 0→1→2→0 순환."""  # 상태 토글
        sel = self._selected_indices()
        if not sel:
            return
        for i in sel:
            self.todos[i].cycle()
        self._save()
        self.refresh_list()

    def _on_space_toggle(self, _e) -> str:
        """스페이스바로 상태 순환(리스트박스 기본 스페이스 동작은 차단)."""  # 키바인드
        self.cycle_status_selected()  # 상태 전환
        return "break"  # 기본 동작 차단

    def show_details(self, _e=None) -> None:
        """선택된 첫 항목의 상세 정보(읽기 전용) 팝업을 표시."""  # 상세 팝업
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
        """정수 초를 'MM:SS' 형식 문자열로 변환(음수 방지/0 패딩 포함)."""  # 포맷 유틸
        s = max(0, int(s))  # 음수 방지 및 정수화
        m, ss = divmod(s, 60)  # 분/초 분리
        return f"{m:02d}:{ss:02d}"  # 2자리 0패딩

    def _set_timer_controls_running(self, running: bool) -> None:
        """타이머 실행 여부에 따라 버튼/입력 상태를 전환(오조작 방지)."""  # 컨트롤 상태 전환
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
        """예약된 타이머 틱(after) 루프를 안전하게 취소."""  # after 취소
        if self._timer_after_id is not None:
            try:
                self.after_cancel(self._timer_after_id)  # 예약 취소
            except Exception:
                pass  # 이미 만료된 경우 무시
            self._timer_after_id = None  # 상태 클리어

    def _stop_blink(self) -> None:
        """타임업 깜박임 루프를 중지하고 글자색을 원래대로 복원."""  # 깜박임 정지
        if self._blink_after_id is not None:
            try:
                self.after_cancel(self._blink_after_id)  # 예약 취소
            except Exception:
                pass
            self._blink_after_id = None
        self._blink_on = False  # 토글 리셋
        self.lbl_timer.config(fg="black")  # 글자색 복원

    def _start_blink(self) -> None:
        """타임업 시 빨강/검정을 교대로 깜박이며 종료를 강하게 알림."""  # 시각 경고
        self._blink_on = not self._blink_on  # 토글
        self.lbl_timer.config(fg=("red" if self._blink_on else "black"))  # 색상 토글
        self._blink_after_id = self.after(450, self._start_blink)  # 0.45초 간격

    def start_timer(self) -> None:
        """입력값 검증 후 타이머를 시작하고 주기 틱 루프를 가동."""  # 시작 로직
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
        self._ai_timer_tip_once()  # New 타이머 컨텍스트 기반 즉시 코칭 1줄 생성

    def pause_resume_timer(self) -> None:
        """일시정지/계속 토글 — 남은 시간을 저장/복구하여 정확도 유지."""  # 일시정지/재개
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
        """타이머를 완전히 초기 상태로 되돌림(루프/깜박임 포함)."""  # 초기화
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
        """남은 시간이 0이 되었을 때 타임업 처리(소리+색+깜박으로 강한 신호)."""  # 타임업 처리
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
        """200ms 간격으로 남은 시간을 갱신하고, 경고/진행률/종료를 처리."""  # 주기 틱
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
        """리포트 자동 갱신(after) 예약이 있으면 취소하여 중복 루프를 방지."""  # after 취소
        if self._report_after_id:
            try:
                self.after_cancel(self._report_after_id)
            except Exception:
                pass
            self._report_after_id = None

    def calc_report_stats(self) -> dict:
        """self.todos를 집계해 리포트용 요약 지표를 계산."""  # 집계 핵심
        total = len(self.todos)  # 총 개수
        today = date.today()  # New 오늘 날짜(주간 범위 표기를 위해 먼저 계산)
        start_week = today - timedelta(days=today.weekday())  # New 이번 주 월요일(기준 시작일)
        end_week = start_week + timedelta(days=6)  # New 이번 주 일요일(기준 종료일)

        if total == 0:  # 비어있을 때
            # New week_detail(요일별 리스트)와 주간 범위(week_start/week_end)도 함께 반환
            return {"rate": 0.0, "avg_days": 0.0, "soon": 0, "overdue": 0,
                    "counts": (0, 0, 0), "week_bins": [0]*7,
                    "week_detail": [{"due": [], "open": [], "doing": [], "done": []} for _ in range(7)],  # New 상세
                    "week_start": start_week.isoformat(), "week_end": end_week.isoformat()}  # New 주간 범위

        cnt0 = sum(1 for t in self.todos if t.status == 0)  # 미완
        cnt1 = sum(1 for t in self.todos if t.status == 1)  # 진행
        cnt2 = sum(1 for t in self.todos if t.status == 2)  # 완료
        rate = round(cnt2 / total * 100, 1)  # 완료율 %

        soon = 0       # 3일 이내 마감
        overdue = 0    # 마감 초과
        durations: list[int] = []  # 기간 리스트
        week_bins = [0]*7          # 월(0)~일(6)
        week_detail = [{"due": [], "open": [], "doing": [], "done": []} for _ in range(7)]  # New 요일별 상세

        for t in self.todos:
            try:
                d1 = parse_date(t.start).date()  # 시작일
                d2 = parse_date(t.end).date()    # 종료일(마감일)
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
                if t.status == 0:
                    week_detail[off]["open"].append(t)  # New 미완
                elif t.status == 1:
                    week_detail[off]["doing"].append(t)  # New 진행
                else:
                    week_detail[off]["done"].append(t)  # New 완료
                week_detail[off]["due"].append(t)  # New due 전체

        avg_days = round(sum(durations)/len(durations), 1) if durations else 0.0  # 평균 기간
        return {"rate": rate, "avg_days": avg_days, "soon": soon, "overdue": overdue,
                "counts": (cnt0, cnt1, cnt2), "week_bins": week_bins, "week_detail": week_detail,  # New 상세 포함
                "week_start": start_week.isoformat(), "week_end": end_week.isoformat()}  # New 주간 범위 포함

    def refresh_report(self) -> None:
        """리포트 텍스트/KPI와 시각화를 갱신하고, 5초 후 다시 자신을 예약."""  # 갱신 루프
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

        # New 히트맵 집계 기간 라벨 업데이트(월~일 기준 범위가 무엇인지 명시)
        self.var_week_range.set(f"📅 집계 범위: {s['week_start']} ~ {s['week_end']} (월~일 기준)")  # New 주간 범위 표기

        self._week_detail_cache = s.get("week_detail", None)  # New 캐시
        self._draw_heat(s["week_bins"], s.get("week_detail"))    # New 히트맵(숫자/클릭)

        prev = self._last_rate  # 이전 완료율
        if self._report_booted and any(prev < m <= s['rate'] for m in (50, 80, 100)):  # 마일스톤 돌파
            self._burst_confetti(duration=800)  # 컨페티
        self._report_booted = True  # 첫 갱신 이후
        self._last_rate = s["rate"]  # 현재 저장

        self._report_after_id = self.after(5000, self.refresh_report)  # 5초 후 자동 갱신

    def _rate_color(self, rate: float) -> str:
        """완료율(%)에 따른 시그널 색을 반환: <50 빨강, <80 주황, 그 외 초록."""  # 컬러 스케일
        return "#e53935" if rate < 50 else "#fb8c00" if rate < 80 else "#43a047"  # 삼항

    def _draw_ring(self, rate: float) -> None:
        """완료율(0~100)을 도넛 형태로 그린다(베이스 링+진행 아크+중앙 퍼센트)."""  # 도넛 렌더
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
        """완료율 변화량에 따라 도넛을 부드럽게 보간 렌더(아주 작으면 즉시 반영)."""  # 도넛 애니
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
        """상태 구성(미완/진행/완료)을 가로 스택바로 시각화."""  # 스택바 렌더
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

    def _draw_heat(self, bins: list[int], detail: list[dict] | None) -> None:
        """이번 주(월~일) 마감 건수 히트맵을 숫자(미완/진행/완료)와 함께 렌더하고 클릭 가능하게 한다."""  # New 히트맵 렌더
        c = self.cnv_heat  # New 캔버스
        c.delete("all")  # New 초기화
        self._heat_cells = []  # New 이전 셀 기록 초기화
        w = c.winfo_width() or 420  # New 폭
        h = 70  # New 높이
        cell = w // 7  # New 칸 폭
        pad = 4  # New 내부 패딩
        days = ["월", "화", "수", "목", "금", "토", "일"]  # New 요일
        mx = max(bins) or 1  # New 색상 스케일 최대값
        def blend(a: str, b: str, t: float) -> str:
            """hex 색상 a→b 사이를 t(0~1)로 보간하여 hex로 반환."""  # New 색 보간
            ah, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)  # New 시작 RGB
            bh, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)  # New 끝 RGB
            ih, ig, ib = int(ah + (bh - ah) * t), int(ag + (bg - ag) * t), int(ab + (bb - ab) * t)  # New 보간
            return f"#{ih:02x}{ig:02x}{ib:02x}"  # New hex 반환

        for i, v in enumerate(bins):  # New 각 요일 반복
            x0, x1 = i * cell + pad, (i + 1) * cell - pad  # New x 범위
            y0, y1 = pad, h - 22  # New y 범위(아래쪽 텍스트 공간 확보)
            col = blend("#e8f5e9", "#1b5e20", v / mx)  # New 연녹→진녹
            c.create_rectangle(x0, y0, x1, y1, fill=col, outline="#cfd8dc")  # New 칸 박스
            open_n = len(detail[i]["open"]) if detail else 0  # New 미완
            doing_n = len(detail[i]["doing"]) if detail else 0  # New 진행
            done_n = len(detail[i]["done"]) if detail else 0  # New 완료
            c.create_text((x0 + x1)//2, (y0 + y1)//2 - 6, text=f"{open_n}/{doing_n}/{done_n}", font=("Helvetica", 9, "bold"))  # New 숫자
            c.create_text((x0 + x1)//2, y1 + 8, text=days[i], font=("Helvetica", 9))  # New 요일 라벨
            self._heat_cells.append((i, (x0, y0, x1, y1)))  # New 셀 bbox 기록

        c.create_rectangle(pad, pad, w - pad, h - pad - 12, outline="#b0bec5")  # New 전체 박스(테두리)

    def _hit_test_heat(self, event) -> int | None:
        """히트맵 클릭 좌표를 요일 인덱스로 변환."""  # New 히트 테스트
        x, y = event.x, event.y  # New 클릭 좌표
        for idx, (x0, y0, x1, y1) in self._heat_cells:  # New 각 셀 검사
            if x0 <= x <= x1 and y0 <= y <= y1:  # New 범위 안?
                return idx  # New 해당 요일 반환
        return None  # New 없으면 None

    def _on_heat_click(self, event) -> None:
        """히트맵 클릭 시 해당 칸 하이라이트만 적용."""  # New 클릭 처리
        idx = self._hit_test_heat(event)  # New 요일 인덱스
        if idx is None:  # New 빈 영역
            return  # New 무시
        c = self.cnv_heat  # New 캔버스
        c.delete("hl")  # New 이전 하이라이트 제거
        x0, y0, x1, y1 = self._heat_cells[idx][1]  # New bbox
        c.create_rectangle(x0-2, y0-2, x1+2, y1+2, outline="#1e88e5", width=2, tags="hl")  # New 하이라이트 박스

    def _on_heat_dblclick(self, event) -> None:
        """히트맵 더블클릭 시 해당 요일 상세 팝업을 표시."""  # New 더블클릭 처리
        idx = self._hit_test_heat(event)  # New 요일 인덱스
        if idx is None or not self._week_detail_cache:  # New 유효성
            return  # New 무시
        detail = self._week_detail_cache[idx]  # New 상세

        pop = tk.Toplevel(self)  # New 팝업 생성
        pop.title(f"요일 상세 - {['월','화','수','목','금','토','일'][idx]}")  # New 제목
        pop.resizable(False, False)  # New 고정
        frm = ttk.Frame(pop)  # New 컨텐츠
        frm.pack(fill="both", expand=True, padx=10, pady=10)  # New 배치

        ttk.Label(frm, text=f"미완 {len(detail['open'])} · 진행 {len(detail['doing'])} · 완료 {len(detail['done'])}",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(0, 6))  # New 헤더

        box = tk.Listbox(frm, height=10, width=56)  # New 목록
        box.pack(fill="both", expand=True)  # New 배치
        for t in detail["open"] + detail["doing"] + detail["done"]:  # New 상태 순서대로
            box.insert("end", f"{STATUS_ICON.get(t.status)} {t.start}~{t.end} | {t.title}")  # New 항목

        foot = ttk.Frame(frm)  # New 버튼행
        foot.pack(fill="x", pady=(8, 0))  # New 배치
        ttk.Button(foot, text="닫기", command=pop.destroy).pack(side="right")  # New 닫기
        ttk.Button(foot, text="선택 편집", command=lambda: self._open_from_heat_selection(box, pop)).pack(side="right", padx=(0, 6))  # New 편집 이동
        center_over(self, pop)  # New 위치

    def _open_from_heat_selection(self, listbox: tk.Listbox, pop: tk.Toplevel) -> None:
        """히트맵 상세 팝업에서 선택한 항목을 메인 리스트에서 찾아 편집."""  # New 기능
        sel = listbox.curselection()  # New 선택
        if not sel:  # New 없으면
            return  # New 종료
        text = listbox.get(sel[0])  # New 항목 텍스트
        title = text.split("|", 1)[-1].strip() if "|" in text else text  # New 제목 추출
        idx = next((i for i, t in enumerate(self.todos) if t.title == title), None)  # New 검색
        if idx is None:  # New 못 찾음
            return  # New 종료
        pop.destroy()  # New 팝업 닫기
        self.listbox.selection_clear(0, "end")  # New 초기화
        if 0 <= idx < self.listbox.size():  # New 범위 체크
            self.listbox.selection_set(idx)  # New 선택
            self.listbox.see(idx)  # New 스크롤
            self.edit_selected()  # New 편집 실행

    # ─────────────────────────────────────────────────────────
    # 색상/도넛/스택바/히트맵/컨페티 드로잉 유틸                 # 시각화 유틸
    # ─────────────────────────────────────────────────────────
    def _burst_confetti(self, n: int = 28, duration: int = 800) -> None:
        """도넛 캔버스 위에서만 0.8초간 컨페티를 떨어뜨려 시각적 보상을 제공."""  # 축하 애니
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
    # 숨은 AI 도우미 로직(백그라운드 호출/자동추천/폴백)         # 핵심 추가
    # ─────────────────────────────────────────────────────────
    def _assistant_available(self) -> bool:
        """도우미 사용 가능 여부(키 설정 여부) 확인."""  # New 유틸
        return self.assist_enabled  # New 간단 반환

    def _assistant_call(self, user_prompt: str, system_prompt: str = "너는 일정·태스크 관리 코치다. 한국어로 간결하고 실용적인 조언만 제공하라.",
                         temperature: float = 0.6) -> tuple[bool, str]:
        """동기적으로 Chat Completions 호출(에러 시 False, 메시지)."""  # New 네트워크 호출
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}  # New 인증 헤더
        data = {"model": ASSIST_MODEL_DEFAULT,
                "messages": [{"role": "system", "content": system_prompt},
                             {"role": "user", "content": user_prompt}],
                "temperature": temperature}  # New 요청 본문
        code, text = _http_post(OPENAI_URL_CHAT, headers=headers, data=data, timeout=ASSIST_TIMEOUT)  # New POST
        if code == 200:  # New 성공
            try:
                obj = json.loads(text)  # New 파싱
                msg = (obj.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()  # New 메시지
                if not msg:  # New 빈 응답
                    return False, "빈 응답입니다."  # New 실패
                return True, msg  # New 성공
            except Exception as e:  # New 파싱 실패
                return False, f"응답 파싱 실패: {e}"  # New 실패
        else:  # New HTTP 오류
            try:
                err = json.loads(text).get("error", {}).get("message", text)  # New 에러 추출
            except Exception:
                err = text  # New 원문
            return False, f"오류 {code}: {err}"  # New 실패

    def _assistant_call_async(self, prompt: str, purpose: str = "todo_tip") -> None:
        """도우미를 비동기 호출하고 목적(purpose)에 맞게 UI 반영."""  # New 비동기 래퍼
        if self._assist_busy:  # New 중복 방지
            return  # New 무시
        self._assist_busy = True  # New 바쁨 플래그
        def worker():  # New 스레드 함수
            if not self._assistant_available():  # New 키 없음 → 로컬 폴백
                ok, msg = False, self._local_fallback_advice(purpose)  # New 폴백
            else:
                ok, msg = self._assistant_call(prompt)  # New 네트워크 호출
            def ui():  # New UI 반영 클로저
                self._assist_busy = False  # New 플래그 해제
                if purpose == "todo_tip":  # New ToDo 라벨
                    self._assistant_last_tip = msg  # New 저장
                    self.lbl_ai_tip.config(text=msg, fg=("#1b5e20" if ok else "#e53935"))  # New 표시
                elif purpose == "popup":  # New 팝업 응답
                    self._assistant_append_text(msg)  # New 출력
                elif purpose == "timer_tip":  # New 타이머 힌트
                    self.var_timer_tip.set(msg)  # New 표시
            self.after(0, ui)  # New 메인 스레드 예약
        self._assist_thread = threading.Thread(target=worker, daemon=True)  # New 스레드 생성
        self._assist_thread.start()  # New 시작

    def _compose_context_for_active_tab(self) -> str:
        """현재 활성 탭의 컨텍스트를 JSON 문자열로 요약."""  # New 컨텍스트 빌드
        try:
            sel = self.listbox.curselection()  # New 선택
            selected_titles = [self.todos[i].title for i in sel] if sel else []  # New 선택 제목
        except Exception:
            selected_titles = []  # New 예외 시 비움
        stats = self.calc_report_stats()  # New 집계
        ctx = {
            "tab": "todo/timer/report(unified)",  # New 탭 개념 통합
            "todos_total": len(self.todos),  # New 총수
            "selected": selected_titles,  # New 선택 목록
            "counts": {"open": stats["counts"][0], "doing": stats["counts"][1], "done": stats["counts"][2]},  # New 상태
            "soon": stats["soon"], "overdue": stats["overdue"], "rate": stats["rate"],  # New KPI
            "timer": {"running": self.timer_running, "remain_sec": self.timer_remain_sec,
                      "total_sec": self.timer_total_sec, "warn_sec": self.timer_warn_sec},  # New 타이머
            "top_items": [{"title": t.title, "end": t.end, "status": t.status} for t in self.todos[:10]]  # New 상위 N
        }  # New 컨텍스트
        return json.dumps(ctx, ensure_ascii=False, indent=2)  # New JSON 문자열

    def _compose_context_for_todo_tip(self) -> str:
        """ToDo 탭 전용 요약(JSON) 생성."""  # New 전용 컨텍스트
        today = date.today()  # New 오늘
        items = []
        for t in self.todos:  # New 순회
            try:
                d2 = parse_date(t.end).date()  # New 마감일
                days = (d2 - today).days  # New 남은 일수
            except Exception:
                days = None  # New 파싱 실패
            items.append({"title": t.title, "end": t.end, "status": STATUS_TEXT.get(t.status), "dday": days})  # New 기록
        ctx = {"total": len(self.todos),
               "imminent": sum(1 for it in items if it["dday"] is not None and 0 <= it["dday"] <= 3 and it["status"] != "완료"),  # New 임박
               "overdue": sum(1 for it in items if it["dday"] is not None and it["dday"] < 0 and it["status"] != "완료"),  # New 지남
               "items": items}  # New 아이템
        return json.dumps(ctx, ensure_ascii=False, indent=2)  # New 문자열

    def _ai_refresh_todo_tip(self) -> None:
        """ToDo 탭 하단 추천 라벨을 갱신."""  # New 동작
        ctx = self._compose_context_for_todo_tip()  # New 컨텍스트
        prompt = (
            "다음 ToDo 목록 컨텍스트를 참고해 '지금 바로 할 3가지 액션'을 한국어로 제안하고, 각 항목에 한 줄 근거를 붙이세요. "
            "지남/임박 항목에 우선순위를 두고, 진행중인 항목은 다음 체크포인트를 제시하세요.\n\n" + ctx
        )  # New 프롬프트
        self._assistant_call_async(prompt, purpose="todo_tip")  # New 호출

    def _ai_timer_tip_once(self) -> None:
        """타이머 시작 직후 1줄 코칭 문구 제공."""  # New 타이머 힌트
        prompt = f"발표 타이머가 {self.timer_total_sec}초로 시작했습니다. 경고 임계 {self.timer_warn_sec}초입니다. " \
                 f"남은 시간 신호에 맞춰 마무리 루틴을 1~2문장으로 조언해 주세요(한국어)."  # New 프롬프트
        self._assistant_call_async(prompt, purpose="timer_tip")  # New 호출

    def _local_fallback_advice(self, purpose: str) -> str:
        """API 키 미설정/오프라인 시 로컬 규칙으로 간단 추천을 생성."""  # New 폴백 로직
        today = date.today()  # New 오늘
        scored = []  # New (점수, 작업) 목록
        for t in self.todos:
            try:
                d2 = parse_date(t.end).date()  # New 마감
                days = (d2 - today).days  # New D-day
            except Exception:
                days = 9999  # New 파싱 실패는 낮은 우선순위
            score = (-1000 if (t.status != 2 and days < 0) else
                     -500 if (t.status != 2 and 0 <= days <= 3) else
                     -200 if t.status == 1 else
                     -50)  # New 간단 점수 규칙
            scored.append((score, t))  # New 추가
        scored.sort(key=lambda x: x[0])  # New 정렬
        top = [s[1] for s in scored[:3]]  # New 상위 3개
        if purpose == "timer_tip":  # New 타이머용 문구
            return "⏱️ 발표는 끝맺음이 중요합니다. 마지막 30초엔 핵심 요약→콜투액션 순으로 마무리하세요."  # New 문구
        lines = []
        for t in top:
            tag = "지남" if parse_date(t.end).date() < today else "임박" if (parse_date(t.end).date()-today).days <= 3 else "일반"  # New 태그
            why = "마감 초과" if tag == "지남" else "3일 내 마감" if tag == "임박" else "현재 우선순위 상위"  # New 근거
            lines.append(f"• {t.title} → 지금 15분만 투자해서 다음 체크포인트 정의 ({why})")  # New 제안
        if not lines:
            lines = ["• 오늘은 새 작업을 추가하기보다 완료율을 높여보세요(작은 항목 1~2개 마무리)."]  # New 기본 제안
        return "키 미설정/오프라인 폴백 제안:\n" + "\n".join(lines)  # New 결과

    # ─────────────────────────────────────────────────────────
    # 종료 처리(안전 정리)                                      # 종료 시퀀스
    # ─────────────────────────────────────────────────────────
    def _on_close(self) -> None:
        """예약된 after 루프(타이머/깜박/리포트)를 모두 취소하고 창을 닫는다."""  # 종료 정리
        self._stop_tick_loop()   # 타이머 루프 정지
        self._stop_blink()       # 깜박임 루프 정지
        self._stop_report_loop() # 리포트 루프 정지
        if self._assistant_popup and self._assistant_popup.winfo_exists():  # New 도우미 팝업 있으면
            try:
                self._assistant_popup.destroy()  # New 닫기
            except Exception:
                pass  # New 무시
        self.destroy()  # 창 파괴(프로세스 종료)

# ─────────────────────────────────────────────────────────
# 실행 엔트리포인트                                           # main guard
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":  # 이 파일을 직접 실행할 때만 아래 코드 실행
    app = TodoApp()   # 최상위 앱 인스턴스 생성
    app.mainloop()    # Tk 이벤트 루프 시작(사용자 인터랙션 처리)
