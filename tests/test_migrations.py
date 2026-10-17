import sqlite3

from core.storage_sqlite import migrate


def test_migrations_apply_once_in_order(tmp_path):
    (tmp_path / "001_a.sql").write_text("CREATE TABLE a (x INTEGER);")
    (tmp_path / "002_b.sql").write_text("ALTER TABLE a ADD COLUMN y TEXT; INSERT INTO a VALUES (1, 'k');")
    conn = sqlite3.connect(":memory:")
    assert migrate(conn, tmp_path) == ["001_a.sql", "002_b.sql"]
    assert migrate(conn, tmp_path) == []
    assert conn.execute("SELECT x, y FROM a").fetchall() == [(1, "k")]


def test_broken_migration_leaves_nothing_half_done(tmp_path):
    (tmp_path / "001_a.sql").write_text("CREATE TABLE a (x INTEGER);")
    (tmp_path / "002_bad.sql").write_text("INSERT INTO a VALUES (1); THIS IS NOT SQL;")
    conn = sqlite3.connect(":memory:")
    try:
        migrate(conn, tmp_path)
    except sqlite3.Error:
        pass
    assert conn.execute("SELECT count(*) FROM a").fetchone() == (0,)
    names = [r[0] for r in conn.execute("SELECT name FROM schema_migrations")]
    assert names == ["001_a.sql"]


def test_failed_migration_rolls_back_schema_changes_too(tmp_path):
    (tmp_path / "001_bad.sql").write_text("CREATE TABLE a (x INTEGER); THIS IS NOT SQL;")
    conn = sqlite3.connect(":memory:")
    try:
        migrate(conn, tmp_path)
    except sqlite3.Error:
        pass
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert "a" not in tables
