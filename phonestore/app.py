"""

NOVA+ Phone Store - Flask Application

Run: python app.py  -> http://localhost:5000

Admin: /admin/login  (default: admin@nova.com / admin123)

"""

import os

import sqlite3

from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,

                   session, flash, g, abort)

from werkzeug.security import generate_password_hash, check_password_hash

from werkzeug.utils import secure_filename



# ============== CONFIG ==============

STORE_NAME       = "NOVA+"

STORE_TAGLINE    = "متجر الهواتف الذكية الفاخرة"

CURRENCY         = "د.ج"   # Algerian Dinar

WHATSAPP_NUMBER  = "213000000000"  # ← غيّر الرقم هنا

INSTAGRAM_URL    = "https://instagram.com/"

FACEBOOK_URL     = "https://facebook.com/"

ADMIN_EMAIL      = "admin@nova.com"

ADMIN_PASSWORD   = "Motou3122009"

SECRET_KEY       = "change-this-secret-key"

DB_PATH          = "store.db"

UPLOAD_FOLDER    = "static/uploads"

ALLOWED_EXT      = {"png", "jpg", "jpeg", "webp", "gif"}

# ====================================



app = Flask(__name__)

app.config["SECRET_KEY"] = SECRET_KEY

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB



os.makedirs(UPLOAD_FOLDER, exist_ok=True)





# ---------- DB helpers ----------

def get_db():

    db = getattr(g, "_db", None)

    if db is None:

        db = g._db = sqlite3.connect(DB_PATH)

        db.row_factory = sqlite3.Row

    return db





@app.teardown_appcontext

def close_db(exc):

    db = getattr(g, "_db", None)

    if db is not None:

        db.close()





def init_db():

    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS products(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        name TEXT NOT NULL,

        brand TEXT,

        price REAL NOT NULL,

        old_price REAL,

        description TEXT,

        image TEXT,

        stock INTEGER DEFAULT 1,

        featured INTEGER DEFAULT 0,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP

    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS admins(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        email TEXT UNIQUE NOT NULL,

        password TEXT NOT NULL

    )""")

    # default admin

    c.execute("SELECT id FROM admins WHERE email=?", (ADMIN_EMAIL,))

    if not c.fetchone():

        c.execute("INSERT INTO admins(email,password) VALUES(?,?)",

                  (ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD)))



    # seed demo products

    c.execute("SELECT COUNT(*) FROM products")

    if c.fetchone()[0] == 0:

        demo = [

            ("iPhone 15 Pro Max", "Apple", 285000, 310000,

             "أحدث هاتف من Apple بشريحة A17 Pro وكاميرا احترافية بدقة 48MP.",

             "", 5, 1),

            ("Samsung Galaxy S24 Ultra", "Samsung", 260000, 280000,

             "هاتف Samsung الرائد بقلم S Pen وكاميرا 200MP وشاشة Dynamic AMOLED 2X.",

             "", 8, 1),

            ("Xiaomi 14 Pro", "Xiaomi", 145000, 160000,

             "أداء قوي بمعالج Snapdragon 8 Gen 3 وكاميرا Leica.",

             "", 12, 1),

            ("Google Pixel 8 Pro", "Google", 175000, None,

             "تجربة Android النقية مع ذكاء اصطناعي متقدم وكاميرا مذهلة.",

             "", 4, 0),

            ("OnePlus 12", "OnePlus", 155000, 170000,

             "شحن سريع 100W وأداء استثنائي وشاشة 120Hz.",

             "", 7, 0),

            ("Honor Magic 6 Pro", "Honor", 135000, None,

             "تصميم فاخر وكاميرا متطورة وبطارية تدوم طويلاً.",

             "", 6, 0),

        ]

        c.executemany("""INSERT INTO products

            (name,brand,price,old_price,description,image,stock,featured)

            VALUES (?,?,?,?,?,?,?,?)""", demo)

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





def allowed_file(name):

    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED_EXT





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

    sql = "SELECT * FROM products WHERE 1=1"

    args = []

    if q:

        sql += " AND (name LIKE ? OR brand LIKE ? OR description LIKE ?)"

        args += [f"%{q}%"] * 3

    if brand:

        sql += " AND brand=?"

        args.append(brand)

    sql += " ORDER BY featured DESC, created_at DESC"

    products = db.execute(sql, args).fetchall()

    featured = db.execute(

        "SELECT * FROM products WHERE featured=1 ORDER BY created_at DESC LIMIT 3"

    ).fetchall()

    brands = [r[0] for r in db.execute(

        "SELECT DISTINCT brand FROM products WHERE brand!='' ORDER BY brand"

    ).fetchall()]

    return render_template("index.html", products=products, featured=featured,

                           brands=brands, q=q, current_brand=brand)





@app.route("/product/<int:pid>")

def product(pid):

    db = get_db()

    p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()

    if not p:

        abort(404)

    related = db.execute(

        "SELECT * FROM products WHERE brand=? AND id!=? LIMIT 4",

        (p["brand"], pid)).fetchall()

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

        row = get_db().execute(

            "SELECT * FROM admins WHERE email=?", (email,)).fetchone()

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

    products = get_db().execute(

        "SELECT * FROM products ORDER BY created_at DESC").fetchall()

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

    p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()

    if not p:

        abort(404)

    if request.method == "POST":

        return _save_product(pid)

    return render_template("admin_form.html", p=p)





@app.route("/admin/delete/<int:pid>", methods=["POST"])

@login_required

def admin_delete(pid):

    db = get_db()

    db.execute("DELETE FROM products WHERE id=?", (pid,))

    db.commit()

    flash("تم حذف المنتج", "success")

    return redirect(url_for("admin_dashboard"))





def _save_product(pid):

    f = request.form

    image = ""

    file = request.files.get("image")

    if file and file.filename and allowed_file(file.filename):

        fn = secure_filename(file.filename)

        base, ext = os.path.splitext(fn)

        i = 1

        while os.path.exists(os.path.join(UPLOAD_FOLDER, fn)):

            fn = f"{base}_{i}{ext}"

            i += 1

        file.save(os.path.join(UPLOAD_FOLDER, fn))

        image = fn



    db = get_db()

    if pid:

        if not image:

            image = db.execute(

                "SELECT image FROM products WHERE id=?", (pid,)).fetchone()["image"]

        db.execute("""UPDATE products SET name=?,brand=?,price=?,old_price=?,

                      description=?,image=?,stock=?,featured=? WHERE id=?""",

                   (f["name"], f.get("brand", ""), float(f["price"] or 0),

                    float(f["old_price"]) if f.get("old_price") else None,

                    f.get("description", ""), image,

                    int(f.get("stock") or 0),

                    1 if f.get("featured") else 0, pid))

        flash("تم تحديث المنتج", "success")

    else:

        db.execute("""INSERT INTO products

            (name,brand,price,old_price,description,image,stock,featured)

            VALUES(?,?,?,?,?,?,?,?)""",

                   (f["name"], f.get("brand", ""), float(f["price"] or 0),

                    float(f["old_price"]) if f.get("old_price") else None,

                    f.get("description", ""), image,

                    int(f.get("stock") or 0),

                    1 if f.get("featured") else 0))

        flash("تم إضافة المنتج", "success")

    db.commit()

    return redirect(url_for("admin_dashboard"))





@app.errorhandler(404)

def e404(_):

    return render_template("404.html"), 404





if __name__ == "__main__":

    init_db()

    app.run(debug=True, host="0.0.0.0", port=5000
