"""
wELEC 프로젝트 전용 DB 생성 스크립트
- PostgreSQL localhost:55432
- 새 데이터베이스: welec
- PLAN.md 4. DB 스키마 개요 기반
"""
import sys, io, psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env = {}
with open('C:/MES/backend/.env', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

PG_PASSWORD = env.get('DB_PASSWORD', '')

# ── 1. postgres DB에 연결 → welec DB 생성 ──
print("1단계: welec 데이터베이스 생성...")
conn0 = psycopg2.connect(
    host='localhost', port=55432,
    dbname='postgres', user='postgres',
    password=PG_PASSWORD
)
conn0.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur0 = conn0.cursor()

# 이미 존재하는지 확인
cur0.execute("SELECT 1 FROM pg_database WHERE datname = 'welec'")
if cur0.fetchone():
    print("  welec DB 이미 존재 — 스킵")
else:
    cur0.execute(sql.SQL("CREATE DATABASE welec ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0"))
    print("  welec DB 생성 완료")

cur0.close()
conn0.close()

# ── 2. welec DB에 연결 → 테이블 생성 ──
print("2단계: welec DB 테이블 생성...")
conn = psycopg2.connect(
    host='localhost', port=55432,
    dbname='welec', user='postgres',
    password=PG_PASSWORD
)
cur = conn.cursor()

SCHEMA_SQL = """
-- projects: 전장설계 프로젝트
CREATE TABLE IF NOT EXISTS projects (
    id          BIGSERIAL PRIMARY KEY,
    code        VARCHAR(50) UNIQUE NOT NULL,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    created_by  VARCHAR(100),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- sheets: 프로젝트 내 시트 (도면 페이지)
CREATE TABLE IF NOT EXISTS sheets (
    id          BIGSERIAL PRIMARY KEY,
    project_id  BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL DEFAULT '페이지1',
    "order"     INTEGER NOT NULL DEFAULT 1,
    width       FLOAT NOT NULL DEFAULT 297.0,   -- A4 가로 mm
    height      FLOAT NOT NULL DEFAULT 210.0,   -- A4 세로 mm
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- symbol_types: 심볼 라이브러리 정의 (IEC 60617 등)
CREATE TABLE IF NOT EXISTS symbol_types (
    id                   BIGSERIAL PRIMARY KEY,
    code                 VARCHAR(100) UNIQUE NOT NULL,  -- 예: NO_CONTACT, COIL, FUSE
    name                 VARCHAR(200) NOT NULL,
    category             VARCHAR(100),                  -- 예: 전원, 제어, 모터, 센서, 단자
    svg_data             TEXT,                          -- SVG 원본 데이터
    ports                JSONB NOT NULL DEFAULT '[]',   -- [{id, x, y, direction, type}]
    default_properties   JSONB NOT NULL DEFAULT '{}',   -- {part_number, rated_current, ...}
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- symbols: 시트에 배치된 심볼 인스턴스
CREATE TABLE IF NOT EXISTS symbols (
    id              BIGSERIAL PRIMARY KEY,
    sheet_id        BIGINT NOT NULL REFERENCES sheets(id) ON DELETE CASCADE,
    symbol_type_id  BIGINT NOT NULL REFERENCES symbol_types(id),
    x               FLOAT NOT NULL DEFAULT 0,
    y               FLOAT NOT NULL DEFAULT 0,
    rotation        FLOAT NOT NULL DEFAULT 0,    -- 도 단위 (0/90/180/270)
    mirror          BOOLEAN NOT NULL DEFAULT FALSE,
    properties      JSONB NOT NULL DEFAULT '{}', -- {tag, part_number, rated_current, ...}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- wires: 배선 (심볼 포트 간 연결)
CREATE TABLE IF NOT EXISTS wires (
    id              BIGSERIAL PRIMARY KEY,
    sheet_id        BIGINT NOT NULL REFERENCES sheets(id) ON DELETE CASCADE,
    from_symbol_id  BIGINT REFERENCES symbols(id) ON DELETE SET NULL,
    from_port       VARCHAR(50),                 -- 출발 포트 ID
    to_symbol_id    BIGINT REFERENCES symbols(id) ON DELETE SET NULL,
    to_port         VARCHAR(50),                 -- 도착 포트 ID
    wire_number     VARCHAR(50),                 -- 배선 번호 (예: W001)
    waypoints       JSONB NOT NULL DEFAULT '[]', -- [{x, y}] 경유점
    properties      JSONB NOT NULL DEFAULT '{}', -- {color, cross_section, ...}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- terminals: 단자대
CREATE TABLE IF NOT EXISTS terminals (
    id              BIGSERIAL PRIMARY KEY,
    project_id      BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    terminal_strip  VARCHAR(100),                -- 단자대 이름 (예: X1)
    terminal_number VARCHAR(50),                 -- 단자 번호
    type            VARCHAR(50),                 -- feedthrough, ground, fuse
    wire_id         BIGINT REFERENCES wires(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- macros: 반복 사용 회로 블록 (매크로 라이브러리)
CREATE TABLE IF NOT EXISTS macros (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    category    VARCHAR(100),                -- 예: 모터기동, 제어회로
    data        JSONB NOT NULL DEFAULT '{}', -- {symbols, wires, ...} 직렬화된 블록 데이터
    thumbnail   TEXT,                        -- Base64 or Storage URL
    created_by  VARCHAR(100),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- bom_items: 자재 목록 (BOM)
CREATE TABLE IF NOT EXISTS bom_items (
    id              BIGSERIAL PRIMARY KEY,
    project_id      BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    symbol_type_id  BIGINT REFERENCES symbol_types(id) ON DELETE SET NULL,
    part_number     VARCHAR(200),
    manufacturer    VARCHAR(200),
    quantity        INTEGER NOT NULL DEFAULT 1,
    description     TEXT,
    unit_price      NUMERIC(12,2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_sheets_project_id ON sheets(project_id);
CREATE INDEX IF NOT EXISTS idx_symbols_sheet_id ON symbols(sheet_id);
CREATE INDEX IF NOT EXISTS idx_symbols_type_id ON symbols(symbol_type_id);
CREATE INDEX IF NOT EXISTS idx_wires_sheet_id ON wires(sheet_id);
CREATE INDEX IF NOT EXISTS idx_wires_from_symbol ON wires(from_symbol_id);
CREATE INDEX IF NOT EXISTS idx_wires_to_symbol ON wires(to_symbol_id);
CREATE INDEX IF NOT EXISTS idx_terminals_project_id ON terminals(project_id);
CREATE INDEX IF NOT EXISTS idx_bom_project_id ON bom_items(project_id);
CREATE INDEX IF NOT EXISTS idx_symbol_types_category ON symbol_types(category);
"""

cur.execute(SCHEMA_SQL)
conn.commit()

# ── 3. 결과 검증 ──
print("3단계: 생성된 테이블 확인...")
cur.execute("""
    SELECT table_name,
           (SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = t.table_name AND table_schema = 'public') AS col_count
    FROM information_schema.tables t
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")
tables = cur.fetchall()
for name, cols in tables:
    print(f"  ✓ {name} ({cols}개 컬럼)")

cur.close()
conn.close()
print(f"\n완료: welec DB — {len(tables)}개 테이블 생성")
