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
