from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)
    shop_name = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(500), nullable=True)
    whatsapp_number = db.Column(db.String(100), nullable=True)
    social_handle = db.Column(db.String(255), nullable=True)
    logo_path = db.Column(db.String(500), nullable=True)


class Admin(db.Model):
    __tablename__ = "admin"

    id = db.Column(db.Integer, primary_key=True)
    gold_price_1g = db.Column(db.Float, nullable=True)
    gold_price_8g = db.Column(db.Float, nullable=True)
    full_name = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(100), nullable=True)
    company = db.Column(db.String(255), nullable=True)
    logo_path = db.Column(db.String(500), nullable=True)


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    file_name = db.Column(db.String(200), nullable=False, unique=True)
    category = db.Column(db.String(50), nullable=False, default="General")
    font_size = db.Column(db.Integer, nullable=True)
    font_color = db.Column(db.String(20), nullable=True)
    text_x = db.Column(db.Integer, nullable=True)
    text_y = db.Column(db.Integer, nullable=True)
    logo_x = db.Column(db.Integer, nullable=True)
    logo_y = db.Column(db.Integer, nullable=True)
