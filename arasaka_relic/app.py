"""
ARASAKA RELIC // interface (PySide6 / Qt 6).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from . import core, fx
from .core import APP_NAME, VERSION, Config
from .kit import CutFrame, Page, SidebarBrand, button, label, load_fonts, spaced, stylesheet

EXTRA_QSS = """
QSpinBox { background: #050506; border: 1px solid #2a2a31; padding: 7px 8px; selection-background-color: #e3121f; }
QSpinBox:focus { border-color: #e3121f; }
QPlainTextEdit { background: #050506; border: 1px solid #2a2a31; color: #ececf0; padding: 6px; selection-background-color: #e3121f; }
QPlainTextEdit:focus { border-color: #e3121f; }
QPlainTextEdit#log { background: #030304; border: 1px solid #1d1d22; color: #c9c9cf; }
QProgressBar { background: #0b0b0d; border: 1px solid #2a2a31; height: 10px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #e3121f; }
QListWidget#snaps::item { padding: 12px 10px; border-bottom: 1px solid #16161a; }
QListWidget#snaps::item:selected { background: rgba(227,18,31,0.18); border-left: 3px solid #e3121f; }
"""


class Task(QThread):
    progress = Signal(float, str)
    line = Signal(str)
    done = Signal(object)

    def __init__(self, fn, *args, **kw):
        super().__init__()
        self.fn, self.args, self.kw = fn, args, kw

    def run(self):
        try:
            self.done.emit(self.fn(*self.args, **self.kw))
        except Exception as e:  # noqa: BLE001
            self.done.emit(e)


# ================================================================ paginas
class SnapshotsPage(Page):
    def __init__(self, win):
        super().__init__(win, "BACKUPS", "Cada backup é uma foto completa da data; só o que mudou ocupa espaço novo", "RELIC://ENGRAMS")
        self.state = CutFrame(cut=12)
        sl = QVBoxLayout(self.state)
        sl.setContentsMargins(18, 14, 18, 14)
        self.status = label("", px=1.5, bold=True)
        self.sub = label("", "muted", wrap=True)
        sl.addWidget(self.status)
        sl.addWidget(self.sub)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.hide()
        sl.addWidget(self.bar)
        self.lay.addWidget(self.state)
        row = QHBoxLayout()
        self.run_btn = button("FAZER BACKUP AGORA", "primary", self.run_backup)
        row.addWidget(self.run_btn)
        row.addWidget(button("RESTAURAR...", None, self.restore))
        row.addWidget(button("ABRIR PASTA", None, self.open_folder))
        row.addStretch()
        row.addWidget(button("EXCLUIR", "danger", self.delete))
        self.lay.addLayout(row)
        self.list = QListWidget()
        self.list.setObjectName("snaps")
        self.list.setMinimumHeight(260)
        self.list.itemDoubleClicked.connect(lambda _i: self.restore())
        self.lay.addWidget(self.list, 1)
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.hide()
        self.lay.addWidget(self.log)
        self.task: Task | None = None

    def refresh(self):
        cfg = self.win.cfg
        ok, why = core.dest_status(cfg["dest"])
        last = cfg["last"]
        if not cfg["dest"]:
            self.status.setText("■  NENHUM DESTINO")
            self.sub.setText("Escolha um HD externo, pendrive ou pasta em 03 DESTINO E AGENDA.")
        elif not ok:
            self.status.setText("■  DESTINO OFFLINE")
            self.sub.setText(f"{cfg['dest']}: {why}")
        else:
            self.status.setText("■  ULTIMO BACKUP: " + (core.time.strftime("%d/%m/%Y %H:%M", core.time.strptime(last["when"], core.STAMP))
                                                         + ("" if last.get("status") == "ok" else " (com avisos)") if last else "NENHUM AINDA"))
            self.sub.setText(f"{cfg['dest']} · {why} · guarda os {cfg['keep']} mais novos" + (" · backup diário ligado" if cfg["schedule"] else ""))
        self.run_btn.setEnabled(ok and self.task is None)
        self.list.clear()
        for s in core.list_snapshots(cfg["dest"]) if ok else []:
            it = QListWidgetItem(f"{s.label}      {s.files} arquivos · {core.human(s.size)} novos" + ("" if s.status == "ok" else "   ·   PARCIAL"))
            it.setData(Qt.UserRole, s)
            self.list.addItem(it)
        if ok and not self.list.count():
            self.list.addItem("Nenhum backup ainda. Clique em FAZER BACKUP AGORA.")

    def current(self):
        it = self.list.currentItem()
        s = it.data(Qt.UserRole) if it else None
        if not s:
            self.win.toast("Selecione um backup na lista")
        return s

    def run_backup(self):
        if self.task:
            return
        self.log.clear()
        self.log.show()
        self.bar.setValue(0)
        self.bar.show()
        self.run_btn.setEnabled(False)
        self.status.setText("■  FAZENDO BACKUP...")
        t = Task(core.run_backup, self.win.cfg)
        t.kw = {"on_progress": lambda p, txt: t.progress.emit(p, txt), "on_line": lambda ln: t.line.emit(ln)}
        t.progress.connect(lambda p, txt: (self.bar.setValue(int(p * 1000)), self.sub.setText(txt)))
        t.line.connect(self.log.appendPlainText)
        t.done.connect(self._done)
        self.task = t
        t.start()

    def _done(self, r):
        self.task = None
        self.bar.hide()
        if isinstance(r, Exception):
            self.win.alert("Backup falhou", str(r))
        else:
            self.win.toast(f"Backup feito: {r.files} arquivos, {core.human(r.size)} novos")
        self.refresh()

    def restore(self):
        s = self.current()
        if not s:
            return
        pick = QFileDialog.getExistingDirectory(self, "Escolha a pasta a restaurar (cancele para escolher um arquivo)", str(s.path),
                                                QFileDialog.DontUseNativeDialog)
        if not pick:
            pick, _ = QFileDialog.getOpenFileName(self, "Escolha o arquivo a restaurar", str(s.path), "", "",
                                                  QFileDialog.DontUseNativeDialog)
        if not pick:
            return
        inside = Path(pick)
        try:
            inside.relative_to(s.path)
        except ValueError:
            return self.win.alert("Restaurar", "Escolha algo dentro da pasta do backup.")
        if inside == s.path:
            return self.win.alert("Restaurar", "Escolha uma pasta ou arquivo dentro do backup (não o backup inteiro).")
        orig = core.original_path(s.path, inside)
        mb = QMessageBox(self)
        mb.setWindowTitle("Restaurar")
        mb.setText(f"Restaurar {inside.name} do backup de {s.label}?")
        mb.setInformativeText(f"No lugar original ({orig}), os arquivos com o mesmo nome são substituídos pela versão do backup. "
                              "Nada a mais é apagado.")
        here = mb.addButton("NO LUGAR ORIGINAL", QMessageBox.AcceptRole)
        here.setProperty("kind", "primary")
        other = mb.addButton("EM OUTRA PASTA...", QMessageBox.ActionRole)
        mb.addButton("CANCELAR", QMessageBox.RejectRole)
        mb.exec()
        target = None
        if mb.clickedButton() is other:
            d = QFileDialog.getExistingDirectory(self, "Restaurar em", str(core.HOME))
            if not d:
                return
            target = Path(d)
        elif mb.clickedButton() is not here:
            return
        try:
            dst = core.restore(s.path, inside, target)
            self.win.toast(f"Restaurado em {dst}")
        except Exception as e:  # noqa: BLE001
            self.win.alert("Restaurar", str(e))

    def open_folder(self):
        s = self.list.currentItem() and self.list.currentItem().data(Qt.UserRole)
        p = s.path if s else core.repo_dir(self.win.cfg["dest"]) if self.win.cfg["dest"] else None
        if p and Path(p).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def delete(self):
        s = self.current()
        if s and self.win.confirm("Excluir backup", f"Excluir o backup de {s.label}? Os outros backups continuam inteiros."):
            core.delete_snapshot(s)
            self.refresh()


class SourcesPage(Page):
    def __init__(self, win):
        super().__init__(win, "O QUE SALVAR", "Pastas e dados que entram em cada backup", "RELIC://SOURCES")
        self.box = QVBoxLayout()
        self.box.setSpacing(6)
        self.lay.addLayout(self.box)
        row = QHBoxLayout()
        row.addWidget(button("ADICIONAR PASTA...", None, self.add_folder))
        row.addStretch()
        self.lay.addLayout(row)
        self.lay.addWidget(label("NÃO SALVAR (um padrão por linha, ex.: *.iso  ou  node_modules/)", "muted", 1.5, 12, True))
        self.excl = QPlainTextEdit()
        self.excl.setMaximumHeight(120)
        self.excl.textChanged.connect(self._save_excludes)
        self.lay.addWidget(self.excl)
        self.lay.addStretch()
        self.sizes: dict[str, str] = {}

    def refresh(self):
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        cfg = self.win.cfg
        for s in core.presets():
            exists = [p for p in s.paths if p.exists()]
            cb = QCheckBox(f"{s.title}" + (f"   ·   {s.note}" if s.note else "") + ("" if exists else "   ·   (não existe neste PC)"))
            cb.setChecked(s.key in cfg["sources"])
            cb.setEnabled(bool(exists))
            cb.setToolTip("\n".join(str(p) for p in s.paths))
            cb.toggled.connect(lambda on, k=s.key: self._toggle(k, on))
            self.box.addWidget(cb)
        for p in cfg["custom"]:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(label(f"■  {p}", px=0.5))
            h.addStretch()
            h.addWidget(button("REMOVER", None, lambda pp=p: self._remove(pp)))
            self.box.addWidget(row)
        self.excl.blockSignals(True)
        self.excl.setPlainText("\n".join(cfg["excludes"] or []))
        self.excl.blockSignals(False)

    def _toggle(self, key, on):
        src = [k for k in self.win.cfg["sources"] if k != key] + ([key] if on else [])
        self.win.cfg["sources"] = src

    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Pasta para salvar", str(core.HOME))
        if d and d not in self.win.cfg["custom"]:
            self.win.cfg["custom"] = self.win.cfg["custom"] + [d]
            self.refresh()

    def _remove(self, p):
        self.win.cfg["custom"] = [x for x in self.win.cfg["custom"] if x != p]
        self.refresh()

    def _save_excludes(self):
        self.win.cfg["excludes"] = [ln.strip() for ln in self.excl.toPlainText().splitlines() if ln.strip()]


class DestPage(Page):
    def __init__(self, win):
        super().__init__(win, "DESTINO E AGENDA", "Onde os backups ficam e quando são feitos", "RELIC://VAULT")
        card = CutFrame(cut=12)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 14, 18, 16)
        cl.addWidget(label("DESTINO", px=2, bold=True))
        cl.addWidget(label("Use um HD externo ou pendrive: um backup no mesmo disco do sistema não protege contra defeito no disco.", "muted", wrap=True))
        row = QHBoxLayout()
        self.dest = QLineEdit()
        self.dest.setReadOnly(True)
        row.addWidget(self.dest, 1)
        row.addWidget(button("ESCOLHER...", "primary", self.pick))
        cl.addLayout(row)
        self.dest_info = label("", "muted")
        cl.addWidget(self.dest_info)
        self.lay.addWidget(card)

        card2 = CutFrame(cut=12)
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(18, 14, 18, 16)
        c2.addWidget(label("QUANTOS GUARDAR", px=2, bold=True))
        r2 = QHBoxLayout()
        self.keep = QSpinBox()
        self.keep.setRange(1, 365)
        self.keep.valueChanged.connect(lambda v: self.win.cfg.__setitem__("keep", v))
        r2.addWidget(self.keep)
        r2.addWidget(label("backups mais novos (os mais antigos são apagados depois de cada backup)", "muted"))
        r2.addStretch()
        c2.addLayout(r2)
        self.lay.addWidget(card2)

        card3 = CutFrame(cut=12)
        c3 = QVBoxLayout(card3)
        c3.setContentsMargins(18, 14, 18, 16)
        c3.addWidget(label("AGENDA", px=2, bold=True))
        self.sched = QCheckBox("Fazer backup todo dia sozinho (se o PC estiver desligado, faz quando ligar)")
        self.sched.toggled.connect(self.toggle_schedule)
        c3.addWidget(self.sched)
        c3.addWidget(label("Se o destino não estiver conectado na hora, o Relic avisa e tenta no dia seguinte.", "muted", wrap=True))
        self.lay.addWidget(card3)
        self.lay.addStretch()

    def refresh(self):
        cfg = self.win.cfg
        self.dest.setText(cfg["dest"] or "")
        ok, why = core.dest_status(cfg["dest"])
        self.dest_info.setText(why)
        self.keep.blockSignals(True)
        self.keep.setValue(int(cfg["keep"] or 14))
        self.keep.blockSignals(False)
        self.sched.blockSignals(True)
        self.sched.setChecked(bool(cfg["schedule"]))
        self.sched.blockSignals(False)

    def pick(self):
        d = QFileDialog.getExistingDirectory(self, "Onde guardar os backups", self.win.cfg["dest"] or (str(core.HOME) if core.WIN else "/media"))
        if d:
            self.win.cfg["dest"] = d
            self.refresh()

    def toggle_schedule(self, on):
        msg = core.set_schedule(on)
        self.win.cfg["schedule"] = on and "ligado" in msg
        self.win.toast(msg)
        self.refresh()


# ================================================================ janela
class MainWindow(QMainWindow):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle(APP_NAME)
        self.resize(1080, 760)
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 14)
        sl.setSpacing(2)
        sl.addWidget(SidebarBrand("RELIC"))
        sl.addSpacing(10)
        self.nav = QButtonGroup(self)
        self.stack = QStackedWidget()
        self.pages = {"snaps": SnapshotsPage(self), "sources": SourcesPage(self), "dest": DestPage(self)}
        for i, (key, text) in enumerate([("snaps", "BACKUPS"), ("sources", "O QUE SALVAR"), ("dest", "DESTINO E AGENDA")]):
            b = QPushButton(f"{i + 1:02d}   {text}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            spaced(b, 2.5)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav.addButton(b, i)
            sl.addWidget(b)
            self.stack.addWidget(self.pages[key])
        sl.addStretch()
        if core.WIN and not core.rsync_ok():   # Windows: copia em Python com hardlinks (nao precisa do rsync)
            rs = label("■  COPIA NATIVA · HARDLINKS", "muted", 1.5, 11, True)
        else:
            rs = label("■  RSYNC" + (" · ONLINE" if core.rsync_ok() else " AUSENTE"), "muted" if core.rsync_ok() else "red", 1.5, 11, True)
        rs.setContentsMargins(20, 0, 0, 0)
        sl.addWidget(rs)
        ver = label(f"RELIC v{VERSION}", "dim", 2, 11)
        ver.setContentsMargins(20, 0, 0, 0)
        sl.addWidget(ver)
        h.addWidget(side)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.toast_lbl = QLabel(self)
        self.toast_lbl.setStyleSheet("background:#000; border:1px solid #e3121f; padding:10px 18px; color:#ececf0;")
        self.toast_lbl.hide()
        self.go("snaps" if cfg["dest"] else "dest")

    def go(self, key: str):
        self.nav.button(list(self.pages).index(key)).setChecked(True)
        self.stack.setCurrentWidget(self.pages[key])
        self.pages[key].refresh()

    def toast(self, text: str):
        self.toast_lbl.setText(text)
        spaced(self.toast_lbl, 1)
        self.toast_lbl.adjustSize()
        self.toast_lbl.move(self.width() - self.toast_lbl.width() - 24, 20)
        self.toast_lbl.raise_()
        self.toast_lbl.show()
        QTimer.singleShot(3500, self.toast_lbl.hide)

    def confirm(self, title: str, text: str) -> bool:
        mb = QMessageBox(self)
        mb.setWindowTitle(title)
        mb.setText(text)
        yes = mb.addButton("CONFIRMAR", QMessageBox.AcceptRole)
        yes.setProperty("kind", "danger")
        mb.addButton("CANCELAR", QMessageBox.RejectRole)
        mb.exec()
        return mb.clickedButton() is yes

    def alert(self, title: str, text: str):
        mb = QMessageBox(self)
        mb.setWindowTitle(title)
        mb.setText(text)
        mb.addButton("OK", QMessageBox.AcceptRole).setProperty("kind", "primary")
        mb.exec()


def main(argv: list[str] | None = None):
    argv = list(sys.argv if argv is None else argv)
    QApplication.setApplicationName(core.APP_ID)
    QApplication.setApplicationDisplayName(APP_NAME)
    QApplication.setDesktopFileName(core.APP_ID)
    app = QApplication(argv)
    load_fonts()
    app.setStyleSheet(stylesheet() + EXTRA_QSS)
    app.setWindowIcon(QIcon(str(core.ASSETS / "arasaka-relic.svg")))
    win = MainWindow(Config())
    fx.install(win, name=APP_NAME, icon=core.ASSETS / "arasaka-relic.svg", boot=not any(a.startswith("--screenshot=") for a in argv))
    win.show()
    shot = next((a.split("=", 1)[1] for a in argv if a.startswith("--screenshot=")), None)
    if shot:
        path, _, page = shot.partition(",")
        if page:
            QTimer.singleShot(200, lambda: win.go(page))
        QTimer.singleShot(2600, lambda: (win.grab().save(path), app.quit()))
    return app.exec()
