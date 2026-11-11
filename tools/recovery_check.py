"""Non-destructive synthetic-database dump/restore check. Never drops a database."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


def main():
    url = make_url(os.environ["RECOVERY_SOURCE_URL"])
    if not url.database.endswith("_test"):
        raise RuntimeError("Recovery checks only accept a dedicated synthetic *_test source")
    target = "constructpm_restore_" + uuid4().hex[:8] + "_test"
    env = {**os.environ, "PGHOST":url.host or "127.0.0.1", "PGPORT":str(url.port or 5432), "PGUSER":url.username or "postgres"}
    if url.password:
        env["PGPASSWORD"] = url.password
    pg_bin = Path(os.environ["PG_BIN"])
    suffix = ".exe" if os.name == "nt" else ""
    options = {"host":env["PGHOST"], "port":env["PGPORT"], "user":env["PGUSER"], "password":url.password}
    with psycopg.connect(dbname="postgres", autocommit=True, **options) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
    work = Path(os.environ.get("RECOVERY_WORK_DIR", "work/recovery"))
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as folder:
        dump = str(Path(folder) / "foundation.dump")
        subprocess.run([str(pg_bin / ("pg_dump"+suffix)), "-Fc", "-d", url.database, "-f", dump], env=env, check=True)
        subprocess.run([str(pg_bin / ("pg_restore"+suffix)), "--exit-on-error", "-d", target, dump], env=env, check=True)
    def snapshot(database):
        with psycopg.connect(dbname=database, **options) as db:
            names = [row[0] for row in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
            values = {}
            for name in names:
                rows = db.execute(sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text").format(sql.Identifier(name))).fetchall()
                values[name] = {"rows":len(rows), "hash":hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()}
            policies = db.execute("SELECT tablename,policyname,cmd,qual,with_check FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname").fetchall()
            return {"tables":values,"policy_hash":hashlib.sha256(json.dumps(policies,default=str).encode()).hexdigest()}
    source = snapshot(url.database)
    restored = snapshot(target)
    assert source == restored, "Restored content or policies differ"
    with psycopg.connect(dbname=target, **{**options,"user":"constructpm_app","password":os.environ.get("RECOVERY_APP_PASSWORD")}) as db:
        assert db.execute("SELECT count(*) FROM projects").fetchone()[0] == 0, "Missing-context RLS failed after restore"
        roles = db.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
        assert roles == (False,False)
    report = {"result":"PASS", "source":url.database, "restored_database":target, **source,
              "note":"Synthetic local restore only; this is not proof of production RPO/RTO or object-store recovery."}
    report_path = work / "recovery-result.json"
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()

