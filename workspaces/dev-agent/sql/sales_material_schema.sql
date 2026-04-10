-- =====================================================
-- 판매자재관리 (sales_material_master) + equipment_models 확장
-- cs-wta.com csagent schema
-- 2026-04-10
-- 기존 csagent.equipment_models(id, model_name, category, description, created_at) 재사용
-- =====================================================

BEGIN;

-- ---------- 1. 기존 equipment_models 컬럼 확장 ----------
ALTER TABLE csagent.equipment_models
    ADD COLUMN IF NOT EXISTS code VARCHAR(50),
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS sort_order INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_equipment_models_active
    ON csagent.equipment_models(is_active, sort_order);

-- Seed: MES api_equipmentmodel 스냅샷 14건 + CSV 카테고리 8건
INSERT INTO csagent.equipment_models (model_name, code, category, description, sort_order) VALUES
    ('호닝형상검사기',   'HIM-H',       'HN',  '기본모델',                         10),
    ('검사기-F1',        'HIM-F1',      'HIM', 'HIM-F1 Final Inspection Equipment', 20),
    ('프레스-2CV',       'HAM-HP3-2CV', 'HP',  '',                                 30),
    ('검사기-F2',        'HIM-F2',      'HIM', '',                                 40),
    ('프레스-EV',        'HAM-HP3-EV',  'HP',  '',                                 50),
    ('소결취출기',        'HAM-SINT',    'HS3', '',                                 60),
    ('PVD-L',            'HAM-PVD-L',   'HS2', 'PVD Loading',                      70),
    ('PVD-UL',           'HAM-PVD-UL',  'HS2', 'PVD Unloading',                    80),
    ('포장기',            'HAM-HPL',     'HPL', '',                                 90),
    ('CVD',              'HAM-CVD',     'HS1', '',                                100),
    ('마스크자동기',      'HAM-MASK',    'HS5', '',                                110),
    ('양면연삭핸들러',    'HGM-HD',      'HG',  '',                                120),
    ('라벨부착기',        'HAM-LABEL',   'HLB', '',                                130),
    ('양면연삭설비',      'HGM-DG',      'HGM', '',                                140),
    -- CSV 장비모델구분 카테고리 값도 seed (매칭률 확보)
    ('공통',              NULL,          'CSV', 'CSV 카테고리: 공통',                 1),
    ('PVD 로딩',          NULL,          'CSV', 'CSV 카테고리 (→ PVD-L 매핑 가능)',  71),
    ('PVD 언로딩',        NULL,          'CSV', 'CSV 카테고리 (→ PVD-UL 매핑 가능)', 81),
    ('CVD 로딩',          NULL,          'CSV', 'CSV 카테고리: CVD 로딩',           101),
    ('CVD 언로딩',        NULL,          'CSV', 'CSV 카테고리: CVD 언로딩',         102),
    ('프레스핸들러',      NULL,          'CSV', 'CSV 카테고리: 프레스 핸들러',        31),
    ('검사기',            NULL,          'CSV', 'CSV 카테고리: 검사기 (F1/F2 공통)', 21),
    ('포장핸들러',        NULL,          'CSV', 'CSV 카테고리: 포장 핸들러',          91)
ON CONFLICT (model_name) DO NOTHING;


-- ---------- 2. 판매자재 마스터 ----------
CREATE TABLE IF NOT EXISTS csagent.sales_material_master (
    id BIGSERIAL PRIMARY KEY,
    legacy_id INTEGER UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT '대기'
        CHECK (status IN ('대기', '승인', '반려')),
    material_type VARCHAR(20) NOT NULL DEFAULT '일반'
        CHECK (material_type IN ('소모품', 'Spare', '일반')),
    erp_item_cd VARCHAR(40),
    item_nm VARCHAR(200) NOT NULL,
    sale_model VARCHAR(60),
    unit_price NUMERIC(14,2),
    remark TEXT,
    maker VARCHAR(100),
    equipment_model_id INTEGER REFERENCES csagent.equipment_models(id) ON DELETE SET NULL,
    image_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    drawing_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    sop_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    image_filenames TEXT,
    drawing_filenames TEXT,
    sop_filenames TEXT,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sales_material_status
    ON csagent.sales_material_master(status);
CREATE INDEX IF NOT EXISTS idx_sales_material_type
    ON csagent.sales_material_master(material_type);
CREATE INDEX IF NOT EXISTS idx_sales_material_equip
    ON csagent.sales_material_master(equipment_model_id);
CREATE INDEX IF NOT EXISTS idx_sales_material_erp
    ON csagent.sales_material_master(erp_item_cd);
CREATE INDEX IF NOT EXISTS idx_sales_material_sale_model
    ON csagent.sales_material_master(sale_model);
CREATE INDEX IF NOT EXISTS idx_sales_material_search
    ON csagent.sales_material_master
    USING GIN (to_tsvector('simple', coalesce(item_nm,'') || ' ' || coalesce(sale_model,'') || ' ' || coalesce(erp_item_cd,'')));

-- updated_at triggers
CREATE OR REPLACE FUNCTION csagent.tg_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sales_material_touch ON csagent.sales_material_master;
CREATE TRIGGER trg_sales_material_touch
    BEFORE UPDATE ON csagent.sales_material_master
    FOR EACH ROW EXECUTE FUNCTION csagent.tg_touch_updated_at();

DROP TRIGGER IF EXISTS trg_equipment_models_touch ON csagent.equipment_models;
CREATE TRIGGER trg_equipment_models_touch
    BEFORE UPDATE ON csagent.equipment_models
    FOR EACH ROW EXECUTE FUNCTION csagent.tg_touch_updated_at();

COMMIT;

-- 검증
SELECT 'equipment_models' AS t, COUNT(*) FROM csagent.equipment_models
UNION ALL
SELECT 'sales_material_master', COUNT(*) FROM csagent.sales_material_master;
