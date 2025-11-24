# main.py  --------------------------------------------------
# 최상위 Tk 앱을 생성하고, 각 탭 프레임을 Notebook 에 붙이며,
# 숨은 AI 도우미(우하단 '✨ 도우미')와 ToDo/타이머/리포트/대시보드 탭을 연결하는 파일이다.

from __future__ import annotations  # 타입을 문자열로 참조 허용

import json  # AI 컨텍스트를 JSON 문자열로 만들 때 사용
import threading  # OpenAI API 호출을 백그라운드 스레드에서 실행
from datetime import date  # 오늘 날짜 계산에 사용
import os  # 환경변수에서 OPENAI_API_KEY 읽기
import tkinter as tk  # Tkinter 기본 위젯
from tkinter import ttk, messagebox  # ttk 스타일 + 메시지 박스

from core import (  # 공통 모듈에서 기능 import
    DATE_FMT,            # 날짜 포맷(실제 사용은 Todo.display 쪽)
    STATUS_ICON,         # 상태 아이콘(직접 쓰지는 않지만 컨텍스트 등에서 사용 가능)
    STATUS_TEXT,         # 상태 텍스트
    PAD6, PAD8,          # 여백 설정(일부는 각 탭에서 직접 사용)
    parse_date,          # 날짜 파싱
    center_over,         # 팝업 위치 조정
    init_db,             # DB 초기화
    load_all,            # Todo 전체 로드
    save_all,            # Todo 전체 저장(폴백/일괄 저장 시 사용 가능)
    _http_post,          # OpenAI API 호출용 HTTP POST
    Todo,                # Todo 데이터 모델
)
from tab_todo import TodoTab  # 할 일 탭 프레임
from tab_timer import TimerTab  # 타이머 탭 프레임
from tab_report import ReportTab  # 리포트 탭 프레임
from tab_dashboard import DashboardTab  # 대시보드 탭 프레임


# ─────────────────────────────────────────────
# OpenAI Chat Completions 설정 (AI 도우미용)
# ─────────────────────────────────────────────

OPENAI_URL_CHAT = "https://api.openai.com/v1/chat/completions"  # Chat API 엔드포인트
ASSIST_MODEL_DEFAULT = "gpt-4o-mini"  # 빠르고 저렴한 경량 모델
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "realkey")  # 환경변수 또는 기본값
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "realkey")  # 환경변수 또는 기본값
ASSIST_TIMEOUT = 40  # AI 도우미 호출 타임아웃(초)


# ─────────────────────────────────────────────
# UI 스타일 설정 (Global)
# ─────────────────────────────────────────────

def configure_app_style():
    """앱 전체에 적용될 Soft Modern 스타일 설정."""
    style = ttk.Style()
    
    # 1. 색상 팔레트 (Soft Modern)
    ACCENT_COLOR = "#3F51B5"        # 인디고 (강조색)
    ACCENT_LIGHT = "#E8EAF6"        # 연한 인디고 (선택 배경)
    BG_COLOR = "#F5F7FA"            # 쿨 그레이 (전체 배경)
    CARD_BG = "#FFFFFF"             # 카드 배경
    BORDER_COLOR = "#E0E0E0"        # 카드 테두리
    
    TEXT_MAIN = "#263238"           # 진한 슬레이트
    TEXT_SUB = "#546E7A"            # 중간 슬레이트
    
    BTN_BG = "#E3F2FD"              # 버튼 배경 (소프트 블루)
    BTN_HOVER = "#BBDEFB"           # 버튼 호버
    BTN_TEXT = "#1565C0"            # 버튼 텍스트
    
    HEADER_BG = "#FAFAFA"           # 헤더 배경

    # 2. 폰트 정의 (Segoe UI)
    FONT_TITLE = ("Segoe UI", 14, "bold")
    FONT_HEADER = ("Segoe UI", 11, "bold")
    FONT_BODY = ("Segoe UI", 10)
    FONT_SMALL = ("Segoe UI", 9)

    # 3. 공통 스타일 설정
    style.configure("TFrame", background=BG_COLOR)
    
    # Card Style (No Border for cleaner look)
    style.configure(
        "Card.TFrame", 
        background=CARD_BG,
        relief="flat",
        borderwidth=0
    )
    
    # Card Plain (No Border, White BG) - For inner layouts
    style.configure(
        "CardPlain.TFrame",
        background=CARD_BG,
        borderwidth=0,
        relief="flat"
    )
    
    # Accent Strip
    style.configure("Accent.TFrame", background=ACCENT_COLOR)
    # Treeview (Dashboard Style)
    style.configure(
        "Dashboard.Treeview",
        font=FONT_BODY,
        rowheight=38,
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


# ─────────────────────────────────────────────
# 메인 앱 클래스
# ─────────────────────────────────────────────

class MainApp(tk.Tk):
    """Notebook 과 4개 탭, 그리고 숨은 AI 도우미를 관리하는 최상위 Tk 앱."""

    def __init__(self) -> None:
        super().__init__()  # Tk 루트 윈도우 초기화

        self.title("갓생살기")  # 윈도우 제목
        
        # 스타일 설정 적용
        configure_app_style()
        
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()  # 화면 해상도
        x, y = (sw - 1100) // 2, (sh - 750) // 2  # 중앙 근처 위치 계산
        self.geometry(f"1100x750+{x}+{y}")  # 윈도우 크기/위치 지정

        self.protocol("WM_DELETE_WINDOW", self._on_close)  # 닫기 버튼 클릭 시 핸들러

        # AI 도우미 관련 상태
        self._assist_busy: bool = False  # 중복 호출 방지 플래그
        self._assist_thread: threading.Thread | None = None  # 백그라운드 스레드 핸들
        self._assistant_last_tip: str = ""  # 마지막 ToDo 추천 문구 캐시
        self._assistant_popup: tk.Toplevel | None = None  # 도우미 팝업 핸들

        # API 키가 제대로 설정되어 있으면 True
        self.assist_enabled: bool = bool(
            OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_OPENAI_API_KEY"
        )

        # Todo 리스트를 DB 에서 로드
        init_db()  # 테이블 보장
        self.todos: list[Todo] = load_all()  # 현재 Todo 목록(모든 탭과 공유)

        # Notebook 생성 및 탭 프레임 추가
        nb = ttk.Notebook(self)
        nb.pack(expand=True, fill="both", padx=10, pady=10)

        # 할 일 탭: TodoTab 에 Todo 리스트와 변경 콜백, AI 새로고침 콜백 전달
        self.tab_todo = TodoTab(
            nb,
            self.todos,
            on_todos_changed=self._on_todos_changed,
            on_request_ai_refresh=self._ai_refresh_todo_tip,
        )

        # 타이머 탭: TimerTab 에 타이머 시작 콜백(AI 코칭)을 전달
        self.tab_timer = TimerTab(
            nb,
            on_started=self._ai_timer_tip_once,
        )

        # 리포트 탭: ReportTab 에 Todo 리스트와 '제목으로 편집 요청' 콜백 전달
        self.tab_report = ReportTab(
            nb,
            self.todos,
            on_request_edit=self._edit_todo_by_title,
        )

        # 대시보드 탭: 내부에 또 하나의 Notebook 을 가지는 프레임
        self.tab_dashboard = DashboardTab(nb)

        # Notebook 에 실제 탭으로 추가
        nb.add(self.tab_dashboard, text="대시보드")
        nb.add(self.tab_todo, text="할 일")
        nb.add(self.tab_timer, text="타이머")
        nb.add(self.tab_report, text="리포트")

        # 할 일 리스트/리포트 초기 렌더링
        self.tab_todo.refresh_list()
        # ReportTab 은 __init__ 에서 이미 refresh_now 를 수행하지만, 다시 호출해도 무방
        self.tab_report.refresh_now()

        # 우측 하단 '✨ 도우미' 도크 버튼 생성
        self._build_assistant_dock()

        # 앱 시작 직후 ToDo 컨텍스트 기반 AI 추천 자동 요청
        self.after(700, self._ai_refresh_todo_tip)

    # -----------------------------
    # Todo 변경 → 리포트/AI 갱신
    # -----------------------------
    def _on_todos_changed(self) -> None:
        """
        할 일 탭에서 Todo 가 추가/편집/삭제/상태전환 되면 호출된다.
        - 리포트 탭 리프레시
        - ToDo 추천 AI 문구 재요청
        """
        self.tab_report.refresh_now()  # 통계/시각화 즉시 갱신
        # 약간의 딜레이 후 AI 추천 요청(여러 변경을 한 번에 묶는 효과)
        self.after(250, self._ai_refresh_todo_tip)

    # -----------------------------
    # 대시보드 → Todo 편집 요청 처리
    # -----------------------------
    def _edit_todo_by_title(self, title: str) -> None:
        """
        리포트 탭의 요일 상세 팝업 등에서 '선택 편집'을 눌렀을 때
        제목으로 Todo 를 찾아 할 일 탭에서 편집 다이얼로그를 띄운다.
        """
        idx = next((i for i, t in enumerate(self.todos) if t.title == title), None)
        if idx is None:
            return  # 해당 제목의 Todo 를 찾지 못하면 아무것도 하지 않음
        self.tab_todo.select_and_edit_index(idx)  # 할 일 탭에 편집을 위임

    # -----------------------------
    # 우하단 '✨ 도우미' 도크/팝업
    # -----------------------------
    def _build_assistant_dock(self) -> None:
        """우하단에 '✨ 도우미' 버튼을 띄우고 Ctrl+K 단축키로 토글한다."""
        dock = ttk.Frame(self)  # 도크용 프레임
        dock.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")  # 우하단 모서리에 부착

        self.btn_assist = ttk.Button(
            dock,
            text="✨ 도우미",
            command=self._toggle_assistant_popup,
        )
        self.btn_assist.pack()

        self.update_idletasks()  # 실제 위젯 크기 계산
        # 버튼 크기를 가지고 ToDo 하단 'AI 추천 새로고침' 버튼과 겹치지 않게 패딩 조정
        self._assist_btn_w = self.btn_assist.winfo_width()
        self._assist_btn_h = self.btn_assist.winfo_height()

        self._reflow_for_dock()  # 초기 배치 보정
        self.bind("<Configure>", lambda e: self._reflow_for_dock())  # 창 크기 변경 시 재보정
        self.bind_all("<Control-k>", lambda e: self._toggle_assistant_popup())  # Ctrl+K 단축키

    def _reflow_for_dock(self) -> None:
        """도우미 버튼과 ToDo 탭 AI 새로고침 버튼이 겹치지 않도록 패딩을 동적으로 조정한다."""
        try:
            self.update_idletasks()  # 최신 크기 반영
            dock_w = (self.btn_assist.winfo_width() or 80)  # 도우미 버튼 폭
            right_pad = max(10, dock_w + 18)  # 우측 패딩(여유 포함)
            # TodoTab 에 있는 AI 새로고침 버튼의 오른쪽 여백을 늘려서 겹침 방지
            if hasattr(self, "tab_todo") and hasattr(self.tab_todo, "btn_ai_tip_refresh"):
                self.tab_todo.btn_ai_tip_refresh.pack_configure(padx=(8, right_pad))
        except Exception:
            pass  # 초기 레이아웃 타이밍 이슈 등은 무시

    def _toggle_assistant_popup(self) -> None:
        """도우미 팝업을 토글(없으면 생성, 있으면 닫기)한다."""
        if self._assistant_popup and self._assistant_popup.winfo_exists():
            # 이미 열려 있으면 닫기
            self._assistant_popup.destroy()
            self._assistant_popup = None
            return

        pop = tk.Toplevel(self)  # 새 팝업 생성
        pop.title("✨ 도우미")  # 제목
        pop.resizable(False, False)  # 크기 고정
        pop.transient(self)  # 메인 윈도우 앞에 표시
        self._assistant_popup = pop  # 핸들 저장

        frm = ttk.Frame(pop)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(
            frm,
            text="현재 탭 컨텍스트를 바탕으로 질문하거나, '컨텍스트 분석'으로 제안을 받아보세요.",
        ).pack(anchor="w", pady=(0, 6))

        # 질문 입력 텍스트 박스
        self.txt_ask = tk.Text(frm, width=46, height=4, wrap="word")
        self.txt_ask.pack(fill="x")

        row = ttk.Frame(frm)
        row.pack(fill="x", pady=(6, 0))

        # 컨텍스트 분석 버튼(사용자 질문 없이 현재 상태만으로 제안 요청)
        ttk.Button(
            row,
            text="컨텍스트 분석",
            command=self._assistant_analyze_context,
        ).pack(side="left")

        # 사용자 질문 전송 버튼
        ttk.Button(
            row,
            text="보내기",
            command=self._assistant_send_prompt,
        ).pack(side="right")

        # 응답 표시 텍스트 박스(읽기 전용)
        self.txt_ans = tk.Text(frm, width=46, height=10, wrap="word", state="disabled")
        self.txt_ans.pack(fill="both", expand=True, pady=(8, 0))

        center_over(self, pop)  # 메인 윈도우 기준 중앙 배치

    def _assistant_append_text(self, text: str) -> None:
        """도우미 팝업의 응답 영역에 텍스트를 추가한다."""
        if not (self._assistant_popup and self._assistant_popup.winfo_exists()):
            return  # 팝업이 없으면 아무 것도 하지 않음
        self.txt_ans.config(state="normal")  # 편집 가능 상태로 전환
        self.txt_ans.insert("end", text + "\n")  # 텍스트 추가
        self.txt_ans.see("end")  # 스크롤을 맨 아래로 이동
        self.txt_ans.config(state="disabled")  # 다시 읽기 전용으로 잠금

    def _assistant_send_prompt(self) -> None:
        """사용자 질문과 현재 컨텍스트를 결합해 AI 도우미에 질의한다."""
        if not (self._assistant_popup and self._assistant_popup.winfo_exists()):
            return  # 팝업이 닫혀있으면 아무 것도 하지 않음

        prompt = self.txt_ask.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("확인", "질문을 입력하세요.", parent=self._assistant_popup)
            return

        ctx = self._compose_context_for_active_tab()  # 현재 탭/상태 요약(JSON 문자열)
        user_prompt = (
            "다음 컨텍스트를 참고하여 한국어로 간단하고 실용적인 조언을 주세요.\n\n"
            f"컨텍스트(JSON):\n{ctx}\n\n질문:\n{prompt}"
        )
        self._assistant_call_async(user_prompt, purpose="popup")

    def _assistant_analyze_context(self) -> None:
        """사용자 질문 없이 현재 컨텍스트만으로 '바로 실행할 3가지 제안'을 요청한다."""
        ctx = self._compose_context_for_active_tab()
        prompt = (
            "다음 컨텍스트를 바탕으로 '바로 실행할 3가지 제안'과 '근거'를 "
            "한국어 목록으로 요약하세요. 가능하면 작업 이름을 직접 언급하고, "
            "마감 임박/지남/진행중 우선순위를 반영하세요.\n\n"
            f"{ctx}"
        )
        self._assistant_call_async(prompt, purpose="popup")

    # -----------------------------
    # AI 호출 로직
    # -----------------------------
    def _assistant_available(self) -> bool:
        """AI 도우미 사용 가능 여부(키 설정 여부)를 반환한다."""
        return self.assist_enabled

    def _assistant_call(
        self,
        user_prompt: str,
        system_prompt: str = "너는 일정·태스크 관리 코치다. 한국어로 간결하고 실용적인 조언만 제공하라.",
        temperature: float = 0.6,
    ) -> tuple[bool, str]:
        """
        OpenAI Chat Completions 를 동기적으로 호출한다.
        성공 시 (True, 메시지), 실패 시 (False, 에러/메시지) 반환.
        """
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}  # 인증 헤더
        data = {
            "model": ASSIST_MODEL_DEFAULT,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        code, text = _http_post(
            OPENAI_URL_CHAT,
            headers=headers,
            data=data,
            timeout=ASSIST_TIMEOUT,
        )
        if code == 200:
            try:
                obj = json.loads(text)
                msg = (obj.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
                if not msg:
                    return False, "빈 응답입니다."
                return True, msg
            except Exception as e:
                return False, f"응답 파싱 실패: {e}"
        else:
            try:
                err = json.loads(text).get("error", {}).get("message", text)
            except Exception:
                err = text
            return False, f"오류 {code}: {err}"

    def _assistant_call_async(self, prompt: str, purpose: str = "todo_tip") -> None:
        """
        AI 도우미를 별도 스레드에서 호출하고,
        purpose 에 따라 ToDo 라벨/팝업/타이머 코칭 등 적절한 UI 에 반영한다.
        """
        if self._assist_busy:  # 이미 호출 중이면 중복으로 호출하지 않음
            return
        self._assist_busy = True  # 호출 중 플래그 설정

        def worker() -> None:
            """실제 네트워크 호출을 수행하는 백그라운드 함수."""
            if not self._assistant_available():  # 키가 없거나 오프라인인 경우
                ok, msg = False, self._local_fallback_advice(purpose)  # 로컬 폴백 메시지
            else:
                ok, msg = self._assistant_call(prompt)  # OpenAI API 호출

            def ui_update() -> None:
                """메인 스레드에서 UI 를 업데이트한다."""
                self._assist_busy = False  # 호출 중 상태 해제
                if purpose == "todo_tip":
                    self._assistant_last_tip = msg  # 마지막 추천 캐시
                    self.tab_todo.set_ai_tip(msg, ok)  # ToDo 탭 하단 라벨에 표시
                elif purpose == "popup":
                    self._assistant_append_text(msg)  # 도우미 팝업에 텍스트 추가
                elif purpose == "timer_tip":
                    self.tab_timer.set_ai_tip(msg)  # 타이머 탭 코칭 문구 표시

            self.after(0, ui_update)  # Tk 이벤트 루프로 UI 업데이트 예약

        self._assist_thread = threading.Thread(target=worker, daemon=True)
        self._assist_thread.start()

    # -----------------------------
    # AI 컨텍스트 생성 (전체 탭 요약)
    # -----------------------------
    def _compose_context_for_active_tab(self) -> str:
        """
        ToDo/타이머/리포트 상태를 JSON 문자열로 요약해 반환한다.
        - selected: 현재 ToDo 탭에서 선택된 작업 제목들
        - counts, soon, overdue, rate: 리포트 통계
        - timer: 타이머 실행 상태
        - top_items: Todo 리스트 상위 10개 요약
        """
        selected_titles = self.tab_todo.get_selected_titles()  # 선택된 할 일 제목 리스트

        stats = self.tab_report.calc_report_stats()  # 최신 통계 계산
        timer_state = self.tab_timer.get_state_for_ai()  # 타이머 상태 요약

        ctx = {
            "tab": "todo/timer/report(unified)",  # 현재 앱의 탭 구조 요약
            "todos_total": len(self.todos),  # Todo 총 개수
            "selected": selected_titles,  # 현재 선택된 Todo 들의 제목
            "counts": {
                "open": stats["counts"][0],
                "doing": stats["counts"][1],
                "done": stats["counts"][2],
            },
            "soon": stats["soon"],
            "overdue": stats["overdue"],
            "rate": stats["rate"],
            "timer": timer_state,
            "top_items": [
                {"title": t.title, "end": t.end, "status": t.status}
                for t in self.todos[:10]
            ],
        }
        return json.dumps(ctx, ensure_ascii=False, indent=2)

    # -----------------------------
    # AI 컨텍스트 생성 (ToDo 전용)
    # -----------------------------
    def _compose_context_for_todo_tip(self) -> str:
        """
        ToDo 탭 하단 추천 라벨을 위한 전용 컨텍스트(JSON 문자열)를 생성한다.
        - 각 작업별 D-day, 상태, 제목 등을 포함한다.
        """
        today = date.today()
        items = []

        for t in self.todos:
            try:
                d2 = parse_date(t.end).date()
                days = (d2 - today).days
            except Exception:
                days = None
            items.append(
                {
                    "title": t.title,
                    "end": t.end,
                    "status": STATUS_TEXT.get(t.status, ""),
                    "dday": days,
                }
            )

        ctx = {
            "total": len(self.todos),
            "imminent": sum(
                1
                for it in items
                if it["dday"] is not None
                and 0 <= it["dday"] <= 3
                and it["status"] != "완료"
            ),
            "overdue": sum(
                1
                for it in items
                if it["dday"] is not None
                and it["dday"] < 0
                and it["status"] != "완료"
            ),
            "items": items,
        }
        return json.dumps(ctx, ensure_ascii=False, indent=2)

    # -----------------------------
    # ToDo 하단 AI 추천 라벨 갱신
    # -----------------------------
    def _ai_refresh_todo_tip(self) -> None:
        """ToDo 탭 하단 AI 추천 라벨을 새로고침한다."""
        ctx = self._compose_context_for_todo_tip()
        prompt = (
            "다음 ToDo 목록 컨텍스트를 참고해 '지금 바로 할 3가지 액션'을 "
            "한국어로 제안하고, 각 항목에 한 줄 근거를 붙이세요. "
            "지남/임박 항목에 우선순위를 두고, 진행중인 항목은 다음 체크포인트를 제시하세요.\n\n"
            + ctx
        )
        self._assistant_call_async(prompt, purpose="todo_tip")

    # -----------------------------
    # 타이머 시작 시 한 줄 코칭
    # -----------------------------
    def _ai_timer_tip_once(self) -> None:
        """타이머가 새로 시작될 때 한 줄 코칭 문구를 요청한다."""
        state = self.tab_timer.get_state_for_ai()
        prompt = (
            f"발표 타이머가 {state['total_sec']}초로 시작했습니다. "
            f"경고 임계 {state['warn_sec']}초입니다. "
            "남은 시간 신호에 맞춰 마무리 루틴을 1~2문장으로 조언해 주세요(한국어)."
        )
        self._assistant_call_async(prompt, purpose="timer_tip")

    # -----------------------------
    # API 키 미설정/오프라인 폴백 추천
    # -----------------------------
    def _local_fallback_advice(self, purpose: str) -> str:
        """
        OpenAI API 키가 없거나 네트워크가 불안정한 경우,
        간단한 규칙 기반으로 ToDo/타이머 추천 문구를 생성한다.
        """
        today = date.today()
        scored: list[tuple[int, Todo]] = []

        for t in self.todos:
            try:
                d2 = parse_date(t.end).date()
                days = (d2 - today).days
            except Exception:
                days = 9999  # 날짜 이상치면 가장 낮은 우선순위로 취급

            # 마감 초과>임박>진행중>그 외 순으로 점수 부여(값이 작을수록 우선순위 높음)
            if t.status != 2 and days < 0:
                score = -1000  # 마감 초과
            elif t.status != 2 and 0 <= days <= 3:
                score = -500  # 3일 이내 마감
            elif t.status == 1:
                score = -200  # 진행중
            else:
                score = -50   # 나머지

            scored.append((score, t))

        scored.sort(key=lambda x: x[0])
        top = [s[1] for s in scored[:3]]  # 상위 3개만 추출

        if purpose == "timer_tip":
            # 타이머 전용 폴백 문구
            return "⏱️ 발표는 끝맺음이 중요합니다. 마지막 30초엔 핵심 요약→콜투액션 순으로 마무리해 보세요."

        lines: list[str] = []
        for t in top:
            try:
                d2 = parse_date(t.end).date()
                days = (d2 - today).days
            except Exception:
                days = None

            if days is not None and days < 0 and t.status != 2:
                tag = "지남"
                why = "마감 초과"
            elif days is not None and 0 <= days <= 3 and t.status != 2:
                tag = "임박"
                why = "3일 내 마감"
            else:
                tag = "일반"
                why = "현재 우선순위 상위"

            lines.append(
                f"• {t.title} → 지금 15분만 투자해서 다음 체크포인트 정의 ({why})"
            )

        if not lines:
            lines = [
                "• 오늘은 새 작업을 추가하기보다 완료율을 높여보세요(작은 항목 1~2개 마무리)."
            ]

        return "키 미설정/오프라인 폴백 제안:\n" + "\n".join(lines)

    # -----------------------------
    # 종료 처리
    # -----------------------------
    def _on_close(self) -> None:
        """타이머/리포트 루프와 도우미 팝업을 정리한 뒤 메인 윈도우를 닫는다."""
        try:
            self.tab_timer.on_close()  # 타이머 after 루프 정리
        except Exception:
            pass
        try:
            self.tab_report.on_close()  # 리포트 after 루프 정리
        except Exception:
            pass

        if self._assistant_popup and self._assistant_popup.winfo_exists():
            try:
                self._assistant_popup.destroy()
            except Exception:
                pass

        self.destroy()  # Tk 메인 윈도우 파괴 → 앱 종료


# ─────────────────────────────────────────────
# 실행 엔트리포인트
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app = MainApp()  # 메인 앱 인스턴스 생성
    app.mainloop()   # Tk 이벤트 루프 시작
