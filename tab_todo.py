# tab_todo.py  --------------------------------------------------
# "할 일(Todo)" 탭의 UI와 로직, 그리고 할 일 추가/편집을 위한 다이얼로그를 담당하는 모듈입니다.
# 사용자는 여기서 할 일을 추가, 수정, 삭제하고 상태를 변경할 수 있습니다.

from __future__ import annotations  # 파이썬 3.7+에서 타입 힌트를 문자열처럼 처리하여 순환 참조 문제를 방지합니다.

from datetime import date  # 오늘 날짜를 기본값으로 설정하기 위해 사용합니다.
import tkinter as tk  # Tkinter 기본 위젯 기능을 가져옵니다.
from tkinter import ttk, messagebox  # ttk 스타일 위젯과 팝업 메시지 박스를 가져옵니다.

from core import (  # core.py 모듈에서 공통 기능들을 가져옵니다.
    PAD6,             # UI 배치 시 사용할 기본 여백 상수
    Todo,             # 할 일 데이터 모델 클래스
    STATUS_ICON,      # 상태 아이콘 매핑
    STATUS_TEXT,      # 상태 텍스트 매핑
    parse_date,       # 날짜 문자열 파싱 함수
    center_over,      # 팝업 창 중앙 배치 함수
    save_all,         # 할 일 목록 전체 저장 함수
)


# ─────────────────────────────────────────────
# Todo 추가/편집 팝업 다이얼로그 클래스
# ─────────────────────────────────────────────

class TodoDialog(tk.Toplevel):
    """
    할 일 1건을 추가하거나 편집하기 위해 띄우는 모달(Modal) 팝업 창입니다.
    제목, 시작일, 종료일, 상세 설명을 입력받습니다.
    """

    def __init__(self, parent: tk.Tk, title: str,
                 prefill: str = "", item: Todo | None = None) -> None:
        """
        TodoDialog 생성자입니다.
        
        Args:
            parent: 부모 윈도우 (메인 앱)
            title: 팝업 창의 제목 (예: "할 일 추가", "할 일 편집")
            prefill: 빠른 추가 시 제목 입력란에 미리 채울 텍스트
            item: 편집 모드일 경우, 기존 Todo 객체 (없으면 None)
        """
        super().__init__(parent)  # 부모 클래스(Toplevel) 초기화
        self.result: Todo | None = None  # 사용자가 저장을 눌렀을 때 생성된 Todo 객체를 담을 변수
        self._orig_status = item.status if item else 0  # 편집 시 기존 상태를 유지하기 위해 저장합니다.

        self.title(title)  # 윈도우 제목 설정
        self.transient(parent)  # 이 창을 부모 창의 임시 창으로 설정 (부모 위에 항상 뜸)
        self.resizable(False, False)  # 창 크기 조절 불가능하게 설정
        self.grab_set()  # 모달 동작 설정 (이 창이 닫히기 전까지 다른 창 조작 불가)

        pad = PAD6  # 공통 여백 상수 사용
        today_str = date.today().isoformat()  # 오늘 날짜를 "YYYY-MM-DD" 문자열로 가져옵니다.

        # --- UI 구성 ---
        
        # 1. 제목 입력
        ttk.Label(self, text="제목").grid(row=0, column=0, sticky="w", **pad)  # 라벨 배치
        self.ent_title = ttk.Entry(self, width=38)  # 입력 필드 생성
        self.ent_title.grid(row=0, column=1, sticky="w", **pad)  # 그리드로 배치
        # prefill 값이 있으면 그것을, 아니면 기존 item의 제목을, 둘 다 없으면 빈 문자열을 채웁니다.
        self.ent_title.insert(0, prefill or (item.title if item else ""))

        # 2. 시작일 입력
        ttk.Label(self, text="시작일 (YYYY-MM-DD)").grid(row=1, column=0, sticky="w", **pad)
        self.ent_start = ttk.Entry(self, width=20)
        self.ent_start.grid(row=1, column=1, sticky="w", **pad)
        self.ent_start.insert(0, item.start if item else today_str)  # 기본값은 오늘 날짜

        # 3. 종료일 입력
        ttk.Label(self, text="종료일 (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", **pad)
        self.ent_end = ttk.Entry(self, width=20)
        self.ent_end.grid(row=2, column=1, sticky="w", **pad)
        self.ent_end.insert(0, item.end if item else today_str)  # 기본값은 오늘 날짜

        # 4. 상세 설명 입력 (여러 줄 텍스트)
        ttk.Label(self, text="상세설명").grid(row=3, column=0, sticky="nw", **pad)
        self.txt_desc = tk.Text(self, width=40, height=6)  # 멀티라인 텍스트 위젯
        self.txt_desc.grid(row=3, column=1, **pad)
        if item:  # 편집 모드라면 기존 설명을 채워넣습니다.
            self.txt_desc.insert("1.0", item.desc)

        # 5. 버튼 영역 (취소 / 저장)
        btns = ttk.Frame(self)  # 버튼들을 담을 프레임
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=10)  # 우측 하단 배치
        
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="right", padx=6)  # 취소 버튼 (창 닫기)
        ttk.Button(btns, text="저장", command=self._on_save).pack(side="right")  # 저장 버튼 (_on_save 호출)

        self.update_idletasks()  # 위젯 크기 계산
        center_over(parent, self)  # 부모 창 중앙에 배치
        self.ent_title.focus_set()  # 제목 입력란에 포커스 이동

    def _on_save(self) -> None:
        """
        저장 버튼 클릭 시 호출됩니다.
        입력값을 검증하고, 유효하면 self.result에 Todo 객체를 저장한 뒤 창을 닫습니다.
        """
        title = self.ent_title.get().strip()  # 제목의 앞뒤 공백 제거
        start = self.ent_start.get().strip()  # 시작일
        end = self.ent_end.get().strip()  # 종료일
        desc = self.txt_desc.get("1.0", "end").strip()  # 상세 설명

        # 1. 제목 필수 입력 확인
        if not title:
            messagebox.showwarning("확인", "제목을 입력하세요.", parent=self)
            self.ent_title.focus_set()
            return

        # 2. 시작일 날짜 형식 검증
        try:
            d1 = parse_date(start)
        except Exception:
            messagebox.showerror("날짜 오류", "시작일 형식이 잘못되었습니다.\n예: 2025-11-18", parent=self)
            self.ent_start.focus_set()
            return

        # 3. 종료일 날짜 형식 검증
        try:
            d2 = parse_date(end)
        except Exception:
            messagebox.showerror("날짜 오류", "종료일 형식이 잘못되었습니다.\n예: 2025-11-20", parent=self)
            self.ent_end.focus_set()
            return

        # 4. 날짜 범위 논리 검증 (종료일이 시작일보다 앞설 수 없음)
        if d2 < d1:
            messagebox.showerror("날짜 오류", "종료일은 시작일보다 빠를 수 없습니다.", parent=self)
            self.ent_end.focus_set()
            return

        # 모든 검증 통과 시 Todo 객체 생성
        self.result = Todo(
            title=title,
            start=start,
            end=end,
            desc=desc,
            status=self._orig_status,  # 상태는 기존 상태 유지
        )
        self.destroy()  # 팝업 닫기 (메인 앱에서 wait_window가 풀림)


# ─────────────────────────────────────────────
# 할 일(Todo) 탭 프레임 클래스
# ─────────────────────────────────────────────

class TodoTab(ttk.Frame):
    """
    할 일 목록을 보여주고 관리(추가/수정/삭제)하는 메인 탭입니다.
    Treeview를 사용하여 목록을 표시하고, AI 추천 기능을 포함합니다.
    """

    def __init__(
        self,
        master: tk.Misc,                  # 부모 위젯 (Notebook)
        todos: list[Todo],                # 메인 앱과 공유하는 Todo 리스트
        on_todos_changed=None,            # 데이터 변경 시 호출할 콜백 (리포트 갱신 등)
        on_request_ai_refresh=None,       # AI 추천 새로고침 요청 시 호출할 콜백
    ) -> None:
        """
        TodoTab 생성자입니다.
        """
        super().__init__(master)  # 부모 클래스 초기화
        self.todos = todos  # Todo 리스트 참조 저장
        self.on_todos_changed = on_todos_changed  # 변경 콜백 저장
        self.on_request_ai_refresh = on_request_ai_refresh  # AI 콜백 저장

        self.configure(style="TFrame") # 전체 배경색 설정
        self._build_ui()  # UI 구성

    # -----------------------------
    # UI 구성 메서드
    # -----------------------------
    def _build_ui(self) -> None:
        """
        상단 컨트롤 영역, 중앙 리스트 영역, 하단 AI 팁 영역을 구성합니다.
        """
        
        # --- 1. 상단 컨트롤 영역 (빠른 추가 및 버튼들) ---
        # 카드 스타일의 컨테이너 프레임
        top_container = ttk.Frame(self, style="Card.TFrame", padding=10)
        top_container.pack(fill="x", padx=15, pady=(15, 10))

        # 그리드 레이아웃 설정 (0번 컬럼이 늘어나도록)
        top_container.columnconfigure(0, weight=1)

        # 빠른 추가를 위한 입력 필드
        self.quick_entry = ttk.Entry(top_container, font=("Segoe UI", 10))
        self.quick_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10), ipady=5) # 높이를 맞추기 위해 ipady 사용
        self.quick_entry.focus()  # 앱 시작 시 여기에 포커스
        self.quick_entry.bind("<Return>", lambda e: self.add_todo())  # 엔터 키 누르면 추가

        # 버튼들을 담을 내부 프레임
        btn_frame = ttk.Frame(top_container, style="Card.TFrame")
        btn_frame.grid(row=0, column=1, sticky="e")

        # 버튼 생성 헬퍼 함수 (반복 코드 줄이기)
        def create_btn(text, cmd):
            return ttk.Button(btn_frame, text=text, command=cmd, style="Action.TButton", cursor="hand2")

        # 각 기능 버튼 생성 및 배치
        create_btn("➕ 추가", self.add_todo).pack(side="left", padx=2)
        create_btn("✎ 편집", self.edit_selected).pack(side="left", padx=2)
        create_btn("🗑 삭제", self.delete_selected).pack(side="left", padx=2)
        create_btn("↻ 상태변경", self.cycle_status_selected).pack(side="left", padx=2)

        # --- 2. 할 일 목록 영역 (Treeview) ---
        # 리스트를 담을 카드 프레임
        list_card = ttk.Frame(self, style="Card.TFrame", padding=2)
        list_card.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # 상단 강조 색상 띠
        accent = tk.Frame(list_card, bg="#3F51B5", height=4)
        accent.pack(fill="x", side="top")

        # Treeview 위젯 생성 (리스트박스 대신 사용)
        self.tree = ttk.Treeview(
            list_card, 
            columns=("task",), 
            show="tree",  # 헤더 숨김 (트리 형태만 표시)
            selectmode="browse", # 하나만 선택 가능
            style="Dashboard.Treeview" # 대시보드와 동일한 스타일 적용
        )
        self.tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        # 스크롤바 연결
        scrollbar = ttk.Scrollbar(list_card, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=10)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 이벤트 바인딩
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())  # 더블클릭 시 편집
        self.tree.bind("<Delete>", lambda e: self.delete_selected())  # Delete 키 누르면 삭제
        self.tree.bind("<space>", self._on_space_toggle)  # 스페이스바 누르면 상태 변경

        # 목록이 비었을 때 보여줄 안내 라벨 (Overlay 방식)
        self.lbl_empty = tk.Label(
            self.tree, 
            text="할 일이 없습니다.\n새로운 목표를 추가해보세요! ✨", 
            font=("Segoe UI", 12),
            fg="#90A4AE",
            bg="white"
        )
        # 실제 표시는 refresh_list()에서 데이터가 없을 때 place() 합니다.

        # --- 3. 하단 AI 추천 영역 ---
        # (이전 버전의 잔재인 lbl_recommend는 제거해도 되지만 호환성을 위해 둠)
        self.lbl_recommend = tk.Label(
            self,
            text="",
            font=("Segoe UI", 10, "italic"),
            fg="#5C6BC0",
            bg="#F5F7FA",
            wraplength=600
        )
        self.lbl_recommend.pack(side="bottom", pady=10)

        # AI 팁을 담을 하단 프레임
        bottom_frame = ttk.Frame(self, style="TFrame")
        bottom_frame.pack(fill="x", padx=15, pady=(0, 15))

        # AI 조언 텍스트 라벨
        self.lbl_ai_tip = tk.Label(
            bottom_frame,
            text="(AI 추천이 여기에 표시됩니다)",
            anchor="w",
            justify="left",
            fg="#1b5e20", # 기본 녹색 텍스트
            bg="#F5F7FA", 
            font=("Segoe UI", 9),
            wraplength=560,
        )
        self.lbl_ai_tip.pack(side="left", fill="x", expand=True)

        # AI 새로고침 버튼
        self.btn_ai_tip_refresh = ttk.Button(
            bottom_frame,
            text="AI 추천 새로고침",
            style="Action.TButton",
            command=(self.on_request_ai_refresh or (lambda: None)), # 콜백이 없으면 빈 함수
        )
        self.btn_ai_tip_refresh.pack(side="right", padx=(8, 0))

    # -----------------------------
    # 헬퍼 메서드: 선택된 항목 확인
    # -----------------------------
    def _selected_indices(self) -> tuple[int, ...] | None:
        """
        현재 Treeview에서 선택된 항목들의 인덱스 튜플을 반환합니다.
        선택된 항목이 없으면 경고창을 띄우고 None을 반환합니다.
        """
        sel_iids = self.tree.selection()  # 선택된 항목의 IID(Item ID)들을 가져옵니다.
        if not sel_iids:
            messagebox.showwarning("확인", "항목을 선택하세요.", parent=self)
            return None
        # IID를 정수 인덱스로 변환하여 반환합니다.
        return tuple(self.tree.index(iid) for iid in sel_iids)

    # -----------------------------
    # 리스트 갱신 메서드
    # -----------------------------
    def refresh_list(self) -> None:
        """
        self.todos 리스트의 최신 내용을 바탕으로 Treeview를 다시 그립니다.
        """
        # 기존 항목 모두 제거
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 데이터가 있으면 리스트에 추가
        if self.todos:
            self.lbl_empty.place_forget() # 빈 상태 라벨 숨김
            for t in self.todos:
                # Todo 객체의 display() 메서드를 호출해 표시할 문자열을 얻습니다.
                self.tree.insert("", "end", text=t.display())
        else:
            # 데이터가 없으면 빈 상태 라벨을 중앙에 표시
            self.lbl_empty.place(relx=0.5, rely=0.4, anchor="center")

    # -----------------------------
    # CRUD 및 상태 변경 로직
    # -----------------------------
    def add_todo(self) -> None:
        """
        '추가' 버튼 또는 엔터 키 입력 시 호출됩니다.
        빠른 입력칸의 내용을 바탕으로 새 할 일을 추가합니다.
        """
        prefill = self.quick_entry.get().strip()  # 입력칸 텍스트 가져오기
        dlg = TodoDialog(self.winfo_toplevel(), "할 일 추가", prefill=prefill)  # 다이얼로그 띄우기
        dlg.wait_window()  # 창이 닫힐 때까지 대기
        
        if dlg.result:  # 결과가 있으면 (저장 버튼 클릭 시)
            self.todos.append(dlg.result)  # 리스트에 추가
            save_all(self.todos)  # DB 저장
            self.refresh_list()  # UI 갱신
            if self.on_todos_changed:  # 변경 알림
                self.on_todos_changed()

    def edit_selected(self) -> None:
        """
        '편집' 버튼 또는 더블클릭 시 호출됩니다.
        선택된 할 일을 수정하는 다이얼로그를 엽니다.
        """
        sel = self._selected_indices()  # 선택된 항목 확인
        if not sel:
            return
        idx = sel[0]  # 첫 번째 선택 항목만 처리
        item = self.todos[idx]  # 해당 Todo 객체 가져오기
        
        dlg = TodoDialog(self.winfo_toplevel(), "할 일 편집", item=item)  # 편집 모드로 다이얼로그 생성
        dlg.wait_window()
        
        if dlg.result:  # 수정 결과가 있으면
            self.todos[idx] = dlg.result  # 리스트 업데이트
            save_all(self.todos)  # DB 저장
            self.refresh_list()  # UI 갱신
            if self.on_todos_changed:  # 변경 알림
                self.on_todos_changed()

    def delete_selected(self) -> None:
        """
        '삭제' 버튼 또는 Delete 키 입력 시 호출됩니다.
        선택된 할 일들을 삭제합니다.
        """
        sel = self._selected_indices()  # 선택된 항목 확인
        if not sel:
            return
            
        # 삭제 확인 메시지 박스
        if not messagebox.askyesno(
            "삭제 확인",
            f"선택한 {len(sel)}개 항목을 정말 삭제할까요?",
            parent=self,
        ):
            return  # 취소 시 중단

        # 인덱스가 꼬이지 않도록 뒤에서부터 삭제합니다.
        for i in reversed(sel):
            del self.todos[i]
            
        save_all(self.todos)  # DB 저장
        self.refresh_list()  # UI 갱신
        if self.on_todos_changed:  # 변경 알림
            self.on_todos_changed()

    def cycle_status_selected(self) -> None:
        """
        '상태변경' 버튼 또는 스페이스바 입력 시 호출됩니다.
        선택된 할 일들의 상태를 순환(미완료->진행중->완료)시킵니다.
        """
        sel = self._selected_indices()
        if not sel:
            return
        for i in sel:
            self.todos[i].cycle()  # 상태 순환 메서드 호출
            
        save_all(self.todos)  # DB 저장
        self.refresh_list()  # UI 갱신
        if self.on_todos_changed:  # 변경 알림
            self.on_todos_changed()

    def _on_space_toggle(self, _e) -> str:
        """
        스페이스바 이벤트 핸들러입니다.
        상태를 변경하고, Treeview의 기본 동작(스크롤 등)을 막기 위해 'break'를 반환합니다.
        """
        self.cycle_status_selected()
        return "break"

    def show_details(self, _e=None) -> None:
        """
        (현재 UI에는 버튼이 없지만) 선택된 할 일의 상세 내용을 팝업으로 보여주는 기능입니다.
        """
        sel = self._selected_indices()
        if not sel:
            return
        t = self.todos[sel[0]]
        icon = STATUS_ICON.get(t.status, "☐")
        msg = (
            f"제목: {t.title}\n"
            f"기간: {t.start} ~ {t.end}\n"
            f"상태: {icon} {STATUS_TEXT.get(t.status, '')}\n\n"
            f"상세설명:\n{t.desc or '(없음)'}"
        )
        messagebox.showinfo("할 일 상세", msg, parent=self.winfo_toplevel())

    # -----------------------------
    # AI 연동 및 외부 제어 메서드
    # -----------------------------
    def get_selected_titles(self) -> list[str]:
        """
        현재 선택된 할 일들의 제목 리스트를 반환합니다 (AI 컨텍스트용).
        """
        sel_iids = self.tree.selection()
        return [self.todos[self.tree.index(iid)].title for iid in sel_iids]

    def select_and_edit_index(self, idx: int) -> None:
        """
        외부(예: 리포트 탭)에서 특정 인덱스의 할 일을 편집하려고 할 때 호출됩니다.
        해당 항목을 선택하고 편집 다이얼로그를 엽니다.
        """
        # 기존 선택 해제
        for item in self.tree.selection():
            self.tree.selection_remove(item)
        
        children = self.tree.get_children()
        if 0 <= idx < len(children):
            item_id = children[idx]
            self.tree.selection_set(item_id)  # 항목 선택
            self.tree.see(item_id)  # 스크롤 이동하여 보이게 함
            self.edit_selected()  # 편집 창 열기

    def set_ai_tip(self, text: str, ok: bool) -> None:
        """
        메인 앱에서 AI 추천 결과를 받아 하단 라벨에 표시합니다.
        
        Args:
            text: 표시할 팁 텍스트
            ok: 정상 응답이면 True (녹색), 오류면 False (빨간색)
        """
        self.lbl_ai_tip.config(
            text=text,
            fg=("#1b5e20" if ok else "#e53935"),  # 성공/실패에 따른 색상 변경
        )
