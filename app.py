# ─────────────────────────────────────────────────────────
# Tkinter: 파이썬 기본 GUI
# ─────────────────────────────────────────────────────────
from dataclasses import dataclass  # dataclass 기능 가져오기. 클래스 필드로 자동 생성자 같은 거 만들어줌.
from datetime import date, datetime  # 날짜(date)랑 날짜시간(datetime) 타입 쓰려고 가져오기.
import tkinter as tk  # Tkinter 기본 GUI 모듈. tk 라는 짧은 이름으로 부르기.
from tkinter import ttk, messagebox  # ttk는 모던 위젯 모음, messagebox는 알림창 띄우는 기능.
import time  # 현재 시간 재고 타이머 계산할 때 쓰려고 가져오기.
import math  # 올림/내림 같은 수학 계산에 쓰려고 가져오기.
import sqlite3 as sql  # [NEW] SQLite 내장 DB로 간단 영속화.
DB_PATH = "todo.db"    # [NEW] 앱이 사용할 DB 파일 경로/이름.

DATE_FMT = "%Y-%m-%d"  # 날짜 문자열 형식 통일. 예: 2025-09-16
STATUS_ICON = {0: "☐", 1: "⏳", 2: "✔"}  # 상태 숫자→아이콘 매핑. 0=미완, 1=진행, 2=완료.
STATUS_TEXT = {0: "미완료", 1: "진행중", 2: "완료"}  # 상태 숫자→한글 설명 매핑.

def parse_date(s: str) -> datetime:  # 날짜 문자열을 datetime 객체로 바꾸는 함수.
    return datetime.strptime(s, DATE_FMT)  # 정해둔 형식에 맞춰서 해석.

@dataclass  # 아래 클래스를 dataclass로 꾸며서 편하게 필드 넣고 쓰기.
class Todo:  # 할 일 하나를 표현하는 데이터 덩어리.
    title: str  # 할 일 제목.
    start: str  # 시작일(문자열). 형식은 YYYY-MM-DD.
    end: str  # 종료일(문자열). 형식은 YYYY-MM-DD.
    desc: str = ""  # 상세 설명. 기본은 빈 문자열.
    status: int = 0  # 상태. 0=미완, 1=진행, 2=완료. 기본은 0.

    def cycle(self) -> None:  # 상태를 다음 단계로 넘기는 동작.
        self.status = (self.status + 1) % 3  # 0→1→2→0 순환.

    def display(self, today: date | None = None) -> str:  # 리스트에 표시할 한 줄 텍스트 만들기.
        icon = STATUS_ICON.get(self.status, "☐")  # 상태에 맞는 아이콘 고르기. 못 찾으면 기본 □.
        try:  # 종료일이 날짜 형식인지 확인해보기.
            d_end = datetime.strptime(self.end, DATE_FMT).date()  # 종료일 문자열을 date로 바꾸기.
        except Exception:  # 형식이 엉켜도 앱 안 죽게 예외 잡기.
            return f"{icon} {self.start} ~ {self.end} | {self.title}"  # 날짜 계산 못 하면 태그 없이 기본 정보만 보여주기.

        today = today or date.today()  # today가 안 들어오면 오늘 날짜로 설정.
        delta = (d_end - today).days  # 종료일까지 몇 일이 남았는지 계산.
        if delta < 0:  # 이미 지난 경우.
            tag = "⛔ 지남"  # 지난 표시.
        elif delta == 0:  # 오늘이 마감일인 경우.
            tag = "⚠️ D-DAY"  # 디데이 표시.
        elif delta <= 3:  # 3일 이내로 남은 경우.
            tag = f"⏰ D-{delta}"  # 촉박 느낌 아이콘 붙이기.
        else:  # 여유가 좀 있는 경우.
            tag = f"D-{delta}"  # 일반 D-n 표시.
        return f"{icon} [{tag}] {self.start} ~ {self.end} | {self.title}"  # 최종 한 줄 문자열 조립해서 반환.

# ─────────────────────────────────────────────────────────
# [DB 연동]
# ─────────────────────────────────────────────────────────
def _db() -> sql.Connection:  # [NEW] DB 연결 헬퍼. 호출할 때마다 연결 열고 with 블록이 닫히면 자동 종료.
    return sql.connect(DB_PATH)

def init_db() -> None:  # [NEW] 앱 최초 실행 시 테이블 생성(이미 있으면 무시).
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS todos(
                id     INTEGER PRIMARY KEY AUTOINCREMENT,  -- 내부용 PK(사용 안 해도 무방)
                title  TEXT NOT NULL,                      -- 제목
                start  TEXT NOT NULL,                      -- 시작일(YYYY-MM-DD)
                end    TEXT NOT NULL,                      -- 종료일(YYYY-MM-DD)
                memo   TEXT DEFAULT '',                    -- 상세설명 (SQL 키워드 충돌 피하려고 'memo' 컬럼명 사용)
                status INTEGER NOT NULL                    -- 상태(0/1/2)
            )
        """)

def load_all() -> list[Todo]:  # [NEW] DB → 메모리(리스트[Todo])로 읽기.
    init_db()  # 테이블 없으면 만들어두기.
    with _db() as con:
        rows = con.execute(
            "SELECT title, start, end, memo, status FROM todos ORDER BY id"
        ).fetchall()
    return [Todo(title, start, end, memo, status) for (title, start, end, memo, status) in rows]

def save_all(items: list[Todo]) -> None:  # [NEW] 메모리 → DB로 전량 덮어쓰기(간결, 실수 적음).
    with _db() as con:  # 트랜잭션으로 묶여서 중간 실패 시 자동 롤백.
        con.execute("DELETE FROM todos")  # 기존 전부 지우고
        con.executemany(                  # 현재 리스트를 그대로 넣기.
            "INSERT INTO todos(title, start, end, memo, status) VALUES(?,?,?,?,?)",
            [(t.title, t.start, t.end, t.desc, t.status) for t in items],
        )

class TodoDialog(tk.Toplevel):  # 할 일 추가/편집 팝업 창.

    def __init__(self, parent: tk.Tk, title: str, prefill: str = "", item: Todo | None = None):  # 생성자. 부모창/제목/기본입력/편집대상 받기.
        super().__init__(parent)  # Toplevel 기본 초기화. 부모창 연결.
        self.result: Todo | None = None  # 저장 버튼 누른 뒤 결과를 담아둘 곳.
        self._orig_status = item.status if item else 0  # 편집 모드면 기존 상태 기억. 새로 만들면 0.

        self.title(title)  # 창 제목 바꾸기.
        self.transient(parent)  # 부모창 위에 떠 있도록 설정.
        self.resizable(False, False)  # 창 크기 조절 못 하게 잠그기.
        self.grab_set()  # 이 창에 집중(모달). 닫을 때까지 다른 창 못 누르게.

        pad = {"padx": 10, "pady": 6}  # 위젯 사이 여백 기본값.
        today_str = date.today().isoformat()  # 오늘 날짜를 yyyy-mm-dd 문자열로.

        ttk.Label(self, text="제목").grid(row=0, column=0, sticky="w", **pad)  # 제목 라벨. 왼쪽 정렬로 배치.
        self.ent_title = ttk.Entry(self, width=38)  # 제목 입력칸. 적당히 넓게.
        self.ent_title.grid(row=0, column=1, sticky="w", **pad)  # 제목 입력칸 배치.
        self.ent_title.insert(0, prefill or (item.title if item else ""))  # 빠른입력값 있으면 쓰고, 편집이면 기존 제목, 아니면 빈 값.

        ttk.Label(self, text="시작일 (YYYY-MM-DD)").grid(row=1, column=0, sticky="w", **pad)  # 시작일 라벨.
        self.ent_start = ttk.Entry(self, width=20)  # 시작일 입력칸.
        self.ent_start.grid(row=1, column=1, sticky="w", **pad)  # 시작일 입력칸 배치.
        self.ent_start.insert(0, item.start if item else today_str)  # 편집이면 기존 날짜, 아니면 오늘 날짜 채우기.

        ttk.Label(self, text="종료일 (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", **pad)  # 종료일 라벨.
        self.ent_end = ttk.Entry(self, width=20)  # 종료일 입력칸.
        self.ent_end.grid(row=2, column=1, sticky="w", **pad)  # 종료일 입력칸 배치.
        self.ent_end.insert(0, item.end if item else today_str)  # 편집이면 기존 종료일, 아니면 오늘 날짜.

        ttk.Label(self, text="상세설명").grid(row=3, column=0, sticky="nw", **pad)  # 설명 라벨. 위쪽 정렬.
        self.txt_desc = tk.Text(self, width=40, height=6)  # 여러 줄 텍스트 박스. 설명 적을 용도.
        self.txt_desc.grid(row=3, column=1, **pad)  # 텍스트 박스 배치.
        if item:  # 편집 모드인 경우.
            self.txt_desc.insert("1.0", item.desc)  # 기존 설명 채워넣기.

        btns = ttk.Frame(self)  # 버튼들 담을 가로 프레임.
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=10)  # 프레임을 오른쪽에 붙여 배치.
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="right", padx=6)  # 취소 버튼. 누르면 창 닫기.
        ttk.Button(btns, text="저장", command=self._on_save).pack(side="right")  # 저장 버튼. 누르면 _on_save 실행.

        self.update_idletasks()  # 배치/크기 계산 먼저 반영.
        TodoApp.center_over(parent, self)  # 부모창 기준으로 화면 중앙에 위치시키기.
        self.ent_title.focus_set()  # 커서를 제목 입력칸으로 이동.

    def _on_save(self) -> None:  # 저장 버튼 눌렀을 때 하는 일.
        title = self.ent_title.get().strip()  # 제목 텍스트 꺼내고 앞뒤 공백 제거.
        start = self.ent_start.get().strip()  # 시작일 문자열 꺼내기.
        end = self.ent_end.get().strip()  # 종료일 문자열 꺼내기.
        desc = self.txt_desc.get("1.0", "end").strip()  # 텍스트 박스에서 전체 가져와 공백 제거.

        if not title:  # 제목이 비어있으면.
            messagebox.showwarning("확인", "제목을 입력하세요.")  # 경고창 띄우기.
            self.ent_title.focus_set()  # 커서를 제목으로.
            return  # 저장 중단.
        try:  # 시작일 형식 검사.
            d1 = parse_date(start)  # 시작일을 datetime으로 파싱.
        except Exception:  # 실패하면.
            messagebox.showerror("날짜 오류", "시작일 형식이 잘못되었습니다.\n예: 2025-09-16")  # 에러창.
            self.ent_start.focus_set()  # 커서 이동.
            return  # 중단.
        try:  # 종료일 형식 검사.
            d2 = parse_date(end)  # 종료일을 datetime으로 파싱.
        except Exception:  # 실패하면.
            messagebox.showerror("날짜 오류", "종료일 형식이 잘못되었습니다.\n예: 2025-09-18")  # 에러창.
            self.ent_end.focus_set()  # 커서 이동.
            return  # 중단.
        if d2 < d1:  # 종료일이 시작일보다 빠르면 말이 안 됨.
            messagebox.showerror("날짜 오류", "종료일은 시작일보다 빠를 수 없습니다.")  # 에러창.
            self.ent_end.focus_set()  # 커서 이동.
            return  # 중단.

        self.result = Todo(title=title, start=start, end=end, desc=desc, status=self._orig_status)  # 입력값으로 Todo 하나 만들고 결과에 담기.
        self.destroy()  # 창 닫기(대화상자 끝).

class TodoApp(tk.Tk):  # 메인 앱 창. 탭 여러 개 들어가는 윈도우.

    # ─────────────────────────────────────────────────────────
    # [앱 초기화: 메인창 크기/제목 설정, 탭 구성]
    # ─────────────────────────────────────────────────────────
    def __init__(self) -> None:  # 앱 시작할 때 한 번 실행되는 부분.
        super().__init__()  # Tk 윈도우 생성.
        self.title("갓생살기")  # 창 제목 정하기.
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()  # 화면 전체 폭/높이 가져오기.
        x, y = (sw - 580) // 2, (sh - 380) // 2  # 중앙에 오도록 좌표 계산.
        self.geometry(f"580x380+{x}+{y}")  # 창 크기와 위치 지정.

        self.todos: list[Todo] = []  # 할 일들을 담을 리스트. 처음엔 비어 있음.

        self._timer_after_id: str | None = None  # 타이머 루프 after 예약 id 저장. 취소할 때 쓰려고.
        self._blink_after_id: str | None = None  # 깜박임 루프 after 예약 id.
        self.timer_running: bool = False  # 타이머가 동작 중인지 표시.
        self.timer_total_sec: int = 0  # 총 타이머 초.
        self.timer_warn_sec: int = 30  # 경고 시작 기준 초.
        self.timer_end_ts: float = 0.0  # 끝나는 목표 시각(유닉스 타임스탬프).
        self.timer_remain_sec: int = 0  # 남은 초.
        self._blink_on: bool = False  # 빨간색/검은색 번갈아 표시 상태.

        nb = ttk.Notebook(self)  # 탭을 관리하는 노트북 위젯 만들기.
        nb.pack(expand=True, fill="both", padx=10, pady=10)  # 창을 꽉 채우도록 배치.

        self.tab_todo = ttk.Frame(nb)  # 할 일 탭 프레임.
        self.tab_timer = ttk.Frame(nb)  # 타이머 탭 프레임.
        self.tab_grade = ttk.Frame(nb)  # 성적 탭 프레임(아직 빈 껍데기).
        self.tab_report = ttk.Frame(nb)  # 리포트 탭 프레임(아직 빈 껍데기).
        nb.add(self.tab_todo, text="할 일")  # 첫 번째 탭 추가.
        nb.add(self.tab_timer, text="타이머")  # 두 번째 탭 추가.
        nb.add(self.tab_grade, text="성적")  # 세 번째 탭 추가.
        nb.add(self.tab_report, text="리포트")  # 네 번째 탭 추가.

        self._build_todo_tab()  # 할 일 탭 UI 만들기.
        self._build_timer_tab()  # 타이머 탭 UI 만들기.
        ttk.Label(self.tab_grade, text="여기에 '성적' 기능 추가 예정").pack(pady=20)  # 자리 표시 라벨.
        ttk.Label(self.tab_report, text="여기에 '리포트' 기능 추가 예정").pack(pady=20)  # 자리 표시 라벨.

        init_db()                 # [NEW] DB 준비(없으면 생성).
        self.todos = load_all()   # [NEW] DB에서 기존 항목 불러오기.
        self.refresh_list()  # 시작할 때 리스트박스 초기 표시 갱신.

    # ─────────────────────────────────────────────────────────
    # [할 일 탭 UI]
    # ─────────────────────────────────────────────────────────
    def _build_todo_tab(self) -> None:  # 할 일 탭 만들기.
        top = ttk.Frame(self.tab_todo)  # 상단 입력/버튼 영역 프레임.
        top.pack(fill="x", padx=10, pady=10)  # 가로로 꽉 차게 배치.

        self.quick_entry = ttk.Entry(top)  # 빠른 제목 입력칸. 엔터로 바로 추가할 용도.
        self.quick_entry.pack(side="left", fill="x", expand=True)  # 가능한 공간을 넓게 차지.
        self.quick_entry.focus()  # 앱 열자마자 커서를 여기로.
        self.quick_entry.bind("<Return>", lambda e: self.add_todo())  # 엔터 누르면 추가 실행.

        ttk.Button(top, text="추가", command=self.add_todo).pack(side="left", padx=6)  # 추가 버튼. 누르면 대화상자 열기.
        ttk.Button(top, text="편집", command=self.edit_selected).pack(side="left", padx=6)  # 편집 버튼. 선택 항목 수정.
        ttk.Button(top, text="삭제", command=self.delete_selected).pack(side="left", padx=6)  # 삭제 버튼. 선택 항목 삭제.
        ttk.Button(top, text="상태전환 (☐→⏳→✔)", command=self.cycle_status_selected).pack(side="left", padx=6)  # 상태 순환 버튼.

        mid = ttk.Frame(self.tab_todo)  # 가운데 리스트 영역 프레임.
        mid.pack(fill="both", expand=True, padx=10, pady=5)  # 남는 공간을 다 쓰게 배치.

        self.listbox = tk.Listbox(mid, height=10, selectmode="extended")  # 여러 개 선택 가능한 리스트박스.
        self.listbox.pack(side="left", fill="both", expand=True)  # 리스트박스를 크게 배치.

        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)  # 세로 스크롤바.
        scroll.pack(side="left", fill="y")  # 스크롤바를 리스트 옆에 배치.
        self.listbox.config(yscrollcommand=scroll.set)  # 리스트와 스크롤바 서로 연결.

        self.listbox.bind("<Delete>", lambda e: self.delete_selected())  # Delete 키로도 삭제 가능.
        self.listbox.bind("<space>", self._on_space_toggle)  # 스페이스바로 상태 토글.
        self.listbox.bind("<Double-Button-1>", self.show_details)  # 더블클릭하면 상세보기.

    # ─────────────────────────────────────────────────────────
    # [타이머 탭 UI]
    # ─────────────────────────────────────────────────────────
    def _build_timer_tab(self) -> None:  # 타이머 탭 만들기.
        pad = {"padx": 10, "pady": 8}  # 공통 여백 설정.

        top = ttk.Frame(self.tab_timer)  # 상단 입력 영역 프레임.
        top.pack(fill="x", **pad)  # 가로로 꽉 차게 배치.

        ttk.Label(top, text="발표 시간(분)").pack(side="left")  # 분 단위 전체 시간 라벨.
        self.ent_minutes = ttk.Entry(top, width=6)  # 전체 시간 입력칸.
        self.ent_minutes.pack(side="left", padx=(4, 12))  # 라벨 옆에 붙여서 배치.
        self.ent_minutes.insert(0, "5")  # 기본값 5분.

        ttk.Label(top, text="경고 임계(초)").pack(side="left")  # 경고 시작 기준 라벨.
        self.ent_warn = ttk.Entry(top, width=6)  # 경고 기준 초 입력칸.
        self.ent_warn.pack(side="left", padx=(4, 12))  # 라벨 옆에 배치.
        self.ent_warn.insert(0, "30")  # 기본값 30초.

        self.btn_start = ttk.Button(top, text="시작", command=self.start_timer)  # 타이머 시작 버튼.
        self.btn_start.pack(side="left", padx=4)  # 버튼 배치.
        self.btn_pause = ttk.Button(top, text="일시정지", command=self.pause_resume_timer, state="disabled")  # 일시정지/계속 버튼. 처음엔 비활성.
        self.btn_pause.pack(side="left", padx=4)  # 버튼 배치.
        self.btn_reset = ttk.Button(top, text="초기화", command=self.reset_timer, state="disabled")  # 초기화 버튼. 처음엔 비활성.
        self.btn_reset.pack(side="left", padx=4)  # 버튼 배치.

        mid = ttk.Frame(self.tab_timer)  # 가운데 표시 영역 프레임.
        mid.pack(expand=True, fill="both", **pad)  # 공간 채우기.

        self.lbl_timer = tk.Label(mid, text="00:00", font=("Helvetica", 36, "bold"))  # 남은 시간을 크게 보여줄 라벨.
        self.lbl_timer.pack(pady=10)  # 라벨 배치.

        self.pb_timer = ttk.Progressbar(mid, orient="horizontal", mode="determinate", length=360)  # 진행률 바.
        self.pb_timer.pack(fill="x", padx=20, pady=10)  # 가로로 길게 배치.

        bottom = ttk.Frame(self.tab_timer)  # 하단 안내 영역 프레임.
        bottom.pack(fill="x", **pad)  # 가로로 배치.
        ttk.Label(  # 안내 문구 라벨.
            bottom,
            text="Tip) 남은 시간이 임계값 이하로 떨어지면 주황색, 0이 되면 빨간색으로 깜박이며 종료를 알립니다."
        ).pack(anchor="w")  # 왼쪽으로 붙여서 배치.

    # ─────────────────────────────────────────────────────────
    # [헬퍼 함수: 공통 동작 모음 - 선택 확인, 창 중앙 배치, 리스트 갱신]
    # ─────────────────────────────────────────────────────────
    @staticmethod  # 인스턴스 없어도 호출 가능한 정적 메서드로 선언.
    def center_over(parent: tk.Tk, win: tk.Toplevel) -> None:  # 부모창 기준으로 자식창을 중앙에 두는 함수.
        parent.update_idletasks()  # 부모 레이아웃 최신화.
        win.update_idletasks()  # 자식 레이아웃 최신화.
        px, py = parent.winfo_rootx(), parent.winfo_rooty()  # 부모 좌상단 화면 좌표.
        pw, ph = parent.winfo_width(), parent.winfo_height()  # 부모 폭/높이.
        ww, wh = win.winfo_width(), win.winfo_height()  # 자식 폭/높이.
        x = max(0, min(px + (pw - ww) // 2, win.winfo_screenwidth() - ww))  # 화면 밖으로 안 나가게 x 계산.
        y = max(0, min(py + (ph - wh) // 2, win.winfo_screenheight() - wh))  # 화면 밖으로 안 나가게 y 계산.
        win.geometry(f"+{x}+{y}")  # 위치만 지정(크기는 그대로).

    def _selected_indices(self) -> tuple[int, ...] | None:  # 리스트에서 선택한 항목 인덱스들 꺼내는 함수.
        sel = self.listbox.curselection()  # 선택된 인덱스 튜플 가져오기.
        if not sel:  # 하나도 안 골랐으면.
            messagebox.showwarning("확인", "항목을 선택하세요.")  # 경고 띄우기.
            return None  # 없다고 알려주기.
        return sel  # 선택된 인덱스들 반환.

    def refresh_list(self) -> None:  # 리스트박스 내용을 지금 상태에 맞게 다시 채우기.
        self.listbox.delete(0, tk.END)  # 기존 표시 다 지우기.
        if self.todos:  # 할 일이 하나라도 있으면.
            self.listbox.insert(tk.END, *[t.display() for t in self.todos])  # 각 항목의 표시 문자열을 집어넣기.

    def _save(self) -> None:  # [NEW] 현재 리스트를 DB에 반영.
        save_all(self.todos)

    # ─────────────────────────────────────────────────────────
    # [사용자 액션: 추가/편집/삭제/상태전환/상세보기 동작]
    # ─────────────────────────────────────────────────────────
    def add_todo(self) -> None:  # 새 할 일 추가.
        prefill = self.quick_entry.get().strip()  # 위에 빠른 입력칸 내용 미리 가져오기.
        dlg = TodoDialog(self, "할 일 추가", prefill=prefill)  # 대화상자 열기. 기본 제목 넣어주기.
        self.wait_window(dlg)  # 대화상자가 닫힐 때까지 기다리기.
        if dlg.result:  # 저장을 눌러 결과가 있으면.
            self.todos.append(dlg.result)  # 리스트에 추가.
            self._save()  # [NEW] 추가 후 DB 저장.
            self.refresh_list()  # 화면 갱신.

    def edit_selected(self) -> None:  # 선택한 항목 편집.
        sel = self._selected_indices()  # 선택 확인.
        if not sel:  # 선택이 없으면.
            return  # 그냥 끝.
        idx = sel[0]  # 여러 개라도 첫 번째 것만 편집.
        dlg = TodoDialog(self, "할 일 편집", item=self.todos[idx])  # 기존 항목 넘겨서 대화상자 열기.
        self.wait_window(dlg)  # 닫힐 때까지 대기.
        if dlg.result:  # 결과가 있으면.
            self.todos[idx] = dlg.result  # 해당 위치에 새 값 덮어쓰기.
            self._save()  # [NEW] 편집 후 DB 저장.
            self.refresh_list()  # 화면 갱신.

    def delete_selected(self) -> None:  # 선택 항목 삭제.
        sel = self._selected_indices()  # 선택 확인.
        if not sel:  # 없으면.
            return  # 끝.
        if not messagebox.askyesno("삭제 확인", f"선택한 {len(sel)}개 항목을 정말 삭제할까요?"):  # 진짜 지울지 물어보기.
            return  # 아니오면 취소.
        for i in reversed(sel):  # 뒤에서부터 지워야 인덱스 안 꼬임.
            del self.todos[i]  # 해당 항목 삭제.
        self._save()  # [NEW] 삭제 후 DB 저장.
        self.refresh_list()  # 화면 갱신.

    def cycle_status_selected(self) -> None:  # 선택 항목들의 상태를 한 칸씩 넘기기.
        sel = self._selected_indices()  # 선택 확인.
        if not sel:  # 없으면.
            return  # 끝.
        for i in sel:  # 선택된 각 인덱스에 대해.
            self.todos[i].cycle()  # 상태 순환.
        self._save()  # [NEW] 상태 전환 후 DB 저장.
        self.refresh_list()  # 화면 갱신.

    def _on_space_toggle(self, _e) -> str:  # 스페이스바 눌렀을 때 핸들러.
        self.cycle_status_selected()  # 상태 전환 실행.
        return "break"  # 기본 스페이스 동작(선택 이동) 막기.

    def show_details(self, _e=None) -> None:  # 선택 항목 상세 정보 팝업.
        sel = self._selected_indices()  # 선택 확인.
        if not sel:  # 없으면.
            return  # 끝.
        t = self.todos[sel[0]]  # 첫 번째 선택 항목 가져오기.
        icon = STATUS_ICON.get(t.status, "☐")  # 상태 아이콘.
        msg = (  # 팝업에 보여줄 문자열 만들기.
            f"제목: {t.title}\n"
            f"기간: {t.start} ~ {t.end}\n"
            f"상태: {icon} {STATUS_TEXT.get(t.status,'')}\n\n"
            f"상세설명:\n{t.desc or '(없음)'}"
        )
        messagebox.showinfo("할 일 상세", msg)  # 정보 팝업 띄우기.

    # ─────────────────────────────────────────────────────────
    # [타이머 로직]
    # ─────────────────────────────────────────────────────────
    def _format_sec(self, s: int) -> str:  # 초를 "MM:SS" 문자열로 만드는 함수.
        s = max(0, int(s))  # 0보다 작아지지 않게 보정하고 정수로.
        m, ss = divmod(s, 60)  # 분과 초로 나누기.
        return f"{m:02d}:{ss:02d}"  # 2자리 형식으로 반환.

    def _set_timer_controls_running(self, running: bool) -> None:  # 타이머 상태에 따라 버튼/입력칸 활성화 조절.
        if running:  # 타이머 도는 중.
            self.btn_start.config(state="disabled")  # 시작 버튼 비활성.
            self.btn_pause.config(state="normal", text="일시정지")  # 일시정지 버튼 활성/텍스트 설정.
            self.btn_reset.config(state="normal")  # 초기화 버튼 활성.
            self.ent_minutes.config(state="disabled")  # 시간 입력칸 잠그기.
            self.ent_warn.config(state="disabled")  # 경고 입력칸 잠그기.
        else:  # 멈춘 상태.
            self.btn_start.config(state="normal")  # 시작 버튼 활성.
            self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 버튼 비활성/텍스트 되돌리기.
            self.btn_reset.config(state="disabled")  # 초기화 버튼 비활성.
            self.ent_minutes.config(state="normal")  # 시간 입력칸 열기.
            self.ent_warn.config(state="normal")  # 경고 입력칸 열기.

    def _stop_tick_loop(self) -> None:  # after로 예약한 타이머 업데이트 멈추기.
        if self._timer_after_id is not None:  # 예약 id가 있으면.
            try:  # 혹시 이미 취소됐을 수 있으니 안전하게.
                self.after_cancel(self._timer_after_id)  # 예약 취소.
            except Exception:  # 실패해도 앱 안 죽게 무시.
                pass  # 아무 것도 안 함.
            self._timer_after_id = None  # id 비우기.

    def _stop_blink(self) -> None:  # 깜박임 루프 멈추기.
        if self._blink_after_id is not None:  # 예약 id 있으면.
            try:  # 안전 취소.
                self.after_cancel(self._blink_after_id)  # 예약 취소.
            except Exception:  # 실패해도 무시.
                pass  # 그대로 두기.
            self._blink_after_id = None  # id 비우기.
        self._blink_on = False  # 깜박 상태 리셋.
        self.lbl_timer.config(fg="black")  # 글자색을 검정으로 되돌리기.

    def _start_blink(self) -> None:  # 0초 되었을 때 빨강/검정 번갈이로 깜박이기 시작.
        self._blink_on = not self._blink_on  # 상태 토글.
        self.lbl_timer.config(fg=("red" if self._blink_on else "black"))  # 빨강/검정 바꾸기.
        self._blink_after_id = self.after(450, self._start_blink)  # 0.45초마다 재실행 예약.

    def start_timer(self) -> None:  # 시작 버튼 눌렀을 때.
        self._stop_tick_loop()  # 혹시 돌던 루프 있으면 멈추기.
        self._stop_blink()  # 깜박임도 멈추기.

        try:  # 분 입력값 숫자인지 확인.
            minutes = float(self.ent_minutes.get().strip())  # 문자열을 실수로 변환(7.5 같은 것도 허용).
        except Exception:  # 숫자 아니면.
            messagebox.showerror("입력 오류", "발표 시간(분)을 숫자로 입력하세요. 예: 5 또는 7.5")  # 에러 알림.
            self.ent_minutes.focus_set()  # 커서 이동.
            return  # 시작 중단.
        if minutes <= 0:  # 0 이하이면 말이 안 됨.
            messagebox.showerror("입력 오류", "발표 시간(분)은 0보다 커야 합니다.")  # 에러 알림.
            self.ent_minutes.focus_set()  # 커서 이동.
            return  # 중단.

        try:  # 경고 초 숫자 확인.
            warn = int(self.ent_warn.get().strip())  # 정수로 변환.
        except Exception:  # 실패하면.
            messagebox.showerror("입력 오류", "경고 임계(초)를 정수로 입력하세요. 예: 30")  # 에러 알림.
            self.ent_warn.focus_set()  # 커서 이동.
            return  # 중단.
        if warn < 1:  # 1초 이하는 의미 없음.
            messagebox.showerror("입력 오류", "경고 임계(초)는 1초 이상이어야 합니다.")  # 에러 알림.
            self.ent_warn.focus_set()  # 커서 이동.
            return  # 중단.

        total_sec = int(round(minutes * 60))  # 총 초로 바꾸고 반올림해서 정수 만들기.
        self.timer_total_sec = total_sec  # 총 시간 저장.
        self.timer_warn_sec = min(warn, max(1, total_sec - 1))  # 경고 초는 총 시간보다 작게, 최소 1초 보장.

        self.timer_running = True  # 타이머 시작 상태로.
        self.timer_end_ts = time.time() + self.timer_total_sec  # 지금 시각 + 총 시간 = 종료 목표 시각.
        self.timer_remain_sec = self.timer_total_sec  # 남은 시간 초기화.
        self.lbl_timer.config(text=self._format_sec(self.timer_remain_sec), fg="black")  # 라벨 초기 표시.
        self.pb_timer.config(maximum=self.timer_total_sec, value=0)  # 프로그레스바 최대/현재값 설정.

        self._set_timer_controls_running(True)  # 버튼/입력칸 상태 갱신.
        self._tick_update()  # 주기 업데이트 루프 시작.

    def pause_resume_timer(self) -> None:  # 일시정지/계속 버튼 동작.
        if not self.timer_running:  # 현재 멈춰있는 상태면 = 계속 누른 것.
            if self.timer_remain_sec <= 0:  # 이미 끝난 상태면 할 것 없음.
                return  # 그냥 끝.
            self.timer_end_ts = time.time() + self.timer_remain_sec  # 지금 기준으로 종료 목표 다시 잡기.
            self.timer_running = True  # 다시 달리기.
            self.btn_pause.config(text="일시정지")  # 버튼 텍스트 되돌리기.
            self._tick_update()  # 루프 재시작.
            return  # 처리 끝.

        now = time.time()  # 현재 시각.
        remain = max(0, int(math.ceil(self.timer_end_ts - now)))  # 남은 초 계산해서 올림. 음수면 0으로.
        self.timer_remain_sec = remain  # 남은 초 저장.
        self.timer_running = False  # 일시정지 상태로 전환.
        self.btn_pause.config(text="계속")  # 버튼 텍스트 바꾸기.
        self._stop_tick_loop()  # 주기 업데이트 멈추기.

    def reset_timer(self) -> None:  # 초기화 버튼 동작.
        self.timer_running = False  # 멈추기.
        self.timer_total_sec = 0  # 총 시간 리셋.
        self.timer_remain_sec = 0  # 남은 시간 리셋.
        self.timer_end_ts = 0.0  # 목표 시각 리셋.
        self._stop_tick_loop()  # 주기 업데이트 취소.
        self._stop_blink()  # 깜박임 취소.
        self.lbl_timer.config(text="00:00", fg="black")  # 라벨 초기화.
        self.pb_timer.config(maximum=100, value=0)  # 프로그레스바 초기화(대충 100 기준).
        self._set_timer_controls_running(False)  # 버튼/입력칸 상태 되돌리기.

    def _on_time_up(self) -> None:  # 시간이 0이 되었을 때 처리.
        self.timer_running = False  # 멈추기.
        self._stop_tick_loop()  # 루프 취소.
        self.lbl_timer.config(text="00:00", fg="red")  # 라벨은 00:00 빨간색으로.
        self.pb_timer.config(value=self.timer_total_sec)  # 프로그레스바를 꽉 채우기.
        try:  # 시스템 종소리 같은 거 울리기.
            self.bell()  # 삐 소리.
        except Exception:  # 소리 실패해도 무시.
            pass  # 그냥 넘어가기.
        self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 버튼 끄기.
        self._start_blink()  # 빨강/검정 깜박임 시작.

    def _tick_update(self) -> None:  # 0.2초마다 남은 시간 갱신하는 루프.
        if not self.timer_running:  # 돌고 있지 않으면.
            return  # 아무 것도 안 함.

        now = time.time()  # 현재 시각.
        remain = int(max(0, math.ceil(self.timer_end_ts - now)))  # 남은 초 계산(올림) 후 음수 방지.
        self.timer_remain_sec = remain  # 저장.

        self.lbl_timer.config(text=self._format_sec(remain))  # 라벨 텍스트 갱신.

        if remain == 0:  # 다 됨.
            self._on_time_up()  # 종료 처리.
            return  # 여기서 끝.
        elif remain <= self.timer_warn_sec:  # 경고 구간 진입.
            self.lbl_timer.config(fg="orange")  # 글자색 주황.
        else:  # 아직 여유.
            self.lbl_timer.config(fg="black")  # 글자색 검정.

        done = self.timer_total_sec - remain  # 얼마나 진행됐는지 계산.
        self.pb_timer.config(value=done)  # 프로그레스바 채우기.

        self._timer_after_id = self.after(200, self._tick_update)  # 0.2초 뒤에 다시 실행 예약.

# ─────────────────────────────────────────────────────────
# 앱 실행
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":  # 이 파일을 직접 실행할 때만 아래 실행.
    app = TodoApp()  # 앱 인스턴스 만들기.
    app.mainloop()  # Tk 이벤트 루프 시작. 창이 닫힐 때까지 여기서 대기.
