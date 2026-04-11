import subprocess, time, os, re, sys
from pathlib import Path

base = Path('C:/MES/wta-agents/data/manuals-v2')
files = [
  ('2_sensor','Cognex_IS5000_QuickStart_KO.pdf'),
  ('1_robot','Mitsubishi_BFP-A8586-D_MaintenanceManual_KO.pdf'),
  ('5_inverter','Yaskawa_V1000_TechnicalManual_KO.pdf'),
]
# pre-check
missing = [f'{c}/{f}' for c,f in files if not (base/c/f).exists()]
if missing:
    print('PRECHECK FAIL:', missing); sys.exit(1)
print(f'precheck OK {len(files)}/{len(files)}')

env = os.environ.copy()
env['V2_VLM'] = '1'
env['V2_EMBED'] = '1'

t0 = time.time()
for i,(c,f) in enumerate(files, 8):
    p = str(base/c/f)
    print(f'--- [{i}/10] {f} (cat={c}) ---', flush=True)
    st = time.time()
    r = subprocess.run(
        ['C:/Python314/python.exe','manuals_v2_parse_docling.py', p],
        capture_output=True, text=True, encoding='utf-8', errors='replace', env=env
    )
    el = time.time() - st
    out = r.stdout or ''
    # extract summary line (dict)
    m = re.search(r"\{'file_id':[^}]+\}", out)
    if m: print(' ', m.group(0))
    # error counts
    vlm_err = out.count('vlm_err') and 0  # simple
    vlm_err = len(re.findall(r'vlm fail', out))
    upload_err = len(re.findall(r'upload fail', out))
    print(f'  elapsed: {el:.1f}s  vlm_err={vlm_err}  upload_err={upload_err}  (total: {(time.time()-t0)/60:.1f} min)', flush=True)
    if r.returncode != 0:
        print(f'  ❌ exit={r.returncode}\n  STDERR tail: {(r.stderr or "")[-500:]}', flush=True)
print(f'\n=== DONE total {(time.time()-t0)/60:.1f} min ===')
