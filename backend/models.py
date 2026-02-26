from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True)  # Nullable para usuarios OAuth
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    is_active = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    # OAuth: proveedor (google, apple, github) e id único del usuario en ese proveedor
    oauth_provider = db.Column(db.String(20), nullable=True)
    oauth_id = db.Column(db.String(120), nullable=True)
    __table_args__ = (db.UniqueConstraint('oauth_provider', 'oauth_id', name='uq_oauth_provider_id'),)

    def __init__(self, email, name, role='user', password=None, oauth_provider=None, oauth_id=None):
        self.email = email
        self.name = name
        self.role = role
        if password:
            self.password = self.hash_password(password)
        else:
            self.password = None
        self.oauth_provider = oauth_provider
        self.oauth_id = oauth_id

    def hash_password(self, password):
        try:
            return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        except Exception as e:
            raise Exception(f"Error hashing password: {str(e)}")

    def check_password(self, password):
        if not self.password:
            return False
        try:
            return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))
        except Exception as e:
            return False

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'oauth_provider': self.oauth_provider
        } 