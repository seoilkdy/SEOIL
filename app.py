# ─────────────────────────────────────────────────────────
# Tkinter: 파이썬 기본 GUI                                   # 앱의 목적/범주 설명
# ─────────────────────────────────────────────────────────
# 간단한 ToDo 관리 + 프리젠테이션 타이머 + 실시간 '성과 리포트' 대시보드를 제공하는 Tkinter 데스크톱 앱이다.  # New 상위 요약

from dataclasses import dataclass  # dataclass 데코레이터로 생성자/표현 등 보일러플레이트 자동 생성
from datetime import date, datetime, timedelta  # 날짜(date), 날짜시간(datetime), 기간(timedelta)
from pathlib import Path  # 운영체제 무관한 경로 처리
import time  # 단조 증가 시계(time.monotonic) 사용 → 시스템 시간 변경 영향을 안 받는 타이머
import math  # 올림/내림, 보간 계산 등에 사용
import sqlite3 as sql  # 내장 SQLite DB로 간단 영속화(파일 1개)
import tkinter as tk  # Tkinter 기본 위젯
from tkinter import ttk, messagebox  # ttk(현대식 스킨), messagebox(모달 알림/확인)

# ─────────────────────────────────────────────────────────
# 상수/포맷/공용 패딩                                         # 상수/공용 값 묶음
# ─────────────────────────────────────────────────────────
DATE_FMT = "%Y-%m-%d"  # 날짜 문자열 형식(예: 2025-09-16) — DB/표시 포맷을 통일해 파싱오류를 줄임
STATUS_ICON = {0: "☐", 1: "⏳", 2: "✔"}  # 상태코드→아이콘 매핑(미완/진행/완료)
STATUS_TEXT = {0: "미완료", 1: "진행중", 2: "완료"}  # 상태코드→읽을 수 있는 텍스트
PAD6 = {"padx": 10, "pady": 6}  # grid/pack 공통 여백 프리셋(6)
PAD8 = {"padx": 10, "pady": 8}  # 공통 여백 프리셋(8)
# New 아이콘/텍스트 매핑을 통해 리스트, 상세 팝업, 리포트 문구 등 UI 전반의 표현을 일관되게 유지한다.

# ─────────────────────────────────────────────────────────
# DB 경로 고정(스크립트 폴더) + 대화형 환경 폴백             # 실행 환경 차이에 따른 DB 경로 보정
# ─────────────────────────────────────────────────────────
try:
    DB_PATH = str(Path(__file__).with_name("todo.db"))  # 스크립트 파일과 같은 폴더에 todo.db 생성/사용
except NameError:
    DB_PATH = "todo.db"  # __file__이 없는 인터프리터/노트북 환경에서는 현재 작업 폴더에 저장
# New __file__ 유무에 따라 경로 전략을 분기 → 어디서 실행해도 동일한 파일명을 쓰도록 안정화.

# ─────────────────────────────────────────────────────────
# 유틸: 날짜 파싱 / 창 중앙 배치                              # 자주 쓰는 헬퍼 함수 모음
# ─────────────────────────────────────────────────────────
def parse_date(s: str) -> datetime:  # 날짜 문자열을 datetime으로 파싱하는 헬퍼 시그니처
    """날짜 문자열(YYYY-MM-DD)을 datetime 객체로 변환."""  # 형식 오류 시 예외를 발생시켜 호출부에서 UX 처리
    return datetime.strptime(s, DATE_FMT)  # 형식 불일치 시 ValueError 발생 → 호출부에서 UX 메시지 처리

def center_over(parent: tk.Tk, win: tk.Toplevel) -> None:  # 부모 기준 중앙 배치 함수 시그니처
    """부모창 기준으로 자식창을 화면 중앙에 배치(화면 밖으로 나가지 않게 보정 포함)."""  # 목적/보정 설명
    parent.update_idletasks()  # 부모 레이아웃/위치 정보 최신화
    win.update_idletasks()     # 자식 레이아웃/크기 정보 최신화
    px, py = parent.winfo_rootx(), parent.winfo_rooty()     # 부모 좌상단의 화면 절대좌표
    pw, ph = parent.winfo_width(), parent.winfo_height()    # 부모 폭/높이
    ww, wh = win.winfo_width(), win.winfo_height()          # 자식 폭/높이
    # New min/max로 화면 경계를 넘지 않도록 보정(작은 해상도/멀티모니터에서도 안전)
    x = max(0, min(px + (pw - ww) // 2, win.winfo_screenwidth() - ww))  # 계산된 X 좌표 클램프
    y = max(0, min(py + (ph - wh) // 2, win.winfo_screenheight() - wh))  # 계산된 Y 좌표 클램프
    win.geometry(f"+{x}+{y}")  # 크기는 유지하고 위치만 이동

# ─────────────────────────────────────────────────────────
# 데이터 모델                                                 # 도메인 모델 정의
# ─────────────────────────────────────────────────────────
@dataclass  # dataclass로 간단한 데이터 컨테이너 정의
class Todo:  # Todo 데이터 클래스 선언
    """할 일 1건을 표현하는 데이터 모델."""  # 모델 목적/필드 의미 설명
    title: str  # 제목
    start: str  # 시작일(YYYY-MM-DD)
    end: str    # 종료일(YYYY-MM-DD)
    desc: str = ""   # 상세 설명(옵션)
    status: int = 0  # 상태 코드(0=미완,1=진행,2=완료) — UI/DB 공용 코드

    def cycle(self) -> None:  # 상태 순환 메서드 시그니처
        """상태를 다음 단계로 순환(0→1→2→0)."""  # 순환 규칙 설명
        self.status = (self.status + 1) % 3  # 키보드 스페이스/버튼으로 빠른 상태 전환 지원
        # New 리스트에서 '스페이스'로 토글할 때 이 메서드만 호출하면 되어 UI-로직 결합이 느슨해진다.

    def display(self, today: date | None = None) -> str:  # 리스트 표시 문자열 생성 시그니처
        """리스트박스에 표시할 1줄 요약 문자열을 생성(D-DAY 태그 포함)."""  # 반환 포맷 설명
        icon = STATUS_ICON.get(self.status, "☐")  # 상태에 맞는 시각 아이콘
        try:
            d_end = datetime.strptime(self.end, DATE_FMT).date()  # 종료일 파싱
        except Exception:
            # New 날짜 파싱 실패 케이스(유효성 검사가 완벽하지 않을 때를 대비) → 최소정보만 표시
            return f"{icon} {self.start} ~ {self.end} | {self.title}"  # 안전한 폴백 문자열

        today = today or date.today()  # today 미지정 시 시스템 오늘 날짜
        delta = (d_end - today).days   # 종료일까지 남은 일수(D-표기 기준)
        if delta < 0:  # 마감 초과 여부 판단
            tag = "⛔ 지남"            # 마감 초과
        elif delta == 0:  # 당일 마감 여부
            tag = "⚠️ D-DAY"          # 마감 당일
        elif delta <= 3:  # 3일 이내 임박 여부
            tag = f"⏰ D-{delta}"      # 3일 이내 임박
        else:  # 일반 케이스
            tag = f"D-{delta}"         # 일반 D-N 표기
        return f"{icon} [{tag}] {self.start} ~ {self.end} | {self.title}"  # 최종 1줄 표시 문자열
        # New 태그를 통해 리스트만 보고도 긴급도/우선순위를 직관적으로 파악 가능.

# ─────────────────────────────────────────────────────────
# DB 연동                                                     # 영속화 레이어
# ─────────────────────────────────────────────────────────
def _db() -> sql.Connection:  # DB 연결 함수 시그니처
    """SQLite 연결을 열어 반환(컨텍스트 매니저와 함께 사용)."""  # 연결 수명/사용법 설명
    return sql.connect(DB_PATH)  # New 호출 시마다 짧게 열었다가 with 블록 종료 시 자동 닫힘 → 핸들 누수 방지

def init_db() -> None:  # DB 초기화 함수 시그니처
    """앱 최초 실행 시 todos 테이블 생성(존재하면 무시)."""  # 테이블 스키마 개요
    with _db() as con:  # 연결 컨텍스트(오류 시 자동 롤백, 정상 시 커밋)
        # New status 컬럼에 CHECK 제약을 둬서 유효하지 않은 상태 값(0/1/2 외)을 DB 차원에서 차단
        con.execute("""
            CREATE TABLE IF NOT EXISTS todos(
                id     INTEGER PRIMARY KEY AUTOINCREMENT,  -- 내부 PK(표시용 아님)
                title  TEXT NOT NULL,                      -- 제목
                start  TEXT NOT NULL,                      -- 시작일(YYYY-MM-DD)
                end    TEXT NOT NULL,                      -- 종료일(YYYY-MM-DD)
                memo   TEXT DEFAULT '',                    -- 상세설명(예약어 피하려고 'memo' 사용)
                status INTEGER NOT NULL CHECK(status IN (0,1,2)) -- 상태코드(무결성 보장)
            )
        """)  # 스키마 생성 쿼리 실행

def load_all() -> list[Todo]:  # 전체 로드 함수 시그니처
    """DB의 모든 항목을 읽어 메모리(list[Todo])로 반환."""  # 정렬/모델 변환 설명
    init_db()  # 테이블 존재 보장
    with _db() as con:  # 연결 컨텍스트
        rows = con.execute(
            "SELECT title, start, end, memo, status FROM todos ORDER BY id"  # id 순으로 안정 정렬
        ).fetchall()  # New ORDER BY id로 사용자 입력 순서를 그대로 유지 → UX 일관성
    return [Todo(title, start, end, memo, status) for (title, start, end, memo, status) in rows]  # 행→모델 변환
    # New 얇은 변환 계층: SQL 행 → 도메인 모델(Todo). 뷰/로직은 모델만 신경 쓰면 됨.

def save_all(items: list[Todo]) -> None:  # 전량 저장 함수 시그니처
    """현재 메모리 리스트 상태를 DB에 전량 반영(덮어쓰기 방식)."""  # 단순/안전 전략 설명
    with _db() as con:  # 트랜잭션 컨텍스트
        con.execute("DELETE FROM todos")  # New 간단/안전: 순서/상태를 있는 그대로 재기록(소규모 데이터 전제)
        con.executemany(
            "INSERT INTO todos(title, start, end, memo, status) VALUES(?,?,?,?,?)",  # 일괄 삽입 SQL
            [(t.title, t.start, t.end, t.desc, t.status) for t in items],  # 파라미터 시퀀스
        )  # executemany로 성능/가독성을 동시에 확보

# ─────────────────────────────────────────────────────────
# 할 일 추가/편집 팝업(모달)                                  # 입력/편집 UX
# ─────────────────────────────────────────────────────────
class TodoDialog(tk.Toplevel):  # Toplevel 기반 모달 선언
    """할 일 추가/편집을 위한 모달 대화상자."""  # 역할/범위 설명

    def __init__(self, parent: tk.Tk, title: str, prefill: str = "", item: Todo | None = None):  # 생성자 시그니처
        """부모창, 타이틀, 제목 기본값(prefill), 편집 대상(item)을 받아 팝업을 구성."""  # 파라미터 설명
        super().__init__(parent)  # 부모 루트에 부착된 Toplevel 생성
        self.result: Todo | None = None              # 저장 성공 시 채워질 결과(Todo) — 호출자에서 회수
        self._orig_status = item.status if item else 0  # 편집이면 기존 상태를 유지, 신규면 0으로 시작
        # New 편집에서 상태를 초기화하지 않는 이유: 사용자가 이미 진행중/완료 상태를 부여했을 수 있기 때문(의도 존중).

        self.title(title)       # 창 타이틀
        self.transient(parent)  # 부모창 위에 함께 떠 있도록 표시
        self.resizable(False, False)  # 크기 고정(레이아웃 무너짐 방지)
        self.grab_set()         # 모달(닫을 때까지 다른 창 포커스 차단) — 실수 방지

        pad = PAD6  # 공용 여백 프리셋
        today_str = date.today().isoformat()  # 오늘 날짜 문자열

        # 제목 필드
        ttk.Label(self, text="제목").grid(row=0, column=0, sticky="w", **pad)  # 제목 라벨 배치
        self.ent_title = ttk.Entry(self, width=38)  # 제목 입력 박스 생성
        self.ent_title.grid(row=0, column=1, sticky="w", **pad)  # 제목 입력 박스 배치
        self.ent_title.insert(0, prefill or (item.title if item else ""))  # New 빠른입력(prefill) 우선 적용

        # 시작일
        ttk.Label(self, text="시작일 (YYYY-MM-DD)").grid(row=1, column=0, sticky="w", **pad)  # 시작일 라벨
        self.ent_start = ttk.Entry(self, width=20)  # 시작일 입력 박스
        self.ent_start.grid(row=1, column=1, sticky="w", **pad)  # 시작일 입력 배치
        self.ent_start.insert(0, item.start if item else today_str)  # 기본값: 오늘

        # 종료일
        ttk.Label(self, text="종료일 (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", **pad)  # 종료일 라벨
        self.ent_end = ttk.Entry(self, width=20)  # 종료일 입력 박스
        self.ent_end.grid(row=2, column=1, sticky="w", **pad)  # 종료일 입력 배치
        self.ent_end.insert(0, item.end if item else today_str)  # 기본값: 오늘

        # 상세 설명(멀티라인)
        ttk.Label(self, text="상세설명").grid(row=3, column=0, sticky="nw", **pad)  # 상세설명 라벨
        self.txt_desc = tk.Text(self, width=40, height=6)  # 멀티라인 텍스트 박스
        self.txt_desc.grid(row=3, column=1, **pad)  # 상세설명 박스 배치
        if item:  # 편집 모드 여부
            self.txt_desc.insert("1.0", item.desc)  # 편집 시 기존 설명 채움

        # 저장/취소 버튼 행
        btns = ttk.Frame(self)  # 버튼 컨테이너 프레임
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=10)  # 오른쪽 정렬 배치
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="right", padx=6)  # 취소 버튼(창 닫기)
        ttk.Button(btns, text="저장", command=self._on_save).pack(side="right")  # 저장 버튼(검증 후 result 세팅)

        # 팝업 배치/포커스
        self.update_idletasks()     # 내부 위젯 크기 계산을 먼저 반영
        center_over(parent, self)   # 부모 기준 중앙 배치
        self.ent_title.focus_set()  # 첫 입력 포커스는 제목

    def _on_save(self) -> None:  # 저장 콜백 시그니처
        """입력 검증 후 self.result에 Todo를 세팅하고 팝업을 닫는다."""  # 처리 순서 설명
        title = self.ent_title.get().strip()  # 제목 입력 값 추출
        start = self.ent_start.get().strip()  # 시작일 입력 값 추출
        end   = self.ent_end.get().strip()    # 종료일 입력 값 추출
        desc  = self.txt_desc.get("1.0", "end").strip()  # 상세설명 전체 텍스트 추출

        # 1) 제목 필수
        if not title:  # 공백/미입력 검증
            messagebox.showwarning("확인", "제목을 입력하세요.", parent=self)  # 사용자 경고
            self.ent_title.focus_set()  # 포커스 복구
            return  # 저장 중단

        # 2) 날짜 형식 검증(포맷 상수 사용)
        try:
            d1 = parse_date(start)  # 시작일 파싱 시도
        except Exception:
            messagebox.showerror("날짜 오류", "시작일 형식이 잘못되었습니다.\n예: 2025-09-16", parent=self)  # 오류 안내
            self.ent_start.focus_set()  # 포커스 이동
            return  # 저장 중단

        try:
            d2 = parse_date(end)  # 종료일 파싱 시도
        except Exception:
            messagebox.showerror("날짜 오류", "종료일 형식이 잘못되었습니다.\n예: 2025-09-18", parent=self)  # 오류 안내
            self.ent_end.focus_set()  # 포커스 이동
            return  # 저장 중단

        # 3) 논리 검증(종료일 < 시작일 금지)
        if d2 < d1:  # 날짜 논리 검증
            messagebox.showerror("날짜 오류", "종료일은 시작일보다 빠를 수 없습니다.", parent=self)  # 오류 안내
            self.ent_end.focus_set()  # 포커스 이동
            return  # 저장 중단

        # 4) 결과 세팅 후 닫기
        self.result = Todo(title=title, start=start, end=end, desc=desc, status=self._orig_status)  # 결과 구성
        self.destroy()  # 팝업 닫기
        # New 팝업 외부에서는 self.result 존재 여부만 확인해 추가/교체 로직을 간단히 처리한다.

# ─────────────────────────────────────────────────────────
# 메인 앱(노트북 탭: 할 일 / 타이머 / 리포트)                 # 최상위 윈도우/탭 구조
# ─────────────────────────────────────────────────────────
class TodoApp(tk.Tk):  # Tk 루트 윈도우 상속
    """최상위 윈도우: 탭 컨테이너 + 각 탭 로직을 포함."""  # 역할 개요

    def __init__(self) -> None:  # 생성자 시그니처
        """창 생성/크기/탭 구성/DB 로드/초기 렌더링까지 한 번에 수행."""  # 초기화 플로 설명
        super().__init__()  # Tk 루트 초기화
        self.title("갓생살기")  # 창 타이틀 세팅
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()  # 스크린 크기 조회
        x, y = (sw - 580) // 2, (sh - 380) // 2  # 중앙 좌표 계산
        self.geometry(f"580x380+{x}+{y}")  # New 발표/시연에 적합한 소형 고정 크기(가독성 우선)

        # 안전 종료 핸들러: 예약된 after/깜박임 등을 모두 정리
        self.protocol("WM_DELETE_WINDOW", self._on_close)  # 닫기 이벤트 바인딩

        # 애플리케이션 상태(메모리)
        self.todos: list[Todo] = []  # 현재 세션의 할 일 리스트(화면/DB 싱크는 save_all/load_all로 유지)

        # ── 타이머 상태(모노토닉 기반) ──
        self._timer_after_id: str | None = None  # 타이머 틱 루프 예약 ID(after_cancel용)
        self._blink_after_id: str | None = None  # 타임업 깜박임 루프 ID
        self.timer_running: bool = False  # 타이머 동작 여부
        self.timer_total_sec: int = 0     # 총 타이머 시간(초)
        self.timer_warn_sec: int = 30     # 경고 시작 임계(초)
        self.timer_end_mono: float = 0.0  # 단조 시계 기준 종료 목표 시각
        self.timer_remain_sec: int = 0    # 남은 시간(초)
        self._blink_on: bool = False      # 깜박임 토글 상태
        # New time.monotonic() 사용으로 OS 시간 변경/동기화에 따른 튀는 현상 방지.

        # ── 리포트 루프/마일스톤 상태 ──
        self._report_after_id: str | None = None  # 리포트 자동 갱신 루프 ID(after_cancel용)
        self._last_rate: float = 0.0              # 이전 완료율(마일스톤 돌파 감지)
        self._report_booted: bool = False         # New 첫 갱신 여부(앱 시작 직후 컨페티 오발 방지)

        # 탭 컨테이너
        nb = ttk.Notebook(self)  # 노트북 위젯 생성
        nb.pack(expand=True, fill="both", padx=10, pady=10)  # 창 내부에 배치

        # 탭 생성(성적 탭은 제거)
        self.tab_todo   = ttk.Frame(nb)  # 할 일 탭 프레임
        self.tab_timer  = ttk.Frame(nb)  # 타이머 탭 프레임
        self.tab_report = ttk.Frame(nb)  # 리포트 탭 프레임
        nb.add(self.tab_todo, text="할 일")  # 탭 추가(할 일)
        nb.add(self.tab_timer, text="타이머")  # 탭 추가(타이머)
        nb.add(self.tab_report, text="리포트")  # 탭 추가(리포트)
        # New 사용자가 바로 리포트를 확인할 수 있도록 탭 순서를 단순화(3개).

        # 각 탭 UI 구성
        self._build_todo_tab()  # 할 일 탭 구성
        self._build_timer_tab()  # 타이머 탭 구성
        self._build_report_tab()  # 리포트 탭 구성

        # DB → 메모리 → UI 초기 렌더
        init_db()  # 테이블 보장
        self.todos = load_all()  # DB로부터 로드
        self.refresh_list()  # New 내부에서 refresh_report()도 호출하여 첫 화면부터 일관된 상태 표시

    # ─────────────────────────────────────────────────────────
    # [할 일] 탭 UI                                            # ToDo 탭 구성
    # ─────────────────────────────────────────────────────────
    def _build_todo_tab(self) -> None:  # 할 일 탭 빌드 함수
        """할 일 탭의 입력/버튼/리스트 UI를 구성."""  # 구성 요소 설명
        top = ttk.Frame(self.tab_todo)  # 상단 입력/버튼 컨테이너
        top.pack(fill="x", padx=10, pady=10)  # 가로 채움 배치

        # 빠른 제목 입력 + Enter로 즉시 추가
        self.quick_entry = ttk.Entry(top)  # 제목 한 줄 입력 위젯
        self.quick_entry.pack(side="left", fill="x", expand=True)  # 좌측부터 확장 배치
        self.quick_entry.focus()  # 시작 시 포커스 부여
        self.quick_entry.bind("<Return>", lambda e: self.add_todo())  # New 텍스트 입력 → Enter 한 번으로 등록

        # 기본 버튼들(CRUD + 상태전환)
        ttk.Button(top, text="추가",   command=self.add_todo).pack(side="left", padx=6)  # 추가 버튼
        ttk.Button(top, text="편집",   command=self.edit_selected).pack(side="left", padx=6)  # 편집 버튼
        ttk.Button(top, text="삭제",   command=self.delete_selected).pack(side="left", padx=6)  # 삭제 버튼
        ttk.Button(top, text="상태전환 (☐→⏳→✔)", command=self.cycle_status_selected).pack(side="left", padx=6)  # 상태 순환 버튼

        # 리스트 + 스크롤
        mid = ttk.Frame(self.tab_todo)  # 리스트/스크롤 컨테이너
        mid.pack(fill="both", expand=True, padx=10, pady=5)  # 남는 공간 채우기

        self.listbox = tk.Listbox(mid, height=10, selectmode="extended")  # New 다중 선택으로 일괄 삭제/상태전환 가능
        self.listbox.pack(side="left", fill="both", expand=True)  # 리스트 박스 배치

        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)  # 세로 스크롤바
        scroll.pack(side="left", fill="y")  # 스크롤바 배치
        self.listbox.config(yscrollcommand=scroll.set)  # 리스트와 스크롤바 연동

        # 단축키(생산성)
        self.listbox.bind("<Delete>", lambda e: self.delete_selected())  # Del: 삭제
        self.listbox.bind("<space>",  self._on_space_toggle)             # Space: 상태 토글
        self.listbox.bind("<Double-Button-1>", self.show_details)        # 더블클릭: 상세 보기

    # ─────────────────────────────────────────────────────────
    # [타이머] 탭 UI                                            # 발표 타이머 UI
    # ─────────────────────────────────────────────────────────
    def _build_timer_tab(self) -> None:  # 타이머 탭 빌드 함수
        """발표 타이머 입력/컨트롤/피드백 UI 구성."""  # 구성 요소 설명
        top = ttk.Frame(self.tab_timer)  # 상단 입력/컨트롤 컨테이너
        top.pack(fill="x", **PAD8)  # 가로 채움

        # 시간/임계값 입력
        ttk.Label(top, text="발표 시간(분)").pack(side="left")  # 분 입력 라벨
        self.ent_minutes = ttk.Entry(top, width=6)  # 분 입력 박스
        self.ent_minutes.pack(side="left", padx=(4, 12))  # 라벨과 간격
        self.ent_minutes.insert(0, "5")  # 기본 5분

        ttk.Label(top, text="경고 임계(초)").pack(side="left")  # 경고 임계 라벨
        self.ent_warn = ttk.Entry(top, width=6)  # 경고 임계 입력 박스
        self.ent_warn.pack(side="left", padx=(4, 12))  # 간격
        self.ent_warn.insert(0, "30")  # 기본 30초

        # 컨트롤 버튼(상태 흐름에 따라 활성/비활성화)
        self.btn_start = ttk.Button(top, text="시작",     command=self.start_timer)  # 시작 버튼
        self.btn_pause = ttk.Button(top, text="일시정지", command=self.pause_resume_timer, state="disabled")  # 일시정지 버튼
        self.btn_reset = ttk.Button(top, text="초기화",   command=self.reset_timer,       state="disabled")  # 초기화 버튼
        self.btn_start.pack(side="left", padx=4)  # 버튼 배치
        self.btn_pause.pack(side="left", padx=4)  # 버튼 배치
        self.btn_reset.pack(side="left", padx=4)  # 버튼 배치

        # 중앙: 남은 시간 + 진행률 바
        mid = ttk.Frame(self.tab_timer)  # 중앙 표시 영역
        mid.pack(expand=True, fill="both", **PAD8)  # 남는 공간 채움
        self.lbl_timer = tk.Label(mid, text="00:00", font=("Helvetica", 36, "bold"))  # 남은 시간 라벨
        self.lbl_timer.pack(pady=10)  # 여백
        self.pb_timer  = ttk.Progressbar(mid, orient="horizontal", mode="determinate", length=360)  # 진행률 바
        self.pb_timer.pack(fill="x", padx=20, pady=10)  # 바 배치

        # 하단: 사용 팁
        bottom = ttk.Frame(self.tab_timer)  # 하단 프레임
        bottom.pack(fill="x", **PAD8)  # 가로 채움
        ttk.Label(
            bottom,
            text="Tip) 남은 시간이 임계값 이하로 떨어지면 주황색, 0이 되면 빨간색으로 깜박이며 종료를 알립니다."
        ).pack(anchor="w")  # 좌측 정렬 라벨

    # ─────────────────────────────────────────────────────────
    # [리포트] 탭 UI (텍스트 KPI + 도넛 + 스택바 + 주간 히트맵)  # 대시보드 구성
    # ─────────────────────────────────────────────────────────
    def _build_report_tab(self) -> None:  # 리포트 탭 빌드 함수
        """리포트 탭의 KPI 텍스트/간단 시각화 위젯을 구성."""  # 탭의 목적/구성 설명
        frm = ttk.Frame(self.tab_report)  # 루트 컨테이너 프레임
        frm.pack(fill="both", expand=True, padx=12, pady=12)  # 프레임 배치

        ttk.Label(frm, text="📊 주간 성과 리포트", font=("Helvetica", 14, "bold")
                 ).pack(anchor="w", pady=(0, 8))  # 제목 라벨(크게/볼드)
        
        # New 상단 영역: 좌측 도넛, 우측 텍스트 KPI 블럭으로 2열 레이아웃을 구성
        top = ttk.Frame(frm)  # 상단 행 컨테이너
        top.pack(fill="x")  # 가로 채움

        # 도넛 게이지(완료율 핵심 KPI)
        self.cnv_ring = tk.Canvas(top, width=160, height=160, highlightthickness=0)  # 도넛 캔버스
        self.cnv_ring.pack(side="left", padx=(0, 16))  # 좌측 배치, 우측 여백 확보

        # 오른쪽 텍스트 KPI 묶음
        right = ttk.Frame(top)  # 우측 KPI 컨테이너
        right.pack(side="left", fill="both", expand=True)  # 남는 공간 채움
        self.lbl_rate   = ttk.Label(right, text="완료율 0.0%", font=("Helvetica", 12, "bold"))  # 완료율 굵은 라벨
        self.lbl_rate.pack(anchor="w", pady=(4, 6))  # 라벨 배치

        self.var_avg    = tk.StringVar(value="평균 기간: 0.0일")  # 평균 기간 바인딩 변수
        self.var_soon   = tk.StringVar(value="마감 임박: 0건")    # 임박 건수 바인딩 변수
        self.var_over   = tk.StringVar(value="지남: 0건")  # 지남 건수 바인딩 변수
        self.var_counts = tk.StringVar(value="상태 구성: 미완 0 · 진행 0 · 완료 0")  # 상태 구성 바인딩 변수

        ttk.Label(right, textvariable=self.var_avg   ).pack(anchor="w")  # 평균 표기 라벨
        ttk.Label(right, textvariable=self.var_soon  ).pack(anchor="w")  # 임박 표기 라벨
        ttk.Label(right, textvariable=self.var_over  ).pack(anchor="w")  # 지남 표기 라벨
        ttk.Label(right, textvariable=self.var_counts).pack(anchor="w", pady=(2, 0))  # 상태 구성 라벨
        # New 숫자 + 설명을 같이 표기해 '읽히는 KPI'를 지향(그래프 해석시간을 줄임).

        # 상태 비중 스택바
        self.cnv_stack = tk.Canvas(frm, height=22, highlightthickness=0)  # 스택바 캔버스
        self.cnv_stack.pack(fill="x", pady=(10, 6))  # 가로 채움 + 상하 여백

        # 이번 주 마감 히트맵(월~일)
        self.cnv_heat = tk.Canvas(frm, height=56, highlightthickness=0)  # 히트맵 캔버스
        self.cnv_heat.pack(fill="x")  # 가로 채움

        ttk.Label(frm, text="※ 5초마다 자동 갱신 · 리스트 변경 시 즉시 반영", foreground="#666"
                 ).pack(anchor="w", pady=(8, 0))  # 안내 라벨(보조 색)
        # New 실시간성(자동/즉시)을 명시해 “살아있는 리포트” 느낌 강화.

    # ─────────────────────────────────────────────────────────
    # 공통 동작: 선택/리스트 갱신/저장                           # 공통 헬퍼
    # ─────────────────────────────────────────────────────────
    def _selected_indices(self) -> tuple[int, ...] | None:  # 선택 인덱스 획득 함수
        """리스트박스에서 사용자가 선택한 항목 인덱스 튜플을 반환(없으면 경고 후 None)."""  # 반환/에러 경고 설명
        sel = self.listbox.curselection()  # 현재 선택된 인덱스들
        if not sel:  # 선택 없음
            messagebox.showwarning("확인", "항목을 선택하세요.", parent=self)  # 사용자 경고
            return None  # None 반환
        return sel  # 선택 인덱스 튜플 반환
        # New selectmode="extended"이므로 여러 항목을 한 번에 조작 가능(삭제/상태전환).

    def refresh_list(self) -> None:  # 리스트 리프레시 함수
        """현재 self.todos를 리스트박스에 반영하고, 리포트도 함께 갱신."""  # 처리 내용 설명
        self.listbox.delete(0, tk.END)  # 기존 내용 초기화
        if self.todos:  # 항목 존재 시
            self.listbox.insert(tk.END, *[t.display() for t in self.todos])  # display()는 D-DAY 태그 포함 문자열
        self.refresh_report()  # New 리스트 변경 → 리포트 즉시 갱신(행동과 피드백의 연결)

    def _save(self) -> None:  # 저장 함수
        """현재 메모리 리스트(self.todos)를 DB에 저장(덮어쓰기 방식)."""  # 저장 전략 설명
        save_all(self.todos)  # 덮어쓰기 저장 호출
        # New 모든 조작 흐름은 '저장 → 리스트 갱신 → 리포트 갱신'으로 통일하여 화면/DB 싱크를 보장.

    # ─────────────────────────────────────────────────────────
    # 사용자 액션: 추가/편집/삭제/상태전환/상세보기               # CRUD/토글/뷰
    # ─────────────────────────────────────────────────────────
    def add_todo(self) -> None:  # 추가 핸들러
        """새 할 일을 추가(빠른입력칸 내용으로 제목 prefill)."""  # UX 흐름 설명
        prefill = self.quick_entry.get().strip()  # prefill 텍스트 추출
        dlg = TodoDialog(self, "할 일 추가", prefill=prefill)  # 추가 팝업 생성
        self.wait_window(dlg)       # 모달 완료 대기
        if dlg.result:              # 저장되었으면
            self.todos.append(dlg.result)  # 리스트에 추가
            self._save()  # DB에 반영
            self.refresh_list()  # UI 갱신

    def edit_selected(self) -> None:  # 편집 핸들러
        """선택한 첫 항목을 편집 팝업으로 열고 저장 시 교체."""  # 동작 설명
        sel = self._selected_indices()  # 선택 확인
        if not sel:  # 무선택
            return  # 조용히 종료
        idx = sel[0]  # 첫 선택 인덱스
        dlg = TodoDialog(self, "할 일 편집", item=self.todos[idx])  # 편집 모달
        self.wait_window(dlg)  # 대기
        if dlg.result:  # 저장됨
            self.todos[idx] = dlg.result  # 교체
            self._save()  # 저장
            self.refresh_list()  # 갱신

    def delete_selected(self) -> None:  # 삭제 핸들러
        """선택된 여러 항목을 삭제(뒤에서부터 지워 인덱스 당김 문제 방지)."""  # 구현 상세 설명
        sel = self._selected_indices()  # 선택 확인
        if not sel:  # 무선택
            return  # 종료
        if not messagebox.askyesno("삭제 확인", f"선택한 {len(sel)}개 항목을 정말 삭제할까요?", parent=self):  # 사용자 확인
            return  # 취소
        for i in reversed(sel):  # New 뒤에서부터 지우면 앞쪽 인덱스의 안전성이 보장됨
            del self.todos[i]  # 리스트에서 제거
        self._save()  # 저장
        self.refresh_list()  # 갱신

    def cycle_status_selected(self) -> None:  # 상태 순환 핸들러
        """선택된 모든 항목의 상태를 0→1→2→0 순환."""  # 동작 설명
        sel = self._selected_indices()  # 선택 확인
        if not sel:  # 무선택
            return  # 종료
        for i in sel:  # 선택 항목 순회
            self.todos[i].cycle()  # 상태 순환 실행
        self._save()  # 저장
        self.refresh_list()  # 갱신

    def _on_space_toggle(self, _e) -> str:  # 스페이스 토글 바인딩
        """스페이스바로 상태 순환(리스트박스 기본 스페이스 동작은 차단)."""  # 기본 동작 차단 이유 설명
        self.cycle_status_selected()  # 상태 순환 호출
        return "break"  # New Tk의 기본 스페이스 동작(선택 이동)을 막지 않으면 UX가 혼란스러워짐

    def show_details(self, _e=None) -> None:  # 상세보기 핸들러
        """선택된 첫 항목의 상세 정보(읽기 전용) 팝업을 표시."""  # 표시 내용 설명
        sel = self._selected_indices()  # 선택 확인
        if not sel:  # 무선택
            return  # 종료
        t = self.todos[sel[0]]  # 대상 항목
        icon = STATUS_ICON.get(t.status, "☐")  # 상태 아이콘
        msg = (  # 상세 메시지 문자열
            f"제목: {t.title}\n"
            f"기간: {t.start} ~ {t.end}\n"
            f"상태: {icon} {STATUS_TEXT.get(t.status,'')}\n\n"
            f"상세설명:\n{t.desc or '(없음)'}"
        )  # 메시지 구성 완료
        messagebox.showinfo("할 일 상세", msg, parent=self)  # 정보 팝업 표시

    # ─────────────────────────────────────────────────────────
    # 타이머 로직(모노토닉 기반, 드리프트 최소화)                 # 타이머 엔진
    # ─────────────────────────────────────────────────────────
    def _format_sec(self, s: int) -> str:  # 포맷 함수 시그니처
        """정수 초를 'MM:SS' 형식 문자열로 변환(음수 방지/0 패딩 포함)."""  # 포맷 규칙 설명
        s = max(0, int(s))  # 음수 방지 및 정수화
        m, ss = divmod(s, 60)  # 분/초 분리
        return f"{m:02d}:{ss:02d}"  # 2자리 0패딩 포맷

    def _set_timer_controls_running(self, running: bool) -> None:  # 컨트롤 상태 전환 함수
        """타이머 실행 여부에 따라 버튼/입력 상태를 전환(오조작 방지)."""  # UI 상태 머신 설명
        if running:  # 실행 중
            self.btn_start.config(state="disabled")  # 시작 비활성화
            self.btn_pause.config(state="normal", text="일시정지")  # 일시정지 활성
            self.btn_reset.config(state="normal")  # 초기화 활성
            self.ent_minutes.config(state="disabled")  # 분 입력 잠금
            self.ent_warn.config(state="disabled")  # 경고 입력 잠금
        else:  # 정지 상태
            self.btn_start.config(state="normal")  # 시작 활성화
            self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 비활성
            self.btn_reset.config(state="disabled")  # 초기화 비활성
            self.ent_minutes.config(state="normal")  # 분 입력 허용
            self.ent_warn.config(state="normal")  # 경고 입력 허용

    def _stop_tick_loop(self) -> None:  # 타이머 틱 루프 중지
        """예약된 타이머 틱(after) 루프를 안전하게 취소."""  # 예외 안전성 설명
        if self._timer_after_id is not None:  # 예약 존재 검사
            try:
                self.after_cancel(self._timer_after_id)  # 예약 취소
            except Exception:
                pass  # New 이미 만료/취소된 ID일 수 있으므로 예외를 무시해 안전성 확보
            self._timer_after_id = None  # 상태 클리어

    def _stop_blink(self) -> None:  # 깜박임 중지
        """타임업 깜박임 루프를 중지하고 글자색을 원래대로 복원."""  # 시각 상태 복원 설명
        if self._blink_after_id is not None:  # 예약 존재 검사
            try:
                self.after_cancel(self._blink_after_id)  # 예약 취소
            except Exception:
                pass  # 예외 무시
            self._blink_after_id = None  # 상태 클리어
        self._blink_on = False  # 토글 리셋
        self.lbl_timer.config(fg="black")  # 글자색 복원

    def _start_blink(self) -> None:  # 깜박임 시작
        """타임업 시 빨강/검정을 교대로 깜박이며 종료를 강하게 알림."""  # 사용자 주목 유도 목적
        self._blink_on = not self._blink_on  # 토글 반전
        self.lbl_timer.config(fg=("red" if self._blink_on else "black"))  # 색상 토글 적용
        self._blink_after_id = self.after(450, self._start_blink)  # New 0.45초 간격 → 자극은 주되 과도하지 않게

    def start_timer(self) -> None:  # 타이머 시작 핸들러
        """입력값 검증 후 타이머를 시작하고 주기 틱 루프를 가동."""  # 단계별 처리 설명
        self._stop_tick_loop()  # 기존 루프 중지
        self._stop_blink()  # 기존 깜박 중지
        # 1) 분 입력(실수 허용)
        try:
            minutes = float(self.ent_minutes.get().strip())  # 분 입력 파싱
        except Exception:
            messagebox.showerror("입력 오류", "발표 시간(분)을 숫자로 입력하세요. 예: 5 또는 7.5", parent=self)  # 오류 안내
            self.ent_minutes.focus_set()  # 포커스 복구
            return  # 중단
        if minutes <= 0:  # 최소값 검증
            messagebox.showerror("입력 오류", "발표 시간(분)은 0보다 커야 합니다.", parent=self)  # 오류 안내
            self.ent_minutes.focus_set()  # 포커스 복구
            return  # 중단
        # 2) 경고 임계(정수)
        try:
            warn = int(self.ent_warn.get().strip())  # 임계 파싱
        except Exception:
            messagebox.showerror("입력 오류", "경고 임계(초)를 정수로 입력하세요. 예: 30", parent=self)  # 오류 안내
            self.ent_warn.focus_set()  # 포커스 복구
            return  # 중단
        if warn < 1:  # 최소 1초 보장
            messagebox.showerror("입력 오류", "경고 임계(초)는 1초 이상이어야 합니다.", parent=self)  # 오류 안내
            self.ent_warn.focus_set()  # 포커스 복구
            return  # 중단

        # 3) 내부 상태 셋업
        total_sec = int(round(minutes * 60))  # 분→초 환산
        self.timer_total_sec = total_sec  # 총 시간 저장
        self.timer_warn_sec  = min(warn, max(1, total_sec - 1))  # New 경고 임계가 총시간 이상이 되지 않게 보정
        self.timer_running   = True  # 실행 플래그
        self.timer_end_mono  = time.monotonic() + self.timer_total_sec  # 종료 목표 시각
        self.timer_remain_sec = self.timer_total_sec  # 남은 시간 초기화

        # 4) UI 초기화
        self.lbl_timer.config(text=self._format_sec(self.timer_remain_sec), fg="black")  # 초기 라벨/색
        self.pb_timer.config(maximum=self.timer_total_sec, value=0)  # 진행 바 초기화
        self._set_timer_controls_running(True)  # 컨트롤 상태 전환

        # 5) 틱 루프 시작
        self._tick_update()  # 주기 업데이트 가동

    def pause_resume_timer(self) -> None:  # 일시정지/계속 토글
        """일시정지/계속 토글 — 남은 시간을 저장/복구하여 정확도 유지."""  # 로직 요약
        if not self.timer_running:  # 현재 정지 상태면
            # 계속
            if self.timer_remain_sec <= 0:  # 이미 완료된 타이머면 무시
                return  # 종료
            self.timer_end_mono = time.monotonic() + self.timer_remain_sec  # 목표 시각 재설정
            self.timer_running = True  # 실행 재개
            self.btn_pause.config(text="일시정지")  # 버튼 라벨 변경
            self._tick_update()  # 틱 루프 재가동
            return  # 반환

        # 일시정지
        now_mono = time.monotonic()  # 현재 단조 시각
        remain = max(0, int(math.ceil(self.timer_end_mono - now_mono)))  # 남은 초 계산
        self.timer_remain_sec = remain  # 상태 반영
        self.timer_running = False  # 정지
        self.btn_pause.config(text="계속")  # 라벨 변경
        self._stop_tick_loop()  # 루프 중지

    def reset_timer(self) -> None:  # 초기화 핸들러
        """타이머를 완전히 초기 상태로 되돌림(루프/깜박임 포함)."""  # 리셋 범위 설명
        self.timer_running = False  # 정지
        self.timer_total_sec = 0  # 총 시간 리셋
        self.timer_remain_sec = 0  # 남은 시간 리셋
        self.timer_end_mono = 0.0  # 목표 시각 리셋
        self._stop_tick_loop()  # 틱 루프 중지
        self._stop_blink()  # 깜박 중지
        self.lbl_timer.config(text="00:00", fg="black")  # 라벨 리셋
        self.pb_timer.config(maximum=1, value=0)  # 바 리셋
        self._set_timer_controls_running(False)  # 컨트롤 비활성화

    def _on_time_up(self) -> None:  # 타임업 처리
        """남은 시간이 0이 되었을 때 타임업 처리(소리+색+깜박으로 강한 신호)."""  # 사용자 알림 강화
        self.timer_running = False  # 정지
        self._stop_tick_loop()  # 루프 중지
        self.lbl_timer.config(text="00:00", fg="red")  # 빨간색 0초
        self.pb_timer.config(value=self.timer_total_sec)  # 진행 바 끝까지
        try:
            self.bell()  # 시스템 벨
        except Exception:
            pass  # 일부 환경에서 시스템 벨 실패 가능 → 조용히 무시
        self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 버튼 비활성화
        self._start_blink()  # 깜박임 시작

    def _tick_update(self) -> None:  # 주기 틱 함수
        """200ms 간격으로 남은 시간을 갱신하고, 경고/진행률/종료를 처리."""  # 주기/역할 설명
        if not self.timer_running:  # 정지 상태면
            return  # 갱신 중단
        now_mono = time.monotonic()  # 현재 단조 시각
        remain = int(max(0, math.ceil(self.timer_end_mono - now_mono)))  # 남은 초 계산(올림)
        self.timer_remain_sec = remain  # 상태 반영
        self.lbl_timer.config(text=self._format_sec(remain))  # 라벨 갱신
        if remain == 0:  # 종료 시점
            self._on_time_up()  # 타임업 처리
            return  # 루프 종료
        elif remain <= self.timer_warn_sec:  # 경고 구간 진입
            self.lbl_timer.config(fg="orange")  # 주황색 표시
        else:  # 정상 구간
            self.lbl_timer.config(fg="black")  # 검정 표시
        done = self.timer_total_sec - remain  # 경과 초
        self.pb_timer.config(value=done)  # 진행 바 갱신
        self._timer_after_id = self.after(200, self._tick_update)  # 다음 틱 예약
        # New 200ms면 충분히 부드럽고, CPU 소모도 과하지 않은 타협값.

    # ─────────────────────────────────────────────────────────
    # 리포트 로직(집계/시각화/오토루프/마일스톤 컨페티)            # 대시보드 엔진
    # ─────────────────────────────────────────────────────────
    def _stop_report_loop(self) -> None:  # 리포트 루프 중지
        """리포트 자동 갱신(after) 예약이 있으면 취소하여 중복 루프를 방지."""  # 중복 방지 설명
        if self._report_after_id:  # 예약 존재 검사
            try:
                self.after_cancel(self._report_after_id)  # 예약 취소
            except Exception:
                pass  # 예외 무시
            self._report_after_id = None  # 상태 클리어
        # New 리스트 갱신/탭 초기화 등에서 refresh_report를 다시 부를 때 중복 예약을 예방.

    def calc_report_stats(self) -> dict:  # 집계 함수
        """self.todos를 집계해 리포트용 요약 지표를 계산."""  # 지표 정의 설명
        total = len(self.todos)  # 총 개수
        if total == 0:  # 비어있을 때
            # New 빈 리스트일 때도 UI가 안정적으로 렌더되도록 0/빈 배열을 반환
            return {"rate": 0.0, "avg_days": 0.0, "soon": 0, "overdue": 0,
                    "counts": (0, 0, 0), "week_bins": [0]*7}  # 기본 구조 반환

        # 상태별 개수
        cnt0 = sum(1 for t in self.todos if t.status == 0)  # 미완
        cnt1 = sum(1 for t in self.todos if t.status == 1)  # 진행
        cnt2 = sum(1 for t in self.todos if t.status == 2)  # 완료
        rate = round(cnt2 / total * 100, 1)                 # 완료율(소수 1자리)

        today = date.today()  # 오늘 날짜
        start_week = today - timedelta(days=today.weekday())  # New 이번 주의 월요일(week anchor)
        soon = 0       # 3일 이내 마감(미완/진행만)
        overdue = 0    # 마감이 지난 항목(미완/진행만)
        durations: list[int] = []  # (종료-시작) 일수
        week_bins = [0]*7          # 월(0)~일(6) 마감 건수

        for t in self.todos:  # 항목 순회
            try:
                d1 = parse_date(t.start).date()  # 시작일 파싱
                d2 = parse_date(t.end).date()    # 종료일 파싱
            except Exception:
                continue  # 잘못된 날짜는 스킵(리포트가 전체 실패로 이어지지 않도록 보호)

            if d2 >= d1:  # 음수 기간 방지
                durations.append((d2 - d1).days)  # 기간 리스트에 추가
            delta = (d2 - today).days  # 오늘 기준 잔여 일수
            if t.status != 2 and 0 <= delta <= 3:  # 완료 제외 + 3일 이내
                soon += 1  # 임박++
            if t.status != 2 and delta < 0:  # 완료 제외 + 마감 초과
                overdue += 1  # 지남++
            off = (d2 - start_week).days  # 이번주 offset
            if 0 <= off < 7:  # 이번 주 범위 내
                week_bins[off] += 1  # 해당 요일 카운트

        avg_days = round(sum(durations)/len(durations), 1) if durations else 0.0  # 평균 기간 계산
        return {"rate": rate, "avg_days": avg_days, "soon": soon, "overdue": overdue,
                "counts": (cnt0, cnt1, cnt2), "week_bins": week_bins}  # 집계 결과 반환
        # New 임박/지남은 “완료되지 않은 항목”만 대상으로 계산 → 관리 포인트만 부각.

    def refresh_report(self) -> None:  # 리포트 갱신 루틴
        """리포트 텍스트/KPI와 시각화를 갱신하고, 5초 후 다시 자신을 예약."""  # 오토루프 설명
        self._stop_report_loop()  # 중복 루프 방지
        s = self.calc_report_stats()  # 집계 수행

        # 텍스트 KPI
        self.lbl_rate.config(text=f"완료율 {s['rate']:.1f}%")  # 완료율 표시
        self.var_avg.set (f"평균 기간: {s['avg_days']}일")  # 평균 기간 표시
        self.var_soon.set(f"마감 임박: {s['soon']}건")  # 임박 표시
        self.var_over.set(f"지남: {s['overdue']}건")  # 지남 표시
        c0, c1, c2 = s["counts"]  # 상태 튜플 언팩
        self.var_counts.set(f"상태 구성: 미완 {c0} · 진행 {c1} · 완료 {c2}")  # 상태 구성 표시

        # 색상 피드백(텍스트/도넛 색 규칙을 통일)
        col = self._rate_color(s["rate"])  # 규칙 기반 색상
        self.lbl_rate.config(foreground=col)  # 레이블 색상 적용

        # 시각화(도넛 애니메이션, 상태 스택바, 주간 히트맵)
        self._animate_ring_to(s["rate"])   # New 미세 변화(<0.2%)는 즉시, 그 외는 보간 애니
        self._draw_stack(s["counts"])  # 스택바 렌더
        self._draw_heat(s["week_bins"])  # 히트맵 렌더

        # 마일스톤 컨페티(첫 갱신 제외, 50/80/100 상향 돌파 시)
        prev = self._last_rate  # 이전 완료율
        if self._report_booted and any(prev < m <= s["rate"] for m in (50, 80, 100)):  # 마일스톤 돌파 판단
            self._burst_confetti(duration=800)  # 0.8초 짧은 보상 애니메이션
        self._report_booted = True  # 첫 갱신 이후로 전환
        self._last_rate = s["rate"]  # 현재 완료율 저장

        # 다음 자동 갱신 예약(5초)
        self._report_after_id = self.after(5000, self.refresh_report)  # 자기 재호출 예약
        # New 리스트 변동이 잦아도 비용이 낮은 집계/드로잉만 수행 → UI 반응성 유지.

    # ─────────────────────────────────────────────────────────
    # New 색상/도넛/스택바/히트맵/컨페티 드로잉 유틸              # 시각화 유틸 모듈
    # ─────────────────────────────────────────────────────────
    def _rate_color(self, rate: float) -> str:  # 색상 결정 함수
        """New 완료율(%)에 따른 시그널 색을 반환: <50 빨강, <80 주황, 그 외 초록."""  # 색상 구간 규칙
        return "#e53935" if rate < 50 else "#fb8c00" if rate < 80 else "#43a047"  # 삼항으로 간결 처리

    def _draw_ring(self, rate: float) -> None:  # 도넛 렌더 함수
        """완료율(0~100)을 도넛 형태로 그린다(베이스 링+진행 아크+중앙 퍼센트)."""  # 요소 구성 설명
        c = self.cnv_ring  # 대상 캔버스 단축 참조
        c.delete("all")  # 이전 프레임 지우기
        cx, cy, r, th = 80, 80, 70, 14  # 중심/반지름/두께 파라미터
        # 베이스(회색 링)
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#e6e6e6", width=th)  # 바탕 링
        # 진행 아크(12시 방향에서 시계방향으로 채움)
        col = self._rate_color(rate)  # 비율에 따른 색상
        extent = 360 * (rate / 100)  # 각도(0~360)
        c.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-extent,
                     style="arc", width=th, outline=col)  # 진행 아크(시계방향)
        # 중앙 퍼센트 라벨
        c.create_text(cx, cy, text=f"{rate:.1f}%", font=("Helvetica", 16, "bold"))  # 퍼센트 텍스트

    def _animate_ring_to(self, target: float) -> None:  # 도넛 애니 함수
        """완료율 변화량에 따라 도넛을 부드럽게 보간 렌더(아주 작으면 즉시 반영)."""  # 애니 정책 설명
        start = getattr(self, "_ring_anim_start", self._last_rate)  # 시작값(없으면 마지막 완료율)
        if abs(target - start) < 0.2:     # New 0.2% 미만 변화는 눈에 안 띄므로 바로 그림
            self._draw_ring(target)  # 즉시 렌더
            self._ring_anim_start = target  # 상태 저장
            return  # 종료
        steps = max(8, int(abs(target - start) // 2))  # 변화폭에 비례한 스텝 수(하한 8)
        def step(i=0):  # 내부 스텝 함수
            val = start + (target - start) * i / steps  # 선형 보간
            self._draw_ring(val)  # 중간값 렌더
            if i < steps:  # 다음 스텝 존재
                self.after(16, step, i + 1)  # 약 60fps
            else:  # 마지막 스텝
                self._ring_anim_start = target  # 상태 저장
        step()  # 애니 시작

    def _draw_stack(self, counts: tuple[int, int, int]) -> None:  # 스택바 렌더 함수
        """상태 구성(미완/진행/완료)을 가로 스택바로 시각화."""  # 입력/표현 설명
        c = self.cnv_stack  # 대상 캔버스
        c.delete("all")  # 초기화
        w = c.winfo_width() or 400  # 현재 폭(레이아웃 초기엔 0일 수 있어 기본값 400)
        h = 22  # 고정 높이
        total = max(1, sum(counts))  # 0분모 방지
        colors = ["#90a4ae", "#fb8c00", "#43a047"]  # 미완/진행/완료 색
        x = 0  # 누적 X 시작점
        for n, col in zip(counts, colors):  # 구간 렌더
            seg = int(w * n / total)  # 구간 길이
            c.create_rectangle(x, 0, x + seg, h, fill=col, width=0)  # 구간 박스
            x += seg  # 다음 시작점 이동
        c.create_rectangle(0, 0, w, h, outline="#d0d0d0")  # 외곽선으로 바 경계 명확화

    def _draw_heat(self, bins: list[int]) -> None:  # 히트맵 렌더 함수
        """이번 주(월~일) 마감 건수를 연녹→진녹 그라데이션으로 히트맵 표시."""  # 색/의미 설명
        c = self.cnv_heat  # 대상 캔버스
        c.delete("all")  # 초기화
        w = c.winfo_width() or 420  # 현재 폭(레이아웃 초기 보정)
        h = 56  # 고정 높이
        cell = w // 7  # 하루당 칸 폭
        pad = 4  # 칸 내부 패딩
        days = ["월", "화", "수", "목", "금", "토", "일"]  # 요일 라벨
        mx = max(bins) or 1  # 최대값 0일 때 0으로 나누기 방지
        def blend(a: str, b: str, t: float) -> str:  # 색 보간 유틸
            """hex 색상 a→b 사이를 t(0~1)로 보간하여 hex로 반환."""  # 보간 규칙 설명
            ah, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)  # 색상 a 분해
            bh, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)  # 색상 b 분해
            ih, ig, ib = int(ah + (bh - ah) * t), int(ag + (bg - ag) * t), int(ab + (bb - ab) * t)  # 보간
            return f"#{ih:02x}{ig:02x}{ib:02x}"  # 보간 결과 hex
        for i, v in enumerate(bins):  # 7일 순회
            x0, x1 = i * cell + pad, (i + 1) * cell - pad  # X 영역
            y0, y1 = pad, h - 18  # Y 영역
            col = blend("#e8f5e9", "#1b5e20", v / mx)  # 연녹→진녹 매핑
            c.create_rectangle(x0, y0, x1, y1, fill=col, outline="#cfd8dc")  # 칸 렌더
            c.create_text((x0 + x1) // 2, h - 8, text=days[i], font=("Helvetica", 9))  # 요일 라벨
        # New 수치 라벨 없이도 '농도'로 피크 요일을 직관적으로 파악 가능.

    def _burst_confetti(self, n: int = 28, duration: int = 800) -> None:  # 컨페티 연출 함수
        """New 도넛 캔버스 위에서만 0.8초간 컨페티를 떨어뜨려(오버레이 없이) 시각적 보상을 제공."""  # 목적/범위 설명
        c = self.cnv_ring  # 투명 오버레이를 쓰지 않기 위해 대상 캔버스(도넛)에 직접 그림
        import random as _r, time as _t  # 지역 임포트(전역 네임스페이스 오염 방지)
        W = c.winfo_width() or 160  # 캔버스 폭(초기값 보정)
        parts = []  # 파편 객체 ID 보관 리스트
        pal = ["#43a047", "#1e88e5", "#fdd835", "#e53935", "#8e24aa"]  # 팔레트(초록/파랑/노랑/빨강/보라)
        # 파편 생성(작은 원)
        for _ in range(n):  # n개 생성
            x = _r.randint(0, max(8, W - 8))  # 시작 X(화면 폭 내 랜덤)
            y = -_r.randint(0, 40)  # 시작 Y(상단 바깥에서 진입)
            s = _r.randint(4, 8)  # 지름(4~8)
            col = _r.choice(pal)  # 색상 랜덤 선택
            parts.append(c.create_oval(x, y, x + s, y + s, fill=col, width=0))  # 원 파편 생성
        t0 = _t.monotonic()  # 시작 시각(모노토닉)
        # 간단한 낙하 애니메이션(수직 이동)
        def tick():  # 프레임 함수
            dt = (_t.monotonic() - t0) * 1000.0  # 경과(ms)
            for p in parts:  # 모든 파편 이동
                c.move(p, 0, 6)  # 아래로 고정 속도 낙하
            if dt < duration:  # 아직 지속 시간 내
                c.after(16, tick)  # 약 60fps로 다음 프레임 예약
            else:  # 시간 만료
                for p in parts:  # 모든 파편
                    c.delete(p)  # 삭제해 잔상/리소스 누수 방지
        tick()  # 첫 프레임 호출
        # New Tk는 캔버스 bg의 '완전 투명'을 지원하지 않아 빈 문자열/투명 컬러 지정 시 오류가 나므로,
        # New 별도 오버레이 캔버스 없이 도넛 캔버스에 직접 그려 안정적으로 연출한다.

    # ─────────────────────────────────────────────────────────
    # 종료 처리(안전 정리)                                      # 종료 시퀀스
    # ─────────────────────────────────────────────────────────
    def _on_close(self) -> None:  # 닫기 핸들러
        """예약된 after 루프(타이머/깜박/리포트)를 모두 취소하고 창을 닫는다."""  # 안전 종료 설명
        self._stop_tick_loop()  # 타이머 루프 정지
        self._stop_blink()  # 깜박임 루프 정지
        self._stop_report_loop()  # 리포트 루프 정지
        self.destroy()  # 창 파괴(프로세스 종료)
        # New after 콜백이 남아있는 상태로 종료하면 예외가 날 수 있으므로 반드시 선 정리

# ─────────────────────────────────────────────────────────
# 실행 엔트리포인트                                           # main guard
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":  # 이 파일을 직접 실행할 때만 아래 코드 실행
    app = TodoApp()   # 최상위 앱 인스턴스 생성
    app.mainloop()    # Tk 이벤트 루프 시작(사용자 인터랙션 처리)
