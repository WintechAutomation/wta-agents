# GraphRAG PoC — DB 스키마 기반 온톨로지 초안 (db-manager 담당)

작성일: 2026-04-05
기준: 실제 PostgreSQL(MES) + ERP 연동 테이블 조회 결과

---

## 1. MES DB 핵심 엔티티 (csagent 스키마)

### 1-1. 장비 도메인

#### EquipmentModel (csagent.equipment_models)
- 속성: `id`, `model_name`, `category`, `description`
- 의미: 장비 기종 마스터 (HIM 검사기, 포장기, NC Press, 연삭기 등 기종 계열)

#### EquipmentUnit (csagent.equipment_units)
- 속성: `id`, `serial_number`, `model_id`, `customer_name`, `install_date`, `warranty_expires`, `location`
- 의미: 실제 출하·설치된 개별 장비 호기 (고객사에 납품된 단위 장비)

#### EquipmentSetup (csagent.equipment_setup)
- 속성: `id`, `branch_id`
- 의미: 장비 설치/셋업 이력 (해외법인 지사별 연결)

#### ErrorCode (csagent.error_codes)
- 속성: `id`, `model_id`
- 의미: 기종별 에러코드 정의

#### BOM (csagent.bom)
- 속성: `id`, `model_id`, `part_id`
- 의미: 장비 모델 ↔ 부품 구성 매핑

### 1-2. CS / 수리 도메인

#### CSHistory (csagent.cs_history)
- 속성: `id`, `shipment_id(→EquipmentUnit)`, `status`, `title`, `symptom_and_cause`, `cs_received_at`, `cs_handler`, `cs_completed_at`, `cause_dept_*`, `cause_part`, `action_result`, `free_paid_type`
- 의미: 고객 CS 접수·처리 이력 (증상, 원인부서, 조치결과 포함)
- 다국어: `title_en/zh/ja`, `symptom_and_cause_en/zh/ja`

#### CSHistoryExpense / Labor / Material
- 속성: `cs_history_id` (공통 FK → CSHistory)
- 의미: CS당 비용·공수·자재 세부내역

#### RepairHistory (csagent.repair_history)
- 속성: `id`, `unit_id(→EquipmentUnit)`, `error_code_id(→ErrorCode)`
- 의미: 수리 이력 (에러코드 → 장비 단위 연결)

#### SetupIssue (csagent.setup_issues)
- 속성: `id`, `setup_id(→EquipmentSetup)`
- 의미: 셋업 중 발생 이슈

### 1-3. 부품/재고 도메인

#### PartsMaster (csagent.parts_master)
- 속성: `id`, `part_number`, `name`, `name_en`, `category_id(→PartsCategory)`, `unit`, `min_stock`
- 의미: 부품 마스터 (소모품/스페어파츠)

#### PartsRequest / PartsRequestItem
- 속성: `request_id(→PartsRequest)`, `part_id(→PartsMaster)`, `branch_id(→Branches)`
- 의미: 지사별 부품 요청·청구

#### InventoryTransaction (csagent.inventory_transaction)
- 속성: `part_id(→PartsMaster)`, `branch_id(→Branches)`
- 의미: 부품 입출고 거래 이력

### 1-4. 조직/지사 도메인

#### Branch (csagent.branches)
- 의미: 해외법인·지사 (중국, 일본, 유럽 등)

#### User (csagent.users)
- 의미: CS 담당자, 수리자, 감사로그 주체

---

## 2. MES DB 핵심 엔티티 (public 스키마)

### 2-1. 프로젝트/출하 도메인

#### ShipmentTable (public.shipment_table)
- 속성: `id`, `doc_no`, `status`, `shipment_no`, `model_category`, `maker_press/grinder`, `project_no`, `project_name`, `customer`, `customer_eng`, `customer_zh/ja`, `serial_no`, `domestic_overseas`, `order_date`, `shipment_date`, `export_date`, `controller`, `io`, `vision`, `linked_equipment_model`, `mes_project_code`, `customer_ref_id(→Customer)`
- 의미: 출하 관리 마스터 (장비 프로젝트 ↔ 고객 연결 핵심 엔티티)

#### Customer (public.customer)
- 속성: `id`, `customer_code`, `company_name_ko`, `company_name_en`, `country`, `industry`, `is_active`
- 의미: 고객사 마스터 (한국야금, 대구텍, Korloy, 교세라, 간저우 하이썽 등)

#### Partner (public.partner)
- 속성: `id`, `partner_code`, `partner_name`, `country`, `main_products`, `status`
- 의미: 협력업체 마스터 (구매처, 외주업체)

### 2-2. 출하검사/품질 도메인

#### ChecklistInspection (public.api_checklistinspection)
- 속성: `id`, `inspection_date`, `status`, `project_id(→Project)`, `product_type_id(→ProductType)`, `inspector_id(→User)`
- 의미: 출하검사 헤더 (프로젝트·제품유형별 검사 레코드)

#### ChecklistInspectionItem (public.api_checklistinspectionitem)
- 속성: `id`, `inspection_id(→ChecklistInspection)`, `template_item_id(→ChecklistItemTemplate)`, `result`, `checked_by_id(→User)`
- 의미: 검사 항목별 결과 (합격/불합격/해당없음)

#### BadInventory (public.api_badinventory)
- 속성: `id`, `item_code`, `item_name`, `category`, `quantity`, `reason`, `status`, `estimated_loss`
- 의미: 불량재고 관리 (부적합품 처리)

#### ProductionIssue (public.production_issues)
- 속성: `id`, `issue_number`, `title`, `issue_type`, `priority`, `status`, `project_code`, `project_name`, `item_code`, `responsible_department`, `reported_date`, `due_date`
- 의미: 생산 이슈 트래킹 (부적합, 개선요청 등)

### 2-3. 재고/자재 도메인

#### SemiStockMaster (public.semi_stock_master)
- 속성: `id`, `project_code`, `project_name`, `unit_number`, `item_code`, `item_name`, `current_stock`, `safety_stock`, `location`, `erp_item_id`, `erp_last_sync`
- 의미: 반제품 재고 마스터 (ERP 연동)

#### Material (public.api_material)
- 속성: `id`, `name`, `material_type`, `unit`, `standard_price`, `stock_quantity`, `min_stock`
- 의미: 자재 마스터

### 2-4. HR/인사 도메인

#### Employee (public.employee)
- 속성: `id`, `employee_number`, `name_korean`, `current_department`, `current_position`, `hire_date`
- 의미: 사내 직원 마스터 (부서·직급 연결)

---

## 3. ERP DB 연동 엔티티 (public.erp_item_master — SQL Server 미러링)

#### ERPItemMaster (public.erp_item_master)
- 속성: `item_cd`, `item_nm`, `spec`, `item_accnt`, `item_kind`, `maker`, `inv_unit`, `base_price`, `item_lvl1/2/3`, `supply_type`, `safe_qty`, `sale_code`, `model`, `cust_cd`, `wc_cd`, `wh_type`, `last_synced_at`
- 의미: ERP 품목 마스터 (제품·반제품·자재·외주 등 계층 분류)
- 주요 분류: `item_kind` (제품=0, 반제품=1, 원자재=2 등), `item_lvl1~3` (계층 카테고리)
- 연동: `erp_last_sync` 기준 MES SemiStockMaster.erp_item_id와 연결

---

## 4. 문서 RAG 테이블 연동 관점

### RAG 엔티티 목록

#### ManualDocument (manual.documents)
- 속성: `id`, `source_file`, `file_hash`, `category`, `chunk_index`, `chunk_type`, `page_number`, `content`, `image_url`, `metadata(jsonb)`, `embedding(vector 2000dim)`
- 의미: 부품/서보/HMI/센서 등 제조사 매뉴얼 청크 (199,355건)
- `category` 값: 1_robot, 2_sensor, 3_hmi, 4_servo, 5_inverter, 6_plc, 7_pneumatic, 8_etc

#### WTADocument (manual.wta_documents)
- 속성: `id`, `source_file`, `category`, `chunk_index`, `content`, `metadata(jsonb)`, `embedding(vector 2000dim)`
- 의미: WTA 사내 문서 청크 — Confluence CM 스페이스, 기술문서 등 (64,851건)
- `category` 값: Confluence_CM, 기술문서, 사양서 등

#### CSVectorEmbedding (csagent.vector_embeddings)
- 속성: `id`, `source_type`, `source_id`, `text`, `metadata(jsonb)`, `embedding(vector)`
- 의미: CS 이력·매뉴얼 등 다용도 임베딩 (3,318건)
- `source_type`: cs_history, manual, error_code 등

---

## 5. 핵심 FK / 주요 관계 목록

| 관계 | 소스 테이블.컬럼 → 대상 테이블.컬럼 | 의미 |
|------|--------------------------------------|------|
| R1 | `csagent.equipment_units.model_id` → `csagent.equipment_models.id` | 장비 호기 ↔ 기종 모델 |
| R2 | `csagent.cs_history.shipment_id` → `csagent.equipment_units.id` | CS이력 ↔ 개별 장비 호기 |
| R3 | `csagent.repair_history.unit_id` → `csagent.equipment_units.id` | 수리이력 ↔ 장비 호기 |
| R4 | `csagent.repair_history.error_code_id` → `csagent.error_codes.id` | 수리이력 ↔ 에러코드 |
| R5 | `csagent.error_codes.model_id` → `csagent.equipment_models.id` | 에러코드 ↔ 기종 모델 |
| R6 | `csagent.bom.model_id` → `csagent.equipment_models.id` | BOM ↔ 기종 모델 |
| R7 | `csagent.bom.part_id` → `csagent.parts.id` | BOM ↔ 부품 |
| R8 | `public.shipment_table.customer_ref_id` → `public.customer.id` | 출하 ↔ 고객사 |
| R9 | `public.api_checklistinspection.project_id` → `public.api_project.id` | 출하검사 ↔ 프로젝트 |
| R10 | `public.api_checklistinspectionitem.inspection_id` → `public.api_checklistinspection.id` | 검사항목 ↔ 검사헤더 |
| R11 | `public.api_checklistinspectionitem.template_item_id` → `public.api_checklistitemtemplate.id` | 검사항목 ↔ 표준템플릿 |
| R12 | `public.semi_stock_master.erp_item_id` → `public.erp_item_master.item_cd` | 반제품재고 ↔ ERP품목 |
| R13 | `manual.documents.category` ↔ `csagent.equipment_models.category` | 매뉴얼 카테고리 ↔ 장비 기종 (논리적 연결, FK 없음) |
| R14 | `csagent.vector_embeddings.source_type=cs_history, source_id` → `csagent.cs_history.id` | CS 벡터 ↔ CS 이력 (논리적 연결) |
| R15 | `csagent.cs_history_expense/labor/material.cs_history_id` → `csagent.cs_history.id` | CS 세부비용·공수·자재 ↔ CS 이력 |

---

## 6. GraphRAG 연결 관점 핵심 패스

```
고객사(Customer)
  └─ 출하(ShipmentTable)
       └─ 장비호기(EquipmentUnit)
            ├─ 기종모델(EquipmentModel)
            │    ├─ 에러코드(ErrorCode)  ←→  수리이력(RepairHistory)
            │    └─ BOM ─→ 부품(Parts/PartsMaster)
            └─ CS이력(CSHistory)
                 ├─ 비용(CSHistoryExpense) / 공수(CSHistoryLabor) / 자재(CSHistoryMaterial)
                 └─ [벡터] CSVectorEmbedding

제품유형(ProductType)
  └─ 출하검사(ChecklistInspection)
       └─ 검사항목(ChecklistInspectionItem) ←→ 표준템플릿(ChecklistItemTemplate)

ERP품목(ERPItemMaster)
  └─ 반제품재고(SemiStockMaster)

매뉴얼(ManualDocument, 카테고리=장비기종)
  └─ [유사도 검색] EquipmentModel.category 기준 연결
WTA문서(WTADocument)
  └─ [유사도 검색] CS이력 증상·원인 텍스트 연결
```

---

*본 초안은 실제 DB 테이블·컬럼 조회 결과 기준. 추측 없음.*
*crafter/MAX 초안과 통합 후 최종본 작성 예정.*
