# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

html_path = r'C:\MES\wta-agents\reports\MAX\slide-cs-chatbot.html'

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the table in slide 3 with updated data
old_table = """    <table>
      <tr><th>데이터셋</th><th>청크 수</th><th>용량</th><th>상태</th></tr>
      <tr><td>CS이력 RAG</td><td><strong>265,635</strong></td><td>6.1GB</td><td><span class="tag green">완료</span></td></tr>
      <tr><td>WTA 자체 매뉴얼</td><td><strong>120,492</strong></td><td>3.1GB</td><td><span class="tag green">완료 (656/656)</span></td></tr>
      <tr><td>기술문서</td><td><strong>2,095</strong></td><td>-</td><td><span class="tag green">완료</span></td></tr>
      <tr><td>부품매뉴얼 (892개)</td><td><strong>633</strong></td><td>-</td><td><span class="tag green">완료</span></td></tr>
      <tr><td>CS이력 원본 임베딩</td><td><strong>3,318건</strong></td><td>-</td><td><span class="tag green">완료</span></td></tr>
    </table>
    <div class="box blue">
      <h4>임베딩 모델</h4>
      <p>• <strong>Qwen3-Embedding-8B</strong> (2000차원) — 한국어·영어·중국어 고성능 임베딩</p>
      <p>• PostgreSQL pgvector 기반 코사인 유사도 Top-K 검색 — 벡터 인덱스 최적화</p>
    </div>"""

new_table = """    <table>
      <tr><th>데이터셋</th><th>원본 건수</th><th>청크 수</th><th>용량</th><th>상태</th></tr>
      <tr><td><strong>부품매뉴얼</strong></td><td>1,164건</td><td><strong>265,635</strong></td><td><strong class="hl">6.0GB</strong></td><td><span class="tag green">완료</span></td></tr>
      <tr><td><strong>WTA 기술문서</strong></td><td>656건</td><td><strong>120,492</strong></td><td><strong class="hl">3.0GB</strong></td><td><span class="tag green">완료</span></td></tr>
      <tr><td><strong>CS 이력</strong></td><td>3,318건</td><td><strong>2,095</strong></td><td><strong>138MB</strong></td><td><span class="tag green">완료</span></td></tr>
    </table>
    <div class="box blue">
      <h4>임베딩 모델</h4>
      <p>• <strong>Qwen3-Embedding-8B</strong> (2000차원) — 한국어·영어·중국어 고성능 임베딩</p>
      <p>• PostgreSQL pgvector 기반 코사인 유사도 Top-K 검색 — 벡터 인덱스 최적화</p>
    </div>"""

if old_table in html:
    html = html.replace(old_table, new_table)
    print("Table replaced successfully")
else:
    print("ERROR: old table not found!")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("Done")
