# ─────────────────────────────────────────────────────────
# Tkinter: 파이썬 기본 GUI
# ─────────────────────────────────────────────────────────

from dataclasses import dataclass  # dataclass 데코레이터를 사용해 보일러플레이트(생성자 등)를 자동 생성
from datetime import date, datetime  # 날짜(date)와 날짜시간(datetime) 타입 사용을 위해 임포트
from pathlib import Path  # 파일 경로를 OS에 독립적으로 다루기 위해 Path 사용
import time  # 단조 증가하는 시간(time.monotonic)과 지연 등을 위해 사용
import math  # 올림/내림 등 수학 연산에 필요
import sqlite3 as sql  # 내장 SQLite 데이터베이스 사용 (간단한 영속화)
import tkinter as tk  # Tkinter GUI 기본 모듈
from tkinter import ttk, messagebox  # ttk는 현대식 위젯, messagebox는 알림창/확인창

# ─────────────────────────────────────────────────────────
# 상수/포맷/공용 패딩
# ─────────────────────────────────────────────────────────
DATE_FMT = "%Y-%m-%d"  # 날짜 문자열 형식 (예: 2025-09-16)
STATUS_ICON = {0: "☐", 1: "⏳", 2: "✔"}  # 상태코드→아이콘 매핑 (0=미완,1=진행,2=완료)
STATUS_TEXT = {0: "미완료", 1: "진행중", 2: "완료"}  # 상태코드→텍스트 매핑
PAD6 = {"padx": 10, "pady": 6}  # 그리드/팩에서 자주 쓰는 여백(6) 프리셋
PAD8 = {"padx": 10, "pady": 8}  # 여백(8) 프리셋

# ─────────────────────────────────────────────────────────
# [NEW] DB 경로 고정(스크립트 파일과 같은 폴더) + 대화형 환경 폴백
# ─────────────────────────────────────────────────────────
try:
    DB_PATH = str(Path(__file__).with_name("todo.db"))  # 스크립트 파일과 같은 폴더의 todo.db 경로 생성
except NameError:
    DB_PATH = "todo.db"  # __file__이 없는 인터프리터/노트북 환경에서는 현재 작업 폴더에 저장

# ─────────────────────────────────────────────────────────
# 유틸: 날짜 파싱 / 창 중앙 배치
# ─────────────────────────────────────────────────────────
def parse_date(s: str) -> datetime:  # 문자열 날짜를 datetime으로 바꾸는 헬퍼
    """날짜 문자열을 datetime 객체로 바꾸는 함수."""  # 도큐스트링(사용자/개발자용 설명)
    return datetime.strptime(s, DATE_FMT)  # 지정 포맷에 맞춰 파싱 (형식 불일치 시 예외 발생)

def center_over(parent: tk.Tk, win: tk.Toplevel) -> None:  # 부모창 기준 자식창을 화면 중앙에 배치
    """부모창 기준으로 자식창을 중앙에 두는 함수(화면 밖으로 안 나가게 보정)."""  # 도큐스트링
    parent.update_idletasks()  # 부모 레이아웃 정보를 최신화 (크기/위치 계산 정확도 ↑)
    win.update_idletasks()  # 자식 레이아웃 정보 최신화
    px, py = parent.winfo_rootx(), parent.winfo_rooty()  # 부모창 좌상단의 화면 절대좌표
    pw, ph = parent.winfo_width(), parent.winfo_height()  # 부모창 폭/높이
    ww, wh = win.winfo_width(), win.winfo_height()  # 자식창 폭/높이
    # 화면 경계 내에서 중앙 위치 계산 (음수/오버플로 방지)
    x = max(0, min(px + (pw - ww) // 2, win.winfo_screenwidth() - ww))  # 가로 위치 보정
    y = max(0, min(py + (ph - wh) // 2, win.winfo_screenheight() - wh))  # 세로 위치 보정
    win.geometry(f"+{x}+{y}")  # 창 위치만 지정 (크기 변경 없음)

# ─────────────────────────────────────────────────────────
# 데이터 모델
# ─────────────────────────────────────────────────────────
@dataclass  # Todo 클래스를 데이터 전용 객체로 간결하게 정의
class Todo:
    """할 일 하나를 표현하는 데이터 덩어리."""  # 도큐스트링: 필드/동작 개요
    title: str  # 할 일 제목
    start: str  # 시작일 (YYYY-MM-DD)
    end: str  # 종료일 (YYYY-MM-DD)
    desc: str = ""  # 상세 설명 (기본 빈 문자열)
    status: int = 0  # 상태 코드(0=미완,1=진행,2=완료), 기본 0

    def cycle(self) -> None:  # 상태를 다음 단계로 바꾸는 편의 메서드
        """상태를 다음 단계로 순환(0→1→2→0)."""  # 도큐스트링
        self.status = (self.status + 1) % 3  # 0→1→2→0 순환

    def display(self, today: date | None = None) -> str:  # 리스트박스에 보여줄 1줄 요약 문자열 생성
        """리스트에 표시할 한 줄 텍스트 만들기."""  # 도큐스트링
        icon = STATUS_ICON.get(self.status, "☐")  # 상태 아이콘 선택(기본값 □)
        try:
            d_end = datetime.strptime(self.end, DATE_FMT).date()  # 종료일을 date로 파싱
        except Exception:
            # 날짜 파싱 실패 시 D-DAY 태그 없이 기본 정보만 반환
            return f"{icon} {self.start} ~ {self.end} | {self.title}"  # 최소 정보 표시

        today = today or date.today()  # today가 없으면 오늘 날짜 사용
        delta = (d_end - today).days  # 종료일까지 남은 일수 계산
        if delta < 0:
            tag = "⛔ 지남"  # 마감 지남
        elif delta == 0:
            tag = "⚠️ D-DAY"  # 마감 당일
        elif delta <= 3:
            tag = f"⏰ D-{delta}"  # 임박 (3일 이내)
        else:
            tag = f"D-{delta}"  # 일반 D-표기
        return f"{icon} [{tag}] {self.start} ~ {self.end} | {self.title}"  # 표시 문자열 구성

# ─────────────────────────────────────────────────────────
# [DB 연동]
# ─────────────────────────────────────────────────────────
def _db() -> sql.Connection:  # DB 연결을 생성하는 헬퍼 (with 문에서 자동 닫힘)
    """[NEW] DB 연결 헬퍼. 호출할 때마다 연결 열고 with 블록이 닫히면 자동 종료."""  # 도큐스트링
    return sql.connect(DB_PATH)  # 지정된 파일 경로로 SQLite 연결

def init_db() -> None:  # 앱 최초 실행 시 테이블 생성 (있으면 무시)
    """[NEW] 앱 최초 실행 시 테이블 생성(이미 있으면 무시)."""  # 도큐스트링
    with _db() as con:  # 연결 자동 해제 보장
        # 상태 값 무결성 체크를 위해 CHECK 제약 포함
        con.execute("""
            CREATE TABLE IF NOT EXISTS todos(
                id     INTEGER PRIMARY KEY AUTOINCREMENT,  -- 내부 PK (표시용 아님)
                title  TEXT NOT NULL,                      -- 제목
                start  TEXT NOT NULL,                      -- 시작일(YYYY-MM-DD)
                end    TEXT NOT NULL,                      -- 종료일(YYYY-MM-DD)
                memo   TEXT DEFAULT '',                    -- 상세설명 (SQL 예약어 충돌 피하려고 'memo' 사용)
                status INTEGER NOT NULL CHECK(status IN (0,1,2)) -- 상태(0/1/2) 제약
            )
        """)  # 테이블 없으면 생성

def load_all() -> list[Todo]:  # DB 모든 항목을 읽어 Todo 리스트로 반환
    """[NEW] DB → 메모리(리스트[Todo])로 읽기."""  # 도큐스트링
    init_db()  # 테이블 존재 보장
    with _db() as con:  # 연결 자동 해제
        rows = con.execute(
            "SELECT title, start, end, memo, status FROM todos ORDER BY id"
        ).fetchall()  # 모든 행을 id 순으로 읽기
    return [Todo(title, start, end, memo, status) for (title, start, end, memo, status) in rows]  # 행→Todo 변환

def save_all(items: list[Todo]) -> None:  # 현재 메모리 상태를 DB에 전량 반영(덮어쓰기)
    """[NEW] 메모리 → DB로 전량 덮어쓰기(간결, 실수 적음)."""  # 도큐스트링
    with _db() as con:  # 트랜잭션 범위 (실패 시 자동 롤백)
        con.execute("DELETE FROM todos")  # 기존 데이터 전부 삭제
        con.executemany(                  # 현재 리스트를 그대로 삽입
            "INSERT INTO todos(title, start, end, memo, status) VALUES(?,?,?,?,?)",
            [(t.title, t.start, t.end, t.desc, t.status) for t in items],  # 필드 튜플 시퀀스
        )  # executemany로 일괄 삽입

# ─────────────────────────────────────────────────────────
# 할 일 추가/편집 팝업
# ─────────────────────────────────────────────────────────
class TodoDialog(tk.Toplevel):  # 추가/편집에 사용하는 모달 대화상자
    """할 일 추가/편집 팝업 창."""  # 도큐스트링

    def __init__(self, parent: tk.Tk, title: str, prefill: str = "", item: Todo | None = None):  # 생성자
        """생성자. 부모창/제목/기본입력/편집대상 받기."""  # 도큐스트링
        super().__init__(parent)  # Toplevel 초기화 및 부모 지정
        self.result: Todo | None = None  # 저장 결과(Todo)를 담아 반환할 슬롯
        self._orig_status = item.status if item else 0  # 편집이면 기존 상태, 신규면 0으로 시작

        self.title(title)  # 창 타이틀 설정
        self.transient(parent)  # 부모창 위에 떠 있도록 설정(작업 전환 시 함께)
        self.resizable(False, False)  # 창 크기 조절 비활성화
        self.grab_set()  # 모달 상태(닫기 전까지 다른 창 포커스 차단)

        pad = PAD6  # 공통 여백 프리셋
        today_str = date.today().isoformat()  # 오늘 날짜 문자열(YYYY-MM-DD)

        # 제목
        ttk.Label(self, text="제목").grid(row=0, column=0, sticky="w", **pad)  # 제목 라벨
        self.ent_title = ttk.Entry(self, width=38)  # 제목 입력창
        self.ent_title.grid(row=0, column=1, sticky="w", **pad)  # 제목 입력 배치
        self.ent_title.insert(0, prefill or (item.title if item else ""))  # 기본값(빠른입력/편집값/빈값)

        # 시작일
        ttk.Label(self, text="시작일 (YYYY-MM-DD)").grid(row=1, column=0, sticky="w", **pad)  # 시작일 라벨
        self.ent_start = ttk.Entry(self, width=20)  # 시작일 입력창
        self.ent_start.grid(row=1, column=1, sticky="w", **pad)  # 시작일 입력 배치
        self.ent_start.insert(0, item.start if item else today_str)  # 기본값(편집 시 기존값/신규면 오늘)

        # 종료일
        ttk.Label(self, text="종료일 (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", **pad)  # 종료일 라벨
        self.ent_end = ttk.Entry(self, width=20)  # 종료일 입력창
        self.ent_end.grid(row=2, column=1, sticky="w", **pad)  # 종료일 입력 배치
        self.ent_end.insert(0, item.end if item else today_str)  # 기본값(편집 시 기존값/신규면 오늘)

        # 상세설명
        ttk.Label(self, text="상세설명").grid(row=3, column=0, sticky="nw", **pad)  # 상세설명 라벨
        self.txt_desc = tk.Text(self, width=40, height=6)  # 상세설명 멀티라인 텍스트 박스
        self.txt_desc.grid(row=3, column=1, **pad)  # 상세설명 배치
        if item:  # 편집 모드라면
            self.txt_desc.insert("1.0", item.desc)  # 기존 설명 채우기

        # 버튼들
        btns = ttk.Frame(self)  # 버튼 묶음 프레임
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=10)  # 오른쪽 정렬 배치
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="right", padx=6)  # 취소 버튼(창 닫기)
        ttk.Button(btns, text="저장", command=self._on_save).pack(side="right")  # 저장 버튼(검증 후 result 세팅)

        # 배치/위치/포커스
        self.update_idletasks()  # 위젯 배치 계산 반영
        center_over(parent, self)  # 부모 기준 중앙 배치
        self.ent_title.focus_set()  # 제목 입력에 포커스

    def _on_save(self) -> None:  # 저장 버튼 콜백: 입력 검증 후 result 채우고 닫기
        """저장 버튼 눌렀을 때 유효성 검사 후 결과 설정."""  # 도큐스트링
        title = self.ent_title.get().strip()  # 제목 가져와 공백 제거
        start = self.ent_start.get().strip()  # 시작일 문자열
        end = self.ent_end.get().strip()  # 종료일 문자열
        desc = self.txt_desc.get("1.0", "end").strip()  # 상세설명 전체 텍스트

        if not title:  # 제목 미입력 검증
            messagebox.showwarning("확인", "제목을 입력하세요.", parent=self)  # 경고창
            self.ent_title.focus_set()  # 포커스 복귀
            return  # 저장 중단
        try:
            d1 = parse_date(start)  # 시작일 파싱
        except Exception:
            messagebox.showerror("날짜 오류", "시작일 형식이 잘못되었습니다.\n예: 2025-09-16", parent=self)  # 오류 안내
            self.ent_start.focus_set()  # 포커스 이동
            return  # 저장 중단
        try:
            d2 = parse_date(end)  # 종료일 파싱
        except Exception:
            messagebox.showerror("날짜 오류", "종료일 형식이 잘못되었습니다.\n예: 2025-09-18", parent=self)  # 오류 안내
            self.ent_end.focus_set()  # 포커스 이동
            return  # 저장 중단
        if d2 < d1:  # 종료일이 시작일보다 빠른 경우
            messagebox.showerror("날짜 오류", "종료일은 시작일보다 빠를 수 없습니다.", parent=self)  # 오류 안내
            self.ent_end.focus_set()  # 포커스 이동
            return  # 저장 중단

        # 입력값으로 Todo 객체 생성 (편집 시 기존 상태 유지)
        self.result = Todo(title=title, start=start, end=end, desc=desc, status=self._orig_status)  # 결과 세팅
        self.destroy()  # 대화상자 닫기 (wait_window 종료)

# ─────────────────────────────────────────────────────────
# 메인 앱
# ─────────────────────────────────────────────────────────
class TodoApp(tk.Tk):  # 전체 애플리케이션 윈도우
    """메인 앱 창. 탭 여러 개 들어가는 윈도우."""  # 도큐스트링

    # ─────────────────────────────────────────────────────────
    # [앱 초기화: 메인창 크기/제목 설정, 탭 구성]
    # ─────────────────────────────────────────────────────────
    def __init__(self) -> None:  # 생성자: UI/상태 초기화
        """앱 시작할 때 한 번 실행되는 부분."""  # 도큐스트링
        super().__init__()  # Tk 루트 윈도우 생성
        self.title("갓생살기")  # 창 타이틀
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()  # 화면 전체 폭/높이
        x, y = (sw - 580) // 2, (sh - 380) // 2  # 중앙 배치 좌표
        self.geometry(f"580x380+{x}+{y}")  # 초기 크기/위치 지정

        # 창 닫기 처리: 예약된 after 취소 등 안전 종료
        self.protocol("WM_DELETE_WINDOW", self._on_close)  # 닫기(X) 이벤트 핸들러 지정

        # 할 일 목록(메모리 상의 상태)
        self.todos: list[Todo] = []  # 앱이 관리하는 Todo 리스트

        # 타이머 관련 상태값 초기화
        self._timer_after_id: str | None = None  # after 예약 ID(틱 루프), 취소에 필요
        self._blink_after_id: str | None = None  # after 예약 ID(깜박임 루프)
        self.timer_running: bool = False  # 타이머 동작 여부
        self.timer_total_sec: int = 0  # 총 타이머 시간(초)
        self.timer_warn_sec: int = 30  # 경고 시작 임계(초)
        self.timer_end_mono: float = 0.0  # 단조 시계로 계산한 종료 목표 시각
        self.timer_remain_sec: int = 0  # 남은 시간(초)
        self._blink_on: bool = False  # 깜박임 토글 상태

        # 탭 노트북 구성
        nb = ttk.Notebook(self)  # 탭 컨테이너
        nb.pack(expand=True, fill="both", padx=10, pady=10)  # 전체 창에 맞게 배치

        # 탭 프레임 생성
        self.tab_todo = ttk.Frame(nb)  # 할 일 탭
        self.tab_timer = ttk.Frame(nb)  # 타이머 탭
        self.tab_grade = ttk.Frame(nb)  # 성적 탭(향후)
        self.tab_report = ttk.Frame(nb)  # 리포트 탭(향후)
        nb.add(self.tab_todo, text="할 일")  # 탭 추가
        nb.add(self.tab_timer, text="타이머")  # 탭 추가
        nb.add(self.tab_grade, text="성적")  # 탭 추가
        nb.add(self.tab_report, text="리포트")  # 탭 추가

        # 각 탭 UI 구성
        self._build_todo_tab()  # 할 일 탭 위젯 구성
        self._build_timer_tab()  # 타이머 탭 위젯 구성
        ttk.Label(self.tab_grade, text="여기에 '성적' 기능 추가 예정").pack(pady=20)  # 자리표시자
        ttk.Label(self.tab_report, text="여기에 '리포트' 기능 추가 예정").pack(pady=20)  # 자리표시자

        # [NEW] DB 준비/로드 후 리스트 표시
        init_db()  # 테이블 생성(없으면)
        self.todos = load_all()  # 기존 할 일 불러오기
        self.refresh_list()  # 리스트 UI 갱신

    # ─────────────────────────────────────────────────────────
    # [할 일 탭 UI]
    # ─────────────────────────────────────────────────────────
    def _build_todo_tab(self) -> None:  # 할 일 탭 구성 함수
        """할 일 탭 만들기."""  # 도큐스트링
        top = ttk.Frame(self.tab_todo)  # 상단 입력줄/버튼 영역
        top.pack(fill="x", padx=10, pady=10)  # 가로 채움 배치

        # 빠른 제목 입력칸 + 버튼들
        self.quick_entry = ttk.Entry(top)  # 빠른 제목 입력
        self.quick_entry.pack(side="left", fill="x", expand=True)  # 좌측부터 확장 배치
        self.quick_entry.focus()  # 포커스 지정
        self.quick_entry.bind("<Return>", lambda e: self.add_todo())  # 엔터로 추가 실행

        ttk.Button(top, text="추가", command=self.add_todo).pack(side="left", padx=6)  # 추가 버튼
        ttk.Button(top, text="편집", command=self.edit_selected).pack(side="left", padx=6)  # 편집 버튼
        ttk.Button(top, text="삭제", command=self.delete_selected).pack(side="left", padx=6)  # 삭제 버튼
        ttk.Button(top, text="상태전환 (☐→⏳→✔)", command=self.cycle_status_selected).pack(side="left", padx=6)  # 상태전환

        # 리스트 영역 + 스크롤바
        mid = ttk.Frame(self.tab_todo)  # 리스트/스크롤 컨테이너
        mid.pack(fill="both", expand=True, padx=10, pady=5)  # 남는 공간 채우기

        self.listbox = tk.Listbox(mid, height=10, selectmode="extended")  # 다중 선택 가능한 리스트박스
        self.listbox.pack(side="left", fill="both", expand=True)  # 확장 배치

        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)  # 세로 스크롤바
        scroll.pack(side="left", fill="y")  # 세로 방향으로 채우기
        self.listbox.config(yscrollcommand=scroll.set)  # 리스트 스크롤 연동

        # 단축키 바인딩
        self.listbox.bind("<Delete>", lambda e: self.delete_selected())  # Del로 삭제
        self.listbox.bind("<space>", self._on_space_toggle)  # Space로 상태 전환
        self.listbox.bind("<Double-Button-1>", self.show_details)  # 더블클릭 상세 보기

    # ─────────────────────────────────────────────────────────
    # [타이머 탭 UI]
    # ─────────────────────────────────────────────────────────
    def _build_timer_tab(self) -> None:  # 타이머 탭 구성 함수
        """타이머 탭 만들기."""  # 도큐스트링
        top = ttk.Frame(self.tab_timer)  # 상단 입력+제어 영역
        top.pack(fill="x", **PAD8)  # 가로 채움 배치

        # 시간/경고 입력 + 제어 버튼들
        ttk.Label(top, text="발표 시간(분)").pack(side="left")  # 분 입력 라벨
        self.ent_minutes = ttk.Entry(top, width=6)  # 분 입력 상자
        self.ent_minutes.pack(side="left", padx=(4, 12))  # 라벨 옆 간격
        self.ent_minutes.insert(0, "5")  # 기본값 5분

        ttk.Label(top, text="경고 임계(초)").pack(side="left")  # 경고 임계 라벨
        self.ent_warn = ttk.Entry(top, width=6)  # 경고 임계 입력
        self.ent_warn.pack(side="left", padx=(4, 12))  # 간격
        self.ent_warn.insert(0, "30")  # 기본값 30초

        self.btn_start = ttk.Button(top, text="시작", command=self.start_timer)  # 시작 버튼
        self.btn_start.pack(side="left", padx=4)  # 간격
        self.btn_pause = ttk.Button(top, text="일시정지", command=self.pause_resume_timer, state="disabled")  # 일시정지 버튼
        self.btn_pause.pack(side="left", padx=4)  # 간격
        self.btn_reset = ttk.Button(top, text="초기화", command=self.reset_timer, state="disabled")  # 초기화 버튼
        self.btn_reset.pack(side="left", padx=4)  # 간격

        # 남은 시간 표시 + 진행률 바
        mid = ttk.Frame(self.tab_timer)  # 중앙 표시 영역
        mid.pack(expand=True, fill="both", **PAD8)  # 남는 공간 채우기

        self.lbl_timer = tk.Label(mid, text="00:00", font=("Helvetica", 36, "bold"))  # 남은 시간 라벨
        self.lbl_timer.pack(pady=10)  # 위아래 여백

        self.pb_timer = ttk.Progressbar(mid, orient="horizontal", mode="determinate", length=360)  # 진행률 바
        self.pb_timer.pack(fill="x", padx=20, pady=10)  # 가로 채움

        # 안내 문구
        bottom = ttk.Frame(self.tab_timer)  # 하단 안내 영역
        bottom.pack(fill="x", **PAD8)  # 가로 채움
        ttk.Label(
            bottom,
            text="Tip) 남은 시간이 임계값 이하로 떨어지면 주황색, 0이 되면 빨간색으로 깜박이며 종료를 알립니다."
        ).pack(anchor="w")  # 좌측 정렬

    # ─────────────────────────────────────────────────────────
    # [헬퍼 함수: 공통 동작 모음 - 선택 확인, 리스트 갱신, 저장]
    # ─────────────────────────────────────────────────────────
    def _selected_indices(self) -> tuple[int, ...] | None:  # 리스트 선택 인덱스 얻기
        """리스트에서 선택한 항목 인덱스들 꺼내는 함수."""  # 도큐스트링
        sel = self.listbox.curselection()  # 현재 선택된 인덱스 튜플
        if not sel:  # 아무 것도 선택 안 했다면
            messagebox.showwarning("확인", "항목을 선택하세요.", parent=self)  # 경고
            return None  # None 반환
        return sel  # 선택 인덱스 튜플 반환

    def refresh_list(self) -> None:  # 리스트박스 내용을 현재 상태로 재구성
        """리스트박스 내용을 지금 상태에 맞게 다시 채우기."""  # 도큐스트링
        self.listbox.delete(0, tk.END)  # 기존 아이템 모두 삭제
        if self.todos:  # 항목이 있으면
            self.listbox.insert(tk.END, *[t.display() for t in self.todos])  # 표시 문자열로 채움

    def _save(self) -> None:  # 현재 todos를 DB에 반영
        """[NEW] 현재 리스트를 DB에 반영."""  # 도큐스트링
        save_all(self.todos)  # 전체 덮어쓰기 방식 저장

    # ─────────────────────────────────────────────────────────
    # [사용자 액션: 추가/편집/삭제/상태전환/상세보기 동작]
    # ─────────────────────────────────────────────────────────
    def add_todo(self) -> None:  # 새 할 일 추가
        """새 할 일 추가."""  # 도큐스트링
        prefill = self.quick_entry.get().strip()  # 빠른 입력칸의 텍스트
        dlg = TodoDialog(self, "할 일 추가", prefill=prefill)  # 팝업 생성
        self.wait_window(dlg)  # 사용자가 닫을 때까지 대기(모달)
        if dlg.result:  # 저장됨
            self.todos.append(dlg.result)  # 메모리 리스트에 추가
            self._save()      # DB 반영
            self.refresh_list()  # 리스트 새로고침

    def edit_selected(self) -> None:  # 선택 항목 편집
        """선택한 항목 편집."""  # 도큐스트링
        sel = self._selected_indices()  # 선택 확인
        if not sel:
            return  # 선택 없으면 종료
        idx = sel[0]  # 첫 번째 선택 인덱스
        dlg = TodoDialog(self, "할 일 편집", item=self.todos[idx])  # 편집 모드 팝업
        self.wait_window(dlg)  # 팝업 닫힐 때까지 대기
        if dlg.result:  # 저장됨
            self.todos[idx] = dlg.result  # 항목 교체
            self._save()      # DB 반영
            self.refresh_list()  # 리스트 새로고침

    def delete_selected(self) -> None:  # 선택 항목 삭제
        """선택 항목 삭제."""  # 도큐스트링
        sel = self._selected_indices()  # 선택 확인
        if not sel:
            return  # 선택 없으면 종료
        if not messagebox.askyesno("삭제 확인", f"선택한 {len(sel)}개 항목을 정말 삭제할까요?", parent=self):  # 확인
            return  # 취소 시 종료
        for i in reversed(sel):  # 뒤에서부터 삭제(앞에서 지우면 인덱스 당김 문제 방지)
            del self.todos[i]  # 리스트에서 제거
        self._save()  # DB 반영
        self.refresh_list()  # 리스트 새로고침

    def cycle_status_selected(self) -> None:  # 선택 항목 상태 순환
        """선택 항목들의 상태를 한 칸씩 넘기기."""  # 도큐스트링
        sel = self._selected_indices()  # 선택 확인
        if not sel:
            return  # 선택 없으면 종료
        for i in sel:  # 모든 선택 항목에 대해
            self.todos[i].cycle()  # 상태 순환
        self._save()  # DB 반영
        self.refresh_list()  # UI 새로고침

    def _on_space_toggle(self, _e) -> str:  # Space 키로 상태 토글
        """스페이스바 눌렀을 때 상태 토글."""  # 도큐스트링
        self.cycle_status_selected()  # 상태 변경 실행
        return "break"  # 기본 스페이스 동작(선택 이동) 막기

    def show_details(self, _e=None) -> None:  # 선택 항목 상세 보기
        """선택 항목 상세 정보 팝업."""  # 도큐스트링
        sel = self._selected_indices()  # 선택 확인
        if not sel:
            return  # 선택 없으면 종료
        t = self.todos[sel[0]]  # 첫 항목
        icon = STATUS_ICON.get(t.status, "☐")  # 상태 아이콘
        msg = (  # 상세 메시지 구성
            f"제목: {t.title}\n"
            f"기간: {t.start} ~ {t.end}\n"
            f"상태: {icon} {STATUS_TEXT.get(t.status,'')}\n\n"
            f"상세설명:\n{t.desc or '(없음)'}"
        )
        messagebox.showinfo("할 일 상세", msg, parent=self)  # 정보창 표시

    # ─────────────────────────────────────────────────────────
    # [타이머 로직] — 모노토닉 시계 기반으로 안정성 강화
    # ─────────────────────────────────────────────────────────
    def _format_sec(self, s: int) -> str:  # 초 → "MM:SS" 문자열 변환
        """초를 'MM:SS' 문자열로 만드는 함수."""  # 도큐스트링
        s = max(0, int(s))  # 음수 방지 및 정수화
        m, ss = divmod(s, 60)  # 분/초 분리
        return f"{m:02d}:{ss:02d}"  # 2자리 0패딩 포맷

    def _set_timer_controls_running(self, running: bool) -> None:  # 타이머 동작 여부에 따른 UI 상태 전환
        """타이머 상태에 따라 버튼/입력칸 활성화 조절."""  # 도큐스트링
        if running:  # 동작 중일 때
            self.btn_start.config(state="disabled")  # 시작 비활성
            self.btn_pause.config(state="normal", text="일시정지")  # 일시정지 활성
            self.btn_reset.config(state="normal")  # 초기화 활성
            self.ent_minutes.config(state="disabled")  # 입력 잠금
            self.ent_warn.config(state="disabled")  # 입력 잠금
        else:  # 멈춤 상태
            self.btn_start.config(state="normal")  # 시작 활성
            self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 비활성
            self.btn_reset.config(state="disabled")  # 초기화 비활성
            self.ent_minutes.config(state="normal")  # 입력 가능
            self.ent_warn.config(state="normal")  # 입력 가능

    def _stop_tick_loop(self) -> None:  # after로 예약된 타이머 틱 루프 취소
        """after로 예약한 타이머 업데이트 멈추기."""  # 도큐스트링
        if self._timer_after_id is not None:  # 예약이 있으면
            try:
                self.after_cancel(self._timer_after_id)  # 예약 취소
            except Exception:
                pass  # 이미 취소/만료 등 예외 무시
            self._timer_after_id = None  # ID 클리어

    def _stop_blink(self) -> None:  # 깜박임 루프 중지 및 색상 복원
        """깜박임 루프 멈추기."""  # 도큐스트링
        if self._blink_after_id is not None:  # 예약이 있으면
            try:
                self.after_cancel(self._blink_after_id)  # 예약 취소
            except Exception:
                pass  # 예외 무시
            self._blink_after_id = None  # ID 클리어
        self._blink_on = False  # 상태 리셋
        self.lbl_timer.config(fg="black")  # 글자색 복원

    def _start_blink(self) -> None:  # 타임업 후 빨강/검정 깜박임 시작
        """0초 되었을 때 빨강/검정 번갈이로 깜박이기 시작."""  # 도큐스트링
        self._blink_on = not self._blink_on  # 토글
        self.lbl_timer.config(fg=("red" if self._blink_on else "black"))  # 색상 전환
        self._blink_after_id = self.after(450, self._start_blink)  # 0.45초 간격 재호출

    def start_timer(self) -> None:  # 시작 버튼 핸들러
        """시작 버튼 눌렀을 때 타이머 시작."""  # 도큐스트링
        self._stop_tick_loop()  # 기존 틱 루프 정지
        self._stop_blink()  # 깜박임 정지

        # 분 입력값 검사(실수 허용: 7.5 등)
        try:
            minutes = float(self.ent_minutes.get().strip())  # 분 입력 파싱
        except Exception:
            messagebox.showerror("입력 오류", "발표 시간(분)을 숫자로 입력하세요. 예: 5 또는 7.5", parent=self)  # 오류 안내
            self.ent_minutes.focus_set()  # 포커스 이동
            return  # 중단
        if minutes <= 0:  # 0 이하 방지
            messagebox.showerror("입력 오류", "발표 시간(분)은 0보다 커야 합니다.", parent=self)  # 오류 안내
            self.ent_minutes.focus_set()  # 포커스 이동
            return  # 중단

        # 경고 임계(초) 검사(정수)
        try:
            warn = int(self.ent_warn.get().strip())  # 임계 파싱
        except Exception:
            messagebox.showerror("입력 오류", "경고 임계(초)를 정수로 입력하세요. 예: 30", parent=self)  # 오류 안내
            self.ent_warn.focus_set()  # 포커스 이동
            return  # 중단
        if warn < 1:  # 최소 1초 보장
            messagebox.showerror("입력 오류", "경고 임계(초)는 1초 이상이어야 합니다.", parent=self)  # 오류 안내
            self.ent_warn.focus_set()  # 포커스 이동
            return  # 중단

        # 총 초/경고 초 세팅
        total_sec = int(round(minutes * 60))  # 분→초 환산(반올림)
        self.timer_total_sec = total_sec  # 총 시간 저장
        self.timer_warn_sec = min(warn, max(1, total_sec - 1))  # 총 시간보다 작게, 최소 1초

        # 모노토닉 기준으로 종료 목표 시각 설정
        self.timer_running = True  # 실행 상태
        self.timer_end_mono = time.monotonic() + self.timer_total_sec  # 종료 목표 시각
        self.timer_remain_sec = self.timer_total_sec  # 남은 시간 초기화

        # UI 초기화
        self.lbl_timer.config(text=self._format_sec(self.timer_remain_sec), fg="black")  # 시간 표시/색상 초기화
        self.pb_timer.config(maximum=self.timer_total_sec, value=0)  # 진행률 바 초기화
        self._set_timer_controls_running(True)  # 버튼/입력 상태 전환

        # 주기 업데이트 루프 시작
        self._tick_update()  # 첫 틱 호출

    def pause_resume_timer(self) -> None:  # 일시정지/계속 토글
        """일시정지/계속 토글."""  # 도큐스트링
        if not self.timer_running:  # 현재 멈춤 상태면
            # 계속
            if self.timer_remain_sec <= 0:  # 이미 끝났으면 무시
                return  # 종료
            self.timer_end_mono = time.monotonic() + self.timer_remain_sec  # 새 목표 시각 재계산
            self.timer_running = True  # 실행
            self.btn_pause.config(text="일시정지")  # 버튼 라벨
            self._tick_update()  # 틱 재개
            return  # 반환

        # 현재 실행 중이면 → 일시정지
        now_mono = time.monotonic()  # 현재 단조 시각
        remain = max(0, int(math.ceil(self.timer_end_mono - now_mono)))  # 남은 초 계산(올림)
        self.timer_remain_sec = remain  # 상태 업데이트
        self.timer_running = False  # 멈춤
        self.btn_pause.config(text="계속")  # 버튼 라벨
        self._stop_tick_loop()  # 틱 루프 중단

    def reset_timer(self) -> None:  # 초기화 버튼 핸들러
        """초기화 버튼 동작."""  # 도큐스트링
        self.timer_running = False  # 멈춤 상태
        self.timer_total_sec = 0  # 총 시간 리셋
        self.timer_remain_sec = 0  # 남은 시간 리셋
        self.timer_end_mono = 0.0  # 목표 시각 리셋
        self._stop_tick_loop()  # 틱 루프 중단
        self._stop_blink()  # 깜박임 중단
        self.lbl_timer.config(text="00:00", fg="black")  # 표시 리셋
        self.pb_timer.config(maximum=1, value=0)  # 진행률 바 최소 상태
        self._set_timer_controls_running(False)  # 버튼/입력 잠금 해제

    def _on_time_up(self) -> None:  # 타임업 처리
        """시간이 0이 되었을 때 처리."""  # 도큐스트링
        self.timer_running = False  # 멈춤 상태
        self._stop_tick_loop()  # 틱 중단
        self.lbl_timer.config(text="00:00", fg="red")  # 0초/빨간색 표시
        self.pb_timer.config(value=self.timer_total_sec)  # 진행률 바 꽉 채우기
        try:
            self.bell()  # 시스템 알림음
        except Exception:
            pass  # 환경에 따라 실패할 수 있으므로 무시
        self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 버튼 비활성
        self._start_blink()  # 깜박임 시작

    def _tick_update(self) -> None:  # 0.2초 간격으로 남은 시간 갱신
        """0.2초마다 남은 시간 갱신하는 루프."""  # 도큐스트링
        if not self.timer_running:  # 멈춤 상태면
            return  # 갱신 중단

        now_mono = time.monotonic()  # 현재 단조 시각
        remain = int(max(0, math.ceil(self.timer_end_mono - now_mono)))  # 남은 초(올림, 음수 방지)
        self.timer_remain_sec = remain  # 상태 업데이트

        # 라벨 텍스트/색상 갱신
        self.lbl_timer.config(text=self._format_sec(remain))  # 남은 시간 표시
        if remain == 0:  # 타임업
            self._on_time_up()  # 타임업 처리
            return  # 루프 종료
        elif remain <= self.timer_warn_sec:  # 경고 구간
            self.lbl_timer.config(fg="orange")  # 주황색
        else:
            self.lbl_timer.config(fg="black")  # 정상 색상

        # 진행률 갱신 (경과 시간)
        done = self.timer_total_sec - remain  # 진행된 초
        self.pb_timer.config(value=done)  # 바 값 설정

        # 다음 틱 예약(200ms 후)
        self._timer_after_id = self.after(200, self._tick_update)  # 재호출 예약

    # ─────────────────────────────────────────────────────────
    # [종료 처리]
    # ─────────────────────────────────────────────────────────
    def _on_close(self) -> None:  # 창 닫기 요청 시 정리
        """창 닫기 요청 시 안전하게 after/깜박임 정리 후 종료."""  # 도큐스트링
        self._stop_tick_loop()  # 틱 중단
        self._stop_blink()  # 깜박임 중단
        self.destroy()  # 창 파괴(프로그램 종료)

# ─────────────────────────────────────────────────────────
# 앱 실행
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":  # 이 파일을 직접 실행할 때만 실행 (모듈 임포트 시 미실행)
    app = TodoApp()  # 앱 인스턴스 생성
    app.mainloop()  # Tk 이벤트 루프 시작(사용자 상호작용 처리)
