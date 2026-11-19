"""
ARASAKA RELIC // nucleo: backups com rsync em "fotos" (snapshots) com hardlinks.

Cada backup e uma pasta com a data (DESTINO/ArasakaRelic/<pc>/2026-11-19_083000) que parece uma copia completa,
mas os arquivos que nao mudaram desde o anterior sao hardlinks: so o que mudou ocupa espaco novo.
Restaurar e copiar de volta. Nada sai do PC: o destino e uma pasta ou um HD/pendrive.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

APP_ID = "arasaka-relic"
APP_NAME = "ARASAKA RELIC"
VERSION = "1.0.0"

HOME = Path(os.environ.get("ARASAKA_RELIC_HOME") or Path.home())
DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / APP_ID
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / APP_ID
ASSETS = Path(__file__).resolve().parent / "assets"
LOG_DIR = DATA / "logs"
STAMP = "%Y-%m-%d_%H%M%S"
SNAP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")


# ================================================================ pastas do usuario
def user_dir(key: str, fallback: str) -> Path:
    """Pastas do xdg-user-dirs (Documentos, Imagens...) no idioma do sistema."""
    try:
        txt = (Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "user-dirs.dirs").read_text(encoding="utf-8")
        m = re.search(rf'^XDG_{key}_DIR="?([^"\n]+)"?', txt, re.M)
        if m:
            return Path(m.group(1).replace("$HOME", str(HOME)))
    except OSError:
        pass
    return HOME / fallback


@dataclass
class Source:
    key: str
    title: str
    paths: list[Path]
    default: bool
    note: str = ""


def presets() -> list[Source]:
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
    share = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    arasaka_cfg = sorted(p for p in cfg.glob("arasaka*") if p.is_dir() and p.name != APP_ID)
    return [
        Source("documents", "Documentos", [user_dir("DOCUMENTS", "Documents")], True),
        Source("pictures", "Imagens", [user_dir("PICTURES", "Pictures")], True),
        Source("music", "Músicas", [user_dir("MUSIC", "Music")], True),
        Source("videos", "Vídeos", [user_dir("VIDEOS", "Videos")], True),
        Source("desktop", "Área de Trabalho", [user_dir("DESKTOP", "Desktop")], True),
        Source("downloads", "Downloads", [user_dir("DOWNLOAD", "Downloads")], False, "costuma ser grande e fácil de baixar de novo"),
        Source("holo", "Chave e conversas fixadas do Holo", [cfg / "arasaka-holo"], True, "sem a chave, você perde o nick"),
        Source("arasaka", "Configurações dos apps Arasaka", arasaka_cfg, True, "Daemon, Bridge, Blackwall, tema..."),
        Source("central", "Dados dos módulos da Central", [cfg / "Arasaka Central" / "module-data"], True, "finanças, macros, jogos..."),
        Source("bridge", "Programas Windows do Bridge", [share / "arasaka-bridge" / "containers"], False, "pode ter vários GB"),
        Source("vms", "Máquinas virtuais do Blackwall", [share / "arasaka-blackwall" / "machines"], False, "discos de dezenas de GB"),
        Source("ssh", "Chaves SSH e Git", [HOME / ".ssh", HOME / ".gitconfig"], True),
    ]


DEFAULT_EXCLUDES = ["*.tmp", "*.part", "*.crdownload", "node_modules/", "__pycache__/", ".cache/", "Cache/",
                    "CachedData/", "GPUCache/", ".venv/", "venv/", "*.iso", "Trash/", ".Trash-*/"]


# ================================================================ configuracao
class Config:
    def __init__(self):
        self.path = CONFIG_DIR / "config.json"
        self.data = {"dest": "", "keep": 14, "schedule": False, "sources": [s.key for s in presets() if s.default],
                     "custom": [], "excludes": list(DEFAULT_EXCLUDES), "last": None}
        try:
            self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
        except Exception:
            pass

    def __getitem__(self, k):
        return self.data.get(k)

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def selected_paths(self) -> list[Path]:
        out: list[Path] = []
        for s in presets():
            if s.key in self.data["sources"]:
                out += s.paths
        out += [Path(p).expanduser() for p in self.data.get("custom", [])]
        seen, uniq = set(), []
        for p in out:
            if p.exists() and str(p) not in seen:
                seen.add(str(p))
                uniq.append(p)
        return uniq


def machine_name() -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", socket.gethostname()) or "pc"


def repo_dir(dest: str | Path) -> Path:
    return Path(dest).expanduser() / "ArasakaRelic" / machine_name()


# ================================================================ snapshots
@dataclass
class Snapshot:
    path: Path
    when: float
    status: str = "ok"
    size: int = 0
    files: int = 0
    sources: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def label(self) -> str:
        return time.strftime("%d/%m/%Y  %H:%M", time.localtime(self.when))


def list_snapshots(dest: str | Path) -> list[Snapshot]:
    root = repo_dir(dest)
    out = []
    try:
        names = sorted((p for p in root.iterdir() if p.is_dir() and SNAP_RE.match(p.name)), reverse=True)
    except OSError:
        return []
    for p in names:
        try:
            when = time.mktime(time.strptime(p.name, STAMP))
        except ValueError:
            continue
        m = {}
        try:
            m = json.loads((p / "relic.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        out.append(Snapshot(p, when, m.get("status", "ok"), int(m.get("size", 0)), int(m.get("files", 0)), m.get("sources", [])))
    return out


def rel_in_snapshot(src: Path) -> str:
    """Caminho dentro da foto: relativo a pasta pessoal (ou 'raiz/...' para fora dela)."""
    src = src.resolve() if src.exists() else src
    try:
        return str(src.relative_to(HOME))
    except ValueError:
        return "raiz" + str(src)


def original_path(snapshot: Path, inside: Path) -> Path:
    """Caminho original de algo que esta dentro da foto."""
    rel = inside.relative_to(snapshot)
    parts = rel.parts
    if parts and parts[0] == "raiz":
        return Path("/", *parts[1:])
    return HOME / rel


def rsync_ok() -> bool:
    return shutil.which("rsync") is not None


def dest_status(dest: str) -> tuple[bool, str]:
    """(pode gravar?, explicacao)"""
    if not dest:
        return False, "escolha onde guardar os backups"
    d = Path(dest).expanduser()
    if not d.exists():
        return False, "destino nao encontrado (o HD ou pendrive esta conectado?)"
    if not os.access(d, os.W_OK):
        return False, "sem permissao para gravar no destino"
    du = shutil.disk_usage(d)
    return True, f"{human(du.free)} livres de {human(du.total)}"


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u in ("B", "KB") else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def folder_size(p: Path, excludes: list[str] | None = None, limit_s: float = 8.0) -> int:
    """Tamanho aproximado (para a tela); para depois de alguns segundos em pastas enormes."""
    total, t0 = 0, time.time()
    if p.is_file():
        return p.stat().st_size
    for root, dirs, files in os.walk(p):
        if excludes:
            dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d + "/", e) for e in excludes)]
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
        if time.time() - t0 > limit_s:
            break
    return total


def run_backup(cfg: Config, on_progress=None, on_line=None) -> Snapshot:
    """Faz uma foto nova. on_progress(pct, texto); on_line(linha do log)."""
    ok, why = dest_status(cfg["dest"])
    if not ok:
        raise RuntimeError(why)
    if not rsync_ok():
        raise RuntimeError("o rsync nao esta instalado (sudo apt install rsync)")
    sources = cfg.selected_paths()
    if not sources:
        raise RuntimeError("nada selecionado para salvar")
    root = repo_dir(cfg["dest"])
    root.mkdir(parents=True, exist_ok=True)
    prev = next((s for s in list_snapshots(cfg["dest"]) if s.status == "ok"), None)
    name = time.strftime(STAMP)
    work = root / f".parcial-{name}"
    final = root / name
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / f"relic-{name}.log", "w", encoding="utf-8")
    say = lambda t: (log.write(t + "\n"), log.flush(), on_line and on_line(t))  # noqa: E731
    errors = 0
    say(f"ARASAKA RELIC {VERSION} · backup {name} · {len(sources)} origem(ns) · destino {root}")
    for i, src in enumerate(sources):
        rel = rel_in_snapshot(src)
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        args = ["rsync", "-a", "--delete", "--info=progress2", "--no-inc-recursive", "--human-readable"]
        for e in cfg["excludes"] or []:
            args += ["--exclude", e]
        if prev and (prev.path / rel).exists():   # o que nao mudou vira hardlink da foto anterior
            args.append(f"--link-dest={(prev.path / rel).parent if src.is_file() else prev.path / rel}")
        args += [str(src) + ("/" if src.is_dir() else ""), str(target) + ("/" if src.is_dir() else "")]
        say(f"> {src}")
        base = i / len(sources)
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        buf = ""
        while True:
            ch = p.stdout.read(1)
            if not ch:
                break
            if ch in "\r\n":
                line = buf.strip()
                buf = ""
                m = re.search(r"(\d+)%", line)
                if m and "/s" in line:            # linha de progresso do --info=progress2
                    if on_progress:
                        pct = base + int(m.group(1)) / 100 / len(sources)
                        on_progress(min(pct, 0.999), f"{src.name}: {line.split()[0]}")
                elif line:
                    say("  " + line)
            else:
                buf += ch
        code = p.wait()
        if code not in (0, 24):          # 24 = arquivos que sumiram durante a copia (normal)
            errors += 1
            say(f"!! rsync terminou com codigo {code} em {src}")
    size, files = 0, 0
    for r, _d, fs in os.walk(work):
        for f in fs:
            files += 1
            try:
                st = os.lstat(os.path.join(r, f))
                if st.st_nlink == 1:      # so o que e novo nesta foto
                    size += st.st_size
            except OSError:
                pass
    status = "ok" if errors == 0 else "parcial"
    (work / "relic.json").write_text(json.dumps({"version": VERSION, "status": status, "size": size, "files": files,
                                                  "sources": [str(s) for s in sources], "when": name}, indent=1),
                                     encoding="utf-8")
    work.rename(final)
    say(f"■ backup {status}: {files} arquivos, {human(size)} novos")
    log.close()
    cfg["last"] = {"when": name, "status": status, "size": size}
    prune(cfg)
    if on_progress:
        on_progress(1.0, "pronto")
    return Snapshot(final, time.mktime(time.strptime(name, STAMP)), status, size, files, [str(s) for s in sources])


def prune(cfg: Config):
    """Mantem so as N fotos mais novas (as parciais nao contam e nunca apagam uma boa)."""
    keep = max(1, int(cfg["keep"] or 14))
    snaps = [s for s in list_snapshots(cfg["dest"]) if s.status == "ok"]
    for s in snaps[keep:]:
        shutil.rmtree(s.path, ignore_errors=True)


def delete_snapshot(s: Snapshot):
    shutil.rmtree(s.path)


def restore(snapshot: Path, inside: Path, target: Path | None = None, on_line=None) -> Path:
    """Copia de volta. Sem target: para o lugar original (sobrescreve o que mudou, nao apaga nada a mais)."""
    if not rsync_ok():
        raise RuntimeError("o rsync nao esta instalado")
    dst = target or original_path(snapshot, inside)
    if target and inside.is_dir():
        dst = target / inside.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = ["rsync", "-a", str(inside) + ("/" if inside.is_dir() else ""), str(dst) + ("/" if inside.is_dir() else "")]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode not in (0, 24):
        raise RuntimeError(r.stderr.strip()[-300:] or f"rsync terminou com codigo {r.returncode}")
    if on_line:
        on_line(f"■ restaurado: {dst}")
    return dst


# ================================================================ agenda (systemd --user)
UNIT_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "systemd" / "user"


def set_schedule(on: bool) -> str:
    """Liga/desliga o backup diario. Devolve uma mensagem."""
    svc, tmr = UNIT_DIR / f"{APP_ID}.service", UNIT_DIR / f"{APP_ID}.timer"
    if not shutil.which("systemctl"):
        return "este sistema nao tem o systemd: a agenda nao funciona aqui"
    if on:
        UNIT_DIR.mkdir(parents=True, exist_ok=True)
        exe = HOME / ".local" / "bin" / APP_ID
        svc.write_text(f"[Unit]\nDescription=ARASAKA RELIC: backup\n\n[Service]\nType=oneshot\nExecStart={exe} --run\nNice=10\n"
                       "IOSchedulingClass=idle\n", encoding="utf-8")
        tmr.write_text("[Unit]\nDescription=ARASAKA RELIC: backup diario\n\n[Timer]\nOnCalendar=daily\nPersistent=true\n"
                       "RandomizedDelaySec=15min\n\n[Install]\nWantedBy=timers.target\n", encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        r = subprocess.run(["systemctl", "--user", "enable", "--now", f"{APP_ID}.timer"], capture_output=True, text=True)
        return "backup diario ligado" if r.returncode == 0 else f"falha ao ligar a agenda: {r.stderr.strip()[:160]}"
    subprocess.run(["systemctl", "--user", "disable", "--now", f"{APP_ID}.timer"], capture_output=True)
    for f in (svc, tmr):
        f.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    return "backup diario desligado"


def notify(title: str, body: str):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "Arasaka Relic", "-i", APP_ID, title, body], capture_output=True)


def run_cli() -> int:
    """arasaka-relic --run (usado pela agenda): faz o backup sem janela."""
    cfg = Config()
    ok, why = dest_status(cfg["dest"])
    if not ok:
        notify("Backup não feito", why)
        print(why, file=sys.stderr)
        return 2
    try:
        s = run_backup(cfg, on_line=print)
    except Exception as e:  # noqa: BLE001
        notify("Backup falhou", str(e))
        print(e, file=sys.stderr)
        return 1
    notify("Backup feito" if s.status == "ok" else "Backup com avisos", f"{s.files} arquivos · {human(s.size)} novos")
    return 0 if s.status == "ok" else 1
