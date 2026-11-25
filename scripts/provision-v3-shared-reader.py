"""Provision SELECT-only credentials for 8024. Run manually as the runtime's Windows user."""
import json
import os
import runpy
import secrets
from pathlib import Path

import psycopg
from psycopg import sql

ROLE = "gant_v3_shared_reader"
MARKER = "GANT V3 shared viewer read-only"
GRANTS = {
    "v2_research": ("55434", "forecast_lab_research", [
        "SELECT (id,ticker,data_session,entry_at,snapshot) ON public.lab_cases",
        "SELECT (case_id,method,probability,status,published_at) ON public.lab_arms"]),
    "v2_console": ("55434", "forecast_lab_console", [
        "SELECT (id,schedule_job_id,created_at) ON public.reports",
        "SELECT (id,schedule_config_id) ON public.schedule_jobs",
        "SELECT (id,ticker) ON public.schedule_configs"]),
    "v3_archive": ("55436", "forecast_lab_research", [
        "SELECT ON public.v3_issue_runs, public.v3_issues"]),
}


def provision(base):
    runtime = base / "TradingAgentsV3"
    target = runtime / "shared-read"
    target.mkdir(exist_ok=True)
    runpy.run_path(str(Path(__file__).with_name("initialize-v3-runtime.py")))["restrict_directory"](target)
    config = target / "logins.json"
    if config.is_file():
        credentials = json.loads(config.read_text(encoding="utf-8"))
    else:
        v2 = secrets.token_urlsafe(36)
        credentials = {"v2_research": v2, "v2_console": v2, "v3_archive": secrets.token_urlsafe(36)}
        with config.open("x", encoding="utf-8") as stream:
            json.dump(credentials, stream)
    if set(credentials) != set(GRANTS) or credentials["v2_research"] != credentials["v2_console"]:
        raise RuntimeError("Invalid reader configuration")
    for key, (port, database, grants) in GRANTS.items():
        v3 = key == "v3_archive"
        admin_root = runtime if v3 else base / "TradingAgentsForecastLab"
        admin = "gant_v3_admin" if v3 else "forecast_lab_admin"
        with psycopg.connect(host="127.0.0.1", port=port, user=admin, dbname=database,
                password=(admin_root / "cluster-admin.pw").read_text().strip(), connect_timeout=3) as conn:
            row = conn.execute("""SELECT shobj_description(oid,'pg_authid'),rolsuper,rolcreatedb,
                rolcreaterole,rolreplication,rolbypassrls,EXISTS(SELECT FROM pg_auth_members WHERE member=r.oid)
                FROM pg_roles r WHERE rolname=%s""", (ROLE,)).fetchone()
            if row and (row[0] != MARKER or any(row[1:])):
                raise RuntimeError("Existing role identity or grants differ")
            if not row:
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT PASSWORD {}").format(
                    sql.Identifier(ROLE), sql.Literal(credentials[key])))
                conn.execute(sql.SQL("COMMENT ON ROLE {} IS {}").format(sql.Identifier(ROLE), sql.Literal(MARKER)))
            conn.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only TO on").format(sql.Identifier(ROLE)))
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(ROLE)))
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(ROLE)))
            for grant in grants:
                conn.execute(sql.SQL("GRANT " + grant + " TO {}").format(sql.Identifier(ROLE)))
        # Check the stored password on rerun too. Never reset an existing role silently.
        with psycopg.connect(host="127.0.0.1", port=port, user=ROLE, dbname=database,
                             password=credentials[key], connect_timeout=3) as conn:
            if not conn.execute("SHOW transaction_read_only").fetchone()[0] == "on":
                raise RuntimeError("Read-only sessions are required")


if __name__ == "__main__":
    try:
        provision(Path(os.environ["LOCALAPPDATA"]))
    except Exception as exc:
        raise SystemExit(f"Reader provisioning failed ({type(exc).__name__}); verify local roles and protected configuration.") from None
    print("Dedicated shared viewer reader is ready.")
