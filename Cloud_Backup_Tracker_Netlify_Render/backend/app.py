import os, sqlite3, uuid
from functools import wraps
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

app=Flask(__name__)
app.config["SECRET_KEY"]=os.environ.get("SECRET_KEY","change-me-before-deploy")
app.config["MAX_CONTENT_LENGTH"]=100*1024*1024
CORS(app, resources={r"/api/*":{"origins":os.environ.get("FRONTEND_ORIGIN","*")}},
     allow_headers=["Content-Type","Authorization"], expose_headers=["Content-Disposition"])
DB=os.environ.get("DATABASE_PATH","cloud_backup_tracker.db")
STORE=os.environ.get("STORAGE_PATH","backup_storage")
os.makedirs(os.path.dirname(DB) or ".",exist_ok=True); os.makedirs(STORE,exist_ok=True)
signer=URLSafeTimedSerializer(app.config["SECRET_KEY"],salt="cbt")
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with db() as c:
 c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,password TEXT)")
 c.execute("""CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY,user_id INTEGER,name TEXT,stored TEXT,type TEXT,size INTEGER,date TEXT)""")
def auth(fn):
 @wraps(fn)
 def wrap(*a,**kw):
  try:
   tok=request.headers.get("Authorization","").removeprefix("Bearer ")
   uid=signer.loads(tok,max_age=604800)["uid"]
   with db() as c: u=c.execute("SELECT id,name,email FROM users WHERE id=?",(uid,)).fetchone()
   if not u: raise ValueError()
  except Exception: return jsonify(error="Please log in again."),401
  return fn(u,*a,**kw)
 return wrap
def tok(uid): return signer.dumps({"uid":uid})
def public(u): return {"id":u["id"],"name":u["name"],"email":u["email"]}
def listfiles(uid):
 with db() as c: rows=c.execute("SELECT * FROM files WHERE user_id=? ORDER BY id DESC",(uid,)).fetchall()
 return [{"id":r["id"],"name":r["name"],"type":r["type"],"size":r["size"],"date":r["date"]} for r in rows]
@app.get("/api/health")
def health(): return jsonify(ok=True,service="Cloud Backup Tracker API")
@app.post("/api/signup")
def signup():
 d=request.get_json() or {}; name=str(d.get("name","")).strip(); email=str(d.get("email","")).strip().lower(); pw=str(d.get("password",""))
 if not name or "@" not in email or len(pw)<6: return jsonify(error="Enter name, valid email, and password of 6+ characters."),400
 try:
  with db() as c: cur=c.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",(name,email,generate_password_hash(pw))); uid=cur.lastrowid
 except sqlite3.IntegrityError: return jsonify(error="Email already registered."),409
 return jsonify(token=tok(uid),user={"id":uid,"name":name,"email":email}),201
@app.post("/api/login")
def login():
 d=request.get_json() or {}; email=str(d.get("email","")).strip().lower()
 with db() as c: u=c.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
 if not u or not check_password_hash(u["password"],str(d.get("password",""))): return jsonify(error="Incorrect email or password."),401
 return jsonify(token=tok(u["id"]),user=public(u))
@app.get("/api/me")
@auth
def me(u): return jsonify(user=public(u))
@app.patch("/api/me")
@auth
def rename(u):
 name=str((request.get_json() or {}).get("name","")).strip()
 if not name:return jsonify(error="Name is required."),400
 with db() as c:c.execute("UPDATE users SET name=? WHERE id=?",(name,u["id"])); v=c.execute("SELECT id,name,email FROM users WHERE id=?",(u["id"],)).fetchone()
 return jsonify(user=public(v))
@app.get("/api/files")
@auth
def files(u):
 fs=listfiles(u["id"]); return jsonify(files=fs,count=len(fs),total_size=sum(x["size"] for x in fs),quota_bytes=2*1024**3)
@app.post("/api/upload")
@auth
def upload(u):
 items=[f for f in request.files.getlist("files") if f and f.filename]
 if not items:return jsonify(error="Choose files first."),400
 n=0
 for f in items:
  name=secure_filename(f.filename)
  if not name:continue
  stored=uuid.uuid4().hex+"_"+name; path=os.path.join(STORE,stored); f.save(path); size=os.path.getsize(path)
  with db() as c:c.execute("INSERT INTO files(user_id,name,stored,type,size,date) VALUES(?,?,?,?,?,?)",(u["id"],name,stored,(os.path.splitext(name)[1].lstrip(".") or "file").upper(),size,datetime.now().strftime("%Y-%m-%d %H:%M")))
  n+=1
 return jsonify(message=f"{n} file(s) backed up."),201
@app.get("/api/download/<int:fid>")
@auth
def download(u,fid):
 with db() as c:r=c.execute("SELECT * FROM files WHERE id=? AND user_id=?",(fid,u["id"])).fetchone()
 if not r or not os.path.isfile(os.path.join(STORE,r["stored"])):return jsonify(error="File not found."),404
 return send_from_directory(STORE,r["stored"],as_attachment=True,download_name=r["name"])
@app.delete("/api/files/<int:fid>")
@auth
def delete(u,fid):
 with db() as c:r=c.execute("SELECT * FROM files WHERE id=? AND user_id=?",(fid,u["id"])).fetchone()
 if not r:return jsonify(error="File not found."),404
 p=os.path.join(STORE,r["stored"])
 if os.path.isfile(p):os.remove(p)
 with db() as c:c.execute("DELETE FROM files WHERE id=? AND user_id=?",(fid,u["id"]))
 return jsonify(message="Backup deleted.")
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
