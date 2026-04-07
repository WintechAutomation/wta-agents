"""
MES 헬스 체크 스크립트 (Phase 2 자율점검)
- MES 백엔드 로그인 확인
- mes-wta.com 외부 접근 확인
결과를 stdout으로 출력 (비밀번호 노출 없음)
"""
import json
import urllib.request
import urllib.error
import sys


ENV_FILE = r"C:\MES\backend\.env"
BACKEND_URL = "http://localhost:8100"
EXTERNAL_URL = "https://mes-wta.com/"
TIMEOUT = 8


def load_env():
    env = {}
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def check_backend(env):
    payload = json.dumps({
        "username": env.get("MES_SERVICE_USERNAME", ""),
        "password": env.get("MES_SERVICE_PASSWORD", "")
    }).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read())
            if "access" in data.get("data", {}):
                return "OK", "로그인 성공, 토큰 발급"
            return "WARN", f"응답 이상: {list(data.keys())}"
    except urllib.error.HTTPError as e:
        return "FAIL", f"HTTP {e.code}"
    except Exception as e:
        return "FAIL", str(e)


def check_external():
    req = urllib.request.Request(EXTERNAL_URL, method="GET")
    req.add_header("User-Agent", "MES-HealthCheck/1.0")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return "OK", f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return "FAIL", f"HTTP {e.code}"
    except Exception as e:
        return "FAIL", str(e)


def main():
    env = load_env()
    results = {}

    status, msg = check_backend(env)
    results["backend"] = {"status": status, "msg": msg}

    status, msg = check_external()
    results["external"] = {"status": status, "msg": msg}

    # 출력 (이모지 없이 ASCII 호환)
    all_ok = all(v["status"] == "OK" for v in results.values())
    print("=== MES Health Check ===")
    for key, val in results.items():
        icon = "[OK]" if val["status"] == "OK" else "[FAIL]"
        print(f"{icon} {key}: {val['msg']}")

    if all_ok:
        print("\n[ALL OK]")
        sys.exit(0)
    else:
        failed = [k for k, v in results.items() if v["status"] != "OK"]
        print(f"\n[ALERT] {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
