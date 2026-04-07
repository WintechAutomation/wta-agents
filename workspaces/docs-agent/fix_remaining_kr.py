import re

filepath = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_JP.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# TOC remaining items
toc_replacements = {
    '<span>6. 팔레트 관리</span>': '<span>6. パレット管理</span>',
    '<span>6.1. 팔레트 관리 설정</span>': '<span>6.1. パレット管理設定</span>',
    '<span>9.1. 티칭 위치 설정</span>': '<span>9.1. ティーチング位置設定</span>',
    '<span>10. 자동 운전</span>': '<span>10. 自動運転</span>',
    '<span>10.1. 원점 복귀</span>': '<span>10.1. 原点復帰</span>',
    '<span>10.2. 시작 및 일시정지</span>': '<span>10.2. 開始および一時停止</span>',
    '<span>10.3. 정지</span>': '<span>10.3. 停止</span>',
    '<span>10.4. 카메라 위치 보정</span>': '<span>10.4. カメラ位置補正</span>',
    '<span>10.5. 이미지 설정</span>': '<span>10.5. 画像設定</span>',
    '<span>10.6. 소모품 확인</span>': '<span>10.6. 消耗品確認</span>',
    '<span>11. 작업자 조작 순서</span>': '<span>11. 作業者操作手順</span>',
    '<span>11.1. 팔레트 설정</span>': '<span>11.1. パレット設定</span>',
    '<span>11.2. 봉 설정</span>': '<span>11.2. ロッド設定</span>',
    '<span>11.3. 스페이서 설정</span>': '<span>11.3. スペーサー設定</span>',
    '<span>11.4. 모델 파일 생성</span>': '<span>11.4. モデルファイル作成</span>',
    '<span>11.5. 적재 설정</span>': '<span>11.5. 積載設定</span>',
    '<span>11.6. 환경설정</span>': '<span>11.6. 環境設定</span>',
    '<span>11.7. 티칭 선택</span>': '<span>11.7. ティーチング選択</span>',
    '<span>11.8. 운전 시작</span>': '<span>11.8. 運転開始</span>',
    '<span>11.9. 비전 설정</span>': '<span>11.9. ビジョン設定</span>',
    '<span>12.1. 에러 리스트</span>': '<span>12.1. エラーリスト</span>',
    '<span>13. 유지보수</span>': '<span>13. メンテナンス</span>',
    '<span>13.1. 정기 점검</span>': '<span>13.1. 定期点検</span>',
    '<span>13.2. 자주 발생하는 문제</span>': '<span>13.2. よくある問題</span>',
    '<span>13.3. 소모품 리스트</span>': '<span>13.3. 消耗品リスト</span>',
    '<span>부록 A. 도면</span>': '<span>付録 A. 図面</span>',
}

# Safety sticker alt attributes
sticker_replacements = {
    'alt="電気 위험 (SLE-199)"': 'alt="電気危険 (SLE-199)"',
    'alt="끼임/말림 위험 (SLC-135)"': 'alt="挟まれ/巻き込まれ危険 (SLC-135)"',
    'alt="충돌 위험 (SLA-004)"': 'alt="衝突危険 (SLA-004)"',
    'alt="도어 인터록 운전 중 (SLA-029)"': 'alt="ドアインターロック稼働中 (SLA-029)"',
}

# Chapter 11 page section label
ch11_replacements = {
    '>11. 작업자 조작 순서</div>': '>11. 作業者操作手順</div>',
    # Line 896: mixed content
    '<td>자동 運転開始</td>': '<td>自動運転開始</td>',
    # Line 935
    '>11.5. 적재 설정</h2>': '>11.5. 積載設定</h2>',
    # Line 937-939
    '<li>모델을 선택합니다.</li>': '<li>モデルを選択します。</li>',
    '<li>+ 버튼으로 팔레트를 하나 추가합니다.</li>': '<li>+ ボタンでパレットを1つ追加します。</li>',
    '<li>큰 원 안의 작은 숫자 원을 클릭하여 작업 인덱스를 설정합니다.</li>': '<li>大きい円の中の小さい数字円をクリックして作業インデックスを設定します。</li>',
    # Line 943
    '>그림 11-6 적재 설정</div>': '>図 11-6 積載設定</div>',
    # Line 945
    '>11.6. 환경설정</h2>': '>11.6. 環境設定</h2>',
    # Line 946
    '<p>파라미터를 조정합니다.</p>': '<p>パラメータを調整します。</p>',
    # Line 949
    '>그림 11-7 환경설정</div>': '>図 11-7 環境設定</div>',
    # Line 951
    '>11.7. 티칭 선택</h2>': '>11.7. ティーチング選択</h2>',
    # Line 954
    '>그림 11-8 티칭 선택</div>': '>図 11-8 ティーチング選択</div>',
    # Line 956
    '>11.8. 운전 시작</h2>': '>11.8. 運転開始</h2>',
    # Line 959
    '>그림 11-9 운전 시작</div>': '>図 11-9 運転開始</div>',
    # Line 961
    '<p>TP 조작 화면 (티칭 시):</p>': '<p>TP 操作画面（ティーチング時）：</p>',
    # Line 963-969
    '<li>축 선택 버튼</li>': '<li>軸選択ボタン</li>',
    '<li>상/하/좌/우 버튼</li>': '<li>上/下/左/右ボタン</li>',
    '<li>빠른 동작 버튼 (좌→우: 빈 에어 블로우 / 反転 電気 그리퍼 / 팔레트 ピックアップ 그리퍼 / 제품 그리퍼 / 스페이서 그리퍼)</li>': '<li>クイック動作ボタン（左→右：空エアブロー / 反転電気グリッパー / パレットピックアップグリッパー / 製品グリッパー / スペーサーグリッパー）</li>',
    '<li>Move / Jog 선택</li>': '<li>Move / Jog 選択</li>',
    '<li>Move 시 1회 이동 거리</li>': '<li>Move 時の1回移動距離</li>',
    '<li>수동 조작 시 이동 속도</li>': '<li>手動操作時の移動速度</li>',
    '<li>저장/취소 버튼</li>': '<li>保存/キャンセルボタン</li>',
    # Line 971
    '>11.9. 비전 설정</h2>': '>11.9. ビジョン設定</h2>',
    # Line 974
    '>그림 11-10 비전 설정</div>': '>図 11-10 ビジョン設定</div>',
    # Line 979-982
    '<td>밝기 설정</td><td>검출용 이미지의 밝기를 설정합니다.</td>': '<td>明るさ設定</td><td>検出用画像の明るさを設定します。</td>',
    '<td>형태 설정</td><td>인서트의 형태를 선택하고 크기를 조정합니다.</td>': '<td>形状設定</td><td>インサートの形状を選択しサイズを調整します。</td>',
    '<td>등록</td><td>형태 설정이 완료된 이미지를 등록합니다.</td>': '<td>登録</td><td>形状設定が完了した画像を登録します。</td>',
    '<td>검출</td><td>검출 결과를 확인합니다.</td>': '<td>検出</td><td>検出結果を確認します。</td>',
    # Line 985
    '>조명 설정</h3>': '>照明設定</h3>',
    # Line 986
    '<p>캡처 버튼을 클릭하여 이미지를 표시하고, 제품 검출에 최적인 조건으로 밝기를 조정합니다 (최대 255).</p>': '<p>キャプチャボタンをクリックして画像を表示し、製品検出に最適な条件で明るさを調整します（最大255）。</p>',
}

all_replacements = {}
all_replacements.update(toc_replacements)
all_replacements.update(sticker_replacements)
all_replacements.update(ch11_replacements)

count = 0
for old, new in all_replacements.items():
    if old in content:
        content = content.replace(old, new)
        count += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Applied {count} replacements')
