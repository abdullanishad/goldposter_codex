import os
import sqlite3
from functools import wraps
from uuid import uuid4

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from twilio.twiml.messaging_response import MessagingResponse
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from poster_engine import generate_poster

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "users.db")
GENERATED_DIR = os.path.join(BASE_DIR, "static", "generated")
LOGOS_DIR = os.path.join(BASE_DIR, "static", "logos")
TEMPLATES_DIR = os.path.join(BASE_DIR, "static", "templates")
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_TEMPLATE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-in-production")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            shop_name TEXT NOT NULL,
            logo_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    existing_columns = {
        row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()
    }
    if "shop_name" not in existing_columns:
        db.execute("ALTER TABLE users ADD COLUMN shop_name TEXT NOT NULL DEFAULT ''")
    if "logo_path" not in existing_columns:
        db.execute("ALTER TABLE users ADD COLUMN logo_path TEXT")
    db.commit()
    db.close()


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute(
        "SELECT id, username, shop_name, logo_path FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def list_template_names():
    if not os.path.isdir(TEMPLATES_DIR):
        return []
    return sorted(
        filename
        for filename in os.listdir(TEMPLATES_DIR)
        if os.path.isfile(os.path.join(TEMPLATES_DIR, filename))
        and os.path.splitext(filename)[1].lower() in ALLOWED_TEMPLATE_EXTENSIONS
    )


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        shop_name = request.form.get("shop_name", "").strip()
        logo_file = request.files.get("logo")

        if not username or not password or not shop_name:
            flash("Username, password, and shop name are required.", "danger")
            return render_template("signup.html")

        password_hash = generate_password_hash(password)
        saved_logo_path = None
        logo_db_path = None

        if logo_file and logo_file.filename:
            filename = secure_filename(logo_file.filename)
            extension = os.path.splitext(filename)[1].lower()
            if extension not in ALLOWED_LOGO_EXTENSIONS:
                flash("Logo must be a PNG, JPG, JPEG, or WEBP file.", "danger")
                return render_template("signup.html")

            os.makedirs(LOGOS_DIR, exist_ok=True)
            unique_name = f"{uuid4().hex}{extension}"
            saved_logo_path = os.path.join(LOGOS_DIR, unique_name)
            logo_file.save(saved_logo_path)
            logo_db_path = os.path.join("static", "logos", unique_name)

        db = get_db()

        try:
            cursor = db.execute(
                "INSERT INTO users (username, password_hash, shop_name, logo_path) VALUES (?, ?, ?, ?)",
                (username, password_hash, shop_name, logo_db_path),
            )
            db.commit()
            session.clear()
            session["user_id"] = cursor.lastrowid
            session["username"] = username
            flash("Account created successfully.", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            if saved_logo_path and os.path.exists(saved_logo_path):
                os.remove(saved_logo_path)
            flash("Username already exists.", "danger")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("login.html")

        user = get_db().execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    if user is None:
        flash("Please log in to continue.", "warning")
        return redirect(url_for("login"))

    generated_image = request.args.get("generated", "").strip() or None
    templates = list_template_names()
    return render_template(
        "dashboard.html",
        username=user["username"],
        shop_name=user["shop_name"],
        generated_image=generated_image,
        templates=templates,
    )


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    user = get_current_user()
    if user is None:
        flash("Please log in to continue.", "warning")
        return redirect(url_for("login"))

    gold_price = request.form.get("gold_price", "").strip()
    template_name = request.form.get("template_name", "").strip()
    shop_name = (user["shop_name"] or "").strip()
    logo_path = user["logo_path"]

    if not gold_price:
        flash("Gold price is required.", "danger")
        return redirect(url_for("dashboard"))
    if not template_name:
        flash("Please select a template.", "danger")
        return redirect(url_for("dashboard"))

    if not shop_name:
        flash("Shop name is missing in your profile. Please contact support.", "danger")
        return redirect(url_for("dashboard"))

    os.makedirs(GENERATED_DIR, exist_ok=True)

    try:
        generated_path = generate_poster(
            shop_name=shop_name,
            gold_price=gold_price,
            template_name=template_name,
            logo_path=logo_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("dashboard"))
    except Exception:
        flash("Failed to generate poster. Please try again.", "danger")
        return redirect(url_for("dashboard"))

    generated_filename = os.path.basename(generated_path)
    flash("Poster generated successfully.", "success")
    return redirect(url_for("dashboard", generated=generated_filename))


@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """
    Twilio WhatsApp webhook endpoint.
    Receives inbound messages and replies with a generated poster image URL.
    """
    twiml = MessagingResponse()
    message = twiml.message()

    incoming_text = request.form.get("Body", "").strip()
    if not incoming_text:
        message.body("Send a gold price text (example: 6245) to generate your poster.")
        return str(twiml), 200, {"Content-Type": "application/xml"}

    user = get_current_user()
    if user is None:
        message.body("Please log in to your dashboard first, then send your gold price.")
        return str(twiml), 200, {"Content-Type": "application/xml"}

    shop_name = (user["shop_name"] or "").strip()
    logo_path = user["logo_path"]
    if not shop_name:
        message.body("Shop profile is incomplete. Add your shop name in dashboard settings.")
        return str(twiml), 200, {"Content-Type": "application/xml"}

    templates = list_template_names()
    if not templates:
        message.body("No poster templates are configured right now.")
        return str(twiml), 200, {"Content-Type": "application/xml"}

    try:
        generated_path = generate_poster(
            shop_name=shop_name,
            gold_price=incoming_text,
            template_name=templates[0],
            logo_path=logo_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        message.body(f"Poster generation failed: {exc}")
        return str(twiml), 200, {"Content-Type": "application/xml"}
    except Exception:
        message.body("Poster generation failed. Please try again.")
        return str(twiml), 200, {"Content-Type": "application/xml"}

    generated_filename = os.path.basename(generated_path)
    static_path = url_for("static", filename=f"generated/{generated_filename}")
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if public_base_url:
        media_url = f"{public_base_url}{static_path}"
    else:
        media_url = url_for("static", filename=f"generated/{generated_filename}", _external=True)

    message.body(f"{shop_name} poster is ready.")
    message.media(media_url)
    return str(twiml), 200, {"Content-Type": "application/xml"}


@app.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
