#!/usr/bin/env python3
"""Elimina y recrea todas las tablas. SOLO para desarrollo local."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from config import DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME

import mysql.connector


def reset_db():
    confirm = input("WARNING: This will delete ALL data. Type 'yes' to confirm: ")
    if confirm.strip().lower() != 'yes':
        print("Aborted.")
        sys.exit(0)

    conn = mysql.connector.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset='utf8mb4'
    )
    cursor = conn.cursor()

    # Desactivar FK checks para poder dropear en cualquier orden
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
        print(f"  ✓ Dropped '{table}'")

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cursor.close()
    conn.close()

    print(f"\n  ✓ All tables dropped")

    # Recrear schema
    print("\nRecreating schema...")
    from init_db import init_db
    init_db()


if __name__ == '__main__':
    reset_db()
