# tab_todo.py  --------------------------------------------------
# "할 일" 탭과 할 일 추가/편집용 TodoDialog 를 담당하는 모듈이다.

from __future__ import annotations  # 앞으로 나올 타입을 문자열로 참조 허용

from datetime import date  # 오늘 날짜 기본값을 설정할 때 사용
import tkinter as tk  # Tkinter 기본 위젯
from tkinter import ttk, messagebox  # ttk 스타일 위젯 + 메시지 박스

from core import (  # core.py 에서 공통 기능 import
    PAD6,             # grid/pack 에 사용할 기본 여백
    Todo,             # Todo 데이터 모델
    STATUS_ICON,      # 상태 아이콘
    STATUS_TEXT,      # 상태 텍스트
    parse_date,       # 날짜 문자열 파서
    center_over,      # 팝업을 부모창 중앙에 배치
    save_all,         # Todo 리스트 전체를 DB 에 저장
)


# ─────────────────────────────────────────────
# Todo 추가/편집 팝업 다이얼로그
# ─────────────────────────────────────────────

class TodoDialog(tk.Toplevel):
    """할 일 1건을 추가하거나 편집하기 위한 모달 팝업 창."""

    def __init__(self, parent: tk.Tk, title: str,
                 prefill: str = "", item: Todo | None = None) -> None:
        """
        parent: 부모 Tk 창
        title: 팝업 윈도우 타이틀
        prefill: 새로 추가할 때 제목에 미리 채울 문자열
        item: 편집 모드일 때 기존 Todo 객체
        """
        super().__init__(parent)  # Toplevel 기본 초기화
        self.result: Todo | None = None  # 저장 성공 시 돌려줄 Todo 결과값
        self._orig_status = item.status if item else 0  # 편집 시 기존 상태 유지용

        self.title(title)  # 윈도우 타이틀 텍스트 설정
        self.transient(parent)  # 부모창 위에 항상 떠 있도록 설정
        self.resizable(False, False)  # 팝업 크기 고정
        self.grab_set()  # 모달 동작(닫힐 때까지 다른 창 포커스 불가)

        pad = PAD6  # 공통 여백 설정
        today_str = date.today().isoformat()  # 오늘 날짜 문자열(YYYY-MM-DD)

        ttk.Label(self, text="제목").grid(row=0, column=0, sticky="w", **pad)  # 제목 라벨
        self.ent_title = ttk.Entry(self, width=38)  # 제목 입력 칸
        self.ent_title.grid(row=0, column=1, sticky="w", **pad)  # 그리드 배치
        # prefill 이 있으면 우선 사용, 없으면 편집 대상의 제목 또는 빈 문자열
        self.ent_title.insert(0, prefill or (item.title if item else ""))

        ttk.Label(self, text="시작일 (YYYY-MM-DD)").grid(row=1, column=0, sticky="w", **pad)  # 시작일 라벨
        self.ent_start = ttk.Entry(self, width=20)  # 시작일 입력 칸
        self.ent_start.grid(row=1, column=1, sticky="w", **pad)  # 배치
        self.ent_start.insert(0, item.start if item else today_str)  # 기본값은 오늘

        ttk.Label(self, text="종료일 (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", **pad)  # 종료일 라벨
        self.ent_end = ttk.Entry(self, width=20)  # 종료일 입력 칸
        self.ent_end.grid(row=2, column=1, sticky="w", **pad)  # 배치
        self.ent_end.insert(0, item.end if item else today_str)  # 기본값은 오늘

        ttk.Label(self, text="상세설명").grid(row=3, column=0, sticky="nw", **pad)  # 상세설명 라벨
        self.txt_desc = tk.Text(self, width=40, height=6)  # 멀티라인 텍스트 입력 영역
        self.txt_desc.grid(row=3, column=1, **pad)  # 배치
        if item:  # 편집 모드일 경우
            self.txt_desc.insert("1.0", item.desc)  # 기존 상세설명 채워넣기

        btns = ttk.Frame(self)  # 버튼들을 담을 하단 프레임
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=10)  # 오른쪽 정렬로 배치
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="right", padx=6)  # 취소 버튼
        ttk.Button(btns, text="저장", command=self._on_save).pack(side="right")  # 저장 버튼

        self.update_idletasks()  # 내부 위젯의 실제 크기 계산
        center_over(parent, self)  # 부모 창 기준으로 중앙 배치
        self.ent_title.focus_set()  # 제목 입력란에 포커스 주기

    def _on_save(self) -> None:
        """검증을 통과하면 self.result 에 Todo 를 넣고 팝업을 닫는다."""
        title = self.ent_title.get().strip()  # 제목 문자열
        start = self.ent_start.get().strip()  # 시작일 문자열
        end = self.ent_end.get().strip()  # 종료일 문자열
        desc = self.txt_desc.get("1.0", "end").strip()  # 상세설명 전체 텍스트

        if not title:  # 제목이 비어있으면
            messagebox.showwarning("확인", "제목을 입력하세요.", parent=self)  # 경고 메시지
            self.ent_title.focus_set()  # 포커스를 제목에 다시 주고
            return  # 저장 중단

        try:
            d1 = parse_date(start)  # 시작일 형식 검증
        except Exception:
            messagebox.showerror("날짜 오류", "시작일 형식이 잘못되었습니다.\n예: 2025-11-18", parent=self)
            self.ent_start.focus_set()  # 잘못된 입력 위치에 포커스
            return

        try:
            d2 = parse_date(end)  # 종료일 형식 검증
        except Exception:
            messagebox.showerror("날짜 오류", "종료일 형식이 잘못되었습니다.\n예: 2025-11-20", parent=self)
            self.ent_end.focus_set()
            return

        if d2 < d1:  # 종료일이 시작일보다 빠르면 잘못된 범위
            messagebox.showerror("날짜 오류", "종료일은 시작일보다 빠를 수 없습니다.", parent=self)
            self.ent_end.focus_set()
            return

        # 검증을 통과하면 Todo 인스턴스를 만들어 결과에 저장
        self.result = Todo(
            title=title,
            start=start,
            end=end,
            desc=desc,
            status=self._orig_status,  # 편집 중인 항목이면 기존 상태 유지
        )
        self.destroy()  # 팝업 닫기


# ─────────────────────────────────────────────
# "할 일" 탭 프레임
# ─────────────────────────────────────────────

class TodoTab(ttk.Frame):
    """할 일 목록 관리 UI + CRUD 로직을 담당하는 탭."""

    def __init__(
        self,
        master: tk.Misc,                  # Notebook 을 부모로 받는다.
        todos: list[Todo],                # 공유 Todo 리스트(메인과 같은 객체)
        on_todos_changed=None,            # Todo 변경 시 호출할 콜백(리포트/AI 갱신용)
        on_request_ai_refresh=None,       # 'AI 추천 새로고침' 버튼이 눌릴 때 호출할 콜백
    ) -> None:
        super().__init__(master)  # Frame 초기화
        self.todos = todos  # Todo 리스트 참조 저장(공유 객체)
        self.on_todos_changed = on_todos_changed  # 변경 콜백 저장
        self.on_request_ai_refresh = on_request_ai_refresh  # AI 새로고침 콜백 저장

        self._build_ui()  # 실제 위젯 구성

    # -----------------------------
    # UI 구성
    # -----------------------------
    def _build_ui(self) -> None:
        """상단 입력/버튼, 중앙 리스트, 하단 AI 추천 라벨을 구성한다."""
        top = ttk.Frame(self)  # 상단 입력/버튼 영역 프레임
        top.pack(fill="x", padx=10, pady=10)  # 좌우로 가득 채우며 여백을 둠

        self.quick_entry = ttk.Entry(top)  # 제목 빠른 입력용 Entry
        self.quick_entry.pack(side="left", fill="x", expand=True)  # 좌측에 배치하고 가로 확장
        self.quick_entry.focus()  # 탭이 열리면 자동으로 포커스
        self.quick_entry.bind("<Return>", lambda e: self.add_todo())  # Enter 키로 추가

        ttk.Button(top, text="추가", command=self.add_todo).pack(side="left", padx=6)  # 추가 버튼
        ttk.Button(top, text="편집", command=self.edit_selected).pack(side="left", padx=6)  # 편집 버튼
        ttk.Button(top, text="삭제", command=self.delete_selected).pack(side="left", padx=6)  # 삭제 버튼
        ttk.Button(
            top,
            text="상태전환 (☐→⏳→✔)",  # 상태 순환 안내 텍스트
            command=self.cycle_status_selected,  # 상태 전환 핸들러
        ).pack(side="left", padx=6)

        mid = ttk.Frame(self)  # 리스트 + 스크롤 영역
        mid.pack(fill="both", expand=True, padx=10, pady=5)  # 전체 공간을 채우며 여백

        self.listbox = tk.Listbox(
            mid,
            height=10,           # 기본 높이(행 수)
            selectmode="extended",  # 다중 선택 허용
        )
        self.listbox.pack(side="left", fill="both", expand=True)  # 리스트가 대부분 공간을 차지

        scroll = ttk.Scrollbar(
            mid,
            orient="vertical",        # 세로 스크롤
            command=self.listbox.yview,  # 리스트 스크롤링과 연동
        )
        scroll.pack(side="left", fill="y")  # 리스트 오른쪽에 세로로 배치
        self.listbox.config(yscrollcommand=scroll.set)  # 리스트와 스크롤을 서로 연결

        # 리스트 단축키 바인딩
        self.listbox.bind("<Delete>", lambda e: self.delete_selected())  # Delete 키로 삭제
        self.listbox.bind("<space>", self._on_space_toggle)  # 스페이스로 상태 토글
        self.listbox.bind("<Double-Button-1>", self.show_details)  # 더블클릭으로 상세보기

        bottom = ttk.Frame(self)  # 하단 AI 추천 표시부
        bottom.pack(fill="x", padx=10, pady=(0, 8))  # 상단은 0, 하단은 8 픽셀 여백

        # AI 추천 텍스트 라벨 (wraplength 로 길면 줄바꿈)
        self.lbl_ai_tip = tk.Label(
            bottom,
            text="(AI 추천이 여기에 표시됩니다)",  # 초기 안내 텍스트
            anchor="w",          # 왼쪽 정렬
            justify="left",      # 여러 줄일 때 왼쪽 정렬
            fg="#1b5e20",        # 기본 녹색 계열 텍스트 색
            wraplength=560,      # 너무 길면 560px 에서 줄바꿈
        )
        self.lbl_ai_tip.pack(side="left", fill="x", expand=True)  # 나머지 공간을 채움

        # AI 추천 새로고침 버튼 (메인 앱의 콜백을 호출)
        self.btn_ai_tip_refresh = ttk.Button(
            bottom,
            text="AI 추천 새로고침",
            command=(self.on_request_ai_refresh or (lambda: None)),  # 콜백이 없으면 아무것도 안 함
        )
        self.btn_ai_tip_refresh.pack(side="right", padx=(8, 10))  # 오른쪽 끝 근처에 배치

    # -----------------------------
    # 헬퍼: 선택된 인덱스
    # -----------------------------
    def _selected_indices(self) -> tuple[int, ...] | None:
        """현재 선택된 리스트 인덱스 튜플을 반환, 없으면 경고 후 None."""
        sel = self.listbox.curselection()  # 선택된 인덱스들을 가져옴
        if not sel:  # 아무것도 선택 안 된 경우
            messagebox.showwarning("확인", "항목을 선택하세요.", parent=self)
            return None
        return sel  # 정상적으로 선택된 인덱스 튜플 반환

    # -----------------------------
    # 외부에서 호출: 리스트 갱신
    # -----------------------------
    def refresh_list(self) -> None:
        """self.todos 내용을 기반으로 리스트박스 문자열을 모두 다시 그린다."""
        self.listbox.delete(0, tk.END)  # 기존 리스트 항목을 모두 제거
        if self.todos:  # Todo 항목이 하나라도 있으면
            # 각 Todo 의 display() 문자열을 한 번에 insert
            self.listbox.insert(tk.END, *[t.display() for t in self.todos])

    # -----------------------------
    # CRUD / 상태 전환 / 상세보기
    # -----------------------------
    def add_todo(self) -> None:
        """빠른 입력칸 내용을 제목으로 하는 새 Todo 를 추가한다."""
        prefill = self.quick_entry.get().strip()  # 입력칸 텍스트를 미리 채울 제목으로 사용
        dlg = TodoDialog(self.winfo_toplevel(), "할 일 추가", prefill=prefill)  # 팝업 생성
        dlg.wait_window()  # 모달처럼 동작: 닫힐 때까지 대기
        if dlg.result:  # 저장 버튼을 눌러 결과가 존재할 때만
            self.todos.append(dlg.result)  # Todo 리스트에 새 항목 추가
            save_all(self.todos)  # DB 에 전체 리스트 저장
            self.refresh_list()  # UI 리스트 갱신
            if self.on_todos_changed:  # 메인에 변경 사실 알리기(리포트/AI 갱신용)
                self.on_todos_changed()

    def edit_selected(self) -> None:
        """선택된 첫 번째 Todo 를 편집 다이얼로그로 연다."""
        sel = self._selected_indices()  # 선택 확인
        if not sel:  # 선택이 없으면 함수 종료
            return
        idx = sel[0]  # 첫 번째 선택 인덱스만 사용
        item = self.todos[idx]  # 해당 Todo 객체
        dlg = TodoDialog(self.winfo_toplevel(), "할 일 편집", item=item)  # 편집 팝업 생성
        dlg.wait_window()  # 사용자가 닫을 때까지 대기
        if dlg.result:  # 수정된 결과가 있을 경우
            self.todos[idx] = dlg.result  # 리스트에서 해당 항목 교체
            save_all(self.todos)  # 변경 내용을 DB 에 저장
            self.refresh_list()  # 리스트 UI 갱신
            if self.on_todos_changed:  # 상위 콜백 호출
                self.on_todos_changed()

    def delete_selected(self) -> None:
        """선택된 Todo 들을 모두 삭제한다."""
        sel = self._selected_indices()  # 선택된 인덱스 확인
        if not sel:  # 없으면 종료
            return
        # 사용자에게 실제 삭제 여부 재확인
        if not messagebox.askyesno(
            "삭제 확인",
            f"선택한 {len(sel)}개 항목을 정말 삭제할까요?",
            parent=self,
        ):
            return  # 아니오 선택 시 삭제 취소

        for i in reversed(sel):  # 인덱스 꼬임 방지를 위해 뒤에서부터 삭제
            del self.todos[i]
        save_all(self.todos)  # DB 에 반영
        self.refresh_list()  # 리스트 갱신
        if self.on_todos_changed:  # 상위에 변경 알림
            self.on_todos_changed()

    def cycle_status_selected(self) -> None:
        """선택된 Todo 들의 상태를 0→1→2→0 순환시킨다."""
        sel = self._selected_indices()  # 선택 인덱스
        if not sel:
            return
        for i in sel:  # 각 선택된 인덱스에 대해
            self.todos[i].cycle()  # 상태 순환
        save_all(self.todos)  # 변경 저장
        self.refresh_list()  # 리스트 갱신
        if self.on_todos_changed:  # 상위 콜백
            self.on_todos_changed()

    def _on_space_toggle(self, _e) -> str:
        """Space 키로 상태 토글 후 리스트박스 기본 행동은 막는다."""
        self.cycle_status_selected()  # 상태 전환 실행
        return "break"  # Tkinter 에게 기본 처리(포커스 이동 등)를 하지 말라고 지시

    def show_details(self, _e=None) -> None:
        """선택된 첫 Todo 의 상세 정보를 messagebox 로 보여준다."""
        sel = self._selected_indices()  # 선택 확인
        if not sel:
            return
        t = self.todos[sel[0]]  # 첫 번째 선택 항목
        icon = STATUS_ICON.get(t.status, "☐")  # 상태 아이콘
        msg = (
            f"제목: {t.title}\n"
            f"기간: {t.start} ~ {t.end}\n"
            f"상태: {icon} {STATUS_TEXT.get(t.status, '')}\n\n"
            f"상세설명:\n{t.desc or '(없음)'}"
        )  # 상세 설명 문자열 구성
        messagebox.showinfo("할 일 상세", msg, parent=self.winfo_toplevel())  # 팝업으로 표시

    # -----------------------------
    # AI 연동용 정보 & 제어 함수
    # -----------------------------
    def get_selected_titles(self) -> list[str]:
        """현재 선택된 Todo 들의 제목 리스트를 반환한다(AI 컨텍스트용)."""
        sel = self.listbox.curselection()  # 선택 인덱스 튜플
        return [self.todos[i].title for i in sel] if sel else []  # 선택된 Todo 의 제목 목록

    def select_and_edit_index(self, idx: int) -> None:
        """외부(리포트 탭 등)에서 인덱스로 Todo 를 선택 후 편집할 때 사용."""
        self.listbox.selection_clear(0, "end")  # 기존 선택 모두 해제
        if 0 <= idx < self.listbox.size():  # 인덱스 유효성 검증
            self.listbox.selection_set(idx)  # 리스트박스에서 해당 인덱스 선택
            self.listbox.see(idx)  # 스크롤 영역 안으로 가져오기
            self.edit_selected()  # 편집 다이얼로그 호출

    def set_ai_tip(self, text: str, ok: bool) -> None:
        """
        메인 앱의 AI 도우미가 계산한 추천 문구를 표시한다.
        - ok=True: 정상 응답 → 초록색
        - ok=False: 오류/폴백 → 빨간색
        """
        self.lbl_ai_tip.config(
            text=text,  # 표시할 텍스트
            fg=("#1b5e20" if ok else "#e53935"),  # 색상 조건에 따라 변경
        )
