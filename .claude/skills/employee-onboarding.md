# 신규직원 온보딩 스킬

## 트리거
- IMAP 메일 모니터(`imap-monitor.py`)가 신규입사자 안내 메일 감지 시 MAX 보고 → admin-agent 위임
- 부서장 직접 요청 시 ("OOO 온보딩 진행해줘")

## 입력 정보
메일 파싱 또는 수동 입력:
- **이름** (한글 실명, 예: 홍길동)
- **부서** (예: 기구설계, 제어설계)
- **이메일** (그룹웨어 계정, 예: gdhong@wta.kr)
- **입사일** (예: 2026-04-08)

---

## 부서 → Atlassian 그룹 매핑

| 부서명 | Atlassian 그룹 |
|--------|--------------|
| 기구설계 | 기구설계팀 |
| 제어설계 | 제어설계팀 |
| 소프트웨어 | 소프트웨어팀 |
| 품질/CS | 품질/CS팀 |
| 영업 | 영업팀 |
| 구매 | 구매팀 |
| 생산관리 | 생산관리팀 |
| 제작 | 제작팀 |
| 연삭 | 연삭팀 |
| 연구소 | 연구소 |
| 광학기술센터 | 광학기술센터 |
| 전략기획 | 전략기획팀 |
| 장비사업부 | 장비사업부 |
| 비전팀 | 비전팀 |
| 임원/CEO | CEO |

공통 그룹 (모든 신규직원 추가): `jira-software-users`, `confluence-users`

---

## 처리 단계

### 1단계 — Atlassian (Jira/Confluence) ✅ API 자동

API 정보는 MES DB `api_systemconfig` 테이블 (`system_type = 'jira'`)에서 로드.

**1-1. 계정 초대**
```
POST {jira_url}/rest/api/3/user
Authorization: Basic {base64(email:api_token)}
Content-Type: application/json

{
  "emailAddress": "{입사자이메일}",
  "displayName": "{이름}",
  "notification": true
}
```
- 성공: 201 Created → `accountId` 저장
- 이미 존재: 409 Conflict → 기존 계정 검색 후 accountId 확인

**1-2. 부서 그룹 추가**
```
POST {jira_url}/rest/api/3/group/user?groupname={부서그룹}
{
  "accountId": "{accountId}"
}
```

**1-3. 공통 그룹 추가** (2회 반복)
```
POST {jira_url}/rest/api/3/group/user?groupname=jira-software-users
POST {jira_url}/rest/api/3/group/user?groupname=confluence-users
```

**1-4. 확인**
```
GET {jira_url}/rest/api/3/user?accountId={accountId}&expand=groups
```
소속 그룹 목록에 부서 그룹 + 공통 그룹 포함 확인.

**구현 참조**: `workspaces/admin-agent/atlassian_restrict_access.py` (그룹 조작 패턴 동일)

---

### 2단계 — NAS (시놀로지 192.168.1.6) ⚠️ 수동 처리

> **추후 자동화 예정** — 현재는 아래 절차 안내로 대체

수동 처리 가이드:
1. 브라우저에서 `http://192.168.1.6:5000` 접속 (관리자 계정)
2. 제어판 → 사용자 및 그룹 → 사용자 → 생성
3. 이름: `{이름}`, 이메일: `{이메일}`, 초기 비밀번호 설정
4. 소속 그룹: 부서별 공유폴더 접근 그룹 지정
5. 처리 후 부서장에게 확인 요청

---

### 3단계 — ERP ⚠️ 수동 처리

> **추후 자동화 예정** — 현재는 아래 절차 안내로 대체

수동 처리 가이드:
1. ERP 서버(192.168.1.201) 관리자 페이지 접속
2. 시스템 → 사용자 관리 → 신규 등록
3. 부서, 직책, 권한 레벨 설정
4. 처리 후 부서장에게 확인 요청

---

### 4단계 — 완료 처리

**4-1. 부서장 텔레그램 보고**
```
send_message(to="MAX", message="""
[신규직원 온보딩 완료]
이름: {이름} / 부서: {부서} / 입사일: {입사일}

✅ Atlassian: 계정 초대 + {부서그룹} + jira-software-users + confluence-users 추가
⚠️ NAS: 수동 처리 필요
⚠️ ERP: 수동 처리 필요
""")
```

**4-2. 완료 메일 발송** (SMTP)
- 수신: 관리팀 담당자 (입사 안내 메일 발신자에게 회신)
- 내용: 처리 완료 항목, 수동 처리 필요 항목 안내

---

## 실행 체크리스트

- [ ] 입력 정보 확인 (이름, 부서, 이메일, 입사일)
- [ ] 부서 → Atlassian 그룹 매핑 확인
- [ ] Atlassian 계정 초대 완료 (accountId 확보)
- [ ] 부서 그룹 추가 완료
- [ ] jira-software-users 추가 완료
- [ ] confluence-users 추가 완료
- [ ] 그룹 소속 최종 확인
- [ ] NAS 수동 처리 안내 전달
- [ ] ERP 수동 처리 안내 전달
- [ ] 부서장 텔레그램 보고 완료
- [ ] 완료 메일 발송 완료

---

## 오류 대응

| 오류 | 원인 | 조치 |
|------|------|------|
| 계정 초대 409 | 이미 Atlassian 계정 존재 | `/rest/api/3/user/search`로 accountId 조회 후 그룹 추가 진행 |
| 그룹 추가 403 | 권한 부족 | DB `api_systemconfig` 토큰 확인, admin.atlassian.com에서 수동 처리 |
| 그룹명 404 | 그룹명 불일치 | `/rest/api/3/groups/picker`로 실제 그룹명 확인 |
