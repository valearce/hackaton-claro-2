"""Persistencia local y Vercel Blob privado; los resultados sobreviven al proceso."""
import os
from pathlib import Path, PurePosixPath
from uuid import uuid4
import json


class Almacen:
    def __init__(self, root):
        self.cloud = bool(os.environ.get("VERCEL"))
        self.blob = bool(os.environ.get("BLOB_READ_WRITE_TOKEN") or os.environ.get("BLOB_STORE_ID"))
        self.local = Path(os.environ.get("NBA_STORAGE_DIR", str(root / ".local/consola")))
        environment = os.environ.get("VERCEL_ENV", "local")
        branch = os.environ.get("VERCEL_GIT_COMMIT_REF", "default").replace("/", "-")
        self.prefix = f"nba/v1/{environment}/" + (f"{branch}/" if environment == "preview" else "")

    def key(self, name):
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError("Ruta de almacenamiento no válida")
        return self.prefix + name

    def read(self, name):
        key = self.key(name)
        if self.blob:
            from vercel.blob import sync, BlobNotFoundError
            try:
                return sync.get_blob(key, access="private").body
            except BlobNotFoundError:
                return None
        if self.cloud:
            raise RuntimeError("Conecta el almacenamiento privado de Vercel al proyecto")
        path = self.local / key
        return path.read_bytes() if path.is_file() else None

    def write(self, name, data, content_type="application/octet-stream"):
        key = self.key(name)
        if self.blob:
            from vercel.blob import sync
            sync.put_blob(key, data, access="private", content_type=content_type,
                          add_random_suffix=False, allow_overwrite=True)
            return
        if self.cloud:
            raise RuntimeError("Conecta el almacenamiento privado de Vercel al proyecto")
        path = self.local / key
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)

    def json(self, name):
        raw = self.read(name)
        return json.loads(raw) if raw is not None else None

    def delete(self, name):
        key = self.key(name)
        if self.blob:
            from vercel.blob import sync
            sync.delete_blob(key)
        elif self.cloud:
            raise RuntimeError("Conecta el almacenamiento privado de Vercel al proyecto")
        else:
            (self.local / key).unlink(missing_ok=True)

    def write_json(self, name, value):
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        self.write(name, raw, "application/json")

    def keys(self, prefix):
        key = self.key(prefix)
        if self.blob:
            from vercel.blob import sync
            return [item.pathname.removeprefix(self.prefix) for item in sync.query_blobs(prefix=key)]
        if self.cloud:
            raise RuntimeError("Conecta el almacenamiento privado de Vercel al proyecto")
        directory = self.local / key
        return [str(path.relative_to(self.local / self.prefix)).replace("\\", "/")
                for path in directory.rglob("*.json")] if directory.is_dir() else []
