import os
import sqlite3

import psycopg
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "seitorri.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "postgres_schema.sql")
DATABASE_TABLES = (
    "allegati_circuiti",
    "allegati_gare",
    "allegati_soci",
    "certificati",
    "circuiti",
    "gare",
    "partecipanti_gare",
    
    "partecipazioni",
    "soci",
    "trasferte",
    "utenti",
)

load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(BASE_DIR, ".env.local"))


class _HybridRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def _hybrid_row_factory(cursor):
    if cursor.description is None:
        return lambda values: values
    columns = [column.name for column in cursor.description]

    def make_row(values):
        return _HybridRow(zip(columns, values))

    return make_row


class _QmarkCursor(psycopg.Cursor):
    def execute(self, query, params=None, *, prepare=None, binary=False):
        if isinstance(query, str):
            query = query.replace("?", "%s")
        return super().execute(
            query,
            params,
            prepare=prepare,
            binary=binary,
        )


def _connect(connection_string):
    return psycopg.connect(
        connection_string,
        row_factory=_hybrid_row_factory,
        cursor_factory=_QmarkCursor,
    )


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return _connect(database_url)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_migration_connection():
    connection_string = os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("DATABASE_URL")
    if not connection_string:
        raise RuntimeError("DATABASE_URL is required to migrate to Neon")
    return _connect(connection_string)


def initialize_database():
    if not os.getenv("DATABASE_URL"):
        return

    with get_migration_connection() as conn:
        with conn.cursor() as cursor:
            with open(SCHEMA_PATH, encoding="utf-8") as schema_file:
                for statement in schema_file.read().split(";"):
                    if statement.strip():
                        cursor.execute(statement)