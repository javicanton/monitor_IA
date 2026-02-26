#!/usr/bin/env python3
"""
Script para inicializar la base de datos y crear un usuario administrador
"""

import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def init_database():
    """Inicializa la base de datos y crea un usuario administrador."""
    
    print("🔧 Inicializando base de datos...")
    print("=" * 50)
    
    try:
        # Importar la aplicación Flask (desde raíz del repo, sin PYTHONPATH)
        from backend.app import app, db
        from backend.models import User
        
        with app.app_context():
            # Crear todas las tablas
            print("📊 Creando tablas de la base de datos...")
            db.create_all()
            print("✅ Tablas creadas correctamente")
            
            # Verificar si ya existe un usuario administrador
            admin_user = User.query.filter_by(role='admin').first()
            
            if admin_user:
                print(f"👤 Usuario administrador ya existe: {admin_user.email}")
            else:
                # Crear usuario administrador por defecto
                print("👑 Creando usuario administrador por defecto...")
                
                admin_email = os.environ.get('ADMIN_EMAIL', 'admin@monitoria.org')
                admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
                admin_name = os.environ.get('ADMIN_NAME', 'Administrador')
                
                admin_user = User(
                    email=admin_email,
                    name=admin_name,
                    role='admin',
                    password=admin_password
                )
                
                # Marcar como verificado y activo
                admin_user.email_verified = True
                admin_user.is_active = True
                
                db.session.add(admin_user)
                db.session.commit()
                
                print(f"✅ Usuario administrador creado:")
                print(f"   - Email: {admin_email}")
                print(f"   - Contraseña: {admin_password}")
                print(f"   - Nombre: {admin_name}")
                print("\n⚠️  IMPORTANTE: Cambia la contraseña después del primer login!")
            
            print("\n🎉 Base de datos inicializada correctamente!")
            return True
            
    except ImportError as e:
        print(f"❌ Error al importar módulos: {e}")
        print("   - Asegúrate de haber instalado las dependencias: pip install -r requirements.txt")
        return False
        
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def main():
    """Función principal."""
    print("🚀 Iniciando configuración de la base de datos")
    print("=" * 60)
    
    success = init_database()
    
    print("\n" + "=" * 60)
    if success:
        print("🎯 Base de datos configurada correctamente")
        print("   Tu aplicación está lista para usar")
    else:
        print("💥 Error al configurar la base de datos")
        print("   Revisa los errores arriba y corrige la configuración")
    
    print("\n📚 Para más información, consulta el README.md")

if __name__ == "__main__":
    main()
