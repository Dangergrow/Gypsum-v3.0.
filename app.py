"""
Gypsum — калькулятор изделий и библиотека знаний.
Автор: Камашев В.Е.
Версия: 4.0
Поддерживает запуск из исходников и как .exe (PyInstaller).
"""
import sys
import webview
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# ============================================================
# ПУТИ
# ============================================================
if getattr(sys, 'frozen', False):
    BASE = Path(sys._MEIPASS)
    USER_BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).parent
    USER_BASE = BASE

HTML_PATH = BASE / 'index.html'
LIBRARY_PATH = BASE / 'library.json'
DB_PATH = USER_BASE / 'gypsum.db'
BACKUP_DIR = USER_BASE / 'backups'
BACKUP_DIR.mkdir(exist_ok=True)


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            price_unit TEXT DEFAULT 'unit',
            stock REAL DEFAULT 0,
            stock_min REAL DEFAULT 0,
            supplier_id INTEGER,
            meta TEXT DEFAULT '{}',
            favorite INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            data TEXT NOT NULL,
            total REAL NOT NULL DEFAULT 0,
            price REAL DEFAULT 0,
            status TEXT DEFAULT 'draft',
            client_id INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS bookmarks (article_id TEXT PRIMARY KEY, added_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS library_edits (article_id TEXT PRIMARY KEY, title TEXT, content TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            data TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT, phone TEXT, email TEXT, website TEXT, notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            project_name TEXT,
            type TEXT,
            quantity INTEGER DEFAULT 1,
            cost REAL DEFAULT 0,
            revenue REAL DEFAULT 0,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    defaults = {
        'labor_rate': '500', 'electricity_rate': '6', 'printer_power': '150',
        'default_waste': '5', 'amort_rate': '20', 'default_markup': '50',
        'theme': 'light', 'author': 'Камашев В.Е.', 'currency': '₽',
        'marketplace_fee': '15', 'tax_rate': '6',
    }
    for k, v in defaults.items():
        c.execute('INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)', (k, v))

    c.execute("SELECT COUNT(*) FROM materials")
    if c.fetchone()[0] == 0:
        seed = [
            # Гипс и добавки
            ('Гипс строительный Г-16', 'gypsum', 'kg', 45, {'water_ratio': 0.7, 'loss': 5}, 1),
            ('Гипс скульптурный', 'gypsum', 'kg', 90, {'water_ratio': 0.6, 'loss': 3}, 1),
            ('Гипс формовочный', 'gypsum', 'kg', 120, {'water_ratio': 0.5, 'loss': 3}, 0),
            ('Пеногаситель для гипса', 'gypsum_additive', 'g', 5.0, {}, 0),
            ('Пластификатор для гипса', 'gypsum_additive', 'g', 4.0, {}, 0),
            ('Замедлитель схватывания', 'gypsum_additive', 'g', 6.0, {}, 0),
            ('Ускоритель схватывания', 'gypsum_additive', 'g', 7.0, {}, 0),
            ('Армирующее волокно', 'gypsum_additive', 'g', 3.0, {}, 0),
            # Смолы и добавки
            ('Смола эпоксидная A', 'resin_a', 'g', 1.2, {}, 1),
            ('Смола полиуретановая A', 'resin_a', 'g', 1.8, {}, 0),
            ('Смола полиэстеровая A', 'resin_a', 'g', 0.9, {}, 0),
            ('Отвердитель B', 'resin_b', 'g', 1.5, {}, 1),
            ('Ускоритель для смолы', 'resin_additive', 'g', 8.0, {}, 0),
            ('Пластификатор для смолы', 'resin_additive', 'g', 6.0, {}, 0),
            ('Тиксотропная добавка', 'resin_additive', 'g', 9.0, {}, 0),
            ('УФ-стабилизатор', 'resin_additive', 'g', 12.0, {}, 0),
            ('Пигмент для смолы', 'resin_additive', 'g', 5.0, {}, 0),
            # 3D-печать FDM
            ('Филамент PLA', 'fdm', 'g', 2.5, {}, 1),
            ('Филамент PETG', 'fdm', 'g', 3.0, {}, 0),
            ('Филамент ABS', 'fdm', 'g', 2.8, {}, 0),
            ('Пигмент для филамента', 'fdm_additive', 'g', 4.0, {}, 0),
            ('Модификатор адгезии', 'fdm_additive', 'g', 7.0, {}, 0),
            # 3D-печать SLA
            ('Смола UV (фотополимер)', 'sla', 'ml', 8, {}, 1),
            ('Смола водоразбавляемая', 'sla', 'ml', 12, {}, 0),
            ('УФ-стабилизатор для SLA', 'sla_additive', 'g', 10.0, {}, 0),
            ('Пигмент для SLA', 'sla_additive', 'g', 6.0, {}, 0),
            # Декор и прочее
            ('Бисер стеклянный', 'decor', 'g', 3.0, {}, 0),
            ('Кабошоны стеклянные', 'decor', 'piece', 15, {}, 0),
            ('Клей-момент', 'decor', 'g', 0.9, {}, 0),
            ('Краска акриловая', 'decor', 'ml', 2.0, {}, 0),
            ('Пигмент сухой', 'decor', 'g', 4.5, {}, 0),
            ('Пигмент жидкий', 'decor', 'ml', 3.5, {}, 0),
            ('Патина (битум)', 'decor', 'ml', 4.0, {}, 0),
            ('Лак акриловый матовый', 'decor', 'ml', 2.5, {}, 0),
            ('Лак акриловый глянцевый', 'decor', 'ml', 2.5, {}, 0),
            ('Силикон платиновый', 'other', 'g', 3.5, {}, 0),
            ('Силикон оловянный', 'other', 'g', 2.0, {}, 0),
            ('Воск разделительный', 'other', 'ml', 5.0, {}, 0),
            ('Спрей-разделитель', 'other', 'ml', 3.5, {}, 0),
        ]
        for s in seed:
            c.execute("INSERT INTO materials(name, category, unit, price, meta, favorite) VALUES(?,?,?,?,?,?)",
                      (s[0], s[1], s[2], s[3], json.dumps(s[4]), s[5]))

    c.execute("SELECT COUNT(*) FROM templates")
    if c.fetchone()[0] == 0:
        seed_templates = [
            ('Подсвечник классический','gypsum','Простая форма, 250 г гипса, 30 мин работы', json.dumps({'gypsum_kg':0.25,'labor_hours':0.5,'waste_pct':5})),
            ('Панно декоративное (20×20)','gypsum','С армированием, 1.2 кг гипса, 2 ч работы', json.dumps({'gypsum_kg':1.2,'labor_hours':2,'waste_pct':8})),
            ('Кулон-капля','resin','Эпоксидка A 20 г, B 10 г, 30 мин работы', json.dumps({'resin_a_g':20,'resin_b_g':10,'ab_ratio':2,'labor_hours':0.5})),
            ('Миниатюра 28мм','sla','UV-смола 3 мл, 1.5 ч печати', json.dumps({'sub':'sla','sla_ml':3,'print_hours':1.5,'printer_power':60})),
            ('Функциональная деталь','fdm','PLA 40 г, 3 ч печати', json.dumps({'sub':'fdm','fdm_g':40,'print_hours':3,'printer_power':150})),
        ]
        for t in seed_templates:
            c.execute("INSERT INTO templates(name, type, description, data) VALUES(?,?,?,?)", t)
    conn.commit()
    conn.close()


def load_library():
    if not LIBRARY_PATH.exists():
        print(f'library.json не найден: {LIBRARY_PATH}')
        return {'categories': []}
    try:
        with open(LIBRARY_PATH, 'r', encoding='utf-8') as f:
            lib = json.load(f)
    except Exception as e:
        print(f'Ошибка чтения library.json: {e}')
        return {'categories': []}
    conn = get_conn()
    edits = {r['article_id']: dict(r) for r in conn.execute("SELECT * FROM library_edits").fetchall()}
    bookmarks = {r['article_id'] for r in conn.execute("SELECT article_id FROM bookmarks").fetchall()}
    conn.close()
    for cat in lib.get('categories', []):
        for art in cat.get('articles', []):
            aid = art.get('id')
            if not aid: continue
            if aid in edits:
                if edits[aid].get('title'): art['title'] = edits[aid]['title']
                if edits[aid].get('content'): art['content'] = edits[aid]['content']
                art['edited'] = True
            art['bookmarked'] = aid in bookmarks
    return lib


class Api:
    def get_settings(self):
        conn = get_conn(); rows = conn.execute("SELECT key, value FROM settings").fetchall(); conn.close()
        return {r['key']: r['value'] for r in rows}

    def save_settings(self, data):
        conn = get_conn()
        for k, v in data.items():
            conn.execute("INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
        conn.commit(); conn.close(); return {'ok': True}

    def get_materials(self, category=None):
        conn = get_conn()
        if category:
            rows = conn.execute("SELECT * FROM materials WHERE category=? ORDER BY name", (category,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM materials ORDER BY category, name").fetchall()
        conn.close()
        out = []
        for r in rows:
            d = dict(r)
            try: d['meta'] = json.loads(d['meta'] or '{}')
            except: d['meta'] = {}
            out.append(d)
        return out

    def save_material(self, data):
        conn = get_conn()
        meta = json.dumps(data.get('meta', {}))
        fav = 1 if data.get('favorite') else 0
        params = (data['name'], data['category'], data['unit'], float(data['price']),
                  data.get('price_unit', 'unit'), float(data.get('stock', 0)),
                  float(data.get('stock_min', 0)), data.get('supplier_id'), meta, fav)
        if data.get('id'):
            conn.execute("UPDATE materials SET name=?, category=?, unit=?, price=?, price_unit=?, stock=?, stock_min=?, supplier_id=?, meta=?, favorite=? WHERE id=?", params + (data['id'],))
        else:
            conn.execute("INSERT INTO materials(name, category, unit, price, price_unit, stock, stock_min, supplier_id, meta, favorite) VALUES(?,?,?,?,?,?,?,?,?,?)", params)
        conn.commit(); conn.close(); return {'ok': True}

    def toggle_favorite(self, mid):
        conn = get_conn()
        conn.execute("UPDATE materials SET favorite = 1 - favorite WHERE id=?", (mid,))
        conn.commit()
        row = conn.execute("SELECT favorite FROM materials WHERE id=?", (mid,)).fetchone()
        conn.close()
        return {'favorite': bool(row['favorite']) if row else False}

    def delete_material(self, mid):
        conn = get_conn(); conn.execute("DELETE FROM materials WHERE id=?", (mid,)); conn.commit(); conn.close()
        return {'ok': True}

    def get_projects(self):
        conn = get_conn()
        rows = conn.execute("SELECT id, name, type, total, price, status, created_at FROM projects ORDER BY created_at DESC").fetchall()
        conn.close(); return [dict(r) for r in rows]

    def get_project(self, pid):
        conn = get_conn(); r = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone(); conn.close()
        if not r: return None
        d = dict(r)
        try: d['data'] = json.loads(d['data'])
        except: d['data'] = {}
        return d

    def save_project(self, data):
        conn = get_conn()
        payload = json.dumps(data['data'], ensure_ascii=False)
        fields = (data['name'], data['type'], payload, float(data['total']),
                  float(data.get('price', 0)), data.get('status', 'draft'), data.get('notes', ''))
        if data.get('id'):
            conn.execute("UPDATE projects SET name=?, type=?, data=?, total=?, price=?, status=?, notes=? WHERE id=?", fields + (data['id'],))
            pid = data['id']
        else:
            cur = conn.execute("INSERT INTO projects(name, type, data, total, price, status, notes) VALUES(?,?,?,?,?,?,?)", fields)
            pid = cur.lastrowid
        conn.commit(); conn.close(); return {'ok': True, 'id': pid}

    def delete_project(self, pid):
        conn = get_conn(); conn.execute("DELETE FROM projects WHERE id=?", (pid,)); conn.commit(); conn.close()
        return {'ok': True}

    def get_library(self): return load_library()

    def toggle_bookmark(self, article_id):
        conn = get_conn()
        exists = conn.execute("SELECT 1 FROM bookmarks WHERE article_id=?", (article_id,)).fetchone()
        if exists:
            conn.execute("DELETE FROM bookmarks WHERE article_id=?", (article_id,)); result = False
        else:
            conn.execute("INSERT INTO bookmarks(article_id) VALUES(?)", (article_id,)); result = True
        conn.commit(); conn.close(); return {'bookmarked': result}

    def save_article(self, article_id, title, content):
        conn = get_conn()
        conn.execute("INSERT INTO library_edits(article_id, title, content, updated_at) VALUES(?,?,?,?) ON CONFLICT(article_id) DO UPDATE SET title=excluded.title, content=excluded.content, updated_at=excluded.updated_at",
                     (article_id, title, content, datetime.now().isoformat()))
        conn.commit(); conn.close(); return {'ok': True}

    def reset_article(self, article_id):
        conn = get_conn(); conn.execute("DELETE FROM library_edits WHERE article_id=?", (article_id,)); conn.commit(); conn.close()
        return {'ok': True}

    def get_bookmarks(self):
        conn = get_conn(); rows = conn.execute("SELECT article_id FROM bookmarks").fetchall(); conn.close()
        return [r['article_id'] for r in rows]

    def get_templates(self):
        conn = get_conn(); rows = conn.execute("SELECT * FROM templates ORDER BY type, name").fetchall(); conn.close()
        out = []
        for r in rows:
            d = dict(r)
            try: d['data'] = json.loads(d['data'])
            except: d['data'] = {}
            out.append(d)
        return out

    def save_template(self, data):
        conn = get_conn()
        payload = json.dumps(data['data'], ensure_ascii=False)
        if data.get('id'):
            conn.execute("UPDATE templates SET name=?, type=?, description=?, data=? WHERE id=?",
                         (data['name'], data['type'], data.get('description', ''), payload, data['id']))
        else:
            conn.execute("INSERT INTO templates(name, type, description, data) VALUES(?,?,?,?)",
                         (data['name'], data['type'], data.get('description', ''), payload))
        conn.commit(); conn.close(); return {'ok': True}

    def delete_template(self, tid):
        conn = get_conn(); conn.execute("DELETE FROM templates WHERE id=?", (tid,)); conn.commit(); conn.close()
        return {'ok': True}

    def get_suppliers(self):
        conn = get_conn(); rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall(); conn.close()
        return [dict(r) for r in rows]

    def save_supplier(self, data):
        conn = get_conn()
        fields = (data['name'], data.get('contact', ''), data.get('phone', ''),
                  data.get('email', ''), data.get('website', ''), data.get('notes', ''))
        if data.get('id'):
            conn.execute("UPDATE suppliers SET name=?, contact=?, phone=?, email=?, website=?, notes=? WHERE id=?", fields + (data['id'],))
        else:
            conn.execute("INSERT INTO suppliers(name, contact, phone, email, website, notes) VALUES(?,?,?,?,?,?)", fields)
        conn.commit(); conn.close(); return {'ok': True}

    def delete_supplier(self, sid):
        conn = get_conn(); conn.execute("DELETE FROM suppliers WHERE id=?", (sid,)); conn.commit(); conn.close()
        return {'ok': True}

    def get_journal(self):
        conn = get_conn(); rows = conn.execute("SELECT * FROM journal ORDER BY created_at DESC").fetchall(); conn.close()
        return [dict(r) for r in rows]

    def add_journal(self, data):
        conn = get_conn()
        conn.execute("INSERT INTO journal(project_id, project_name, type, quantity, cost, revenue, note) VALUES(?,?,?,?,?,?,?)",
                     (data.get('project_id'), data.get('project_name', ''), data.get('type', ''),
                      int(data.get('quantity', 1)), float(data.get('cost', 0)),
                      float(data.get('revenue', 0)), data.get('note', '')))
        conn.commit(); conn.close(); return {'ok': True}

    def delete_journal(self, jid):
        conn = get_conn(); conn.execute("DELETE FROM journal WHERE id=?", (jid,)); conn.commit(); conn.close()
        return {'ok': True}

    def get_low_stock(self):
        conn = get_conn()
        rows = conn.execute("SELECT * FROM materials WHERE stock_min > 0 AND stock <= stock_min ORDER BY (stock - stock_min) ASC").fetchall()
        conn.close()
        out = []
        for r in rows:
            d = dict(r)
            try: d['meta'] = json.loads(d['meta'] or '{}')
            except: d['meta'] = {}
            out.append(d)
        return out

    def update_stock(self, mid, value):
        conn = get_conn(); conn.execute("UPDATE materials SET stock=? WHERE id=?", (float(value), mid)); conn.commit(); conn.close()
        return {'ok': True}

    def export_backup(self):
        conn = get_conn(); data = {}
        for table in ['materials', 'projects', 'settings', 'bookmarks', 'library_edits', 'templates', 'suppliers', 'journal']:
            try:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                data[table] = [dict(r) for r in rows]
            except: data[table] = []
        conn.close()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = BACKUP_DIR / f'gypsum_backup_{ts}.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {'ok': True, 'path': str(path)}

    def import_backup(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        conn = get_conn(); c = conn.cursor()
        for table in ['materials', 'projects', 'templates', 'suppliers', 'journal']:
            if table not in data: continue
            c.execute(f"DELETE FROM {table}")
            for row in data[table]:
                cols = list(row.keys())
                sql = f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?'*len(cols))})"
                c.execute(sql, [row[k] for k in cols])
        for table in ['settings', 'bookmarks', 'library_edits']:
            if table not in data: continue
            for row in data[table]:
                cols = list(row.keys())
                sql = f"INSERT OR REPLACE INTO {table}({','.join(cols)}) VALUES({','.join('?'*len(cols))})"
                c.execute(sql, [row[k] for k in cols])
        conn.commit(); conn.close(); return {'ok': True}

    def list_backups(self):
        files = sorted(BACKUP_DIR.glob('gypsum_backup_*.json'), reverse=True)
        return [{'path': str(f), 'name': f.name, 'size': f.stat().st_size,
                 'date': datetime.fromtimestamp(f.stat().st_mtime).isoformat()} for f in files]


if __name__ == '__main__':
    init_db()
    api = Api()
    icon_path = BASE / 'icon.ico'
    start_args = {}
    if icon_path.exists():
        start_args['icon'] = str(icon_path)
    webview.create_window(
        'Gypsum — калькулятор изделий',
        str(HTML_PATH),
        js_api=api,
        width=1480, height=940, min_size=(1120, 720),
        background_color='#f6f7f9',
        easy_drag=False,
    )
    webview.start(**start_args)
