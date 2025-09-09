# ─────────────────────────────────────────────────────────
# 기본 틀
# ─────────────────────────────────────────────────────────
# Tkinter: 파이썬 기본 GUI
import tkinter as tk
from tkinter import ttk

# 1) 메인 창 만들기
root = tk.Tk()                          # Tk()로 창 하나 만들기
root.title("학업")        # 창 제목
root.geometry("520x380")                # 창 크기 (조금만 키움)

# 2) 탭 컨테이너(Notebook) 만들고 배치
nb = ttk.Notebook(root)                 # 탭들을 담는 상자(폴더)
nb.pack(expand=True, fill="both", padx=10, pady=10)  # 창을 넓게 채우고 가장자리에 여백

# 3) 탭(페이지) 4개: Frame(빈 상자)로 생성
tab_todo   = ttk.Frame(nb)              # '할 일' 탭
tab_timer  = ttk.Frame(nb)              # '타이머' 탭
tab_grade  = ttk.Frame(nb)              # '성적' 탭
tab_report = ttk.Frame(nb)              # '리포트' 탭

# 4) 탭 등록 + 탭 이름
nb.add(tab_todo,   text="할 일")
nb.add(tab_timer,  text="타이머")
nb.add(tab_grade,  text="성적")
nb.add(tab_report, text="리포트")

# ─────────────────────────────────────────────────────────
# [할 일] 탭에 "입력 → 추가 → 리스트 표시"
# ─────────────────────────────────────────────────────────

# 메모리에만 갖고 있을 '할 일' 데이터 (문자열 목록)
todos = []                               # 예: ["파이썬 실습하기", "과제 제출하기"]

# 5) 입력칸 + 추가 버튼이 들어갈 상단 영역
top = ttk.Frame(tab_todo)                # 상단 줄(입력 줄) 넣을 칸막이
top.pack(fill="x", padx=10, pady=10)     # 가로로 쭉 붙이기 + 여백

# 6) 입력칸(Entry)
entry = ttk.Entry(top)                   # 한 줄짜리 텍스트 입력 상자
entry.pack(side="left", fill="x", expand=True)  # 왼쪽에 두고, 가로 공간을 넓게 차지
entry.focus()                            # 실행하자마자 커서가 여기에 오도록

# 7) "추가" 버튼
def add_todo():                          # 버튼이 눌리면 실행할 함수(행동)
    text = entry.get().strip()           # 입력칸에서 글자를 꺼내고 앞뒤 공백 제거
    if not text:                         # 아무것도 없으면
        return                           # 그냥 무시
    todos.append(text)                   # 목록에 새 할 일을 추가(문자열)
    entry.delete(0, tk.END)              # 입력칸 비우기
    refresh_list()                       # 리스트박스 화면 갱신(화면에 반영)

btn_add = ttk.Button(top, text="추가", command=add_todo)  # 버튼 클릭→ add_todo 실행
btn_add.pack(side="left", padx=6)        # 입력칸 오른쪽에 배치

# 8) Listbox(리스트 표시 상자) + 스크롤바
mid = ttk.Frame(tab_todo)                # 리스트와 스크롤을 넣을 영역
mid.pack(fill="both", expand=True, padx=10, pady=5)

listbox = tk.Listbox(mid, height=10)     # 간단 리스트 표시 위젯
listbox.pack(side="left", fill="both", expand=True)  # 세로/가로로 공간 채우기

scroll = ttk.Scrollbar(mid, orient="vertical", command=listbox.yview)  # 세로 스크롤
scroll.pack(side="left", fill="y")       # 세로로 꽉 차게
listbox.config(yscrollcommand=scroll.set) # 리스트와 스크롤 연결(동기화)

# 9) 리스트 갱신 함수(화면을 데이터에 맞게 다시 그리기)
def refresh_list():                      # todos 목록 → listbox 화면 반영
    listbox.delete(0, tk.END)            # 먼저 다 지움(초기화)
    for t in todos:                      # 목록을 돌면서
        listbox.insert(tk.END, t)        # 한 줄씩 추가

# 10) 편의 기능: 엔터 키로도 추가되게 하기
def on_enter(event):                     # 키보드 이벤트 핸들러 (event는 써도 되고 안 써도 됨)
    add_todo()                           # 엔터 치면 add_todo와 같은 행동
entry.bind("<Return>", on_enter)         # 입력칸에 포커스가 있을 때 엔터키 감지

# 다른 탭들은 자리표시자 라벨만 유지
ttk.Label(tab_timer,  text="여기에 '타이머' 기능 추가 예정").pack(pady=20)
ttk.Label(tab_grade,  text="여기에 '성적' 기능 추가 예정").pack(pady=20)
ttk.Label(tab_report, text="여기에 '리포트' 기능 추가 예정").pack(pady=20)

# 11) GUI 이벤트 루프 시작
root.mainloop()                          # 창이 닫힐 때까지 버튼/키보드 등 이벤트 처리