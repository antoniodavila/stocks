#!/usr/bin/env python3
"""Inicializa la base de datos seasonal_stocks ejecutando schema.sql."""

import sys
import os
from pathlib import Path

# Añadir scripts/ al path para importar config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from config import DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME

import mysql.connector


def init_db():
    schema_path = Path(__file__).resolve().parent / 'schema.sql'
    if not schema_path.exists():
        print(f"ERROR: {schema_path} not found")
        sys.exit(1)

    sql = schema_path.read_text(encoding='utf-8')

    # Conectar sin especificar base de datos
    conn = mysql.connector.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        charset='utf8mb4'
    )
    cursor = conn.cursor()

    # Ejecutar statement por statement
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    for stmt in statements:
        try:
            cursor.execute(stmt)
            # Detectar nombre de tabla creada
            lower = stmt.lower()
            if 'create table' in lower:
                # Extraer nombre de tabla
                parts = lower.split('create table')[-1].split('(')[0]
                table_name = parts.replace('if not exists', '').strip().strip('`')
                print(f"  ✓ Table '{table_name}' created")
            elif 'create database' in lower:
                print(f"  ✓ Database '{DB_NAME}' ready")
            elif 'use ' in lower:
                pass  # silencioso
        except mysql.connector.Error as e:
            if e.errno == 1050:  # Table already exists
                print(f"  ~ Table already exists, skipping")
            else:
                print(f"  ✗ Error: {e.msg}")
                conn.rollback()
                cursor.close()
                conn.close()
                sys.exit(1)

    conn.commit()
    cursor.close()
    conn.close()
    print(f"\n  ✓ Schema initialization complete")


if __name__ == '__main__':
    init_db()
