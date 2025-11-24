# tab_timer.py  --------------------------------------------------
# 발표 타이머 탭의 UI와 타이머 작동 로직을 담당하는 모듈입니다.
# 사용자가 시간을 설정하고, 시작/일시정지/초기화하며, 남은 시간을 시각적으로 확인할 수 있습니다.

from __future__ import annotations  # 파이썬 3.7+에서 타입 힌트를 문자열처럼 처리하여 순환 참조 문제를 방지합니다.

import time  # 타이머의 정확도를 유지하기 위해 단조 증가 시계(time.monotonic)를 사용합니다.
import math  # 남은 시간을 계산할 때 올림(ceil) 처리를 위해 사용합니다.
import tkinter as tk  # Tkinter 기본 위젯 기능을 가져옵니다.
from tkinter import ttk  # 더 현대적인 스타일의 ttk 위젯을 가져옵니다.

from core import PAD8  # UI 배치 시 사용할 공통 여백 상수를 가져옵니다.


# ─────────────────────────────────────────────
# 타이머 탭 프레임 클래스
# ─────────────────────────────────────────────

class TimerTab(ttk.Frame):
    """
    발표 타이머 기능을 제공하는 탭 클래스입니다.
    시간 설정, 타이머 동작 제어, 시각적 피드백(프로그레스 바, 색상 변경)을 처리합니다.
    """

    def __init__(self, master: tk.Misc, on_started=None) -> None:
        """
        TimerTab 클래스의 생성자입니다.
        
        Args:
            master: 이 탭이 포함될 부모 위젯 (주로 Notebook)
            on_started: 타이머가 시작될 때 호출될 콜백 함수 (AI 코칭 등에 사용)
        """
        super().__init__(master)  # 부모 클래스(ttk.Frame)의 초기화 메서드를 호출합니다.
        self.on_started = on_started  # 타이머 시작 시 호출할 콜백 함수를 저장합니다.

        # --- 타이머 상태 관련 변수 초기화 ---
        self._timer_after_id: str | None = None  # 타이머 갱신 루프(after)의 ID를 저장 (취소용)
        self._blink_after_id: str | None = None  # 시간 종료 후 깜박임 루프의 ID를 저장 (취소용)
        self.timer_running: bool = False  # 현재 타이머가 실행 중인지 여부
        self.timer_total_sec: int = 0  # 설정된 총 타이머 시간 (초 단위)
        self.timer_warn_sec: int = 30  # 경고 색상으로 변경될 남은 시간 임계값 (초 단위)
        self.timer_end_mono: float = 0.0  # 타이머가 종료될 목표 시간 (time.monotonic 기준)
        self.timer_remain_sec: int = 0  # 현재 남은 시간 (초 단위)
        self._blink_on: bool = False  # 시간 종료 후 깜박임 효과를 위한 토글 상태

        self.var_timer_tip = tk.StringVar(value="")  # AI 코칭 문구를 표시할 문자열 변수

        self._build_ui()  # UI를 구성하는 메서드를 호출합니다.

    # -----------------------------
    # UI 구성 메서드
    # -----------------------------
    def _build_ui(self) -> None:
        """
        타이머 탭의 전체 UI를 구성합니다.
        상단 설정 영역, 중앙 타이머 디스플레이, 하단 컨트롤 버튼 및 AI 팁 영역으로 나뉩니다.
        """
        
        # 1. 메인 카드 프레임 (외곽 테두리 및 배경)
        card = ttk.Frame(self, style="Card.TFrame", padding=0)
        card.pack(fill="both", expand=True, padx=20, pady=20)  # 화면에 꽉 차게 배치하되 여백을 둡니다.
        
        # 상단 강조 색상 띠 (디자인 요소)
        ttk.Frame(card, style="Accent.TFrame", height=4).pack(fill="x", side="top")
        
        # 내부 컨텐츠를 담을 프레임 (테두리 없음, 넉넉한 패딩)
        inner = ttk.Frame(card, style="CardPlain.TFrame", padding=30)
        inner.pack(fill="both", expand=True)

        # 2. 상단 설정 영역 (시간 입력 및 경고 설정)
        top = ttk.Frame(inner, style="CardPlain.TFrame")
        top.pack(fill="x", pady=(0, 40)) # 하단 여백을 넉넉히 주어 답답함을 해소합니다.
        
        # 입력 필드들을 중앙에 정렬하기 위한 컨테이너
        top_center = ttk.Frame(top, style="CardPlain.TFrame")
        top_center.pack(anchor="center")

        # 발표 시간 입력 라벨 및 엔트리
        ttk.Label(top_center, text="발표 시간(분)", font=("Segoe UI", 11), background="white").pack(side="left", padx=(0, 10))
        self.ent_minutes = ttk.Entry(top_center, width=5, font=("Segoe UI", 11), justify="center")
        self.ent_minutes.pack(side="left", padx=(0, 30)) # 다음 그룹과의 간격을 넓게 둡니다.
        self.ent_minutes.insert(0, "5")  # 기본값 5분 설정

        # 경고 임계 시간 입력 라벨 및 엔트리
        ttk.Label(top_center, text="경고 임계(초)", font=("Segoe UI", 11), background="white").pack(side="left", padx=(0, 10))
        self.ent_warn = ttk.Entry(top_center, width=5, font=("Segoe UI", 11), justify="center")
        self.ent_warn.pack(side="left", padx=(0, 10))
        self.ent_warn.insert(0, "30")  # 기본값 30초 설정

        # 3. 타이머 디스플레이 영역 (중앙)
        mid = ttk.Frame(inner, style="CardPlain.TFrame")
        mid.pack(fill="both", expand=True, pady=20)

        # 남은 시간을 크게 보여줄 라벨
        self.lbl_timer = tk.Label(
            mid,
            text="00:00",
            font=("Segoe UI", 90, "bold"), # 매우 큰 폰트로 시인성 확보
            fg="#263238",  # 기본 글자색 (진한 회색)
            bg="white"     # 배경색 (흰색)
        )
        self.lbl_timer.pack(expand=True) # 중앙에 배치

        # 4. 컨트롤 버튼 & 프로그레스 바 영역
        ctrl_frame = ttk.Frame(inner, style="CardPlain.TFrame")
        ctrl_frame.pack(fill="x", pady=30)
        
        # 버튼들을 담을 컨테이너 (중앙 정렬)
        btn_box = ttk.Frame(ctrl_frame, style="CardPlain.TFrame")
        btn_box.pack(anchor="center", pady=(0, 30))

        # 시작 버튼
        self.btn_start = ttk.Button(btn_box, text="▶ 시작", style="Action.TButton", command=self.start_timer)
        self.btn_start.pack(side="left", padx=15)
        
        # 일시정지 버튼
        self.btn_pause = ttk.Button(btn_box, text="⏸ 일시정지", style="Action.TButton", command=self.pause_resume_timer)
        self.btn_pause.pack(side="left", padx=15)
        
        # 초기화 버튼
        self.btn_reset = ttk.Button(btn_box, text="↺ 초기화", style="Action.TButton", command=self.reset_timer)
        self.btn_reset.pack(side="left", padx=15)

        # 진행률 표시 바 (두꺼운 스타일 적용)
        self.pb_timer = ttk.Progressbar(
            ctrl_frame,
            orient="horizontal",
            mode="determinate",
            length=500, # 길이를 넉넉하게 설정
            style="Thick.Horizontal.TProgressbar"
        )
        self.pb_timer.pack(fill="x", padx=60) # 좌우 여백을 주어 안정감 있게 배치

        # 5. 하단 팁 영역 (AI 코칭 및 사용법 안내)
        self.lbl_tip = tk.Label(
            inner,
            text="Tip) 남은 시간이 임계값 이하로 떨어지면 주황색, 0이 되면 빨간색으로 깜박입니다.",
            font=("Segoe UI", 10),
            fg="#78909C", # 연한 회색 텍스트
            bg="white",
            wraplength=600
        )
        self.lbl_tip.pack(side="bottom", pady=(10, 0))

        # AI 코칭 메시지를 표시할 라벨
        self.lbl_timer_tip = tk.Label(
            inner,
            textvariable=self.var_timer_tip, # AI 팁 변수와 연결
            font=("Segoe UI", 10, "bold"),
            fg="#3F51B5", # 강조색 (인디고)
            bg="white"
        )
        self.lbl_timer_tip.pack(side="bottom", pady=(5, 0))

    # -----------------------------
    # 타이머 포맷/제어 유틸리티
    # -----------------------------
    def _format_sec(self, s: int) -> str:
        """
        초 단위 정수를 'MM:SS' 형식의 문자열로 변환합니다.
        예: 65 -> "01:05"
        """
        s = max(0, int(s))  # 음수가 되지 않도록 방지하고 정수화합니다.
        m, ss = divmod(s, 60)  # 분과 초로 나눕니다.
        return f"{m:02d}:{ss:02d}"  # 두 자리 숫자로 패딩하여 반환합니다.

    def _set_controls_running(self, running: bool) -> None:
        """
        타이머 실행 상태에 따라 버튼과 입력 필드의 활성화/비활성화 상태를 전환합니다.
        
        Args:
            running: 타이머가 실행 중이면 True, 아니면 False
        """
        if running:  # 타이머가 실행 중일 때
            self.btn_start.config(state="disabled")  # 시작 버튼 비활성화 (중복 시작 방지)
            self.btn_pause.config(state="normal", text="일시정지")  # 일시정지 버튼 활성화
            self.btn_reset.config(state="normal")  # 초기화 버튼 활성화
            self.ent_minutes.config(state="disabled")  # 시간 설정 변경 불가
            self.ent_warn.config(state="disabled")     # 경고 설정 변경 불가
        else:  # 타이머가 멈춰 있거나 초기화 상태일 때
            self.btn_start.config(state="normal")  # 시작 버튼 활성화
            self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 버튼 비활성화
            self.btn_reset.config(state="disabled")  # 초기화 버튼 비활성화
            self.ent_minutes.config(state="normal")  # 시간 설정 가능
            self.ent_warn.config(state="normal")     # 경고 설정 가능

    def _stop_tick_loop(self) -> None:
        """
        현재 예약된 타이머 갱신 루프(after)가 있다면 취소합니다.
        """
        if self._timer_after_id is not None:  # 예약 ID가 존재하면
            try:
                self.after_cancel(self._timer_after_id)  # Tkinter after 예약 취소
            except Exception:
                pass  # 이미 실행되었거나 취소된 경우 무시
            self._timer_after_id = None  # ID 초기화

    def _stop_blink(self) -> None:
        """
        타임업 후 진행 중인 깜박임 효과를 중지하고, 라벨 색상을 원래대로 복원합니다.
        """
        if self._blink_after_id is not None:  # 깜박임 예약이 존재하면
            try:
                self.after_cancel(self._blink_after_id)  # 예약 취소
            except Exception:
                pass
            self._blink_after_id = None  # ID 초기화
        self._blink_on = False  # 깜박임 상태 초기화
        self.lbl_timer.config(fg="black")  # 라벨 색상을 검정색으로 복원

    def _start_blink(self) -> None:
        """
        타임업 상태에서 라벨 색상을 빨간색과 검정색으로 번갈아 변경하여 깜박임 효과를 줍니다.
        """
        self._blink_on = not self._blink_on  # 상태 토글 (True <-> False)
        self.lbl_timer.config(fg=("red" if self._blink_on else "black"))  # 상태에 따라 색상 변경
        self._blink_after_id = self.after(450, self._start_blink)  # 0.45초마다 재귀적으로 호출

    # -----------------------------
    # 타이머 시작/일시정지/초기화 로직
    # -----------------------------
    def start_timer(self) -> None:
        """
        사용자 입력을 검증하고 새로운 타이머를 시작합니다.
        """
        self._stop_tick_loop()  # 기존에 실행 중인 타이머 루프가 있다면 중지
        self._stop_blink()  # 깜박임 효과도 중지

        # 1. 발표 시간 입력 검증
        try:
            minutes = float(self.ent_minutes.get().strip())  # 입력값을 실수로 변환
        except Exception:
            self.ent_minutes.focus_set()
            from tkinter import messagebox
            messagebox.showerror("입력 오류", "발표 시간(분)을 숫자로 입력하세요. 예: 5 또는 7.5", parent=self.winfo_toplevel())
            return

        if minutes <= 0:  # 0 이하의 값은 허용하지 않음
            from tkinter import messagebox
            messagebox.showerror("입력 오류", "발표 시간(분)은 0보다 커야 합니다.", parent=self.winfo_toplevel())
            self.ent_minutes.focus_set()
            return

        # 2. 경고 임계 시간 입력 검증
        try:
            warn = int(self.ent_warn.get().strip())  # 입력값을 정수로 변환
        except Exception:
            from tkinter import messagebox
            messagebox.showerror("입력 오류", "경고 임계(초)를 정수로 입력하세요. 예: 30", parent=self.winfo_toplevel())
            self.ent_warn.focus_set()
            return

        if warn < 1:  # 최소 1초 이상이어야 함
            from tkinter import messagebox
            messagebox.showerror("입력 오류", "경고 임계(초)는 1초 이상이어야 합니다.", parent=self.winfo_toplevel())
            self.ent_warn.focus_set()
            return

        # 3. 타이머 설정 및 시작
        total_sec = int(round(minutes * 60))  # 분을 초로 변환
        self.timer_total_sec = total_sec  # 총 시간 저장
        # 경고 임계값은 총 시간보다 클 수 없으므로 조정(clamp)
        self.timer_warn_sec = min(warn, max(1, total_sec - 1))
        
        self.timer_running = True  # 실행 상태로 설정
        self.timer_end_mono = time.monotonic() + self.timer_total_sec  # 종료 목표 시간 계산
        self.timer_remain_sec = self.timer_total_sec  # 남은 시간 초기화

        # UI 초기화
        self.lbl_timer.config(text=self._format_sec(self.timer_remain_sec), fg="black")
        self.pb_timer.config(maximum=self.timer_total_sec, value=0)

        self._set_controls_running(True)  # 버튼 상태 업데이트
        self._tick_update()  # 타이머 갱신 루프 시작

        # 메인 앱에 타이머 시작 알림 (AI 코칭용)
        if self.on_started:
            self.on_started()

    def pause_resume_timer(self) -> None:
        """
        타이머의 일시정지 및 재개 기능을 토글합니다.
        """
        if not self.timer_running:  # 현재 멈춰있는 상태라면 (재개)
            if self.timer_remain_sec <= 0:  # 이미 종료된 타이머라면 무시
                return
            # 남은 시간을 기준으로 새로운 종료 목표 시간을 계산
            self.timer_end_mono = time.monotonic() + self.timer_remain_sec
            self.timer_running = True  # 실행 상태로 변경
            self.btn_pause.config(text="일시정지")  # 버튼 텍스트 변경
            self._tick_update()  # 루프 재시작
            return

        # 현재 실행 중인 상태라면 (일시정지)
        now_mono = time.monotonic()
        remain = max(0, int(math.ceil(self.timer_end_mono - now_mono)))  # 남은 시간 계산
        self.timer_remain_sec = remain  # 남은 시간 저장
        self.timer_running = False  # 실행 중단 상태로 변경
        self.btn_pause.config(text="계속")  # 버튼 텍스트 변경
        self._stop_tick_loop()  # 루프 중단

    def reset_timer(self) -> None:
        """
        타이머를 완전히 초기화하고 정지합니다.
        """
        self.timer_running = False  # 실행 상태 해제
        self.timer_total_sec = 0  # 총 시간 초기화
        self.timer_remain_sec = 0  # 남은 시간 초기화
        self.timer_end_mono = 0.0  # 목표 시간 초기화
        
        self._stop_tick_loop()  # 루프 중단
        self._stop_blink()  # 깜박임 중단
        
        self.lbl_timer.config(text="00:00", fg="black")  # 디스플레이 초기화
        self.pb_timer.config(maximum=1, value=0)  # 프로그레스 바 초기화
        self._set_controls_running(False)  # 버튼 상태 초기화

    # -----------------------------
    # 타임업 및 갱신 루프
    # -----------------------------
    def _on_time_up(self) -> None:
        """
        타이머 시간이 0이 되었을 때 호출되어 종료 처리를 수행합니다.
        """
        self.timer_running = False  # 실행 상태 해제
        self._stop_tick_loop()  # 루프 중단
        
        self.lbl_timer.config(text="00:00", fg="red")  # 0초 표시 및 빨간색 변경
        self.pb_timer.config(value=self.timer_total_sec)  # 프로그레스 바 꽉 채움
        
        try:
            self.bell()  # 시스템 알림음 재생
        except Exception:
            pass  # 알림음 재생 실패 시 무시
            
        self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 버튼 비활성화
        self._start_blink()  # 깜박임 효과 시작

    def _tick_update(self) -> None:
        """
        약 200ms 간격으로 호출되어 남은 시간을 갱신하고 UI를 업데이트합니다.
        """
        if not self.timer_running:  # 실행 중이 아니면 중단
            return
            
        now_mono = time.monotonic()  # 현재 시간 측정
        # 남은 시간 계산 (목표 시간 - 현재 시간), 0 미만은 0으로 처리
        remain = int(max(0, math.ceil(self.timer_end_mono - now_mono)))
        self.timer_remain_sec = remain  # 상태 업데이트
        self.lbl_timer.config(text=self._format_sec(remain))  # 라벨 텍스트 갱신

        if remain == 0:  # 시간이 다 되었으면
            self._on_time_up()  # 종료 처리
            return
        elif remain <= self.timer_warn_sec:  # 경고 임계값 이하로 떨어지면
            self.lbl_timer.config(fg="orange")  # 글자색을 주황색으로 변경
        else:
            self.lbl_timer.config(fg="black")  # 평상시는 검정색

        done = self.timer_total_sec - remain  # 경과 시간 계산
        self.pb_timer.config(value=done)  # 프로그레스 바 업데이트

        # 200ms 후에 다시 이 함수를 호출하도록 예약 (재귀적 호출)
        self._timer_after_id = self.after(200, self._tick_update)

    # -----------------------------
    # AI 연동 및 종료 처리
    # -----------------------------
    def get_state_for_ai(self) -> dict:
        """
        AI 컨텍스트 생성을 위해 현재 타이머 상태를 딕셔너리로 반환합니다.
        """
        return {
            "running": self.timer_running,
            "remain_sec": self.timer_remain_sec,
            "total_sec": self.timer_total_sec,
            "warn_sec": self.timer_warn_sec,
        }

    def set_ai_tip(self, text: str) -> None:
        """
        AI가 생성한 코칭 문구를 화면 하단 라벨에 표시합니다.
        """
        self.var_timer_tip.set(text)  # StringVar 값 변경 -> 라벨 자동 갱신

    def on_close(self) -> None:
        """
        프로그램 종료 시 호출되어 실행 중인 타이머 루프를 정리합니다.
        """
        self._stop_tick_loop()  # 틱 루프 취소
        self._stop_blink()  # 깜박임 루프 취소
