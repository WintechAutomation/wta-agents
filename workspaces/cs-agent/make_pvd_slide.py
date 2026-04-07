import json, sys, re, os
sys.stdout.reconfigure(encoding='utf-8')

with open('C:/MES/wta-agents/workspaces/cs-agent/pvd_cs_full.json', encoding='utf-8') as f:
    data = json.load(f)

# ── 카테고리 분류 (이전 분석과 동일 키워드) ──
CATEGORIES = [
    ("에러/알람",    r"에러|알람|오류|alarm|error|fault|경보"),
    ("스페이서",     r"스페이서|spacer"),
    ("진공/진공도",  r"진공|vacuum|펌프|pump|리크|leak"),
    ("로딩/언로딩",  r"로딩|언로딩|loading|unloading|인덱스|index"),
    ("파워/전원",    r"파워|전원|power|voltage|전압|UPS|퓨즈|fuse|전기"),
    ("코팅 품질",    r"코팅|coating|박리|색상|두께|density|품질"),
    ("센서/감지",    r"센서|sensor|감지|detect|광센서|proximity"),
    ("타겟/소모품",  r"타겟|target|cathode|캐소드|소모"),
    ("냉각/수냉",    r"냉각|수냉|cooling|water|온도|temperature|열"),
    ("기계/실린더",  r"실린더|cylinder|모터|motor|서보|servo|액추에이터|구동|불량"),
]
OTHERS = "기타"

def classify(title, symptom=""):
    text = f"{title} {symptom or ''}"
    for name, pat in CATEGORIES:
        if re.search(pat, text, re.IGNORECASE):
            return name
    return OTHERS

# 분류 + 첨부 여부
for r in data:
    r['category'] = classify(r.get('title',''), r.get('symptom_and_cause','') or '')
    # Collect image/video attachments
    imgs, vids = [], []
    for au in (r.get('attachment_urls') or []):
        if not isinstance(au, dict): continue
        url = au.get('url','')
        ct = au.get('content_type','')
        if 'image' in ct or url.lower().endswith(('.jpg','.jpeg','.png','.gif','.webp')):
            imgs.append(url)
        elif 'video' in ct or url.lower().endswith(('.mp4','.mov','.avi','.webm')):
            vids.append(url)
    for au in (r.get('result_attachment_urls') or []):
        if not isinstance(au, dict): continue
        url = au.get('url','')
        ct = au.get('content_type','')
        if 'image' in ct or url.lower().endswith(('.jpg','.jpeg','.png','.gif','.webp')):
            imgs.append(url)
        elif 'video' in ct or url.lower().endswith(('.mp4','.mov','.avi','.webm')):
            vids.append(url)
    r['img_urls'] = imgs
    r['vid_urls'] = vids
    r['has_media'] = bool(imgs or vids)

# TOP 10 by frequency
from collections import Counter
cat_counts = Counter(r['category'] for r in data)
top10 = [c for c, _ in cat_counts.most_common(10)]
print("TOP 10 categories:", cat_counts.most_common(10))

# For each category, find best representative case (with media preferred)
slides = []
for rank, cat in enumerate(top10, 1):
    cat_records = [r for r in data if r['category'] == cat]
    # Prefer records with media
    with_media = [r for r in cat_records if r['has_media']]
    pool = with_media if with_media else cat_records
    # Pick the one with most media
    rep = max(pool, key=lambda r: len(r['img_urls']) + len(r['vid_urls'])*2)
    slides.append({
        'rank': rank,
        'category': cat,
        'total': cat_counts[cat],
        'with_media': len(with_media),
        'rep': rep,
    })
    print(f"[{rank}] {cat}: {cat_counts[cat]}건, 미디어포함 {len(with_media)}건 → 대표 id={rep['id']}, imgs={len(rep['img_urls'])}, vids={len(rep['vid_urls'])}")

# Save slides data
out_path = 'C:/MES/wta-agents/workspaces/cs-agent/pvd_slides_data.json'
# Prepare serializable version
slides_out = []
for s in slides:
    r = s['rep']
    slides_out.append({
        'rank': s['rank'],
        'category': s['category'],
        'total': s['total'],
        'with_media': s['with_media'],
        'rep_id': r['id'],
        'title': r.get('title',''),
        'project_name': r.get('project_name',''),
        'customer': r.get('customer',''),
        'serial_no': r.get('serial_no',''),
        'received_at': str(r.get('cs_received_at','')),
        'symptom': (r.get('symptom_and_cause','') or '')[:300],
        'action': (r.get('action_result','') or '')[:300],
        'img_urls': r['img_urls'],
        'vid_urls': r['vid_urls'],
    })

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(slides_out, f, ensure_ascii=False, indent=2)
print(f"\nSaved slides data: {out_path}")
