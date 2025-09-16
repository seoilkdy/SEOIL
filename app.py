# ─────────────────────────────────────────────────────────
# Tkinter: 파이썬 기본 GUI
# ─────────────────────────────────────────────────────────
from dataclasses import dataclass
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk, messagebox

DATE_FMT = "%Y-%m-%d"
STATUS_ICON = {0: "☐", 1: "⏳", 2: "✔"}
STATUS_TEXT = {0: "미완료", 1: "진행중", 2: "완료"}

def parse_date(s: str) -> datetime:
    return datetime.strptime(s, DATE_FMT)

@dataclass
class Todo:
    title: str
    start: str
    end: str
    desc: str = ""
    status: int = 0

    def cycle(self) -> None:
        self.status = (self.status + 1) % 3

    def display(self, today: date | None = None) -> str:
        icon = STATUS_ICON.get(self.status, "☐")
        try:
            d_end = datetime.strptime(self.end, DATE_FMT).date()
        except Exception:
            return f"{icon} {self.start} ~ {self.end} | {self.title}"

        today = today or date.today()
        delta = (d_end - today).days
        if delta < 0:
            tag = "⛔ 지남"
        elif delta == 0:
            tag = "⚠️ D-DAY"
        elif delta <= 3:
            tag = f"⏰ D-{delta}"
        else:
            tag = f"D-{delta}"
        return f"{icon} [{tag}] {self.start} ~ {self.end} | {self.title}"

class TodoDialog(tk.Toplevel):

    def __init__(self, parent: tk.Tk, title: str, prefill: str = "", item: Todo | None = None):
        super().__init__(parent)
        self.result: Todo | None = None
        self._orig_status = item.status if item else 0

        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        pad = {"padx": 10, "pady": 6}
        today_str = date.today().isoformat()

        ttk.Label(self, text="제목").grid(row=0, column=0, sticky="w", **pad)
        self.ent_title = ttk.Entry(self, width=38)
        self.ent_title.grid(row=0, column=1, sticky="w", **pad)
        self.ent_title.insert(0, prefill or (item.title if item else ""))

        ttk.Label(self, text="시작일 (YYYY-MM-DD)").grid(row=1, column=0, sticky="w", **pad)
        self.ent_start = ttk.Entry(self, width=20)
        self.ent_start.grid(row=1, column=1, sticky="w", **pad)
        self.ent_start.insert(0, item.start if item else today_str)

        ttk.Label(self, text="종료일 (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", **pad)
        self.ent_end = ttk.Entry(self, width=20)
        self.ent_end.grid(row=2, column=1, sticky="w", **pad)
        self.ent_end.insert(0, item.end if item else today_str)

        ttk.Label(self, text="상세설명").grid(row=3, column=0, sticky="nw", **pad)
        self.txt_desc = tk.Text(self, width=40, height=6)
        self.txt_desc.grid(row=3, column=1, **pad)
        if item:
            self.txt_desc.insert("1.0", item.desc)

        btns = ttk.Frame(self)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=10)
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="right", padx=6)
        ttk.Button(btns, text="저장", command=self._on_save).pack(side="right")

        self.update_idletasks()
        TodoApp.center_over(parent, self)
        self.ent_title.focus_set()

    def _on_save(self) -> None:
        title = self.ent_title.get().strip()
        start = self.ent_start.get().strip()
        end = self.ent_end.get().strip()
        desc = self.txt_desc.get("1.0", "end").strip()

        if not title:
            messagebox.showwarning("확인", "제목을 입력하세요.")
            self.ent_title.focus_set()
            return
        try:
            d1 = parse_date(start)
        except Exception:
            messagebox.showerror("날짜 오류", "시작일 형식이 잘못되었습니다.\n예: 2025-09-16")
            self.ent_start.focus_set()
            return
        try:
            d2 = parse_date(end)
        except Exception:
            messagebox.showerror("날짜 오류", "종료일 형식이 잘못되었습니다.\n예: 2025-09-18")
            self.ent_end.focus_set()
            return
        if d2 < d1:
            messagebox.showerror("날짜 오류", "종료일은 시작일보다 빠를 수 없습니다.")
            self.ent_end.focus_set()
            return

        self.result = Todo(title=title, start=start, end=end, desc=desc, status=self._orig_status)
        self.destroy()

class TodoApp(tk.Tk):
    # ─────────────────────────────────────────────────────────
    # [앱 초기화: 메인창 크기/제목 설정, 탭 구성]
    # ─────────────────────────────────────────────────────────
    def __init__(self) -> None:
        super().__init__()
        self.title("갓생살기")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = (sw - 580) // 2, (sh - 380) // 2
        self.geometry(f"580x380+{x}+{y}")

        self.todos: list[Todo] = []

        nb = ttk.Notebook(self)
        nb.pack(expand=True, fill="both", padx=10, pady=10)

        self.tab_todo = ttk.Frame(nb)
        self.tab_timer = ttk.Frame(nb)
        self.tab_grade = ttk.Frame(nb)
        self.tab_report = ttk.Frame(nb)
        nb.add(self.tab_todo, text="할 일")
        nb.add(self.tab_timer, text="타이머")
        nb.add(self.tab_grade, text="성적")
        nb.add(self.tab_report, text="리포트")

        self._build_todo_tab()
        ttk.Label(self.tab_timer, text="여기에 '타이머' 기능 추가 예정").pack(pady=20)
        ttk.Label(self.tab_grade, text="여기에 '성적' 기능 추가 예정").pack(pady=20)
        ttk.Label(self.tab_report, text="여기에 '리포트' 기능 추가 예정").pack(pady=20)

        self.refresh_list()

    # ─────────────────────────────────────────────────────────
    # [할 일 탭 UI]
    # ─────────────────────────────────────────────────────────
    def _build_todo_tab(self) -> None:
        top = ttk.Frame(self.tab_todo)
        top.pack(fill="x", padx=10, pady=10)

        self.quick_entry = ttk.Entry(top)
        self.quick_entry.pack(side="left", fill="x", expand=True)
        self.quick_entry.focus()
        self.quick_entry.bind("<Return>", lambda e: self.add_todo())

        ttk.Button(top, text="추가", command=self.add_todo).pack(side="left", padx=6)
        ttk.Button(top, text="편집", command=self.edit_selected).pack(side="left", padx=6)
        ttk.Button(top, text="삭제", command=self.delete_selected).pack(side="left", padx=6)
        ttk.Button(top, text="상태전환 (☐→⏳→✔)", command=self.cycle_status_selected).pack(side="left", padx=6)

        mid = ttk.Frame(self.tab_todo)
        mid.pack(fill="both", expand=True, padx=10, pady=5)

        self.listbox = tk.Listbox(mid, height=10, selectmode="extended")
        self.listbox.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)

        self.listbox.bind("<Delete>", lambda e: self.delete_selected())
        self.listbox.bind("<space>", self._on_space_toggle)
        self.listbox.bind("<Double-Button-1>", self.show_details)

    # ─────────────────────────────────────────────────────────
    # [헬퍼 함수: 공통 동작 모음 - 선택 확인, 창 중앙 배치, 리스트 갱신]
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def center_over(parent: tk.Tk, win: tk.Toplevel) -> None:
        parent.update_idletasks()
        win.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        ww, wh = win.winfo_width(), win.winfo_height()
        x = max(0, min(px + (pw - ww) // 2, win.winfo_screenwidth() - ww))
        y = max(0, min(py + (ph - wh) // 2, win.winfo_screenheight() - wh))
        win.geometry(f"+{x}+{y}")

    def _selected_indices(self) -> tuple[int, ...] | None:
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("확인", "항목을 선택하세요.")
            return None
        return sel

    def refresh_list(self) -> None:
        self.listbox.delete(0, tk.END)
        if self.todos:
            self.listbox.insert(tk.END, *[t.display() for t in self.todos])

    # ─────────────────────────────────────────────────────────
    # [사용자 액션: 추가/편집/삭제/상태전환/상세보기 동작]
    # ─────────────────────────────────────────────────────────
    def add_todo(self) -> None:
        prefill = self.quick_entry.get().strip()
        dlg = TodoDialog(self, "할 일 추가", prefill=prefill)
        self.wait_window(dlg)
        if dlg.result:
            self.todos.append(dlg.result)
            self.refresh_list()

    def edit_selected(self) -> None:
        sel = self._selected_indices()
        if not sel:
            return
        idx = sel[0]
        dlg = TodoDialog(self, "할 일 편집", item=self.todos[idx])
        self.wait_window(dlg)
        if dlg.result:
            self.todos[idx] = dlg.result
            self.refresh_list()

    def delete_selected(self) -> None:
        sel = self._selected_indices()
        if not sel:
            return
        if not messagebox.askyesno("삭제 확인", f"선택한 {len(sel)}개 항목을 정말 삭제할까요?"):
            return
        for i in reversed(sel):
            del self.todos[i]
        self.refresh_list()

    def cycle_status_selected(self) -> None:
        sel = self._selected_indices()
        if not sel:
            return
        for i in sel:
            self.todos[i].cycle()
        self.refresh_list()

    def _on_space_toggle(self, _e) -> str:
        self.cycle_status_selected()
        return "break"

    def show_details(self, _e=None) -> None:
        sel = self._selected_indices()
        if not sel:
            return
        t = self.todos[sel[0]]
        icon = STATUS_ICON.get(t.status, "☐")
        msg = (
            f"제목: {t.title}\n"
            f"기간: {t.start} ~ {t.end}\n"
            f"상태: {icon} {STATUS_TEXT.get(t.status,'')}\n\n"
            f"상세설명:\n{t.desc or '(없음)'}"
        )
        messagebox.showinfo("할 일 상세", msg)

if __name__ == "__main__":
    app = TodoApp()
    app.mainloop()
