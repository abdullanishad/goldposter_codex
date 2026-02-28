import os
import sqlite3
from datetime import datetime
from functools import wraps
from uuid import uuid4

from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config_manager import get_template
from models import Admin, User, db
from poster_engine import generate_poster
from routes.template_calibration import create_template_calibration_blueprint

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "users.db")
GENERATED_DIR = os.path.join(BASE_DIR, "static", "generated")
UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads")
TEMPLATES_DIR = os.path.join(BASE_DIR, "static", "templates")
TEMPLATE_CONFIG_PATH = os.path.join(BASE_DIR, "template_config.json")
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_TEMPLATE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_DEFAULT_PASSWORD = os.environ.get("ADMIN_DEFAULT_PASSWORD", "admin123")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id: str):
    if not user_id:
        return None
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def _is_admin_user(user: User | None) -> bool:
    return bool(user and user.role == "admin")


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if not _is_admin_user(current_user):
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped_view


def list_template_names() -> list[str]:
    if not os.path.isdir(TEMPLATES_DIR):
        return []
    return sorted(
        filename
        for filename in os.listdir(TEMPLATES_DIR)
        if os.path.isfile(os.path.join(TEMPLATES_DIR, filename))
        and os.path.splitext(filename)[1].lower() in ALLOWED_TEMPLATE_EXTENSIONS
    )


def get_admin_settings() -> Admin:
    admin = db.session.get(Admin, 1)
    if admin is None:
        admin = Admin(id=1)
        db.session.add(admin)
        db.session.commit()
    return admin


def format_today_uppercase() -> str:
    return datetime.now().strftime("%d %B %Y").upper()


def _save_logo(file_storage) -> str:
    filename = secure_filename(file_storage.filename)
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_LOGO_EXTENSIONS:
        raise ValueError("Logo must be a PNG, JPG, JPEG, or WEBP file.")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    unique_name = f"{uuid4().hex}{extension}"
    save_path = os.path.join(UPLOADS_DIR, unique_name)
    file_storage.save(save_path)
    return os.path.join("static", "uploads", unique_name)


def _bootstrap_defaults() -> None:
    _ensure_legacy_user_columns_sqlite()
    db.create_all()
    _ensure_user_profile_columns()
    db.session.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL OR TRIM(role) = ''"))

    admin_user = User.query.filter_by(role="admin").first()
    if admin_user is None:
        named_admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()
        if named_admin_user is not None:
            named_admin_user.role = "admin"
            named_admin_user.password_hash = generate_password_hash(ADMIN_DEFAULT_PASSWORD)
        else:
            admin_user = User(
                username=ADMIN_USERNAME,
                password_hash=generate_password_hash(ADMIN_DEFAULT_PASSWORD),
                role="admin",
                shop_name="Admin",
                address="",
                whatsapp_number="",
                social_handle="",
                logo_path="",
            )
            db.session.add(admin_user)

    if db.session.get(Admin, 1) is None:
        db.session.add(Admin(id=1, gold_price_1g=None, gold_price_8g=None))

    db.session.commit()


def _ensure_legacy_user_columns_sqlite() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        table_exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if table_exists is None:
            return

        existing_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        alter_statements = []
        if "address" not in existing_columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN address VARCHAR(500)")
        if "whatsapp_number" not in existing_columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN whatsapp_number VARCHAR(100)")
        if "social_handle" not in existing_columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN social_handle VARCHAR(255)")
        if "role" not in existing_columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'")

        for statement in alter_statements:
            connection.execute(statement)
        connection.commit()
    finally:
        connection.close()


def _ensure_user_profile_columns() -> None:
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    alter_statements = []
    if "address" not in existing_columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN address VARCHAR(500)")
    if "whatsapp_number" not in existing_columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN whatsapp_number VARCHAR(100)")
    if "social_handle" not in existing_columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN social_handle VARCHAR(255)")
    if "role" not in existing_columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'")

    if not alter_statements:
        return

    with db.engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))


app.register_blueprint(
    create_template_calibration_blueprint(
        admin_required=admin_required,
        list_template_names=list_template_names,
        templates_dir=TEMPLATES_DIR,
        config_path=TEMPLATE_CONFIG_PATH,
    )
)


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("signup.html")

        if User.query.filter_by(username=username).first() is not None:
            flash("Username already exists.", "danger")
            return render_template("signup.html")

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role="user",
            shop_name="",
            address="",
            whatsapp_number="",
            social_handle="",
            logo_path="",
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Account created. Complete your profile.", "success")
        return redirect(url_for("profile"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("login.html")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if current_user.role != "user":
        abort(403)

    if request.method == "POST":
        shop_name = request.form.get("shop_name", "").strip()
        address = request.form.get("address", "").strip()
        whatsapp_number = request.form.get("whatsapp_number", "").strip()
        social_handle = request.form.get("social_handle", "").strip()
        logo_file = request.files.get("logo")

        if not shop_name or not address or not whatsapp_number or not social_handle:
            flash("All profile fields are required.", "danger")
            return render_template("profile.html", user=current_user, is_admin=_is_admin_user(current_user))

        if logo_file and logo_file.filename:
            try:
                current_user.logo_path = _save_logo(logo_file)
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("profile.html", user=current_user, is_admin=_is_admin_user(current_user))

        current_user.shop_name = shop_name
        current_user.address = address
        current_user.whatsapp_number = whatsapp_number
        current_user.social_handle = social_handle
        db.session.commit()

        flash("Profile updated successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("profile.html", user=current_user, is_admin=_is_admin_user(current_user))


@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("admin_dashboard"))

    generated_image = request.args.get("generated", "").strip() or None
    download_name = request.args.get("download_name", "").strip() or None
    templates = list_template_names()
    return render_template(
        "dashboard.html",
        username=current_user.username,
        is_admin=_is_admin_user(current_user),
        generated_image=generated_image,
        download_name=download_name,
        templates=templates,
        has_profile=bool(
            current_user.shop_name
            and current_user.address
            and current_user.whatsapp_number
            and current_user.social_handle
            and current_user.logo_path
        ),
    )


@app.route("/admin", methods=["GET", "POST"])
@app.route("/admin-dashboard", methods=["GET", "POST"])
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        abort(403)

    admin = get_admin_settings()

    if request.method == "POST":
        price_1g_raw = request.form.get("price_1g", "").strip()
        price_8g_raw = request.form.get("price_8g", "").strip()

        if not price_1g_raw or not price_8g_raw:
            flash("Both 1g and 8g gold prices are required.", "danger")
            return redirect(url_for("admin_dashboard"))

        try:
            price_1g = float(price_1g_raw)
            price_8g = float(price_8g_raw)
            if price_1g <= 0 or price_8g <= 0:
                raise ValueError
        except ValueError:
            flash("Please enter valid positive prices.", "danger")
            return redirect(url_for("admin_dashboard"))

        admin.gold_price_1g = float(price_1g)
        admin.gold_price_8g = float(price_8g)
        db.session.commit()
        flash("Gold prices updated.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_dashboard.html", admin=admin)


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    if current_user.role != "user":
        abort(403)

    template_name = request.form.get("template_name", "").strip()

    if not template_name:
        flash("Please select a template.", "danger")
        return redirect(url_for("dashboard"))

    if not (
        current_user.shop_name
        and current_user.address
        and current_user.whatsapp_number
        and current_user.social_handle
        and current_user.logo_path
    ):
        flash("Complete your profile before generating posters.", "danger")
        return redirect(url_for("profile"))

    admin = get_admin_settings()
    if admin.gold_price_1g is None or admin.gold_price_8g is None:
        return "Admin has not configured gold prices yet.", 400

    template_data = get_template(template_name)
    if template_data is None:
        flash("Template not found in configuration", "danger")
        return redirect(url_for("dashboard"))

    os.makedirs(GENERATED_DIR, exist_ok=True)

    try:
        generated_path = generate_poster(
            template_name=template_name,
            template_data=template_data,
            todays_date=format_today_uppercase(),
            price_1g=str(admin.gold_price_1g),
            price_8g=str(admin.gold_price_8g),
            address=current_user.address,
            whatsapp_number=current_user.whatsapp_number,
            social_handle=social_handle_value(current_user.social_handle, current_user.shop_name),
            logo_path=current_user.logo_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("dashboard"))
    except Exception:
        flash("Failed to generate poster. Please try again.", "danger")
        return redirect(url_for("dashboard"))

    generated_filename = os.path.basename(generated_path)
    shop_slug = secure_filename(current_user.shop_name or current_user.username).replace("-", "_").lower() or "poster"
    download_name = f"{shop_slug}_{datetime.now().strftime('%Y%m%d')}.png"

    flash("Poster generated successfully.", "success")
    return redirect(url_for("dashboard", generated=generated_filename, download_name=download_name))


def social_handle_value(handle: str, shop_name: str) -> str:
    clean = (handle or "").strip()
    return clean if clean else (shop_name or "").strip()


@app.route("/download/<path:filename>", methods=["GET"])
@login_required
def download_generated_poster(filename):
    safe_filename = os.path.basename(filename)
    absolute_path = os.path.join(GENERATED_DIR, safe_filename)
    if not os.path.isfile(absolute_path):
        flash("Generated poster file not found.", "danger")
        return redirect(url_for("dashboard"))

    requested_name = request.args.get("download_name", "").strip()
    download_name = secure_filename(requested_name) or safe_filename
    return send_from_directory(
        GENERATED_DIR,
        safe_filename,
        as_attachment=True,
        download_name=download_name,
    )


@app.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/create-admin")
def create_admin():
    admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()
    if admin_user is None:
        admin_user = User(
            username=ADMIN_USERNAME,
            password_hash=generate_password_hash(ADMIN_DEFAULT_PASSWORD),
            role="admin",
            shop_name="Admin",
            address="",
            whatsapp_number="",
            social_handle="",
            logo_path="",
        )
        db.session.add(admin_user)
    else:
        admin_user.password_hash = generate_password_hash(ADMIN_DEFAULT_PASSWORD)
        admin_user.role = "admin"

    if db.session.get(Admin, 1) is None:
        db.session.add(Admin(id=1, gold_price_1g=None, gold_price_8g=None))

    db.session.commit()
    return "Admin user created/updated successfully."


with app.app_context():
    _bootstrap_defaults()


if __name__ == "__main__":
    app.run(debug=True)
