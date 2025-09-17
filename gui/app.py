"""PyQt6 front-end for the MangaPark downloader."""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
import traceback
from typing import Callable, Dict, List, Tuple

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRunnable, Qt, QThreadPool, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QGraphicsOpacityEffect,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mangapark import (
    create_cbz,
    create_pdf,
    download_chapter_with_selenium,
    download_chapters_threaded,
    get_chapter_info,
)
from gui.style import APP_STYLE, apply_palette


class _StreamRedirect:
    def __init__(self, emit: Callable[[str], None]):
        self.emit = emit
        self.buffer = ""

    def _push(self, chunk: str) -> None:
        chunk = chunk.strip()
        if chunk:
            self.emit(chunk)

    def write(self, text: str) -> None:
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self._push(line)

    def flush(self) -> None:
        if self.buffer:
            self._push(self.buffer)
            self.buffer = ""


@contextlib.contextmanager
def redirect_streams(emit: Callable[[str], None]):
    redirector = _StreamRedirect(emit)
    stdout, stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = redirector  # type: ignore
    try:
        yield
    finally:
        redirector.flush()
        sys.stdout, sys.stderr = stdout, stderr


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    log = pyqtSignal(str)
    progress = pyqtSignal(int)


class TaskRunnable(QRunnable):
    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = WorkerSignals()

    def run(self) -> None:  # pragma: no cover
        try:
            with redirect_streams(self.signals.log.emit):
                result = self.fn(self.signals, *self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception:  # pylint: disable=broad-except
            self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()


def fetch_chapter_metadata(signals: WorkerSignals, manga_url: str):
    signals.log.emit(f"Fetching chapter information from {manga_url}...")
    chapters = get_chapter_info(manga_url)
    if not chapters:
        raise ValueError("No chapters found. Verify the URL or try again later.")
    signals.log.emit(f"Found {len(chapters)} chapter(s).")
    return chapters


def run_download_job(
    signals: WorkerSignals,
    chapters: List[Dict[str, str]],
    threaded: bool,
    concurrency: int,
    convert_mode: str,
    delete_sources: bool,
):
    if not chapters:
        raise ValueError("Select at least one chapter before downloading.")

    os.makedirs("downloads", exist_ok=True)
    mode = f"{concurrency} threads" if threaded else "sequential mode"
    signals.log.emit(f"Downloading {len(chapters)} chapter(s) in {mode}.")

    if threaded:
        successful = download_chapters_threaded(chapters, max(1, concurrency))
    else:
        successful = []
        total = len(chapters)
        for idx, chapter in enumerate(chapters, 1):
            signals.log.emit(f"[{idx}/{total}] {chapter['title']}")
            chapter_dir, ok = download_chapter_with_selenium(chapter['url'], chapter['title'], 1)
            if ok:
                successful.append((chapter_dir, chapter['title']))
            signals.progress.emit(int(idx / total * 60))

    if not successful:
        signals.log.emit("No chapters finished successfully.")
        signals.progress.emit(100)
        return []

    conversions: List[Tuple[str, Callable[[str, str], str | None]]] = []
    if convert_mode in {"cbz", "both"}:
        conversions.append(("CBZ", create_cbz))
    if convert_mode in {"pdf", "both"}:
        conversions.append(("PDF", create_pdf))

    for phase, (label, converter) in enumerate(conversions, 1):
        signals.log.emit(f"{label} conversion running...")
        total = len(successful)
        for idx, (chapter_dir, chapter_title) in enumerate(successful, 1):
            if label == "PDF" and not os.path.exists(chapter_dir):
                signals.log.emit(f"Sources missing for {chapter_title}, skipping PDF.")
                continue
            output = converter(chapter_dir, chapter_title)
            if output:
                signals.log.emit(f"✔ {label} ready: {output}")
                if delete_sources and os.path.isdir(chapter_dir):
                    try:
                        shutil.rmtree(chapter_dir)
                        signals.log.emit(f"Removed source images for {chapter_title}.")
                    except Exception as exc:  # pylint: disable=broad-except
                        signals.log.emit(f"Cleanup failed for {chapter_title}: {exc}")
            else:
                signals.log.emit(f"✖ {label} failed for {chapter_title}")
            span = 35 // max(1, len(conversions))
            progress = 60 + (phase - 1) * span + int(idx / max(1, total) * span)
            signals.progress.emit(min(95, progress))

    signals.progress.emit(100)
    return successful


class MangaParkWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MangaPark Downloader")
        self.setMinimumSize(900, 600)
        self.thread_pool = QThreadPool()
        self._build_ui()
        self._animate_banner()

    def _build_ui(self) -> None:
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        self.banner = QLabel("MangaPark Downloader")
        self.banner.setObjectName("TitleLabel")
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.banner)

        card = QFrame()
        card.setObjectName("Card")
        grid = QGridLayout(card)
        grid.setVerticalSpacing(14)
        grid.setHorizontalSpacing(12)

        manga_url_label = QLabel("Manga URL")
        manga_url_label.setObjectName("SectionLabel")
        grid.addWidget(manga_url_label, 0, 0)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://mangapark.net/...")
        fetch_btn = QPushButton("Fetch Chapters")
        fetch_btn.clicked.connect(self._on_fetch_clicked)
        row = QHBoxLayout()
        row.addWidget(self.url_input)
        row.addWidget(fetch_btn)
        grid.addLayout(row, 0, 1)

        available_chapters_label = QLabel("Available Chapters")
        available_chapters_label.setObjectName("SectionLabel")
        grid.addWidget(available_chapters_label, 1, 0)
        self.chapter_list = QListWidget()
        self.chapter_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        grid.addWidget(self.chapter_list, 1, 1)

        options = QHBoxLayout()
        self.threading_box = QCheckBox("Use threaded downloads")
        self.threading_box.setChecked(True)
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 16)
        self.concurrency_spin.setValue(5)
        self.convert_combo = QComboBox()
        self.convert_combo.addItems(["none", "cbz", "pdf", "both"])
        self.cleanup_box = QCheckBox("Delete images after converting")
        for widget in (
            self.threading_box,
            QLabel("Concurrency"),
            self.concurrency_spin,
            QLabel("Convert"),
            self.convert_combo,
            self.cleanup_box,
        ):
            options.addWidget(widget)
        grid.addLayout(options, 2, 1)

        controls = QHBoxLayout()
        controls.addStretch()
        self.open_folder_button = QPushButton("Open downloads folder")
        self.open_folder_button.clicked.connect(self._open_downloads)
        self.download_button = QPushButton("Start Download")
        self.download_button.clicked.connect(self._on_download_clicked)
        controls.addWidget(self.open_folder_button)
        controls.addWidget(self.download_button)
        grid.addLayout(controls, 3, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        grid.addWidget(self.progress, 4, 1)

        activity_log_label = QLabel("Activity log")
        activity_log_label.setObjectName("SectionLabel")
        grid.addWidget(activity_log_label, 5, 0)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(160)
        grid.addWidget(self.log_area, 5, 1)

        root.addWidget(card)
        self.setCentralWidget(container)

    def _animate_banner(self) -> None:
        effect = QGraphicsOpacityEffect(self.banner)
        self.banner.setGraphicsEffect(effect)
        self.anim = QPropertyAnimation(effect, b"opacity", self)
        self.anim.setStartValue(0.35)
        self.anim.setEndValue(1.0)
        self.anim.setDuration(2200)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.setLoopCount(-1)
        self.anim.start()

    def _bind_worker(self, worker: TaskRunnable, on_result: Callable):
        worker.signals.result.connect(on_result)
        worker.signals.log.connect(self._append_log)
        worker.signals.error.connect(self._show_error)
        worker.signals.finished.connect(lambda: self._set_busy(False))
        worker.signals.progress.connect(self.progress.setValue)
        self.thread_pool.start(worker)

    def _on_fetch_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self._show_error("Please enter a MangaPark URL.")
            return
        worker = TaskRunnable(fetch_chapter_metadata, url)
        self._append_log("Retrieving chapters...")
        self._set_busy(True)
        self._bind_worker(worker, self._populate_chapters)

    def _on_download_clicked(self) -> None:
        selected = [
            (item.data(Qt.ItemDataRole.UserRole)
            for i in range(self.chapter_list.count())
            if (item := self.chapter_list.item(i)) and item.isSelected())
        ]
        if not selected:
            self._show_error("Select at least one chapter.")
            return
        worker = TaskRunnable(
            run_download_job,
            chapters=selected,
            threaded=self.threading_box.isChecked(),
            concurrency=self.concurrency_spin.value(),
            convert_mode=self.convert_combo.currentText(),
            delete_sources=self.cleanup_box.isChecked(),
        )
        self._append_log("Download task queued...")
        self._set_busy(True)
        self._bind_worker(worker, lambda _: self._append_log("Download task finished."))

    def _populate_chapters(self, chapters: List[Dict[str, str]]) -> None:
        self.chapter_list.clear()
        for chapter in chapters:
            item = QListWidgetItem(chapter["title"])
            item.setData(Qt.ItemDataRole.UserRole, chapter)
            self.chapter_list.addItem(item)
        if chapters:
            self._append_log("Chapters ready. Select the ones to download.")

    def _open_downloads(self) -> None:
        path = os.path.abspath("downloads")
        os.makedirs(path, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _append_log(self, text: str) -> None:
        self.log_area.append(text)
        self.log_area.ensureCursorVisible()

    def _show_error(self, message: str) -> None:
        self._append_log(message)
        QMessageBox.critical(self, "MangaPark Downloader", message)

    def _set_busy(self, busy: bool) -> None:
        self.download_button.setDisabled(busy)
        self.open_folder_button.setDisabled(busy)
        self.progress.setRange(0, 0 if busy else 100)
        if not busy and self.progress.value() in {0, 100}:
            self.progress.setValue(0)


def launch() -> None:
    app = QApplication(sys.argv)
    apply_palette(app)
    app.setStyleSheet(APP_STYLE)
    window = MangaParkWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch()



