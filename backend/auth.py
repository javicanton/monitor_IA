from flask import Blueprint, request, jsonify, redirect
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
from models import db, User
from functools import wraps
import os
import secrets
import requests

auth_bp = Blueprint('auth', __name__)
mail = Mail()
serializer = URLSafeTimedSerializer(os.environ.get('SECRET_KEY', 'your-secret-key'))

# URL del frontend para redirigir tras login OAuth (ej. https://app.monitoria.org)
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

def _backend_base():
    """Base URL del backend para redirect_uri OAuth (debe ser la URL pública del API)."""
    return (os.environ.get('BACKEND_URL') or request.host_url or '').rstrip('/')

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user = User.query.get(get_jwt_identity())
        if not current_user or current_user.role != 'admin':
            return jsonify({'error': 'Admin privileges required'}), 403
        return fn(*args, **kwargs)
    return wrapper

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if not data or not all(key in data for key in ['email', 'password', 'name']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        user = User(
            email=data['email'],
            name=data['name'],
            password=data['password']
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Generar token de verificación
        token = serializer.dumps(user.email, salt='email-verification')
        verification_url = f"http://localhost:3000/verify-email/{token}"
        
        # Enviar email de verificación (comentado por ahora)
        # msg = Message(
        #     'Verifica tu email',
        #     recipients=[user.email]
        # )
        # msg.body = f'Por favor, verifica tu email haciendo clic en el siguiente enlace: {verification_url}'
        # mail.send(msg)
        
        return jsonify({'message': 'User registered successfully. Please verify your email.'}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    try:
        email = serializer.loads(token, salt='email-verification', max_age=3600)
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.email_verified = True
            user.is_active = True
            db.session.commit()
            return jsonify({'message': 'Email verified successfully'}), 200
    except:
        return jsonify({'error': 'Invalid or expired token'}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data or not all(key in data for key in ['email', 'password']):
            return jsonify({'error': 'Missing email or password'}), 400
        
        user = User.query.filter_by(email=data['email']).first()
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        if not user.password:
            return jsonify({'error': 'This account uses social login. Use Google, Apple or GitHub.'}), 401
        if not user.check_password(data['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.email_verified:
            return jsonify({'error': 'Please verify your email first'}), 401
        
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        access_token = create_access_token(identity=user.id)
        return jsonify({
            'access_token': access_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if user:
        token = serializer.dumps(user.email, salt='password-reset')
        reset_url = f"http://localhost:3000/reset-password/{token}"
        
        msg = Message(
            'Recuperación de contraseña',
            recipients=[user.email]
        )
        msg.body = f'Para restablecer tu contraseña, haz clic en el siguiente enlace: {reset_url}'
        mail.send(msg)
    
    return jsonify({'message': 'If an account exists with this email, you will receive a password reset link'}), 200

@auth_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset', max_age=3600)
        user = User.query.filter_by(email=email).first()
        
        if user:
            data = request.get_json()
            user.password = user.hash_password(data['new_password'])
            db.session.commit()
            return jsonify({'message': 'Password reset successfully'}), 200
    except:
        return jsonify({'error': 'Invalid or expired token'}), 400

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user = User.query.get(get_jwt_identity())
    return jsonify(user.to_dict()), 200


# --- OAuth: Google, GitHub, Apple ---

def _oauth_find_or_create_user(provider, oauth_id, email, name):
    """Busca usuario por oauth_provider+oauth_id o por email; si no existe, lo crea."""
    user = User.query.filter_by(oauth_provider=provider, oauth_id=str(oauth_id)).first()
    if user:
        return user
    user = User.query.filter_by(email=email).first()
    if user:
        user.oauth_provider = provider
        user.oauth_id = str(oauth_id)
        user.email_verified = True
        user.is_active = True
        db.session.commit()
        return user
    user = User(
        email=email,
        name=name or email.split('@')[0],
        oauth_provider=provider,
        oauth_id=str(oauth_id)
    )
    user.email_verified = True
    user.is_active = True
    db.session.add(user)
    db.session.commit()
    return user


def _redirect_with_token(access_token, error=None):
    if error:
        return redirect(f"{FRONTEND_URL}/login?error={error}")
    return redirect(f"{FRONTEND_URL}/auth/callback?token={access_token}")


@auth_bp.route('/google', methods=['GET'])
def oauth_google():
    base = (os.environ.get('BACKEND_URL') or request.host_url or '').rstrip('/')
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Google OAuth not configured'}), 503
    state = secrets.token_urlsafe(32)
    redirect_uri = f"{base}/api/auth/google/callback"
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
        "&scope=openid%20email%20profile&state=" + state
    )
    return redirect(url)


@auth_bp.route('/google/callback', methods=['GET'])
def oauth_google_callback():
    base = (os.environ.get('BACKEND_URL') or request.host_url or '').rstrip('/')
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    if not client_id or not client_secret:
        return _redirect_with_token(None, error='oauth_not_configured')
    code = request.args.get('code')
    if not code:
        return _redirect_with_token(None, error='missing_code')
    redirect_uri = f"{base}/api/auth/google/callback"
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if r.status_code != 200:
        return _redirect_with_token(None, error='token_exchange_failed')
    data = r.json()
    access = data.get("access_token")
    if not access:
        return _redirect_with_token(None, error='no_access_token')
    r2 = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access}"},
        timeout=10,
    )
    if r2.status_code != 200:
        return _redirect_with_token(None, error='profile_failed')
    profile = r2.json()
    email = profile.get("email") or profile.get("id") + "@google.oauth"
    name = profile.get("name") or (profile.get("email") or "").split("@")[0] or "User"
    user = _oauth_find_or_create_user("google", profile.get("id"), email, name)
    user.last_login = datetime.utcnow()
    db.session.commit()
    token = create_access_token(identity=user.id)
    return _redirect_with_token(token)


@auth_bp.route('/github', methods=['GET'])
def oauth_github():
    base = (os.environ.get('BACKEND_URL') or request.host_url or '').rstrip('/')
    client_id = os.environ.get('GITHUB_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'GitHub OAuth not configured'}), 503
    state = secrets.token_urlsafe(32)
    redirect_uri = f"{base}/api/auth/github/callback"
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={client_id}&redirect_uri={redirect_uri}&scope=user:email&state={state}"
    )
    return redirect(url)


@auth_bp.route('/github/callback', methods=['GET'])
def oauth_github_callback():
    base = (os.environ.get('BACKEND_URL') or request.host_url or '').rstrip('/')
    client_id = os.environ.get('GITHUB_CLIENT_ID')
    client_secret = os.environ.get('GITHUB_CLIENT_SECRET')
    if not client_id or not client_secret:
        return _redirect_with_token(None, error='oauth_not_configured')
    code = request.args.get('code')
    if not code:
        return _redirect_with_token(None, error='missing_code')
    redirect_uri = f"{base}/api/auth/github/callback"
    r = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=10,
    )
    if r.status_code != 200:
        return _redirect_with_token(None, error='token_exchange_failed')
    data = r.json()
    access = data.get("access_token")
    if not access:
        return _redirect_with_token(None, error='no_access_token')
    r2 = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access}", "Accept": "application/vnd.github.v3+json"},
        timeout=10,
    )
    if r2.status_code != 200:
        return _redirect_with_token(None, error='profile_failed')
    profile = r2.json()
    email = profile.get("email")
    if not email:
        r3 = requests.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access}", "Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )
        if r3.status_code == 200 and r3.json():
            for e in r3.json():
                if e.get("primary"):
                    email = e.get("email")
                    break
            if not email and r3.json():
                email = r3.json()[0].get("email")
    if not email:
        email = f"{profile.get('id')}@github.oauth"
    name = profile.get("name") or profile.get("login") or email.split("@")[0]
    user = _oauth_find_or_create_user("github", profile.get("id"), email, name)
    user.last_login = datetime.utcnow()
    db.session.commit()
    token = create_access_token(identity=user.id)
    return _redirect_with_token(token)


@auth_bp.route('/apple', methods=['GET'])
def oauth_apple():
    client_id = os.environ.get('APPLE_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Apple Sign In not configured'}), 503
    base = (os.environ.get('BACKEND_URL') or request.host_url or '').rstrip('/')
    state = secrets.token_urlsafe(32)
    redirect_uri = f"{base}/api/auth/apple/callback"
    url = (
        "https://appleid.apple.com/auth/authorize"
        f"?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code%20id_token"
        "&response_mode=form_post&scope=name%20email&state=" + state
    )
    return redirect(url)


@auth_bp.route('/apple/callback', methods=['POST'])
def oauth_apple_callback():
    code = request.form.get('code')
    if not code:
        return _redirect_with_token(None, error='missing_code')
    client_secret = os.environ.get('APPLE_CLIENT_SECRET')
    if not client_secret:
        return _redirect_with_token(None, error='apple_not_configured')
    base = (os.environ.get('BACKEND_URL') or request.host_url or '').rstrip('/')
    client_id = os.environ.get('APPLE_CLIENT_ID')
    redirect_uri = f"{base}/api/auth/apple/callback"
    r = requests.post(
        "https://appleid.apple.com/auth/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if r.status_code != 200:
        return _redirect_with_token(None, error='token_exchange_failed')
    data = r.json()
    id_token = data.get("id_token")
    if not id_token:
        return _redirect_with_token(None, error='no_id_token')
    import base64
    import json as _json
    try:
        payload_b64 = id_token.split('.')[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return _redirect_with_token(None, error='invalid_id_token')
    sub = payload.get("sub")
    email = payload.get("email") or f"{sub}@apple.oauth"
    name = request.form.get('user')
    if name:
        try:
            name = _json.loads(name).get('name', {}).get('firstName', '') or email.split('@')[0]
        except Exception:
            name = email.split('@')[0]
    else:
        name = email.split('@')[0]
    user = _oauth_find_or_create_user("apple", sub, email, name)
    user.last_login = datetime.utcnow()
    db.session.commit()
    token = create_access_token(identity=user.id)
    return _redirect_with_token(token) 