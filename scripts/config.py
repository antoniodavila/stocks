import os
from pathlib import Path
from dotenv import load_dotenv
import mysql.connector

# Cargar .env desde la raíz del proyecto
_env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(_env_path)

# Base de datos
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_NAME = os.getenv('DB_NAME', 'seasonal_stocks')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', '')

# API Keys
FMP_API_KEY = os.getenv('FMP_API_KEY', '')
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '')
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', '')

# AWS
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET', 'seasonal-stocks-data')

# Dashboard
DASHBOARD_TOKEN = os.getenv('DASHBOARD_TOKEN', 'local_dev_token_changeme')


def get_db_connection():
    """Retorna conexión MySQL/MariaDB."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        charset='utf8mb4'
    )


if __name__ == '__main__':
    print(f"DB: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        print(f"Conexion OK — MySQL/MariaDB {version}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error de conexion: {e}")
