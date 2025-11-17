# tab_timer.py  --------------------------------------------------
# 발표 타이머 탭 UI 및 타이머 로직을 담당하는 모듈이다.

from __future__ import annotations  # 향후 타입 참조를 문자열로 허용

import time  # 단조 증가 시계(time.monotonic)를 사용해 타이머 정확도 유지
import math  # 남은 시간 계산 시 올림/내림에 사용
import tkinter as tk  # Tkinter 기본 위젯
from tkinter import ttk  # ttk 스타일 위젯

from core import PAD8  # 여백 설정을 재사용


# ─────────────────────────────────────────────
# 타이머 탭 프레임
# ─────────────────────────────────────────────

class TimerTab(ttk.Frame):
    """발표 타이머 UI + 타이머 동작 로직을 가진 탭."""

    def __init__(self, master: tk.Misc, on_started=None) -> None:
        """
        master: Notebook 을 부모로 받는다.
        on_started: 타이머가 새로 시작될 때 한 번 호출할 콜백(AI 코칭용)
        """
        super().__init__(master)  # Frame 기본 초기화
        self.on_started = on_started  # 타이머 시작 콜백 저장

        # 타이머 상태 관련 필드 초기화
        self._timer_after_id: str | None = None  # after 로 예약된 틱 루프 ID
        self._blink_after_id: str | None = None  # after 로 예약된 깜박임 루프 ID
        self.timer_running: bool = False  # 현재 타이머 동작 여부
        self.timer_total_sec: int = 0  # 총 타이머 시간(초)
        self.timer_warn_sec: int = 30  # 경고 임계(초)
        self.timer_end_mono: float = 0.0  # time.monotonic 기준 종료 목표 시각
        self.timer_remain_sec: int = 0  # 남은 시간(초)
        self._blink_on: bool = False  # 깜박임 상태 토글

        self.var_timer_tip = tk.StringVar(value="")  # AI 코칭 문구를 위한 StringVar

        self._build_ui()  # 실제 위젯 구성

    # -----------------------------
    # UI 구성
    # -----------------------------
    def _build_ui(self) -> None:
        """상단 입력/버튼, 중앙 타이머 표시, 하단 안내/AI 코칭을 구성한다."""
        top = ttk.Frame(self)  # 상단 입력/버튼 영역
        top.pack(fill="x", **PAD8)  # 좌우로 채우고 여백 적용

        ttk.Label(top, text="발표 시간(분)").pack(side="left")  # 발표시간 라벨
        self.ent_minutes = ttk.Entry(top, width=6)  # 분 입력 필드
        self.ent_minutes.pack(side="left", padx=(4, 12))  # 라벨 오른쪽에 여백 두고 배치
        self.ent_minutes.insert(0, "5")  # 기본값 5분

        ttk.Label(top, text="경고 임계(초)").pack(side="left")  # 경고 임계 라벨
        self.ent_warn = ttk.Entry(top, width=6)  # 경고 초 입력 필드
        self.ent_warn.pack(side="left", padx=(4, 12))  # 우측에 여백 배치
        self.ent_warn.insert(0, "30")  # 기본값 30초

        # 타이머 제어 버튼들 생성
        self.btn_start = ttk.Button(top, text="시작", command=self.start_timer)  # 시작 버튼
        self.btn_pause = ttk.Button(top, text="일시정지",
                                    command=self.pause_resume_timer,
                                    state="disabled")  # 일시정지 버튼(처음엔 비활성)
        self.btn_reset = ttk.Button(top, text="초기화",
                                    command=self.reset_timer,
                                    state="disabled")  # 초기화 버튼(처음엔 비활성)

        # 버튼들을 가로로 나란히 배치
        self.btn_start.pack(side="left", padx=4)
        self.btn_pause.pack(side="left", padx=4)
        self.btn_reset.pack(side="left", padx=4)

        mid = ttk.Frame(self)  # 중앙 타이머 표시 영역
        mid.pack(expand=True, fill="both", **PAD8)  # 남는 공간 대부분 차지

        # 남은 시간을 크게 표시하는 라벨
        self.lbl_timer = tk.Label(
            mid,
            text="00:00",
            font=("Helvetica", 36, "bold"),
        )
        self.lbl_timer.pack(pady=10)  # 위/아래 여백을 주고 배치

        # 진행률 바 (0 ~ 총 시간)
        self.pb_timer = ttk.Progressbar(
            mid,
            orient="horizontal",
            mode="determinate",
            length=360,
        )
        self.pb_timer.pack(fill="x", padx=20, pady=10)  # 가로로 꽉 채우도록 배치

        bottom = ttk.Frame(self)  # 하단 안내 영역
        bottom.pack(fill="x", **PAD8)

        ttk.Label(
            bottom,
            text=(
                "Tip) 남은 시간이 임계값 이하로 떨어지면 주황색, "
                "0이 되면 빨간색으로 깜박이며 종료를 알립니다."
            ),
        ).pack(anchor="w")  # 안내 문구를 왼쪽 정렬로 배치

        # AI 타이머 코칭을 위한 라벨
        self.lbl_timer_tip = ttk.Label(
            self,
            textvariable=self.var_timer_tip,  # StringVar 을 통해 동적 업데이트
            foreground="#1e88e5",  # 파란색 계열 텍스트
        )
        self.lbl_timer_tip.pack(anchor="w", padx=12, pady=(0, 10))  # 아래쪽 여백을 살짝 주고 배치

    # -----------------------------
    # 타이머 포맷/제어 유틸
    # -----------------------------
    def _format_sec(self, s: int) -> str:
        """정수 초를 'MM:SS' 형식의 문자열로 바꾼다."""
        s = max(0, int(s))  # 음수 방지 + 정수화
        m, ss = divmod(s, 60)  # 분과 초로 나누기
        return f"{m:02d}:{ss:02d}"  # 두 자리 0 패딩 형식으로 반환

    def _set_controls_running(self, running: bool) -> None:
        """타이머 실행 상태에 따라 버튼/입력 필드 활성/비활성을 전환한다."""
        if running:  # 타이머가 돌아가는 상태
            self.btn_start.config(state="disabled")  # 시작 버튼 비활성
            self.btn_pause.config(state="normal", text="일시정지")  # 일시정지 활성
            self.btn_reset.config(state="normal")  # 초기화 활성
            self.ent_minutes.config(state="disabled")  # 설정값 변경 방지
            self.ent_warn.config(state="disabled")
        else:  # 타이머가 멈춰 있는 상태
            self.btn_start.config(state="normal")  # 시작 활성
            self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 비활성
            self.btn_reset.config(state="disabled")  # 초기화 비활성
            self.ent_minutes.config(state="normal")  # 다시 입력 가능
            self.ent_warn.config(state="normal")

    def _stop_tick_loop(self) -> None:
        """예약된 타이머 틱(after) 호출이 있으면 취소한다."""
        if self._timer_after_id is not None:  # 예약 ID 가 있을 때만
            try:
                self.after_cancel(self._timer_after_id)  # after 예약 취소
            except Exception:
                pass  # 이미 실행된 경우 예외 무시
            self._timer_after_id = None  # ID 초기화

    def _stop_blink(self) -> None:
        """타임업 후 진행 중인 깜박임 루프를 종료하고 색상을 복원한다."""
        if self._blink_after_id is not None:  # 깜박임 예약이 있을 때
            try:
                self.after_cancel(self._blink_after_id)  # 예약 취소
            except Exception:
                pass
            self._blink_after_id = None  # ID 초기화
        self._blink_on = False  # 토글 상태 초기화
        self.lbl_timer.config(fg="black")  # 라벨 색상 원래대로 복원

    def _start_blink(self) -> None:
        """타임업 상태에서 빨강/검정으로 라벨 색상을 번갈아가며 깜박인다."""
        self._blink_on = not self._blink_on  # 토글 플래그 반전
        self.lbl_timer.config(fg=("red" if self._blink_on else "black"))  # 색상을 토글
        self._blink_after_id = self.after(450, self._start_blink)  # 0.45초마다 재귀적으로 호출

    # -----------------------------
    # 타이머 시작/일시정지/초기화
    # -----------------------------
    def start_timer(self) -> None:
        """입력값을 검증한 뒤 새 타이머를 시작한다."""
        self._stop_tick_loop()  # 기존 틱 루프가 있으면 먼저 중지
        self._stop_blink()  # 깜박임도 중지

        try:
            minutes = float(self.ent_minutes.get().strip())  # 분 입력을 float 으로 파싱
        except Exception:
            # 숫자 형식이 아닐 때 에러 메시지
            self.ent_minutes.focus_set()
            from tkinter import messagebox
            messagebox.showerror("입력 오류", "발표 시간(분)을 숫자로 입력하세요. 예: 5 또는 7.5", parent=self.winfo_toplevel())
            return

        if minutes <= 0:  # 0 이하의 값은 허용하지 않음
            from tkinter import messagebox
            messagebox.showerror("입력 오류", "발표 시간(분)은 0보다 커야 합니다.", parent=self.winfo_toplevel())
            self.ent_minutes.focus_set()
            return

        try:
            warn = int(self.ent_warn.get().strip())  # 경고 임계초를 int 로 파싱
        except Exception:
            from tkinter import messagebox
            messagebox.showerror("입력 오류", "경고 임계(초)를 정수로 입력하세요. 예: 30", parent=self.winfo_toplevel())
            self.ent_warn.focus_set()
            return

        if warn < 1:  # 최소 1초
            from tkinter import messagebox
            messagebox.showerror("입력 오류", "경고 임계(초)는 1초 이상이어야 합니다.", parent=self.winfo_toplevel())
            self.ent_warn.focus_set()
            return

        total_sec = int(round(minutes * 60))  # 분을 초 단위로 변환
        self.timer_total_sec = total_sec  # 총 시간 저장
        # 경고 임계치는 총 시간보다 커지지 않도록 클램프
        self.timer_warn_sec = min(warn, max(1, total_sec - 1))
        self.timer_running = True  # 타이머 실행 플래그
        self.timer_end_mono = time.monotonic() + self.timer_total_sec  # 현재 시각 기준 종료 목표 시각
        self.timer_remain_sec = self.timer_total_sec  # 남은 시간 초기화

        # UI 초기화
        self.lbl_timer.config(text=self._format_sec(self.timer_remain_sec), fg="black")
        self.pb_timer.config(maximum=self.timer_total_sec, value=0)

        self._set_controls_running(True)  # 버튼/입력 상태 전환
        self._tick_update()  # 틱 루프 시작

        # 메인 앱에 '타이머가 막 시작됨' 을 알리기(AI 코칭 프롬프트용)
        if self.on_started:
            self.on_started()

    def pause_resume_timer(self) -> None:
        """일시정지와 계속을 토글한다."""
        if not self.timer_running:  # 현재 멈춰있는 상태에서 호출되면
            if self.timer_remain_sec <= 0:  # 이미 끝난 타이머면 아무 것도 안 함
                return
            # 남은 시간을 기준으로 새로운 종료 목표 시각 계산
            self.timer_end_mono = time.monotonic() + self.timer_remain_sec
            self.timer_running = True  # 다시 실행 상태로 전환
            self.btn_pause.config(text="일시정지")  # 버튼 텍스트 변경
            self._tick_update()  # 틱 루프 다시 시작
            return

        # 여기까지 왔다는 것은 현재 실행 중이므로 일시정지 동작
        now_mono = time.monotonic()  # 현재 단조 시각
        remain = max(0, int(math.ceil(self.timer_end_mono - now_mono)))  # 남은 시간 계산
        self.timer_remain_sec = remain  # 상태에 저장
        self.timer_running = False  # 실행 중단
        self.btn_pause.config(text="계속")  # 버튼 텍스트를 '계속'으로 변경
        self._stop_tick_loop()  # 틱 루프 중단

    def reset_timer(self) -> None:
        """타이머 상태를 완전히 초기화한다."""
        self.timer_running = False  # 실행 플래그 해제
        self.timer_total_sec = 0  # 총 시간 초기화
        self.timer_remain_sec = 0  # 남은 시간 초기화
        self.timer_end_mono = 0.0  # 목표 시각 초기화
        self._stop_tick_loop()  # 틱 루프 중단
        self._stop_blink()  # 깜박임 중단
        self.lbl_timer.config(text="00:00", fg="black")  # 표시 시간/색상 초기화
        self.pb_timer.config(maximum=1, value=0)  # 진행률 바 초기화
        self._set_controls_running(False)  # 버튼/입력 상태 초기화

    # -----------------------------
    # 타임업 / 틱 업데이트
    # -----------------------------
    def _on_time_up(self) -> None:
        """남은 시간이 0이 되었을 때 타임업 처리를 수행한다."""
        self.timer_running = False  # 실행 상태 해제
        self._stop_tick_loop()  # 틱 루프 중단
        self.lbl_timer.config(text="00:00", fg="red")  # 0초를 빨간색으로 표시
        self.pb_timer.config(value=self.timer_total_sec)  # 진행률 바를 끝까지 채움
        try:
            self.bell()  # OS 기본 알림음 울리기
        except Exception:
            pass  # 일부 환경에서 벨이 지원되지 않을 수 있으므로 예외 무시
        self.btn_pause.config(state="disabled", text="일시정지")  # 일시정지 버튼 비활성화
        self._start_blink()  # 깜박임 시작

    def _tick_update(self) -> None:
        """200ms 간격으로 남은 시간을 갱신하는 틱 루프."""
        if not self.timer_running:  # 실행 중이 아니면 루프 중단
            return
        now_mono = time.monotonic()  # 현재 단조 시각
        # 목표 시각까지 남은 시간(초)을 계산하고 0 미만은 0 으로 처리
        remain = int(max(0, math.ceil(self.timer_end_mono - now_mono)))
        self.timer_remain_sec = remain  # 남은 초를 상태에 반영
        self.lbl_timer.config(text=self._format_sec(remain))  # 라벨 텍스트 갱신

        if remain == 0:  # 0초가 되면 타임업 처리
            self._on_time_up()
            return
        elif remain <= self.timer_warn_sec:  # 경고 임계 이하
            self.lbl_timer.config(fg="orange")  # 주황색으로 표시
        else:
            self.lbl_timer.config(fg="black")  # 평상시 검정

        done = self.timer_total_sec - remain  # 경과 시간(초)
        self.pb_timer.config(value=done)  # 진행률 바 갱신

        # 200ms 후에 다시 자신을 호출하도록 예약
        self._timer_after_id = self.after(200, self._tick_update)

    # -----------------------------
    # AI 연동 / 종료 처리
    # -----------------------------
    def get_state_for_ai(self) -> dict:
        """AI 컨텍스트 생성을 위해 타이머 상태를 dict 로 요약해 반환한다."""
        return {
            "running": self.timer_running,
            "remain_sec": self.timer_remain_sec,
            "total_sec": self.timer_total_sec,
            "warn_sec": self.timer_warn_sec,
        }

    def set_ai_tip(self, text: str) -> None:
        """AI 타이머 코칭 문구를 라벨에 표시한다."""
        self.var_timer_tip.set(text)  # StringVar 에 텍스트 설정

    def on_close(self) -> None:
        """메인 윈도우 종료 시 타이머 관련 after 루프를 정리한다."""
        self._stop_tick_loop()  # 틱 루프 취소
        self._stop_blink()  # 깜박임 루프 취소
