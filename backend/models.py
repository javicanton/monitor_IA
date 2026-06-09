from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt

db = SQLAlchemy()


# --- Tablas para dataset Telegram (PostgreSQL) ---

class Channel(db.Model):
    """Canal de Telegram. Normalizado para evitar repetir el nombre en cada mensaje."""
    __tablename__ = 'channels'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='channel', lazy='dynamic')


class Message(db.Model):
    """Mensaje de Telegram. La clave natural es (message_id, channel_id)."""
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.BigInteger, nullable=False, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False, index=True)
    message_text = db.Column(db.Text)
    date_sent = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    views = db.Column(db.Integer, default=0, index=True)
    forwards = db.Column(db.Integer, default=0, index=True)
    replies = db.Column(db.Integer, default=0)
    url = db.Column(db.Text)
    embed = db.Column(db.Text)
    score = db.Column(db.Float, default=0.0)
    label = db.Column(db.SmallInteger, nullable=True)
    media_type = db.Column(db.String(100))
    creation_date = db.Column(db.DateTime(timezone=True))
    edit_date = db.Column(db.DateTime(timezone=True))
    average_views = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('message_id', 'channel_id', name='uq_message_channel'),
    )


class MessageTopic(db.Model):
    """Asignación de topic a mensaje (compatible con message_topics.csv)."""
    __tablename__ = 'message_topics'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False, index=True)
    topic_id = db.Column(db.Integer, nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint('message_id', 'topic_id', name='uq_message_topic'),)


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