"""QA 테스트 계정 생성 스크립트."""
import asyncio
import os
import bcrypt
import asyncpg


async def main():
    db_url = os.environ.get("DATABASE_URL", "")
    # asyncpg는 postgresql+asyncpg:// 스킴 미지원 → postgresql://로 변환
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    # 테이블 컬럼 확인
    cols = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND table_schema = 'csagent' "
        "ORDER BY ordinal_position"
    )
    print("users columns:", [c["column_name"] for c in cols])

    # 기존 qa-test 계정 확인
    existing = await conn.fetchrow(
        "SELECT id, username FROM csagent.users WHERE username = 'qa-test'"
    )
    if existing:
        print(f"Already exists: id={existing['id']}, username={existing['username']}")
        await conn.close()
        return

    # 비밀번호 해싱
    hashed = bcrypt.hashpw(b"qa-test-2026!", bcrypt.gensalt()).decode()

    # 계정 생성
    row = await conn.fetchrow(
        "INSERT INTO csagent.users (username, hashed_password, full_name, role, language, location, is_active, mfa_enabled) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id, username",
        "qa-test", hashed, "QA Tester", "viewer", "ko", "HQ", True, False,
    )
    print(f"Created: id={row['id']}, username={row['username']}")
    await conn.close()


asyncio.run(main())
