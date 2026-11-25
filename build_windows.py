"""Build an onedir Windows app; never collect personal state or an existing browser profile."""
from pathlib import Path
import os
from importlib.metadata import distributions
import shutil
import subprocess
import sys

if __name__ == "__main__":
    if os.name != "nt": raise SystemExit("Build on Windows x64.")
    root=Path(__file__).resolve().parent
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--clean","--onedir",
        "--name","CanvasLink","--distpath",str(root/"dist"),"--workpath",str(root/"build/work"),
        "--specpath",str(root/"build"),"--paths",str(root/"src"),"--collect-all","playwright",
        "--copy-metadata","mcp","--copy-metadata","playwright",str(root/"launcher.py")],check=True,cwd=root)
    notices=root/"dist/CanvasLink/third-party-licenses";notices.mkdir(exist_ok=True)
    names=[]
    for dist in distributions():
        name=dist.metadata['Name']
        if name.lower() in ('canvaslink-local','pip'):continue
        names.append(f"{name}=={dist.version}")
        for entry in dist.files or []:
            if entry.name.lower().startswith(('license','copying','notice')):
                original=dist.locate_file(entry)
                if original.is_file() and original.stat().st_size<2*1024*1024:
                    target=notices/name/entry.name;target.parent.mkdir(exist_ok=True)
                    shutil.copyfile(original,target)
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.is_file():shutil.copyfile(python_license,notices/'Python-LICENSE.txt')
    (notices/'DEPENDENCIES.txt').write_text('\n'.join(sorted(names))+'\n',encoding='utf-8')
