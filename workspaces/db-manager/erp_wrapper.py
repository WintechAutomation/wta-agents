"""wMES Django 환경에서 ERP 쿼리 실행 래퍼"""
import sys, os

# wMES backend를 sys.path에 추가
sys.path.insert(0, 'C:/wMES/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wmes.settings')

# wMES venv 경로 추가
venv_site = 'C:/wMES/wmes_env/Lib/site-packages'
if venv_site not in sys.path:
    sys.path.insert(1, venv_site)

import django
django.setup()

# 이후 실제 쿼리 모듈 실행
exec(open(sys.argv[1], encoding='utf-8').read())
