"""upload-server.py — WTA secure file share server.

UUID-based file sharing: upload -> unique link -> download (repeatable).
No file listing. Only link holders can access.
Files persist until server restart.
Cloudflare tunnel (port 8080) serves this externally.

Usage:
  py scripts/upload-server.py
  py scripts/upload-server.py --port 8080
"""

import argparse
import os
import sys
import json
import uuid
import mimetypes
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, quote

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 파일 레지스트리: {uuid: {filename, path, size, created}}
# 메모리 기반 — 서버 재시작 시 초기화
file_registry: dict[str, dict] = {}


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WTA &#xD30C;&#xC77C; &#xACF5;&#xC720;</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Malgun Gothic',sans-serif;background:#f5f7fa;color:#333;min-height:100vh;display:flex;flex-direction:column;align-items:center}

.header{width:100%;background:#fff;border-bottom:1px solid #e5e7eb;padding:20px 0;text-align:center}
.header h1{font-size:22px;color:#1f2937;font-weight:700}

.main{width:100%;max-width:560px;padding:28px 16px;flex:1}

.drop-zone{border:2px dashed #d1d5db;border-radius:14px;padding:44px 20px;text-align:center;cursor:pointer;transition:all 0.2s;background:#fff}
.drop-zone:hover,.drop-zone.dragover{border-color:#3b82f6;background:#eff6ff}
.drop-zone .icon{font-size:40px;margin-bottom:10px}
.drop-zone p{color:#6b7280;font-size:14px;line-height:1.7}
.drop-zone .browse{color:#3b82f6;cursor:pointer;font-weight:600}
input[type="file"]{display:none}

.progress-wrap{margin-top:14px;display:none}
.progress-bar{width:100%;height:4px;background:#e5e7eb;border-radius:2px;overflow:hidden}
.progress-bar .fill{height:100%;background:#3b82f6;border-radius:2px;transition:width 0.3s;width:0%}
.progress-text{text-align:center;font-size:12px;color:#9ca3af;margin-top:5px}

.upload-results{margin-top:18px}
.result-card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px;margin-bottom:8px;animation:fadeIn 0.3s}
.result-card.error{border-color:#fca5a5;background:#fef2f2}
.result-header{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.result-header .name{flex:1;word-break:break-all;color:#374151;font-size:14px;font-weight:500}
.result-header .meta{color:#9ca3af;font-size:12px;white-space:nowrap}
.result-link{display:block;background:#f0f7ff;border:1px solid #bfdbfe;border-radius:8px;padding:10px 12px;font-size:11px;color:#2563eb;word-break:break-all;font-family:monospace;cursor:pointer;transition:background 0.15s;position:relative}
.result-link:hover{background:#dbeafe}
.result-link .copy-hint{position:absolute;right:10px;top:50%;transform:translateY(-50%);color:#93c5fd;font-size:11px;font-family:-apple-system,sans-serif}

.footer{text-align:center;padding:16px;color:#d1d5db;font-size:11px}

.copied-toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#065f46;color:#a7f3d0;padding:8px 20px;border-radius:8px;font-size:13px;opacity:0;transition:opacity 0.3s;pointer-events:none;z-index:100}
.copied-toast.show{opacity:1}

@keyframes fadeIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:600px){
  .main{padding:20px 10px}
  .drop-zone{padding:32px 16px}
  .header h1{font-size:19px}
}
</style>
</head>
<body>

<div class="header">
  <h1>WTA &#xD30C;&#xC77C; &#xACF5;&#xC720;</h1>
</div>

<div class="main">
  <div class="drop-zone" id="dropZone">
    <div class="icon">&#x1F4C1;</div>
    <p>&#xD30C;&#xC77C;&#xC744; &#xC5EC;&#xAE30;&#xB85C; &#xB4DC;&#xB798;&#xADF8;&#xD558;&#xC138;&#xC694;<br>&#xB610;&#xB294; <span class="browse">&#xD30C;&#xC77C; &#xC120;&#xD0DD;</span></p>
  </div>
  <input type="file" id="fileInput" multiple>
  <div class="progress-wrap" id="progressWrap">
    <div class="progress-bar"><div class="fill" id="progressFill"></div></div>
    <div class="progress-text" id="progressText"></div>
  </div>
  <div class="upload-results" id="results"></div>
</div>

<div class="footer">&copy; 2026 (&#xC8FC;)&#xC708;&#xD14D;&#xC624;&#xD1A0;&#xBA54;&#xC774;&#xC158;</div>
<div class="copied-toast" id="copiedToast">&#x2705; &#xB9C1;&#xD06C; &#xBCF5;&#xC0AC; &#xC644;&#xB8CC;</div>

<script>
const dropZone=document.getElementById('dropZone');
const fileInput=document.getElementById('fileInput');
const progressWrap=document.getElementById('progressWrap');
const progressFill=document.getElementById('progressFill');
const progressText=document.getElementById('progressText');
const results=document.getElementById('results');

dropZone.addEventListener('click',()=>fileInput.click());
dropZone.addEventListener('dragover',e=>{e.preventDefault();dropZone.classList.add('dragover')});
dropZone.addEventListener('dragleave',()=>dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop',e=>{
  e.preventDefault();dropZone.classList.remove('dragover');
  handleFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change',()=>{handleFiles(fileInput.files);fileInput.value=''});

function fmtSize(b){
  if(b<1024)return b+' B';
  if(b<1048576)return(b/1024).toFixed(1)+' KB';
  if(b<1073741824)return(b/1048576).toFixed(1)+' MB';
  return(b/1073741824).toFixed(1)+' GB';
}

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

function copyLink(url){
  navigator.clipboard.writeText(url).then(()=>{
    showToast();
  }).catch(()=>{
    const ta=document.createElement('textarea');
    ta.value=url;document.body.appendChild(ta);ta.select();
    document.execCommand('copy');document.body.removeChild(ta);
    showToast();
  });
}

function showToast(){
  const toast=document.getElementById('copiedToast');
  toast.classList.add('show');
  setTimeout(()=>toast.classList.remove('show'),1500);
}

async function handleFiles(files){
  for(const file of files){
    progressWrap.style.display='block';
    progressFill.style.width='0%';
    progressText.textContent=file.name+' \uC5C5\uB85C\uB4DC \uC911...';

    const formData=new FormData();
    formData.append('file',file);

    try{
      const resp=await new Promise((resolve,reject)=>{
        const xhr=new XMLHttpRequest();
        xhr.open('POST','/upload');
        xhr.upload.onprogress=e=>{
          if(e.lengthComputable){
            const pct=Math.round(e.loaded/e.total*100);
            progressFill.style.width=pct+'%';
            progressText.textContent=file.name+' \uC5C5\uB85C\uB4DC \uC911... '+pct+'%';
          }
        };
        xhr.onload=()=>resolve(xhr);
        xhr.onerror=()=>reject(new Error('\uB124\uD2B8\uC6CC\uD06C \uC624\uB958'));
        xhr.send(formData);
      });

      progressFill.style.width='100%';

      if(resp.status===200){
        const data=JSON.parse(resp.responseText);
        const dlUrl=location.origin+'/api/files/'+data.id+'/'+encodeURIComponent(data.filename);

        results.innerHTML='<div class="result-card">'
          +'<div class="result-header">'
          +'<span class="name">&#x2705; '+esc(data.filename)+'</span>'
          +'<span class="meta">'+fmtSize(data.size)+'</span>'
          +'</div>'
          +'<div class="result-link" onclick="copyLink(\''+dlUrl.replace(/'/g,"\\'")+'\')" title="\uD074\uB9AD\uD558\uC5EC \uBCF5\uC0AC">'
          +esc(dlUrl)
          +'<span class="copy-hint">\uBCF5\uC0AC</span>'
          +'</div>'
          +'</div>'+results.innerHTML;
      }else{
        results.innerHTML='<div class="result-card error">'
          +'<div class="result-header">'
          +'<span class="name">&#x274C; '+esc(file.name)+' \u2014 \uC5C5\uB85C\uB4DC \uC2E4\uD328</span>'
          +'</div></div>'+results.innerHTML;
      }
    }catch(err){
      results.innerHTML='<div class="result-card error">'
        +'<div class="result-header">'
        +'<span class="name">&#x274C; '+esc(file.name)+' \u2014 '+esc(err.message)+'</span>'
        +'</div></div>'+results.innerHTML;
    }

    setTimeout(()=>{progressWrap.style.display='none'},600);
  }
}
</script>
</body>
</html>"""


class UploadHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[share] {ts} {args[0]}")

    def do_GET(self):
        if self.path.startswith("/api/files/"):
            self._serve_download()
        elif self.path.startswith("/assets/"):
            self._serve_asset()
        elif self._try_serve_static_page():
            pass  # 정적 HTML 파일 서빙 완료
        else:
            self._serve_html()

    def _serve_asset(self):
        """reports/ 하위 정적 에셋(이미지 등) 서빙. /assets/MAX/template-images/img.jpeg"""
        clean = self.path[len("/assets/"):].split("?")[0]
        if ".." in clean:
            self.send_error(403)
            return
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
        fpath = os.path.join(reports_dir, clean)
        if not os.path.isfile(fpath):
            self.send_error(404)
            return
        ext = os.path.splitext(fpath)[1].lower()
        ct_map = {".jpeg": "image/jpeg", ".jpg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".svg": "image/svg+xml", ".css": "text/css", ".js": "application/javascript"}
        ct = ct_map.get(ext, "application/octet-stream")
        try:
            with open(fpath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_error(500)

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        else:
            self.send_error(404)

    def _try_serve_static_page(self):
        """reports/ 폴더의 정적 HTML 파일 서빙. 성공 시 True 반환."""
        # /pagename → reports/pagename.html 또는 reports/*/pagename.html
        clean = self.path.strip("/").split("?")[0]
        if not clean:
            return False
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
        # 직접 매치: reports/{clean}.html
        html_path = os.path.join(reports_dir, f"{clean}.html")
        if not os.path.isfile(html_path):
            # 하위 폴더 탐색: reports/*/{clean}.html
            for sub in os.listdir(reports_dir):
                candidate = os.path.join(reports_dir, sub, f"{clean}.html")
                if os.path.isfile(candidate):
                    html_path = candidate
                    break
            else:
                return False
        try:
            with open(html_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return True
        except Exception:
            return False

    def _serve_html(self):
        data = HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_download(self):
        # /api/files/<uuid>/<filename>
        path_part = self.path[len("/api/files/"):]
        parts = path_part.split("/", 1)
        if not parts:
            self.send_error(404, "Invalid link")
            return

        file_id = parts[0]
        info = file_registry.get(file_id)

        if not info:
            self._serve_expired_page()
            return

        fpath = info["path"]
        filename = info["filename"]

        if not os.path.isfile(fpath):
            file_registry.pop(file_id, None)
            self._serve_expired_page()
            return

        stat = os.stat(fpath)
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(stat.st_size))
        safe_name = quote(filename, safe="")
        self.send_header(
            "Content-Disposition",
            f"attachment; filename*=UTF-8''{safe_name}",
        )
        self.end_headers()

        with open(fpath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

        print(f"[share] Downloaded: {filename} ({file_id[:8]})")

    def _serve_expired_page(self):
        html = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>&#xD30C;&#xC77C; &#xC5C6;&#xC74C;</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#f5f7fa;color:#333;min-height:100vh;display:flex;align-items:center;justify-content:center}
.box{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:40px;text-align:center;max-width:360px}
.box .icon{font-size:40px;margin-bottom:14px}
.box h2{color:#1f2937;margin-bottom:8px;font-size:18px}
.box p{color:#6b7280;font-size:14px;line-height:1.6;margin-bottom:20px}
.box a{color:#3b82f6;font-size:14px}
</style></head><body>
<div class="box">
<div class="icon">&#x26A0;&#xFE0F;</div>
<h2>&#xD30C;&#xC77C;&#xC744; &#xCC3E;&#xC744; &#xC218; &#xC5C6;&#xC2B5;&#xB2C8;&#xB2E4;</h2>
<p>&#xC720;&#xD6A8;&#xD558;&#xC9C0; &#xC54A;&#xC740; &#xB9C1;&#xD06C;&#xC774;&#xAC70;&#xB098;<br>&#xD30C;&#xC77C;&#xC774; &#xC0AD;&#xC81C;&#xB418;&#xC5C8;&#xC2B5;&#xB2C8;&#xB2E4;.</p>
<a href="/">&#x2190; &#xBA54;&#xC778;&#xC73C;&#xB85C;</a>
</div></body></html>"""
        data = html.encode("utf-8")
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error(400, "multipart/form-data required")
            return

        boundary = content_type.split("boundary=")[1].strip()
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        parts = body.split(f"--{boundary}".encode())
        for part in parts:
            if b"filename=" not in part:
                continue

            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            header_section = part[:header_end].decode("utf-8", errors="replace")
            file_data = part[header_end + 4:]
            if file_data.endswith(b"\r\n"):
                file_data = file_data[:-2]

            # extract filename
            filename = ""
            for line in header_section.split("\r\n"):
                if "filename=" in line:
                    if "filename*=" in line:
                        idx = line.index("filename*=")
                        encoded = line[idx + 10:].split(";")[0].strip().strip('"')
                        if encoded.lower().startswith("utf-8''"):
                            filename = unquote(encoded.split("''", 1)[1])
                    if not filename and 'filename="' in line:
                        start = line.index('filename="') + 10
                        end = line.index('"', start)
                        filename = line[start:end]

            if not filename:
                filename = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # UUID 기반 저장
            file_id = str(uuid.uuid4())
            file_dir = os.path.join(UPLOAD_DIR, file_id)
            os.makedirs(file_dir, exist_ok=True)
            save_path = os.path.join(file_dir, filename)

            with open(save_path, "wb") as f:
                f.write(file_data)

            file_size = len(file_data)

            # 레지스트리 등록
            file_registry[file_id] = {
                "filename": filename,
                "path": save_path,
                "size": file_size,
                "created": datetime.now().isoformat(),
            }

            print(f"[share] Uploaded: {filename} ({file_size / 1024:.0f} KB) -> {file_id[:8]}")

            resp = json.dumps(
                {"id": file_id, "filename": filename, "size": file_size},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            return

        self.send_error(400, "No file found")


def main():
    parser = argparse.ArgumentParser(description="WTA Secure File Share Server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), UploadHandler)
    print(f"[share] WTA File Share started: http://{args.host}:{args.port}")
    print(f"[share] Upload dir: {UPLOAD_DIR}")
    print(f"[share] UUID-based private sharing (no file listing)")
    print(f"[share] Files persist until server restart")
    print(f"[share] Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[share] Server stopped")
        server.server_close()


if __name__ == "__main__":
    main()
