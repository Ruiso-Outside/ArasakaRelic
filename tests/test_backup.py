"""Backup, hardlinks, limite de fotos e restauracao numa pasta pessoal de teste.   python tests/test_backup.py"""
import os
import sys
import tempfile
import time
from pathlib import Path

T = Path(tempfile.mkdtemp())
home, dest = T / "home", T / "dest"
(home / "Documentos" / "sub").mkdir(parents=True)
(home / ".config" / "arasaka-holo").mkdir(parents=True)
dest.mkdir()
(home / "Documentos" / "a.txt").write_text("um")
(home / "Documentos" / "sub" / "b.txt").write_text("dois")
(home / ".config" / "arasaka-holo" / "identity.key").write_text("chave")
(home / ".config" / "user-dirs.dirs").write_text('XDG_DOCUMENTS_DIR="$HOME/Documentos"\n')
os.environ.update(HOME=str(home), ARASAKA_RELIC_HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                  XDG_DATA_HOME=str(home / ".local/share"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from arasaka_relic import core as C  # noqa: E402

cfg = C.Config()
cfg["dest"], cfg["keep"] = str(dest), 2
s1 = C.run_backup(cfg)
time.sleep(1.1)
(home / "Documentos" / "a.txt").write_text("mudou")
s2 = C.run_backup(cfg)
assert s1.status == s2.status == "ok"
same = lambda p: os.stat(s1.path / p).st_ino == os.stat(s2.path / p).st_ino  # noqa: E731
assert same("Documentos/sub/b.txt"), "arquivo igual devia ser hardlink"
assert not same("Documentos/a.txt"), "arquivo mudado devia ser copia nova"
assert (s2.path / ".config/arasaka-holo/identity.key").read_text() == "chave"
time.sleep(1.1)
C.run_backup(cfg)
assert len(C.list_snapshots(cfg["dest"])) == 2, "limite de fotos"
(home / "Documentos" / "sub" / "b.txt").unlink()
last = C.list_snapshots(cfg["dest"])[0]
C.restore(last.path, last.path / "Documentos/sub/b.txt")
assert (home / "Documentos" / "sub" / "b.txt").read_text() == "dois"

# copia em Python (a do Windows, sem rsync): a mesma foto com hardlinks, exclusoes e restauracao
os.environ["ARASAKA_RELIC_NO_RSYNC"] = "1"
dest2 = T / "dest2"
dest2.mkdir()
(home / "Documentos" / "lixo.tmp").write_text("x")
cfg["dest"] = str(dest2)
p1 = C.run_backup(cfg)
time.sleep(1.1)
(home / "Documentos" / "a.txt").write_text("de novo")
p2 = C.run_backup(cfg)
assert p1.status == p2.status == "ok"
same2 = lambda p: os.stat(p1.path / p).st_ino == os.stat(p2.path / p).st_ino  # noqa: E731
assert same2("Documentos/sub/b.txt"), "copia em Python: arquivo igual devia ser hardlink"
assert not same2("Documentos/a.txt") and (p2.path / "Documentos/a.txt").read_text() == "de novo"
assert not (p2.path / "Documentos/lixo.tmp").exists(), "*.tmp fica fora"
(home / "Documentos" / "sub" / "b.txt").unlink()
C.restore(p2.path, p2.path / "Documentos/sub")
assert (home / "Documentos" / "sub" / "b.txt").read_text() == "dois"
print("OK: backup, hardlinks, limite de fotos e restauracao (rsync e copia em Python)")
