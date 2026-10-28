import sqlite3

from psycopg import sql

from database import (
    DATABASE_TABLES,
    DB_PATH,
    get_migration_connection,
    initialize_database,
)


def migrate():
    initialize_database()

    with sqlite3.connect(DB_PATH) as local_connection:
        local_connection.row_factory = sqlite3.Row
        source_rows = {}
        for table in DATABASE_TABLES:
            source_rows[table] = local_connection.execute(
                f'SELECT * FROM "{table}" ORDER BY id'
            ).fetchall()

    with get_migration_connection() as neon_connection:
        with neon_connection.cursor() as cursor:
            populated_tables = []
            for table in DATABASE_TABLES:
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
                )
                if cursor.fetchone()[0]:
                    populated_tables.append(table)

            if populated_tables:
                raise RuntimeError(
                    "Neon already contains data; refusing to copy SQLite rows into: "
                    + ", ".join(populated_tables)
                )

            for table, rows in source_rows.items():
                if not rows:
                    continue

                columns = rows[0].keys()
                insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                )
                for row in rows:
                    cursor.execute(insert, tuple(row[column] for column in columns))

                cursor.execute(
                    sql.SQL(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                        "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {}"
                    ).format(sql.Identifier(table)),
                    (table,),
                )

    for table, rows in source_rows.items():
        print(f"{table}: migrated {len(rows)} rows")


if __name__ == "__main__":
    migrate()