# MES 백엔드 API 목록 (DB 조회 관련)

> 기준: `C:/MES/backend/cmd/server/main.go`
> 베이스: `http://localhost:8100/api`
> 인증: JWT Bearer (공개 API 제외)

---

## ERP 데이터 조회 (`/api/erp`)

| 메서드 | 경로 | 용도 |
|-------|------|------|
| POST | `/erp/items/search` | 품목 검색 (body: 검색어) |
| GET  | `/erp/items/:item_cd` | 품목 상세 조회 |
| POST | `/erp/bom` | BOM 조회 |
| POST | `/erp/bom/hierarchical` | BOM 계층 조회 |
| POST | `/erp/bom/raw-materials` | 원자재 BOM 조회 |
| GET  | `/erp/inventory/raw-materials` | 원자재 재고 현황 |
| GET  | `/erp/orders/status` | 수주 현황 |
| GET  | `/erp/projects` | ERP 프로젝트 목록 |
| GET  | `/erp/projects/active` | 진행중 ERP 프로젝트 |
| GET  | `/erp/purchase/progress/:po_plan_no` | 구매 진행 현황 |
| POST | `/erp/purchase/progress/bulk` | 구매 진행 일괄 조회 |
| GET  | `/erp/project-purchase-orders/:project_code` | 프로젝트별 발주현황 |
| GET  | `/erp/suppliers` | 거래처 목록 |
| GET  | `/erp/suppliers/:cust_cd` | 거래처 상세 |
| GET  | `/erp/suppliers/:cust_cd/receipt-waiting` | 거래처별 입고대기 품목 |
| GET  | `/erp/receipts` | 입고 목록 |
| GET  | `/erp/receipts/:acpt_no/:acpt_seq` | 입고 상세 |
| GET  | `/erp/receiving-status` | 입고 현황 |
| GET  | `/erp/receiving-summary-stats` | 입고 요약 통계 |
| GET  | `/erp/unit-receiving-stats` | 단위 입고 통계 |
| POST | `/erp/pending-receiving-status` | 미입고 현황 (MCA210T 기반) |
| POST | `/erp/actual-receiving-status` | 실입고 현황 (MCA210T 기반) |
| POST | `/erp/search-projects` | ERP 프로젝트 검색 |
| GET  | `/erp/bom-release/status/:itemCode` | BOM 출도 상태 |
| GET  | `/erp/bom-release/history/:itemCode` | BOM 출도 이력 |
| GET  | `/erp/delivery-date-change/history` | 납기일 변경 이력 |
| GET  | `/materials/today-receipts` | 오늘 입고 현황 |

---

## MES 생산 데이터 조회 (`/api/production`)

| 메서드 | 경로 | 용도 |
|-------|------|------|
| GET | `/production/projects` | 프로젝트 목록 |
| GET | `/production/projects/active_projects` | 진행중 프로젝트 |
| GET | `/production/projects/dashboard_projects` | 대시보드 프로젝트 |
| GET | `/production/projects/:id` | 프로젝트 상세 |
| GET | `/production/projects/:id/processes` | 프로젝트 공정 |
| GET | `/production/projects/:id/shipping` | 프로젝트 출하 데이터 |
| GET | `/production/project-schedules/get_project_schedule_by_code` | 프로젝트 일정 |
| GET | `/production/project-detailed-schedules` | 상세 일정 목록 |
| GET | `/production/project-detailed-schedules/by_project_code_detailed` | 프로젝트별 상세 일정 |
| GET | `/production/project-detailed-schedules/calendar_events` | 캘린더 이벤트 |
| GET | `/production/project-detailed-schedules/get_statistics` | 일정 통계 |
| GET | `/production/labor-hours` | 공수 목록 |
| GET | `/production/labor-hours/by_model_code` | 모델별 공수 |

---

## 대시보드 통계 (`/api/dashboard`)

| 메서드 | 경로 | 용도 |
|-------|------|------|
| GET | `/dashboard/stats` | 전체 통계 |
| GET | `/dashboard/project-stats` | 프로젝트 통계 |
| GET | `/dashboard/shipment-stats` | 출하 통계 |
| GET | `/dashboard/inventory-stats` | 재고 통계 |
| GET | `/dashboard/workspace-projects` | 워크스페이스 프로젝트 |
| GET | `/dashboard/my` | 내 대시보드 |

---

## 품질 관리 (`/api/quality`)

| 메서드 | 경로 | 용도 |
|-------|------|------|
| GET | `/quality/nonconformance` | 부적합 목록 |
| GET | `/quality/nonconformance/statistics` | 부적합 통계 |
| GET | `/quality/nonconformance/:id` | 부적합 상세 |
| GET | `/quality/nonconformance/:id/history` | 부적합 변경이력 |
| GET | `/quality/nonconformance/project/:project_id/statistics` | 프로젝트별 부적합 통계 |
| GET | `/quality/inspection-items` | 검사항목 목록 |

---

## 자재 관리 (`/api/materials`)

| 메서드 | 경로 | 용도 |
|-------|------|------|
| GET | `/materials/bad-inventory` | 불량재고 목록 |
| GET | `/materials/bad-inventory/statistics` | 불량재고 통계 |
| GET | `/materials/saleable-items` | 판매자재 목록 |
| GET | `/materials/today-receipts` | 오늘 입고 |

---

## 수주/판매 관리 (`/api/orders`)

| 메서드 | 경로 | 용도 |
|-------|------|------|
| GET | `/orders` | 수주 목록 |
| GET | `/orders/statistics` | 수주 통계 |
| GET | `/orders/dashboard_stats` | 수주 대시보드 통계 |
| GET | `/orders/:id` | 수주 상세 |

---

## 공개 API (인증 불필요, `/api/external/v1`)

| 메서드 | 경로 | 용도 |
|-------|------|------|
| GET | `/external/v1/projects` | 프로젝트 목록 (외부) |
| GET | `/external/v1/projects/:projectCode` | 프로젝트 상세 (외부) |

---

## 참고

- ERP 데이터 중 **자재 사용(출고) 이력** 전용 API는 현재 없음
  - 입고(`/erp/receipts`) 및 재고현황(`/erp/inventory/raw-materials`)은 존재
  - 월별 사용량 조회는 `POST /erp/actual-receiving-status` 에서 기간 파라미터로 근접 가능
- 모든 ERP API는 erpDB 연결이 필요하며, 서버 시작 시 연결 실패 시 비활성화됨
