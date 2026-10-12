import os, json, sqlite3, uuid, base64, secrets, smtplib
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import requests

load_dotenv()
BASE = Path(__file__).resolve().parent
DB = BASE / 'ngenoai.db'
UPLOADS = BASE / 'static' / 'uploads'
UPLOADS.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.secret_key = os.getenv('NGENO_SECRET_KEY', 'change-this-secret-key-in-production')
app.config['JSON_SORT_KEYS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.5')
IMAGE_MODEL = os.getenv('OPENAI_IMAGE_MODEL', 'gpt-image-2.5-flare')
WEB_SEARCH = os.getenv('OPENAI_WEB_SEARCH_ENABLED', 'true').lower() == 'true'
GERMAN_SYLLABUS_URL = 'https://www.nied.edu.na/assets/documents/02Syllabuses/05SeniorSecondary/GermanForeignLanguage/NSSCO_Syllabuses_FO-GE_Aug2008.pdf'
GERMAN_SYLLABUS_SUMMARY = 'NSSCO German Foreign Language, Ordinary Level, Grades 11-12, syllabus code 4121. Learning content covers listening, reading, productive writing, grammar/usage and speaking; assessment includes listening, reading/writing and speaking.'
DEMO_MODE = os.getenv('NGENO_DEMO_MODE','true').lower()=='true'

SUBJECTS = [
 ('Mathematics','math','∑'),('Physical Science','science','⚛'),('Physics','physics','⚡'),('Chemistry','chemistry','🧪'),('Biology','biology','🧬'),('Life Science','biology','🫀'),('Environmental Science','environment','🌿'),('Agricultural Science','agriculture','🌱'),
 ('Geography','geography','🌍'),('History','history','⌛'),('Development Studies','humanities','📈'),('Social Studies','humanities','👥'),('Religious Studies','humanities','☀'),('Government','civics','🏛'),('Civics','civics','⚖'),
 ('English','english','Aa'),('Oshindonga','language','文'),('Oshikwanyama','language','文'),('Afrikaans','language','A'),('Otjiherero','language','文'),('Khoekhoegowab','language','文'),('Rukwangali','language','文'),('Silozi','language','文'),('Thimbukushu','language','文'),('Other supported Namibian language','language','文'),
 ('Accounting','business','₮'),('Economics','business','₿'),('Business Studies','business','▤'),('Entrepreneurship','business','↗'),('Commerce','business','▥'),
 ('Computer Science','computer','</>'),('Information Technology','computer','⌘'),('Programming','computer','{}'),('Design & Technology','technology','◈'),('Engineering-related subjects','technology','⚙'),
 ('Art','creative','✦'),('Music','creative','♫'),('Drama','creative','◉'),('Design','creative','◇'),('Home Economics','practical','⌂'),('Hospitality','practical','♨'),('Food and Nutrition','practical','◌'),('Fashion and Clothing','practical','✂'),('Technical subjects','practical','⚒'),('Other Subject','other','＋')
]

SYSTEM = '''You are NgenoAI 🇳🇦, a professional educational AI for secondary-school learners in Namibia. Prioritize Namibian curriculum context, NSSCO and NSSCAS when relevant, and use simple clear English. Adapt to the learner profile. Give step-by-step solutions, examples, revision notes, exam techniques, quizzes and study plans. Respect exam command words such as describe, explain, discuss, compare and evaluate. Never invent facts, dates, statistics, translations, sources or official examination rules. If information is uncertain or may be outdated, say so. For German NSSCO, use the NIED syllabus source supplied by the platform when relevant and distinguish it from AI-generated practice. For Namibian languages, never pretend a translation is reliable when you are uncertain. Distinguish official past-paper material from AI-generated practice. Be encouraging, concise when appropriate, and educational rather than doing dishonest academic work for the learner.'''

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init_db():
    c = conn()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, email TEXT UNIQUE, password TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY, name TEXT, grade TEXT, school TEXT, exam TEXT, subjects TEXT, language TEXT, goals TEXT, difficulty TEXT, picture TEXT, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, messages TEXT, created_at TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS quizzes(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject TEXT, score INTEGER, total INTEGER, created_at TEXT);
    CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS translations(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_lang TEXT, target_lang TEXT, source TEXT, result TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS saved_images(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, prompt TEXT, image TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS topics(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject TEXT, topic TEXT, completed INTEGER DEFAULT 0, created_at TEXT);
    CREATE TABLE IF NOT EXISTS verification_tokens(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, token TEXT UNIQUE, expires_at TEXT, used INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS university_profiles(user_id INTEGER PRIMARY KEY, institution TEXT, student_number TEXT, programme TEXT, year_level TEXT, faculty TEXT, semester TEXT, gpa TEXT, credits TEXT, timetable TEXT, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS university_courses(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, code TEXT, name TEXT, lecturer TEXT, credits INTEGER DEFAULT 0, mark REAL DEFAULT 0, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS university_tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, course_code TEXT, title TEXT, due_date TEXT, status TEXT DEFAULT 'Pending', FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS university_announcements(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, body TEXT, created_at TEXT, FOREIGN KEY(user_id) REFERENCES users(id));
    ''')
    cols=[r[1] for r in c.execute('PRAGMA table_info(users)').fetchall()]
    if 'verified' not in cols: c.execute('ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0')
    c.commit(); c.close()

def current_user():
    uid = session.get('user_id')
    if not uid: return None
    c=conn(); u=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); c.close(); return u

def profile_for(uid):
    c=conn(); p=c.execute('SELECT * FROM profiles WHERE user_id=?',(uid,)).fetchone(); c.close()
    if not p: return {}
    d=dict(p); d['subjects']=json.loads(d['subjects'] or '[]'); return d

def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not current_user(): return jsonify(error='Please log in first.'),401
        return fn(*a,**kw)
    return wrapper

def call_openai(messages, web=False, json_mode=False):
    if not OPENAI_API_KEY: return None,'OpenAI API key is not configured. Add OPENAI_API_KEY to your .env file.'
    payload={'model':OPENAI_MODEL,'input':[{'role':'system','content':SYSTEM},*messages]}
    if web and WEB_SEARCH: payload['tools']=[{'type':'web_search'}]
    if json_mode: payload['text']={'format':{'type':'json_object'}}
    try:
        r=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':f'Bearer {OPENAI_API_KEY}','Content-Type':'application/json'},json=payload,timeout=120)
        if not r.ok: return None,r.text[:1500]
        d=r.json(); text=d.get('output_text','')
        if not text:
            parts=[]
            for item in d.get('output',[]):
                for part in item.get('content',[]):
                    if part.get('type') in ('output_text','text'): parts.append(part.get('text',''))
            text='\n'.join(parts).strip()
        return text or 'I could not generate an answer.',None
    except Exception as e: return None,str(e)

def send_email(to_email, subject, html, text=None):
    host=os.getenv('EMAIL_HOST','').strip(); username=os.getenv('EMAIL_USERNAME','').strip(); password=os.getenv('EMAIL_PASSWORD',''); port=int(os.getenv('EMAIL_PORT','587')); sender=os.getenv('EMAIL_FROM', username or 'no-reply@ngenoai.local')
    if not host or not to_email:
        return False, 'Email provider is not configured.'
    msg=EmailMessage(); msg['Subject']=subject; msg['From']=sender; msg['To']=to_email; msg.set_content(text or 'Please open this message in an HTML-capable email client.'); msg.add_alternative(html,'html')
    try:
        with smtplib.SMTP(host,port,timeout=20) as smtp:
            smtp.starttls();
            if username: smtp.login(username,password)
            smtp.send_message(msg)
        return True,None
    except Exception as e:
        return False,str(e)

def make_verification_email(name, token):
    base=os.getenv('PUBLIC_BASE_URL','http://127.0.0.1:5000').rstrip('/')
    link=f'{base}/verify-email/{token}'
    html=f'''<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;padding:32px"><h1 style="color:#003580">NgenoAI 🇳🇦</h1><h2>Welcome, {name}!</h2><p>Your AI learning journey starts now.</p><p>Verify your email to activate your NgenoAI account.</p><p><a href="{link}" style="background:#003580;color:#fff;padding:12px 18px;border-radius:10px;text-decoration:none">Verify my email</a></p><p>Learn Namibia. Understand More. Achieve More.</p></div>'''
    return html, link

def add_activity(uid, text):
    c=conn(); c.execute('INSERT INTO activity(user_id,text,created_at) VALUES(?,?,?)',(uid,text,datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close()

@app.get('/')
def home(): return render_template('index.html')

@app.get('/api/me')
def me():
    u=current_user()
    if not u: return jsonify(authenticated=False)
    return jsonify(authenticated=True,user={'id':u['id'],'username':u['username'],'email':u['email']},profile=profile_for(u['id']))

@app.post('/api/register')
def register():
    d=request.get_json() or {}; username=(d.get('username') or d.get('email','').split('@')[0]).strip(); email=d.get('email','').strip().lower(); password=d.get('password','')
    first=(d.get('first_name') or d.get('name') or username).strip(); last=(d.get('last_name') or '').strip(); mode=d.get('mode','secondary')
    if len(username)<2 or '@' not in email or len(password)<8: return jsonify(error='Enter a valid email and a password of at least 8 characters.'),400
    c=conn()
    try:
        cur=c.execute('INSERT INTO users(username,email,password,created_at) VALUES(?,?,?,?)',(username,email,generate_password_hash(password),datetime.now().isoformat(timespec='seconds'))); uid=cur.lastrowid
        c.execute('INSERT INTO profiles(user_id,name,grade,school,exam,subjects,language,goals,difficulty,picture) VALUES(?,?,?,?,?,?,?,?,?,?)',(uid,f'{first} {last}'.strip(),d.get('grade','Grade 10'),d.get('school',''),d.get('exam','NSSCO'),json.dumps(d.get('subjects',[])),d.get('language','English'),d.get('goals',''),'Intermediate',''))
        c.execute('INSERT INTO university_profiles(user_id,institution,student_number,programme,year_level,faculty,semester,gpa,credits,timetable) VALUES(?,?,?,?,?,?,?,?,?,?)',(uid,d.get('institution',''),d.get('student_number',''),d.get('programme',''),d.get('year_level',''),d.get('faculty',''),d.get('semester',''),'', '0',''))
        token=secrets.token_urlsafe(32); c.execute('INSERT INTO verification_tokens(user_id,token,expires_at) VALUES(?,?,?)',(uid,token,(datetime.now()+timedelta(hours=24)).isoformat()))
        c.commit(); session['user_id']=uid
    except sqlite3.IntegrityError:
        c.close(); return jsonify(error='That username or email is already registered.'),409
    c.close()
    html,link=make_verification_email(first,token); sent,err=send_email(email,'Welcome to NgenoAI 🇳🇦 — Verify your email',html,f'Welcome to NgenoAI. Verify your email: {link}')
    add_activity(uid,'Account created')
    return jsonify(ok=True,email_sent=sent,verification_link=(link if not sent else None),email_error=err,mode=mode)

@app.get('/verify-email/<token>')
def verify_email(token):
    c=conn(); row=c.execute('SELECT * FROM verification_tokens WHERE token=? AND used=0',(token,)).fetchone()
    if not row or datetime.fromisoformat(row['expires_at']) < datetime.now(): c.close(); return '<h2>NgenoAI</h2><p>This verification link is invalid or expired.</p>',400
    c.execute('UPDATE verification_tokens SET used=1 WHERE id=?',(row['id'],)); c.execute('UPDATE users SET verified=1 WHERE id=?',(row['user_id'],)) if 'verified' in [x[1] for x in c.execute('PRAGMA table_info(users)').fetchall()] else None; c.commit(); c.close(); return redirect('/')

@app.post('/api/login')
def login():
    d=request.get_json() or {}; identity=d.get('identity','').strip().lower(); password=d.get('password','')
    c=conn(); u=c.execute('SELECT * FROM users WHERE lower(email)=? OR lower(username)=?',(identity,identity)).fetchone(); c.close()
    if not u or not check_password_hash(u['password'],password): return jsonify(error='Incorrect login details.'),401
    if not DEMO_MODE and not u['verified']: return jsonify(error='Please verify your email before signing in.'),403
    session['user_id']=u['id']; return jsonify(ok=True)

@app.post('/api/forgot-password')
def forgot_password():
    d=request.get_json() or {}; email=d.get('email','').strip().lower(); c=conn(); u=c.execute('SELECT * FROM users WHERE lower(email)=?',(email,)).fetchone()
    if not u: c.close(); return jsonify(ok=True,message='If the account exists, reset instructions have been sent.')
    token=secrets.token_urlsafe(32); c.execute('INSERT INTO verification_tokens(user_id,token,expires_at) VALUES(?,?,?)',(u['id'],token,(datetime.now()+timedelta(hours=1)).isoformat())); c.commit(); c.close()
    base=os.getenv('PUBLIC_BASE_URL','http://127.0.0.1:5000').rstrip('/'); link=f'{base}/reset-password/{token}'
    html=f'<div style="font-family:Arial;padding:30px"><h1>NgenoAI 🇳🇦</h1><p>Password reset requested for your account.</p><p><a href="{link}">Reset password</a></p><p>This link expires in one hour.</p></div>'
    sent,err=send_email(email,'NgenoAI — Password reset',html,f'Reset your password: {link}')
    return jsonify(ok=True,email_sent=sent,reset_link=(link if not sent else None),email_error=err)

@app.post('/api/logout')
def logout(): session.clear(); return jsonify(ok=True)

@app.post('/api/profile')
@login_required
def save_profile():
    uid=current_user()['id']; d=request.get_json() or {}; subjects=d.get('subjects',[])
    if isinstance(subjects,str): subjects=[x.strip() for x in subjects.split(',') if x.strip()]
    c=conn(); c.execute('''UPDATE profiles SET name=?,grade=?,school=?,exam=?,subjects=?,language=?,goals=?,difficulty=?,picture=? WHERE user_id=?''',(d.get('name',''),d.get('grade','Grade 10'),d.get('school',''),d.get('exam','NSSCO'),json.dumps(subjects),d.get('language','English'),d.get('goals',''),d.get('difficulty','Intermediate'),d.get('picture',''),uid)); c.commit(); c.close(); add_activity(uid,'Updated learner profile'); return jsonify(ok=True,profile=profile_for(uid))

@app.get('/api/subjects')
def subjects(): return jsonify(subjects=[{'name':n,'slug':s,'icon':i} for n,s,i in SUBJECTS])

@app.post('/api/chat')
@login_required
def chat():
    d=request.get_json() or {}; msgs=d.get('messages',[]); profile=profile_for(current_user()['id'])
    if not msgs: return jsonify(error='No messages supplied'),400
    note={'role':'system','content':'Learner profile: '+json.dumps(profile)}
    answer,error=call_openai([note,*msgs[-24:]],bool(d.get('web_search',True)))
    if error: return jsonify(error=error),503 if not OPENAI_API_KEY else 502
    add_activity(current_user()['id'],'AI Chat: '+str(msgs[-1].get('content',''))[:70]); return jsonify(answer=answer,time=datetime.now().strftime('%H:%M'))

@app.post('/api/quiz')
@login_required
def quiz():
    d=request.get_json() or {}; subject=d.get('subject','Mathematics'); level=d.get('level','secondary school'); topic=d.get('topic',''); difficulty=d.get('difficulty','Medium'); n=max(1,min(20,int(d.get('number',1))))
    prompt=f'''Create {n} original practice question(s) for a Namibian secondary learner. Subject: {subject}. Grade/level: {level}. Topic: {topic}. Difficulty: {difficulty}. They must not be described as official past-paper questions. Return JSON with key questions, each containing question, options (4 strings), answer_index (0-3), explanation.''' 
    text,error=call_openai([{'role':'user','content':prompt}],json_mode=True)
    if error: return jsonify(error=error),503
    try: return jsonify(json.loads(text))
    except: return jsonify(error='The quiz generator returned invalid data. Try again.'),502

@app.post('/api/quiz/result')
@login_required
def quiz_result():
    d=request.get_json() or {}; uid=current_user()['id']; c=conn(); c.execute('INSERT INTO quizzes(user_id,subject,score,total,created_at) VALUES(?,?,?,?,?)',(uid,d.get('subject',''),int(d.get('score',0)),int(d.get('total',0)),datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close(); add_activity(uid,f"Quiz: {d.get('subject','')} — {d.get('score',0)}/{d.get('total',0)}"); return jsonify(ok=True)

@app.post('/api/translate')
@login_required
def translate():
    d=request.get_json() or {}; src=d.get('source','').strip(); sl=d.get('source_lang','English'); tl=d.get('target_lang','Oshindonga')
    if not src:return jsonify(error='Enter text to translate.'),400
    prompt=f'''Translate the following educational text from {sl} to {tl}. Do not invent wording. If you are not sufficiently confident in the language pair, return JSON with reliable=false and explain that the translation needs verification. Otherwise return reliable=true and the translation. JSON keys: reliable, translation, note. Text: {src}'''
    text,error=call_openai([{'role':'user','content':prompt}],json_mode=True)
    if error:return jsonify(error=error),503
    try:
        out=json.loads(text); uid=current_user()['id']; c=conn(); c.execute('INSERT INTO translations(user_id,source_lang,target_lang,source,result,created_at) VALUES(?,?,?,?,?,?)',(uid,sl,tl,src,out.get('translation',''),datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close(); return jsonify(**out)
    except:return jsonify(error='Translation service returned invalid data.'),502

@app.post('/api/image')
@login_required
def image():
    if not OPENAI_API_KEY:return jsonify(error='OpenAI API key is not configured.'),503
    d=request.get_json() or {}; p=d.get('prompt','').strip(); mode=d.get('mode','Educational diagram')
    if not p:return jsonify(error='Enter an image description.')
    prompt=f"Create a high-quality educational {mode.lower()} for a Namibian secondary-school learner. {p}. Use clear labels and avoid unsupported factual claims."
    try:
        r=requests.post('https://api.openai.com/v1/images/generations',headers={'Authorization':f'Bearer {OPENAI_API_KEY}','Content-Type':'application/json'},json={'model':IMAGE_MODEL,'prompt':prompt,'size':'1024x1024','quality':'medium'},timeout=180)
        if not r.ok:return jsonify(error=r.text[:1500]),r.status_code
        item=r.json().get('data',[{}])[0]; img=('data:image/png;base64,'+item['b64_json']) if item.get('b64_json') else item.get('url')
        uid=current_user()['id']; c=conn(); c.execute('INSERT INTO saved_images(user_id,prompt,image,created_at) VALUES(?,?,?,?)',(uid,p,img,datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close(); add_activity(uid,'Generated educational image'); return jsonify(image=img,prompt=p)
    except Exception as e:return jsonify(error=str(e)),502

@app.post('/api/conversation')
@login_required
def conversation():
    d=request.get_json() or {}; uid=current_user()['id']; title=d.get('title','New learning session'); messages=d.get('messages',[]); cid=d.get('id')
    c=conn(); now=datetime.now().isoformat(timespec='seconds')
    if cid: c.execute('UPDATE conversations SET title=?,messages=?,updated_at=? WHERE id=? AND user_id=?',(title,json.dumps(messages),now,cid,uid))
    else: c.execute('INSERT INTO conversations(user_id,title,messages,created_at,updated_at) VALUES(?,?,?,?,?)',(uid,title,json.dumps(messages),now,now)); cid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.commit(); c.close(); return jsonify(id=cid)

@app.get('/api/conversations')
@login_required
def conversations():
    c=conn(); rows=c.execute('SELECT id,title,created_at,updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC LIMIT 50',(current_user()['id'],)).fetchall(); c.close(); return jsonify(items=[dict(x) for x in rows])

@app.get('/api/progress')
@login_required
def progress():
    uid=current_user()['id']; c=conn(); qs=c.execute('SELECT score,total,subject,created_at FROM quizzes WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall(); acts=c.execute('SELECT text,created_at FROM activity WHERE user_id=? ORDER BY id DESC LIMIT 30',(uid,)).fetchall(); topics=c.execute('SELECT subject,topic,completed FROM topics WHERE user_id=? ORDER BY id DESC',(uid,)).fetchall(); imgs=c.execute('SELECT id,prompt,created_at FROM saved_images WHERE user_id=? ORDER BY id DESC LIMIT 20',(uid,)).fetchall(); c.close(); total=sum(x['total'] for x in qs); score=sum(x['score'] for x in qs); return jsonify(profile=profile_for(uid),quizzes=[dict(x) for x in qs],activity=[dict(x) for x in acts],topics=[dict(x) for x in topics],images=[dict(x) for x in imgs],quiz_score=round(score/total*100) if total else 0)

@app.post('/api/topic')
@login_required
def topic():
    d=request.get_json() or {}; uid=current_user()['id']; c=conn(); c.execute('INSERT INTO topics(user_id,subject,topic,completed,created_at) VALUES(?,?,?,?,?)',(uid,d.get('subject',''),d.get('topic',''),1 if d.get('completed') else 0,datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close(); return jsonify(ok=True)

@app.post('/api/upload')
@login_required
def upload():
    f=request.files.get('file')
    if not f:return jsonify(error='No file selected.'),400
    allowed={'.pdf','.doc','.docx','.txt','.png','.jpg','.jpeg','.webp'}; ext=Path(f.filename).suffix.lower()
    if ext not in allowed:return jsonify(error='Supported: PDF, Word, text and common image files.'),400
    name=f"{uuid.uuid4().hex}{ext}"; f.save(UPLOADS/name); add_activity(current_user()['id'],f'Uploaded study file: {f.filename}')
    return jsonify(ok=True,filename=f.filename,path=f'/static/uploads/{name}')

@app.post('/api/reset-password')
def reset_password():
    d=request.get_json() or {}; token=d.get('token',''); password=d.get('password','')
    if len(password)<8:return jsonify(error='Password must be at least 8 characters.'),400
    c=conn(); row=c.execute('SELECT * FROM verification_tokens WHERE token=? AND used=0',(token,)).fetchone()
    if not row or datetime.fromisoformat(row['expires_at'])<datetime.now(): c.close(); return jsonify(error='Reset link is invalid or expired.'),400
    c.execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(password),row['user_id'])); c.execute('UPDATE verification_tokens SET used=1 WHERE id=?',(row['id'],)); c.commit(); c.close(); return jsonify(ok=True)

@app.get('/api/university')
@login_required
def university_data():
    uid=current_user()['id']; c=conn(); p=c.execute('SELECT * FROM university_profiles WHERE user_id=?',(uid,)).fetchone(); courses=c.execute('SELECT * FROM university_courses WHERE user_id=? ORDER BY id DESC',(uid,)).fetchall(); tasks=c.execute('SELECT * FROM university_tasks WHERE user_id=? ORDER BY due_date ASC',(uid,)).fetchall(); anns=c.execute('SELECT * FROM university_announcements WHERE user_id=? ORDER BY created_at DESC LIMIT 10',(uid,)).fetchall(); c.close(); return jsonify(profile=dict(p) if p else {},courses=[dict(x) for x in courses],tasks=[dict(x) for x in tasks],announcements=[dict(x) for x in anns])

@app.post('/api/university/profile')
@login_required
def university_profile():
    uid=current_user()['id']; d=request.get_json() or {}; c=conn(); c.execute('''INSERT INTO university_profiles(user_id,institution,student_number,programme,year_level,faculty,semester,gpa,credits,timetable) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET institution=excluded.institution,student_number=excluded.student_number,programme=excluded.programme,year_level=excluded.year_level,faculty=excluded.faculty,semester=excluded.semester,gpa=excluded.gpa,credits=excluded.credits,timetable=excluded.timetable''',(uid,d.get('institution',''),d.get('student_number',''),d.get('programme',''),d.get('year_level',''),d.get('faculty',''),d.get('semester',''),d.get('gpa',''),d.get('credits','0'),d.get('timetable',''))); c.commit(); c.close(); add_activity(uid,'Updated university student portal'); return jsonify(ok=True)

@app.post('/api/university/course')
@login_required
def university_course():
    uid=current_user()['id']; d=request.get_json() or {}; c=conn(); c.execute('INSERT INTO university_courses(user_id,code,name,lecturer,credits,mark) VALUES(?,?,?,?,?,?)',(uid,d.get('code',''),d.get('name',''),d.get('lecturer',''),int(d.get('credits',0) or 0),float(d.get('mark',0) or 0))); c.commit(); c.close(); return jsonify(ok=True)

@app.post('/api/university/task')
@login_required
def university_task():
    uid=current_user()['id']; d=request.get_json() or {}; c=conn(); c.execute('INSERT INTO university_tasks(user_id,course_code,title,due_date,status) VALUES(?,?,?,?,?)',(uid,d.get('course_code',''),d.get('title',''),d.get('due_date',''),d.get('status','Pending'))); c.commit(); c.close(); return jsonify(ok=True)

@app.get('/api/syllabus/german')
def german_syllabus():
    return jsonify(title='NSSCO German Foreign Language — Ordinary Level', code='4121', grades='11–12', source=GERMAN_SYLLABUS_URL, summary=GERMAN_SYLLABUS_SUMMARY, components=['Listening','Reading and Writing','Speaking','Grammar and Usage'])

@app.get('/api/status')
def status(): return jsonify(ok=True,openai=bool(OPENAI_API_KEY),model=OPENAI_MODEL,web_search=WEB_SEARCH)

@app.get('/sw.js')
def service_worker():
    response = make_response(send_from_directory(BASE / 'static', 'sw.js'))
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return response

@app.get('/robots.txt')
def robots(): return 'User-agent: *\nAllow: /\n'

if __name__=='__main__':
    init_db(); app.run(host=os.getenv('FLASK_HOST','127.0.0.1'),port=int(os.getenv('FLASK_PORT','5000')),debug=os.getenv('FLASK_DEBUG','true').lower()=='true')
