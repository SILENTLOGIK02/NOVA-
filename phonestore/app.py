"""
NOVA+ Phone Store - Flask Application (Standard Environment Setup)
"""
import os
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, g, abort)
from werkzeug.security import generate_password_hash, check_password_hash
import urllib.parse
import pg8000
import cloudinary
import cloudinary.uploader

# ============== CONFIG ==============
STORE_NAME       = "NOVA+"
STORE_TAGLINE    = "متجر الهواتف الذكية الفاخرة"
CURRENCY         = "د.ج"   # Algerian Dinar
WHATSAPP_NUMBER  = "213000000000"  
INSTAGRAM_URL    = "https://instagram.com/"
FACEBOOK_URL     = "https://facebook.com/"
ADMIN_EMAIL      = "admin@nova.com"
ADMIN_PASSWORD   = "Motou3122009"  
SECRET_KEY       = "change-this-secret-key"
# ====================================

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB

# ترك المكتبة تتعرف تلقائياً على متغير البيئة CLOUDINARY_URL السليم الذي عدلته الآن
DATABASE_URL = os.environ.get('DATABASE_URL')

def parse_db_url(url):
    parsed = urllib.parse.urlparse(url)
    return {
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip('/')
    }

# ---------- DB helpers ----------
def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        if DATABASE_URL:
            creds = parse_db_url(DATABASE_URL)
            db = g._db = pg8000.connect(
                user=creds["user"],
                password=creds["password"],
                host=creds["host"],
                port=creds["port"],
                database=creds["database"],
                ssl_context=True
            )
        else:
            import sqlite3
            db = g._db = sqlite3.connect("store.db")
            db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()

def make_dict(cursor, row):
    return {col[0]: val for col, val in zip(cursor.description, row)}

def init_db():
    if DATABASE_URL:
        creds = parse_db_url(DATABASE_URL)
        conn = pg8000.connect(
            user=creds["user"],
            password=creds["password"],
            host=creds["host"],
            port=creds["port"],
            database=creds["database"],
            ssl_context=True
        )
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS products(
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            brand TEXT,
            price REAL NOT NULL,
            old_price REAL,
            description TEXT,
            image TEXT,
            stock INTEGER DEFAULT 1,
            featured INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS admins(
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )""")
        
        c.execute("SELECT id FROM admins WHERE email=%s", (ADMIN_EMAIL,))
        row = c.fetchone()
        hashed_password = generate_password_hash(ADMIN_PASSWORD)
        if not row:
            c.execute("INSERT INTO admins(email,password) VALUES(%s,%s)", (ADMIN_EMAIL, hashed_password))
        else:
            c.execute("UPDATE admins SET password=%s WHERE email=%s", (hashed_password, ADMIN_EMAIL))
            
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect("store.db")
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, brand TEXT, price REAL NOT NULL, old_price REAL, description TEXT, image TEXT, stock INTEGER DEFAULT 1, featured INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL)""")
        c.execute("SELECT id FROM admins WHERE email=?", (ADMIN_EMAIL,))
        hashed_password = generate_password_hash(ADMIN_PASSWORD)
        if not c.fetchone():
            c.execute("INSERT INTO admins(email,password) VALUES(?,?)", (ADMIN_EMAIL, hashed_password))
        else:
            c.execute("UPDATE admins SET password=? WHERE email=?", (ADMIN_EMAIL, hashed_password))
        conn.commit()
        conn.close()

# ---------- Auth ----------
def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*a, **kw)
    return wrap

# ---------- Context ----------
@app.context_processor
def inject_globals():
    return dict(
        STORE_NAME=STORE_NAME,
        STORE_TAGLINE=STORE_TAGLINE,
        CURRENCY=CURRENCY,
        WHATSAPP_NUMBER=WHATSAPP_NUMBER,
        INSTAGRAM_URL=INSTAGRAM_URL,
        FACEBOOK_URL=FACEBOOK_URL,
    )

# ---------- Public routes ----------
@app.route("/")
def index():
    db = get_db()
    q = request.args.get("q", "").strip()
    brand = request.args.get("brand", "").strip()
    
    placeholder = "%s" if DATABASE_URL else "?"
    sql = "SELECT id, name, brand, price, old_price, description, image, stock, featured FROM products WHERE 1=1"
    args = []
    if q:
        sql += f" AND (name LIKE {placeholder} OR brand LIKE {placeholder} OR description LIKE {placeholder})"
        args += [f"%{q}%"] * 3
    if brand:
        sql += f" AND brand={placeholder}"
        args.append(brand)
        
    sql += " ORDER BY featured DESC, created_at DESC"
    
    if DATABASE_URL:
        c = db.cursor()
        c.execute(sql, args)
        products = [make_dict(c, r) for r in c.fetchall()]
        c.execute("SELECT id, name, brand, price, old_price, description, image, stock, featured FROM products WHERE featured=1 ORDER BY created_at DESC LIMIT 3")
        featured = [make_dict(c, r) for r in c.fetchall()]
        c.execute("SELECT DISTINCT brand FROM products WHERE brand!='' ORDER BY brand")
        brands = [r[0] for r in c.fetchall()]
    else:
        products = db.execute(sql, args).fetchall()
        featured = db.execute("SELECT * FROM products WHERE featured=1 ORDER BY created_at DESC LIMIT 3").fetchall()
        brands = [r[0] for r in db.execute("SELECT DISTINCT brand FROM products WHERE brand!='' ORDER BY brand").fetchall()]
        
    return render_template("index.html", products=products, featured=featured, brands=brands, q=q, current_brand=brand)

@app.route("/product/<int:pid>")
def product(pid):
    db = get_db()
    placeholder = "%s" if DATABASE_URL else "?"
    if DATABASE_URL:
        c = db.cursor()
        c.execute(f"SELECT id, name, brand, price, old_price, description, image, stock, featured FROM products WHERE id={placeholder}", (pid,))
        row = c.fetchone()
        p = make_dict(c, row) if row else None
        related = []
        if p:
            c.execute(f"SELECT id, name, brand, price, old_price, description, image, stock, featured FROM products WHERE brand={placeholder} AND id!={placeholder} LIMIT 4", (p["brand"], pid))
            related = [make_dict(c, r) for r in c.fetchall()]
    else:
        p = db.execute(f"SELECT * FROM products WHERE id={placeholder}", (pid,)).fetchone()
        related = db.execute(f"SELECT * FROM products WHERE brand={placeholder} AND id!={placeholder} LIMIT 4", (p["brand"], pid)).fetchall() if p else []
        
    if not p:
        abort(404)
    return render_template("product.html", p=p, related=related)

@app.route("/contact")
def contact():
    return render_template("contact.html")

# ---------- Admin ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        pw = request.form.get("password", "")
        db = get_db()
        placeholder = "%s" if DATABASE_URL else "?"
        
        if DATABASE_URL:
            c = db.cursor()
            c.execute(f"SELECT email, password FROM admins WHERE email={placeholder}", (email,))
            row = c.fetchone()
            row = make_dict(c, row) if row else None
        else:
            row = db.execute(f"SELECT * FROM admins WHERE email={placeholder}", (email,)).fetchone()
            
        if row and check_password_hash(row["password"], pw):
            session["admin"] = email
            return redirect(url_for("admin_dashboard"))
        flash("بيانات الدخول غير صحيحة", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    if DATABASE_URL:
        c = db.cursor()
        c.execute("SELECT id, name, brand, price, old_price, description, image, stock, featured FROM products ORDER BY created_at DESC")
        products = [make_dict(c, r) for r in c.fetchall()]
    else:
        products = db.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    return render_template("admin_dashboard.html", products=products)

@app.route("/admin/add", methods=["GET", "POST"])
@login_required
def admin_add():
    if request.method == "POST":
        return _save_product(None)
    return render_template("admin_form.html", p=None)

@app.route("/admin/edit/<int:pid>", methods=["GET", "POST"])
@login_required
def admin_edit(pid):
    db = get_db()
    placeholder = "%s" if DATABASE_URL else "?"
    if DATABASE_URL:
        c = db.cursor()
        c.execute(f"SELECT id, name, brand, price, old_price, description, image, stock, featured FROM products WHERE id={placeholder}", (pid,))
        row = c.fetchone()
        p = make_dict(c, row) if row else None
    else:
        p = db.execute(f"SELECT * FROM products WHERE id={placeholder}", (pid,)).fetchone()
        
    if not p:
        abort(404)
    if request.method == "POST":
        return _save_product(pid)
    return render_template("admin_form.html", p=p)

@app.route("/admin/delete/<int:pid>", methods=["POST"])
@login_required
def admin_delete(pid):
    db = get_db()
    placeholder = "%s" if DATABASE_URL else "?"
    if DATABASE_URL:
        c = db.cursor()
        c.execute(f"DELETE FROM products WHERE id={placeholder}", (pid,))
    else:
        db.execute(f"DELETE FROM products WHERE id={placeholder}", (pid,))
    db.commit()
    flash("تم حذف المنتج", "success")
    return redirect(url_for("admin_dashboard"))

def _save_product(pid):
    f = request.form
    image_url = ""
    file = request.files.get("image")
    
    if file and file.filename:
        # الرفع يعتمد الآن بسلاسة وتلقائية تامة على متغير البيئة الصحيح المتواجد في Render
        upload_result = cloudinary.uploader.upload(file)
        image_url = upload_result.get("secure_url")

    db = get_db()
    placeholder = "%s" if DATABASE_URL else "?"
    
    if pid:
        if not image_url:
            if DATABASE_URL:
                c = db.cursor()
                c.execute(f"SELECT image FROM products WHERE id={placeholder}", (pid,))
                row = c.fetchone()
                if row:
                    image_url = row[0] if isinstance(row, (list, tuple)) else row.get("image")
            else:
                image_url = db.execute(f"SELECT image FROM products WHERE id={placeholder}", (pid,)).fetchone()["image"]
                
        sql = f"""UPDATE products SET name={placeholder},brand={placeholder},price={placeholder},old_price={placeholder},
                  description={placeholder},image={placeholder},stock={placeholder},featured={placeholder} WHERE id={placeholder}"""
        params = (f["name"], f.get("brand", ""), float(f["price"] or 0),
                  float(f["old_price"]) if f.get("old_price") else None,
                  f.get("description", ""), image_url, int(f.get("stock") or 0),
                  1 if f.get("featured") else 0, pid)
    else:
        sql = f"""INSERT INTO products (name,brand,price,old_price,description,image,stock,featured)
                  VALUES({placeholder},{placeholder},{placeholder},{placeholder},{placeholder},{placeholder},{placeholder},{placeholder})"""
        params = (f["name"], f.get("brand", ""), float(f["price"] or 0),
                  float(f["old_price"]) if f.get("old_price") else None,
                  f.get("description", ""), image_url, int(f.get("stock") or 0),
                  1 if f.get("featured") else 0)
                  
    if DATABASE_URL:
        c = db.cursor()
        c.execute(sql, params)
    else:
        db.execute(sql, params)
        
    db.commit()
    flash("تم حفظ التعديلات بنجاح", "success")
    return redirect(url_for("admin_dashboard"))

@app.errorhandler(404)
def e404(_):
    return render_template("404.html"), 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
