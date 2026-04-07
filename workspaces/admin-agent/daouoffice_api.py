"""
daouoffice_api.py — 다우오피스 OpenAPI 유틸리티

인증정보: MES DB system_configs 테이블에서 key='daouoffice' 조회
  (clientId, clientSecret, sender_employee_number)

사용법:
  python daouoffice_api.py users               # 전체 직원 목록
  python daouoffice_api.py departments          # 부서별 구성원
  python daouoffice_api.py user 김철수          # 특정 직원 조회
  python daouoffice_api.py test                 # 연결 테스트
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Optional

# ── 상수 ──────────────────────────────────────────────────────────────────────
ACCOUNT_URL    = "https://api.daouoffice.com/public/v1/account"
DEPT_URL       = "https://api.daouoffice.com/public/v1/dept/member"
NOTI_URL       = "https://api.daouoffice.com/public/v1/noti"
MES_ENV_PATH   = "C:/MES/backend/.env"
TIMEOUT        = 30

ERROR_MESSAGES = {
    "901": "유효하지 않은 client ID",
    "902": "유효하지 않은 client Secret",
    "903": "서비스 이용 제한",
    "904": "서비스 이용 기간 만료",
    "905": "API 호출 한도 초과",
    "920": "발송자(sender) 누락",
    "921": "수신자(receivers) 누락",
    "924": "알림 메시지(message) 누락",
    "925": "잘못된 파라미터 형식",
    "926": "유효하지 않은 사용자 ID",
    "927": "발송 권한 없음",
    "928": "수신자 정보 없음",
    "955": "도메인 코드 오류",
}


# ── DB에서 인증정보 로드 ───────────────────────────────────────────────────────
def _load_db_password() -> Optional[str]:
    """C:/MES/backend/.env에서 DB_PASSWORD 읽기"""
    try:
        with open(MES_ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DB_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return None


def load_credentials() -> dict:
    """
    MES DB의 system_configs 테이블에서 daouoffice 설정 조회.
    반환: {"clientId": str, "clientSecret": str, "sender_employee_number": str}
    """
    password = _load_db_password()
    if not password:
        raise RuntimeError(f"DB 비밀번호 로드 실패: {MES_ENV_PATH} 확인")

    try:
        import psycopg2
    except ImportError:
        raise RuntimeError("psycopg2 미설치: pip install psycopg2-binary")

    conn = psycopg2.connect(
        host="localhost", port=55432,
        user="postgres", password=password,
        dbname="postgres", connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT config_data FROM api_systemconfig"
                " WHERE system_type = 'daouoffice' AND is_active = TRUE LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError(
                    "api_systemconfig에 system_type='daouoffice' 레코드 없음. "
                    "MES 시스템관리 > 설정에서 다우오피스 연동을 먼저 설정하세요."
                )
            config_data = row[0]
            # config_data가 dict(jsonb)로 반환되거나 문자열일 수 있음
            if isinstance(config_data, str):
                config_data = json.loads(config_data)
            if not config_data.get("clientId") or not config_data.get("clientSecret"):
                raise RuntimeError(
                    "daouoffice 설정에 clientId/clientSecret 누락"
                )
            return {
                "clientId": config_data["clientId"],
                "clientSecret": config_data["clientSecret"],
                "sender_employee_number": config_data.get("sender_employee_number", ""),
            }
    finally:
        conn.close()


# ── API 호출 ──────────────────────────────────────────────────────────────────
def _call_api(url: str, body: dict) -> dict:
    """
    다우오피스 API POST 호출.
    응답 code != '200' 시 RuntimeError 발생.
    """
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json; charset=UTF-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"API 호출 실패: {e}")

    result = json.loads(raw)
    code = str(result.get("code", ""))
    if code != "200":
        msg = ERROR_MESSAGES.get(code, result.get("message", "알 수 없는 오류"))
        raise RuntimeError(f"다우오피스 오류 (code={code}): {msg}")
    return result


# ── DaouOfficeClient ──────────────────────────────────────────────────────────
class DaouOfficeClient:
    """다우오피스 OpenAPI 클라이언트"""

    def __init__(self, client_id: str, client_secret: str, sender_employee_number: str = ""):
        self._cid = client_id
        self._csec = client_secret
        self.sender_employee_number = sender_employee_number

    @classmethod
    def from_db(cls) -> "DaouOfficeClient":
        """DB에서 인증정보를 읽어 클라이언트 생성"""
        creds = load_credentials()
        return cls(
            client_id=creds["clientId"],
            client_secret=creds["clientSecret"],
            sender_employee_number=creds["sender_employee_number"],
        )

    def _auth_body(self) -> dict:
        return {"clientId": self._cid, "clientSecret": self._csec}

    # ── 계정 API (전체 직원) ──────────────────────────────────────────────────
    def _fetch_account_raw(self) -> list[dict]:
        result = _call_api(ACCOUNT_URL, self._auth_body())
        data = result.get("data", [])
        if isinstance(data, str):
            data = json.loads(data)
        return data if isinstance(data, list) else []

    # ── 부서원 API ─────────────────────────────────────────────────────────────
    def _fetch_dept_raw(self) -> list[dict]:
        try:
            result = _call_api(DEPT_URL, self._auth_body())
            data = result.get("data", [])
            if isinstance(data, str):
                data = json.loads(data)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _build_dept_map(self) -> dict[str, dict]:
        """loginId → 부서 정보 맵"""
        dept_map: dict[str, dict] = {}
        for item in self._fetch_dept_raw():
            login_id = item.get("loginId", "")
            if login_id:
                dept_map[login_id] = item
        return dept_map

    # ── 공개 메서드 ──────────────────────────────────────────────────────────
    def list_users(self) -> list[dict]:
        """
        전체 활성 직원 목록 반환.
        각 항목: name, employee_number, login_id, email, department, position, duty, phone
        """
        dept_map = self._build_dept_map()
        users = []
        for u in self._fetch_account_raw():
            ko_name = u.get("koName", "")
            if not ko_name:
                continue
            # 비활성 제외 (Status가 있을 때만 필터)
            status = u.get("status", "")
            if status and status != "ONLINE":
                continue

            login_id = u.get("loginId", "")
            email = u.get("email", "") or (f"{login_id}@wta.kr" if login_id else "")
            dept = dept_map.get(login_id, {})

            department = dept.get("orgName", "") or "미지정"
            position = u.get("positionName", "") or "미지정"
            duty = dept.get("dutyName", "")
            phone = u.get("mobileNo", "") or u.get("directTel", "")
            emp_num = u.get("employeeNumber", "") or login_id

            users.append({
                "name": ko_name,
                "employee_number": emp_num,
                "login_id": login_id,
                "email": email,
                "department": department,
                "department_code": dept.get("orgCode", ""),
                "position": position,
                "duty": duty,
                "member_type": dept.get("memberType", ""),
                "phone": phone,
                "join_date": u.get("joinDate", ""),
                "status": "active",
            })

        return users

    def list_departments(self) -> dict[str, list[dict]]:
        """
        부서별 구성원 반환.
        반환: {부서명: [직원목록]}
        """
        from collections import defaultdict
        result: dict[str, list] = defaultdict(list)
        for user in self.list_users():
            result[user["department"]].append(user)
        return dict(result)

    def get_user(self, name_or_id: str) -> Optional[dict]:
        """
        이름 또는 loginId/사번으로 직원 조회.
        일치하는 첫 번째 직원 반환, 없으면 None.
        """
        query = name_or_id.strip().lower()
        for user in self.list_users():
            if (user["name"] == name_or_id
                    or user["login_id"].lower() == query
                    or user["employee_number"].lower() == query
                    or user["email"].lower() == query):
                return user
        return None

    def test_connection(self) -> str:
        """연결 테스트 — 성공 시 직원 수 반환, 실패 시 예외"""
        users = self.list_users()
        return f"연결 성공: {len(users)}명 조회됨"


# ── CLI ───────────────────────────────────────────────────────────────────────
def _print_user(u: dict) -> None:
    print(f"  이름: {u['name']}  |  사번: {u['employee_number']}  |  부서: {u['department']}")
    print(f"  직위: {u['position']}  |  직책: {u['duty'] or '-'}  |  이메일: {u['email']}")
    print(f"  전화: {u['phone'] or '-'}  |  loginId: {u['login_id']}")


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if not argv:
        print(__doc__)
        return

    cmd = argv[0].lower()
    client = DaouOfficeClient.from_db()

    if cmd == "test":
        print(client.test_connection())

    elif cmd == "users":
        users = client.list_users()
        print(f"전체 직원 {len(users)}명\n")
        for u in users:
            _print_user(u)
            print()

    elif cmd == "departments":
        depts = client.list_departments()
        print(f"부서 {len(depts)}개\n")
        for dept_name, members in sorted(depts.items()):
            print(f"[{dept_name}] {len(members)}명")
            for u in members:
                print(f"  - {u['name']} ({u['position']})")
            print()

    elif cmd == "user":
        if len(argv) < 2:
            print("사용법: python daouoffice_api.py user <이름|loginId|사번>")
            return
        user = client.get_user(argv[1])
        if user:
            print(f"직원 정보: {argv[1]}\n")
            _print_user(user)
        else:
            print(f"직원 '{argv[1]}' 을 찾을 수 없습니다.")

    else:
        print(f"알 수 없는 명령: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
