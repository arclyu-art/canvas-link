"""Allowlisted releases: never archive a working directory or a user's AppData."""
import hashlib
import os
from pathlib import Path
import sys
import types
import ntpath
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ("pyproject.toml", "requirements-windows.lock", "launcher.py", "build_windows.py",
         "release.py", "README.md", "LICENSE", "PRIVACY.md", "SECURITY.md", ".gitignore",
         ".github/workflows/windows.yml")
FORBIDDEN_NAMES = {"config.json", "session.json", "cookies.json", "snapshot.json", "validation.json", ".env"}


def private_markers():
    home = str(Path.home())
    # Hosted Windows Python DLLs can contain the public runneradmin build prefix.
    # That agent identity is not a developer's private profile; own code paths
    # are still required to be relative by audit_frozen_code below.
    if os.environ.get("GITHUB_ACTIONS")=="true" and Path.home().name.lower() in {"runneradmin","runner","vssadministrator"}:
        return []
    values = {home.lower(), home.replace("\\", "/").lower()}
    return [v.encode("utf-8") for v in values if len(v)>5]


def audit_file(path):
    if path.is_symlink():
        raise ValueError("Symlinks are not allowed in a release.")
    if path.name.lower() in FORBIDDEN_NAMES or path.suffix.lower() in (".dpapi", ".tmp", ".log"):
        raise ValueError("Runtime/private state found in release inputs.")
    markers = private_markers()
    previous = b""
    with path.open("rb") as stream:
        while data := stream.read(1024*1024):
            sample = (previous + data).lower()
            if any(m in sample for m in markers):
                raise ValueError("A private build-machine home path was found in release file: " + path.name)
            previous = sample[-2048:]


def source_files(root=ROOT):
    selected = [root/name for name in FILES]
    selected += sorted((root/"src/canvaslink").glob("*.py"))
    selected += sorted((root/"tests").glob("*.py"))
    for path in selected:
        if not path.is_file(): raise FileNotFoundError(path.name)
        if not path.resolve().is_relative_to(root.resolve()): raise ValueError("Source escaped project directory.")
        audit_file(path)
    return selected


def audit_frozen_code(executable):
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(executable))
    pyz = archive.open_embedded_archive("PYZ.pyz")
    def visit(code):
        if not isinstance(code,types.CodeType):return
        filename=code.co_filename.lower().replace("\\","/")
        if ntpath.isabs(filename):
            raise ValueError("Absolute source path embedded in bundled CanvasLink code.")
        if any(marker.decode().replace("\\","/") in filename for marker in private_markers()):
            raise ValueError("Build-machine path embedded in bundled Python code.")
        for item in code.co_consts:visit(item)
    for name in pyz.toc:
        if name.startswith("canvaslink"):
            visit(pyz.extract(name))


def main():
    release=ROOT/"releases";release.mkdir(exist_ok=True)
    source=release/"CanvasLink-source.zip"
    with zipfile.ZipFile(source,"w",zipfile.ZIP_DEFLATED) as z:
        for path in source_files():z.write(path,Path("canvas-link")/path.relative_to(ROOT))
    outputs=[source]
    app=ROOT/"dist/CanvasLink"
    if (app/"CanvasLink.exe").exists():
        audit_frozen_code(app/"CanvasLink.exe")
        windows=release/"CanvasLink-windows-x64.zip"
        with zipfile.ZipFile(windows,"w",zipfile.ZIP_DEFLATED) as z:
            for path in sorted(app.rglob("*")):
                if path.is_file():
                    audit_file(path);z.write(path,Path("CanvasLink")/path.relative_to(app))
            for name in ("README.md","LICENSE","PRIVACY.md","SECURITY.md"):
                z.write(ROOT/name,Path("CanvasLink")/name)
        outputs.append(windows)
    sums=[]
    for path in outputs:
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None:raise ValueError("Archive integrity check failed.")
        digest=hashlib.file_digest(path.open("rb"),"sha256").hexdigest()
        sums.append(digest+"  "+path.name)
        print(f"Created {path.name}: {path.stat().st_size/1048576:.2f} MiB")
    (release/"SHA256SUMS.txt").write_text("\n".join(sums)+"\n",encoding="ascii")
    print("Allowlist, private-state, build-path and ZIP-integrity checks passed.")


if __name__=="__main__":main()
