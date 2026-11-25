"""Explicit, same-origin install assets for the integrated Forecast Lab shell."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

ASSET_TYPES = {
    "gant.webmanifest": "application/manifest+json",
    "gant-sw.js": "application/javascript",
    "gant-192.png": "image/png",
    "gant-512.png": "image/png",
    "gant-maskable-192.png": "image/png",
    "gant-maskable-512.png": "image/png",
    "apple-touch-icon.png": "image/png",
}
REVALIDATE_PATHS = {"/gant-sw.js", "/gant.webmanifest"}


def mount_install_assets(app: FastAPI, dist: Path) -> None:
    def handler(name: str, content_type: str):
        def serve():
            asset = dist / name
            if not asset.is_file():
                raise HTTPException(404)
            headers = {"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"}
            if name == "gant-sw.js":
                headers["Service-Worker-Allowed"] = "/"
            return FileResponse(asset, media_type=content_type, headers=headers)

        return serve

    for name, content_type in ASSET_TYPES.items():
        app.add_api_route(
            "/" + name, handler(name, content_type),
            methods=["GET", "HEAD"], include_in_schema=False,
        )
