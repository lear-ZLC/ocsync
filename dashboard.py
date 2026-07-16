#!/usr/bin/env python3
"""ConfigHub-style local UI for ocsync v3. No auth values are ever returned."""
import base64, difflib, html, importlib.machinery, importlib.util
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_loader = importlib.machinery.SourceFileLoader("ocsync", str(Path(__file__).with_name("ocsync")))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
ocsync = importlib.util.module_from_spec(_spec)
_loader.exec_module(ocsync)


def schema():
    ocsync.ensure_schema()
    ocsync.pg("ALTER TABLE ocsync_jobs ADD COLUMN IF NOT EXISTS filepaths TEXT;", fetch=False)
    ocsync.pg("CREATE TABLE IF NOT EXISTS ocsync_snapshots (id BIGSERIAL PRIMARY KEY, hostname TEXT NOT NULL, filepath TEXT NOT NULL, content TEXT NOT NULL, checksum TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), reason TEXT NOT NULL);", fetch=False)


def q(value): return ocsync.sql_quote(value)
def esc(value): return html.escape(str(value))

def hosts():
    return [r.split('|') for r in ocsync.pg("SELECT hostname, COUNT(*), COALESCE(MAX(updated_at)::text,'') FROM ocsync_configs GROUP BY hostname ORDER BY hostname;")]

def files(host):
    return [(p, v) for p, v in ocsync.parse_rows(ocsync.rows_for_host(host)).items()]

def row(host, path):
    if not ocsync.is_safe_relative(path): raise ValueError('Unsafe filepath')
    return ocsync.parse_rows(ocsync.pg("SELECT filepath, content, checksum, updated_at FROM ocsync_configs WHERE hostname="+q(host)+" AND filepath="+q(path)+"; ")).get(path)

def enqueue(source, target, profiles, auth=False, filepaths=''):
    ocsync.pg("INSERT INTO ocsync_jobs (source_hostname,target_hostname,profiles,include_auth,filepaths) VALUES ("+q(source)+","+q(target)+","+q(profiles)+","+('TRUE' if auth else 'FALSE')+","+q(filepaths)+");",fetch=False)

CSS='''*{box-sizing:border-box}body{margin:0;background:#0b1018;color:#e6edf3;font:14px Inter,system-ui,sans-serif}header{height:64px;border-bottom:1px solid #263040;display:flex;align-items:center;padding:0 22px;gap:14px;background:#101722;position:sticky;top:0}h1{font-size:18px;margin:0}.badge{color:#8bb7ff;background:#172a48;border-radius:20px;padding:4px 9px;font-size:12px}.layout{display:grid;grid-template-columns:240px 300px 1fr;min-height:calc(100vh - 64px)}aside,.files{border-right:1px solid #263040;padding:18px;background:#0e151f}.panel{padding:22px;min-width:0}.host,.file{display:block;padding:9px 10px;border-radius:7px;color:#b9c6d8;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.host:hover,.file:hover,.active{background:#1c2b40!important;color:#fff}.label{color:#7f91a9;text-transform:uppercase;letter-spacing:.08em;font-size:11px;margin:12px 0 7px}button,select,input{background:#182333;color:#e6edf3;border:1px solid #34445b;border-radius:7px;padding:9px}button{background:#2563eb;border:0;font-weight:650;cursor:pointer}button.warn{background:#be7a11}textarea{width:100%;min-height:420px;background:#0a0f17;color:#dce8f7;border:1px solid #34445b;border-radius:8px;padding:14px;font:12px ui-monospace,SFMono-Regular,monospace;line-height:1.5}pre{white-space:pre-wrap;overflow:auto;background:#090e15;border:1px solid #2b394d;border-radius:8px;padding:14px;line-height:1.5}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:16px}.muted{color:#91a1b5}.empty{color:#91a1b5;padding:50px;text-align:center}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px;border-bottom:1px solid #263040}.diff-add{color:#70d6a5}.diff-del{color:#ff9b9b}.tabs a{color:#9fb4d0;text-decoration:none;margin-right:14px}.tabs a.active{background:none;color:#fff;border-bottom:2px solid #4b8dff;padding-bottom:6px;border-radius:0}'''

def page(content, host='', path='', tab='files'):
    host_list=hosts()
    hosts_html=''.join(f'<a class="host {"active" if h[0]==host else ""}" href="/?host={esc(h[0])}"><b>{esc(h[0])}</b><br><small>{esc(h[1])} file · {esc(h[2])[:16]}</small></a>' for h in host_list)
    tree=''
    if host:
        tree=''.join(f'<a class="file {"active" if p==path else ""}" href="/?host={esc(host)}&path={esc(p)}">{esc(p)}</a>' for p,_ in files(host))
    return f'''<!doctype html><meta charset="utf-8"><title>ocsync ConfigHub</title><style>{CSS}</style><header><h1>ocsync <span class="badge">ConfigHub</span></h1><span class="muted">OpenCode / OMO configuration control plane</span></header><main class="layout"><aside><div class="label">Registered hosts</div>{hosts_html or '<div class="empty">No host</div>'}<div class="label">Security</div><small class="muted">Auth values never enter this UI. Only encrypted recipient envelopes exist in storage.</small></aside><section class="files"><div class="label">{esc(host or 'Select host')}</div>{tree or '<div class="empty">Select a host to browse its config inventory.</div>'}</section><section class="panel">{content}</section></main>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self,body,code=200):
        data=body.encode();self.send_response(code);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        schema(); qy=parse_qs(urlparse(self.path).query); host=qy.get('host',[''])[0]; path=qy.get('path',[''])[0]; compare=qy.get('compare',[''])[0]
        if not host:
            body='<h2>Config control plane</h2><p class="muted">Soldan bir host seç. Dosya ağacından config açabilir, başka hostla diff alabilir, düzenleyip snapshot oluşturabilir ve hedef agent’a seçili dosya sync işi kuyruğa koyabilirsin.</p><h3>Son sync işleri</h3>'+jobs_html()
        elif not path:
            body=f'<h2>{esc(host)}</h2><p class="muted">Soldaki envanterden bir dosya seç.</p><h3>Host snapshots</h3>'+snapshots_html(host)
        else:
            data=row(host,path)
            if not data: body='<h2>Not found</h2>'
            elif compare:
                other=row(compare,path); before=(other or {}).get('content',''); after=data['content']; diff='\n'.join(difflib.unified_diff(before.splitlines(),after.splitlines(),fromfile=compare+'/'+path,tofile=host+'/'+path,lineterm=''))
                colored='\n'.join('<span class="diff-add">'+esc(x)+'</span>' if x.startswith('+') and not x.startswith('+++') else '<span class="diff-del">'+esc(x)+'</span>' if x.startswith('-') and not x.startswith('---') else esc(x) for x in diff.splitlines())
                body=f'<div class="toolbar"><h2>{esc(path)}</h2></div><div class="tabs"><a href="/?host={esc(host)}&path={esc(path)}">Content</a><a class="active">Diff: {esc(compare)} → {esc(host)}</a></div><pre>{colored or "No difference"}</pre>'
            else:
                options=''.join(f'<option value="{esc(h[0])}">{esc(h[0])}</option>' for h in hosts() if h[0]!=host)
                body=f'''<div class="toolbar"><h2 style="margin:0">{esc(path)}</h2><span class="muted">sha256 {esc(data['checksum'])[:16]} · {esc(data['updated_at'])}</span></div><div class="toolbar"><form method="get"><input type="hidden" name="host" value="{esc(host)}"><input type="hidden" name="path" value="{esc(path)}"><select name="compare">{options}</select><button>Compare host</button></form><form method="post" action="/queue"><input type="hidden" name="source" value="{esc(host)}"><input type="hidden" name="filepath" value="{esc(path)}"><select name="target">{options}</select><button class="warn">Queue selected file sync</button></form></div><form method="post" action="/edit"><input type="hidden" name="host" value="{esc(host)}"><input type="hidden" name="path" value="{esc(path)}"><textarea name="content">{esc(data['content'])}</textarea><div class="toolbar"><button>Save snapshot + update source config</button><span class="muted">Saves a rollback snapshot first. Changes source snapshot only; sync remains explicit.</span></div></form><h3>History</h3>{snapshots_html(host,path)}'''
        self.send(page(body,host,path))
    def do_POST(self):
        schema(); form=parse_qs(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode()); action=urlparse(self.path).path
        try:
            if action=='/edit':
                host,path,content=form['host'][0],form['path'][0],form['content'][0]; old=row(host,path)
                if not old: raise ValueError('File missing')
                ocsync.pg("INSERT INTO ocsync_snapshots (hostname,filepath,content,checksum,reason) VALUES ("+q(host)+","+q(path)+","+q(base64.b64encode(old['content'].encode()).decode())+","+q(old['checksum'])+",'dashboard edit');",fetch=False)
                ocsync.upsert_config(host,path,content); dest='/?host='+host+'&path='+path
            elif action=='/queue':
                source,target,path=form['source'][0],form['target'][0],form['filepath'][0]
                if source==target: raise ValueError('Source and target must differ')
                enqueue(source,target,'selected',False,path); dest='/?host='+source+'&path='+path
            elif action=='/rollback':
                host,path,sid=form['host'][0],form['path'][0],int(form['snapshot'][0]); r=ocsync.pg('SELECT content FROM ocsync_snapshots WHERE id='+str(sid)+' AND hostname='+q(host)+' AND filepath='+q(path)+';')[0]; ocsync.upsert_config(host,path,base64.b64decode(r).decode());dest='/?host='+host+'&path='+path
            else: raise ValueError('Unknown action')
            self.send_response(303);self.send_header('Location',dest);self.end_headers()
        except Exception as e: self.send(page('<h2>Error</h2><pre>'+esc(e)+'</pre>'),400)

def snapshots_html(host,path=None):
    where='hostname='+q(host)+((' AND filepath='+q(path)) if path else '')
    rows=ocsync.pg('SELECT id,filepath,created_at::text,reason FROM ocsync_snapshots WHERE '+where+' ORDER BY id DESC LIMIT 15;')
    if not rows:return '<p class="muted">No snapshots yet.</p>'
    body='<table><tr><th>ID</th><th>File</th><th>When</th><th>Reason</th><th></th></tr>'
    for r in rows:
        a=r.split('|',3); action=(f'<form method="post" action="/rollback"><input type="hidden" name="host" value="{esc(host)}"><input type="hidden" name="path" value="{esc(a[1])}"><input type="hidden" name="snapshot" value="{esc(a[0])}"><button class="warn">Rollback</button></form>' if path else '')
        body+=f'<tr><td>{esc(a[0])}</td><td>{esc(a[1])}</td><td>{esc(a[2])}</td><td>{esc(a[3])}</td><td>{action}</td></tr>'
    return body+'</table>'
def jobs_html():
    rows=ocsync.pg("SELECT id,source_hostname,target_hostname,profiles,COALESCE(filepaths,''),status,created_at::text,COALESCE(result,'') FROM ocsync_jobs ORDER BY id DESC LIMIT 20;")
    if not rows:return '<p class="muted">No queued jobs.</p>'
    out='<table><tr><th>ID</th><th>Flow</th><th>Scope</th><th>Status</th><th>Created</th><th>Result</th></tr>'
    for r in rows:
        a=r.split('|',7);out+=f'<tr><td>{esc(a[0])}</td><td>{esc(a[1])} → {esc(a[2])}</td><td>{esc(a[4] or a[3])}</td><td>{esc(a[5])}</td><td>{esc(a[6])}</td><td>{esc(a[7])}</td></tr>'
    return out+'</table>'
def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8787);a=p.parse_args();schema();print(f'ocsync ConfigHub: http://{a.host}:{a.port}');ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
if __name__=='__main__':main()
