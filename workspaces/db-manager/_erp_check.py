
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ['DJANGO_SETTINGS_MODULE'] = 'wmes.settings'
import django
django.setup()
from api.models import SystemConfig
config = SystemConfig.objects.get(system_type='erp')
data = config.get_config(decrypt=True)
import pyodbc

for db in ['SCMDB', 'SMSDB']:
    try:
        conn_str = 'DRIVER={SQL Server};SERVER=' + data['host'] + ',' + str(data['port']) + ';DATABASE=' + db + ';UID=' + data['username'] + ';PWD=' + data['password'] + ';Timeout=30;'
        conn = pyodbc.connect(conn_str)
        cur = conn.cursor()
        cur.execute('SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_NAME')
        rows = cur.fetchall()
        sys.stdout.write('DB=' + db + ' count=' + str(len(rows)) + '\n')
        for r in rows:
            sys.stdout.write(db + '.' + r[0] + '.' + r[1] + '\n')
        sys.stdout.flush()
        conn.close()
    except Exception as e:
        sys.stdout.write('ERR ' + db + ': ' + str(e)[:200] + '\n')
        sys.stdout.flush()
