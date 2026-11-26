"""V3 read-only presentation of V2. Numeric identities always belong to V2."""
import json
import re
from datetime import datetime
from functools import partial
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, build_opener
from urllib.error import HTTPError, URLError

from fastapi import HTTPException
from .issue_collector import EXPORT, SOURCE
from .public_app import create_app, read_upstream, NoRedirect
from .public_projection import instant, instrument

V2 = "http://127.0.0.1:8014"
CORE = "http://127.0.0.1:8024"
MAX_IDS = 40


def empty_archive(as_of, status):
    return {key: {"as_of": as_of, "status": status, "items": [], "collected_at": None,
                  "source": source, "provenance": "v3_archive_as_of"}
            for key, source in (("issues", SOURCE), ("last30days", EXPORT))}


def private_get(path):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(CORE + path, timeout=5) as response:
            data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError("Oversized supplemental response")
        return json.loads(data)
    except HTTPError as exc:
        raise HTTPException(404 if exc.code == 404 else 503) from None
    except (ValueError, URLError, OSError):
        raise HTTPException(503) from None


class RemoteSupplement:
    def forecast_tickers(self):
        return private_get("/api/forecast-tickers")

    def probabilities(self, ids):
        return private_get("/_shared/probabilities?" + urlencode({"ids": ",".join(map(str, ids))}))

    def evidence(self, kind, record_id):
        return private_get(f"/_shared/{kind}/{record_id}")


class SharedReader:
    def __init__(self, supplement, upstream=partial(read_upstream, origin=V2)):
        self.supplement = supplement
        self.upstream = upstream

    def __call__(self, path):
        route = urlsplit(path).path
        if path == "/api/forecast-tickers":
            return self.supplement.forecast_tickers()
        if match := re.fullmatch(r"/api/report-sources/([1-9][0-9]{0,15})", route):
            return self.supplement.evidence("report", int(match[1]))
        data = self.upstream(path)
        if route == "/api/cases" and isinstance(data, list):
            missing = [row for row in data[:200] if isinstance(row, dict)
                       and type(row.get("id")) is int and "forecast_probabilities" not in row]
            for start in range(0, len(missing), MAX_IDS):
                group = missing[start:start + MAX_IDS]
                values = self.supplement.probabilities([row["id"] for row in group])
                for row in group:
                    source = values.get(str(row["id"]))
                    if (not source or source["ticker"] != row.get("ticker")
                            or source["data_session"] != row.get("data_session")):
                        raise HTTPException(503, "Published list unavailable")
                    row["forecast_probabilities"] = source["probabilities"]
        elif re.fullmatch(r"/api/cases/[1-9][0-9]{0,15}", route) and isinstance(data, dict):
            cutoff = instant((data.get("snapshot") or {}).get("observed_at"))
            symbol = instrument(data)
            if cutoff and symbol and data.get("id") == int(route.rsplit("/", 1)[1]):
                evidence = empty_archive(cutoff, "failed")
                try:
                    found = self.supplement.evidence("case", data["id"])
                    if (found["ticker"] == symbol["ticker"] and found["id"] == data["id"]
                            and datetime.fromisoformat(found["as_of"]) == datetime.fromisoformat(cutoff)):
                        evidence = {k: found[k] for k in evidence}
                except (HTTPException, KeyError, ValueError, TypeError):
                    pass
                data.update(evidence)
            data["forecast_probabilities"] = {
                a["method"]: a["probability"] for a in data.get("arms", [])
                if a.get("status") == "published" and instant(a.get("published_at"))
                and instant(data.get("entry_open_at"))
                and datetime.fromisoformat(a["published_at"]) < datetime.fromisoformat(data["entry_open_at"])
            }
        return data


def build_shared_core():
    import os
    from .shared_archive import LocalSupplement

    # Only this process receives the location of protected, SELECT-only logins.
    local = LocalSupplement(Path(os.environ["GANT_SHARED_READ_CONFIG"]))
    app = create_app(SharedReader(local), workspace_origin=V2, shared_role="core")

    @app.get("/_shared/probabilities")
    def probabilities(ids: str):
        if not re.fullmatch(r"[1-9][0-9]{0,15}(?:,[1-9][0-9]{0,15}){0,39}", ids):
            raise HTTPException(400)
        return local.probabilities([int(i) for i in ids.split(",")])

    @app.get("/_shared/{kind}/{record_id:int}")
    def evidence(kind: str, record_id: int):
        if kind not in ("case", "report") or not 0 < record_id < 10**16:
            raise HTTPException(404)
        return local.evidence(kind, record_id)

    return app


def build_shared_edge():
    return create_app(SharedReader(RemoteSupplement()), workspace_origin=V2, shared_role="edge")
