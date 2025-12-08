# core.py  --------------------------------------------------
# 앱 전반에서 공통으로 사용하는 상수, 유틸리티 함수, 데이터베이스 연결,
# 그리고 Todo 데이터 모델을 정의하는 핵심 모듈입니다.

from __future__ import annotations  # 파이썬 3.7+에서 타입 힌트를 문자열처럼 처리하여 순환 참조 문제를 방지합니다.

from dataclasses import dataclass  # 클래스 정의 시 __init__, __repr__ 등을 자동으로 생성해주는 데코레이터입니다.
from datetime import date, datetime, timedelta  # 날짜 및 시간 계산을 위한 표준 라이브러리입니다.
from pathlib import Path  # 파일 경로를 객체 지향적으로 다루기 위한 라이브러리입니다.
import sqlite3 as sql  # 경량 로컬 데이터베이스인 SQLite를 사용하기 위한 모듈입니다.
from urllib import request as urlrequest, error as urlerror  # HTTP 요청 및 에러 처리를 위한 모듈입니다.
import json  # 데이터를 JSON 형식으로 직렬화하거나 역직렬화하기 위해 사용합니다.
import os  # 운영체제 환경 변수 접근 등을 위해 사용합니다.
import tkinter as tk  # GUI 윈도우 위치 계산 등을 위해 Tkinter 타입을 가져옵니다.


# ─────────────────────────────────────────────
# 1. 공통 상수 정의 (날짜 포맷, 상태 아이콘, UI 여백)
# ─────────────────────────────────────────────

DATE_FMT = "%Y-%m-%d"  # 날짜를 문자열로 변환하거나 파싱할 때 사용할 통일된 형식입니다 (예: "2025-11-18").

STATUS_ICON = {  # 할 일(Todo)의 상태 코드(정수)를 UI에 표시할 아이콘 문자열로 매핑합니다.
    0: "☐",     # 상태 0: 미완료 (빈 체크박스)
    1: "⏳",     # 상태 1: 진행 중 (모래시계)
    2: "✔",     # 상태 2: 완료 (체크 표시)
}

STATUS_TEXT = {  # 할 일의 상태 코드를 사용자에게 보여줄 한국어 텍스트로 매핑합니다.
    0: "미완료",  # 상태 0에 대한 설명
    1: "진행중",  # 상태 1에 대한 설명
    2: "완료",    # 상태 2에 대한 설명
}

PAD6 = {"padx": 10, "pady": 6}  # 위젯 배치 시 사용할 기본 여백 설정입니다 (가로 10, 세로 6).
PAD8 = {"padx": 10, "pady": 8}  # 위젯 배치 시 사용할 조금 더 넓은 여백 설정입니다 (가로 10, 세로 8).


# ─────────────────────────────────────────────
# 2. 데이터베이스 경로 설정
# ─────────────────────────────────────────────

try:
    # 현재 실행 중인 스크립트 파일(__file__)의 경로를 기준으로 DB 파일 경로를 설정합니다.
    DB_PATH = str(Path(__file__).with_name("todo.db"))  # 현재 파일과 같은 폴더에 'todo.db'라는 이름으로 저장합니다.
except NameError:
    # Jupyter Notebook이나 대화형 인터프리터 등 __file__ 변수가 없는 환경을 위한 예외 처리입니다.
    DB_PATH = "todo.db"  # 현재 작업 디렉토리에 'todo.db'를 생성하거나 사용합니다.


# ─────────────────────────────────────────────
# 3. 공통 유틸리티 함수 (날짜 파싱, 윈도우 중앙 배치, HTTP 요청)
# ─────────────────────────────────────────────

def parse_date(s: str) -> datetime:
    """
    문자열을 받아 datetime 객체로 변환하는 헬퍼 함수입니다.
    입력 문자열은 반드시 'YYYY-MM-DD' 형식이어야 합니다.
    """
    return datetime.strptime(s, DATE_FMT)  # 지정된 포맷(DATE_FMT)에 맞지 않으면 ValueError가 발생합니다.


def center_over(parent: tk.Tk, win: tk.Toplevel) -> None:
    """
    자식 윈도우(win)를 부모 윈도우(parent)의 정중앙에 배치하는 함수입니다.
    """
    parent.update_idletasks()  # 부모 윈도우의 최신 크기와 위치 정보를 얻기 위해 대기 중인 이벤트를 처리합니다.
    win.update_idletasks()  # 자식 윈도우의 크기가 결정되도록 내부 위젯들의 레이아웃을 계산합니다.

    px, py = parent.winfo_rootx(), parent.winfo_rooty()  # 부모 윈도우의 화면상 좌상단 X, Y 좌표를 가져옵니다.
    pw, ph = parent.winfo_width(), parent.winfo_height()  # 부모 윈도우의 너비와 높이를 가져옵니다.
    ww, wh = win.winfo_width(), win.winfo_height()  # 자식 윈도우의 너비와 높이를 가져옵니다.

    # 자식 윈도우가 화면 밖으로 나가지 않도록 X 좌표를 계산하고 제한(clamp)합니다.
    x = max(0, min(px + (pw - ww) // 2, win.winfo_screenwidth() - ww))
    # 자식 윈도우가 화면 밖으로 나가지 않도록 Y 좌표를 계산하고 제한(clamp)합니다.
    y = max(0, min(py + (ph - wh) // 2, win.winfo_screenheight() - wh))

    win.geometry(f"+{x}+{y}")  # 계산된 위치로 자식 윈도우를 이동시킵니다 (크기는 변경하지 않음).


def _http_get(url: str, headers: dict[str, str] | None = None,
              timeout: int = 15) -> tuple[int, str]:
    """
    간단한 HTTP GET 요청을 보내는 유틸리티 함수입니다.
    외부 라이브러리(requests 등) 없이 표준 라이브러리만 사용합니다.
    
    Args:
        url: 요청을 보낼 URL 주소
        headers: 요청 헤더 (딕셔너리 형태, 옵션)
        timeout: 요청 타임아웃 시간 (초 단위, 기본 15초)
        
    Returns:
        (상태코드, 응답본문) 튜플을 반환합니다.
    """
    req = urlrequest.Request(url, method="GET", headers=headers or {})  # GET 요청 객체를 생성합니다.
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # 타임아웃을 설정하여 요청을 보냅니다.
            code = getattr(resp, "status", resp.getcode())  # 응답 객체에서 상태 코드를 가져옵니다.
            text = resp.read().decode("utf-8", "ignore")  # 응답 본문을 읽고 UTF-8로 디코딩합니다 (에러 무시).
            return code, text  # 상태 코드와 본문 텍스트를 반환합니다.
    except urlerror.HTTPError as e:  # 404, 500 등 HTTP 에러가 발생한 경우입니다.
        return e.code, e.read().decode("utf-8", "ignore")  # 에러 코드와 에러 메시지를 반환합니다.
    except Exception as e:  # 네트워크 연결 실패 등 기타 예외가 발생한 경우입니다.
        return 0, f"{e}"  # 상태 코드를 0으로 설정하여 로컬 오류임을 알리고, 예외 메시지를 반환합니다.


def center_window(window: tk.Toplevel | tk.Tk, width: int, height: int) -> None:
    """
    Tkinter 윈도우를 화면 중앙에 배치하는 유틸리티 함수입니다.
    
    Args:
        window: 중앙 배치할 윈도우 객체
        width: 윈도우 너비 (픽셀)
        height: 윈도우 높이 (픽셀)
    """
    # 윈도우 크기 업데이트를 강제합니다
    window.update_idletasks()
    
    # 화면 크기 가져오기
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # 중앙 위치 계산
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    
    # 윈도우 위치 설정
    window.geometry(f"{width}x{height}+{x}+{y}")


def _http_post(url: str, headers: dict[str, str] | None = None,
               data: dict | None = None, timeout: int = 30) -> tuple[int, str]:
    """
    간단한 HTTP POST 요청을 보내는 유틸리티 함수입니다.
    데이터는 딕셔너리로 받아 JSON으로 변환하여 전송합니다.
    
    Args:
        url: 요청을 보낼 URL 주소
        headers: 추가 요청 헤더 (옵션)
        data: 전송할 데이터 (딕셔너리 형태)
        timeout: 타임아웃 시간 (초 단위, 기본 30초)
    """
    body = json.dumps(data or {}).encode("utf-8")  # 딕셔너리 데이터를 JSON 문자열로 변환 후 UTF-8 바이트로 인코딩합니다.
    hdrs = {"Content-Type": "application/json"}  # 기본 헤더로 Content-Type을 JSON으로 설정합니다.
    if headers:  # 사용자가 제공한 추가 헤더가 있다면
        hdrs.update(headers)  # 기본 헤더에 병합합니다 (사용자 헤더가 우선).

    req = urlrequest.Request(url, data=body, method="POST", headers=hdrs)  # POST 요청 객체를 생성합니다.
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # 요청을 전송하고 응답을 기다립니다.
            code = getattr(resp, "status", resp.getcode())  # 상태 코드를 확인합니다.
            text = resp.read().decode("utf-8", "ignore")  # 응답 본문을 디코딩합니다.
            return code, text  # 결과 반환
    except urlerror.HTTPError as e:  # HTTP 에러 발생 시
        return e.code, e.read().decode("utf-8", "ignore")  # 에러 코드와 내용을 반환합니다.
    except Exception as e:  # 기타 예외 발생 시
        return 0, f"{e}"  # 로컬 오류(0)와 예외 메시지를 반환합니다.


# ─────────────────────────────────────────────
# 3-1. 스마트폰 푸시 알림 (ntfy.sh) 관련 함수
# ─────────────────────────────────────────────

# 설정 파일 경로 (todo.db와 같은 폴더에 저장)
try:
    SETTINGS_PATH = str(Path(__file__).with_name("settings.json"))
except NameError:
    SETTINGS_PATH = "settings.json"

# 기본 알림 시간 (오전 9시)
DEFAULT_NOTIFICATION_HOUR = 9


def load_notification_settings() -> dict:
    """
    알림 설정을 파일에서 불러옵니다.
    파일이 없거나 오류 시 기본값을 반환합니다.
    """
    default = {
        "ntfy_topic": "",           # ntfy 토픽 이름 (비어있으면 비활성화)
        "notifications_enabled": True,  # 알림 활성화 여부
        "notification_hour": DEFAULT_NOTIFICATION_HOUR,  # 알림 시간 (시)
        "sent_notifications": [],   # 이미 전송된 알림 기록 (중복 방지)
    }
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            # 기본값과 병합 (새로운 설정 항목이 추가되어도 호환되도록)
            for key in default:
                if key not in loaded:
                    loaded[key] = default[key]
            return loaded
    except Exception:
        return default


def save_notification_settings(settings: dict) -> None:
    """
    알림 설정을 파일에 저장합니다.
    """
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[알림 설정 저장 오류] {e}")


def send_ntfy_notification(
    topic: str,
    title: str,
    message: str,
    scheduled_at: datetime | None = None,
    priority: str = "default"
) -> tuple[bool, str]:
    """
    ntfy.sh를 통해 스마트폰에 푸시 알림을 보냅니다.
    
    Args:
        topic: ntfy 토픽 이름 (스마트폰 앱에서 구독한 이름)
        title: 알림 제목
        message: 알림 내용
        scheduled_at: 예약 시간 (None이면 즉시 전송)
        priority: 알림 우선순위 ("min", "low", "default", "high", "urgent")
    
    Returns:
        (성공 여부, 메시지) 튜플
    """
    if not topic:
        return False, "토픽이 설정되지 않았습니다."
    
    url = f"https://ntfy.sh/{topic}"
    
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": "bell",  # 알림 아이콘에 벨 이모지 추가
    }
    
    # 예약 알림인 경우 At 헤더 추가
    if scheduled_at:
        # ntfy는 최대 3일(72시간) 후까지만 예약 가능
        max_scheduled = datetime.now() + timedelta(hours=72)
        if scheduled_at > max_scheduled:
            return False, "예약은 최대 72시간(3일) 후까지만 가능합니다."
        
        timestamp = int(scheduled_at.timestamp())
        headers["At"] = str(timestamp)
    
    # ntfy는 body를 raw text로 전송
    body = message.encode("utf-8")
    
    req = urlrequest.Request(url, data=body, method="POST")
    for key, value in headers.items():
        # urllib/http.client는 헤더를 latin-1로 인코딩하므로,
        # UTF-8 문자열을 바이트로 변환 후 latin-1로 디코딩하여 우회합니다.
        safe_value = str(value).encode("utf-8").decode("latin-1")
        req.add_header(key, safe_value)
    
    try:
        with urlrequest.urlopen(req, timeout=15) as resp:
            code = getattr(resp, "status", resp.getcode())
            if code == 200:
                if scheduled_at:
                    return True, f"예약됨: {scheduled_at.strftime('%Y-%m-%d %H:%M')}"
                return True, "알림 전송 성공"
            return False, f"응답 코드: {code}"
    except urlerror.HTTPError as e:
        return False, f"HTTP 오류 {e.code}: {e.read().decode('utf-8', 'ignore')}"
    except Exception as e:
        return False, f"전송 오류: {e}"


def get_notification_key(todo_title: str, notify_date: date, notify_type: str) -> str:
    """
    중복 알림 방지를 위한 고유 키를 생성합니다.
    
    Args:
        todo_title: 할일 제목
        notify_date: 알림 날짜
        notify_type: 알림 종류 ("D-3", "D-1", "D-day")
    
    Returns:
        고유 키 문자열 (예: "과제_2025-12-12_D-1")
    """
    return f"{todo_title}_{notify_date.strftime(DATE_FMT)}_{notify_type}"


def mark_notification_sent(notification_key: str) -> None:
    """
    알림을 전송 완료로 표시합니다 (중복 방지용).
    """
    settings = load_notification_settings()
    if notification_key not in settings["sent_notifications"]:
        settings["sent_notifications"].append(notification_key)
        # 오래된 알림 기록 정리 (최근 100개만 유지)
        if len(settings["sent_notifications"]) > 100:
            settings["sent_notifications"] = settings["sent_notifications"][-100:]
        save_notification_settings(settings)


def is_notification_sent(notification_key: str) -> bool:
    """
    이미 전송된 알림인지 확인합니다.
    """
    settings = load_notification_settings()
    return notification_key in settings["sent_notifications"]


# ─────────────────────────────────────────────
# 4. SQLite 데이터베이스 관리 (Todo 저장소)
# ─────────────────────────────────────────────

def _db() -> sql.Connection:
    """
    SQLite 데이터베이스 파일에 대한 연결 객체를 생성하여 반환합니다.
    """
    return sql.connect(DB_PATH)  # 위에서 설정한 DB_PATH 경로의 파일을 엽니다.


def init_db() -> None:
    """
    애플리케이션 시작 시 호출되어, 필요한 테이블이 없으면 생성합니다.
    """
    with _db() as con:  # DB 연결을 엽니다 (with 문을 사용하여 자동으로 커밋 및 종료).
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS todos(
                id     INTEGER PRIMARY KEY AUTOINCREMENT,  -- 각 할 일의 고유 ID (자동 증가)
                title  TEXT NOT NULL,                      -- 할 일 제목 (필수)
                start  TEXT NOT NULL,                      -- 시작일 (YYYY-MM-DD 문자열)
                end    TEXT NOT NULL,                      -- 종료일 (YYYY-MM-DD 문자열)
                memo   TEXT DEFAULT '',                    -- 상세 설명 (기본값 빈 문자열)
                status INTEGER NOT NULL CHECK(status IN (0,1,2)) -- 상태 코드 (0, 1, 2 중 하나만 허용)
            )
            """
        )  # SQL 쿼리를 실행하여 테이블을 생성합니다.


def load_all() -> list["Todo"]:
    """
    데이터베이스에 저장된 모든 할 일(Todo)을 불러와 객체 리스트로 반환합니다.
    """
    init_db()  # 테이블이 존재하는지 먼저 확인하고 없으면 생성합니다.
    with _db() as con:  # DB 연결을 엽니다.
        rows = con.execute(
            "SELECT title, start, end, memo, status FROM todos ORDER BY id"
        ).fetchall()  # ID 순서대로 모든 데이터를 조회합니다.
    
    # 조회된 각 행(row)을 Todo 객체로 변환하여 리스트에 담아 반환합니다.
    return [Todo(title, start, end, memo, status) for (title, start, end, memo, status) in rows]


def save_all(items: list["Todo"]) -> None:
    """
    현재 메모리에 있는 Todo 리스트 전체를 데이터베이스에 덮어씁니다.
    (기존 데이터를 모두 지우고 새로 쓰는 방식입니다.)
    """
    with _db() as con:  # DB 연결을 엽니다.
        con.execute("DELETE FROM todos")  # 기존의 모든 할 일 데이터를 삭제합니다.
        con.executemany(
            "INSERT INTO todos(title, start, end, memo, status) VALUES(?,?,?,?,?)",
            [(t.title, t.start, t.end, t.desc, t.status) for t in items],  # 각 Todo 객체를 튜플로 변환합니다.
        )  # 변환된 데이터들을 일괄 삽입(Bulk Insert)합니다.


# ─────────────────────────────────────────────
# 5. Todo 데이터 모델 클래스
# ─────────────────────────────────────────────

@dataclass
class Todo:
    """
    할 일 하나를 표현하는 데이터 클래스입니다.
    데이터베이스의 행(row)과 1:1로 매핑됩니다.
    """
    title: str  # 할 일의 제목
    start: str  # 시작 날짜 (문자열)
    end: str    # 종료 날짜 (문자열)
    desc: str = ""   # 상세 설명 (기본값 없음)
    status: int = 0  # 진행 상태 (0:미완료, 1:진행중, 2:완료)

    def cycle(self) -> None:
        """
        할 일의 상태를 순환시킵니다.
        (미완료 -> 진행중 -> 완료 -> 미완료 순서)
        """
        self.status = (self.status + 1) % 3  # 0, 1, 2 사이를 순환하도록 나머지 연산을 사용합니다.

    def display(self, today: date | None = None) -> str:
        """
        UI 리스트에 표시하기 위한 포맷팅된 문자열을 생성합니다.
        아이콘, D-Day, 날짜, 제목을 포함합니다.
        """
        icon = STATUS_ICON.get(self.status, "☐")  # 현재 상태에 해당하는 아이콘을 가져옵니다.
        try:
            d_end = datetime.strptime(self.end, DATE_FMT).date()  # 종료일 문자열을 날짜 객체로 변환합니다.
        except Exception:
            # 날짜 형식이 잘못된 경우 D-Day 계산을 생략하고 기본 정보만 반환합니다.
            return f"{icon} {self.start} ~ {self.end} | {self.title}"

        today = today or date.today()  # 기준 날짜가 주어지지 않으면 오늘 날짜를 사용합니다.
        delta = (d_end - today).days  # 종료일까지 남은 일수를 계산합니다.

        # 남은 일수에 따라 D-Day 태그를 다르게 설정합니다.
        if delta < 0:  # 마감일이 지난 경우
            tag = "⛔ 지남"
        elif delta == 0:  # 오늘이 마감일인 경우
            tag = "⚠️ D-DAY"
        elif delta <= 3:  # 마감 임박 (3일 이내)
            tag = f"⏰ D-{delta}"
        else:  # 여유가 있는 경우
            tag = f"D-{delta}"

        # 최종적으로 구성된 문자열을 반환합니다.
        return f"{icon} [{tag}] {self.start} ~ {self.end} | {self.title}"
