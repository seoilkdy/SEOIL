# core.py  --------------------------------------------------
# 앱 전반에서 공통으로 쓰는 상수, 유틸 함수, DB, Todo 데이터 모델을 모아둔 파일이다.

from __future__ import annotations  # 향후 참조(type hint)에서 문자열 사용 허용

from dataclasses import dataclass  # dataclass 데코레이터로 보일러플레이트 제거
from datetime import date, datetime, timedelta  # 날짜/시간 관련 타입
from pathlib import Path  # __file__ 기준으로 DB 경로 계산에 사용
import sqlite3 as sql  # 내장 SQLite DB 사용
from urllib import request as urlrequest, error as urlerror  # HTTP 요청/에러 처리
import json  # JSON 직렬화/역직렬화(HTTP POST 시 사용)
import os  # 환경변수에서 API 키를 읽을 때 사용
import tkinter as tk  # center_over 유틸에서 타입/위치 계산에 사용


# ─────────────────────────────────────────────
# 공통 상수 (날짜 포맷 / 상태 아이콘 / 여백)
# ─────────────────────────────────────────────

DATE_FMT = "%Y-%m-%d"  # 날짜 문자열 통일 포맷(예: "2025-11-18")

STATUS_ICON = {  # 할 일 상태코드 → UI에서 보여줄 아이콘 매핑
    0: "☐",     # 0 = 미완료
    1: "⏳",     # 1 = 진행중
    2: "✔",     # 2 = 완료
}

STATUS_TEXT = {  # 할 일 상태코드 → 한국어 설명 텍스트
    0: "미완료",
    1: "진행중",
    2: "완료",
}

PAD6 = {"padx": 10, "pady": 6}  # grid/pack 에서 자주 쓰는 기본 여백(조금 좁게)
PAD8 = {"padx": 10, "pady": 8}  # grid/pack 에서 자주 쓰는 기본 여백(조금 넓게)


# ─────────────────────────────────────────────
# DB 경로 설정 (스크립트 폴더 / 인터프리터 환경 대응)
# ─────────────────────────────────────────────

try:  # __file__ 이 존재하는 일반 스크립트 실행 환경인 경우
    DB_PATH = str(Path(__file__).with_name("todo.db"))  # 현재 파일과 같은 폴더에 todo.db 사용
except NameError:  # 예: 인터프리터/노트북 환경 등에서 __file__ 이 없는 경우
    DB_PATH = "todo.db"  # 현재 작업 디렉토리에 todo.db 생성/사용


# ─────────────────────────────────────────────
# 공통 유틸: 날짜 파싱 / 창 중앙 배치 / HTTP GET/POST
# ─────────────────────────────────────────────

def parse_date(s: str) -> datetime:
    """YYYY-MM-DD 형식 문자열을 datetime 객체로 변환하는 헬퍼 함수."""
    return datetime.strptime(s, DATE_FMT)  # 형식이 다르면 ValueError 가 발생한다.


def center_over(parent: tk.Tk, win: tk.Toplevel) -> None:
    """자식 창(win)을 부모 창(parent) 기준으로 화면 중앙 근처에 배치한다."""
    parent.update_idletasks()  # 부모의 위치/크기 정보를 최신 상태로 계산
    win.update_idletasks()  # 자식 창 내부 위젯 레이아웃까지 모두 계산

    px, py = parent.winfo_rootx(), parent.winfo_rooty()  # 부모창 좌상단 화면 좌표
    pw, ph = parent.winfo_width(), parent.winfo_height()  # 부모창 폭/높이
    ww, wh = win.winfo_width(), win.winfo_height()  # 자식창 폭/높이

    # 화면 경계를 넘어가지 않도록 X 좌표를 클램프
    x = max(0, min(px + (pw - ww) // 2, win.winfo_screenwidth() - ww))
    # 화면 경계를 넘어가지 않도록 Y 좌표를 클램프
    y = max(0, min(py + (ph - wh) // 2, win.winfo_screenheight() - wh))

    win.geometry(f"+{x}+{y}")  # 크기는 유지하고 위치만 지정


def _http_get(url: str, headers: dict[str, str] | None = None,
              timeout: int = 15) -> tuple[int, str]:
    """
    단순 HTTP GET 유틸.
    - url: 호출할 주소
    - headers: 필요한 경우 추가 헤더(dict)
    - timeout: 타임아웃(초)
    return: (HTTP 상태코드, 응답본문 텍스트) 튜플
    """
    req = urlrequest.Request(url, method="GET", headers=headers or {})  # GET 요청 객체 생성
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # 타임아웃과 함께 요청 전송
            code = getattr(resp, "status", resp.getcode())  # 파이썬 버전에 따라 status 혹은 getcode 사용
            text = resp.read().decode("utf-8", "ignore")  # 응답 본문을 UTF-8 문자열로 디코드
            return code, text  # (상태코드, 본문) 반환
    except urlerror.HTTPError as e:  # 4xx / 5xx 등 HTTP 에러인 경우
        return e.code, e.read().decode("utf-8", "ignore")  # 에러 상태코드와 에러본문 반환
    except Exception as e:  # 네트워크 단절 등 기타 예외
        return 0, f"{e}"  # 0 코드는 로컬 예외/오류를 의미하도록 사용


def _http_post(url: str, headers: dict[str, str] | None = None,
               data: dict | None = None, timeout: int = 30) -> tuple[int, str]:
    """
    단순 HTTP POST(JSON) 유틸.
    - data 는 dict 로 받고, 내부에서 JSON 으로 직렬화해서 전송한다.
    """
    body = json.dumps(data or {}).encode("utf-8")  # dict → JSON 문자열 → UTF-8 바이트
    hdrs = {"Content-Type": "application/json"}  # 기본 Content-Type 헤더
    if headers:  # 추가 헤더가 있으면
        hdrs.update(headers)  # 우선순위를 추가 헤더에 주며 병합

    req = urlrequest.Request(url, data=body, method="POST", headers=hdrs)  # POST 요청 객체 생성
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # 요청 전송 및 응답 수신
            code = getattr(resp, "status", resp.getcode())  # 상태코드 추출
            text = resp.read().decode("utf-8", "ignore")  # 응답본문 문자열로 디코드
            return code, text  # (상태코드, 본문) 반환
    except urlerror.HTTPError as e:  # HTTP 에러 (4xx/5xx)
        return e.code, e.read().decode("utf-8", "ignore")  # 에러 상태코드와 에러본문 반환
    except Exception as e:  # 기타 예외
        return 0, f"{e}"  # 0 코드는 로컬 오류 의미


# ─────────────────────────────────────────────
# SQLite DB 래퍼 (todo.db 에 Todo 목록 저장)
# ─────────────────────────────────────────────

def _db() -> sql.Connection:
    """todo.db 에 대한 SQLite 연결을 열어 반환한다."""
    return sql.connect(DB_PATH)  # 경로 상수 사용


def init_db() -> None:
    """앱 최초 실행 시 todos 테이블이 없으면 생성한다."""
    with _db() as con:  # with 블록으로 자동 커밋/닫기 처리
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS todos(
                id     INTEGER PRIMARY KEY AUTOINCREMENT,  -- 내부 PK
                title  TEXT NOT NULL,                      -- 제목
                start  TEXT NOT NULL,                      -- 시작일 (YYYY-MM-DD)
                end    TEXT NOT NULL,                      -- 종료일 (YYYY-MM-DD)
                memo   TEXT DEFAULT '',                    -- 상세 설명
                status INTEGER NOT NULL CHECK(status IN (0,1,2)) -- 상태코드(0,1,2) 제약
            )
            """
        )  # 존재하지 않는 경우에만 테이블 생성


def load_all() -> list["Todo"]:
    """DB 에 저장된 모든 Todo 항목을 읽어 list[Todo] 로 반환한다."""
    init_db()  # 테이블이 항상 존재하도록 보장
    with _db() as con:  # 연결 컨텍스트
        rows = con.execute(
            "SELECT title, start, end, memo, status FROM todos ORDER BY id"
        ).fetchall()  # id 순으로 모든 행 조회
    # 각 행을 Todo 인스턴스로 변환해서 리스트로 반환
    return [Todo(title, start, end, memo, status) for (title, start, end, memo, status) in rows]


def save_all(items: list["Todo"]) -> None:
    """현재 Todo 리스트 전체를 DB 에 그대로 반영(덮어쓰기)한다."""
    with _db() as con:  # 트랜잭션 컨텍스트
        con.execute("DELETE FROM todos")  # 기존 내용을 모두 삭제
        con.executemany(
            "INSERT INTO todos(title, start, end, memo, status) VALUES(?,?,?,?,?)",
            [(t.title, t.start, t.end, t.desc, t.status) for t in items],  # Todo → 튜플 변환
        )  # executemany 로 일괄 삽입


# ─────────────────────────────────────────────
# Todo 데이터 모델
# ─────────────────────────────────────────────

@dataclass
class Todo:
    """할 일 1건을 표현하는 단순 데이터 클래스."""
    title: str  # 제목
    start: str  # 시작일 (YYYY-MM-DD 문자열)
    end: str    # 종료일 (YYYY-MM-DD 문자열)
    desc: str = ""   # 상세 설명(옵션)
    status: int = 0  # 상태코드(0=미완, 1=진행, 2=완료)

    def cycle(self) -> None:
        """상태를 0→1→2→0 순서로 하나씩 순환시킨다."""
        self.status = (self.status + 1) % 3  # 나머지 연산으로 0~2 순환

    def display(self, today: date | None = None) -> str:
        """
        리스트박스에 표시할 한 줄짜리 문자열 생성.
        - 상태 아이콘
        - D-DAY 표기
        - 기간 및 제목 등을 포함한다.
        """
        icon = STATUS_ICON.get(self.status, "☐")  # 상태코드에 맞는 아이콘 선택
        try:
            d_end = datetime.strptime(self.end, DATE_FMT).date()  # 종료일을 date 로 파싱
        except Exception:
            # 날짜 파싱 실패 시에는 D-DAY 계산 없이 단순 문자열만 반환
            return f"{icon} {self.start} ~ {self.end} | {self.title}"

        today = today or date.today()  # today 인자가 없으면 오늘 날짜 사용
        delta = (d_end - today).days  # 오늘 기준 남은 일수 계산

        if delta < 0:  # 이미 마감이 지난 경우
            tag = "⛔ 지남"
        elif delta == 0:  # 오늘 마감
            tag = "⚠️ D-DAY"
        elif delta <= 3:  # 3일 이내 마감
            tag = f"⏰ D-{delta}"
        else:  # 그 외 일반 D-N
            tag = f"D-{delta}"

        # 최종 표시 문자열 구성 후 반환
        return f"{icon} [{tag}] {self.start} ~ {self.end} | {self.title}"
