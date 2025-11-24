# tab_report.py  --------------------------------------------------
# 할 일 통계를 시각화하는 '리포트' 탭 모듈이다.
# - 완료율 도넛
# - 상태 구성 스택바
# - 이번 주(월~일) 학습 히트맵 + 상세 팝업
# - 완료율 마일스톤(50,80,100%)에서 컨페티 애니메이션

from __future__ import annotations  # 향후 참조를 문자열로 허용

from datetime import date, timedelta  # 오늘 날짜/주간 계산에 사용
import random  # 컨페티 파티클 색/위치 랜덤에 사용
import tkinter as tk  # Tkinter 기본 위젯
from tkinter import ttk  # ttk 스타일 위젯

from core import (  # 공통 기능 import
    PAD8,             # 여백 설정
    Todo,             # Todo 데이터 모델
    parse_date,       # 날짜 파싱
    STATUS_ICON,      # 상태 아이콘(요일 상세 팝업에 사용)
    center_over,      # 팝업 위치 조정
)


# ─────────────────────────────────────────────
# 리포트 탭 프레임
# ─────────────────────────────────────────────

class ReportTab(ttk.Frame):
    """Todo 리스트를 기반으로 통계를 계산/시각화하는 탭."""

    def __init__(
        self,
        master: tk.Misc,               # Notebook 을 부모로 받는다.
        todos: list[Todo],             # 공유 Todo 리스트(메인/할 일 탭과 같은 객체)
        on_request_edit=None,          # 요일 상세에서 '선택 편집'을 눌렀을 때 호출할 콜백
    ) -> None:
        super().__init__(master)  # Frame 초기화
        self.todos = todos  # Todo 리스트 참조 저장
        self.on_request_edit = on_request_edit  # 외부 편집 콜백 저장

        # 리포트 자동 갱신 루프 상태
        self._report_after_id: str | None = None  # after 예약 ID
        self._last_rate: float = 0.0  # 이전 완료율 (마일스톤 체크용)
        self._report_booted: bool = False  # 첫 갱신 이후 여부 플래그

        # 히트맵 상세/클릭 처리를 위한 상태
        self._week_detail_cache: list[dict] | None = None  # 요일별 상세 Todo 캐시
        self._heat_cells: list[tuple[int, tuple[int, int, int, int]]] = []  # (요일 인덱스, bbox) 목록

        self._ring_anim_start: float = 0.0  # 도넛 애니메이션 시작값 캐시
        self._last_stats: dict | None = None  # 마지막으로 계산된 통계 저장(AI 컨텍스트용)

        self._build_ui()  # 위젯 구성
        self.refresh_now()  # 초기 리포트 한 번 계산/표시

    # -----------------------------
    # UI 구성
    # -----------------------------
    def _build_ui(self) -> None:
        """텍스트 KPI + 도넛 + 스택바 + 주간 히트맵의 UI 구조를 만든다."""
        self.configure(style="TFrame")  # 배경색 설정

        # 메인 컨테이너 (여백 추가)
        main_container = ttk.Frame(self, style="TFrame", padding=20)
        main_container.pack(fill="both", expand=True)

        # 카드 프레임 (흰색 배경, 그림자 효과 느낌)
        card = ttk.Frame(main_container, style="Card.TFrame", padding=30)
        card.pack(fill="both", expand=True)

        # ─── 타이틀 영역 ───
        title_frame = ttk.Frame(card, style="Card.TFrame")
        title_frame.pack(fill="x", pady=(0, 20))
        
        ttk.Label(
            title_frame,
            text="📊 주간 성과 리포트",
            font=("Segoe UI", 18, "bold"),  # 폰트 크기 키움
            foreground="#3F51B5",  # 강조색 사용
            background="white"
        ).pack(side="left")

        # ─── 컨텐츠 영역 (수직 중앙 정렬을 위한 프레임) ───
        content_frame = ttk.Frame(card, style="Card.TFrame")
        content_frame.pack(fill="both", expand=True)
        
        # 상단/하단 여백을 위한 grid row 설정
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_rowconfigure(4, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        # 실제 내용물 컨테이너
        inner_box = ttk.Frame(content_frame, style="Card.TFrame")
        inner_box.grid(row=1, column=0, sticky="ew")

        # 1. 상단: 도넛 + KPI 텍스트
        top_section = ttk.Frame(inner_box, style="Card.TFrame")
        top_section.pack(fill="x", pady=(0, 30))

        # 도넛 캔버스
        self.cnv_ring = tk.Canvas(
            top_section,
            width=180, height=180,  # 크기 약간 키움
            bg="white",
            highlightthickness=0
        )
        self.cnv_ring.pack(side="left", padx=(20, 40))

        # KPI 텍스트 그룹
        kpi_group = ttk.Frame(top_section, style="Card.TFrame")
        kpi_group.pack(side="left", fill="both", expand=True)

        self.lbl_rate = ttk.Label(
            kpi_group,
            text="완료율 0.0%",
            font=("Segoe UI", 24, "bold"),  # 폰트 키움
            background="white"
        )
        self.lbl_rate.pack(anchor="w", pady=(0, 15))

        # KPI 항목 스타일
        kpi_style = {"font": ("Segoe UI", 11), "background": "white", "foreground": "#546E7A"}
        
        self.var_avg = tk.StringVar(value="평균 기간: 0.0일")
        self.var_soon = tk.StringVar(value="마감 임박: 0건")
        self.var_over = tk.StringVar(value="지남: 0건")
        self.var_counts = tk.StringVar(value="상태 구성: 미완 0 · 진행 0 · 완료 0")

        ttk.Label(kpi_group, textvariable=self.var_avg, **kpi_style).pack(anchor="w", pady=2)
        ttk.Label(kpi_group, textvariable=self.var_soon, **kpi_style).pack(anchor="w", pady=2)
        ttk.Label(kpi_group, textvariable=self.var_over, **kpi_style).pack(anchor="w", pady=2)
        ttk.Label(kpi_group, textvariable=self.var_counts, **kpi_style).pack(anchor="w", pady=(10, 0))

        # 2. 중간: 스택바
        self.cnv_stack = tk.Canvas(
            inner_box,
            height=24,
            bg="white",
            highlightthickness=0
        )
        self.cnv_stack.pack(fill="x", pady=(0, 30))

        # 3. 하단: 히트맵
        # 집계 범위 라벨
        self.var_week_range = tk.StringVar(value="")
        ttk.Label(
            inner_box,
            textvariable=self.var_week_range,
            font=("Segoe UI", 10),
            foreground="#78909C",
            background="white"
        ).pack(anchor="w", pady=(0, 5))

        self.cnv_heat = tk.Canvas(
            inner_box,
            height=80,  # 높이 약간 키움
            bg="white",
            highlightthickness=0,
            cursor="hand2"
        )
        self.cnv_heat.pack(fill="x")
        self.cnv_heat.bind("<Button-1>", self._on_heat_click)
        self.cnv_heat.bind("<Double-Button-1>", self._on_heat_dblclick)

        # 푸터 메시지
        ttk.Label(
            card,
            text="※ 5초마다 자동 갱신 · 리스트 변경 시 즉시 반영",
            font=("Segoe UI", 9),
            foreground="#90A4AE",
            background="white"
        ).pack(side="bottom", anchor="e", pady=(10, 0))

    # -----------------------------
    # 자동 갱신 루프 제어
    # -----------------------------
    def _stop_report_loop(self) -> None:
        """after 로 예약된 리포트 자동 갱신이 있으면 취소한다."""
        if self._report_after_id:
            try:
                self.after_cancel(self._report_after_id)  # 예약 취소
            except Exception:
                pass  # 이미 실행된 경우 예외 무시
            self._report_after_id = None  # ID 초기화

    # -----------------------------
    # 통계 계산
    # -----------------------------
    def calc_report_stats(self) -> dict:
        """
        self.todos 를 기반으로 각종 통계를 계산한다.
        return: {
          'rate': 완료율(%),
          'avg_days': 평균 기간,
          'soon': 마감 임박 수,
          'overdue': 마감 초과 수,
          'counts': (미완, 진행, 완료),
          'week_bins': [월~일 마감 Todo 수],
          'week_detail': 요일별 상세 Todo 구조,
          'week_start': 이번 주 월요일 날짜 문자열,
          'week_end': 이번 주 일요일 날짜 문자열,
        }
        """
        total = len(self.todos)  # 전체 Todo 개수
        today = date.today()  # 오늘 날짜
        # 이번 주 월요일(weekday() == 0) 기준 시작/끝일 계산
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)

        if total == 0:  # Todo 가 없으면 의미 있는 통계가 없으므로 기본값 반환
            return {
                "rate": 0.0,
                "avg_days": 0.0,
                "soon": 0,
                "overdue": 0,
                "counts": (0, 0, 0),
                "week_bins": [0] * 7,
                "week_detail": [
                    {"due": [], "open": [], "doing": [], "done": []} for _ in range(7)
                ],
                "week_start": start_week.isoformat(),
                "week_end": end_week.isoformat(),
            }

        # 상태별 개수를 세기 위한 변수
        cnt0 = sum(1 for t in self.todos if t.status == 0)  # 미완료
        cnt1 = sum(1 for t in self.todos if t.status == 1)  # 진행중
        cnt2 = sum(1 for t in self.todos if t.status == 2)  # 완료
        rate = round(cnt2 / total * 100, 1)  # 완료율(%) 소수점 첫째자리까지

        soon = 0  # 마감 임박 Todo 수
        overdue = 0  # 마감 초과 Todo 수
        durations: list[int] = []  # 기간(일수) 목록
        week_bins = [0] * 7  # 이번 주 월~일까지 요일별 마감 Todo 수
        week_detail = [
            {"due": [], "open": [], "doing": [], "done": []} for _ in range(7)
        ]  # 요일별 상세 구조

        for t in self.todos:  # 각 Todo 순회
            try:
                d1 = parse_date(t.start).date()  # 시작일
                d2 = parse_date(t.end).date()  # 종료일(마감일)
            except Exception:
                continue  # 날짜가 잘못된 경우 해당 Todo 는 통계에서 제외

            if d2 >= d1:  # 마이너스 기간은 제외하고 정상적인 기간만 계산
                durations.append((d2 - d1).days)

            delta = (d2 - today).days  # 오늘 기준 남은 일수
            if t.status != 2 and 0 <= delta <= 3:
                soon += 1  # 3일 이내 마감이며 미완/진행중이면 임박++
            if t.status != 2 and delta < 0:
                overdue += 1  # 이미 마감이 지났고 완료가 아니면 지남++

            # 이번 주 안에 마감되는 Todo 를 히트맵 데이터에 반영
            off = (d2 - start_week).days  # 이번 주 월요일 기준 offset(0~6)
            if 0 <= off < 7:
                week_bins[off] += 1  # 해당 요일 칸 카운트 증가
                # 상태별로도 분류
                if t.status == 0:
                    week_detail[off]["open"].append(t)
                elif t.status == 1:
                    week_detail[off]["doing"].append(t)
                else:
                    week_detail[off]["done"].append(t)
                week_detail[off]["due"].append(t)

        avg_days = round(sum(durations) / len(durations), 1) if durations else 0.0

        return {
            "rate": rate,
            "avg_days": avg_days,
            "soon": soon,
            "overdue": overdue,
            "counts": (cnt0, cnt1, cnt2),
            "week_bins": week_bins,
            "week_detail": week_detail,
            "week_start": start_week.isoformat(),
            "week_end": end_week.isoformat(),
        }

    # -----------------------------
    # 메인에서 호출: 즉시 갱신
    # -----------------------------
    def refresh_now(self) -> None:
        """현재 Todo 리스트 상태를 기반으로 리포트를 즉시 계산하고 5초 후 재갱신 예약."""
        self._stop_report_loop()  # 중복 루프 방지를 위해 먼저 취소

        s = self.calc_report_stats()  # 통계 계산
        self._last_stats = s  # 마지막 통계 캐싱(AI 컨텍스트용)

        # KPI 라벨 갱신
        self.lbl_rate.config(text=f"완료율 {s['rate']:.1f}%")
        self.var_avg.set(f"평균 기간: {s['avg_days']}일")
        self.var_soon.set(f"마감 임박: {s['soon']}건")
        self.var_over.set(f"지남: {s['overdue']}건")
        c0, c1, c2 = s["counts"]
        self.var_counts.set(f"상태 구성: 미완 {c0} · 진행 {c1} · 완료 {c2}")

        col = self._rate_color(s["rate"])  # 완료율에 따른 색상
        self.lbl_rate.config(foreground=col)  # 레이블 색 적용

        self._animate_ring_to(s["rate"])  # 도넛 애니메이션
        self._draw_stack(s["counts"])  # 스택바 그리기

        # 주간 범위 라벨 업데이트
        self.var_week_range.set(
            f"📅 집계 범위: {s['week_start']} ~ {s['week_end']} (월~일 기준)"
        )

        # 히트맵 데이터 캐시 및 렌더링
        self._week_detail_cache = s.get("week_detail", None)
        self._draw_heat(s["week_bins"], self._week_detail_cache)

        # 완료율 마일스톤(50/80/100%) 돌파 시 컨페티
        prev = self._last_rate
        if self._report_booted and any(prev < m <= s["rate"] for m in (50, 80, 100)):
            self._burst_confetti(duration=800)
        self._report_booted = True
        self._last_rate = s["rate"]

        # 5초 후 다시 자신을 호출하도록 예약
        self._report_after_id = self.after(5000, self.refresh_now)

    # -----------------------------
    # 색상/도넛/스택바/히트맵 렌더링
    # -----------------------------
    def _rate_color(self, rate: float) -> str:
        """완료율에 따라 색상을 선택한다: <50 빨강, <80 주황, 그 외 초록."""
        if rate < 50:
            return "#e53935"  # 빨강
        if rate < 80:
            return "#fb8c00"  # 주황
        return "#43a047"  # 초록

    def _draw_ring(self, rate: float) -> None:
        """완료율(0~100)을 도넛 형태로 캔버스에 그린다."""
        c = self.cnv_ring  # 도넛 캔버스
        c.delete("all")  # 이전 내용 제거

        cx, cy, r, th = 80, 80, 70, 14  # 중심 좌표, 반지름, 링 두께
        # 회색 바탕 링
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      outline="#e6e6e6", width=th)

        col = self._rate_color(rate)  # 진행 색상
        extent = 360 * (rate / 100)  # 전체 360도 중 진행각 계산

        # 진행 아크(시작을 90도 위치에서 시계 반대 방향으로 그린다)
        c.create_arc(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            start=90,
            extent=-extent,
            style="arc",
            width=th,
            outline=col,
        )

        # 중앙에 퍼센트 텍스트 표시
        c.create_text(
            cx,
            cy,
            text=f"{rate:.1f}%",
            font=("Helvetica", 16, "bold"),
        )

    def _animate_ring_to(self, target: float) -> None:
        """현재 값에서 target 완료율까지 부드럽게 보간하며 도넛을 갱신한다."""
        start = getattr(self, "_ring_anim_start", self._last_rate)  # 시작값
        if abs(target - start) < 0.2:  # 변화량이 매우 작으면 바로 그려버림
            self._draw_ring(target)
            self._ring_anim_start = target
            return

        # 변화 폭에 비례해 스텝 수를 결정(최소 8스텝)
        steps = max(8, int(abs(target - start) // 2))

        def step(i: int = 0) -> None:
            """각 단계마다 선형 보간된 값을 그리는 내부 함수."""
            val = start + (target - start) * i / steps  # 선형 보간
            self._draw_ring(val)  # 도넛 그림
            if i < steps:  # 아직 마지막 스텝이 아니면
                self.after(16, step, i + 1)  # 약 60fps 정도로 다음 스텝 예약
            else:
                self._ring_anim_start = target  # 마지막 값 저장

        step()  # 애니메이션 시작

    def _draw_stack(self, counts: tuple[int, int, int]) -> None:
        """상태별 개수를 기반으로 가로 스택바를 그린다."""
        c = self.cnv_stack  # 스택바 캔버스
        c.delete("all")  # 기존 그림 삭제
        w = c.winfo_width() or 400  # 전체 폭(초기에는 0일 수 있으므로 기본값 400)
        h = 22  # 바 높이
        total = max(1, sum(counts))  # 0 으로 나누지 않도록 최소 1

        colors = ["#90a4ae", "#fb8c00", "#43a047"]  # 미완/진행/완료 색상
        x = 0  # 왼쪽 시작 좌표

        for n, col in zip(counts, colors):  # 각 상태별 개수를 순회
            seg = int(w * n / total)  # 전체 폭에서 해당 상태 비율만큼 구간 길이 계산
            c.create_rectangle(x, 0, x + seg, h, fill=col, width=0)  # 채워진 사각형
            x += seg  # 다음 구간의 시작 X 좌표

        # 전체 외곽 박스
        c.create_rectangle(0, 0, w, h, outline="#d0d0d0")

    def _draw_heat(self, bins: list[int], detail: list[dict] | None) -> None:
        """이번 주(월~일) 마감 Todo 수를 색상으로 표현하는 히트맵을 그린다."""
        c = self.cnv_heat  # 히트맵 캔버스
        c.delete("all")  # 이전 그림 초기화
        self._heat_cells = []  # 셀 정보 초기화

        w = c.winfo_width() or 420  # 캔버스 폭(초기에는 0일 수 있으므로 기본값)
        h = 70  # 캔버스 높이
        cell = w // 7  # 요일마다 동일한 폭으로 나누기
        pad = 4  # 셀 내부 여백
        days = ["월", "화", "수", "목", "금", "토", "일"]  # 요일 라벨

        mx = max(bins) or 1  # 최대값(색 강도 스케일용, 0이면 1로 설정)

        def blend(a: str, b: str, t: float) -> str:
            """hex 색상 a→b 사이를 t(0~1)만큼 보간한 색상을 hex 문자열로 반환."""
            ah, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
            bh, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
            ih = int(ah + (bh - ah) * t)
            ig = int(ag + (bg - ag) * t)
            ib = int(ab + (bb - ab) * t)
            return f"#{ih:02x}{ig:02x}{ib:02x}"

        for i, v in enumerate(bins):  # 각 요일에 대해
            x0, x1 = i * cell + pad, (i + 1) * cell - pad  # 셀 가로 범위
            y0, y1 = pad, h - 22  # 세로 범위(아래쪽은 텍스트 용도)

            col = blend("#e8f5e9", "#1b5e20", v / mx)  # 연녹 → 진녹 보간
            c.create_rectangle(x0, y0, x1, y1, fill=col, outline="#cfd8dc")

            # 상세 데이터가 있으면 상태별 개수 표시
            open_n = len(detail[i]["open"]) if detail else 0
            doing_n = len(detail[i]["doing"]) if detail else 0
            done_n = len(detail[i]["done"]) if detail else 0

            c.create_text(
                (x0 + x1) // 2,
                (y0 + y1) // 2 - 6,
                text=f"{open_n}/{doing_n}/{done_n}",
                font=("Helvetica", 9, "bold"),
            )
            c.create_text(
                (x0 + x1) // 2,
                y1 + 8,
                text=days[i],
                font=("Helvetica", 9),
            )

            self._heat_cells.append((i, (x0, y0, x1, y1)))  # 클릭용 bbox 저장

        # 전체 박스 테두리
        c.create_rectangle(pad, pad, w - pad, h - pad - 12, outline="#b0bec5")

    # -----------------------------
    # 히트맵 클릭/더블클릭 처리
    # -----------------------------
    def _hit_test_heat(self, event) -> int | None:
        """클릭 좌표가 어느 요일 셀에 속하는지 인덱스를 반환한다."""
        x, y = event.x, event.y  # 클릭 좌표
        for idx, (x0, y0, x1, y1) in self._heat_cells:  # 각 셀의 bbox 를 순회
            if x0 <= x <= x1 and y0 <= y <= y1:  # 클릭 좌표가 사각형 안이면
                return idx  # 해당 요일 인덱스 반환
        return None  # 어떤 셀에도 속하지 않으면 None

    def _on_heat_click(self, event) -> None:
        """히트맵 단일 클릭 시 해당 칸만 파란색 박스로 하이라이트한다."""
        idx = self._hit_test_heat(event)  # 클릭된 요일 인덱스 계산
        if idx is None:  # 빈 영역 클릭이면
            return  # 아무 것도 하지 않음
        c = self.cnv_heat
        c.delete("hl")  # 이전 하이라이트 제거
        x0, y0, x1, y1 = self._heat_cells[idx][1]  # 해당 셀의 bbox
        c.create_rectangle(
            x0 - 2,
            y0 - 2,
            x1 + 2,
            y1 + 2,
            outline="#1e88e5",
            width=2,
            tags="hl",
        )

    def _on_heat_dblclick(self, event) -> None:
        """히트맵 더블클릭 시 해당 요일의 Todo 목록 상세 팝업을 띄운다."""
        idx = self._hit_test_heat(event)  # 요일 인덱스
        if idx is None or not self._week_detail_cache:
            return  # 유효한 셀/데이터가 없으면 종료

        detail = self._week_detail_cache[idx]  # 해당 요일 상세 구조

        pop = tk.Toplevel(self.winfo_toplevel())  # 팝업 창 생성
        pop.title(f"요일 상세 - {['월','화','수','목','금','토','일'][idx]}")  # 제목 설정
        pop.resizable(False, False)  # 크기 고정

        frm = ttk.Frame(pop)  # 내용 프레임
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(
            frm,
            text=(
                f"미완 {len(detail['open'])} · "
                f"진행 {len(detail['doing'])} · "
                f"완료 {len(detail['done'])}"
            ),
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        box = tk.Listbox(frm, height=10, width=56)  # Todo 목록 표시용 리스트박스
        box.pack(fill="both", expand=True)

        # 상태 순서대로 Todo 들을 한 줄 문자열로 채운다.
        for t in detail["open"] + detail["doing"] + detail["done"]:
            box.insert(
                "end",
                f"{STATUS_ICON.get(t.status)} {t.start}~{t.end} | {t.title}",
            )

        foot = ttk.Frame(frm)  # 하단 버튼 행
        foot.pack(fill="x", pady=(8, 0))

        ttk.Button(foot, text="닫기", command=pop.destroy).pack(side="right")

        # 선택된 항목을 메인 Todo 탭에서 편집하도록 요청하는 버튼
        ttk.Button(
            foot,
            text="선택 편집",
            command=lambda: self._open_from_heat_selection(box, pop),
        ).pack(side="right", padx=(0, 6))

        center_over(self.winfo_toplevel(), pop)  # 부모창 기준 중앙 배치

    def _open_from_heat_selection(self, listbox: tk.Listbox, pop: tk.Toplevel) -> None:
        """요일 상세 팝업에서 선택한 Todo 의 제목을 기준으로 외부에 편집 요청을 보낸다."""
        sel = listbox.curselection()  # 선택된 인덱스
        if not sel or not self.on_request_edit:  # 선택이 없거나 콜백이 없으면
            return  # 아무 것도 하지 않음
        text = listbox.get(sel[0])  # 선택된 한 줄 텍스트
        # "아이콘 기간 | 제목" 구조이므로 '|' 이후의 제목만 추출
        title = text.split("|", 1)[-1].strip() if "|" in text else text.strip()
        pop.destroy()  # 상세 팝업 닫기
        self.on_request_edit(title)  # 메인 앱 콜백에 제목 전달

    # -----------------------------
    # 컨페티 애니메이션
    # -----------------------------
    def _burst_confetti(self, n: int = 28, duration: int = 800) -> None:
        """도넛 캔버스 위에서 n 개의 컨페티를 duration(ms) 동안 떨어뜨린다."""
        c = self.cnv_ring  # 도넛 캔버스

        import time as _t  # 경과 시간 측정을 위해 로컬 임포트

        W = c.winfo_width() or 160  # 폭(초기에는 0 일 수 있으므로 기본 160)
        parts = []  # 생성된 파편 ID 목록
        pal = ["#43a047", "#1e88e5", "#fdd835", "#e53935", "#8e24aa"]  # 색상 팔레트

        for _ in range(n):  # n 개의 파편 생성
            x = random.randint(0, max(8, W - 8))  # 시작 X 좌표
            y = -random.randint(0, 40)  # 캔버스 위쪽 밖에서 시작
            s = random.randint(4, 8)  # 원 지름
            col = random.choice(pal)  # 랜덤 색상
            parts.append(
                c.create_oval(x, y, x + s, y + s, fill=col, width=0)
            )  # 원형 파편 그리기

        t0 = _t.monotonic()  # 시작 시각

        def tick() -> None:
            """각 프레임마다 파편을 아래로 이동시키고 duration 후에는 삭제."""
            dt = (_t.monotonic() - t0) * 1000.0  # 경과 시간(ms)
            for p in parts:
                c.move(p, 0, 6)  # 파편을 아래로 6픽셀 이동
            if dt < duration:
                c.after(16, tick)  # 약 60fps 로 다음 프레임 예약
            else:
                for p in parts:
                    c.delete(p)  # duration 이 지나면 파편 삭제

        tick()  # 애니메이션 시작

    # -----------------------------
    # 외부(AI 등)에서 통계 참조
    # -----------------------------
    def get_last_stats(self) -> dict | None:
        """마지막으로 계산된 통계를 그대로 반환(AI 컨텍스트용)."""
        return self._last_stats

    # -----------------------------
    # 메인 앱 종료 시 호출
    # -----------------------------
    def on_close(self) -> None:
        """메인 윈도우 종료 시 리포트 자동 갱신 루프를 정리한다."""
        self._stop_report_loop()  # after 예약 취소
