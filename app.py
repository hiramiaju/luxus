"""LUXU AGS · Catálogo público y administración Flask/JSON."""
import io, json, os, secrets, uuid, zipfile, tempfile
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, jsonify, request, render_template, session, redirect, url_for, send_from_directory, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError
from filelock import FileLock

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('LUXU_DATA_DIR', str(ROOT / 'data')))
UPLOADS = DATA / 'uploads'
DATA.mkdir(parents=True, exist_ok=True); UPLOADS.mkdir(parents=True, exist_ok=True)
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32), MAX_CONTENT_LENGTH=10*1024*1024,
 SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1', PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
# Set SECRET_KEY in production to avoid invalidating sessions across restarts.
RESOURCES={'products','brands','categories','promotions','banners'}
DEFAULTS={
 'store_name':'LUXU AGS','tagline':'YOUR FIT. YOUR RULES.','hero_kicker':'NEW ENERGY · NEW LOOK',
 'hero_description':'El outfit que te acompaña a romper tus límites. Descubre piezas para entrenar, moverte y sentirte increíble.',
 'hero_image':'https://images.unsplash.com/photo-1518611012118-696072aa579a?w=1800&auto=format&fit=crop',
 'logo':'/static/luxu-logo.png','announcement':'LUXU AGS · ACTIVEWEAR CURADO PARA TU ESTILO ✦',
 'instagram':'https://www.instagram.com/luxuags/','whatsapp':'','currency':'MXN',
 'primary_color':'#161616','background_color':'#f5f5f5','accent_color':'#343434',
 'about_title':'La mejor versión de ti, en movimiento.','about_text':'Explora el catálogo y escríbenos por Instagram para consultar modelos y disponibilidad.',
 'footer_text':'Activewear · Aguascalientes, México', 'shipping_text':'Consulta disponibilidad y entregas por mensaje',
 'seo_description':'LUXU AGS, catálogo de moda deportiva en Aguascalientes.'}

def _path(resource):
 if resource not in RESOURCES | {'settings', 'users'}:
  raise ValueError('Recurso inválido')
 return DATA / f'{resource}.json'

def _read(resource):
 path=_path(resource)
 if not path.exists():
  return {} if resource=='settings' else []
 with path.open('r',encoding='utf-8') as stream:
  value=json.load(stream)
 if not isinstance(value,dict if resource=='settings' else list):
  raise ValueError(f'Formato JSON incorrecto: {path.name}')
 return value

def _write(resource, value):
 path=_path(resource)
 # Primero volcar el JSON en un temporal, después reemplazar el original.
 fd,tmp=tempfile.mkstemp(prefix='.luxu-',suffix='.tmp',dir=DATA)
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as out:
   json.dump(value,out,ensure_ascii=False,indent=2)
   out.write('\n');out.flush();os.fsync(out.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def _modify(resource,callback):
 with FileLock(str(_path(resource))+'.lock',timeout=15):
  value=_read(resource)
  result=callback(value)
  _write(resource,value)
  return result

def _stamp():return datetime.now(timezone.utc).isoformat()

def init_db():
 # Función histórica conservada para inicializar el almacenamiento JSON.
 seed=json.loads((ROOT/'initial_catalog.json').read_text(encoding='utf-8'))
 for resource in RESOURCES:
  def initialize(items, resource=resource):
   if items:return
   now=_stamp()
   for idx,obj in enumerate(seed.get(resource,[]),1):
    items.append({'id':idx,**obj,'created_at':now,'updated_at':now})
  _modify(resource,initialize)
 def init_settings(current):
  for k,v in DEFAULTS.items(): current.setdefault(k,v)
 _modify('settings',init_settings)
 _modify('users',lambda users:None)

def records(table):
 if table not in RESOURCES:raise ValueError('Recurso inválido')
 return sorted(_read(table),key=lambda r:r['id'],reverse=True)

def config():return _read('settings')

def find_admin(username=None,uid=None):
 for user in _read('users'):
  if (username is not None and user['username']==username) or (uid is not None and user['id']==uid):return user
 return None

def admin_required(fn):
 @wraps(fn)
 def wrapper(*a,**kw):
  if not session.get('admin_id'):return jsonify(error='Debes iniciar sesión'),401
  return fn(*a,**kw)
 return wrapper

def csrf_required(fn):
 @wraps(fn)
 def wrapper(*a,**kw):
  if request.headers.get('X-CSRF-Token')!=session.get('csrf') or not session.get('csrf'):return jsonify(error='Sesión inválida; recarga la página'),403
  return fn(*a,**kw)
 return wrapper

@app.after_request
def secure_headers(resp):
 resp.headers['X-Content-Type-Options']='nosniff';resp.headers['X-Frame-Options']='DENY';resp.headers['Referrer-Policy']='strict-origin-when-cross-origin'
 if request.path.startswith('/admin'):resp.headers['Cache-Control']='no-store'
 return resp

@app.route('/')
def home():return render_template('catalog.html')

@app.route('/media/<path:name>')
def media(name):return send_from_directory(UPLOADS,name)

@app.get('/api/catalog')
def catalog():
 data={r:records(r) for r in RESOURCES};data['settings']=config()
 data['products']=[p for p in data['products'] if p.get('active',True)]
 data['brands']=[p for p in data['brands'] if p.get('active',True)]
 data['categories']=[p for p in data['categories'] if p.get('active',True)]
 data['promotions']=[p for p in data['promotions'] if p.get('active',True)]
 data['banners']=[p for p in data['banners'] if p.get('active',True)]
 return jsonify(data)

@app.route('/admin/login',methods=['GET','POST'])
def login():
 if request.method=='GET':
  if session.get('admin_id'):return redirect('/admin')
  return render_template('login.html')
 username=(request.form.get('username') or '').strip();password=request.form.get('password') or ''
 row=find_admin(username=username)
 if not row or not check_password_hash(row['password_hash'],password):
  return render_template('login.html',error='Usuario o contraseña incorrectos'),401
 session.clear();session.permanent=True;session['admin_id']=row['id'];session['username']=username;session['csrf']=secrets.token_urlsafe(32)
 return redirect('/admin')

@app.post('/admin/logout')
@admin_required
@csrf_required
def logout():session.clear();return jsonify(ok=True)

@app.get('/admin')
def admin():
 if not session.get('admin_id'):return redirect('/admin/login')
 return render_template('admin.html',csrf=session['csrf'],username=session['username'])

@app.get('/api/admin/all')
@admin_required
def all_data():return jsonify(**{r:records(r) for r in RESOURCES},settings=config(),username=session['username'])

@app.route('/api/admin/<resource>',methods=['POST'])
@admin_required
@csrf_required
def create_record(resource):
 if resource not in RESOURCES:abort(404)
 obj=clean_record(resource,request.get_json(silent=True))
 if isinstance(obj,tuple):return jsonify(error=obj[1]),400
 now=_stamp()
 def create(rows):
  next_id=max((r['id'] for r in rows),default=0)+1
  record={'id':next_id,**obj,'created_at':now,'updated_at':now}
  rows.append(record)
  return record
 return jsonify(_modify(resource,create)),201

@app.route('/api/admin/<resource>/<int:rid>',methods=['PUT','DELETE'])
@admin_required
@csrf_required
def change_record(resource,rid):
 if resource not in RESOURCES:abort(404)
 obj=None
 if request.method=='PUT':
  obj=clean_record(resource,request.get_json(silent=True))
  if isinstance(obj,tuple):return jsonify(error=obj[1]),400
 def update(rows):
  for i,row in enumerate(rows):
   if row['id']==rid:
    if request.method=='DELETE':
     rows.pop(i)
     return {'ok':True}
    saved={'id':rid,**obj,'created_at':row['created_at'],'updated_at':_stamp()}
    rows[i]=saved
    return saved
  return None
 changed=_modify(resource,update)
 if changed is None:return jsonify(error='Registro no encontrado'),404
 return jsonify(changed)

def clean_record(resource,raw):
 if not isinstance(raw,dict):return (None,'Datos incorrectos')
 allowed={
 'products':{'name','sku','description','brand','type','gender','sizes','color','colors','price','compare_price','stock','stock_by_size','collection','image','images','featured','active','demo','tags','sort_order'},
 'brands':{'name','logo','description','active'},
 'categories':{'name','image','description','active','sort_order'},
 'promotions':{'name','type','value','product_ids','brand','category','start_at','end_at','active','badge','priority'},
 'banners':{'title','subtitle','image','button_text','button_link','active','sort_order'}}[resource]
 obj={k:v for k,v in raw.items() if k in allowed}
 if not str(obj.get('name') or obj.get('title') or '').strip():return (None,'El nombre o título es obligatorio')
 if resource=='products':
  try:
   obj['price']=round(float(obj.get('price') or 0),2);obj['stock']=int(obj.get('stock') or 0);obj['compare_price']=round(float(obj.get('compare_price') or 0),2)
  except (ValueError,TypeError):return (None,'Precio o inventario inválido')
  if obj['price']<0 or obj['stock']<0 or obj['compare_price']<0:return (None,'No se permiten valores negativos')
  for k in ['sizes','colors','images','tags']:
   if not isinstance(obj.get(k,[]),list):return (None,f'{k} debe ser una lista')
  if obj.get('stock_by_size') and not isinstance(obj['stock_by_size'],dict):return (None,'Inventario por talla inválido')
 if resource=='promotions':
  if obj.get('type') not in ('percent','fixed'):return (None,'Tipo de descuento inválido')
  try:obj['value']=float(obj.get('value') or 0)
  except (ValueError,TypeError):return (None,'Descuento inválido')
  if obj['value']<0 or (obj['type']=='percent' and obj['value']>100):return (None,'Descuento fuera de rango')
  if not isinstance(obj.get('product_ids',[]),list):return (None,'Productos de la promoción inválidos')
  obj['product_ids']=[int(x) for x in obj.get('product_ids',[]) if str(x).isdigit()]
 for key in ('name','title','description','subtitle','button_text','button_link','image','logo','instagram'):
  if key in obj and isinstance(obj[key],str):obj[key]=obj[key].strip()[:3000]
 return obj

@app.put('/api/admin/settings')
@admin_required
@csrf_required
def settings_update():
 raw=request.get_json(silent=True)
 if not isinstance(raw,dict):return jsonify(error='Datos inválidos'),400
 allowed=set(DEFAULTS)
 def update(settings):
  for k,v in raw.items():
   if k in allowed and isinstance(v,str):settings[k]=v[:3000]
 _modify('settings',update)
 return jsonify(settings=config())

@app.post('/api/admin/upload')
@admin_required
@csrf_required
def upload():
 uploaded=request.files.get('file')
 if not uploaded:return jsonify(error='Elige una imagen'),400
 try:
  img=Image.open(uploaded.stream);img.verify();uploaded.stream.seek(0)
  img=Image.open(uploaded.stream)
  if img.width*img.height>25_000_000:return jsonify(error='Imagen demasiado grande'),400
  if img.format not in ('JPEG','PNG','WEBP'):return jsonify(error='Solo JPG, PNG o WEBP'),400
  img.thumbnail((2200,2200))
  if img.mode not in ('RGB','RGBA'):img=img.convert('RGB')
  filename=f'{uuid.uuid4().hex}.webp';img.save(UPLOADS/filename,'WEBP',quality=86,method=5)
 except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):return jsonify(error='La imagen no es válida'),400
 return jsonify(url='/media/'+filename),201

@app.get('/api/admin/backup')
@admin_required
def backup():
 memory=io.BytesIO()
 with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as archive:
  payload={'settings':config(),**{r:records(r) for r in RESOURCES}}
  archive.writestr('catalogo.json',json.dumps(payload,ensure_ascii=False,indent=2))
  for resource in sorted(RESOURCES | {'settings'}):
   archive.write(_path(resource),'json/'+resource+'.json')
  for f in UPLOADS.iterdir():
   if f.is_file():archive.write(f,'uploads/'+f.name)
 memory.seek(0)
 return send_file(memory,mimetype='application/zip',as_attachment=True,download_name='luxu-backup-'+datetime.now().strftime('%Y%m%d-%H%M')+'.zip')

@app.post('/api/admin/password')
@admin_required
@csrf_required
def password_change():
 raw=request.get_json(silent=True) or {};old=raw.get('current','');new=raw.get('new','')
 if len(new)<12:return jsonify(error='La nueva contraseña debe tener al menos 12 caracteres'),400
 row=find_admin(uid=session['admin_id'])
 if not row or not check_password_hash(row['password_hash'],old):return jsonify(error='Contraseña actual incorrecta'),400
 def update(users):
  for user in users:
   if user['id']==row['id']:
    user['password_hash']=generate_password_hash(new)
    return
 _modify('users',update)
 return jsonify(ok=True)

@app.cli.command('create-admin')
def create_admin():
 import getpass
 username=input('Usuario administrador: ').strip()
 password=getpass.getpass('Contraseña (mínimo 12 caracteres): ')
 if not username or len(password)<12:raise SystemExit('Nombre requerido y contraseña de al menos 12 caracteres')
 def create(users):
  if any(u['username']==username for u in users):raise ValueError('El usuario ya existe')
  users.append({'id':max((u['id'] for u in users),default=0)+1,'username':username,'password_hash':generate_password_hash(password)})
 try:_modify('users',create)
 except ValueError as exc:raise SystemExit(str(exc))
 print('Administrador creado.')

init_db()
if __name__=='__main__':app.run(host='127.0.0.1',port=5000,debug=False)
