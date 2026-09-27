# -*- coding: utf-8 -*-
"""
Block Blast — однофайловая версия для Pydroid 3 (Android) и ПК.

Сгенерировано из пакета blockblast/ скриптом tools/build_single_file.py —
правки лучше вносить в пакет и пересобирать, но и этот файл можно редактировать.

Запуск в Pydroid 3:
  1. Меню ☰ → Pip → найти «pygame» → Install (один раз).
  2. Открыть этот файл и нажать ▶.
Управление на телефоне: перетаскивайте фигуры пальцем, «Назад» — пауза/возврат.
Сохранения лежат в папке block_blast_data рядом с файлом.
"""
from __future__ import annotations

import sys

if sys.version_info < (3, 9):
    raise SystemExit("Нужен Python 3.9 или новее")

from types import SimpleNamespace


def _namespace(*names):
    g = globals()
    return SimpleNamespace(**{n: g[n] for n in names})



# ======================================================================
# blockblast/config.py
# ======================================================================

"""Неизменяемые константы игры. Изменяемое состояние здесь не хранится."""

import os
import sys

TITLE = "Block Blast"
FPS = 60
IDLE_FPS = 30              # когда ничего не анимируется — экономим CPU/батарею
MAX_DT = 1 / 20            # защита от «прыжка» времени после сворачивания окна

# Базовое (дизайнерское) разрешение; всё остальное масштабируется от него
BASE_W, BASE_H = 480, 860
MIN_W, MIN_H = 360, 560

TRAY_SLOTS = 3
BOARD_SIZES = (6, 8, 10)
DEFAULT_BOARD_SIZE = 8
PALETTE_SLOTS = 26         # фигуры хранят индекс цвета, тема сама решает, какой это цвет
                           # (26 — по букве алфавита на цвет; флагов 11, они тоже все выпадают)

MODES = ("endless", "levels")
MODE_NAMES = {"endless": "Бесконечный", "levels": "Уровни"}
DIFFICULTIES = ("easy", "normal", "hard")
DIFFICULTY_NAMES = {"easy": "Лёгкая", "normal": "Обычная", "hard": "Сложная"}

# Анимации (секунды)
CLEAR_ANIM = 0.45
CLEAR_WAVE_DELAY = 0.025   # задержка между клетками «волны» очистки
PICKUP_ANIM = 0.12
RETURN_ANIM = 0.20
TRAY_SPAWN_ANIM = 0.28
GAME_OVER_DELAY = 0.8

DRAG_LIFT_CELLS = 1.6      # насколько фигура поднимается над пальцем/курсором
SNAP_RADIUS = 1            # «магнит»: ищем допустимую позицию в радиусе N клеток

# Качество отрисовки: максимальная длинная сторона кадра. Телефоны имеют экраны
# 1080x2400+, отрисовывать столько пикселей программно дорого — рендерим меньше,
# а SDL растягивает результат на GPU (флаг SCALED).
QUALITY_LEVELS = {"native": 100000, "high": 1600, "medium": 1280, "low": 1024}
QUALITY_NAMES = {"native": "Родное", "high": "Высокое", "medium": "Среднее", "low": "Низкое"}

AUTO_THEME_EVERY = 5
LEADERBOARD_SIZE = 10
AUTOSAVE_INTERVAL = 2.0

MAX_PARTICLES = 600
TEXTURE_CACHE_ITEMS = 900

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# в однофайловой сборке (block_blast_pydroid.py) пакета нет — проект там, где лежит файл
PROJECT_DIR = os.path.dirname(PACKAGE_DIR) if os.path.basename(PACKAGE_DIR) == "blockblast" else PACKAGE_DIR
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")

# Android (Pydroid 3, Pygame Subset и т.п.): sys.platform там "linux", поэтому смотрим на окружение
IS_ANDROID = (hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ
              or "ANDROID_ARGUMENT" in os.environ or os.environ.get("BLOCKBLAST_ANDROID") == "1")
# Веб-сборка (pygbag/WebAssembly): нет потоков, нет полноэкранного режима,
# цикл обязан отдавать управление браузеру через await.
IS_WEB = sys.platform == "emscripten" or os.environ.get("BLOCKBLAST_WEB") == "1"

SAFE_TOP_FRACTION = 0.03 if IS_ANDROID and not IS_WEB else 0.0   # отступ под статус-бар/вырез камеры

# ======================================================================
# blockblast/diag.py
# ======================================================================

"""Журнал запуска и безопасный режим.

На Android падение может случиться внутри SDL — тогда Python не успевает ничего
сообщить, и пользователь видит просто вылет. Поэтому каждый шаг запуска
записывается в файл сразу (с flush), и по нему видно, на чём всё оборвалось.

Если прошлый запуск не дошёл до конца, следующий стартует в безопасном режиме:
без звука, без масштабирования кадра и без vsync.
"""

import os
import sys
import time


PACKAGE = "org.blockblast.blockblast"
LOG_NAME = "block_blast_startup.txt"
MARKER_NAME = "block_blast_launching.flag"
STAGE_NAME = "block_blast_stage.txt"
OK_NAME = "block_blast_ok.txt"      # хотя бы один запуск дошёл до нарисованного кадра

_dir: str = ""
_safe_mode = False


def candidate_dirs() -> list:
    """Сначала папка, видимая в файловом менеджере телефона."""
    external = os.environ.get("EXTERNAL_STORAGE") or "/sdcard"
    return [
        os.path.join(external, "BlockBlast"),                 # видно в файловом менеджере
        os.path.join(external, "Download", "BlockBlast"),
        os.path.join(external, "Android", "data", PACKAGE, "files"),
        os.environ.get("ANDROID_PRIVATE") or "",
        os.path.expanduser("~"),
    ]


def _pick_dir() -> str:
    global _dir
    if _dir:
        return _dir
    for directory in candidate_dirs():
        if not directory:
            continue
        try:
            os.makedirs(directory, exist_ok=True)
            probe = os.path.join(directory, ".diag_test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            _dir = directory
            return _dir
        except OSError:
            continue
    return ""


def begin() -> bool:
    """Начало запуска. Возвращает True, если нужен безопасный режим.

    На компьютере не нужен: там ошибки видны в консоли, а файлы-метки только мешают."""
    global _safe_mode
    if not IS_ANDROID:
        return False
    directory = _pick_dir()
    if not directory:
        return False
    marker = os.path.join(directory, MARKER_NAME)
    _safe_mode = os.path.exists(marker)      # прошлый запуск не завершился штатно
    try:
        with open(os.path.join(directory, LOG_NAME), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%d.%m.%Y %H:%M:%S')} игра стартует, "
                    f"безопасный режим: {'да' if _safe_mode else 'нет'}\n")
            f.write(f"python {sys.version.split()[0]}\n")
        with open(marker, "w") as f:
            f.write("1")
    except OSError:
        pass
    return _safe_mode


def log(step: str) -> None:
    if not _dir:
        return
    try:
        with open(os.path.join(_dir, LOG_NAME), "a", encoding="utf-8") as f:
            f.write(f"  {step}\n")
            f.flush()
            os.fsync(f.fileno())             # чтобы запись пережила жёсткое падение
    except OSError:
        pass


def launched_ok() -> bool:
    """Был ли на этом устройстве хоть один запуск, дошедший до кадра.

    Нужно, чтобы первый запуск после установки шёл самым простым путём:
    без SCALED и прочих необязательных вещей. Если игра хоть раз доехала
    до кадра — дальше можно включать всё остальное."""
    return bool(_dir) and os.path.exists(os.path.join(_dir, OK_NAME))


def success() -> None:
    """Игра дошла до первого кадра — снимаем метку неудачного запуска."""
    log("первый кадр нарисован — запуск удался")
    if not _dir:
        return
    try:
        with open(os.path.join(_dir, OK_NAME), "w") as f:
            f.write("1")
    except OSError:
        pass
    try:
        os.remove(os.path.join(_dir, MARKER_NAME))
    except OSError:
        pass
    try:            # игра работает — следующий запуск снова обычный
        with open(os.path.join(_dir, STAGE_NAME), "w") as f:
            f.write("0")
    except OSError:
        pass


def safe_mode() -> bool:
    return _safe_mode


def read_log() -> str:
    """Журнал запуска плюс отчёт faulthandler, если прошлый запуск убило системно."""
    path = log_path()
    if not path:
        return "журнал недоступен: некуда было писать"
    parts = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            parts.append(f.read())
    except OSError as exc:
        parts.append(f"журнал не прочитан: {exc}")
    fault = os.path.join(_dir, "block_blast_fault.txt")
    try:
        with open(fault, "r", encoding="utf-8") as f:
            text = f.read().strip()
        if text:
            parts.append("--- системное падение ---")
            parts.append(text)
    except OSError:
        pass
    return "\n".join(parts)


def log_path() -> str:
    return os.path.join(_dir, LOG_NAME) if _dir else ""

diag = _namespace("PACKAGE", "LOG_NAME", "MARKER_NAME", "STAGE_NAME", "OK_NAME", "_dir", "_safe_mode", "candidate_dirs", "_pick_dir", "begin", "log", "launched_ok", "success", "safe_mode", "read_log", "log_path")

# ======================================================================
# blockblast/core/shapes.py
# ======================================================================

"""Фигуры (полимино) и игровые фигуры в лотке."""

from dataclasses import dataclass
from typing import Iterable

Cell = tuple[int, int]


@dataclass(frozen=True)
class Shape:
    cells: tuple[Cell, ...]
    rows: int
    cols: int

    @property
    def size(self) -> int:
        return len(self.cells)

    @property
    def size_class(self) -> str:
        if self.size <= 2:
            return "small"
        if self.size <= 4:
            return "medium"
        return "large"


def make_shape(cells: Iterable[Cell]) -> Shape:
    cells = list(cells)
    if not cells:
        raise ValueError("фигура не может быть пустой")
    min_r = min(r for r, _ in cells)
    min_c = min(c for _, c in cells)
    norm = tuple(sorted({(r - min_r, c - min_c) for r, c in cells}))
    return Shape(
        cells=norm,
        rows=max(r for r, _ in norm) + 1,
        cols=max(c for _, c in norm) + 1,
    )


def _rotations(cells: Iterable[Cell]) -> list[Shape]:
    result: dict[tuple[Cell, ...], Shape] = {}
    current = list(cells)
    for _ in range(4):
        shape = make_shape(current)
        result.setdefault(shape.cells, shape)
        current = [(c, -r) for r, c in current]
    return list(result.values())


_BASE_SHAPES: dict[str, list[Cell]] = {
    "dot": [(0, 0)],
    "i2": [(0, 0), (0, 1)],
    "i3": [(0, 0), (0, 1), (0, 2)],
    "i4": [(0, 0), (0, 1), (0, 2), (0, 3)],
    "i5": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)],
    "corner3": [(0, 0), (1, 0), (1, 1)],
    "square2": [(0, 0), (0, 1), (1, 0), (1, 1)],
    "square3": [(r, c) for r in range(3) for c in range(3)],
    "rect23": [(r, c) for r in range(2) for c in range(3)],
    "t4": [(0, 0), (0, 1), (0, 2), (1, 1)],
    "s4": [(0, 1), (0, 2), (1, 0), (1, 1)],
    "z4": [(0, 0), (0, 1), (1, 1), (1, 2)],
    "l4": [(0, 0), (1, 0), (2, 0), (2, 1)],
    "j4": [(0, 1), (1, 1), (2, 1), (2, 0)],
    "corner5": [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)],
}


def _build_all() -> tuple[Shape, ...]:
    seen: dict[tuple[Cell, ...], Shape] = {}
    for cells in _BASE_SHAPES.values():
        for shape in _rotations(cells):
            seen.setdefault(shape.cells, shape)
    return tuple(sorted(seen.values(), key=lambda s: (s.size, s.cells)))


SHAPES: tuple[Shape, ...] = _build_all()
SHAPES_BY_CLASS: dict[str, tuple[Shape, ...]] = {
    cls: tuple(s for s in SHAPES if s.size_class == cls)
    for cls in ("small", "medium", "large")
}


@dataclass(frozen=True)
class Piece:
    shape: Shape
    color: int  # индекс в палитре темы, а не RGB → смена темы не требует перекраски
    labels: tuple = ()  # буква каждого кубика (тема «Алфавит»), по порядку shape.cells

    def to_data(self) -> dict:
        data = {"cells": [list(c) for c in self.shape.cells], "color": self.color}
        if self.labels:
            data["labels"] = list(self.labels)
        return data

    @staticmethod
    def from_data(data: dict) -> "Piece":
        shape = make_shape(tuple(c) for c in data["cells"])
        labels = data.get("labels")
        ok = isinstance(labels, list) and len(labels) == len(shape.cells) and all(isinstance(v, int) for v in labels)
        return Piece(shape, int(data["color"]), tuple(labels) if ok else ())

# ======================================================================
# blockblast/core/board.py
# ======================================================================

"""Игровое поле: чистая логика без pygame."""

from typing import Optional


ClearedCell = tuple[int, int, int, "int | None"]  # (row, col, color, буква кубика)


class Board:
    __slots__ = ("size", "cells", "labels", "version")

    def __init__(self, size: int = 8):
        if not 4 <= size <= 16:
            raise ValueError(f"недопустимый размер поля: {size}")
        self.size = size
        self.cells: list[list[Optional[int]]] = [[None] * size for _ in range(size)]
        # буква каждого кубика (тема «Алфавит»); логике игры не нужна, только отрисовке
        self.labels: list[list[Optional[int]]] = [[None] * size for _ in range(size)]
        # Увеличивается при каждом изменении → рендер пересобирает кэш только тогда
        self.version = 0

    # ---------- запросы ----------

    def can_place(self, shape: Shape, row: int, col: int) -> bool:
        if row < 0 or col < 0 or row + shape.rows > self.size or col + shape.cols > self.size:
            return False
        cells = self.cells
        for dr, dc in shape.cells:
            if cells[row + dr][col + dc] is not None:
                return False
        return True

    def valid_positions(self, shape: Shape) -> list[Cell]:
        return [
            (r, c)
            for r in range(self.size - shape.rows + 1)
            for c in range(self.size - shape.cols + 1)
            if self.can_place(shape, r, c)
        ]

    def has_room_for(self, shape: Shape) -> bool:
        for r in range(self.size - shape.rows + 1):
            for c in range(self.size - shape.cols + 1):
                if self.can_place(shape, r, c):
                    return True
        return False

    def full_lines(self) -> tuple[list[int], list[int]]:
        n = self.size
        rows = [r for r in range(n) if all(v is not None for v in self.cells[r])]
        cols = [c for c in range(n) if all(self.cells[r][c] is not None for r in range(n))]
        return rows, cols

    def lines_if_placed(self, shape: Shape, row: int, col: int) -> tuple[list[int], list[int]]:
        """Какие линии закроются, если поставить фигуру (без изменения поля).
        Проверяем только строки/столбцы, которые задевает фигура."""
        occupied = {(row + dr, col + dc) for dr, dc in shape.cells}
        n = self.size
        cells = self.cells

        def filled(r: int, c: int) -> bool:
            return cells[r][c] is not None or (r, c) in occupied

        rows = sorted({r for r, _ in occupied if all(filled(r, c) for c in range(n))})
        cols = sorted({c for _, c in occupied if all(filled(r, c) for r in range(n))})
        return rows, cols

    def is_empty(self) -> bool:
        return all(v is None for line in self.cells for v in line)

    def filled_count(self) -> int:
        return sum(v is not None for line in self.cells for v in line)

    # ---------- изменения ----------

    def place(self, shape: Shape, color: int, row: int, col: int, labels: tuple = ()) -> list[Cell]:
        if not self.can_place(shape, row, col):
            raise ValueError("фигуру нельзя поставить сюда")
        placed = []
        for k, (dr, dc) in enumerate(shape.cells):
            self.cells[row + dr][col + dc] = color
            self.labels[row + dr][col + dc] = labels[k] if k < len(labels) else None
            placed.append((row + dr, col + dc))
        self.version += 1
        return placed

    def clear_lines(self, rows: list[int], cols: list[int]) -> list[ClearedCell]:
        targets: dict[Cell, None] = {}  # dict сохраняет порядок и убирает дубли на пересечениях
        for r in rows:
            for c in range(self.size):
                targets[(r, c)] = None
        for c in cols:
            for r in range(self.size):
                targets[(r, c)] = None
        cleared = []
        for r, c in targets:
            color = self.cells[r][c]
            if color is not None:
                cleared.append((r, c, color, self.labels[r][c]))
                self.cells[r][c] = None
                self.labels[r][c] = None
        if cleared:
            self.version += 1
        return cleared

    def clear_all(self) -> None:
        for line in self.cells:
            line[:] = [None] * self.size
        self.version += 1

    # ---------- копирование / сериализация ----------

    def copy(self) -> "Board":
        other = Board.__new__(Board)
        other.size = self.size
        other.cells = [line[:] for line in self.cells]
        other.labels = [line[:] for line in self.labels]
        other.version = self.version
        return other

    def to_data(self) -> list[list[int]]:
        return [[-1 if v is None else v for v in line] for line in self.cells]

    def labels_to_data(self) -> list[list[int]]:
        return [[-1 if v is None else v for v in line] for line in self.labels]

    def load_labels(self, data) -> None:
        """Буквы из сохранения. Старые сохранения без букв — просто пропускаем."""
        if not isinstance(data, list) or len(data) != self.size:
            return
        for r, line in enumerate(data):
            if isinstance(line, list) and len(line) == self.size:
                self.labels[r] = [None if not isinstance(v, int) or v < 0 else v for v in line]

    @staticmethod
    def from_data(data: list[list[int]]) -> "Board":
        board = Board(len(data))
        for r, line in enumerate(data):
            if len(line) != board.size:
                raise ValueError("поле должно быть квадратным")
            board.cells[r] = [None if v is None or v < 0 else int(v) for v in line]
        board.version = 1
        return board

# ======================================================================
# blockblast/core/scoring.py
# ======================================================================

"""Очки и комбо.

Старая формула `combo *= 1.5` росла экспоненциально (10 очисток подряд → ×57),
а сбрасывалась после 2 промахов. Новая система:
  * серия (streak) растёт на 1 за каждый ход с очисткой;
  * у серии есть «запас ходов» — COMBO_KEEP_MOVES ходов без очистки, потом сброс;
  * множитель линейный и ограничен сверху.
"""

from dataclasses import dataclass

COMBO_KEEP_MOVES = 3
MULTIPLIER_STEP = 0.5
MAX_MULTIPLIER_STREAK = 9      # множитель не выше 1 + 8 * 0.5 = ×5
PERFECT_CLEAR_BONUS = 300


def line_points(lines: int) -> int:
    """1 → 20, 2 → 60, 3 → 120, 4 → 200 … (бонус за одновременные линии)."""
    return 10 * lines * (lines + 1)


def multiplier_for(streak: int) -> float:
    if streak <= 1:
        return 1.0
    return 1.0 + MULTIPLIER_STEP * (min(streak, MAX_MULTIPLIER_STREAK) - 1)


@dataclass(frozen=True)
class MoveScore:
    cells: int
    lines: int
    streak: int
    multiplier: float
    line_points: int
    perfect_bonus: int

    @property
    def total(self) -> int:
        return self.cells + self.line_points + self.perfect_bonus


class ComboTracker:
    def __init__(self, keep_moves: int = COMBO_KEEP_MOVES):
        self.keep_moves = keep_moves
        self.streak = 0
        self.moves_left = 0
        self.best = 0

    def register(self, lines: int) -> tuple[int, bool]:
        """Возвращает (текущая серия, была ли серия прервана этим ходом)."""
        if lines > 0:
            self.streak += 1
            self.moves_left = self.keep_moves
            self.best = max(self.best, self.streak)
            return self.streak, False
        if self.streak > 0:
            self.moves_left -= 1
            if self.moves_left <= 0:
                self.streak = 0
                self.moves_left = 0
                return 0, True
        return self.streak, False

    def to_data(self) -> dict:
        return {"streak": self.streak, "moves_left": self.moves_left, "best": self.best}

    def load(self, data: dict) -> None:
        self.streak = int(data.get("streak", 0))
        self.moves_left = int(data.get("moves_left", 0))
        self.best = int(data.get("best", 0))


def score_move(cells: int, lines: int, streak: int, perfect: bool, board_size: int) -> MoveScore:
    mult = multiplier_for(streak) if lines else 1.0
    pts = int(round(line_points(lines) * mult)) if lines else 0
    bonus = int(round(PERFECT_CLEAR_BONUS * board_size / 8)) if perfect else 0
    return MoveScore(cells, lines, streak, mult, pts, bonus)

# ======================================================================
# blockblast/core/events.py
# ======================================================================

"""События, которые логика отдаёт наружу (звук, эффекты, достижения).
Логика ничего не знает о pygame — она только публикует события."""

from dataclasses import dataclass, field



@dataclass(frozen=True)
class PiecePlaced:
    tray_index: int
    piece: Piece
    row: int
    col: int
    cells: list[Cell] = field(default_factory=list)


@dataclass(frozen=True)
class LinesCleared:
    rows: list[int]
    cols: list[int]
    cells: list[ClearedCell]
    move: MoveScore
    origin: tuple[float, float]  # центр поставленной фигуры (в клетках) — для «волны»


@dataclass(frozen=True)
class ScoreGained:
    move: MoveScore


@dataclass(frozen=True)
class ComboBroken:
    streak: int


@dataclass(frozen=True)
class PerfectClear:
    bonus: int


@dataclass(frozen=True)
class TrayRefilled:
    pieces: list[Piece]


@dataclass(frozen=True)
class LevelUp:
    level: int
    bonus: int
    goal_text: str


@dataclass(frozen=True)
class GameOver:
    score: int

ev = _namespace("PiecePlaced", "LinesCleared", "ScoreGained", "ComboBroken", "PerfectClear", "TrayRefilled", "LevelUp", "GameOver")

# ======================================================================
# blockblast/core/generator.py
# ======================================================================

"""Генерация фигур с учётом сложности и «честности»."""

import random
from dataclasses import dataclass



@dataclass(frozen=True)
class DifficultyProfile:
    small: float
    medium: float
    large: float
    fairness: str  # "all" — каждая фигура куда-то влезает, "one" — хотя бы одна, "none"


PROFILES = {
    "easy": DifficultyProfile(small=3.0, medium=4.0, large=1.5, fairness="all"),
    "normal": DifficultyProfile(small=2.0, medium=4.0, large=2.5, fairness="one"),
    "hard": DifficultyProfile(small=1.0, medium=3.0, large=4.0, fairness="none"),
}

MAX_ATTEMPTS = 25


class PieceGenerator:
    def __init__(self, rng: random.Random, difficulty: str = "normal"):
        # Собственный экземпляр Random: отрисовка текстур больше не может
        # «пересеять» генератор фигур (баг оригинала с random.seed в draw_cake_block)
        self.rng = rng
        self.profile = PROFILES.get(difficulty, PROFILES["normal"])
        # буквы кубиков идут подряд по алфавиту от фигуры к фигуре. Отдельный
        # счётчик, а не rng: последовательность фигур от букв не меняется
        self._next_letter = 0

    def _make(self, shape, color: int) -> Piece:
        n = len(shape.cells)
        labels = tuple((self._next_letter + k) % 26 for k in range(n))
        self._next_letter = (self._next_letter + n) % 26
        return Piece(shape, color, labels)

    def _pick_shape(self, hardness: float) -> Shape:
        p = self.profile
        h = max(0.0, min(1.0, hardness))
        weights = (p.small * (1 - 0.5 * h), p.medium, p.large * (1 + h))
        cls = self.rng.choices(("small", "medium", "large"), weights=weights)[0]
        return self.rng.choice(SHAPES_BY_CLASS[cls])

    def piece(self, hardness: float = 0.0) -> Piece:
        return self._make(self._pick_shape(hardness), self.rng.randrange(PALETTE_SLOTS))

    def _is_fair(self, board: Board, tray: list[Piece]) -> bool:
        mode = self.profile.fairness
        if mode == "none":
            return True
        fits = [board.has_room_for(p.shape) for p in tray]
        return all(fits) if mode == "all" else any(fits)

    def new_tray(self, board: Board, hardness: float = 0.0) -> list[Piece]:
        tray: list[Piece] = []
        for _ in range(MAX_ATTEMPTS):
            tray = [self.piece(hardness) for _ in range(TRAY_SLOTS)]
            if self._is_fair(board, tray):
                return tray
        # Запасной вариант: гарантируем хотя бы одну подходящую фигуру (если такая вообще есть)
        if self.profile.fairness != "none" and not any(board.has_room_for(p.shape) for p in tray):
            fitting = [s for s in SHAPES if board.has_room_for(s)]
            if fitting:
                smallest = min(s.size for s in fitting)
                shape = self.rng.choice([s for s in fitting if s.size == smallest])
                tray[self.rng.randrange(TRAY_SLOTS)] = self._make(shape, self.rng.randrange(PALETTE_SLOTS))
        return tray

# ======================================================================
# blockblast/core/modes.py
# ======================================================================

"""Режимы игры: бесконечный и уровни с целями."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class Goal:
    kind: str    # "score" | "lines" | "combo"
    target: int

    def text(self) -> str:
        if self.kind == "score":
            return f"Набери {self.target} очков"
        if self.kind == "lines":
            return f"Очисти {self.target} линий"
        return f"Сделай комбо x{self.target}"


class EndlessMode:
    id = "endless"

    def hardness(self, game: "Game") -> float:
        # плавно усложняемся по мере роста счёта
        return min(0.6, game.score / 25000)

    def progress(self, game: "Game") -> Optional[tuple[int, int]]:
        return None

    def goal(self) -> Optional[Goal]:
        return None

    def on_move(self, game: "Game", move: MoveScore) -> list:
        return []

    def to_data(self) -> dict:
        return {}

    def load(self, data: dict) -> None:
        pass


class LevelMode:
    id = "levels"
    KINDS = ("score", "lines", "combo")

    def __init__(self) -> None:
        self.level = 1
        self.base_score = 0
        self.base_lines = 0
        self._goal = self.goal_for(1)

    @staticmethod
    def goal_for(level: int) -> Goal:
        kind = LevelMode.KINDS[(level - 1) % len(LevelMode.KINDS)]
        if kind == "score":
            return Goal(kind, 250 + 150 * level)
        if kind == "lines":
            return Goal(kind, 3 + level)
        return Goal(kind, min(2 + level // 3, 8))

    def goal(self) -> Goal:
        return self._goal

    def hardness(self, game: "Game") -> float:
        return min(1.0, (self.level - 1) * 0.08)

    def progress(self, game: "Game") -> tuple[int, int]:
        g = self._goal
        if g.kind == "score":
            cur = game.score - self.base_score
        elif g.kind == "lines":
            cur = game.lines_total - self.base_lines
        else:
            cur = game.combo.streak
        return max(0, min(cur, g.target)), g.target

    def on_move(self, game: "Game", move: MoveScore) -> list:
        cur, target = self.progress(game)
        if cur < target:
            return []
        self.level += 1
        bonus = 50 * self.level
        game.score += bonus
        self.base_score = game.score
        self.base_lines = game.lines_total
        self._goal = self.goal_for(self.level)
        return [LevelUp(self.level, bonus, self._goal.text())]

    def to_data(self) -> dict:
        return {"level": self.level, "base_score": self.base_score, "base_lines": self.base_lines}

    def load(self, data: dict) -> None:
        self.level = max(1, int(data.get("level", 1)))
        self.base_score = int(data.get("base_score", 0))
        self.base_lines = int(data.get("base_lines", 0))
        self._goal = self.goal_for(self.level)


def create_mode(mode_id: str):
    return LevelMode() if mode_id == "levels" else EndlessMode()

# ======================================================================
# blockblast/core/advisor.py
# ======================================================================

"""Подсказки: поиск хорошего хода простой эвристикой."""

from dataclasses import dataclass
from typing import Optional, Sequence



@dataclass(frozen=True)
class Move:
    tray_index: int
    row: int
    col: int
    value: float


def _isolated_holes(board: Board) -> int:
    """Пустые клетки, со всех сторон зажатые стенами/блоками — в них мало что влезет."""
    n = board.size
    cells = board.cells
    holes = 0
    for r in range(n):
        for c in range(n):
            if cells[r][c] is not None:
                continue
            if all(
                not (0 <= rr < n and 0 <= cc < n) or cells[rr][cc] is not None
                for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
            ):
                holes += 1
    return holes


def evaluate(board: Board, shape: Shape, row: int, col: int) -> float:
    rows, cols = board.lines_if_placed(shape, row, col)
    lines = len(rows) + len(cols)
    n = board.size

    # «прилипание»: сколько сторон фигуры касаются стен или блоков
    occupied = {(row + dr, col + dc) for dr, dc in shape.cells}
    contacts = 0
    for r, c in occupied:
        for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if (rr, cc) in occupied:
                continue
            if not (0 <= rr < n and 0 <= cc < n) or board.cells[rr][cc] is not None:
                contacts += 1

    sim = board.copy()
    sim.place(shape, 0, row, col)
    sim.clear_lines(rows, cols)

    return (
        lines * 100
        + (lines - 1) * 40 * (lines > 1)
        + contacts * 3
        - _isolated_holes(sim) * 12
        + (200 if sim.is_empty() else 0)
    )


def best_move(board: Board, tray: Sequence[Optional[Piece]]) -> Optional[Move]:
    best: Optional[Move] = None
    for idx, piece in enumerate(tray):
        if piece is None:
            continue
        for r, c in board.valid_positions(piece.shape):
            v = evaluate(board, piece.shape, r, c)
            if best is None or v > best.value:
                best = Move(idx, r, c, v)
    return best

# ======================================================================
# blockblast/core/game.py
# ======================================================================

"""Игровая сессия: поле + лоток + очки + режим. Без pygame, легко тестируется."""

import random
from typing import Optional


SAVE_VERSION = 2


class Game:
    def __init__(self, board_size: int = 8, difficulty: str = "normal",
                 mode: str = "endless", seed: Optional[int] = None):
        self.board = Board(board_size)
        self.difficulty = difficulty
        self.rng = random.Random(seed)
        self.generator = PieceGenerator(self.rng, difficulty)
        self.mode = create_mode(mode)
        self.combo = ComboTracker()
        self.score = 0
        self.moves = 0
        self.lines_total = 0
        self.max_lines_move = 0
        self.perfect_clears = 0
        self.over = False
        self._events: list = []
        self._playable_cache: tuple[int, int, list[bool]] = (-1, -1, [])
        self._tray_version = 0
        self.tray: list[Optional[Piece]] = self.generator.new_tray(self.board, 0.0)

    # ---------- события ----------

    def drain_events(self) -> list:
        out, self._events = self._events, []
        return out

    # ---------- запросы ----------

    @property
    def mode_id(self) -> str:
        return self.mode.id

    def can_place(self, tray_index: int, row: int, col: int) -> bool:
        piece = self.piece_at(tray_index)
        return piece is not None and self.board.can_place(piece.shape, row, col)

    def piece_at(self, tray_index: int) -> Optional[Piece]:
        if 0 <= tray_index < len(self.tray):
            return self.tray[tray_index]
        return None

    def playable(self) -> list[bool]:
        """Какие фигуры лотка вообще куда-то влезают (кэш по версии поля/лотка)."""
        bv, tv, value = self._playable_cache
        if bv != self.board.version or tv != self._tray_version:
            value = [p is not None and self.board.has_room_for(p.shape) for p in self.tray]
            self._playable_cache = (self.board.version, self._tray_version, value)
        return value

    def hint(self) -> Optional[Move]:
        if self.over:
            return None
        return best_move(self.board, self.tray)

    # ---------- ход ----------

    def place(self, tray_index: int, row: int, col: int) -> Optional[MoveScore]:
        if self.over or not self.can_place(tray_index, row, col):
            return None
        piece = self.tray[tray_index]
        assert piece is not None

        placed = self.board.place(piece.shape, piece.color, row, col, piece.labels)
        self.tray[tray_index] = None
        self._tray_version += 1
        self.moves += 1
        self._events.append(ev.PiecePlaced(tray_index, piece, row, col, placed))

        rows, cols = self.board.full_lines()
        lines = len(rows) + len(cols)
        cleared = self.board.clear_lines(rows, cols)

        prev_streak = self.combo.streak
        streak, broken = self.combo.register(lines)
        perfect = lines > 0 and self.board.is_empty()
        move = score_move(len(placed), lines, streak, perfect, self.board.size)

        self.score += move.total
        self.lines_total += lines
        self.max_lines_move = max(self.max_lines_move, lines)

        if lines:
            origin = (row + piece.shape.rows / 2, col + piece.shape.cols / 2)
            self._events.append(ev.LinesCleared(rows, cols, cleared, move, origin))
        if broken:
            self._events.append(ev.ComboBroken(prev_streak))
        if perfect:
            self.perfect_clears += 1
            self._events.append(ev.PerfectClear(move.perfect_bonus))
        self._events.append(ev.ScoreGained(move))

        self._events.extend(self.mode.on_move(self, move))

        if all(p is None for p in self.tray):
            self.tray = list(self.generator.new_tray(self.board, self.mode.hardness(self)))
            self._tray_version += 1
            self._events.append(ev.TrayRefilled(list(self.tray)))

        if not any(self.playable()):
            self.over = True
            self._events.append(ev.GameOver(self.score))
        return move

    # ---------- сохранение ----------

    def to_data(self) -> dict:
        state = self.rng.getstate()
        return {
            "version": SAVE_VERSION,
            "board": self.board.to_data(),
            "labels": self.board.labels_to_data(),
            "next_letter": self.generator._next_letter,
            "tray": [None if p is None else p.to_data() for p in self.tray],
            "difficulty": self.difficulty,
            "mode": self.mode.id,
            "mode_state": self.mode.to_data(),
            "combo": self.combo.to_data(),
            "score": self.score,
            "moves": self.moves,
            "lines_total": self.lines_total,
            "max_lines_move": self.max_lines_move,
            "perfect_clears": self.perfect_clears,
            "rng": [state[0], list(state[1]), state[2]],
        }

    @staticmethod
    def from_data(data: dict) -> "Game":
        if data.get("version") != SAVE_VERSION:
            raise ValueError("несовместимая версия сохранения")
        board = Board.from_data(data["board"])
        game = Game(board.size, data.get("difficulty", "normal"), data.get("mode", "endless"))
        board.load_labels(data.get("labels"))
        next_letter = data.get("next_letter")
        game.board = board
        if isinstance(next_letter, int):              # буквы продолжаются, а не с «A» заново
            game.generator._next_letter = next_letter % 26
        tray = [None if p is None else Piece.from_data(p) for p in data["tray"]]
        if len(tray) != TRAY_SLOTS:
            raise ValueError("повреждённый лоток")
        game.tray = tray
        game.mode.load(data.get("mode_state", {}))
        game.combo.load(data.get("combo", {}))
        game.score = int(data["score"])
        game.moves = int(data.get("moves", 0))
        game.lines_total = int(data.get("lines_total", 0))
        game.max_lines_move = int(data.get("max_lines_move", 0))
        game.perfect_clears = int(data.get("perfect_clears", 0))
        rng = data.get("rng")
        if rng:
            game.rng.setstate((rng[0], tuple(rng[1]), rng[2]))
        if all(p is None for p in game.tray):
            game.tray = list(game.generator.new_tray(game.board, game.mode.hardness(game)))
        game.over = not any(game.playable())
        return game

# ======================================================================
# blockblast/data/storage.py
# ======================================================================

"""Сохранение настроек, рекордов, достижений и незаконченной игры.

* Всё хранится в JSON в папке пользователя (а не рядом со скриптом —
  там может не быть прав на запись).
* Запись атомарная (tmp-файл + os.replace): сбой при записи не портит файл.
* Битый файл не роняет игру — берутся значения по умолчанию.
"""

import json
import os
import queue
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Optional



def _writable(directory: str) -> bool:
    try:
        os.makedirs(directory, exist_ok=True)
        probe = os.path.join(directory, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def default_data_dir() -> str:
    if IS_ANDROID:
        # Pydroid: рядом со скриптом удобнее (видно в файловом менеджере, легко забэкапить),
        # но на новых Android туда может не быть доступа — тогда в приватную папку приложения
        near_script = os.path.join(PROJECT_DIR, "block_blast_data")
        if _writable(near_script):
            return near_script
        return os.path.join(os.path.expanduser("~"), ".block_blast")
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "BlockBlast")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/BlockBlast")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "block_blast")


def leaderboard_key(mode: str, board_size: int, difficulty: str) -> str:
    return f"{mode}-{board_size}-{difficulty}"


@dataclass
class Settings:
    theme: str = "watermelon"          # id темы или "auto"
    mode: str = "endless"
    difficulty: str = "normal"
    board_size: int = 8
    sfx_volume: float = 0.8
    music_volume: float = 0.35
    # В браузере рисует процессор, без видеокарты: цена кадра прямо пропорциональна
    # числу пикселей. Замер на телефоне: «Родное» 16 FPS, «Низкое» 40 FPS.
    # «Среднее» — компромисс; игрок всегда может переключить в настройках.
    quality: str = "medium" if IS_WEB else ("high" if IS_ANDROID else "native")
    hints: bool = True
    full_animations: bool = True
    screen_shake: bool = True
    show_fps: bool = False
    fullscreen: bool = False
    window_size: list = field(default_factory=list)

    @staticmethod
    def from_dict(data: Any) -> "Settings":
        s = Settings()
        if not isinstance(data, dict):
            return s
        for f in fields(Settings):
            if f.name not in data:
                continue
            value, default = data[f.name], getattr(s, f.name)
            if isinstance(default, bool):
                if isinstance(value, bool):
                    setattr(s, f.name, value)
            elif isinstance(default, float):
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    setattr(s, f.name, max(0.0, min(1.0, float(value))))
            elif isinstance(default, int):
                if isinstance(value, int) and not isinstance(value, bool):
                    setattr(s, f.name, value)
            elif isinstance(default, str):
                if isinstance(value, str):
                    setattr(s, f.name, value)
            elif isinstance(default, list):
                if isinstance(value, list) and len(value) == 2 and all(isinstance(v, int) for v in value):
                    setattr(s, f.name, value)
        if s.mode not in MODES:
            s.mode = "endless"
        if s.difficulty not in DIFFICULTIES:
            s.difficulty = "normal"
        if s.board_size not in BOARD_SIZES:
            s.board_size = 8
        if s.quality not in QUALITY_LEVELS:
            s.quality = "high"
        return s

    def to_dict(self) -> dict:
        return asdict(self)


class Profile:
    """Рекорды, общая статистика и полученные достижения."""

    def __init__(self) -> None:
        self.highscores: dict[str, list[dict]] = {}
        self.stats: dict[str, int] = {}
        self.achievements: dict[str, str] = {}
        self.themes_seen: list[str] = []

    # --- таблица рекордов ---
    def leaderboard(self, key: str) -> list[dict]:
        return self.highscores.get(key, [])

    def best(self, key: str) -> int:
        board = self.leaderboard(key)
        return board[0]["score"] if board else 0

    def add_score(self, key: str, score: int, lines: int, level: int = 0) -> Optional[int]:
        """Добавляет результат; возвращает место (1..N) или None, если не попал в таблицу."""
        if score <= 0:
            return None
        board = self.highscores.setdefault(key, [])
        entry = {"score": int(score), "lines": int(lines), "level": int(level),
                 "date": time.strftime("%d.%m.%Y")}
        board.append(entry)
        board.sort(key=lambda e: -e["score"])  # стабильная сортировка: старые выше при равенстве
        del board[LEADERBOARD_SIZE:]
        for i, e in enumerate(board):
            if e is entry:
                return i + 1
        return None

    # --- статистика ---
    def stat(self, key: str) -> int:
        return int(self.stats.get(key, 0))

    def add_stat(self, key: str, amount: int = 1) -> None:
        self.stats[key] = self.stat(key) + amount

    def max_stat(self, key: str, value: int) -> None:
        if value > self.stat(key):
            self.stats[key] = int(value)

    def mark_theme_seen(self, theme_id: str) -> None:
        if theme_id not in self.themes_seen:
            self.themes_seen.append(theme_id)
            self.stats["themes_seen"] = len(self.themes_seen)

    def to_dict(self) -> dict:
        return {"highscores": self.highscores, "stats": self.stats,
                "achievements": self.achievements, "themes_seen": self.themes_seen}

    @staticmethod
    def from_dict(data: Any) -> "Profile":
        p = Profile()
        if not isinstance(data, dict):
            return p
        hs = data.get("highscores")
        if isinstance(hs, dict):
            for key, board in hs.items():
                if isinstance(board, list):
                    clean = [e for e in board if isinstance(e, dict) and isinstance(e.get("score"), int)]
                    p.highscores[key] = sorted(clean, key=lambda e: -e["score"])[:LEADERBOARD_SIZE]
        if isinstance(data.get("stats"), dict):
            p.stats = {k: v for k, v in data["stats"].items() if isinstance(v, int)}
        if isinstance(data.get("achievements"), dict):
            p.achievements = {k: str(v) for k, v in data["achievements"].items()}
        if isinstance(data.get("themes_seen"), list):
            p.themes_seen = [t for t in data["themes_seen"] if isinstance(t, str)]
        return p


class Storage:
    SETTINGS = "settings.json"
    PROFILE = "profile.json"
    SAVEGAME = "savegame.json"

    def __init__(self, directory: Optional[str] = None, legacy_dir: Optional[str] = None):
        self.dir = directory or default_data_dir()
        self.legacy_dir = legacy_dir
        self._pending: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._done = threading.Condition(self._lock)   # тот же замок
        self._writing: set[str] = set()                # что прямо сейчас пишется на диск
        self._wake = threading.Event()
        self._worker: Optional[threading.Thread] = None
        try:
            os.makedirs(self.dir, exist_ok=True)
        except OSError as exc:  # только чтение → работаем без сохранений
            print(f"[storage] нет доступа к {self.dir}: {exc}", file=sys.stderr)

    def _write_async(self, name: str, data: Any) -> None:
        """Запись на диск в фоне: на телефоне она занимает десятки миллисекунд
        и в главном потоке давала заметную паузу после хода."""
        if IS_WEB:
            # В WebAssembly настоящих потоков нет: фоновая запись там либо
            # молча не выполняется, либо роняет вкладку. Пишем сразу.
            self._write(name, data)
            return
        with self._lock:
            self._pending[name] = data          # копится только последнее состояние
            if self._worker is None:
                self._worker = threading.Thread(target=self._worker_loop, daemon=True)
                self._worker.start()
        self._wake.set()

    def _worker_loop(self) -> None:
        while True:
            self._wake.wait()
            self._wake.clear()
            while True:
                with self._lock:
                    if not self._pending:
                        break
                    name, data = self._pending.popitem()
                    self._writing.add(name)         # запись «в полёте»
                try:
                    self._write(name, data)
                finally:
                    with self._done:
                        self._writing.discard(name)
                        self._done.notify_all()

    def flush(self) -> None:
        """Дописать всё отложенное (перед выходом и сворачиванием)."""
        while True:
            with self._lock:
                if not self._pending:
                    return
                name, data = self._pending.popitem()
            self._write(name, data)

    def _path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    def _read(self, name: str) -> Any:
        with self._lock:
            if name in self._pending:
                # ещё не записано на диск, но это самое свежее состояние
                return self._pending[name]
        try:
            with open(self._path(name), "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            print(f"[storage] не удалось прочитать {name}: {exc}", file=sys.stderr)
            return None

    def _write(self, name: str, data: Any) -> bool:
        try:
            fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".tmp_", suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self._path(name))
            return True
        except OSError as exc:
            print(f"[storage] не удалось записать {name}: {exc}", file=sys.stderr)
            return False

    # --- настройки ---
    def load_settings(self) -> Settings:
        return Settings.from_dict(self._read(self.SETTINGS))

    def save_settings(self, settings: Settings) -> None:
        self._write(self.SETTINGS, settings.to_dict())

    # --- профиль ---
    def load_profile(self) -> Profile:
        raw = self._read(self.PROFILE)
        profile = Profile.from_dict(raw)
        if raw is None:
            self._migrate_legacy_record(profile)
        return profile

    def save_profile(self, profile: Profile, background: bool = True) -> None:
        data = profile.to_dict()
        if background:
            self._write_async(self.PROFILE, data)
        else:
            self._write(self.PROFILE, data)

    def _migrate_legacy_record(self, profile: Profile) -> None:
        """Переносим рекорд из watermelon_record.txt старой версии игры."""
        if not self.legacy_dir:
            return
        try:
            with open(os.path.join(self.legacy_dir, "watermelon_record.txt"), "r") as f:
                record = int(f.read().strip())
        except (OSError, ValueError):
            return
        if record > 0:
            profile.add_score(leaderboard_key("endless", 8, "normal"), record, lines=0)
            self.save_profile(profile)

    # --- незаконченная игра ---
    def load_game(self) -> Optional[dict]:
        data = self._read(self.SAVEGAME)
        return data if isinstance(data, dict) else None

    def save_game(self, data: dict, background: bool = True) -> None:
        if background:
            self._write_async(self.SAVEGAME, data)
        else:
            self._write(self.SAVEGAME, data)

    def delete_game(self) -> None:
        with self._done:
            self._pending.pop(self.SAVEGAME, None)   # отменяем неуспевшую запись
            # Запись могли уже забрать из очереди и писать на диск прямо сейчас —
            # тогда удаление надо делать ПОСЛЕ неё, иначе файл воскреснет.
            deadline = time.monotonic() + 5.0
            while self.SAVEGAME in self._writing and time.monotonic() < deadline:
                self._done.wait(0.1)
        try:
            os.remove(self._path(self.SAVEGAME))
        except OSError:
            pass

# ======================================================================
# blockblast/data/achievements.py
# ======================================================================

"""Достижения. Все они описаны как «статистика ≥ порог» — так проще
показывать прогресс и не нужен отдельный код на каждое достижение."""

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class Achievement:
    id: str
    title: str
    description: str
    stat: str
    target: int


ACHIEVEMENTS: tuple[Achievement, ...] = (
    Achievement("first_clear", "Первая линия", "Очисти любую линию", "lines_total", 1),
    Achievement("lines_100", "Сотня", "Очисти 100 линий за всё время", "lines_total", 100),
    Achievement("lines_1000", "Тысячник", "Очисти 1000 линий за всё время", "lines_total", 1000),
    Achievement("multi_3", "Тройной удар", "Очисти 3 линии одним ходом", "max_lines_move", 3),
    Achievement("multi_5", "Разрушитель", "Очисти 5 линий одним ходом", "max_lines_move", 5),
    Achievement("combo_4", "В ритме", "Сделай комбо x4", "best_streak", 4),
    Achievement("combo_8", "Комбо-мастер", "Сделай комбо x8", "best_streak", 8),
    Achievement("perfect", "Идеально чисто", "Очисти поле полностью", "perfect_clears", 1),
    Achievement("perfect_10", "Чистюля", "Очисти поле полностью 10 раз", "perfect_clears", 10),
    Achievement("score_1000", "Разминка", "Набери 1 000 очков за игру", "best_score", 1000),
    Achievement("score_5000", "Профи", "Набери 5 000 очков за игру", "best_score", 5000),
    Achievement("score_20000", "Легенда", "Набери 20 000 очков за игру", "best_score", 20000),
    Achievement("level_5", "Покоритель", "Дойди до 5 уровня", "best_level", 5),
    Achievement("level_10", "Вершина", "Дойди до 10 уровня", "best_level", 10),
    Achievement("level_20", "Мастер уровней", "Дойди до 20 уровня", "best_level", 20),
    Achievement("small_board", "В тесноте", "Набери 1 000 очков на поле 6×6", "best_score_6", 1000),
    Achievement("big_board", "Простор", "Набери 3 000 очков на поле 10×10", "best_score_10", 3000),
    Achievement("blocks_1000", "Строитель", "Поставь 1 000 блоков за всё время", "cells_total", 1000),
    Achievement("blocks_5000", "Прораб", "Поставь 5 000 блоков за всё время", "cells_total", 5000),
    Achievement("blocks_10000", "Архитектор", "Поставь 10 000 блоков за всё время", "cells_total", 10000),
    Achievement("pieces_1000", "Тысяча фигур", "Поставь 1 000 фигур за всё время", "pieces_total", 1000),
    Achievement("score_total_100k", "Стотысячник", "Набери 100 000 очков за всё время", "score_total", 100000),
    Achievement("games_10", "Завсегдатай", "Сыграй 10 игр", "games_played", 10),
    Achievement("games_50", "Марафонец", "Сыграй 50 игр", "games_played", 50),
    Achievement("games_100", "Сотня партий", "Сыграй 100 игр", "games_played", 100),
    Achievement("themes_all", "Коллекционер", "Попробуй все темы", "themes_seen", 36),
)


class AchievementTracker:
    def __init__(self, profile: Profile):
        self.profile = profile

    def progress(self, a: Achievement) -> tuple[int, int]:
        return min(self.profile.stat(a.stat), a.target), a.target

    def is_unlocked(self, a: Achievement) -> bool:
        return a.id in self.profile.achievements

    def check(self) -> list[Achievement]:
        new = []
        for a in ACHIEVEMENTS:
            if a.id not in self.profile.achievements and self.profile.stat(a.stat) >= a.target:
                self.profile.achievements[a.id] = time.strftime("%d.%m.%Y")
                new.append(a)
        return new

    def on_event(self, event, game: "Game") -> list[Achievement]:
        p = self.profile
        if isinstance(event, ev.PiecePlaced):
            p.add_stat("cells_total", len(event.cells))
            p.add_stat("pieces_total")
        elif isinstance(event, ev.LinesCleared):
            p.add_stat("lines_total", event.move.lines)
            p.max_stat("max_lines_move", event.move.lines)
            p.max_stat("best_streak", event.move.streak)
        elif isinstance(event, ev.PerfectClear):
            p.add_stat("perfect_clears")
        elif isinstance(event, ev.ScoreGained):
            p.add_stat("score_total", event.move.total)
            p.max_stat("best_score", game.score)
            p.max_stat(f"best_score_{game.board.size}", game.score)
        elif isinstance(event, ev.LevelUp):
            p.max_stat("best_level", event.level)
        elif isinstance(event, ev.GameOver):
            p.add_stat("games_played")
        else:
            return []
        return self.check()

    def on_theme(self, theme_id: str) -> list[Achievement]:
        self.profile.mark_theme_seen(theme_id)
        return self.check()

# ======================================================================
# blockblast/audio/synth.py
# ======================================================================

"""Процедурный синтез звуков и музыки — игра звучит без внешних файлов.
Модуль не зависит от pygame: на выходе обычные 16-битные PCM-байты."""

import math
import random
from array import array

Samples = list[float]

NOTE_A4 = 440.0


def note(semitones_from_a4: float) -> float:
    return NOTE_A4 * 2 ** (semitones_from_a4 / 12)


def _osc(phase: float, wave: str) -> float:
    p = phase % 1.0
    if wave == "sine":
        return math.sin(2 * math.pi * p)
    if wave == "tri":
        return 4 * p - 1 if p < 0.5 else 3 - 4 * p
    if wave == "square":
        return 0.6 if p < 0.5 else -0.6
    return 2 * p - 1  # saw


def tone(rate: int, freq: float, dur: float, wave: str = "sine", vol: float = 0.5,
         slide_to: float | None = None, attack: float = 0.005, decay: float = 6.0) -> Samples:
    n = max(1, int(rate * dur))
    out = [0.0] * n
    phase = 0.0
    f_end = slide_to if slide_to is not None else freq
    att_n = max(1, int(rate * attack))
    for i in range(n):
        t = i / n
        f = freq + (f_end - freq) * t
        phase += f / rate
        env = min(1.0, i / att_n) * math.exp(-decay * t)
        out[i] = _osc(phase, wave) * env * vol
    return out


def noise(rate: int, dur: float, vol: float = 0.3, decay: float = 8.0, seed: int = 1) -> Samples:
    rng = random.Random(seed)
    n = max(1, int(rate * dur))
    prev = 0.0
    out = [0.0] * n
    for i in range(n):
        prev = prev * 0.7 + rng.uniform(-1, 1) * 0.3  # простейший ФНЧ → мягкий «шорох»
        out[i] = prev * vol * math.exp(-decay * i / n)
    return out


def mix(*parts: tuple[float, Samples], rate: int) -> Samples:
    """parts: (смещение в секундах, сэмплы)."""
    length = max(int(off * rate) + len(s) for off, s in parts)
    out = [0.0] * length
    for off, s in parts:
        start = int(off * rate)
        for i, v in enumerate(s):
            out[start + i] += v
    return out


def upsample(samples: Samples, factor: int) -> Samples:
    """Линейная интерполяция: синтез на пониженной частоте в factor раз дешевле
    (важно для телефонов, где чистый Python в 3–5 раз медленнее)."""
    if factor <= 1:
        return samples
    out = []
    append = out.append
    for i in range(len(samples) - 1):
        a, b = samples[i], samples[i + 1]
        step = (b - a) / factor
        for k in range(factor):
            append(a + step * k)
    out.extend([samples[-1]] * factor)
    return out


def to_pcm(samples: Samples, channels: int = 1, gain: float = 1.0) -> bytes:
    peak = max(1e-6, max(abs(v) for v in samples))
    scale = 32767 * gain / max(1.0, peak)  # мягкая нормализация, без клиппинга
    data = array("h", (int(max(-1.0, min(1.0, v)) * scale) for v in samples))
    if channels > 1:
        stereo = array("h", bytes(len(data) * channels * 2))
        for ch in range(channels):
            stereo[ch::channels] = data
        data = stereo
    return data.tobytes()


# ---------------- звуковые эффекты ----------------

def sfx(name: str, rate: int, level: int = 1) -> Samples:
    if name == "pick":
        return tone(rate, 620, 0.06, "tri", 0.35, slide_to=900, decay=5)
    if name == "place":
        return tone(rate, 200, 0.09, "sine", 0.7, slide_to=110, decay=7)
    if name == "invalid":
        return tone(rate, 220, 0.14, "square", 0.25, slide_to=150, decay=4)
    if name == "click":
        return tone(rate, 1200, 0.025, "tri", 0.25, decay=10)
    if name == "clear":
        # арпеджио растёт с количеством линий
        steps = [0, 4, 7, 12, 16, 19][: min(6, 2 + level)]
        parts = [(0.045 * i, tone(rate, note(3 + s), 0.18, "tri", 0.4, decay=5)) for i, s in enumerate(steps)]
        return mix(*parts, rate=rate)
    if name == "combo":
        base = 3 + 2 * min(level, 8)  # выше тон — длиннее серия
        return mix((0, tone(rate, note(base), 0.12, "square", 0.22, decay=6)),
                   (0.06, tone(rate, note(base + 7), 0.2, "square", 0.22, decay=5)), rate=rate)
    if name == "perfect":
        chord = [0, 4, 7, 12, 16]
        return mix(*[(0.03 * i, tone(rate, note(3 + c), 0.7, "sine", 0.3, decay=3)) for i, c in enumerate(chord)],
                   rate=rate)
    if name == "level_up":
        seq = [0, 4, 7, 12]
        return mix(*[(0.09 * i, tone(rate, note(5 + s), 0.25 if i < 3 else 0.5, "tri", 0.4, decay=4))
                     for i, s in enumerate(seq)], rate=rate)
    if name == "game_over":
        seq = [7, 3, 0, -5]
        return mix(*[(0.16 * i, tone(rate, note(s - 5), 0.35, "tri", 0.4, decay=3)) for i, s in enumerate(seq)],
                   rate=rate)
    if name == "achievement":
        return mix((0, tone(rate, note(10), 0.25, "sine", 0.35, decay=4)),
                   (0.1, tone(rate, note(15), 0.45, "sine", 0.35, decay=3)), rate=rate)
    raise KeyError(name)


# ---------------- фоновая музыка ----------------

def music_loop(rate: int, bpm: int = 96) -> Samples:
    """Спокойная петля: пэд на аккордах Am–F–C–G + мягкое арпеджио.
    Длина кратна тактам, поэтому петля бесшовная."""
    beat = 60 / bpm
    bar = beat * 4
    progression = [(-12, [0, 3, 7]), (-16, [0, 4, 7]), (-9, [0, 4, 7]), (-14, [0, 4, 7])]
    total = int(rate * bar * len(progression))
    out = [0.0] * total

    for bi, (root, chord) in enumerate(progression):
        start = int(bi * bar * rate)
        length = int(bar * rate)
        for iv in chord:
            f = note(root + iv)
            ph_step = f / rate
            for i in range(length):
                t = i / length
                env = min(1.0, t * 8) * min(1.0, (1 - t) * 8)
                out[start + i] += math.sin(2 * math.pi * ph_step * i) * 0.09 * env
        arp = [chord[0], chord[1], chord[2], chord[1] + 12, chord[2], chord[1], chord[2] + 12, chord[1]]
        for k, iv in enumerate(arp):
            s = tone(rate, note(root + 12 + iv), beat / 2 * 0.95, "tri", 0.07, decay=4)
            off = start + int(k * beat / 2 * rate)
            for i, v in enumerate(s):
                if off + i < total:
                    out[off + i] += v
    return out

synth = _namespace("Samples", "NOTE_A4", "note", "_osc", "tone", "noise", "mix", "upsample", "to_pcm", "sfx", "music_loop")

# ======================================================================
# blockblast/audio/manager.py
# ======================================================================

"""Звук и музыка.

* Если аудиоустройства нет — игра работает молча, без падений.
* Весь синтез идёт в фоновом потоке: запуск не блокируется даже на телефоне.
  Поток готовит только байты PCM, а pygame.mixer.Sound создаётся в главном потоке.
* На слабых устройствах синтезируем на пониженной частоте и интерполируем."""

import os
import queue
import sys
import threading
from typing import Optional

import pygame


SOUND_EXT = (".ogg", ".wav", ".mp3")
LEVELED = {"clear": 6, "combo": 8}
SIMPLE = ("pick", "place", "invalid", "click", "perfect", "level_up", "game_over", "achievement")
# порядок синтеза: сначала то, что звучит чаще всего
SYNTH_ORDER = ("place", "pick", "click", "invalid", "clear1", "clear2", "combo2", "clear3", "combo3",
               "clear4", "combo4", "perfect", "level_up", "game_over", "achievement",
               "clear5", "clear6", "combo1", "combo5", "combo6", "combo7", "combo8")


class AudioManager:
    def __init__(self, sfx_volume: float, music_volume: float):
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.sfx_volume = sfx_volume
        self.music_volume = music_volume
        self.paused = False
        self._music_channel: Optional[pygame.mixer.Channel] = None
        self._music_sound: Optional[pygame.mixer.Sound] = None
        self._file_music = False
        self._ready: "queue.Queue[tuple[str, bytes]]" = queue.Queue()
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.rate, fmt, self.channels = pygame.mixer.get_init()
            if abs(fmt) != 16:
                raise pygame.error(f"неподдерживаемый формат звука: {fmt}")
            pygame.mixer.set_num_channels(16)
            self.enabled = True
        except (pygame.error, TypeError) as exc:
            print(f"[audio] звук отключён: {exc}", file=sys.stderr)
            return

        # В браузере реальная частота звука (self.rate) может оказаться выше
        # запрошенной (например, 44100/48000 вместо 22050) — Web Audio API сам
        # решает, на чём работать. Понижение там ни к чему, оно даёт шуршание
        # после линейной интерполяции при апсемплинге.
        target = 11025 if IS_ANDROID else (self.rate if IS_WEB else 16000)
        self.factor = max(1, self.rate // target)
        to_synth = self._load_files()
        if IS_WEB:
            # В браузере (pygbag/WebAssembly) настоящих потоков нет — синтезируем сразу,
            # как и с записью на диск в Storage._write_async.
            self._synth_worker(to_synth)
        else:
            threading.Thread(target=self._synth_worker, args=(to_synth,), daemon=True).start()

    # ---------- загрузка ----------

    def _file_for(self, folder: str, name: str) -> Optional[str]:
        for ext in SOUND_EXT:
            path = os.path.join(ASSETS_DIR, folder, name + ext)
            if os.path.isfile(path):
                return path
        return None

    def _load_files(self) -> list[str]:
        """Свои файлы из assets/ грузим сразу; возвращаем то, что нужно синтезировать."""
        missing = []
        for name in SIMPLE + tuple(LEVELED):
            path = self._file_for("sounds", name)
            sound = None
            if path:
                try:
                    sound = pygame.mixer.Sound(path)
                except pygame.error as exc:
                    print(f"[audio] {path}: {exc}", file=sys.stderr)
            keys = [f"{name}{i}" for i in range(1, LEVELED[name] + 1)] if name in LEVELED else [name]
            for key in keys:
                if sound is not None:
                    self.sounds[key] = sound
                else:
                    missing.append(key)

        music_path = self._file_for("music", "music")
        if music_path:
            try:
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(-1)
                self._file_music = True
            except pygame.error as exc:
                print(f"[audio] {music_path}: {exc}", file=sys.stderr)
        order = {k: i for i, k in enumerate(SYNTH_ORDER)}
        return sorted(missing, key=lambda k: order.get(k, 99))

    def _synth_worker(self, keys: list[str]) -> None:
        rate = self.rate // self.factor
        try:
            for key in keys:
                name = key.rstrip("0123456789")
                level = int(key[len(name):] or 0)
                samples = synth.sfx(name, rate, level) if level else synth.sfx(name, rate)
                self._ready.put((key, synth.to_pcm(synth.upsample(samples, self.factor), self.channels, 0.85)))
            if not self._file_music:
                loop = synth.upsample(synth.music_loop(rate), self.factor)
                self._ready.put(("__music__", synth.to_pcm(loop, self.channels, 0.9)))
        except Exception as exc:  # синтез не должен ронять игру
            print(f"[audio] ошибка синтеза: {exc}", file=sys.stderr)

    def update(self) -> None:
        """Каждый кадр: превращаем готовые байты в Sound (быстро, в главном потоке)."""
        if not self.enabled:
            return
        for _ in range(4):
            try:
                key, pcm = self._ready.get_nowait()
            except queue.Empty:
                break
            sound = pygame.mixer.Sound(buffer=pcm)
            if key != "__music__":
                self.sounds[key] = sound
                continue
            self._music_sound = sound
            if not self.paused:
                self._music_channel = sound.play(loops=-1)
                self.set_music_volume(self.music_volume)

    @property
    def loading(self) -> bool:
        return self.enabled and (not self._ready.empty() or (not self._file_music and self._music_sound is None))

    # ---------- воспроизведение ----------

    def play(self, name: str, level: int = 0) -> None:
        if not self.enabled or self.paused or self.sfx_volume <= 0:
            return
        if name in LEVELED:
            name = f"{name}{max(1, min(level, LEVELED[name]))}"
        sound = self.sounds.get(name)
        if sound is None:  # ещё синтезируется — просто пропускаем
            return
        channel = sound.play()
        if channel is not None:
            channel.set_volume(self.sfx_volume)

    def set_sfx_volume(self, v: float) -> None:
        self.sfx_volume = max(0.0, min(1.0, v))

    def set_music_volume(self, v: float) -> None:
        self.music_volume = max(0.0, min(1.0, v))
        if not self.enabled:
            return
        if self._file_music:
            pygame.mixer.music.set_volume(self.music_volume)
        elif self._music_channel is not None:
            self._music_channel.set_volume(self.music_volume)

    def pause_all(self) -> None:
        """Приложение ушло в фон (Android): тишина и никаких звуков до возвращения."""
        if self.enabled and not self.paused:
            self.paused = True
            pygame.mixer.pause()
            if self._file_music:
                pygame.mixer.music.pause()

    def resume_all(self) -> None:
        if self.enabled and self.paused:
            self.paused = False
            pygame.mixer.unpause()
            if self._file_music:
                pygame.mixer.music.unpause()
            elif self._music_sound is not None and self._music_channel is None:
                self._music_channel = self._music_sound.play(loops=-1)
                self.set_music_volume(self.music_volume)

    def shutdown(self) -> None:
        if self.enabled:
            pygame.mixer.stop()
            pygame.mixer.music.stop()

# ======================================================================
# blockblast/render/cache.py
# ======================================================================

"""Кэши поверхностей с ограниченным размером.

В оригинале кэши были обычными dict без лимита. При фиксированном окне это
терпимо, но с адаптивным окном каждый новый размер клетки порождал бы новые
текстуры → бесконечный рост памяти. LRU вытесняет старые записи."""

import os
from collections import OrderedDict
from typing import Callable, Hashable, TypeVar

import pygame


T = TypeVar("T")


class LRUCache:
    def __init__(self, max_items: int):
        self.max_items = max_items
        self._data: OrderedDict[Hashable, object] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: Hashable, factory: Callable[[], T]) -> T:
        try:
            value = self._data[key]
            self._data.move_to_end(key)
            self.hits += 1
            return value  # type: ignore[return-value]
        except KeyError:
            self.misses += 1
            value = factory()
            self._data[key] = value
            if len(self._data) > self.max_items:
                self._data.popitem(last=False)
            return value

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


texture_cache = LRUCache(TEXTURE_CACHE_ITEMS)


class Fonts:
    """Шрифты по размеру + кэш отрендеренного текста."""

    def __init__(self) -> None:
        self._fonts: dict[int, pygame.font.Font] = {}
        self._text = LRUCache(300)
        self._path = self._find_font()

    @staticmethod
    def _find_font():
        folder = os.path.join(ASSETS_DIR, "fonts")
        try:
            for name in sorted(os.listdir(folder)):
                if name.lower().endswith((".ttf", ".otf")):
                    return os.path.join(folder, name)
        except OSError:
            pass
        return None  # встроенный шрифт pygame (поддерживает кириллицу)

    def font(self, size: int) -> pygame.font.Font:
        size = max(8, int(size))
        f = self._fonts.get(size)
        if f is None:
            try:
                f = pygame.font.Font(self._path, size)
            except (OSError, pygame.error):
                f = pygame.font.Font(None, size)
            self._fonts[size] = f
        return f

    def render(self, text: str, size: int, color: tuple, bold: bool = False) -> pygame.Surface:
        size = max(8, int(size))
        key = (text, size, tuple(color), bold)

        def make() -> pygame.Surface:
            f = self.font(size)
            f.set_bold(bold)
            surf = f.render(text, True, color).convert_alpha()
            f.set_bold(False)
            return surf

        return self._text.get(key, make)

    def clear(self) -> None:
        self._text.clear()
        if len(self._fonts) > 40:
            self._fonts.clear()

# ======================================================================
# blockblast/render/tween.py
# ======================================================================

"""Функции плавности и простые твины, основанные на dt (а не на get_ticks)."""

import math


def clamp01(t: float) -> float:
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_in_cubic(t: float) -> float:
    t = clamp01(t)
    return t * t * t


def ease_out_back(t: float, s: float = 1.7) -> float:
    t = clamp01(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def approach(current: float, target: float, speed: float, dt: float) -> float:
    """Экспоненциальное сглаживание, не зависящее от FPS."""
    return target + (current - target) * math.exp(-speed * dt)


class Tween:
    __slots__ = ("start", "end", "duration", "elapsed", "ease", "delay")

    def __init__(self, start: float, end: float, duration: float, ease=ease_out_cubic, delay: float = 0.0):
        self.start, self.end = start, end
        self.duration = max(1e-6, duration)
        self.elapsed = 0.0
        self.ease = ease
        self.delay = delay

    def update(self, dt: float) -> None:
        self.elapsed += dt

    @property
    def t(self) -> float:
        return clamp01((self.elapsed - self.delay) / self.duration)

    @property
    def value(self) -> float:
        return lerp(self.start, self.end, self.ease(self.t))

    @property
    def done(self) -> bool:
        return self.elapsed >= self.delay + self.duration


class RollingNumber:
    """Счёт, который «докручивается» до реального значения."""

    def __init__(self, value: int = 0):
        self.target = value
        self.shown = float(value)

    def set(self, value: int, instant: bool = False) -> None:
        self.target = value
        if instant:
            self.shown = float(value)

    def update(self, dt: float) -> None:
        self.shown = approach(self.shown, self.target, 9.0, dt)
        if abs(self.shown - self.target) < 0.5:
            self.shown = float(self.target)

    @property
    def value(self) -> int:
        return int(round(self.shown))

    @property
    def animating(self) -> bool:
        return self.value != self.target

# ======================================================================
# blockblast/render/painters.py
# ======================================================================

"""Рисование одного блока в разных стилях.

Портированы ПОСЛЕДНИЕ (реально работавшие) версии функций из оригинала.
Отличия:
  * рисуют в поверхность размера (w, h) от точки (0, 0);
  * радиусы/толщины пропорциональны размеру (раньше были жёсткие 6px);
  * вместо random.seed() используется локальный random.Random —
    глобальный генератор фигур больше не сбивается.
Все функции вызываются только при промахе кэша текстур."""

import math
import random
from typing import Callable

import pygame

Color = tuple[int, int, int]
Painter = Callable[[pygame.Surface, int, int, Color, random.Random], None]


def shade(c: Color, delta: int) -> Color:
    return tuple(max(0, min(255, ch + delta)) for ch in c)  # type: ignore[return-value]


def _radius(w: int, h: int, k: float = 0.12) -> int:
    return max(2, int(min(w, h) * k))


def blend_rect(s: pygame.Surface, rgba: tuple, rect, radius: int = 0, width: int = 0, **kw) -> None:
    """pygame.draw с RGBA на SRCALPHA-поверхности НЕ смешивает цвета, а перезаписывает
    альфу (получаются «дырки»). Рисуем на временном слое и накладываем с блендингом."""
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, rgba, layer.get_rect(), width=width, border_radius=radius, **kw)
    s.blit(layer, rect.topleft)


def paint_glossy(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    r = _radius(w, h)
    pygame.draw.rect(s, shade(color, -40), (0, 0, w, h), border_radius=r)
    pygame.draw.rect(s, color, (0, 0, w, h - max(2, h // 12)), border_radius=r)
    hl = shade(color, 45)
    blend_rect(s, (*hl, 140), (max(2, w // 16), max(2, h // 16), int(w * 0.55), int(h * 0.38)), max(1, r - 1))


def paint_watermelon(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    flesh_light, flesh_dark = (250, 110, 104), (225, 70, 66)
    green_rind, seed_color = (48, 130, 68), (35, 25, 20)
    r = _radius(w, h)
    rind_h = max(3, int(h * 0.22))
    flesh_h = h - rind_h

    pygame.draw.rect(s, flesh_dark, (0, 0, w, flesh_h), border_radius=r)
    pygame.draw.rect(s, flesh_light, (0, 0, w, max(1, flesh_h // 2)), border_radius=r)
    pygame.draw.rect(s, green_rind, (0, flesh_h, w, rind_h), border_radius=max(2, r - 2))
    blend_rect(s, (0, 0, 0, 25), (0, flesh_h, w, max(1, int(rind_h * 0.3))))
    blend_rect(s, (0, 0, 0, 30), (0, 0, w, h), r, width=1)

    seed_w = max(2, int(min(w, h) * 0.06))
    seed_h = max(3, int(seed_w * 1.6))
    seed = pygame.Surface((seed_w + 2, seed_h + 2), pygame.SRCALPHA)
    pygame.draw.ellipse(seed, (15, 10, 8), (0, 0, seed_w + 2, seed_h + 2))
    pygame.draw.ellipse(seed, seed_color, (1, 1, seed_w, seed_h))
    for fx, fy, angle in ((0.26, 0.28, -10), (0.55, 0.20, 8), (0.72, 0.42, -6), (0.32, 0.62, 12), (0.58, 0.65, -14)):
        rotated = pygame.transform.rotate(seed, angle)
        s.blit(rotated, rotated.get_rect(center=(w * fx, flesh_h * fy)))


def paint_cake(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    cream = (250, 241, 233)
    band_light = shade(color, 28)
    r = _radius(w, h, 0.14)
    pygame.draw.rect(s, color, (0, 0, w, h), border_radius=r)

    stripes = pygame.Surface((w, h), pygame.SRCALPHA)
    step = max(4, int(w * 0.22))
    for i in range(-h, w + h, step):
        pygame.draw.line(stripes, (*band_light, 70), (i, h), (i + h, 0), 1)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)  # обрезаем полоски по скруглённой форме
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=r)
    stripes.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(stripes, (0, 0))

    cream_h = int(h * 0.5)
    pygame.draw.rect(s, cream, (0, 0, w, cream_h), border_top_left_radius=r, border_top_right_radius=r)
    if w >= 14:
        bump_r = max(3, int(w * 0.19))
        for i in range(3):
            pygame.draw.circle(s, cream, (int(w * (i + 0.5) / 3), cream_h), bump_r)

    if w < 16:
        return
    sprinkles = [(232, 190, 90), (224, 90, 90), (96, 178, 120), (110, 165, 224), (196, 120, 190)]
    cols, rows = 3, 2
    slot_w, slot_h = w / cols, cream_h / rows
    slots = [(c, r_) for c in range(cols) for r_ in range(rows)]
    rng.shuffle(slots)
    for sc, sr in slots[: rng.choice([4, 5])]:
        sx = (sc + 0.5) * slot_w + rng.uniform(-0.18, 0.18) * slot_w
        sy = (sr + 0.5) * slot_h + rng.uniform(-0.18, 0.18) * slot_h
        col = rng.choice(sprinkles)
        max_len = min(slot_w, slot_h) * 0.85
        if rng.random() < 0.7:
            length = min(w * rng.uniform(0.22, 0.3), max_len)
            a = math.radians(rng.choice([-35, -10, 15, 40, 65]))
            dx, dy = math.cos(a) * length / 2, math.sin(a) * length / 2
            width = max(2, int(min(slot_w, slot_h) * 0.22))
            p1, p2 = (sx - dx, sy - dy), (sx + dx, sy + dy)
            pygame.draw.line(s, col, p1, p2, width)
            pygame.draw.circle(s, col, (int(p1[0]), int(p1[1])), width // 2)
            pygame.draw.circle(s, col, (int(p2[0]), int(p2[1])), width // 2)
        else:
            pygame.draw.circle(s, col, (int(sx), int(sy)), max(2, min(int(w * 0.045), int(max_len * 0.4))))


def paint_brick(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    mortar = (206, 194, 176)
    dark_edge, light_edge = shade(color, -35), shade(color, 22)
    r = _radius(w, h)
    pygame.draw.rect(s, mortar, (0, 0, w, h), border_radius=r)
    s.set_clip(pygame.Rect(0, 0, w, h))
    rows = 4
    row_h = h / rows
    gap = max(2, int(min(w, h) * 0.06))
    brick_w = w / 2
    br = max(1, r - 1)
    band = max(2, int(row_h * 0.22))
    for row in range(rows):
        ry = row * row_h
        offset = w * 0.25 if row % 2 else 0
        for b in range(-1, 3):
            rect = pygame.Rect(int(b * brick_w + offset + gap / 2), int(ry + gap / 2),
                               int(brick_w - gap), int(row_h - gap))
            pygame.draw.rect(s, color, rect, border_radius=br)
            blend_rect(s, (*dark_edge, 140), (rect.x, rect.bottom - band, rect.w, band), br)
            blend_rect(s, (*light_edge, 115), (rect.x, rect.y, rect.w, band), br)
    s.set_clip(None)


def paint_grass(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    dirt, dirt_dark = (150, 104, 60), (118, 78, 44)
    grass, grass_dark = (108, 195, 66), (78, 162, 48)
    r = _radius(w, h, 0.05)
    pygame.draw.rect(s, dirt, (0, 0, w, h), border_radius=r)
    for _ in range(4):
        pygame.draw.circle(s, dirt_dark, (int(rng.uniform(0.15, 0.85) * w), int(rng.uniform(0.45, 0.85) * h)),
                           int(min(w, h) * rng.uniform(0.05, 0.09)))
    grass_h = int(h * 0.4)
    pygame.draw.rect(s, grass, (0, 0, w, grass_h), border_top_left_radius=r, border_top_right_radius=r)
    bump_r = max(3, int(w * 0.09))
    for i in range(4):
        pygame.draw.circle(s, grass, (int(w * (i + 0.5) / 4), grass_h), bump_r)
    for i in range(2):
        pygame.draw.circle(s, grass_dark, (int(w * (0.25 + i * 0.45)), int(grass_h * 0.4)), int(w * 0.09))
    hl = pygame.Surface((max(1, int(w * 0.28)), max(1, int(h * 0.14))), pygame.SRCALPHA)
    pygame.draw.ellipse(hl, (255, 255, 255, 51), hl.get_rect())
    s.blit(hl, (int(w * 0.12), int(h * 0.55)))



# --- Флаги стран -----------------------------------------------------------
# Блок рисуется как флаг: тема «Страны». Ключ — «главный» цвет флага, он же
# лежит в палитре темы, поэтому рисовальщик узнаёт страну по цвету и не надо
# менять подпись Painter ради одного стиля.

def _bands(s, w, h, colors, vertical=False, weights=None):
    """Полосы флага. weights задаёт неравные доли, как у Испании (1:2:1)."""
    weights = weights or [1] * len(colors)
    total = sum(weights)
    pos = 0
    for color, weight in zip(colors, weights):
        span = (w if vertical else h) * weight / total
        if vertical:
            pygame.draw.rect(s, color, (int(pos), 0, int(span) + 1, h))
        else:
            pygame.draw.rect(s, color, (0, int(pos), w, int(span) + 1))
        pos += span


def _star(s, cx, cy, r, color, points=5, turn=-math.pi / 2):
    pts = []
    for i in range(points * 2):
        rad = r if i % 2 == 0 else r * 0.42
        a = turn + i * math.pi / points
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    pygame.draw.polygon(s, color, pts)


def _flag_russia(s, w, h):
    _bands(s, w, h, ((255, 255, 255), (0, 57, 166), (213, 43, 30)))


def _flag_france(s, w, h):
    _bands(s, w, h, ((0, 85, 164), (255, 255, 255), (239, 65, 53)), vertical=True)


def _flag_italy(s, w, h):
    _bands(s, w, h, ((0, 140, 69), (255, 255, 255), (205, 33, 42)), vertical=True)


def _flag_spain(s, w, h):
    _bands(s, w, h, ((198, 11, 30), (241, 191, 0), (198, 11, 30)), weights=(1, 2, 1))


def _flag_brazil(s, w, h):
    s.fill((0, 155, 58))
    m = w * 0.08
    pygame.draw.polygon(s, (254, 223, 0), ((w / 2, m), (w - m, h / 2), (w / 2, h - m), (m, h / 2)))
    cx, cy, rc = w / 2, h / 2, w * 0.21
    pygame.draw.circle(s, (0, 39, 118), (int(cx), int(cy)), int(rc))
    # белая лента «Ordem e Progresso»: дуга, спускающаяся слева направо.
    # Рисуем отрезками, а не draw.arc — так лента гарантированно внутри круга.
    band = max(1, int(rc * 0.18))
    pts = []
    for i in range(13):
        t = -0.92 + 1.84 * i / 12                  # от левого края круга к правому
        y = cy + rc * (0.18 * t - 0.16 * (1 - t * t) - 0.02)
        pts.append((cx + rc * t, y))
    for a, b in zip(pts, pts[1:]):
        pygame.draw.line(s, (255, 255, 255), a, b, band)
    # звёзды — несколько точек под лентой
    # на мелком блоке пять точек сливаются в пятно — хватает трёх
    for dx, dy in ((-0.38, 0.38), (0.10, 0.50), (0.45, 0.30)):
        pygame.draw.circle(s, (255, 255, 255), (int(cx + rc * dx), int(cy + rc * dy)),
                           max(1, int(rc * 0.07)))

def _flag_china(s, w, h):
    s.fill((222, 41, 16))
    _star(s, w * 0.32, h * 0.34, w * 0.17, (255, 222, 0))
    for dx, dy in ((0.56, 0.17), (0.67, 0.28), (0.67, 0.45), (0.56, 0.56)):
        pygame.draw.circle(s, (255, 222, 0), (int(w * dx), int(h * dy)), max(1, int(w * 0.045)))


def _flag_usa(s, w, h):
    stripes = 13                                    # 7 красных и 6 белых, как на настоящем
    for i in range(stripes):
        color = (178, 34, 52) if i % 2 == 0 else (255, 255, 255)
        y0 = round(h * i / stripes)
        y1 = round(h * (i + 1) / stripes)
        pygame.draw.rect(s, color, (0, y0, w, max(1, y1 - y0)))
    cw, ch = round(w * 0.42), round(h * 7 / stripes)   # синий угол — на 7 полос
    pygame.draw.rect(s, (60, 59, 110), (0, 0, cw, ch))
    # звёзды шахматкой: ряды со смещением, как 6/5 на флаге
    r = max(1, round(w * 0.016))
    rows = 5
    for row in range(rows):
        cols = 4 if row % 2 == 0 else 3
        for col in range(cols):
            fx = (col + (0.5 if row % 2 == 0 else 1.0)) / 4.5
            fy = (row + 0.6) / (rows + 0.2)
            pygame.draw.circle(s, (255, 255, 255), (int(cw * fx), int(ch * fy)), r)

def _flag_portugal(s, w, h):
    _bands(s, w, h, ((0, 102, 71), (255, 0, 0)), vertical=True, weights=(2, 3))
    pygame.draw.circle(s, (255, 228, 0), (int(w * 0.4), int(h / 2)), int(w * 0.15))
    pygame.draw.circle(s, (255, 0, 0), (int(w * 0.4), int(h / 2)), int(w * 0.08))


def _flag_canada(s, w, h):
    _bands(s, w, h, ((216, 30, 5), (255, 255, 255), (216, 30, 5)), vertical=True, weights=(1, 2, 1))
    cx, cy, r = w / 2, h / 2, min(w, h) * 0.235   # лист ширина 0.47w — влезает в белую полосу 0.5w
    # половина профиля листа, левая сторона — зеркало: так силуэт точно симметричен
    half = ((0.00, -1.05), (0.14, -0.62), (0.40, -0.70), (0.32, -0.36), (0.66, -0.30),
            (0.56, -0.10), (1.00, 0.02), (0.90, 0.16), (0.46, 0.50), (0.56, 0.62),
            (0.14, 0.60), (0.18, 1.05), (0.00, 1.05))
    pts = [(cx + x * r, cy + y * r) for x, y in half]
    pts += [(cx - x * r, cy + y * r) for x, y in reversed(half[:-1])]
    pygame.draw.polygon(s, (216, 30, 5), pts)


def _flag_kazakhstan(s, w, h):
    s.fill((0, 175, 202))
    cx, cy, r = w / 2, h * 0.45, w * 0.15
    for i in range(12):
        a = i * math.pi / 6
        pygame.draw.line(s, (252, 209, 22), (cx, cy),
                         (cx + r * 1.7 * math.cos(a), cy + r * 1.7 * math.sin(a)),
                         max(1, int(w * 0.035)))
    pygame.draw.circle(s, (252, 209, 22), (int(cx), int(cy)), int(r))


def _flag_belarus(s, w, h):
    _bands(s, w, h, ((200, 16, 46), (0, 158, 73)), weights=(2, 1))
    band = max(3, int(w * 0.22))
    pygame.draw.rect(s, (255, 255, 255), (0, 0, band, h))
    for i in range(3):
        cy = h * (0.18 + i * 0.32)
        d = band * 0.3
        pygame.draw.polygon(s, (200, 16, 46),
                            ((band / 2, cy - d), (band / 2 + d, cy), (band / 2, cy + d), (band / 2 - d, cy)))


# порядок = порядок палитры темы «Страны»
FLAG_DRAWERS: tuple[tuple[Color, object], ...] = (
    ((0, 57, 166), _flag_russia),
    ((0, 85, 164), _flag_france),
    ((0, 140, 69), _flag_italy),
    ((198, 11, 30), _flag_spain),
    ((0, 155, 58), _flag_brazil),
    ((222, 41, 16), _flag_china),
    ((60, 59, 110), _flag_usa),
    ((0, 102, 71), _flag_portugal),
    ((216, 30, 5), _flag_canada),
    ((0, 175, 202), _flag_kazakhstan),
    ((200, 16, 46), _flag_belarus),
)
FLAG_PALETTE: tuple[Color, ...] = tuple(color for color, _ in FLAG_DRAWERS)
_FLAG_BY_COLOR = {color: draw for color, draw in FLAG_DRAWERS}


def paint_flag(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    """Блок-флаг: скруглённая подложка цветом флага плюс сам флаг внутри.

    Без масок и BLEND_RGBA_MIN: полагаться на попиксельное смешивание альфы
    ради скруглённых углов — лишний риск, а проверить его в заглушке нельзя.
    Поэтому углы даёт подложка, а флаг рисуется прямоугольником с отступом."""
    radius = _radius(w, h)
    pygame.draw.rect(s, shade(color, -45), (0, 0, w, h), border_radius=radius)
    pygame.draw.rect(s, color, (0, 0, w, h - max(1, h // 16)), border_radius=radius)

    pad = max(1, int(min(w, h) * 0.11))
    fw, fh = w - pad * 2, h - pad * 2
    if fw < 4 or fh < 4:                       # совсем мелкий блок — хватит подложки
        return
    flag = pygame.Surface((fw, fh))
    drawer = _FLAG_BY_COLOR.get(tuple(color))
    if drawer is None:
        flag.fill(color)
    else:
        drawer(flag, fw, fh)
    s.blit(flag, (pad, pad))



def paint_ice(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    """Кубик льда: светлая грань сверху, тёмная снизу, матовая сердцевина,
    косой блик и капли воды. Капли раскладывает rng — у каждого варианта свои."""
    radius = _radius(w, h, 0.16)
    deep = shade(color, -70)
    # тёмная нижняя грань — объём
    pygame.draw.rect(s, deep, (0, 0, w, h), border_radius=radius)
    pygame.draw.rect(s, shade(color, -25), (0, 0, w, h - max(2, h // 10)), border_radius=radius)
    # матовая сердцевина чуть светлее краёв: лёд мутнее в толще
    inset = max(2, int(w * 0.14))
    pygame.draw.rect(s, shade(color, 18),
                     (inset, inset, w - inset * 2, h - inset * 2 - max(1, h // 14)),
                     border_radius=max(1, radius // 2))
    # светлые кромки сверху и слева — свет падает с левого верха
    edge = max(1, w // 18)
    pygame.draw.line(s, shade(color, 70), (radius, edge), (w - radius, edge), edge)
    pygame.draw.line(s, shade(color, 55), (edge, radius), (edge, h - radius - h // 10), edge)
    # косой блик через левый верхний угол
    band = w * 0.13
    pygame.draw.polygon(s, shade(color, 80), (
        (inset, inset + band * 1.6), (inset + band * 1.6, inset),
        (inset + band * 2.4, inset), (inset, inset + band * 2.4)))
    # капли: маленький круг потемнее и белая точка-отсвет на нём
    drops = 2 + rng.randrange(3)
    for _ in range(drops):
        dx = rng.uniform(0.28, 0.80) * w
        dy = rng.uniform(0.30, 0.78) * h
        r = max(1, int(w * rng.uniform(0.045, 0.075)))
        pygame.draw.circle(s, shade(color, -30), (int(dx), int(dy)), r)
        pygame.draw.circle(s, (255, 255, 255), (int(dx - r * 0.35), int(dy - r * 0.35)),
                           max(1, r // 2))



def _luma(c: Color) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def paint_cookie(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    """Печенье с шоколадной крошкой: подрумяненный край, светлая середина,
    трещинки и неровные капли шоколада. На тёмном тесте шоколад белый —
    иначе крошку не видно."""
    radius = _radius(w, h, 0.16)                 # квадратное, углы чуть скруглены
    edge = shade(color, -42)
    pygame.draw.rect(s, shade(color, -70), (0, 0, w, h), border_radius=radius)       # тень снизу
    pygame.draw.rect(s, edge, (0, 0, w, h - max(2, h // 12)), border_radius=radius)   # румяный край
    rim = max(2, int(w * 0.09))
    pygame.draw.rect(s, color, (rim, rim, w - rim * 2, h - rim * 2 - max(1, h // 16)),
                     border_radius=max(2, radius - rim))
    # середина светлее: там тесто пропеклось меньше. Скругление — четверть
    # размера: под квадратный блок, но без жёстких углов
    core = int(w * 0.22)
    cw, ch = w - core * 2, h - core * 2 - rim // 2
    pygame.draw.rect(s, shade(color, 12), (core, core - rim // 2, cw, ch),
                     border_radius=max(2, min(cw, ch) // 4))

    # трещинки на поверхности
    crack = shade(color, -34)
    for _ in range(2 + rng.randrange(2)):
        x0, y0 = rng.uniform(0.26, 0.74) * w, rng.uniform(0.26, 0.70) * h
        a = rng.uniform(0, math.tau)
        ln = w * rng.uniform(0.10, 0.18)
        x1, y1 = x0 + math.cos(a) * ln, y0 + math.sin(a) * ln
        pygame.draw.line(s, crack, (x0, y0), (x1, y1), max(1, w // 28))

    # шоколад: каждая капля — два слипшихся круга, выглядит неровно
    white_choc = _luma(color) < 110
    chip = (240, 228, 204) if white_choc else (62, 36, 24)
    shine = (255, 250, 240) if white_choc else (110, 72, 50)
    # раскладываем по сетке 3×3 с разбросом: иначе капли слипаются в кляксу
    spots = rng.sample([(gx, gy) for gx in range(3) for gy in range(3)], 4 + rng.randrange(3))
    for gx, gy in spots:
        cx = (0.27 + gx * 0.23 + rng.uniform(-0.06, 0.06)) * w
        cy = (0.27 + gy * 0.22 + rng.uniform(-0.06, 0.06)) * h
        r = max(1, int(w * rng.uniform(0.055, 0.085)))
        pygame.draw.circle(s, chip, (int(cx), int(cy)), r)
        a = rng.uniform(0, math.tau)
        pygame.draw.circle(s, chip, (int(cx + math.cos(a) * r * 0.7), int(cy + math.sin(a) * r * 0.7)),
                           max(1, int(r * 0.75)))
        pygame.draw.circle(s, shine, (int(cx - r * 0.35), int(cy - r * 0.35)), max(1, r // 3))



def paint_knit(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    """Вязаный квадрат: лицевая гладь — ряды петель-«ёлочек» (V), между
    ними тёмные провалы, по краю резинка. Сверху немного ворса."""
    radius = _radius(w, h, 0.18)
    deep = shade(color, -40)
    pygame.draw.rect(s, shade(color, -70), (0, 0, w, h), border_radius=radius)       # тень снизу
    pygame.draw.rect(s, deep, (0, 0, w, h - max(2, h // 14)), border_radius=radius)

    # петли держим внутри, чтобы не вылезали за скруглённые углы
    m = max(2, int(w * 0.10))
    x0, y0 = m, m
    iw, ih = w - m * 2, h - m * 2 - max(1, h // 16)
    # на мелком блоке петли 4×5 сливаются в рябь — делаем их крупнее
    cols, rows = (4, 5) if w >= 64 else (3, 4)
    cw, rh = iw / cols, ih / rows
    lit = shade(color, 34)
    for j in range(rows):
        top = y0 + j * rh
        for i in range(cols):
            cx = x0 + (i + 0.5) * cw
            for side in (-1, 1):
                # одна «ножка» петли — пухлый овал, наклонённый к центру.
                # Ряды чуть заходят друг на друга, как в настоящей глади
                leg = ((cx + side * 0.10 * cw, top - 0.08 * rh),
                       (cx + side * 0.52 * cw, top + 0.00 * rh),
                       (cx + side * 0.46 * cw, top + 0.50 * rh),
                       (cx + side * 0.20 * cw, top + 1.06 * rh),
                       (cx - side * 0.04 * cw, top + 0.92 * rh))
                pygame.draw.polygon(s, color, leg)
                # блик вдоль ножки — свет сверху
                pygame.draw.line(s, lit, (cx + side * 0.30 * cw, top + 0.06 * rh),
                                 (cx + side * 0.12 * cw, top + 0.66 * rh), max(1, w // 32))

    # ворс: несколько светлых пушинок
    fuzz = shade(color, 52)
    for _ in range(3 + rng.randrange(3)):
        fx, fy = rng.uniform(0.15, 0.85) * w, rng.uniform(0.15, 0.80) * h
        pygame.draw.line(s, fuzz, (fx, fy), (fx + rng.uniform(-2, 2), fy + rng.uniform(-2, 2)), 1)



STONE = (120, 120, 126)


def _chunk(cx, cy, rr, rng, n=5):
    """Неровный камешек руды: многоугольник со случайными гранями."""
    base = rng.uniform(0, math.tau)
    pts = []
    for i in range(n):
        a = base + i * math.tau / n + rng.uniform(-0.35, 0.35)
        rad = rr * rng.uniform(0.65, 1.0)
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    return pts


def paint_ore(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    """Каменный блок с вкраплениями руды. Камень у всех один, различает
    блоки цвет руды. Руда лежит гнёздами по 3–5 камешков с бликом и тенью."""
    radius = _radius(w, h, 0.08)                 # почти прямые углы — это же камень
    pygame.draw.rect(s, shade(STONE, -58), (0, 0, w, h), border_radius=radius)
    pygame.draw.rect(s, STONE, (0, 0, w, h - max(2, h // 12)), border_radius=radius)
    # фаска: свет сверху слева
    e = max(1, w // 16)
    pygame.draw.line(s, shade(STONE, 40), (radius, e // 2), (w - radius, e // 2), e)
    pygame.draw.line(s, shade(STONE, 28), (e // 2, radius), (e // 2, h - radius - h // 12), e)

    # фактура камня: пятна светлее и темнее, пара трещин
    for _ in range(7 + rng.randrange(5)):
        tone = rng.choice((-22, -14, 14, 20))
        px, py = rng.uniform(0.08, 0.86) * w, rng.uniform(0.08, 0.80) * h
        sz = max(2, int(w * rng.uniform(0.06, 0.12)))
        pygame.draw.rect(s, shade(STONE, tone), (int(px), int(py), sz, max(1, sz * 2 // 3)))
    crack = shade(STONE, -40)
    for _ in range(1 + rng.randrange(2)):
        x, y = rng.uniform(0.15, 0.85) * w, rng.uniform(0.15, 0.75) * h
        for _ in range(3):
            nx = x + rng.uniform(-0.14, 0.14) * w
            ny = y + rng.uniform(0.04, 0.12) * h
            pygame.draw.line(s, crack, (x, y), (nx, ny), 1)
            x, y = nx, ny

    # руда рассыпана по всему блоку: сетка 3×3, в части клеток по 1–2 камешка
    # со сдвигом — так камешки не сбиваются в одну кучу, но и не стоят строем
    dark, lit = shade(color, -60), shade(color, 70)
    spots = rng.sample([(gx, gy) for gx in range(3) for gy in range(3)], 6 + rng.randrange(3))
    for gx, gy in spots:
        for _ in range(1 + (rng.random() < 0.35)):
            px = (0.22 + gx * 0.28 + rng.uniform(-0.08, 0.08)) * w
            py = (0.22 + gy * 0.27 + rng.uniform(-0.08, 0.08)) * h
            rr = w * rng.uniform(0.050, 0.080)
            pts = _chunk(px, py, rr, rng)
            pygame.draw.polygon(s, dark, [(x + 1, y + 1) for x, y in pts])   # тень
            pygame.draw.polygon(s, color, pts)
            pygame.draw.polygon(s, lit, _chunk(px - rr * 0.3, py - rr * 0.3, rr * 0.42, rng, 4))



def paint_gift(s: pygame.Surface, w: int, h: int, color: Color, rng: random.Random) -> None:
    """Подарок, вид сверху: упаковка в горошек, лента крестом и бант в центре.
    Лента золотая, а на светлой бумаге — красная, иначе золото теряется."""
    radius = _radius(w, h, 0.12)
    pygame.draw.rect(s, shade(color, -60), (0, 0, w, h), border_radius=radius)
    pygame.draw.rect(s, color, (0, 0, w, h - max(2, h // 12)), border_radius=radius)
    # горошек на бумаге
    dot = shade(color, 34) if _luma(color) < 200 else shade(color, -26)
    step = max(4, w // 5)
    for gy in range(step // 2, h - h // 12, step):
        for gx in range(step // 2 + (gy // step % 2) * step // 2, w, step):
            pygame.draw.circle(s, dot, (gx, gy), max(1, w // 26))

    ribbon = (222, 48, 62) if _luma(color) > 170 else (250, 206, 72)
    rib_dark, rib_lit = shade(ribbon, -55), shade(ribbon, 45)
    cx, cy = w / 2, (h - h // 12) / 2
    band = max(3, int(w * 0.17))
    # лента крестом, с тёмными краями и бликом по центру
    pygame.draw.rect(s, rib_dark, (int(cx - band / 2), 0, band, h - h // 12))
    pygame.draw.rect(s, rib_dark, (0, int(cy - band / 2), w, band))
    inner = max(1, band - 2)
    pygame.draw.rect(s, ribbon, (int(cx - inner / 2), 0, inner, h - h // 12))
    pygame.draw.rect(s, ribbon, (0, int(cy - inner / 2), w, inner))
    pygame.draw.line(s, rib_lit, (cx - band * 0.18, 0), (cx - band * 0.18, h - h // 12), 1)
    pygame.draw.line(s, rib_lit, (0, cy - band * 0.18), (w, cy - band * 0.18), 1)

    # хвостики банта — вниз влево и вниз вправо, концы с вырезом
    for side in (-1, 1):
        tail = ((cx + side * w * 0.02, cy), (cx + side * w * 0.12, cy - h * 0.02),
                (cx + side * w * 0.30, cy + h * 0.30), (cx + side * w * 0.22, cy + h * 0.26),
                (cx + side * w * 0.20, cy + h * 0.34))
        pygame.draw.polygon(s, rib_dark, [(x + 1, y + 1) for x, y in tail])
        pygame.draw.polygon(s, ribbon, tail)
    # петли банта: овал ленты, внутри тёмная «дырка» петли
    lw, lh = w * 0.30, h * 0.22
    for side in (-1, 1):
        x = cx - lw - w * 0.02 if side < 0 else cx + w * 0.02
        loop = pygame.Rect(int(x), int(cy - lh * 0.72), int(lw), int(lh))
        pygame.draw.ellipse(s, rib_dark, loop.move(1, 1))
        pygame.draw.ellipse(s, ribbon, loop)
        hole = loop.inflate(-int(lw * 0.46), -int(lh * 0.50))
        hole.x += int(side * lw * 0.08)
        pygame.draw.ellipse(s, rib_dark, hole)
        pygame.draw.line(s, rib_lit, (loop.x + lw * 0.25, loop.y + 2),
                         (loop.x + lw * 0.70, loop.y + 2), 1)
    # узел
    knot = max(2, int(w * 0.075))
    pygame.draw.circle(s, rib_dark, (int(cx) + 1, int(cy - lh * 0.22) + 1), knot)
    pygame.draw.circle(s, ribbon, (int(cx), int(cy - lh * 0.22)), knot)
    pygame.draw.circle(s, rib_lit, (int(cx - knot * 0.35), int(cy - lh * 0.22 - knot * 0.35)),
                       max(1, knot // 3))



# === Новая партия тем =======================================================

def _base_tile(s, w, h, color, rf=0.14, drop=-60):
    """Общая подложка: скруглённый блок с тёмной кромкой снизу для объёма."""
    radius = _radius(w, h, rf)
    pygame.draw.rect(s, shade(color, drop), (0, 0, w, h), border_radius=radius)
    pygame.draw.rect(s, color, (0, 0, w, h - max(2, h // 12)), border_radius=radius)
    return radius


def paint_gummy(s, w, h, color, rng):
    """Мармеладный мишка на плитке в сахарной обсыпке.

    Мишка собран из кругов и овалов: голова с ушками, тело, лапки, светлое
    брюшко и мордочка. Сначала весь силуэт тенью со сдвигом — объём."""
    # плитка заметно темнее мишки: на мелком блоке иначе силуэт сливается
    _base_tile(s, w, h, shade(color, -78), 0.20, -30)
    for _ in range(8 + rng.randrange(5)):                       # сахар на плитке
        pygame.draw.circle(s, shade(color, -30), (int(rng.uniform(0.06, 0.94) * w),
                                                 int(rng.uniform(0.06, 0.88) * h)), max(1, w // 44))

    def ell(fx, fy, fw, fh, col, dx=0, dy=0):
        pygame.draw.ellipse(s, col, (int((fx - fw / 2) * w) + dx, int((fy - fh / 2) * h) + dy,
                                     max(2, int(fw * w)), max(2, int(fh * h))))

    parts = ((0.36, 0.84, 0.19, 0.15), (0.64, 0.84, 0.19, 0.15),      # лапки снизу
             (0.26, 0.54, 0.15, 0.21), (0.74, 0.54, 0.15, 0.21),      # лапки по бокам
             (0.50, 0.63, 0.46, 0.44),                                # тело
             (0.35, 0.15, 0.13, 0.13), (0.65, 0.15, 0.13, 0.13),      # уши
             (0.50, 0.30, 0.36, 0.32))                                # голова
    for p in parts:                                                   # тень всего мишки
        ell(*p, shade(color, -110), dx=1, dy=max(1, h // 30))
    for p in parts:
        ell(*p, color)
    ell(0.50, 0.65, 0.25, 0.25, shade(color, 24))                     # брюшко
    ell(0.50, 0.36, 0.16, 0.10, shade(color, 30))                     # мордочка
    eye = shade(color, -85)
    for fx in (0.42, 0.58):
        pygame.draw.circle(s, eye, (int(fx * w), int(0.27 * h)), max(1, w // 40))
    pygame.draw.circle(s, eye, (int(0.5 * w), int(0.34 * h)), max(1, w // 44))  # нос
    ell(0.40, 0.21, 0.12, 0.06, shade(color, 90))                     # блик на голове
    ell(0.38, 0.52, 0.07, 0.12, shade(color, 70))                     # блик на теле


# --- пицца: сыр у всех один, различает начинка ---
def _top_pepperoni(s, w, h, rng):
    for fx, fy in ((0.33, 0.34), (0.68, 0.40), (0.42, 0.70)):
        c = (int(fx * w), int(fy * h)); r = int(w * 0.13)
        pygame.draw.circle(s, (150, 30, 30), c, r)
        pygame.draw.circle(s, (196, 46, 40), c, max(1, r - max(1, w // 30)))
        for _ in range(3):
            pygame.draw.circle(s, (150, 30, 30), (c[0] + rng.randint(-r // 2, r // 2),
                                                  c[1] + rng.randint(-r // 2, r // 2)), max(1, w // 40))


def _top_olives(s, w, h, rng):
    for fx, fy in ((0.30, 0.32), (0.66, 0.30), (0.48, 0.55), (0.30, 0.72), (0.70, 0.70)):
        c = (int(fx * w), int(fy * h)); r = max(2, int(w * 0.08))
        pygame.draw.circle(s, (30, 30, 30), c, r)
        pygame.draw.circle(s, (250, 214, 110), c, max(1, r // 2))


def _top_mushrooms(s, w, h, rng):
    for fx, fy in ((0.34, 0.36), (0.66, 0.46), (0.40, 0.70)):
        x, y = fx * w, fy * h; r = w * 0.13
        pygame.draw.ellipse(s, (170, 140, 110), (int(x - r), int(y - r * 0.8), int(r * 2), int(r * 1.3)))
        pygame.draw.rect(s, (220, 200, 176), (int(x - r * 0.3), int(y - r * 0.2), max(2, int(r * 0.6)), int(r * 0.9)))


def _top_peppers(s, w, h, rng):
    for fx, fy in ((0.34, 0.34), (0.66, 0.42), (0.44, 0.70)):
        pygame.draw.circle(s, (46, 140, 56), (int(fx * w), int(fy * h)), int(w * 0.12), max(2, w // 18))


def _top_pineapple(s, w, h, rng):
    for fx, fy in ((0.32, 0.34), (0.64, 0.32), (0.50, 0.58), (0.30, 0.72), (0.70, 0.70)):
        x, y = fx * w, fy * h; r = w * 0.08
        pts = ((x, y - r), (x + r, y + r * 0.7), (x - r, y + r * 0.7))
        pygame.draw.polygon(s, (176, 134, 30), [(px + 1, py + 1) for px, py in pts])
        pygame.draw.polygon(s, (252, 226, 90), pts)


def _top_ham(s, w, h, rng):
    for fx, fy in ((0.28, 0.28), (0.60, 0.34), (0.36, 0.62), (0.66, 0.66)):
        x, y = fx * w, fy * h; a = w * 0.15
        pygame.draw.rect(s, (214, 110, 120), (int(x), int(y), int(a), int(a * 0.8)))
        pygame.draw.rect(s, (246, 160, 164), (int(x + 1), int(y + 1), max(1, int(a) - 3), max(1, int(a * 0.8) - 3)))


def _top_onion(s, w, h, rng):
    for fx, fy in ((0.36, 0.38), (0.64, 0.56)):
        c = (int(fx * w), int(fy * h))
        for rr in (0.16, 0.10):
            pygame.draw.circle(s, (150, 60, 150), c, int(w * rr), max(1, w // 24))


PIZZA_TOPPINGS = (
    ((196, 46, 40), _top_pepperoni), ((40, 40, 40), _top_olives), ((200, 170, 140), _top_mushrooms),
    ((56, 150, 66), _top_peppers), ((250, 222, 80), _top_pineapple), ((240, 150, 156), _top_ham),
    ((150, 60, 150), _top_onion),
)
PIZZA_PALETTE = tuple(c for c, _ in PIZZA_TOPPINGS)
_PIZZA_BY_COLOR = dict(PIZZA_TOPPINGS)


def paint_pizza(s, w, h, color, rng):
    """Кусок пиццы вид сверху: корочка, соус по краю, сыр с пятнами и начинка."""
    crust = (214, 150, 82)
    _base_tile(s, w, h, crust, 0.14, -55)
    m = max(2, int(w * 0.09))
    pygame.draw.rect(s, (196, 58, 40), (m, m, w - 2 * m, h - 2 * m - h // 14), border_radius=max(2, int(w * 0.08)))
    m2 = m + max(1, w // 24)
    pygame.draw.rect(s, (250, 214, 110), (m2, m2, w - 2 * m2, h - 2 * m2 - h // 14), border_radius=max(2, int(w * 0.07)))
    for _ in range(4):
        x, y = rng.uniform(0.25, 0.75) * w, rng.uniform(0.25, 0.7) * h
        pygame.draw.circle(s, (238, 190, 80), (int(x), int(y)), max(1, int(w * 0.05)))
    top = _PIZZA_BY_COLOR.get(tuple(color))
    if top:
        top(s, w, h, rng)


def paint_sushi(s, w, h, color, rng):
    """Ролл вид сверху: нори по краю, рис, начинка в центре."""
    nori = (28, 40, 34)
    radius = _base_tile(s, w, h, nori, 0.24, -20)
    pygame.draw.line(s, (60, 80, 66), (radius, 2), (w - radius, 2), 1)
    m = int(w * 0.12)
    pygame.draw.rect(s, (246, 244, 236), (m, m, w - 2 * m, h - 2 * m - h // 16), border_radius=max(2, int(w * 0.18)))
    for _ in range(10):
        x, y = rng.uniform(0.16, 0.84) * w, rng.uniform(0.16, 0.80) * h
        pygame.draw.ellipse(s, (224, 222, 212), (int(x), int(y), max(2, w // 14), max(1, w // 28)))
    c = int(w * 0.33)
    fill = (c, c, w - 2 * c, h - 2 * c - h // 16)
    pygame.draw.rect(s, shade(color, -40), fill, border_radius=max(2, int(w * 0.10)))
    pygame.draw.rect(s, color, (fill[0] + 1, fill[1] + 1, fill[2] - 2, fill[3] - 2), border_radius=max(2, int(w * 0.09)))
    # прожилки/зёрна начинки
    for i in range(3):
        y = fill[1] + fill[3] * (i + 1) / 4
        pygame.draw.line(s, shade(color, 45), (fill[0] + 2, y), (fill[0] + fill[2] - 3, y - fill[3] * 0.12), 1)


def paint_shell(s, w, h, color, rng):
    """Ракушка-гребешок: веер рёбер из «замка» внизу."""
    _base_tile(s, w, h, shade(color, -34), 0.18, -40)
    cx, hy = w / 2, h * 0.86
    top = h * 0.12
    pts = [(cx, hy)]
    for i in range(13):
        a = math.pi * (1.05 + 0.9 * i / 12)
        pts.append((cx + math.cos(a) * w * 0.44, hy + math.sin(a) * (hy - top)))
    pygame.draw.polygon(s, color, pts)
    for i in range(1, 12, 2):
        a = math.pi * (1.05 + 0.9 * i / 12)
        pygame.draw.line(s, shade(color, -38), (cx, hy), (cx + math.cos(a) * w * 0.42, hy + math.sin(a) * (hy - top) * 0.96),
                         max(1, w // 30))
    pygame.draw.polygon(s, shade(color, 30), ((cx - w * 0.16, hy - h * 0.02), (cx + w * 0.16, hy - h * 0.02),
                                              (cx + w * 0.10, hy + h * 0.06), (cx - w * 0.10, hy + h * 0.06)))
    pygame.draw.ellipse(s, shade(color, 60), (int(cx - w * 0.2), int(top + h * 0.1), int(w * 0.18), int(h * 0.1)))


LEAF_HALF = ((0.00, -1.05), (0.14, -0.62), (0.40, -0.70), (0.32, -0.36), (0.66, -0.30),
             (0.56, -0.10), (1.00, 0.02), (0.90, 0.16), (0.46, 0.50), (0.56, 0.62),
             (0.14, 0.60), (0.18, 1.05), (0.00, 1.05))


def paint_leaf(s, w, h, color, rng):
    """Осенний лист на тёмной плитке, с прожилками и черешком.
    Плитка у всех одна — тёмная земля: на плитке «своего» оттенка
    красный лист тонул в тёмно-красном."""
    _base_tile(s, w, h, (96, 64, 40), 0.16, -34)      # светлее поля — видна форма фигуры
    cx, cy, r = w / 2, h * 0.47, w * 0.40
    tilt = rng.uniform(-0.25, 0.25)
    def rot(x, y):
        return (cx + (x * math.cos(tilt) - y * math.sin(tilt)) * r,
                cy + (x * math.sin(tilt) + y * math.cos(tilt)) * r)
    pts = [rot(x, y) for x, y in LEAF_HALF] + [rot(-x, y) for x, y in reversed(LEAF_HALF[:-1])]
    pygame.draw.polygon(s, color, pts)
    vein = shade(color, -45)
    for x, y in ((0.0, -0.85), (0.72, -0.12), (-0.72, -0.12), (0.4, 0.45), (-0.4, 0.45)):
        pygame.draw.line(s, vein, rot(0, 0.35), rot(x, y), max(1, w // 32))
    pygame.draw.line(s, (90, 60, 30), rot(0, 0.35), rot(0.06, 1.15), max(1, w // 22))


def paint_planet(s, w, h, color, rng):
    """Планета на кусочке космоса: объём, полосы/кратеры/кольцо — по варианту."""
    _base_tile(s, w, h, (36, 36, 74), 0.14, -16)      # светлее поля — видна форма фигуры
    for _ in range(4):
        pygame.draw.circle(s, (220, 220, 250), (rng.randint(3, w - 4), rng.randint(3, h - 6)), 1)
    # планета почти во всю плитку: на игровом размере мелкая терялась
    cx, cy, r = w // 2, int(h * 0.46), int(w * 0.41)
    pygame.draw.circle(s, shade(color, -60), (cx, cy), r)
    pygame.draw.circle(s, color, (cx - r // 8, cy - r // 8), int(r * 0.88))
    kind = rng.randrange(3)
    if kind == 0:          # полосы
        for k in (-0.35, 0.05, 0.40):
            y = cy + r * k; half = int(r * math.sqrt(max(0.0, 1 - k * k)) * 0.8)
            pygame.draw.line(s, shade(color, -30), (cx - half, y), (cx + half - r // 6, y), max(1, w // 26))
    elif kind == 1:        # кратеры
        for dx, dy, rr in ((-0.3, -0.2, 0.18), (0.25, 0.1, 0.14), (-0.05, 0.38, 0.10)):
            pygame.draw.circle(s, shade(color, -35), (int(cx + dx * r), int(cy + dy * r)), max(1, int(r * rr)))
    else:                  # кольцо
        # кольцо не шире плитки, иначе обрежется по краям
        ring = pygame.Rect(0, 0, min(int(r * 2.5), w - 2), max(3, int(r * 0.55)))
        ring.center = (cx, cy + r // 8)
        pygame.draw.ellipse(s, shade(color, 60), ring, max(1, w // 26))
    pygame.draw.circle(s, shade(color, 70), (cx - r // 3, cy - r // 3), max(1, r // 5))


def paint_wood(s, w, h, color, rng):
    """Торец бревна: кора по краю, годовые кольца, трещина от сердцевины."""
    bark = shade(color, -80)
    radius = _base_tile(s, w, h, bark, 0.32, -30)          # спил круглый — углы сильно скруглены
    m = max(2, int(w * 0.09))
    pygame.draw.rect(s, color, (m, m, w - 2 * m, h - 2 * m - h // 14), border_radius=max(2, radius - m))
    cx = w / 2 + rng.uniform(-0.08, 0.08) * w
    cy = h * 0.46 + rng.uniform(-0.08, 0.08) * h
    ring = shade(color, -26)
    rr = w * 0.07
    # кольца не дальше 0.44w: при сильном скруглении дальние вылезли бы
    # за угол плитки, а кора закрывает только свою полосу внутри
    while rr < w * 0.44:
        pygame.draw.circle(s, ring, (int(cx), int(cy)), int(rr), 1)
        rr += w * rng.uniform(0.06, 0.09)
    # всё, что вылезло за торец, закрываем корой заново
    pygame.draw.rect(s, bark, (0, 0, w, h - h // 12), max(1, m), border_radius=radius)
    pygame.draw.circle(s, shade(color, -40), (int(cx), int(cy)), max(1, w // 26))
    a = rng.uniform(0, math.tau)
    pygame.draw.line(s, shade(color, -60), (cx, cy), (cx + math.cos(a) * w * 0.3, cy + math.sin(a) * h * 0.3), 1)


def paint_marble(s, w, h, color, rng):
    """Мраморная плитка: прожилки случайным блужданием и блик по диагонали."""
    _base_tile(s, w, h, color, 0.10, -50)
    vein = shade(color, 80) if _luma(color) < 90 else shade(color, -70)
    for _ in range(2 + rng.randrange(2)):
        x, y = rng.uniform(0, w), 0.0
        a = rng.uniform(0.6, 2.5)
        while 0 <= y < h - h // 12 and -w * 0.2 < x < w * 1.2:
            nx = x + math.cos(a) * w * 0.12
            ny = y + math.sin(a) * h * 0.12
            pygame.draw.line(s, vein, (x, y), (nx, ny), 1 + (rng.random() < 0.3))
            a += rng.uniform(-0.6, 0.6)
            x, y = nx, ny
    pygame.draw.polygon(s, shade(color, 30), ((w * 0.15, h * 0.05), (w * 0.28, h * 0.05),
                                              (w * 0.05, h * 0.40), (w * 0.05, h * 0.26)))


def paint_neon(s, w, h, color, rng):
    """Неон: чёрная плитка и светящийся контур. Свечение — несколько линий
    от тусклой широкой к яркой узкой, без прозрачности."""
    radius = _base_tile(s, w, h, (14, 12, 22), 0.16, -10)
    inset = max(3, int(w * 0.14))
    box = pygame.Rect(inset, inset, w - 2 * inset, h - 2 * inset - h // 14)
    for grow, tone, width in ((3, -140, 5), (2, -90, 4), (1, -40, 3), (0, 0, 2)):
        pygame.draw.rect(s, shade(color, tone), box.inflate(grow * 2, grow * 2), width,
                         border_radius=max(2, radius - inset // 2))
    pygame.draw.rect(s, shade(color, 110), box, 1, border_radius=max(2, radius - inset // 2))
    pygame.draw.circle(s, shade(color, -120), box.center, max(2, box.w // 4))
    pygame.draw.circle(s, color, box.center, max(1, box.w // 7))


def paint_toy(s, w, h, color, rng):
    """Кубик конструктора: 2×2 пупырышка с тенью и бликом, без надписей."""
    _base_tile(s, w, h, color, 0.08, -60)
    r = max(2, int(w * 0.14))
    for fx in (0.30, 0.70):
        for fy in (0.30, 0.68):
            c = (int(fx * w), int(fy * h))
            pygame.draw.circle(s, shade(color, -45), (c[0] + 1, c[1] + 2), r)
            pygame.draw.circle(s, color, c, r)
            pygame.draw.circle(s, shade(color, 25), c, max(1, r - max(1, w // 26)))
            pygame.draw.circle(s, shade(color, 80), (c[0] - r // 3, c[1] - r // 3), max(1, r // 3))


def paint_pumpkin(s, w, h, color, rng):
    """Тыква с вырезанной рожицей, внутри горит свеча."""
    _base_tile(s, w, h, (62, 38, 80), 0.16, -20)      # светлее поля — видна форма фигуры
    body = pygame.Rect(int(w * 0.10), int(h * 0.20), int(w * 0.80), int(h * 0.66))
    pygame.draw.ellipse(s, shade(color, -45), body)
    for dx, sc in ((-0.18, 0.62), (0.18, 0.62), (0.0, 0.66)):
        rib = pygame.Rect(0, 0, int(body.w * sc), body.h - 2)
        rib.center = (int(body.centerx + dx * w), body.centery)
        pygame.draw.ellipse(s, color if dx == 0 else shade(color, -18), rib)
    pygame.draw.rect(s, (80, 110, 50), (int(w * 0.46), int(h * 0.10), max(3, int(w * 0.09)), int(h * 0.14)))
    # на светлой тыкве свет свечи не виден — вырезаем тёмным
    glow = (255, 206, 70) if _luma(color) < 170 else (70, 34, 24)
    ey = h * 0.44
    for side in (-1, 1):
        ex = w / 2 + side * w * 0.16
        if rng.random() < 0.5:
            pts = ((ex, ey - h * 0.07), (ex + w * 0.07, ey + h * 0.05), (ex - w * 0.07, ey + h * 0.05))
            pygame.draw.polygon(s, glow, pts)
        else:
            pygame.draw.circle(s, glow, (int(ex), int(ey)), max(2, int(w * 0.06)))
    my = h * 0.63
    mouth = [(w * 0.28, my)]
    for i in range(6):
        mouth.append((w * (0.28 + 0.44 * (i + 0.5) / 6), my + (h * 0.07 if i % 2 == 0 else h * 0.01)))
    mouth += [(w * 0.72, my), (w * 0.62, my + h * 0.12), (w * 0.38, my + h * 0.12)]
    pygame.draw.polygon(s, glow, mouth)


def paint_egg(s, w, h, color, rng):
    """Расписное яйцо на светлой плитке: зигзаг, горошек или полоски —
    узор не выходит за край яйца (считаем ширину яйца на каждой высоте)."""
    _base_tile(s, w, h, shade(color, 70), 0.18, -40)
    cx, cy, rx, ry = w / 2, h * 0.47, w * 0.31, h * 0.39
    pygame.draw.ellipse(s, shade(color, -45), (int(cx - rx) + 1, int(cy - ry) + 2, int(rx * 2), int(ry * 2)))
    pygame.draw.ellipse(s, color, (int(cx - rx), int(cy - ry), int(rx * 2), int(ry * 2)))
    def half(y):
        k = (y - cy) / ry
        return rx * math.sqrt(max(0.0, 1 - k * k)) * 0.86
    ink = shade(color, -70) if _luma(color) > 150 else shade(color, 90)
    kind = rng.randrange(3)
    if kind == 0:
        y0 = cy - ry * 0.10; hw = half(y0)
        pts = [(cx - hw + i * hw * 2 / 8, y0 + (h * 0.04 if i % 2 else -h * 0.04)) for i in range(9)]
        for a, b in zip(pts, pts[1:]):
            pygame.draw.line(s, ink, a, b, max(1, w // 22))
    elif kind == 1:
        for fy in (-0.45, 0.0, 0.45):
            y = cy + ry * fy; hw = half(y)
            for k in range(-2, 3):
                x = cx + k * hw / 2.4
                pygame.draw.circle(s, ink, (int(x), int(y)), max(1, w // 26))
    else:
        for fy in (-0.35, 0.25):
            y = cy + ry * fy; hw = half(y)
            pygame.draw.line(s, ink, (cx - hw, y), (cx + hw, y), max(2, w // 16))
    pygame.draw.ellipse(s, shade(color, 70), (int(cx - rx * 0.55), int(cy - ry * 0.65), int(rx * 0.4), int(ry * 0.3)))



def _mix_white(color, k):
    return tuple(int(c + (255 - c) * k) for c in color)


def paint_balloon(s, w, h, color, rng):
    """Воздушный шарик на светлой плитке: овал с бликом, узелок и
    ниточка-завиток. Плитка — бледный тон шарика, чтобы шарик выделялся."""
    _base_tile(s, w, h, _mix_white(color, 0.62), 0.20, -45)
    bx, by, bw, bh = w * 0.11, h * 0.04, w * 0.78, h * 0.72     # шарик почти во всю плитку
    knot_y = by + bh
    # ниточка: плавный завиток от узелка вниз
    pts, sway = [], rng.choice((-1, 1))
    for i in range(9):
        t = i / 8
        pts.append((w / 2 + sway * math.sin(t * math.pi * 1.6) * w * 0.06, knot_y + h * 0.03 + t * h * 0.13))
    for a, b in zip(pts, pts[1:]):
        pygame.draw.line(s, shade(color, -80), a, b, max(1, w // 40))
    # шарик: тень, тело, узелок
    pygame.draw.ellipse(s, shade(color, -60), (int(bx) + 1, int(by) + 2, int(bw), int(bh)))
    pygame.draw.ellipse(s, color, (int(bx), int(by), int(bw), int(bh)))
    pygame.draw.polygon(s, shade(color, -30), ((w / 2, knot_y - h * 0.02), (w / 2 + w * 0.06, knot_y + h * 0.05),
                                               (w / 2 - w * 0.06, knot_y + h * 0.05)))
    # объём: тёмный край справа снизу и блики слева сверху
    pygame.draw.ellipse(s, shade(color, -28), (int(bx + bw * 0.42), int(by + bh * 0.40),
                                               int(bw * 0.52), int(bh * 0.54)))
    pygame.draw.ellipse(s, color, (int(bx + bw * 0.10), int(by + bh * 0.06), int(bw * 0.72), int(bh * 0.78)))
    pygame.draw.ellipse(s, _mix_white(color, 0.75), (int(bx + bw * 0.20), int(by + bh * 0.14),
                                                    int(bw * 0.22), int(bh * 0.30)))
    pygame.draw.circle(s, (255, 255, 255), (int(bx + bw * 0.46), int(by + bh * 0.16)), max(1, w // 30))



_LETTER_FONTS: dict[int, "pygame.font.Font"] = {}


def _letter_font(size: int):
    font = _LETTER_FONTS.get(size)
    if font is None:
        font = _LETTER_FONTS[size] = pygame.font.Font(None, size)
    return font


# Алфавит: буква — часть цвета. Семь оттенков по кругу, у каждого из 26
# цветов крошечная поправка синего канала — на глаз не видно, зато цвет
# уникален и по нему однозначно находится буква. Цвет едет вместе с кубиком
# (лоток, рука, поле, сохранение, раскол), значит и буква не меняется.
_ALPHA_HUES = ((214, 64, 58), (54, 110, 204), (238, 192, 50), (70, 162, 82),
               (238, 132, 50), (142, 90, 192), (38, 170, 170))
ALPHABET_PALETTE: tuple[Color, ...] = tuple(
    (_ALPHA_HUES[i % 7][0], _ALPHA_HUES[i % 7][1], _ALPHA_HUES[i % 7][2] + i // 7) for i in range(26))
LETTER_BY_COLOR = {c: chr(65 + i) for i, c in enumerate(ALPHABET_PALETTE)}


def paint_letter(s, w, h, color, rng):
    """Кубик с буквой английского алфавита, как детские деревянные кубики:
    выпуклая рамка по краю и крупная буква с тенью. Буква — своя у каждого
    кубика (номер варианта); если её нет, берётся из цвета."""
    _base_tile(s, w, h, color, 0.14, -60)
    m = max(2, int(w * 0.09))
    frame = (m, m, w - 2 * m, h - 2 * m - h // 14)
    pygame.draw.rect(s, shade(color, 45), frame, max(1, w // 22), border_radius=max(2, int(w * 0.08)))
    pygame.draw.rect(s, shade(color, -30), (frame[0] + max(1, w // 22), frame[1] + max(1, w // 22),
                                            frame[2] - 2 * max(1, w // 22), frame[3] - 2 * max(1, w // 22)),
                     1, border_radius=max(2, int(w * 0.06)))
    variant = getattr(rng, "variant", -1)
    ch = chr(65 + variant % 26) if variant >= 0 else LETTER_BY_COLOR.get(tuple(color), "A")
    ink = (255, 255, 255) if _luma(color) < 170 else (70, 44, 24)
    font = _letter_font(max(8, int(h * 0.66)))
    shadow = font.render(ch, True, shade(color, -80))
    glyph = font.render(ch, True, ink)
    cx, cy = w // 2, (h - h // 14) // 2
    s.blit(shadow, shadow.get_rect(center=(cx + max(1, w // 30), cy + max(1, w // 22))))
    s.blit(glyph, glyph.get_rect(center=(cx, cy)))



# === Пончики, снег, пуговицы, клавиатура, котики ===========================

SPRINKLES = ((250, 90, 110), (90, 170, 250), (250, 220, 80), (120, 210, 120), (250, 250, 250), (190, 120, 240))


def paint_donut(s, w, h, color, rng):
    """Пончик сверху: румяное тесто, волнистая глазурь, дырка и посыпка."""
    _base_tile(s, w, h, _mix_white(color, 0.72), 0.18, -40)
    cx, cy = w / 2, (h - h // 14) / 2
    dough, dough_d = (214, 158, 88), (176, 120, 60)
    pygame.draw.circle(s, dough_d, (int(cx) + 1, int(cy) + 2), int(w * 0.43))
    pygame.draw.circle(s, dough, (int(cx), int(cy)), int(w * 0.43))
    for i in range(14):                                  # глазурь с волнистым краем
        a = i * math.tau / 14 + rng.uniform(-0.1, 0.1)
        rr = w * rng.uniform(0.33, 0.37)
        pygame.draw.circle(s, color, (int(cx + math.cos(a) * rr), int(cy + math.sin(a) * rr)), max(2, int(w * 0.07)))
    pygame.draw.circle(s, color, (int(cx), int(cy)), int(w * 0.34))
    pygame.draw.circle(s, shade(color, 40), (int(cx - w * 0.12), int(cy - w * 0.14)), max(1, int(w * 0.07)))
    pygame.draw.circle(s, dough, (int(cx), int(cy)), int(w * 0.15))          # край дырки
    pygame.draw.circle(s, _mix_white(color, 0.72), (int(cx), int(cy)), int(w * 0.10))  # дырка
    for _ in range(9):                                   # посыпка
        a = rng.uniform(0, math.tau)
        rr = w * rng.uniform(0.19, 0.31)
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        t = rng.uniform(0, math.pi)
        dx, dy = math.cos(t) * w * 0.035, math.sin(t) * w * 0.035
        col = rng.choice(SPRINKLES)
        if col == tuple(color):
            col = (255, 255, 255)
        pygame.draw.line(s, col, (x - dx, y - dy), (x + dx, y + dy), max(2, w // 26))


def paint_snowflake(s, w, h, color, rng):
    """Снежинка на ледяной плитке: шесть лучей, у каждого варианта свои веточки."""
    _base_tile(s, w, h, color, 0.14, -55)
    inset = int(w * 0.12)
    pygame.draw.rect(s, shade(color, 18), (inset, inset, w - 2 * inset, h - 2 * inset - h // 14),
                     border_radius=max(2, int(w * 0.10)))
    cx, cy, r = w / 2, (h - h // 14) / 2, w * 0.36
    ice, shadow = (250, 252, 255), shade(color, -45)
    lw = max(1, w // 26)
    branch_at = rng.choice(((0.45, 0.72), (0.35, 0.60, 0.82), (0.55,), (0.40, 0.75)))
    branch_len = rng.uniform(0.18, 0.30)
    for pass_, col, off in ((0, shadow, 1), (1, ice, 0)):
        for k in range(6):
            a = k * math.pi / 3 + math.pi / 6
            ca, sa = math.cos(a), math.sin(a)
            tip = (cx + ca * r + off, cy + sa * r + off)
            pygame.draw.line(s, col, (cx + off, cy + off), tip, lw)
            for f in branch_at:
                bx, by = cx + ca * r * f + off, cy + sa * r * f + off
                for side in (-1, 1):
                    b = a + side * 0.75
                    pygame.draw.line(s, col, (bx, by), (bx + math.cos(b) * r * branch_len,
                                                         by + math.sin(b) * r * branch_len), lw)
    pygame.draw.circle(s, ice, (int(cx), int(cy)), max(1, int(w * 0.05)))


def paint_sewbutton(s, w, h, color, rng):
    """Пуговица на льняной ткани: ободок, углубление, 2 или 4 дырочки, нитка крестом."""
    linen = (226, 212, 186)
    _base_tile(s, w, h, linen, 0.14, -40)
    for i in range(1, 6):                                # переплетение ткани
        y = int(h * i / 6)
        pygame.draw.line(s, (214, 198, 170), (3, y), (w - 4, y), 1)
    cx, cy, r = w / 2, (h - h // 14) / 2, w * 0.44     # пуговица почти во всю плитку
    pygame.draw.circle(s, shade(color, -70), (int(cx) + 1, int(cy) + 2), int(r))
    pygame.draw.circle(s, color, (int(cx), int(cy)), int(r))
    pygame.draw.circle(s, shade(color, -30), (int(cx), int(cy)), int(r * 0.72))
    pygame.draw.circle(s, shade(color, 10), (int(cx), int(cy)), int(r * 0.66))
    pygame.draw.circle(s, shade(color, 60), (int(cx - r * 0.45), int(cy - r * 0.5)), max(1, int(r * 0.16)))
    four = rng.random() < 0.65
    d = r * 0.26
    holes = ((-d, -d), (d, -d), (-d, d), (d, d)) if four else ((-d, 0), (d, 0))
    thread = (250, 250, 244) if _luma(color) < 150 else (80, 60, 60)
    if four:
        pygame.draw.line(s, thread, (cx - d, cy - d), (cx + d, cy + d), max(1, w // 22))
        pygame.draw.line(s, thread, (cx + d, cy - d), (cx - d, cy + d), max(1, w // 22))
    else:
        pygame.draw.line(s, thread, (cx - d, cy), (cx + d, cy), max(1, w // 22))
    for dx, dy in holes:
        pygame.draw.circle(s, shade(color, -85), (int(cx + dx), int(cy + dy)), max(1, int(r * 0.11)))


# Надписи на клавишах: буквы вперемешку со служебными клавишами. Номер
# кубика (0–25) выбирает надпись, поэтому в фигуре они идут по порядку.
KEY_LEGENDS = ("Esc", "Tab", "Q", "W", "E", "R", "T", "Shift", "A", "S", "D", "F", "G",
               "Ctrl", "Z", "X", "C", "V", "B", "Alt", "Enter", "Space", "Del", "F1", "F2", "End")


def paint_key(s, w, h, color, rng):
    """Клавиша: объёмный колпачок с вогнутой верхней гранью и надписью —
    буквой или служебной клавишей (Esc, Shift…). Надпись своя у каждого
    кубика (как в «Алфавите») и едет вместе с ним."""
    radius = _radius(w, h, 0.14)
    pygame.draw.rect(s, shade(color, -70), (0, 0, w, h), border_radius=radius)
    pygame.draw.rect(s, shade(color, -30), (0, 0, w, h - max(2, h // 9)), border_radius=radius)
    m = max(2, int(w * 0.12))
    top = (m, max(1, m // 2), w - 2 * m, h - m - max(2, h // 5))
    pygame.draw.rect(s, color, top, border_radius=max(2, int(w * 0.10)))
    pygame.draw.rect(s, shade(color, 22), (top[0] + 1, top[1] + 1, top[2] - 2, max(1, top[3] // 3)),
                     border_radius=max(2, int(w * 0.08)))
    variant = getattr(rng, "variant", -1)
    legend = KEY_LEGENDS[variant % len(KEY_LEGENDS)] if variant >= 0 else "A"
    ink = (40, 40, 48) if _luma(color) > 150 else (240, 240, 246)
    room = top[2] - 2 * max(2, w // 12)
    if len(legend) == 1:
        glyph = _letter_font(max(8, int(h * 0.36))).render(legend, True, ink)
        s.blit(glyph, glyph.get_rect(topleft=(top[0] + max(2, w // 12), top[1] + max(1, w // 20))))
    else:
        # слово — мельче и по центру, уменьшаем, пока не влезет в клавишу
        size = max(6, int(h * 0.26))
        glyph = _letter_font(size).render(legend, True, ink)
        while glyph.get_width() > room and size > 6:
            size -= 1
            glyph = _letter_font(size).render(legend, True, ink)
        s.blit(glyph, glyph.get_rect(center=(top[0] + top[2] // 2, top[1] + top[3] // 2)))


def paint_cat(s, w, h, color, rng):
    """Мордочка котика: уши с розовым, глаза (открытые или сонные), носик,
    рот «w», усы; у части котиков полоски."""
    light = _luma(color) > 170
    tile = shade(color, -55) if light else _mix_white(color, 0.66)
    _base_tile(s, w, h, tile, 0.18, -35)
    cx, cy, r = w / 2, h * 0.54, w * 0.36
    inner = (246, 170, 186)
    for side in (-1, 1):                                 # уши
        ear = ((cx + side * r * 0.95, cy - r * 0.25), (cx + side * r * 0.75, cy - r * 1.25),
               (cx + side * r * 0.20, cy - r * 0.75))
        pygame.draw.polygon(s, color, ear)
        pygame.draw.polygon(s, inner, ((cx + side * r * 0.78, cy - r * 0.42), (cx + side * r * 0.70, cy - r * 1.02),
                                       (cx + side * r * 0.36, cy - r * 0.70)))
    pygame.draw.ellipse(s, color, (int(cx - r * 1.08), int(cy - r * 0.92), int(r * 2.16), int(r * 1.84)))
    if rng.random() < 0.4 and not light:                 # полоски
        for k in (-0.3, 0.0, 0.3):
            pygame.draw.line(s, shade(color, -40), (cx + k * r, cy - r * 0.9), (cx + k * r * 1.2, cy - r * 0.55),
                             max(1, w // 24))
    ink = (40, 32, 36)
    eyes = rng.choice(("open", "open", "sleepy"))
    iris = rng.choice(((110, 200, 90), (240, 200, 60), (90, 170, 230)))
    for side in (-1, 1):
        ex, ey = cx + side * r * 0.42, cy - r * 0.10
        if eyes == "open":
            pygame.draw.ellipse(s, iris, (int(ex - r * 0.17), int(ey - r * 0.20), int(r * 0.34), int(r * 0.40)))
            pygame.draw.ellipse(s, ink, (int(ex - r * 0.05), int(ey - r * 0.18), int(r * 0.10), int(r * 0.36)))
            pygame.draw.circle(s, (255, 255, 255), (int(ex - r * 0.07), int(ey - r * 0.10)), max(1, int(r * 0.05)))
        else:
            pygame.draw.line(s, ink, (ex - r * 0.17, ey), (ex, ey + r * 0.07), max(1, w // 30))
            pygame.draw.line(s, ink, (ex, ey + r * 0.07), (ex + r * 0.17, ey), max(1, w // 30))
    nose_y = cy + r * 0.22
    pygame.draw.polygon(s, (240, 120, 150), ((cx - r * 0.11, nose_y - r * 0.06), (cx + r * 0.11, nose_y - r * 0.06),
                                             (cx, nose_y + r * 0.08)))
    for side in (-1, 1):                                 # рот «w»
        pygame.draw.line(s, ink, (cx, nose_y + r * 0.08), (cx + side * r * 0.16, nose_y + r * 0.22), max(1, w // 34))
        for k in (-0.08, 0.06):                          # усы
            pygame.draw.line(s, shade(color, -70) if light else (250, 250, 250),
                             (cx + side * r * 0.35, nose_y + k * r), (cx + side * r * 1.05, nose_y + k * r * 2.2), 1)



# --- Мусор -----------------------------------------------------------------
# Предмет выбирает номер кубика (как буква в «Алфавите»): едет вместе с ним.

def _trash_paper(s, cx, cy, r, rng):
    """Скомканная бумага: грани разной яркости, как у настоящего комка."""
    outer = _chunk(cx, cy, r, rng, 10)
    pygame.draw.polygon(s, (120, 120, 116), [(x + 2, y + 3) for x, y in outer])        # тень на плитке
    pygame.draw.polygon(s, (214, 214, 208), outer)
    mid = (cx - r * 0.15, cy - r * 0.15)                # свет сверху слева: грани к нему ярче
    for i in range(len(outer)):                        # грани: треугольники от центра к краю
        a, b = outer[i], outer[(i + 1) % len(outer)]
        ex, ey = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy
        facing = -(ex + ey) / (abs(ex) + abs(ey) + 1e-6)      # −1 — от света, +1 — к свету
        light = int(214 + 38 * facing + (18 if i % 2 else -10))
        light = max(160, min(252, light))
        pygame.draw.polygon(s, (light, light, light - 6), (mid, a, b))
    for _ in range(5):                                 # заломы
        a = rng.uniform(0, math.tau)
        pygame.draw.line(s, (160, 160, 154), (cx, cy), (cx + math.cos(a) * r * 0.85, cy + math.sin(a) * r * 0.85), 1)
    pygame.draw.polygon(s, (150, 150, 144), outer, 1)
    for _ in range(3):                                 # строчки текста на листе
        y = cy + rng.uniform(-0.3, 0.3) * r
        pygame.draw.line(s, (170, 176, 196), (cx - r * 0.35, y), (cx + r * 0.2, y + r * 0.05), 1)


def _trash_can(s, cx, cy, r, rng):
    """Смятая банка: цилиндр со светотенью полосами, крышка с ключом, вмятина."""
    w, h = r * 1.25, r * 1.85
    x0, y0 = cx - w / 2, cy - h / 2
    pygame.draw.ellipse(s, (60, 50, 50), (int(x0 + 2), int(y0 + h - r * 0.12), int(w), int(r * 0.4)))   # тень
    bands = ((150, 20, 30), (196, 34, 44), (226, 60, 70), (242, 110, 118), (214, 44, 54), (170, 26, 36), (120, 16, 24))
    bw = w / len(bands)
    for i, col in enumerate(bands):                    # цилиндр: тёмные края, светлая середина
        pygame.draw.rect(s, col, (int(x0 + i * bw), int(y0 + r * 0.12), int(bw) + 1, int(h - r * 0.12)))
    for i, t in enumerate((0.42, 0.55)):               # серебристые полосы логотипа
        y = y0 + h * t
        pygame.draw.line(s, (236, 236, 240), (x0, y), (x0 + w, y + r * 0.04), max(1, int(r * 0.12)))
    pygame.draw.polygon(s, (110, 14, 22), ((x0 + w * 0.62, y0 + h * 0.62), (x0 + w * 0.9, y0 + h * 0.55),
                                           (x0 + w * 0.82, y0 + h * 0.75)))                  # вмятина
    pygame.draw.ellipse(s, (120, 124, 132), (int(x0), int(y0), int(w), int(r * 0.36)))        # крышка
    pygame.draw.ellipse(s, (210, 212, 218), (int(x0 + 1), int(y0 + 1), int(w - 2), int(r * 0.3)))
    pygame.draw.ellipse(s, (170, 172, 180), (int(cx - r * 0.2), int(y0 + r * 0.06), int(r * 0.4), int(r * 0.16)))  # ключ
    pygame.draw.rect(s, (230, 230, 236), (int(x0 + w * 0.2), int(y0 + h * 0.2), max(1, int(r * 0.08)), int(h * 0.6)))


def _trash_bottle(s, cx, cy, r, rng):
    """Пластиковая бутылка: прозрачный голубой пластик с бликом, рёбра, этикетка, крышка."""
    w, h = r * 1.0, r * 1.45
    bx, by = cx - w / 2, cy - h / 2 + r * 0.3
    pygame.draw.ellipse(s, (60, 70, 80), (int(bx + 2), int(by + h - r * 0.1), int(w), int(r * 0.3)))
    pygame.draw.rect(s, (104, 170, 196), (int(bx), int(by), int(w), int(h)), border_radius=max(2, int(r * 0.3)))
    pygame.draw.rect(s, (150, 206, 226), (int(bx + w * 0.12), int(by), int(w * 0.62), int(h)), border_radius=max(2, int(r * 0.25)))
    pygame.draw.polygon(s, (150, 206, 226), ((bx + w * 0.12, by + 1), (cx - w * 0.2, by - r * 0.3),
                                             (cx + w * 0.2, by - r * 0.3), (bx + w * 0.74, by + 1)))       # плечики
    pygame.draw.rect(s, (104, 170, 196), (int(cx - w * 0.2), int(by - r * 0.55), int(w * 0.4), int(r * 0.3)))
    pygame.draw.rect(s, (30, 90, 170), (int(cx - w * 0.26), int(by - r * 0.8), int(w * 0.52), int(r * 0.3)),
                     border_radius=max(1, int(r * 0.06)))                                                  # крышка
    for k in range(3):
        pygame.draw.line(s, (20, 60, 130), (cx - w * 0.2 + k * w * 0.2, by - r * 0.78), (cx - w * 0.2 + k * w * 0.2, by - r * 0.52), 1)
    pygame.draw.rect(s, (246, 246, 246), (int(bx), int(by + h * 0.35), int(w), int(h * 0.28)))              # этикетка
    pygame.draw.rect(s, (40, 130, 210), (int(bx), int(by + h * 0.43), int(w), max(2, int(h * 0.1))))
    for k in range(3):                                                                                     # рёбра
        y = by + h * (0.72 + k * 0.08)
        pygame.draw.line(s, (84, 150, 176), (bx + 2, y), (bx + w - 3, y), 1)
    pygame.draw.line(s, (236, 250, 255), (bx + w * 0.22, by + h * 0.05), (bx + w * 0.22, by + h * 0.32), max(1, int(r * 0.1)))


def _trash_banana(s, cx, cy, r, rng):
    """Банановая кожура: хвостик сверху, три широких лепестка свисают вниз,
    у боковых видна светлая изнанка, по кожуре — спелые пятнышки."""
    stem = (cx, cy - r * 0.75)
    for ang, inner in ((math.pi * 0.72, True), (math.pi * 0.28, True), (math.pi * 0.5, False)):
        tip = (stem[0] + math.cos(ang) * r * 1.55, stem[1] + math.sin(ang) * r * 1.55)
        nx, ny = -math.sin(ang), math.cos(ang)            # поперёк лепестка
        wd = r * 0.34
        mid = (stem[0] + (tip[0] - stem[0]) * 0.55, stem[1] + (tip[1] - stem[1]) * 0.55)
        petal = ((stem[0] + nx * wd * 0.45, stem[1] + ny * wd * 0.45), (mid[0] + nx * wd, mid[1] + ny * wd),
                 tip, (mid[0] - nx * wd, mid[1] - ny * wd), (stem[0] - nx * wd * 0.45, stem[1] - ny * wd * 0.45))
        pygame.draw.polygon(s, (110, 80, 20), [(x + 1, y + 2) for x, y in petal])
        pygame.draw.polygon(s, (246, 204, 52), petal)
        if inner:                                          # светлая изнанка — половина лепестка
            half = (petal[0], (mid[0] + nx * wd * 0.1, mid[1] + ny * wd * 0.1), tip, petal[3], petal[4])
            pygame.draw.polygon(s, (250, 240, 196), half)
        pygame.draw.circle(s, (100, 70, 26), (int(tip[0]), int(tip[1])), max(1, int(r * 0.08)))
    for _ in range(6):                                   # спелые пятнышки
        pygame.draw.circle(s, (140, 100, 36), (int(cx + rng.uniform(-0.45, 0.45) * r), int(cy + rng.uniform(-0.3, 0.5) * r)),
                           max(1, int(r * rng.uniform(0.04, 0.07))))
    pygame.draw.rect(s, (120, 90, 44), (int(stem[0] - r * 0.12), int(stem[1] - r * 0.28), max(2, int(r * 0.24)), int(r * 0.36)),
                     border_radius=max(1, int(r * 0.05)))


def _trash_fishbone(s, cx, cy, r, rng):
    """Рыбий скелет: голова с жаберной дугой и глазом, хребет, рёбра, хвост с лучами."""
    bone, shadow = (238, 234, 220), (150, 146, 134)
    for off, col in ((2, shadow), (0, bone)):
        pygame.draw.line(s, col, (cx - r * 0.95 + off, cy + off), (cx + r * 0.4 + off, cy + off), max(1, int(r * 0.13)))
        for k in range(5):
            x = cx - r * 0.75 + k * r * 0.26 + off
            ln = r * (0.36 + 0.06 * math.sin(k))
            pygame.draw.line(s, col, (x, cy + off), (x + r * 0.12, cy - ln + off), max(1, int(r * 0.08)))
            pygame.draw.line(s, col, (x, cy + off), (x + r * 0.12, cy + ln + off), max(1, int(r * 0.08)))
    head = ((cx + r * 0.35, cy - r * 0.45), (cx + r * 1.05, cy - r * 0.05), (cx + r * 1.0, cy + r * 0.12), (cx + r * 0.35, cy + r * 0.45))
    pygame.draw.polygon(s, shadow, [(x + 2, y + 2) for x, y in head])
    pygame.draw.polygon(s, bone, head)
    pygame.draw.line(s, shadow, (cx + r * 0.5, cy - r * 0.38), (cx + r * 0.5, cy + r * 0.38), 1)          # жабры
    pygame.draw.circle(s, (40, 40, 44), (int(cx + r * 0.72), int(cy - r * 0.1)), max(1, int(r * 0.09)))
    tail = ((cx - r * 0.95, cy), (cx - r * 1.35, cy - r * 0.42), (cx - r * 1.25, cy), (cx - r * 1.35, cy + r * 0.42))
    pygame.draw.polygon(s, bone, tail)
    for k in (-0.25, 0.0, 0.25):
        pygame.draw.line(s, shadow, (cx - r * 0.98, cy), (cx - r * 1.3, cy + k * r * 1.3), 1)


def _trash_core(s, cx, cy, r, rng):
    """Огрызок: красная кожура сверху и снизу, мякоть с потемнением, укусы, семечки."""
    top = ((cx - r * 0.7, cy - r * 0.55), (cx + r * 0.7, cy - r * 0.55), (cx + r * 0.55, cy - r * 0.95), (cx - r * 0.55, cy - r * 0.95))
    bottom = ((cx - r * 0.72, cy + r * 0.55), (cx + r * 0.72, cy + r * 0.55), (cx + r * 0.5, cy + r * 0.95), (cx - r * 0.5, cy + r * 0.95))
    flesh = [(cx - r * 0.66, cy - r * 0.55)]
    for i in range(6):                                   # укус слева: волнистый край
        t = i / 5
        flesh.append((cx - r * (0.28 + 0.1 * math.sin(t * math.pi * 3)), cy - r * 0.55 + t * r * 1.1))
    flesh.append((cx - r * 0.66, cy + r * 0.55))
    flesh += [(cx + r * 0.66, cy + r * 0.55)]
    for i in range(6):                                   # укус справа
        t = 1 - i / 5
        flesh.append((cx + r * (0.3 + 0.1 * math.sin(t * math.pi * 3 + 1)), cy - r * 0.55 + t * r * 1.1))
    flesh.append((cx + r * 0.66, cy - r * 0.55))
    pygame.draw.polygon(s, (90, 60, 40), [(x + 2, y + 2) for x, y in flesh])
    pygame.draw.polygon(s, (244, 230, 186), flesh)
    for dx in (-0.25, 0.22):                             # потемнела на воздухе
        pygame.draw.ellipse(s, (214, 180, 120), (int(cx + dx * r - r * 0.08), int(cy - r * 0.3), int(r * 0.16), int(r * 0.6)))
    for poly, dark, light in ((top, (150, 20, 30), (220, 50, 60)), (bottom, (140, 20, 28), (210, 44, 54))):
        pygame.draw.polygon(s, dark, poly)
        pygame.draw.polygon(s, light, [(x * 0.85 + cx * 0.15, y) for x, y in poly])
    for dy in (-0.12, 0.18):                             # семечки
        pygame.draw.ellipse(s, (70, 38, 20), (int(cx - r * 0.09), int(cy + dy * r - r * 0.12), max(2, int(r * 0.18)), max(3, int(r * 0.26))))
        pygame.draw.circle(s, (140, 90, 60), (int(cx - r * 0.03), int(cy + dy * r - r * 0.06)), max(1, int(r * 0.04)))
    pygame.draw.line(s, (90, 60, 30), (cx, cy - r * 0.95), (cx + r * 0.15, cy - r * 1.3), max(1, int(r * 0.12)))
    pygame.draw.ellipse(s, (80, 150, 60), (int(cx + r * 0.1), int(cy - r * 1.35), int(r * 0.35), int(r * 0.18)))


def _trash_boot(s, cx, cy, r, rng):
    """Старый ботинок: кожа со светотенью, толстая подошва, строчка, шнуровка, дырка."""
    boot = ((cx - r * 0.7, cy - r), (cx - r * 0.05, cy - r), (cx - r * 0.05, cy + r * 0.15),
            (cx + r * 0.9, cy + r * 0.3), (cx + r * 1.05, cy + r * 0.6), (cx + r, cy + r * 0.75), (cx - r * 0.7, cy + r * 0.75))
    pygame.draw.polygon(s, (40, 26, 18), [(x + 2, y + 3) for x, y in boot])
    pygame.draw.polygon(s, (112, 72, 42), boot)
    pygame.draw.polygon(s, (140, 94, 58), ((cx - r * 0.62, cy - r * 0.92), (cx - r * 0.3, cy - r * 0.92),
                                           (cx - r * 0.3, cy + r * 0.6), (cx - r * 0.62, cy + r * 0.6)))     # блик
    pygame.draw.polygon(s, (86, 54, 30), ((cx + r * 0.3, cy + r * 0.2), (cx + r * 0.9, cy + r * 0.3),
                                          (cx + r * 1.02, cy + r * 0.6), (cx + r * 0.3, cy + r * 0.6)))      # мысок темнее
    pygame.draw.rect(s, (36, 30, 28), (int(cx - r * 0.72), int(cy + r * 0.66), int(r * 1.8), max(3, int(r * 0.22))),
                     border_radius=max(1, int(r * 0.08)))                                                   # подошва
    for k in range(7):                                                                                     # строчка
        x = cx - r * 0.6 + k * r * 0.24
        pygame.draw.line(s, (220, 200, 160), (x, cy + r * 0.58), (x + r * 0.1, cy + r * 0.58), 1)
    for k in range(4):                                                                                     # шнуровка
        y = cy - r * 0.8 + k * r * 0.22
        pygame.draw.circle(s, (200, 200, 190), (int(cx - r * 0.12), int(y)), max(1, int(r * 0.05)))
        pygame.draw.line(s, (236, 226, 196), (cx - r * 0.45, y + r * 0.05), (cx - r * 0.12, y), 1)
    hole = (int(cx + r * 0.55), int(cy + r * 0.45))                                                         # дырка
    pygame.draw.circle(s, (30, 20, 14), hole, max(2, int(r * 0.15)))
    for k in range(5):
        a = k * math.tau / 5
        pygame.draw.line(s, (150, 110, 70), hole, (hole[0] + math.cos(a) * r * 0.22, hole[1] + math.sin(a) * r * 0.22), 1)


TRASH_ITEMS = (_trash_paper, _trash_can, _trash_bottle, _trash_banana, _trash_fishbone, _trash_core, _trash_boot)


def paint_trash(s, w, h, color, rng):
    """Мусор на плитке цвета контейнера для раздельного сбора: пластик
    потёртый, в царапинах и грязных разводах — как у настоящего бака."""
    _base_tile(s, w, h, color, 0.14, -55)
    m = max(2, int(w * 0.08))
    pygame.draw.rect(s, shade(color, 18), (m, m, w - 2 * m, h - 2 * m - h // 14), 1, border_radius=max(2, int(w * 0.08)))
    grime = random.Random(int(sum(color)) * 17 + getattr(rng, "variant", 0))
    for _ in range(6):                                   # грязные пятна
        pygame.draw.circle(s, shade(color, -30), (int(grime.uniform(0.1, 0.9) * w), int(grime.uniform(0.1, 0.85) * h)),
                           max(1, int(w * grime.uniform(0.02, 0.05))))
    for _ in range(3):                                   # царапины
        x, y = grime.uniform(0.1, 0.8) * w, grime.uniform(0.1, 0.8) * h
        pygame.draw.line(s, shade(color, 30), (x, y), (x + w * grime.uniform(0.08, 0.2), y + h * grime.uniform(-0.05, 0.05)), 1)
    variant = getattr(rng, "variant", -1)
    item = TRASH_ITEMS[variant % len(TRASH_ITEMS)] if variant >= 0 else rng.choice(TRASH_ITEMS)
    item(s, w / 2, (h - h // 14) / 2, w * 0.36, random.Random(variant * 31 + 7))   # крупно — на поле мелкое теряется



# --- Шахматы ----------------------------------------------------------------
# Фигура задаётся номером кубика (как буква в «Алфавите») и едет вместе с ним.

def _hw_at(profile, t):
    """Полуширина точёной фигуры на высоте t (0 — низ, 1 — верх профиля)."""
    for i in range(len(profile) - 1):
        (y0, w0), (y1, w1) = profile[i], profile[i + 1]
        if y0 <= t <= y1:
            k = 0.0 if y1 == y0 else (t - y0) / (y1 - y0)
            return w0 + (w1 - w0) * k
    return profile[-1][1]


def _chess_turned(s, cx, by, hh, fill, edge, profile, top=1.0):
    """Точёное тело фигуры: рисуем горизонтальными срезами, поэтому легко
    добавить светотень — слева блик, справа тень, как у объёмной фигуры."""
    light = tuple(min(255, c + 26) for c in fill)
    dark = tuple(max(0, int(c * 0.72)) for c in fill)
    steps = max(16, int(hh))
    for i in range(steps):
        t = top * i / (steps - 1)
        hw = _hw_at(profile, t) * hh
        if hw <= 0:
            continue
        y = by - t * hh
        pygame.draw.line(s, edge, (cx - hw - 1, y), (cx + hw + 1, y), 1)
        pygame.draw.line(s, fill, (cx - hw, y), (cx + hw, y), 1)
        pygame.draw.line(s, dark, (cx + hw * 0.42, y), (cx + hw, y), 1)
        pygame.draw.line(s, light, (cx - hw * 0.85, y), (cx - hw * 0.45, y), 1)


def _chess_ball(s, cx, cy, r, fill, edge):
    pygame.draw.circle(s, edge, (int(cx), int(cy)), int(r) + 1)
    pygame.draw.circle(s, fill, (int(cx), int(cy)), int(r))
    pygame.draw.circle(s, tuple(min(255, c + 30) for c in fill), (int(cx - r * 0.3), int(cy - r * 0.3)), max(1, int(r * 0.42)))


# Профили: (доля высоты, полуширина в долях высоты). Снизу вверх.
_P_BASE = ((0.00, 0.33), (0.05, 0.33), (0.07, 0.28), (0.11, 0.21), (0.15, 0.17))
_P_PAWN = _P_BASE + ((0.26, 0.13), (0.36, 0.12), (0.44, 0.17), (0.47, 0.17), (0.49, 0.12))
_P_ROOK = _P_BASE + ((0.22, 0.17), (0.50, 0.19), (0.56, 0.24), (0.60, 0.25))
_P_BISHOP = _P_BASE + ((0.24, 0.13), (0.40, 0.11), (0.50, 0.15), (0.53, 0.15), (0.55, 0.10))
_P_QUEEN = _P_BASE + ((0.26, 0.14), (0.44, 0.12), (0.54, 0.18), (0.57, 0.18), (0.59, 0.13))
_P_KING = _P_BASE + ((0.26, 0.15), (0.46, 0.13), (0.56, 0.19), (0.59, 0.19), (0.61, 0.14))


def _chess_pawn(s, cx, by, hh, fill, edge):
    _chess_turned(s, cx, by, hh, fill, edge, _P_PAWN, 0.49)
    _chess_ball(s, cx, by - hh * 0.62, hh * 0.15, fill, edge)


def _chess_rook(s, cx, by, hh, fill, edge):
    _chess_turned(s, cx, by, hh, fill, edge, _P_ROOK, 0.60)
    tw, th = hh * 0.50, hh * 0.20
    x0, y0 = cx - tw / 2, by - hh * 0.80
    pygame.draw.rect(s, edge, (int(x0) - 1, int(y0) - 1, int(tw) + 2, int(th) + 2))
    pygame.draw.rect(s, fill, (int(x0), int(y0), int(tw), int(th)))
    pygame.draw.rect(s, tuple(max(0, int(c * 0.72)) for c in fill), (int(cx + tw * 0.18), int(y0), int(tw * 0.32), int(th)))
    for k in (0.28, 0.62):                               # зубцы
        pygame.draw.rect(s, edge, (int(x0 + tw * k), int(y0), max(2, int(tw * 0.11)), int(th * 0.5)))


def _chess_bishop(s, cx, by, hh, fill, edge):
    _chess_turned(s, cx, by, hh, fill, edge, _P_BISHOP, 0.55)
    mitre = (int(cx - hh * 0.155), int(by - hh * 0.95), int(hh * 0.31), int(hh * 0.42))
    pygame.draw.ellipse(s, edge, (mitre[0] - 1, mitre[1] - 1, mitre[2] + 2, mitre[3] + 2))
    pygame.draw.ellipse(s, fill, mitre)
    pygame.draw.ellipse(s, tuple(max(0, int(c * 0.78)) for c in fill),
                        (int(cx + hh * 0.02), mitre[1] + 2, int(hh * 0.13), mitre[3] - 4))
    pygame.draw.line(s, edge, (cx + hh * 0.03, by - hh * 0.9), (cx + hh * 0.12, by - hh * 0.74), max(1, int(hh * 0.04)))
    _chess_ball(s, cx, by - hh * 0.99, hh * 0.06, fill, edge)


def _chess_knight(s, cx, by, hh, fill, edge):
    """Конь: морда вправо, длинная переносица, скула, два небольших уха,
    грива тёмной полосой вдоль затылка."""
    _chess_turned(s, cx, by, hh, fill, edge, _P_BASE + ((0.20, 0.17), (0.26, 0.16)), 0.26)
    u = hh
    head = ((-0.22, -0.26), (-0.21, -0.52), (-0.17, -0.72), (-0.12, -0.88),
            (-0.08, -1.02), (-0.02, -0.88), (0.04, -0.98), (0.09, -0.84),     # два уха
            (0.21, -0.78), (0.34, -0.70), (0.40, -0.60),                        # лоб и переносица
            (0.36, -0.52), (0.24, -0.50), (0.16, -0.44), (0.06, -0.36), (0.17, -0.26))
    pts = [(cx + x * u, by + y * u) for x, y in head]
    pygame.draw.polygon(s, edge, [(x + (1.3 if x > cx else -1.3), y - 1) for x, y in pts])
    pygame.draw.polygon(s, fill, pts)
    dark = tuple(max(0, int(c * 0.72)) for c in fill)
    light = tuple(min(255, c + 26) for c in fill)
    pygame.draw.polygon(s, dark, [(cx + x * u, by + y * u) for x, y in          # грива
                                  ((-0.21, -0.52), (-0.17, -0.72), (-0.12, -0.88), (-0.04, -0.90),
                                   (-0.06, -0.70), (-0.10, -0.50), (-0.12, -0.30), (-0.20, -0.30))])
    pygame.draw.polygon(s, dark, [(cx + x * u, by + y * u) for x, y in          # тень под мордой
                                  ((0.06, -0.36), (0.16, -0.44), (0.24, -0.50), (0.36, -0.52),
                                   (0.40, -0.60), (0.28, -0.58), (0.14, -0.50))])
    pygame.draw.polygon(s, light, [(cx + x * u, by + y * u) for x, y in         # блик на щеке
                                   ((0.02, -0.52), (0.12, -0.70), (0.22, -0.72), (0.16, -0.54))])
    pygame.draw.circle(s, edge, (int(cx + u * 0.15), int(by - u * 0.74)), max(1, int(u * 0.05)))   # глаз
    pygame.draw.circle(s, edge, (int(cx + u * 0.35), int(by - u * 0.60)), max(1, int(u * 0.035)))  # ноздря
    pygame.draw.line(s, edge, (cx + u * 0.25, by - u * 0.53), (cx + u * 0.36, by - u * 0.55), 1)   # рот


def _chess_queen(s, cx, by, hh, fill, edge):
    _chess_turned(s, cx, by, hh, fill, edge, _P_QUEEN, 0.59)
    ring = (int(cx - hh * 0.26), int(by - hh * 0.70), int(hh * 0.52), int(hh * 0.10))
    pygame.draw.rect(s, edge, (ring[0] - 1, ring[1] - 1, ring[2] + 2, ring[3] + 2), border_radius=int(hh * 0.04))
    pygame.draw.rect(s, fill, ring, border_radius=int(hh * 0.04))
    for k in range(5):                                   # зубцы с шариками
        x = cx - hh * 0.21 + k * hh * 0.105
        ln = hh * (0.16 if k % 2 == 0 else 0.22)
        pygame.draw.line(s, edge, (x, by - hh * 0.70), (x, by - hh * 0.70 - ln), max(2, int(hh * 0.055)))
        pygame.draw.line(s, fill, (x, by - hh * 0.70), (x, by - hh * 0.70 - ln), max(1, int(hh * 0.04)))
        _chess_ball(s, x, by - hh * 0.70 - ln, hh * 0.05, fill, edge)


def _chess_king(s, cx, by, hh, fill, edge):
    _chess_turned(s, cx, by, hh, fill, edge, _P_KING, 0.61)
    band = (int(cx - hh * 0.22), int(by - hh * 0.74), int(hh * 0.44), int(hh * 0.12))
    pygame.draw.rect(s, edge, (band[0] - 1, band[1] - 1, band[2] + 2, band[3] + 2), border_radius=int(hh * 0.04))
    pygame.draw.rect(s, fill, band, border_radius=int(hh * 0.04))
    pygame.draw.rect(s, tuple(max(0, int(c * 0.74)) for c in fill),
                     (int(cx + hh * 0.06), band[1] + 1, int(hh * 0.15), band[3] - 2))
    cw = max(2, int(hh * 0.075))                          # крест
    for col, off in ((edge, 1), (fill, 0)):
        pygame.draw.rect(s, col, (int(cx - cw / 2) - off, int(by - hh * 1.0) - off, cw + off * 2, int(hh * 0.26) + off * 2))
        pygame.draw.rect(s, col, (int(cx - hh * 0.10) - off, int(by - hh * 0.92) - off, int(hh * 0.20) + off * 2, cw + off * 2))


CHESS_PIECES = (_chess_pawn, _chess_knight, _chess_bishop, _chess_rook, _chess_queen, _chess_king)


SUPERSAMPLE = 3          # во столько раз крупнее рисуем фигуру перед уменьшением


def _smooth(draw_fn, w, h):
    """Рисует draw_fn на поверхности в SUPERSAMPLE раз крупнее и возвращает
    уменьшенную со сглаживанием — края выходят плавными, без «лесенки».
    Текстуры кэшируются, поэтому эта работа делается один раз."""
    k = SUPERSAMPLE
    big = pygame.Surface((w * k, h * k), pygame.SRCALPHA)
    draw_fn(big, w * k, h * k, k)
    return pygame.transform.smoothscale(big, (w, h))


def paint_chess(s, w, h, color, rng):
    """Клетка шахматной доски с фигурой. Фигура белая на тёмной клетке и
    чёрная на светлой — чтобы читалась на любом цвете. Сама фигура рисуется
    крупнее и уменьшается со сглаживанием: иначе края «лесенкой»."""
    _base_tile(s, w, h, color, 0.10, -50)
    for k in range(4):                                   # лёгкая текстура дерева
        y = h * (0.18 + k * 0.2) + rng.uniform(-2, 2)
        pygame.draw.line(s, shade(color, -12), (w * 0.08, y), (w * 0.92, y + rng.uniform(-2, 2)), 1)
    white = _luma(color) < 150
    fill = (246, 242, 230) if white else (44, 40, 46)
    edge = (70, 62, 56) if white else (10, 10, 12)
    variant = getattr(rng, "variant", -1)
    piece = CHESS_PIECES[variant % len(CHESS_PIECES)] if variant >= 0 else rng.choice(CHESS_PIECES)
    by, hh = h * 0.86, h * 0.76
    pygame.draw.ellipse(s, shade(color, -40), (int(w / 2 - hh * 0.34), int(by - hh * 0.05), int(hh * 0.68), int(hh * 0.1)))

    def draw_piece(big, bw, bh, k):
        piece(big, bw / 2, by * k, hh * k, fill, edge)

    s.blit(_smooth(draw_piece, w, h), (0, 0))



# --- Мячи --------------------------------------------------------------
# Площадка выбирает мяч (как сыр у пиццы): тайл = площадка, мяч — свои
# настоящие цвета, независимо от темы.

def _ball_regular(cx, cy, r, n, start=0.0):
    return [(cx + math.cos(start + i * math.tau / n) * r, cy + math.sin(start + i * math.tau / n) * r)
            for i in range(n)]


def _ball_sphere(s, cx, cy, r, base):
    """Настоящий объём: плавный радиальный переход от тёмного края к яркому
    блику — концентрические круги, сдвинутые к точке света, а не один
    сдвинутый силуэт. Вместе с супersэмплингом в paint_ball даёт гладкий шар."""
    hlx, hly = cx - r * 0.34, cy - r * 0.36
    steps = 14
    for i in range(steps, -1, -1):
        t = i / steps                                    # 1 — край, 0 — у блика
        rad = r * (0.14 + 0.86 * t)
        ccx = cx + (hlx - cx) * (1 - t) * 0.55
        ccy = cy + (hly - cy) * (1 - t) * 0.55
        pygame.draw.circle(s, shade(base, int(-58 + 96 * (1 - t))), (int(ccx), int(ccy)), int(rad))
    pygame.draw.circle(s, shade(base, 75), (int(hlx), int(hly)), max(1, int(r * 0.12)))


def _ball_soccer(s, cx, cy, r, rng):
    """Весь мяч расчерчен тонким швом — не только вокруг чёрных долек, но и
    белые шестиугольники между ними, как на настоящем мяче. Сверху — сами
    дольки, некрупные, чтобы не превращаться в кляксу."""
    white = (248, 247, 240)
    _ball_sphere(s, cx, cy, r, white)

    seam = shade(white, -30)                            # мелкая сетка швов по всей сфере
    slw = max(1, int(r * 0.014))
    step = r * 0.20
    rows = int(r * 2 / (step * 0.87)) + 2
    for row in range(-rows, rows + 1):
        y = row * step * 0.87
        offset = (row % 2) * step * 0.5
        for col in range(-rows, rows + 1):
            x = col * step + offset
            if x * x + y * y > (r * 0.95) ** 2:
                continue
            for dx, dy in ((step, 0.0), (step * 0.5, step * 0.87), (-step * 0.5, step * 0.87)):
                nx, ny = x + dx, y + dy
                if nx * nx + ny * ny <= (r * 0.95) ** 2:
                    pygame.draw.line(s, seam, (cx + x, cy + y), (cx + nx, cy + ny), slw)

    ink = (40, 38, 36)                                   # чёрные дольки поверх сетки
    turn = rng.uniform(0, math.tau)
    pygame.draw.polygon(s, ink, _ball_regular(cx, cy, r * 0.26, 5, -math.pi / 2 + turn))
    for i in range(5):
        a = -math.pi / 2 + turn + i * math.tau / 5 + math.pi / 5
        px, py = cx + math.cos(a) * r * 0.50, cy + math.sin(a) * r * 0.50
        pygame.draw.polygon(s, ink, _ball_regular(px, py, r * 0.17, 5, a + math.pi))


def _ball_basketball(s, cx, cy, r, rng):
    """Швы как у настоящего мяча: прямой крест через центр (вертикаль и
    горизонталь) и две боковые дуги, которые начинаются у края мяча сверху
    и снизу и выгибаются к центру, как скобки «) (»."""
    orange = (190, 86, 44)
    _ball_sphere(s, cx, cy, r, orange)
    ink = (30, 18, 12)
    lw = max(1, int(r * 0.085))
    pygame.draw.line(s, ink, (cx, cy - r * 0.97), (cx, cy + r * 0.97), lw)      # вертикаль
    pygame.draw.line(s, ink, (cx - r * 0.97, cy), (cx + r * 0.97, cy), lw)      # горизонталь
    for side in (-1, 1):                                  # боковые дуги, выгнутые к центру
        pts = [(cx + side * (r * 0.72 - r * 0.36 * math.sin(t * math.pi)), cy - r * 0.70 + t * r * 1.40)
               for t in (i / 20 for i in range(21))]
        for a, b in zip(pts, pts[1:]):
            pygame.draw.line(s, ink, a, b, lw)
    pebble = shade(orange, -34)                           # фактура кожи: ровная сетка с дрожанием
    step = max(1.6, r * 0.10)
    n = int(r * 2 / step)
    dot = max(1, int(r * 0.016))
    for gy in range(-n, n + 1):
        for gx in range(-n, n + 1):
            x = cx + gx * step + rng.uniform(-step * 0.25, step * 0.25)
            y = cy + gy * step + rng.uniform(-step * 0.25, step * 0.25)
            if (x - cx) ** 2 + (y - cy) ** 2 <= (r * 0.88) ** 2:
                pygame.draw.circle(s, pebble, (int(x), int(y)), dot)


def _ball_tennis(s, cx, cy, r, rng):
    """Два одинаковых полумесяца шва: правый рогами влево, левый рогами
    вправо — классический «восьмерочный» шов теннисного мяча."""
    green = (214, 230, 64)
    _ball_sphere(s, cx, cy, r, green)
    ink = (250, 250, 246)
    lw = max(2, int(r * 0.10))
    for side in (-1, 1):
        pts = [(cx + side * r * 0.55 * math.cos(a), cy + r * 0.86 * math.sin(a))
               for a in (-math.pi * 0.42 + math.pi * 0.84 * i / 20 for i in range(21))]
        for a, b in zip(pts, pts[1:]):
            pygame.draw.line(s, ink, a, b, lw)
    fuzz = shade(green, 30)                              # ворсинки по краю
    for _ in range(50):
        a = rng.uniform(0, math.tau)
        x, y = cx + math.cos(a) * r * 0.94, cy + math.sin(a) * r * 0.94
        pygame.draw.line(s, fuzz, (x, y), (x + math.cos(a) * r * 0.07, y + math.sin(a) * r * 0.07), 1)


def _ball_volleyball(s, cx, cy, r, rng):
    """Шесть спиральных клиньев — синий, белый, жёлтый, закрученных от
    центра к краю, как на настоящем волейбольном мяче: не ровные полосы,
    а панели-пропеллеры."""
    white = (246, 246, 244)
    _ball_sphere(s, cx, cy, r, white)
    colors = ((38, 72, 150), white, (247, 195, 45))       # синий, белый, жёлтый
    n = 6
    twist = math.radians(65)                              # общий закрут от центра к краю
    turn = rng.uniform(0, math.tau)
    steps = 28
    for i in range(n):
        color = colors[i % 3]
        base = turn + i * math.tau / n
        for k in range(steps):
            t0, t1 = k / steps, (k + 1) / steps
            r0, r1 = r * 1.0 * t0, r * 1.0 * t1
            w0 = (math.tau / n) * 0.90 * (0.25 + 0.75 * t0)   # клин уже к центру, шире к краю
            w1 = (math.tau / n) * 0.90 * (0.25 + 0.75 * t1)
            a0c, a1c = base + twist * t0, base + twist * t1
            p1 = (cx + math.cos(a0c - w0 / 2) * r0, cy + math.sin(a0c - w0 / 2) * r0)
            p2 = (cx + math.cos(a0c + w0 / 2) * r0, cy + math.sin(a0c + w0 / 2) * r0)
            p3 = (cx + math.cos(a1c + w1 / 2) * r1, cy + math.sin(a1c + w1 / 2) * r1)
            p4 = (cx + math.cos(a1c - w1 / 2) * r1, cy + math.sin(a1c - w1 / 2) * r1)
            pygame.draw.polygon(s, color, (p1, p2, p3, p4))


def _ball_baseball(s, cx, cy, r, rng):
    """Два дугообразных шва так же, как у теннисного (но красным), плюс
    короткие стежки-ёлочкой вдоль каждого — как настоящая прошивка."""
    _ball_sphere(s, cx, cy, r, (250, 248, 240))
    ink = (192, 40, 40)
    lw = max(1, int(r * 0.045))
    for side in (-1, 1):
        pts = [(cx + side * r * 0.55 * math.cos(a), cy + r * 0.86 * math.sin(a))
               for a in (-math.pi * 0.42 + math.pi * 0.84 * i / 12 for i in range(13))]
        for a, b in zip(pts, pts[1:]):
            pygame.draw.line(s, ink, a, b, lw)
        for i in range(1, 12, 2):
            px, py = pts[i]
            nx, ny = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
            ln = math.hypot(nx, ny) or 1
            nx, ny = -ny / ln * r * 0.09, nx / ln * r * 0.09
            pygame.draw.line(s, ink, (px - nx, py - ny), (px + nx, py + ny), lw)


def _ball_golf(s, cx, cy, r, rng):
    white = (250, 250, 246)
    _ball_sphere(s, cx, cy, r, white)
    dimple, outline, rim = shade(white, -32), shade(white, -55), shade(white, 20)
    lw = max(1, int(r * 0.012))
    step = r * 0.26
    for gy in range(-3, 4):
        for gx in range(-3, 4):
            off = step * 0.5 if gy % 2 else 0.0          # шахматная раскладка ямочек
            x, y = cx + gx * step + off, cy + gy * step * 0.88
            if (x - cx) ** 2 + (y - cy) ** 2 <= (r * 0.84) ** 2:
                rr = max(1, int(r * 0.06))
                pygame.draw.circle(s, dimple, (int(x), int(y)), rr)
                pygame.draw.circle(s, outline, (int(x), int(y)), rr, lw)      # обводка — ямочка не размыта в пятно
                pygame.draw.circle(s, rim, (int(x - r * 0.015), int(y - r * 0.015)), max(1, int(r * 0.022)))


def _ball_beach(s, cx, cy, r, rng):
    """Полосы от полюса к полюсу, как дольки апельсина, — а не сектора пирога:
    так сразу видно, что это пляжный мяч, а не колесо или кнопка."""
    _ball_sphere(s, cx, cy, r, (246, 246, 244))
    white = (247, 247, 245)
    palette = ((230, 60, 60), white, (250, 200, 50), white, (60, 140, 220), white, (70, 180, 90), white)
    n = len(palette)

    def bx(j, t):                                       # граница гор-панели j на высоте t (0..1, полюс..полюс)
        return r * math.sin(t * math.pi) * math.sin(math.pi * (j / n - 0.5))

    def by(t):                                          # тот же угол t для вертикали — иначе не сфера, а бочка
        return -r * math.cos(t * math.pi)

    steps = 14
    for i, col in enumerate(palette):
        left = [(cx + bx(i, k / steps), cy + by(k / steps)) for k in range(steps + 1)]
        right = [(cx + bx(i + 1, k / steps), cy + by(k / steps)) for k in range(steps, -1, -1)]
        pygame.draw.polygon(s, col, left + right)

    ink = shade(white, -35)                              # тонкий шов на границе каждой дольки
    lw = max(1, int(r * 0.018))
    for j in range(1, n):
        pts = [(cx + bx(j, k / steps), cy + by(k / steps)) for k in range(steps + 1)]
        for a, b in zip(pts, pts[1:]):
            pygame.draw.line(s, ink, a, b, lw)
    for dy in (-0.86, 0.86):
        pygame.draw.circle(s, (250, 250, 248), (int(cx), int(cy + r * dy)), int(r * 0.14))


BALL_ITEMS = (
    ((86, 150, 60), _ball_soccer),        # трава
    ((176, 124, 72), _ball_basketball),   # паркет
    ((44, 110, 190), _ball_tennis),       # корт
    ((222, 198, 146), _ball_volleyball),  # песок
    ((168, 94, 58), _ball_baseball),      # грунт
    ((70, 140, 64), _ball_golf),          # фервей
    ((70, 164, 192), _ball_beach),        # вода
)
BALL_PALETTE: tuple[Color, ...] = tuple(c for c, _ in BALL_ITEMS)
_BALL_BY_COLOR = dict(BALL_ITEMS)


def paint_ball(s, w, h, color, rng):
    """Мяч на своей площадке: тайл — трава/паркет/корт/песок/грунт/фервей/вода,
    мяч поверх — настоящих спортивных цветов, независимо от темы. Сам мяч
    рисуется втрое крупнее и уменьшается со сглаживанием — швы и панели
    выходят плавными кривыми, а не «лесенкой» из пикселей."""
    _base_tile(s, w, h, color, 0.16, -45)
    for k in range(3):
        y = h * (0.20 + k * 0.22) + rng.uniform(-2, 2)
        pygame.draw.line(s, shade(color, -14), (w * 0.08, y), (w * 0.92, y + rng.uniform(-2, 2)), 1)
    fn = _BALL_BY_COLOR.get(tuple(color))
    if fn is None:
        return
    cx, cy, r = w / 2, (h - h // 12) / 2, w * 0.33
    pygame.draw.ellipse(s, shade(color, -35), (int(cx - r * 0.85), int(cy + r * 0.72), int(r * 1.7), int(r * 0.34)))

    def draw_it(big, bw, bh, k):
        fn(big, bw / 2, cy * k, r * k, rng)

    s.blit(_smooth(draw_it, w, h), (0, 0))



# --- Шоколад -----------------------------------------------------------
# Долька выбирает вид (как сыр у пиццы): орехи, изюм, мята, карамель —
# начинка настоящих цветов, независимо от темы.

def _choc_draw(s, w, h, color):
    """Долька как у настоящей плитки: плоская верхняя площадка и четыре
    скошенные грани вокруг. Свет сверху слева — верхняя и левая грани
    светлее, правая и нижняя темнее. Без обводки: объём дают только грани."""
    body = h - max(2, h // 12)
    pygame.draw.rect(s, shade(color, -75), (0, 0, w, h), border_radius=_radius(w, h, 0.06))   # тень под долькой
    o = max(1, int(w * 0.02))
    b = w * 0.18                                         # ширина скоса
    x0, y0, x1, y1 = o, o, w - o, body - o
    ix0, iy0, ix1, iy1 = x0 + b, y0 + b, x1 - b, y1 - b
    pygame.draw.polygon(s, shade(color, 40), ((x0, y0), (x1, y0), (ix1, iy0), (ix0, iy0)))     # верхняя грань
    pygame.draw.polygon(s, shade(color, 16), ((x0, y0), (ix0, iy0), (ix0, iy1), (x0, y1)))     # левая
    pygame.draw.polygon(s, shade(color, -24), ((x1, y0), (x1, y1), (ix1, iy1), (ix1, iy0)))    # правая
    pygame.draw.polygon(s, shade(color, -42), ((x0, y1), (ix0, iy1), (ix1, iy1), (x1, y1)))    # нижняя
    pygame.draw.rect(s, color, (ix0, iy0, ix1 - ix0, iy1 - iy0))                               # площадка
    # мягкий глянец: полоса вдоль верха площадки и косой отсвет в левом углу
    pygame.draw.rect(s, shade(color, 12), (ix0, iy0, ix1 - ix0, (iy1 - iy0) * 0.28))
    pygame.draw.polygon(s, shade(color, 26), ((ix0, iy0), (ix0 + (ix1 - ix0) * 0.42, iy0),
                                              (ix0, iy0 + (iy1 - iy0) * 0.42)))
    pygame.draw.line(s, shade(color, 70), (x0 + b * 0.3, y0 + 1), (x1 - b * 0.3, y0 + 1), max(1, int(w * 0.02)))  # блик на ребре


def _choc_tile(s, w, h, color):
    """Рисуем втрое крупнее и уменьшаем — косые грани без «лесенки»."""
    s.blit(_smooth(lambda big, bw, bh, k: _choc_draw(big, bw, bh, color), w, h), (0, 0))


CHOC_PALETTE: tuple[Color, ...] = (
    (126, 72, 42),     # молочный
    (72, 40, 26),      # тёмный
    (236, 222, 194),   # белый
    (140, 84, 50),     # молочный посветлее
    (58, 32, 22),      # горький
    (224, 206, 174),   # белый потемнее
    (112, 62, 36),     # молочный потемнее
)


def paint_chocolate(s, w, h, color, rng):
    """Плитка шоколада: рант и четыре гладкие дольки со сгибом и бликом.
    Три вида — молочный, тёмный, белый — без крошки и вкраплений."""
    _choc_tile(s, w, h, color)


PAINTERS: dict[str, Painter] = {
    "glossy": paint_glossy,
    "watermelon": paint_watermelon,
    "cake": paint_cake,
    "brick": paint_brick,
    "grass": paint_grass,
    "flag": paint_flag,
    "ice": paint_ice,
    "cookie": paint_cookie,
    "knit": paint_knit,
    "ore": paint_ore,
    "gift": paint_gift,
    "gummy": paint_gummy,
    "pizza": paint_pizza,
    "sushi": paint_sushi,
    "shell": paint_shell,
    "leaf": paint_leaf,
    "planet": paint_planet,
    "wood": paint_wood,
    "marble": paint_marble,
    "neon": paint_neon,
    "toy": paint_toy,
    "pumpkin": paint_pumpkin,
    "egg": paint_egg,
    "balloon": paint_balloon,
    "letter": paint_letter,
    "donut": paint_donut,
    "snowflake": paint_snowflake,
    "sewbutton": paint_sewbutton,
    "key": paint_key,
    "cat": paint_cat,
    "trash": paint_trash,
    "chess": paint_chess,
    "ball": paint_ball,
    "chocolate": paint_chocolate,
}

# стили, где случайный узор делает блоки разными — держим несколько вариантов
VARIANT_STYLES = {"cake": 6, "grass": 6, "ice": 4, "cookie": 6, "knit": 3, "ore": 6, "gummy": 3, "pizza": 4, "sushi": 3, "leaf": 4, "planet": 6, "wood": 4, "marble": 4, "pumpkin": 4, "egg": 6, "donut": 5, "snowflake": 4, "sewbutton": 3, "cat": 6, "ball": 4}

# ======================================================================
# blockblast/render/themes.py
# ======================================================================

"""Темы оформления. Вместо глобальных BLACK/GRID_BG/CELL_EMPTY, которые
переписывались через `global` в трёх местах, — неизменяемые объекты Theme
и один менеджер, знающий текущую тему."""

from dataclasses import dataclass, replace
from typing import Optional


Color = tuple[int, int, int]


@dataclass(frozen=True)
class Theme:
    id: str
    name: str
    style: str
    bg: Color
    board_bg: Color
    cell_empty: Color
    palette: tuple[Color, ...]
    decoration: Optional[str] = None
    text: Color = (255, 255, 255)
    accent: Color = (255, 204, 51)
    button: Color = (70, 130, 230)

    def color(self, index: int) -> Color:
        return self.palette[index % len(self.palette)]

    @property
    def bg_bottom(self) -> Color:
        return tuple(max(0, int(c * 0.78)) for c in self.bg)  # type: ignore[return-value]

    @property
    def panel(self) -> Color:
        return tuple(max(0, int(c * 0.55)) for c in self.board_bg)  # type: ignore[return-value]


_BASE_THEMES: tuple[Theme, ...] = (
    Theme("watermelon", "Арбуз", "watermelon", (116, 181, 98), (23, 51, 31), (30, 66, 41),
          ((245, 90, 86), (235, 75, 70), (250, 105, 100)), button=(214, 76, 70)),
    Theme("violet", "Фиолет", "glossy", (122, 110, 214), (43, 37, 92), (34, 29, 74),
          ((232, 68, 68), (66, 176, 226))),
    Theme("blue", "Синяя", "glossy", (108, 126, 224), (33, 40, 92), (26, 32, 74),
          ((66, 130, 226), (226, 70, 70))),
    Theme("cake", "Тортик", "cake", (181, 133, 102), (94, 61, 42), (120, 82, 58),
          ((232, 132, 140), (140, 188, 226), (188, 140, 208), (222, 108, 118)), button=(196, 104, 118)),
    Theme("brick", "Кирпич", "brick", (150, 108, 78), (66, 46, 34), (84, 60, 44),
          ((172, 80, 58),), decoration="roof", button=(150, 70, 50)),
    Theme("grass", "Трава", "grass", (92, 148, 78), (58, 42, 30), (74, 54, 38),
          ((106, 150, 62),), button=(88, 140, 58)),
    # Блоки — флаги стран: Россия, Франция, Италия, Испания, Бразилия, Китай,
    # США, Португалия, Канада, Казахстан, Беларусь. Палитра приходит из
    # painters.FLAG_PALETTE, чтобы порядок цветов и порядок флагов не разъехались.
    Theme("countries", "Страны", "flag", (38, 48, 84), (20, 26, 48), (28, 36, 62),
          FLAG_PALETTE, button=(0, 57, 166)),
    # Холодные оттенки, но разные по тону — иначе фигуры не различить.
    Theme("ice", "Лёд", "ice", (22, 42, 62), (14, 28, 44), (26, 50, 72),
          ((170, 220, 245),   # голубой
           (110, 175, 235),   # синий
           (150, 232, 225),   # бирюзовый
           (196, 200, 250),   # лавандовый
           (140, 215, 190),   # мятный
           (220, 238, 252),   # почти белый
           (90, 140, 220)),   # глубокий синий
          accent=(190, 235, 255), button=(70, 150, 210)),
    # Разное тесто, чтобы фигуры различались: на тёмном тесте шоколад белый.
    Theme("cookie", "Печенье", "cookie", (170, 138, 102), (58, 36, 26), (80, 54, 40),
          ((214, 160, 90),    # классическое золотистое
           (112, 68, 42),     # двойной шоколад
           (238, 210, 156),   # сахарное
           (170, 54, 60),     # красный бархат
           (140, 168, 88),    # матча
           (192, 124, 64),    # арахисовое
           (158, 116, 80)),   # овсяное
          accent=(255, 214, 140), button=(150, 96, 58)),
    Theme("knit", "Вязание", "knit", (96, 74, 70), (54, 40, 38), (70, 54, 50),
          ((214, 70, 70),     # красная
           (236, 188, 70),    # горчичная
           (70, 140, 90),     # лесная зелёная
           (80, 120, 190),    # джинсовая
           (232, 150, 168),   # пыльная розовая
           (150, 118, 196),   # лавандовая
           (238, 226, 200)),  # молочная
          accent=(255, 220, 150), button=(196, 78, 78)),
    # Камень у всех блоков одинаковый, различает их руда.
    Theme("ore", "Руды", "ore", (34, 36, 42), (20, 20, 24), (44, 44, 50),
          ((36, 36, 40),      # уголь
           (218, 178, 140),   # железо
           (250, 206, 60),    # золото
           (222, 40, 52),     # рубин
           (40, 200, 104),    # изумруд
           (52, 92, 222),     # сапфир
           (112, 232, 226)),  # алмаз
          accent=(250, 206, 60), button=(92, 94, 106)),
    # Упаковочная бумага разных цветов; ленту подбирает сам рисовальщик.
    Theme("gift", "Подарки", "gift", (20, 28, 64), (26, 16, 32), (56, 36, 66),
          ((210, 40, 52),     # красная
           (40, 120, 204),    # синяя
           (40, 150, 82),     # зелёная
           (150, 70, 192),    # фиолетовая
           (246, 206, 62),    # жёлтая
           (240, 240, 246),   # белая
           (240, 120, 172)),  # розовая
          accent=(250, 206, 72), button=(200, 48, 70), decoration="newyear"),
    Theme("gummy", "Мармелад", "gummy", (120, 44, 76), (60, 20, 40), (84, 34, 60),
          ((236, 62, 80), (250, 150, 40), (250, 214, 60), (96, 204, 80),
           (70, 150, 236), (170, 96, 222), (244, 120, 180)),
          accent=(255, 220, 120), button=(214, 62, 100)),
    # сыр у всех кусков один, различает их начинка (painters.PIZZA_TOPPINGS)
    Theme("pizza", "Пицца", "pizza", (132, 90, 56), (72, 46, 30), (92, 62, 42),
          PIZZA_PALETTE, accent=(255, 214, 110), button=(190, 60, 40)),
    Theme("sushi", "Суши", "sushi", (56, 44, 40), (30, 24, 22), (72, 58, 52),
          ((250, 132, 96),    # лосось
           (204, 44, 64),     # тунец
           (96, 176, 84),     # огурец
           (252, 212, 90),    # тамаго
           (178, 206, 96),    # авокадо
           (120, 76, 44),     # угорь
           (255, 110, 30)),   # икра
          accent=(250, 212, 120), button=(196, 56, 56)),
    Theme("ocean", "Океан", "shell", (20, 90, 140), (10, 44, 76), (22, 70, 108),
          ((250, 180, 190), (252, 208, 160), (246, 236, 214), (206, 180, 236),
           (250, 130, 110), (130, 220, 206), (240, 206, 120)),
          accent=(170, 240, 255), button=(30, 130, 180), decoration="ocean"),
    Theme("autumn", "Осень", "leaf", (112, 70, 42), (54, 34, 22), (74, 50, 34),
          ((220, 60, 40), (240, 140, 40), (250, 200, 60), (160, 90, 40),
           (180, 30, 50), (220, 170, 50), (130, 140, 50)),
          accent=(255, 200, 90), button=(196, 90, 40), decoration="autumn"),
    Theme("space", "Космос", "planet", (12, 12, 34), (8, 8, 20), (22, 22, 48),
          ((214, 90, 60), (70, 140, 230), (220, 180, 120), (90, 214, 220),
           (240, 214, 90), (160, 100, 220), (100, 200, 110)),
          accent=(200, 220, 255), button=(80, 70, 180), decoration="space"),
    Theme("wood", "Дерево", "wood", (120, 84, 54), (62, 42, 28), (84, 60, 42),
          ((232, 204, 154),   # сосна
           (204, 152, 92),    # дуб
           (134, 88, 56),     # орех
           (192, 104, 72),    # вишня
           (242, 228, 204),   # берёза
           (156, 64, 48),     # красное дерево
           (182, 172, 156)),  # ясень
          accent=(255, 214, 150), button=(150, 96, 56)),
    Theme("marble", "Мрамор", "marble", (74, 70, 78), (36, 34, 40), (54, 52, 60),
          ((242, 242, 244), (44, 44, 50), (74, 134, 104), (232, 172, 172),
           (92, 124, 176), (222, 202, 162), (152, 152, 160)),
          accent=(230, 210, 150), button=(110, 104, 120)),
    Theme("neon", "Неон", "neon", (10, 8, 20), (4, 4, 10), (18, 16, 32),
          ((255, 60, 200), (40, 230, 255), (140, 255, 60), (255, 236, 60),
           (170, 90, 255), (255, 140, 40), (255, 50, 70)),
          accent=(40, 230, 255), button=(200, 40, 170)),
    Theme("toy", "Конструктор", "toy", (70, 110, 170), (40, 60, 96), (56, 84, 126),
          ((222, 36, 40), (30, 96, 204), (250, 204, 30), (40, 160, 70),
           (240, 240, 240), (250, 130, 30), (100, 190, 236)),
          accent=(250, 204, 30), button=(222, 36, 40)),
    Theme("halloween", "Хэллоуин", "pumpkin", (40, 20, 56), (20, 10, 28), (46, 26, 60),
          ((248, 130, 30), (120, 170, 60), (236, 230, 214), (150, 80, 200),
           (230, 70, 40), (250, 200, 60), (120, 130, 150)),
          accent=(255, 170, 40), button=(220, 110, 30), decoration="halloween"),
    Theme("easter", "Пасха", "egg", (150, 200, 120), (84, 120, 70), (108, 150, 90),
          ((246, 150, 180), (120, 170, 240), (250, 214, 90), (130, 200, 120),
           (190, 150, 230), (250, 170, 120), (110, 210, 190)),
          accent=(255, 240, 160), button=(214, 110, 150), decoration="easter"),
    Theme("balloons", "Шарики", "balloon", (110, 180, 236), (52, 96, 156), (74, 124, 184),
          ((236, 60, 64),     # красный
           (250, 150, 40),    # оранжевый
           (250, 210, 50),    # жёлтый
           (70, 184, 90),     # зелёный
           (60, 130, 230),    # синий
           (160, 90, 220),    # фиолетовый
           (246, 110, 176)),  # розовый
          accent=(255, 230, 120), button=(236, 80, 90), decoration="sky"),
    # 26 цветов = 26 букв (painters.ALPHABET_PALETTE): буква едет с кубиком
    Theme("alphabet", "Алфавит", "letter", (46, 80, 60), (26, 46, 36), (58, 96, 74),
          ALPHABET_PALETTE, accent=(250, 240, 200), button=(122, 82, 48), decoration="chalkboard"),
    Theme("donuts", "Пончики", "donut", (236, 170, 186), (120, 70, 80), (150, 96, 106),
          ((246, 140, 180),   # розовая глазурь
           (116, 70, 44),     # шоколадная
           (244, 232, 206),   # ванильная
           (120, 180, 240),   # голубая
           (140, 220, 180),   # мятная
           (250, 212, 90),    # лимонная
           (180, 130, 222)),  # черничная
          accent=(255, 236, 170), button=(214, 100, 140), decoration="bakery"),
    Theme("snow", "Снег", "snowflake", (40, 70, 120), (22, 38, 70), (40, 62, 100),
          ((150, 200, 240), (90, 150, 220), (170, 170, 230), (100, 200, 210),
           (130, 170, 250), (170, 190, 210), (70, 110, 200)),
          accent=(220, 240, 255), button=(70, 130, 210), decoration="winter"),
    Theme("buttons", "Пуговицы", "sewbutton", (170, 140, 110), (92, 70, 52), (120, 96, 74),
          ((214, 60, 60), (60, 110, 200), (240, 196, 50), (70, 160, 90),
           (240, 130, 170), (140, 96, 64), (60, 60, 70)),
          accent=(255, 230, 170), button=(160, 70, 60), decoration="sewing"),
    # на клавишах буквы кубиков — едут вместе с кубиком, как в «Алфавите»
    Theme("keyboard", "Клавиатура", "key", (54, 60, 72), (28, 30, 38), (44, 48, 58),
          ((232, 232, 236), (74, 76, 86), (226, 214, 190), (90, 140, 222),
           (222, 84, 84), (150, 214, 190), (172, 142, 222)),
          accent=(150, 214, 190), button=(90, 140, 222), decoration="desk"),
    Theme("cats", "Котики", "cat", (236, 206, 170), (120, 90, 70), (150, 118, 94),
          ((244, 152, 62),    # рыжий
           (152, 152, 162),   # серый
           (54, 52, 60),      # чёрный
           (244, 242, 236),   # белый
           (236, 210, 170),   # кремовый
           (150, 100, 70),    # шоколадный
           (182, 172, 204)),  # голубой-лиловый
          accent=(255, 220, 170), button=(210, 120, 60), decoration="windowsill"),
    # плитки — цвета контейнеров раздельного сбора; предмет едет с кубиком
    Theme("trash", "Мусор", "trash", (150, 92, 76), (46, 46, 50), (64, 64, 70),
          ((70, 150, 80),     # стекло
           (60, 110, 190),    # бумага
           (230, 190, 50),    # пластик
           (130, 134, 140),   # смешанный
           (130, 90, 60),     # органика
           (230, 120, 50),    # металл
           (200, 60, 60)),    # опасные
          accent=(230, 190, 50), button=(70, 150, 80), decoration="junkyard"),
    # фигура едет с кубиком; белая на тёмной клетке, чёрная на светлой
    Theme("chess", "Шахматы", "chess", (96, 66, 44), (46, 32, 22), (70, 50, 34),
          ((238, 216, 170),   # клён
           (181, 136, 99),    # орех
           (118, 150, 86),    # турнирная зелёная
           (238, 238, 210),   # кремовая
           (100, 130, 170),   # синяя
           (156, 116, 168),   # фиолетовая
           (140, 140, 146)),  # серый мрамор
          accent=(238, 216, 170), button=(181, 136, 99), decoration="chess"),
    # площадка выбирает мяч (painters.BALL_ITEMS); цвета мячей настоящие
    Theme("balls", "Мячи", "ball", (46, 92, 46), (22, 46, 26), (62, 108, 62),
          BALL_PALETTE, accent=(250, 200, 60), button=(70, 140, 64), decoration="stadium"),
    # начинка выбирает цвет (painters.CHOC_ITEMS): орехи, изюм, мята, карамель
    Theme("chocolate", "Шоколад", "chocolate", (112, 78, 50), (60, 40, 26), (86, 58, 36),
          CHOC_PALETTE, accent=(236, 222, 190), button=(92, 58, 34), decoration="foil"),
    Theme("classic", "Классика", "glossy", (18, 18, 24), (40, 40, 55), (55, 55, 75),
          ((230, 70, 70), (70, 170, 230), (90, 210, 120), (240, 170, 60),
           (180, 100, 230), (240, 220, 80), (240, 120, 180))),
)
# Фоны тем, у которых их раньше не было. Отдельной таблицей, чтобы не
# переписывать каждое объявление выше; «Кирпич» оставляет своё украшение
# (крышу над полем) — фон к нему привязан под тем же именем "roof".
_BACKDROP_FOR = {
    "watermelon": "melon", "violet": "magic", "blue": "rays", "cake": "party",
    "grass": "meadow", "countries": "globe", "ice": "frozen", "cookie": "kitchen",
    "knit": "yarn", "ore": "mine", "gummy": "candy", "pizza": "pizzeria",
    "sushi": "bamboo", "wood": "forest", "marble": "palace", "neon": "neoncity",
    "toy": "baseplate", "classic": "dots",
}
THEMES: tuple[Theme, ...] = tuple(
    replace(t, decoration=_BACKDROP_FOR[t.id]) if t.id in _BACKDROP_FOR and not t.decoration else t
    for t in _BASE_THEMES)

THEME_IDS = tuple(t.id for t in THEMES)


class ThemeManager:
    def __init__(self, setting: str):
        self.auto = setting == "auto"
        self.index = THEME_IDS.index(setting) if setting in THEME_IDS else 0
        self._clears = 0

    @property
    def current(self) -> Theme:
        return THEMES[self.index]

    @property
    def setting(self) -> str:
        return "auto" if self.auto else self.current.id

    def set(self, setting: str) -> None:
        if setting == "auto":
            self.auto = True
            self._clears = 0
        elif setting in THEME_IDS:
            self.auto = False
            self.index = THEME_IDS.index(setting)

    def next(self) -> None:
        self.index = (self.index + 1) % len(THEMES)

    def on_clear(self) -> bool:
        """Для режима «Авто»: смена темы каждые N очисток. True — тема сменилась."""
        if not self.auto:
            return False
        self._clears += 1
        if self._clears >= AUTO_THEME_EVERY:
            self._clears = 0
            self.next()
            return True
        return False

# ======================================================================
# blockblast/render/textures.py
# ======================================================================

"""Все «дорогие» поверхности создаются здесь и живут в LRU-кэше."""

import math
import random

import pygame


SCALE_STEPS = 10  # анимация уменьшения использует 10 заранее отмасштабированных кадров


def block_gap(cell: int) -> int:
    return max(1, cell // 26)


def cell_variant(theme: Theme, r: int, c: int, label=None) -> int:
    """Вариант текстуры кубика. Для алфавита это номер буквы кубика
    (−1 — буквы нет, например старое сохранение: тогда буква из цвета)."""
    if theme.style in LABELED_STYLES:
        return label if label is not None else -1
    return block_variant(theme, r, c)


# стили, у которых на кубике своя буква, едущая вместе с ним
LABELED_STYLES = ("letter", "key", "trash", "chess")


def block_variant(theme: Theme, r: int, c: int) -> int:
    n = VARIANT_STYLES.get(theme.style, 1)
    return (r * 13 + c * 7) % n if n > 1 else 0


def block(theme: Theme, color_index: int, size: int, variant: int = 0) -> pygame.Surface:
    color = theme.color(color_index)
    size = max(4, int(size))
    key = ("block", theme.style, color, size, variant)

    def make() -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        rng = random.Random(variant * 9973 + 17)
        rng.variant = variant            # алфавиту нужен сам номер — это буква кубика
        PAINTERS[theme.style](surf, size, size, color, rng)
        return surf.convert_alpha()

    return texture_cache.get(key, make)


ALPHA_STEP = 32  # квантование прозрачности, чтобы кэш не разрастался


def block_ghost(theme: Theme, color_index: int, size: int, variant: int, alpha: int) -> pygame.Surface:
    """Полупрозрачный блок с уже применённой прозрачностью.

    set_alpha() поверх попиксительной альфы включает самый медленный путь блита
    в SDL, поэтому прозрачность вжигаем один раз в текстуру и кэшируем."""
    alpha = max(ALPHA_STEP, min(255, round(alpha / ALPHA_STEP) * ALPHA_STEP))
    if alpha >= 255:
        return block(theme, color_index, size, variant)
    key = ("ghost", theme.style, theme.color(color_index), int(size), variant, alpha)

    def make() -> pygame.Surface:
        surf = block(theme, color_index, size, variant).copy()
        mask = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        mask.fill((255, 255, 255, alpha))
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return surf.convert_alpha()

    return texture_cache.get(key, make)


def piece_with_shadow(theme: Theme, shape: Shape, color_index: int, cell: int,
                      offset: tuple[int, int], labels: tuple = ()) -> pygame.Surface:
    """Перетаскиваемая фигура и её тень одной текстурой — один блит вместо двух.
    С буквами кубиков: иначе в руке у «Алфавита» и «Клавиатуры» были чужие буквы."""
    labels = tuple(labels) if theme.style in LABELED_STYLES else ()
    key = ("piece_sh", theme.style, theme.color(color_index), shape.cells, int(cell), offset, labels)

    def make() -> pygame.Surface:
        body = piece(theme, shape, color_index, cell, labels=labels)
        w, h = body.get_size()
        surf = pygame.Surface((w + abs(offset[0]), h + abs(offset[1])), pygame.SRCALPHA)
        surf.blit(piece_shadow(shape, cell), (max(0, offset[0]), max(0, offset[1])))
        surf.blit(body, (max(0, -offset[0]), max(0, -offset[1])))
        return surf.convert_alpha()

    return texture_cache.get(key, make)


def block_scaled(theme: Theme, color_index: int, size: int, variant: int, scale: float) -> pygame.Surface:
    """Квантованное масштабирование: вместо smoothscale каждый кадр — 10 кэшированных шагов."""
    step = max(1, min(SCALE_STEPS, round(scale * SCALE_STEPS)))
    if step == SCALE_STEPS:
        return block(theme, color_index, size, variant)
    key = ("block_s", theme.style, theme.color(color_index), int(size), variant, step)

    def make() -> pygame.Surface:
        base = block(theme, color_index, size, variant)
        px = max(1, int(size * step / SCALE_STEPS))
        return pygame.transform.smoothscale(base, (px, px))

    return texture_cache.get(key, make)


def piece(theme: Theme, shape: Shape, color_index: int, cell: int, dimmed: bool = False,
          labels: tuple = ()) -> pygame.Surface:
    cell = max(4, int(cell))
    labels = tuple(labels) if theme.style in LABELED_STYLES else ()   # остальным темам буквы не важны
    key = ("piece", theme.style, theme.color(color_index), shape.cells, cell, dimmed, labels)

    def make() -> pygame.Surface:
        gap = block_gap(cell)
        surf = pygame.Surface((shape.cols * cell, shape.rows * cell), pygame.SRCALPHA)
        for k, (r, c) in enumerate(shape.cells):
            label = labels[k] if k < len(labels) else None
            surf.blit(block(theme, color_index, cell - 2 * gap, cell_variant(theme, r, c, label)),
                      (c * cell + gap, r * cell + gap))
        if dimmed:  # фигура, которой некуда встать: серая и полупрозрачная
            gray = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            gray.fill((120, 120, 120, 150))
            surf.blit(gray, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return surf.convert_alpha()

    return texture_cache.get(key, make)


def piece_ghost(theme: Theme, shape: Shape, color_index: int, cell: int, alpha: int) -> pygame.Surface:
    alpha = max(ALPHA_STEP, min(255, round(alpha / ALPHA_STEP) * ALPHA_STEP))
    key = ("piece_ghost", theme.style, theme.color(color_index), shape.cells, int(cell), alpha)

    def make() -> pygame.Surface:
        surf = piece(theme, shape, color_index, cell).copy()
        mask = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        mask.fill((255, 255, 255, alpha))
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return surf.convert_alpha()

    return texture_cache.get(key, make)


def piece_shadow(shape: Shape, cell: int) -> pygame.Surface:
    key = ("shadow", shape.cells, int(cell))

    def make() -> pygame.Surface:
        gap = block_gap(cell)
        surf = pygame.Surface((shape.cols * cell, shape.rows * cell), pygame.SRCALPHA)
        for r, c in shape.cells:
            pygame.draw.rect(surf, (0, 0, 0, 70), (c * cell + gap, r * cell + gap, cell - 2 * gap, cell - 2 * gap),
                             border_radius=max(2, cell // 8))
        return surf

    return texture_cache.get(key, make)


def gradient(size: tuple[int, int], top: tuple, bottom: tuple) -> pygame.Surface:
    key = ("gradient", size, top, bottom)

    def make() -> pygame.Surface:
        w, h = size
        strip = pygame.Surface((1, max(2, h)))
        for y in range(h):
            t = y / max(1, h - 1)
            strip.set_at((0, y), [int(a + (b - a) * t) for a, b in zip(top, bottom)])
        return pygame.transform.scale(strip, (w, h)).convert()

    return texture_cache.get(key, make)


def flat_background(theme, simple: bool) -> bool:
    """Рисовать ли сплошной цвет вместо фона.

    На «Низком» градиент заменяем заливкой — она дешевле. Но фон с
    украшениями — часть темы: без него «Подарки» теряют Новый год. Он
    рисуется в кэшированный слой, а не каждый кадр, так что оставляем его."""
    return simple and not theme.decoration


def draw_background(surf: pygame.Surface, theme, simple: bool = False) -> None:
    """Фон кадра. fill() заметно быстрее полноэкранного blit, поэтому в «низком»
    качестве рисуем сплошной цвет вместо градиента — кроме тем с украшениями."""
    if flat_background(theme, simple):
        surf.fill(theme.bg)
    else:
        surf.blit(background(surf.get_size(), theme), (0, 0))


def background(size: tuple[int, int], theme) -> pygame.Surface:
    """Полноэкранный фон темы. Один источник для экрана и для подложки
    под скруглёнными углами поля — иначе по углам проступит другой фон."""
    if theme.decoration == "newyear":
        return newyear_background(size, theme)
    painter = BACKDROPS.get(theme.decoration)
    if painter is not None:
        return _backdrop(size, theme, painter)
    return gradient(size, theme.bg, theme.bg_bottom)


def _backdrop(size, theme, painter) -> pygame.Surface:
    """Фон с украшениями: рисуется один раз на размер экрана и кэшируется,
    поэтому кадр стоит столько же, сколько обычный градиент."""
    width, height = size
    key = ("backdrop", theme.decoration, width, height, theme.id)

    def make() -> pygame.Surface:
        surf = gradient(size, theme.bg, theme.bg_bottom).copy()
        rng = random.Random(width * 7 + height * 13 + len(theme.decoration))
        painter(surf, width, height, max(1.0, min(width, height) / 400), rng, theme)
        return surf.convert()

    return texture_cache.get(key, make)


def _mix(a, b, k):
    return tuple(int(a[i] * (1 - k) + b[i] * k) for i in range(3))


def _soft_blob(surf, cx, cy, radius, color, base, steps=8):
    """Мягкое пятно без прозрачности: круги от большого к малому,
    цвет всё ближе к нужному — туманность или отсвет."""
    for i in range(steps):
        k = (i + 1) / steps
        pygame.draw.circle(surf, _mix(base, color, k * 0.55), (int(cx), int(cy)), max(1, int(radius * (1 - i / steps))))


def _space_backdrop(surf, w, h, u, rng, theme):
    for col, fx, fy, fr in (((120, 60, 170), 0.2, 0.18, 0.30), ((40, 90, 170), 0.82, 0.55, 0.34),
                            ((170, 60, 120), 0.35, 0.92, 0.26)):
        _soft_blob(surf, w * fx, h * fy, min(w, h) * fr, col, _mix(theme.bg, theme.bg_bottom, fy))
    for _ in range(int(160 * w * h / (480 * 860))):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        t = rng.randint(170, 255)
        pygame.draw.circle(surf, (t, t, min(255, t + 20)), (int(x), int(y)), 1 if rng.random() < 0.85 else 2)
    for _ in range(6):                                   # яркие звёзды-крестики
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), u * rng.uniform(4, 7)
        pygame.draw.line(surf, (240, 240, 255), (x - r, y), (x + r, y), 1)
        pygame.draw.line(surf, (240, 240, 255), (x, y - r), (x, y + r), 1)


def _ocean_backdrop(surf, w, h, u, rng, theme):
    ray = _mix(theme.bg, (140, 210, 240), 0.18)
    for fx in (0.12, 0.38, 0.66, 0.88):                  # лучи сквозь воду
        x = w * fx
        pygame.draw.polygon(surf, ray, ((x - w * 0.03, 0), (x + w * 0.05, 0),
                                        (x + w * 0.20, h * 0.7), (x + w * 0.06, h * 0.7)))
    sand = (206, 186, 136)
    pts = [(0, h)] + [(w * i / 30, h * (0.93 + 0.012 * math.sin(i * 0.8))) for i in range(31)] + [(w, h)]
    pygame.draw.polygon(surf, sand, pts)
    for fx in (0.05, 0.12, 0.86, 0.94):                  # водоросли
        x, y = w * fx, h * 0.95
        for i in range(10):
            nx = x + math.sin(i * 0.9 + fx * 9) * u * 4
            ny = y - h * 0.018
            pygame.draw.line(surf, (40, 130, 80), (x, y), (nx, ny), max(2, int(u * 3)))
            x, y = nx, ny
    # пузыри не рисуем в фон: они живые, всплывают и лопаются (effects.Bubbles)


def _halloween_backdrop(surf, w, h, u, rng, theme):
    mx, my, mr = w * 0.80, h * 0.10, min(w, h) * 0.12
    _soft_blob(surf, mx, my, mr * 2.2, (120, 90, 150), theme.bg)
    pygame.draw.circle(surf, (246, 238, 196), (int(mx), int(my)), int(mr))
    for dx, dy, rr in ((-0.3, -0.2, 0.18), (0.25, 0.15, 0.14), (-0.1, 0.35, 0.10)):
        pygame.draw.circle(surf, (222, 212, 170), (int(mx + dx * mr), int(my + dy * mr)), max(1, int(mr * rr)))
    for _ in range(7):                                   # летучие мыши
        x, y, s_ = rng.uniform(0.05, 0.95) * w, rng.uniform(0.04, 0.30) * h, u * rng.uniform(5, 9)
        bat = ((x, y), (x - s_ * 0.5, y - s_ * 0.4), (x - s_ * 0.9, y - s_ * 0.1), (x - s_ * 1.4, y - s_ * 0.3),
               (x - s_ * 1.1, y + s_ * 0.2), (x - s_ * 0.5, y + s_ * 0.05), (x, y + s_ * 0.25),
               (x + s_ * 0.5, y + s_ * 0.05), (x + s_ * 1.1, y + s_ * 0.2), (x + s_ * 1.4, y - s_ * 0.3),
               (x + s_ * 0.9, y - s_ * 0.1), (x + s_ * 0.5, y - s_ * 0.4))
        pygame.draw.polygon(surf, (16, 10, 20), bat)
    pts = [(0, h)] + [(w * i / 20, h * (0.92 + 0.03 * math.sin(i * 0.7 + 1))) for i in range(21)] + [(w, h)]
    pygame.draw.polygon(surf, (18, 12, 24), pts)        # холмы
    for fx in (0.08, 0.16, 0.24, 0.76, 0.84, 0.92):      # надгробия
        x, y = w * fx, h * (0.92 + 0.03 * math.sin(fx * 20 * 0.7 + 1))
        pygame.draw.rect(surf, (60, 56, 70), (int(x - u * 6), int(y - u * 14), int(u * 12), int(u * 16)),
                         border_radius=int(u * 6))


def _leaf_shape(cx, cy, r, tilt):
    ca, sa = math.cos(tilt), math.sin(tilt)
    def rot(x, y):
        return (cx + (x * ca - y * sa) * r, cy + (x * sa + y * ca) * r)
    return [rot(x, y) for x, y in LEAF_HALF] + [rot(-x, y) for x, y in reversed(LEAF_HALF[:-1])]


def _autumn_backdrop(surf, w, h, u, rng, theme):
    colors = ((220, 70, 40), (240, 150, 40), (240, 200, 70), (170, 90, 40))
    for _ in range(int(28 * w * h / (480 * 860))):       # падающие листья
        pygame.draw.polygon(surf, _mix(rng.choice(colors), theme.bg, 0.35),
                            _leaf_shape(rng.uniform(0, w), rng.uniform(0, h * 0.85), u * rng.uniform(6, 11),
                                        rng.uniform(0, math.tau)))
    for _ in range(int(60 * w / 480)):                   # куча листвы внизу
        pygame.draw.polygon(surf, rng.choice(colors),
                            _leaf_shape(rng.uniform(0, w), h * rng.uniform(0.95, 1.0), u * rng.uniform(7, 12),
                                        rng.uniform(0, math.tau)))


def _easter_backdrop(surf, w, h, u, rng, theme):
    grass = (80, 150, 70)
    for i in range(int(w / (3 * u))):                    # трава
        x = i * 3 * u + rng.uniform(-1, 1)
        top = h * rng.uniform(0.90, 0.94)
        pygame.draw.line(surf, _mix(grass, (130, 190, 90), rng.random()), (x, h), (x + rng.uniform(-4, 4) * u, top),
                         max(1, int(u * 2)))
    for _ in range(int(14 * w / 480)):                   # цветочки
        x, y, r = rng.uniform(0, w), h * rng.uniform(0.91, 0.97), u * rng.uniform(4, 6)
        petal = rng.choice(((250, 250, 250), (250, 200, 220), (250, 230, 120), (190, 170, 240)))
        for k in range(5):
            a = k * math.tau / 5
            pygame.draw.circle(surf, petal, (int(x + math.cos(a) * r), int(y + math.sin(a) * r)), int(r * 0.7))
        pygame.draw.circle(surf, (250, 200, 60), (int(x), int(y)), max(1, int(r * 0.55)))
    for _ in range(int(20 * w * h / (480 * 860))):       # пыльца в воздухе
        pygame.draw.circle(surf, (250, 250, 220), (int(rng.uniform(0, w)), int(rng.uniform(0, h * 0.85))),
                           max(1, int(u * 1.5)))


def _sky_backdrop(surf, w, h, u, rng, theme):
    """Дневное небо: солнце, облака и далёкие шарики — бледные и мелкие,
    чтобы их не путали с блоками."""
    sx, sy, sr = w * 0.84, h * 0.08, min(w, h) * 0.08
    _soft_blob(surf, sx, sy, sr * 2.4, (255, 244, 190), theme.bg)
    pygame.draw.circle(surf, (255, 236, 150), (int(sx), int(sy)), int(sr))

    def cloud(cx, cy, size):
        for dx, dy, r in ((-0.9, 0.15, 0.55), (-0.35, -0.15, 0.75), (0.35, -0.05, 0.65),
                          (0.9, 0.2, 0.5), (0.0, 0.25, 0.6)):
            pygame.draw.circle(surf, (238, 246, 252), (int(cx + dx * size), int(cy + dy * size)), int(r * size))
        pygame.draw.rect(surf, (238, 246, 252), (int(cx - size * 0.9), int(cy + size * 0.1),
                                                 int(size * 1.8), int(size * 0.55)))
    for fx, fy, fs in ((0.18, 0.06, 18), (0.62, 0.17, 14), (0.10, 0.86, 16), (0.78, 0.93, 20), (0.45, 0.97, 13)):
        cloud(w * fx, h * fy, u * fs)

    # шарики на фоне живые — они в effects.Bubbles (стиль «balloon»)

def _chalkboard_backdrop(surf, w, h, u, rng, theme):
    """Школьная доска: меловые разводы, надписи мелом, деревянная рамка
    и полочка с мелками внизу. Надписи бледные — это фон, а не текст игры."""
    chalk = (238, 236, 222)
    for _ in range(int(60 * w * h / (480 * 860))):       # разводы от стёртого мела
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        ln, a = u * rng.uniform(20, 70), rng.uniform(-0.4, 0.4)
        pygame.draw.line(surf, _mix(theme.bg, chalk, rng.uniform(0.05, 0.11)),
                         (x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln), max(1, int(u * rng.uniform(2, 6))))
    font_big = pygame.font.Font(None, max(12, int(u * 30)))
    font_mid = pygame.font.Font(None, max(10, int(u * 22)))
    for text, font, fx, fy in (("ABC", font_big, 0.06, 0.125), ("Hello!", font_mid, 0.62, 0.14),
                               ("2 + 2 = 4", font_mid, 0.08, 0.86), ("a b c d", font_mid, 0.60, 0.87)):
        glyphs = font.render(text, True, _mix(chalk, theme.bg, 0.45))
        surf.blit(glyphs, (int(w * fx), int(h * fy)))
    # рамка из дерева
    wood, wood_lit = (122, 82, 48), (158, 112, 70)
    b = max(4, int(u * 8))
    for rect in ((0, 0, w, b), (0, h - b, w, b), (0, 0, b, h), (w - b, 0, b, h)):
        pygame.draw.rect(surf, wood, rect)
    pygame.draw.rect(surf, wood_lit, (b, b, w - 2 * b, h - 2 * b), max(1, int(u * 1.5)))
    # полочка с мелками
    shelf_y = h - b - int(u * 10)
    pygame.draw.rect(surf, wood, (b, shelf_y, w - 2 * b, int(u * 10)))
    pygame.draw.line(surf, wood_lit, (b, shelf_y), (w - b, shelf_y), max(1, int(u * 1.5)))
    for fx, col in ((0.18, (246, 246, 240)), (0.26, (250, 226, 120)), (0.70, (246, 180, 196)), (0.78, (170, 210, 246))):
        pygame.draw.rect(surf, col, (int(w * fx), shelf_y - int(u * 4), int(u * 22), int(u * 5)),
                         border_radius=max(1, int(u * 2)))


def _bakery_backdrop(surf, w, h, u, rng, theme):
    """Кондитерская: обои в полоску, полосатый навес поверху, посыпка в воздухе."""
    stripe = max(6, int(u * 18))
    light = _mix(theme.bg, (255, 255, 255), 0.22)
    for i, x in enumerate(range(0, w, stripe)):
        if i % 2:
            pygame.draw.rect(surf, light, (x, 0, stripe, h))
    aw = max(10, int(u * 26))                            # навес с фестонами
    for i, x in enumerate(range(0, w + aw, aw)):
        col = (236, 90, 130) if i % 2 == 0 else (255, 246, 240)
        pygame.draw.rect(surf, col, (x, 0, aw, int(u * 16)))
        pygame.draw.circle(surf, col, (x + aw // 2, int(u * 16)), aw // 2)
    for _ in range(int(40 * w * h / (480 * 860))):
        x, y = rng.uniform(0, w), rng.uniform(h * 0.08, h)
        t = rng.uniform(0, math.pi)
        dx, dy = math.cos(t) * u * 4, math.sin(t) * u * 4
        col = _mix(rng.choice(((250, 90, 110), (90, 170, 250), (250, 220, 80), (120, 210, 120))), theme.bg, 0.35)
        pygame.draw.line(surf, col, (x - dx, y - dy), (x + dx, y + dy), max(2, int(u * 2)))


def _winter_backdrop(surf, w, h, u, rng, theme):
    """Зимний вечер: луна, домики с окошками, сугробы. Снег падает живой (effects.Bubbles)."""
    _soft_blob(surf, w * 0.82, h * 0.09, min(w, h) * 0.14, (200, 210, 240), theme.bg)
    pygame.draw.circle(surf, (244, 244, 230), (int(w * 0.82), int(h * 0.09)), int(min(w, h) * 0.06))
    for _ in range(int(50 * w * h / (480 * 860))):       # далёкие неподвижные снежинки
        pygame.draw.circle(surf, _mix(theme.bg, (255, 255, 255), rng.uniform(0.3, 0.7)),
                           (int(rng.uniform(0, w)), int(rng.uniform(0, h * 0.9))), 1)
    base = h * 0.95
    for fx, fw, fh in ((0.02, 0.16, 0.07), (0.20, 0.12, 0.05), (0.70, 0.13, 0.06), (0.85, 0.15, 0.08)):
        x, bw, bh = w * fx, w * fw, h * fh
        pygame.draw.rect(surf, (36, 40, 60), (int(x), int(base - bh), int(bw), int(bh)))
        pygame.draw.polygon(surf, (30, 32, 50), ((x - bw * 0.1, base - bh), (x + bw / 2, base - bh - bw * 0.45),
                                                 (x + bw * 1.1, base - bh)))
        pygame.draw.polygon(surf, (236, 242, 250), ((x - bw * 0.1, base - bh), (x + bw / 2, base - bh - bw * 0.45),
                                                    (x + bw / 2, base - bh - bw * 0.30), (x, base - bh + 2)))
        for k in range(2):
            pygame.draw.rect(surf, (250, 210, 110), (int(x + bw * (0.2 + 0.4 * k)), int(base - bh * 0.7),
                                                     max(3, int(bw * 0.18)), max(3, int(bh * 0.3))))
    pts = [(0, h)] + [(w * i / 30, h * (0.945 + 0.012 * math.sin(i * 0.9))) for i in range(31)] + [(w, h)]
    pygame.draw.polygon(surf, (232, 240, 250), pts)


def _sewing_backdrop(surf, w, h, u, rng, theme):
    """Швейный стол: переплетение ткани, строчки, булавки и сантиметр поверху."""
    weave = _mix(theme.bg, (0, 0, 0), 0.08)
    step = max(3, int(u * 5))
    for y in range(0, h, step):
        pygame.draw.line(surf, weave, (0, y), (w, y), 1)
    for x in range(0, w, step * 2):
        pygame.draw.line(surf, _mix(theme.bg, (255, 255, 255), 0.06), (x, 0), (x, h), 1)
    for fy in (0.16, 0.88):                              # строчки пунктиром
        y = h * fy
        for x in range(int(u * 10), w, int(u * 14)):
            pygame.draw.line(surf, (250, 246, 236), (x, y), (x + u * 7, y), max(1, int(u * 1.5)))
    tape_h = int(u * 14)                                  # сантиметр
    pygame.draw.rect(surf, (246, 214, 90), (0, int(h * 0.06), w, tape_h))
    font = pygame.font.Font(None, max(10, int(u * 12)))
    for i, x in enumerate(range(int(u * 6), w, int(u * 8))):
        long = i % 5 == 0
        pygame.draw.line(surf, (60, 50, 30), (x, int(h * 0.06)), (x, int(h * 0.06) + (tape_h * 0.55 if long else tape_h * 0.3)), 1)
        if i % 10 == 0 and i:
            surf.blit(font.render(str(i // 10), True, (60, 50, 30)), (x + 2, int(h * 0.06) + tape_h * 0.45))
    for _ in range(5):                                   # булавки
        x, y = rng.uniform(0.05, 0.95) * w, rng.choice((rng.uniform(0.18, 0.24), rng.uniform(0.9, 0.97))) * h
        a = rng.uniform(-0.8, 0.8); ln = u * 22
        pygame.draw.line(surf, (190, 196, 206), (x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln), max(1, int(u)))
        pygame.draw.circle(surf, rng.choice(((220, 60, 70), (60, 120, 220), (240, 200, 60))), (int(x), int(y)), int(u * 3.5))


def _desk_backdrop(surf, w, h, u, rng, theme):
    """Стол программиста: тёмное дерево, кружка кофе, стикер и карандаш."""
    for _ in range(int(40 * h / 860)):                   # волокна дерева
        y = rng.uniform(0, h)
        pygame.draw.line(surf, _mix(theme.bg, (0, 0, 0), rng.uniform(0.08, 0.2)), (0, y),
                         (w, y + rng.uniform(-6, 6) * u), 1)
    mx, my, mr = w * 0.86, h * 0.16, u * 18              # кружка сверху
    pygame.draw.circle(surf, (230, 230, 236), (int(mx), int(my)), int(mr))
    pygame.draw.circle(surf, (94, 60, 40), (int(mx), int(my)), int(mr * 0.78))
    pygame.draw.circle(surf, (130, 90, 60), (int(mx - mr * 0.2), int(my - mr * 0.2)), int(mr * 0.25))
    pygame.draw.rect(surf, (230, 230, 236), (int(mx + mr * 0.85), int(my - mr * 0.25), int(mr * 0.5), int(mr * 0.5)),
                     max(1, int(u * 2)), border_radius=int(u * 3))
    nx, ny, ns = w * 0.05, h * 0.12, u * 40              # стикер
    pygame.draw.rect(surf, (240, 214, 90), (int(nx), int(ny), int(ns), int(ns)))
    font = pygame.font.Font(None, max(10, int(u * 13)))
    surf.blit(font.render("TODO", True, (90, 70, 30)), (int(nx + u * 5), int(ny + u * 5)))
    for k in range(3):
        pygame.draw.line(surf, (190, 160, 70), (nx + u * 5, ny + u * (18 + k * 7)), (nx + ns - u * 6, ny + u * (18 + k * 7)), 1)
    px, py = w * 0.12, h * 0.93                          # карандаш
    pygame.draw.polygon(surf, (240, 190, 60), ((px, py), (px + u * 70, py - u * 10), (px + u * 72, py - u * 4),
                                                (px + u * 2, py + u * 6)))
    pygame.draw.polygon(surf, (236, 210, 170), ((px + u * 70, py - u * 10), (px + u * 82, py - u * 9),
                                                 (px + u * 72, py - u * 4)))


def _windowsill_backdrop(surf, w, h, u, rng, theme):
    """Подоконник: окно с небом поверху, цветы в горшках внизу, следы лапок на стене."""
    wx, wy, ww, wh = w * 0.18, h * 0.02, w * 0.64, h * 0.10
    pygame.draw.rect(surf, (150, 206, 244), (int(wx), int(wy), int(ww), int(wh)))
    pygame.draw.circle(surf, (250, 250, 252), (int(wx + ww * 0.3), int(wy + wh * 0.55)), int(wh * 0.22))
    pygame.draw.circle(surf, (250, 250, 252), (int(wx + ww * 0.36), int(wy + wh * 0.45)), int(wh * 0.28))
    frame = (250, 246, 238)
    pygame.draw.rect(surf, frame, (int(wx), int(wy), int(ww), int(wh)), max(3, int(u * 4)))
    pygame.draw.line(surf, frame, (wx + ww / 2, wy), (wx + ww / 2, wy + wh), max(3, int(u * 4)))
    paw = _mix(theme.bg, (150, 110, 80), 0.25)
    for _ in range(8):                                   # следы лапок
        x, y = rng.uniform(0.05, 0.95) * w, rng.uniform(0.2, 0.85) * h
        pygame.draw.circle(surf, paw, (int(x), int(y)), int(u * 5))
        for k in range(4):
            a = -math.pi / 2 + (k - 1.5) * 0.55
            pygame.draw.circle(surf, paw, (int(x + math.cos(a) * u * 7), int(y + math.sin(a) * u * 7)), int(u * 2.2))
    sill = h * 0.955
    pygame.draw.rect(surf, (246, 240, 228), (0, int(sill), w, h - int(sill)))
    for fx, flower in ((0.08, (236, 80, 110)), (0.90, (250, 200, 60))):
        x = w * fx; pw, ph = u * 22, u * 18
        pygame.draw.polygon(surf, (196, 104, 70), ((x - pw / 2, sill - ph), (x + pw / 2, sill - ph),
                                                   (x + pw * 0.35, sill), (x - pw * 0.35, sill)))
        for a in (-0.6, 0.0, 0.6):
            pygame.draw.line(surf, (70, 150, 80), (x, sill - ph), (x + math.sin(a) * u * 14, sill - ph - u * 18),
                             max(1, int(u * 2)))
        for k in range(5):
            b = k * math.tau / 5
            pygame.draw.circle(surf, flower, (int(x + math.cos(b) * u * 5), int(sill - ph - u * 20 + math.sin(b) * u * 5)),
                               int(u * 3.5))
        pygame.draw.circle(surf, (250, 230, 120), (int(x), int(sill - ph - u * 20)), int(u * 2.5))


def _junkyard_backdrop(surf, w, h, u, rng, theme):
    """Задворки: кирпичи разного оттенка, грязь по низу стены, граффити,
    асфальт с крошкой и лужами, контейнер и бак со светотенью, мешки, мухи."""
    brick_h, brick_w = max(6, int(u * 12)), max(12, int(u * 26))
    mortar = _mix(theme.bg, (40, 36, 34), 0.55)
    wall_bottom = int(h * 0.86)
    surf.fill(mortar, (0, 0, w, wall_bottom))
    for row, y in enumerate(range(0, wall_bottom, brick_h)):
        shift = (brick_w // 2) if row % 2 else 0
        for x in range(-shift, w, brick_w):
            tone = rng.uniform(-0.18, 0.14)                # каждый кирпич своего оттенка
            base = _mix(theme.bg, (0, 0, 0), -tone) if tone < 0 else _mix(theme.bg, (0, 0, 0), tone)
            base = _mix(base, (255, 255, 255), max(0.0, -tone) * 0.4)
            pygame.draw.rect(surf, base, (x + 1, y + 1, brick_w - 2, brick_h - 2))
            pygame.draw.line(surf, _mix(base, (255, 255, 255), 0.12), (x + 1, y + 1), (x + brick_w - 2, y + 1), 1)
    for _ in range(5):                                   # граффити-пятна
        _soft_blob(surf, rng.uniform(0, w), rng.uniform(h * 0.1, h * 0.75), u * rng.uniform(14, 26),
                   rng.choice(((200, 80, 80), (80, 160, 200), (200, 180, 80))), theme.bg, 5)
    for k in range(12):                                  # грязь у земли: темнее к низу стены
        y = wall_bottom - int(u * 3) * k
        pygame.draw.line(surf, _mix(theme.bg, (20, 18, 16), 0.5 - k * 0.04), (0, y), (w, y), max(1, int(u * 3)))
    asphalt = (58, 60, 64)
    pygame.draw.rect(surf, asphalt, (0, wall_bottom, w, h - wall_bottom))
    for _ in range(int(160 * w / 480)):                  # асфальтовая крошка
        c = rng.choice(((74, 76, 80), (46, 48, 52), (86, 86, 88)))
        surf.fill(c, (int(rng.uniform(0, w)), int(rng.uniform(wall_bottom, h)), max(1, int(u)), max(1, int(u))))
    for _ in range(3):                                   # лужи с отражением неба
        px, py = rng.uniform(0.1, 0.8) * w, rng.uniform(0.9, 0.96) * h
        pw, ph = u * rng.uniform(34, 56), u * 7
        pygame.draw.ellipse(surf, (70, 82, 96), (int(px), int(py), int(pw), int(ph)))
        pygame.draw.line(surf, (140, 160, 180), (px + pw * 0.2, py + ph * 0.4), (px + pw * 0.55, py + ph * 0.4), 1)
    # контейнер: корпус со светотенью, рёбра, крышка, колёса
    dx, dy, dw, dh = w * 0.02, wall_bottom - u * 46, u * 84, u * 50
    pygame.draw.rect(surf, (36, 86, 50), (int(dx), int(dy), int(dw), int(dh)))
    pygame.draw.rect(surf, (52, 118, 70), (int(dx), int(dy), int(dw * 0.35), int(dh)))
    for k in range(4):
        x = dx + dw * (0.2 + k * 0.2)
        pygame.draw.line(surf, (28, 70, 40), (x, dy + u * 4), (x, dy + dh - u * 4), max(1, int(u * 2)))
    pygame.draw.rect(surf, (30, 72, 42), (int(dx - u * 3), int(dy - u * 7), int(dw + u * 6), int(u * 9)))
    for fx in (0.15, 0.85):
        pygame.draw.circle(surf, (24, 24, 26), (int(dx + dw * fx), int(dy + dh + u * 2)), int(u * 4))
    for k, (bx, sz) in enumerate(((dx + dw + u * 10, 18), (dx + dw + u * 30, 14))):   # мешки
        by = wall_bottom - u * sz * 1.4
        pygame.draw.ellipse(surf, (22, 22, 24), (int(bx), int(by), int(u * sz * 1.6), int(u * sz * 1.6)))
        pygame.draw.ellipse(surf, (56, 58, 64), (int(bx + u * 4), int(by + u * 3), int(u * sz * 0.5), int(u * sz * 0.35)))
        pygame.draw.polygon(surf, (22, 22, 24), ((bx + u * sz * 0.6, by + u * 1), (bx + u * sz * 0.8, by - u * 5),
                                                 (bx + u * sz, by + u * 1)))
    # бак: металл полосами, рёбра, крышка набок
    cx0, cy0, cw, ch = w * 0.83, wall_bottom - u * 42, u * 34, u * 44
    for i, tone in enumerate((0.85, 1.0, 1.15, 1.0, 0.8)):
        col = tuple(min(255, int(c * tone)) for c in (140, 146, 154))
        pygame.draw.rect(surf, col, (int(cx0 + i * cw / 5), int(cy0), int(cw / 5) + 1, int(ch)))
    for k in range(3):
        y = cy0 + ch * (0.25 + k * 0.25)
        pygame.draw.line(surf, (100, 106, 114), (cx0, y), (cx0 + cw, y), max(1, int(u * 1.5)))
    pygame.draw.ellipse(surf, (116, 122, 130), (int(cx0 - u * 4), int(cy0 - u * 8), int(cw + u * 8), int(u * 11)))
    pygame.draw.ellipse(surf, (170, 176, 184), (int(cx0 + cw * 0.3), int(cy0 - u * 6), int(cw * 0.4), int(u * 4)))
    for _ in range(7):                                   # мухи
        fx, fy = rng.uniform(0.04, 0.96) * w, rng.uniform(0.72, 0.9) * h
        pygame.draw.circle(surf, (24, 24, 24), (int(fx), int(fy)), max(1, int(u * 1.6)))
        pygame.draw.ellipse(surf, (200, 214, 226), (int(fx - u * 3), int(fy - u * 3), int(u * 3), int(u * 2)))
        pygame.draw.ellipse(surf, (200, 214, 226), (int(fx), int(fy - u * 3), int(u * 3), int(u * 2)))


def _stadium_backdrop(surf, w, h, u, rng, theme):
    """Стадион: трибуны с болельщиками, прожекторы, полосатое поле, ворота."""
    stand_h = h * 0.11
    pygame.draw.rect(surf, _mix(theme.bg, (30, 30, 40), 0.45), (0, 0, w, stand_h))
    for x in range(0, w, max(6, int(u * 5))):
        if rng.random() < 0.5:
            col = rng.choice(((230, 60, 60), (250, 220, 80), (80, 150, 230), (250, 250, 250)))
            pygame.draw.rect(surf, col, (x, stand_h * rng.uniform(0.25, 0.8), max(2, int(u * 3)), max(2, int(u * 3))))
    for fx in (0.05, 0.95):
        x = w * fx
        pygame.draw.rect(surf, (150, 150, 158), (int(x - u), int(stand_h), max(2, int(u * 3)), int(h * 0.05)))
        pygame.draw.rect(surf, (228, 228, 220), (int(x - u * 8), int(stand_h - u * 9), int(u * 16), int(u * 9)))
    band = max(10, int(u * 30))
    for i, y in enumerate(range(int(stand_h), h, band)):
        if i % 2:
            pygame.draw.rect(surf, _mix(theme.bg, (255, 255, 255), 0.05), (0, y, w, band))
    gw, gh = u * 76, u * 30
    gx, gy = w / 2 - gw / 2, h - gh - u * 3
    pygame.draw.rect(surf, (240, 240, 240), (int(gx), int(gy), int(gw), int(gh)), max(2, int(u * 2)))
    for k in range(1, 6):
        pygame.draw.line(surf, (220, 220, 220), (gx + gw * k / 6, gy), (gx + gw * k / 6, gy + gh), 1)


def _chess_backdrop(surf, w, h, u, rng, theme):
    """Шахматный стол: крупная доска в клетку поверх дерева, часы, сбитые фигуры."""
    sq = max(20, int(u * 60))
    dark = _mix(theme.bg, (0, 0, 0), 0.30)
    for gy in range(0, h, sq):
        for gx in range(0, w, sq):
            if (gx // sq + gy // sq) % 2:
                pygame.draw.rect(surf, dark, (gx, gy, sq, sq))
    cx, cy, cw, ch = w * 0.64, h * 0.03, u * 110, u * 44  # шахматные часы
    pygame.draw.rect(surf, (40, 30, 24), (int(cx), int(cy + ch * 0.25), int(cw), int(ch * 0.75)),
                     border_radius=int(u * 6))
    for k in range(2):
        fx = cx + cw * (0.27 + k * 0.46)
        pygame.draw.circle(surf, (246, 244, 236), (int(fx), int(cy + ch * 0.6)), int(ch * 0.3))
        pygame.draw.line(surf, (30, 30, 30), (fx, cy + ch * 0.6), (fx + ch * 0.12 * (1 if k else -1), cy + ch * 0.42), max(1, int(u * 1.5)))
        pygame.draw.rect(surf, (200, 60, 50) if k else (60, 60, 64), (int(fx - u * 6), int(cy + ch * 0.12), int(u * 12), int(u * 5)))
    # съеденные фигуры стоят у края стола
    for fx, kind, white in ((0.05, 0, True), (0.12, 1, True), (0.19, 0, False),
                            (0.82, 4, False), (0.90, 0, False), (0.96, 3, True)):
        fill = (242, 238, 226) if white else (42, 40, 46)
        edge = (90, 80, 70) if white else (12, 12, 14)
        CHESS_PIECES[kind](surf, w * fx, h * 0.985, u * 34, fill, edge)


def _watermelon_backdrop(surf, w, h, u, rng, theme):
    """Арбуз: широкие полосы, как у корки."""
    band = max(10, int(u * 34))
    for i, x in enumerate(range(-h, w, band)):
        if i % 2:
            pygame.draw.polygon(surf, _mix(theme.bg, (0, 0, 0), 0.10),
                                ((x, 0), (x + band, 0), (x + band + h * 0.35, h), (x + h * 0.35, h)))


def _violet_backdrop(surf, w, h, u, rng, theme):
    """Фиолет: волшебная ночь — светящиеся сферы и искры."""
    for _ in range(6):
        _soft_blob(surf, rng.uniform(0, w), rng.uniform(0, h), min(w, h) * rng.uniform(0.12, 0.24),
                   rng.choice(((190, 120, 255), (120, 90, 230), (230, 130, 230))), theme.bg, 7)
    for _ in range(int(40 * w * h / (480 * 860))):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), u * rng.uniform(2, 4)
        col = _mix(theme.bg, (255, 240, 255), rng.uniform(0.4, 0.8))
        pygame.draw.line(surf, col, (x - r, y), (x + r, y), 1)
        pygame.draw.line(surf, col, (x, y - r), (x, y + r), 1)


def _blue_backdrop(surf, w, h, u, rng, theme):
    """Синяя: лучи света и мягкие круги-блики, как в воде на солнце."""
    for k in range(5):
        x = w * (0.1 + k * 0.22)
        pygame.draw.polygon(surf, _mix(theme.bg, (255, 255, 255), 0.06),
                            ((x, 0), (x + w * 0.08, 0), (x + w * 0.2, h), (x + w * 0.06, h)))
    for _ in range(int(18 * w * h / (480 * 860))):
        r = u * rng.uniform(8, 22)
        pygame.draw.circle(surf, _mix(theme.bg, (200, 230, 255), rng.uniform(0.08, 0.18)),
                           (int(rng.uniform(0, w)), int(rng.uniform(0, h))), int(r), max(1, int(u * 1.5)))


def _party_backdrop(surf, w, h, u, rng, theme):
    """Тортик: праздник — гирлянда флажков поверху и конфетти."""
    for row, y0 in enumerate((h * 0.02, h * 0.075)):
        n = 9
        for i in range(n):
            x0, x1 = w * i / n, w * (i + 1) / n
            sag = y0 + math.sin((i + 0.5) / n * math.pi) * h * 0.012
            col = ((236, 90, 110), (250, 200, 70), (110, 190, 240), (140, 210, 120))[(i + row) % 4]
            pygame.draw.polygon(surf, col, ((x0 + 2, sag), (x1 - 2, sag), ((x0 + x1) / 2, sag + u * 18)))
        pygame.draw.line(surf, (250, 246, 240), (0, y0), (w, y0), max(1, int(u)))
    for _ in range(int(60 * w * h / (480 * 860))):
        col = rng.choice(((236, 90, 110), (250, 200, 70), (110, 190, 240), (140, 210, 120), (255, 255, 255)))
        x, y = rng.uniform(0, w), rng.uniform(h * 0.12, h)
        pygame.draw.rect(surf, _mix(col, theme.bg, 0.3), (int(x), int(y), max(2, int(u * 4)), max(2, int(u * 2.5))))


def _brick_backdrop(surf, w, h, u, rng, theme):
    """Кирпич: вечерний городок — крыши с горящими окнами поверху, птицы,
    трава и заборчик внизу."""
    base = h * 0.13
    x = 0
    while x < w:                                         # крыши и дома поверху
        bw, bh = u * rng.uniform(40, 64), h * rng.uniform(0.05, 0.09)
        wall = _mix(theme.bg, (40, 26, 18), 0.45)
        pygame.draw.rect(surf, wall, (int(x), int(base - bh), int(bw), int(bh)))
        pygame.draw.polygon(surf, _mix(theme.bg, (90, 40, 30), 0.6),
                            ((x - u * 3, base - bh), (x + bw / 2, base - bh - bw * 0.35), (x + bw + u * 3, base - bh)))
        for k in range(2):
            if rng.random() < 0.7:
                pygame.draw.rect(surf, (250, 206, 110), (int(x + bw * (0.2 + 0.4 * k)), int(base - bh * 0.7),
                                                         max(3, int(bw * 0.18)), max(3, int(bh * 0.3))))
        x += bw + u * 4
    for _ in range(5):                                   # птицы галочками
        bx, by = rng.uniform(0.1, 0.9) * w, rng.uniform(0.16, 0.24) * h
        pygame.draw.line(surf, _mix(theme.bg, (30, 20, 16), 0.6), (bx - u * 5, by - u * 3), (bx, by), max(1, int(u * 1.5)))
        pygame.draw.line(surf, _mix(theme.bg, (30, 20, 16), 0.6), (bx, by), (bx + u * 5, by - u * 3), max(1, int(u * 1.5)))
    ground = int(h * 0.94)
    pygame.draw.rect(surf, (96, 150, 70), (0, ground, w, h - ground))
    for x in range(0, w, max(8, int(u * 18))):         # заборчик
        pygame.draw.rect(surf, (236, 226, 206), (x + 2, ground - int(u * 18), max(3, int(u * 6)), int(u * 20)))
    pygame.draw.line(surf, (236, 226, 206), (0, ground - u * 12), (w, ground - u * 12), max(2, int(u * 3)))


def _meadow_backdrop(surf, w, h, u, rng, theme):
    """Трава: луг — пучки травы повсюду, цветы и бабочки."""
    for _ in range(int(120 * w * h / (480 * 860))):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        col = _mix(theme.bg, (40, 90, 30), rng.uniform(0.15, 0.3))
        for dx in (-3, 0, 3):
            pygame.draw.line(surf, col, (x, y), (x + dx * u, y - u * rng.uniform(6, 10)), 1)
    for _ in range(int(16 * w / 480)):
        x, y, r = rng.uniform(0, w), rng.uniform(0.88, 0.99) * h, u * 3.5
        col = rng.choice(((250, 250, 250), (250, 220, 90), (240, 130, 170)))
        for k in range(5):
            a = k * math.tau / 5
            pygame.draw.circle(surf, col, (int(x + math.cos(a) * r), int(y + math.sin(a) * r)), int(r * 0.7))
        pygame.draw.circle(surf, (250, 200, 60), (int(x), int(y)), max(1, int(r * 0.5)))
    for _ in range(4):
        x, y = rng.uniform(0.05, 0.95) * w, rng.uniform(0.08, 0.25) * h
        col = rng.choice(((250, 170, 60), (140, 190, 250), (240, 120, 200)))
        for side in (-1, 1):
            pygame.draw.ellipse(surf, col, (int(x + (0 if side > 0 else -u * 8)), int(y - u * 5), int(u * 8), int(u * 9)))
        pygame.draw.line(surf, (40, 30, 30), (x, y - u * 5), (x, y + u * 4), max(1, int(u * 1.5)))


def _globe_backdrop(surf, w, h, u, rng, theme):
    """Страны: меридианы и параллели, самолёт с пунктиром маршрута, роза ветров."""
    line = _mix(theme.bg, (255, 255, 255), 0.12)
    for k in range(1, 8):
        y = h * k / 8
        pygame.draw.line(surf, line, (0, y), (w, y), 1)
    for k in range(-3, 4):                               # меридианы — дуги
        pts = [(w / 2 + k * w * 0.16 * math.cos((t - 0.5) * 1.6), h * t) for t in [i / 30 for i in range(31)]]
        for a, b in zip(pts, pts[1:]):
            pygame.draw.line(surf, line, a, b, 1)
    route = [(w * (0.08 + 0.84 * t), h * (0.16 - 0.08 * math.sin(t * math.pi))) for t in [i / 24 for i in range(25)]]
    for i, (a, b) in enumerate(zip(route, route[1:])):
        if i % 2 == 0:
            pygame.draw.line(surf, (250, 250, 250), a, b, max(1, int(u * 1.5)))
    px, py = route[-1]
    pygame.draw.polygon(surf, (250, 250, 250), ((px + u * 10, py), (px - u * 6, py - u * 4), (px - u * 3, py), (px - u * 6, py + u * 4)))
    cx, cy, r = w * 0.87, h * 0.93, u * 18              # роза ветров
    for k in range(4):
        a = k * math.pi / 2
        pygame.draw.polygon(surf, (236, 220, 170), ((cx + math.cos(a) * r, cy + math.sin(a) * r),
                                                    (cx + math.cos(a + 0.4) * r * 0.3, cy + math.sin(a + 0.4) * r * 0.3),
                                                    (cx + math.cos(a - 0.4) * r * 0.3, cy + math.sin(a - 0.4) * r * 0.3)))


def _frozen_backdrop(surf, w, h, u, rng, theme):
    """Лёд: замёрзшее озеро — трещины, сосульки поверху, снег по краям."""
    crack = _mix(theme.bg, (255, 255, 255), 0.35)
    for _ in range(7):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        for _ in range(6):
            nx, ny = x + rng.uniform(-40, 40) * u, y + rng.uniform(-40, 40) * u
            pygame.draw.line(surf, crack, (x, y), (nx, ny), 1)
            x, y = nx, ny
    for i in range(int(w / (u * 14))):                   # сосульки
        x = i * u * 14 + rng.uniform(0, 4)
        pygame.draw.polygon(surf, (230, 244, 255), ((x, 0), (x + u * 10, 0), (x + u * 5, u * rng.uniform(14, 34))))
    pts = [(0, h)] + [(w * i / 20, h * (0.955 + 0.01 * math.sin(i * 1.3))) for i in range(21)] + [(w, h)]
    pygame.draw.polygon(surf, (240, 248, 255), pts)


def _checker_cloth(surf, w, h, u, col, theme, strength=0.35):
    sq = max(8, int(u * 22))
    for gy in range(0, h, sq):
        for gx in range(0, w, sq):
            if (gx // sq + gy // sq) % 2 == 0:
                pygame.draw.rect(surf, _mix(theme.bg, col, strength), (gx, gy, sq, sq))
    for gy in range(0, h, sq):
        pygame.draw.rect(surf, _mix(theme.bg, col, 0.18), (0, gy + sq // 2 - 1, w, 2))


def _cookie_backdrop(surf, w, h, u, rng, theme):
    """Печенье: скатерть в клетку и крошки."""
    _checker_cloth(surf, w, h, u, (246, 236, 214), theme)
    for _ in range(int(40 * w * h / (480 * 860))):
        pygame.draw.circle(surf, (200, 150, 90), (int(rng.uniform(0, w)), int(rng.uniform(0, h))), max(1, int(u * rng.uniform(1.5, 3))))


def _yarn_backdrop(surf, w, h, u, rng, theme):
    """Вязание: крупная вязка на фоне, клубки со спицами по углам."""
    col = _mix(theme.bg, (255, 255, 255), 0.08)
    step = max(10, int(u * 22))
    for y in range(0, h, step):
        for x in range(0, w, step):
            pygame.draw.line(surf, col, (x, y), (x + step / 2, y + step * 0.8), max(1, int(u * 2)))
            pygame.draw.line(surf, col, (x + step, y), (x + step / 2, y + step * 0.8), max(1, int(u * 2)))
    for fx, fy, c in ((0.1, 0.95, (220, 80, 90)), (0.88, 0.94, (90, 150, 220)), (0.9, 0.08, (240, 190, 80))):
        x, y, r = w * fx, h * fy, u * 20
        pygame.draw.circle(surf, c, (int(x), int(y)), int(r))
        wrap = _mix(c, (0, 0, 0), 0.3)
        for k in range(5):                               # намотка нити — дуги ломаными
            a0 = k * 0.6
            pts = [(x + math.cos(a0 + t * 0.2) * r * (0.35 + k * 0.1), y + math.sin(a0 + t * 0.2) * r * (0.35 + k * 0.1))
                   for t in range(8)]
            for p0, p1 in zip(pts, pts[1:]):
                pygame.draw.line(surf, wrap, p0, p1, 1)
        pygame.draw.line(surf, (200, 200, 210), (x - r * 1.4, y - r * 1.2), (x + r * 0.6, y + r * 0.2), max(2, int(u * 2.5)))
        pygame.draw.line(surf, (200, 200, 210), (x + r * 1.3, y - r * 1.1), (x - r * 0.4, y + r * 0.3), max(2, int(u * 2.5)))


def _mine_backdrop(surf, w, h, u, rng, theme):
    """Руды: шахта — камни на стенах, деревянные крепи, фонарь, рельсы."""
    for _ in range(int(50 * w * h / (480 * 860))):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), u * rng.uniform(6, 16)
        pygame.draw.circle(surf, _mix(theme.bg, (90, 90, 96), rng.uniform(0.15, 0.35)), (int(x), int(y)), int(r))
    beam = (110, 76, 44)
    for fx in (0.02, 0.93):
        pygame.draw.rect(surf, beam, (int(w * fx), 0, int(u * 14), h))
    pygame.draw.rect(surf, beam, (0, int(h * 0.02), w, int(u * 14)))
    _soft_blob(surf, w * 0.5, h * 0.07, u * 40, (250, 200, 110), theme.bg, 6)
    pygame.draw.circle(surf, (255, 226, 150), (int(w * 0.5), int(h * 0.07)), int(u * 6))
    ry = h * 0.965
    for k in range(0, w, max(10, int(u * 16))):
        pygame.draw.rect(surf, (90, 64, 40), (k, int(ry - u * 3), int(u * 6), int(u * 12)))
    for dy in (-u * 1, u * 7):
        pygame.draw.line(surf, (160, 160, 170), (0, ry + dy), (w, ry + dy), max(2, int(u * 2)))


def _candy_backdrop(surf, w, h, u, rng, theme):
    """Мармелад: леденцовые диагональные полосы и леденцы на палочке."""
    band = max(10, int(u * 22))
    for i, x in enumerate(range(-h, w, band)):
        if i % 2:
            pygame.draw.polygon(surf, _mix(theme.bg, (255, 255, 255), 0.10),
                                ((x, 0), (x + band, 0), (x + band + h, h), (x + h, h)))
    for fx, fy, c in ((0.08, 0.93, (240, 90, 120)), (0.9, 0.95, (120, 200, 250)), (0.92, 0.07, (250, 200, 80))):
        x, y, r = w * fx, h * fy, u * 16
        pygame.draw.line(surf, (246, 240, 230), (x, y), (x, y + r * 2.5), max(2, int(u * 3)))
        pygame.draw.circle(surf, c, (int(x), int(y)), int(r))
        pygame.draw.circle(surf, (255, 255, 255), (int(x), int(y)), int(r * 0.6), max(1, int(u * 3)))


def _pizzeria_backdrop(surf, w, h, u, rng, theme):
    """Пицца: красно-белая скатерть в клетку и листики базилика."""
    _checker_cloth(surf, w, h, u, (220, 60, 50), theme, 0.2)   # приглушённо, чтобы не спорило с полем
    for _ in range(int(10 * w * h / (480 * 860))):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        a = rng.uniform(0, math.pi)
        pygame.draw.ellipse(surf, (70, 150, 60), (int(x), int(y), int(u * 14), int(u * 8)))


def _bamboo_backdrop(surf, w, h, u, rng, theme):
    """Суши: бамбуковая циновка, палочки и соусница."""
    slat = max(6, int(u * 14))
    for i, y in enumerate(range(0, h, slat)):
        pygame.draw.rect(surf, _mix(theme.bg, (200, 170, 110), 0.25 if i % 2 else 0.18), (0, y, w, slat - 1))
    for dy in (0, u * 8):                                # палочки
        pygame.draw.line(surf, (190, 140, 90), (w * 0.62, h * 0.05 + dy), (w * 0.98, h * 0.02 + dy), max(2, int(u * 3)))
    x, y, r = w * 0.12, h * 0.95, u * 18                 # соусница
    pygame.draw.circle(surf, (236, 236, 230), (int(x), int(y)), int(r))
    pygame.draw.circle(surf, (60, 30, 20), (int(x), int(y)), int(r * 0.72))


def _forest_backdrop(surf, w, h, u, rng, theme):
    """Дерево: лес — ёлки силуэтами, стволы и поленница внизу."""
    for k in range(9):
        x = w * (k / 8) + rng.uniform(-10, 10)
        th = h * rng.uniform(0.12, 0.2)
        col = _mix(theme.bg, (20, 50, 30), rng.uniform(0.35, 0.55))
        for tier in range(3):
            tw, ty = th * (0.5 - tier * 0.12), h - th * (0.35 + tier * 0.25)
            pygame.draw.polygon(surf, col, ((x, ty - th * 0.3), (x + tw / 2, ty + th * 0.1), (x - tw / 2, ty + th * 0.1)))
    for k in range(6):                                   # поленница
        x = w * 0.04 + k * u * 18
        pygame.draw.circle(surf, (170, 120, 70), (int(x), int(h * 0.975)), int(u * 8))
        pygame.draw.circle(surf, (210, 170, 110), (int(x), int(h * 0.975)), int(u * 5))


def _palace_backdrop(surf, w, h, u, rng, theme):
    """Мрамор: дворец — колонны по бокам, мраморный пол в плитку."""
    col, dark = _mix(theme.bg, (240, 240, 244), 0.45), _mix(theme.bg, (0, 0, 0), 0.2)
    cw = max(12, int(u * 26))
    for x in (int(w * 0.01), int(w * 0.99 - cw)):
        pygame.draw.rect(surf, col, (x, int(h * 0.04), cw, int(h * 0.9)))
        for k in range(3):
            pygame.draw.line(surf, dark, (x + cw * (0.25 + k * 0.25), h * 0.06), (x + cw * (0.25 + k * 0.25), h * 0.92), 1)
        pygame.draw.rect(surf, col, (x - int(u * 4), int(h * 0.03), cw + int(u * 8), int(u * 8)))
        pygame.draw.rect(surf, col, (x - int(u * 4), int(h * 0.93), cw + int(u * 8), int(u * 8)))
    tile = max(16, int(u * 40))
    floor = int(h * 0.95)
    for gx in range(0, w, tile):
        pygame.draw.rect(surf, col if (gx // tile) % 2 else dark, (gx, floor, tile, h - floor))


def _neon_city_backdrop(surf, w, h, u, rng, theme):
    """Неон: ночной город — силуэты домов, неоновые вывески и сетка пола."""
    base = h * 0.9
    x = 0
    while x < w:                                         # дома
        bw, bh = u * rng.uniform(26, 52), h * rng.uniform(0.06, 0.16)
        pygame.draw.rect(surf, (30, 24, 52), (int(x), int(base - bh), int(bw), int(bh)))
        for wy in range(int(base - bh + u * 12), int(base - u * 4), max(4, int(u * 9))):     # огни окон
            for wx in range(int(x + u * 4), int(x + bw - u * 4), max(4, int(u * 8))):
                if rng.random() < 0.35:
                    pygame.draw.rect(surf, (250, 220, 140), (wx, wy, max(2, int(u * 3)), max(2, int(u * 3))))
        if rng.random() < 0.6:
            col = rng.choice(((255, 60, 200), (40, 230, 255), (255, 236, 60)))
            pygame.draw.rect(surf, col, (int(x + bw * 0.2), int(base - bh + u * 6), int(bw * 0.6), max(2, int(u * 3))))
        x += bw + u * 2
    for k in range(9):                                   # сетка пола
        y = base + (h - base) * (k / 8) ** 1.6
        pygame.draw.line(surf, (200, 40, 170), (0, y), (w, y), 1)
    for k in range(-6, 7):
        pygame.draw.line(surf, (200, 40, 170), (w / 2 + k * w * 0.02, base), (w / 2 + k * w * 0.18, h), 1)


def _baseplate_backdrop(surf, w, h, u, rng, theme):
    """Конструктор: пластина с пупырышками и рассыпанные детальки внизу."""
    step = max(10, int(u * 24))
    for gy in range(step // 2, h, step):
        for gx in range(step // 2, w, step):
            pygame.draw.circle(surf, _mix(theme.bg, (255, 255, 255), 0.10), (gx, gy), max(2, int(step * 0.3)))
            pygame.draw.circle(surf, _mix(theme.bg, (0, 0, 0), 0.10), (gx + 1, gy + 1), max(2, int(step * 0.3)), 1)
    for _ in range(6):
        x, y = rng.uniform(0.02, 0.9) * w, rng.uniform(0.93, 0.98) * h
        col = rng.choice(((222, 36, 40), (250, 204, 30), (40, 160, 70), (30, 96, 204)))
        pygame.draw.rect(surf, col, (int(x), int(y), int(u * 26), int(u * 12)))
        for k in range(2):
            pygame.draw.circle(surf, col, (int(x + u * (7 + k * 12)), int(y)), int(u * 4))


def _classic_backdrop(surf, w, h, u, rng, theme):
    """Классика: едва заметный узор из точек и мягкое затемнение по краям."""
    step = max(10, int(u * 26))
    for gy in range(0, h, step):
        for gx in range((gy // step % 2) * step // 2, w, step):
            pygame.draw.circle(surf, _mix(theme.bg, (255, 255, 255), 0.06), (gx, gy), max(1, int(u * 1.5)))



def _foil_backdrop(surf, w, h, u, rng, theme):
    """Обёртка фольги: сгибы-блики по диагонали и отогнутый уголок."""
    for i in range(-2, 12):
        x = i * u * 40
        col = _mix(theme.bg, (255, 255, 255), 0.05 if i % 2 else 0.10)
        pygame.draw.polygon(surf, col, ((x, 0), (x + u * 20, 0), (x - h * 0.6 + u * 20, h), (x - h * 0.6, h)))
    corner = u * 60
    pygame.draw.polygon(surf, _mix(theme.bg, (0, 0, 0), 0.20),
                        ((w - corner, 0), (w, 0), (w, corner)))
    pygame.draw.polygon(surf, _mix(theme.bg, (255, 255, 255), 0.20),
                        ((w - corner * 0.7, 0), (w, corner * 0.7), (w - corner, corner * 0.35)))


BACKDROPS = {
    "foil": _foil_backdrop,
    "stadium": _stadium_backdrop,
    "melon": _watermelon_backdrop,
    "magic": _violet_backdrop,
    "rays": _blue_backdrop,
    "party": _party_backdrop,
    "roof": _brick_backdrop,            # у «Кирпича» украшение — крыша над полем, фон к ней
    "meadow": _meadow_backdrop,
    "globe": _globe_backdrop,
    "frozen": _frozen_backdrop,
    "kitchen": _cookie_backdrop,
    "yarn": _yarn_backdrop,
    "mine": _mine_backdrop,
    "candy": _candy_backdrop,
    "pizzeria": _pizzeria_backdrop,
    "bamboo": _bamboo_backdrop,
    "forest": _forest_backdrop,
    "palace": _palace_backdrop,
    "neoncity": _neon_city_backdrop,
    "baseplate": _baseplate_backdrop,
    "dots": _classic_backdrop,
    "chess": _chess_backdrop,
    "junkyard": _junkyard_backdrop,
    "bakery": _bakery_backdrop,
    "winter": _winter_backdrop,
    "sewing": _sewing_backdrop,
    "desk": _desk_backdrop,
    "windowsill": _windowsill_backdrop,
    "chalkboard": _chalkboard_backdrop,
    "sky": _sky_backdrop,
    "space": _space_backdrop,
    "ocean": _ocean_backdrop,
    "halloween": _halloween_backdrop,
    "autumn": _autumn_backdrop,
    "easter": _easter_backdrop,
}


def newyear_background(size: tuple[int, int], theme) -> pygame.Surface:
    """Новогодняя ночь: снежинки, гирлянда поверху, сугробы и ёлки внизу.

    Рисуется один раз на размер экрана и кэшируется — по стоимости кадра
    это тот же один blit, что и обычный градиент."""
    width, height = size
    key = ("newyear", width, height, theme.id)

    def make() -> pygame.Surface:
        surf = gradient(size, theme.bg, theme.bg_bottom).copy()
        rng = random.Random(width * 7 + height)
        unit = max(1, min(width, height) / 400)

        # снежинки: мелкие — точки, крупные — шестилучевые звёздочки
        for _ in range(int(70 * width * height / (480 * 860)) + 20):
            x, y = rng.uniform(0, width), rng.uniform(0, height * 0.9)
            big = rng.random() < 0.28
            tone = rng.randint(200, 250)
            col = (tone, tone, min(255, tone + 8))
            if big:
                r = unit * rng.uniform(3.0, 5.5)
                for k in range(3):
                    a = k * math.pi / 3 + rng.uniform(0, 0.3)
                    dx, dy = math.cos(a) * r, math.sin(a) * r
                    pygame.draw.line(surf, col, (x - dx, y - dy), (x + dx, y + dy), max(1, int(unit)))
            else:
                pygame.draw.circle(surf, col, (int(x), int(y)), max(1, int(unit * rng.uniform(1, 2))))

        # ёлки по краям внизу — силуэты с заснеженными ярусами
        def tree(cx, base, th):
            for tier in range(3):
                tw = th * (0.62 - tier * 0.14)
                ty = base - th * (0.30 + tier * 0.26)
                pts = ((cx, ty - th * 0.34), (cx + tw / 2, ty + th * 0.08), (cx - tw / 2, ty + th * 0.08))
                pygame.draw.polygon(surf, (24, 84, 60), pts)
                pygame.draw.line(surf, (226, 236, 246), (cx - tw / 2 + 2, ty + th * 0.07),
                                 (cx + tw / 2 - 2, ty + th * 0.07), max(1, int(unit * 1.5)))
            pygame.draw.rect(surf, (70, 44, 34), (int(cx - th * 0.05), int(base - th * 0.10),
                                                  max(2, int(th * 0.10)), int(th * 0.10)))
        base = height * 0.965
        for cx, th in ((width * 0.07, height * 0.13), (width * 0.19, height * 0.09),
                       (width * 0.92, height * 0.14), (width * 0.80, height * 0.08)):
            tree(cx, base, th)

        # сугробы: два слоя волн по низу
        for layer, (top, amp, col) in enumerate(((0.945, 0.012, (206, 220, 238)),
                                                 (0.962, 0.010, (236, 244, 252)))):
            pts = [(0, height)]
            for i in range(41):
                x = width * i / 40
                y = height * (top + amp * math.sin(i * 0.9 + layer * 1.7))
                pts.append((x, y))
            pts.append((width, height))
            pygame.draw.polygon(surf, col, pts)

        # гирлянда: провод провисает двумя дугами, лампочки чередуют цвета
        wire = (58, 96, 72)                         # тёмно-зелёный провод, виден на ночном небе
        sag, top = height * 0.022, height * 0.006
        def wire_y(x):
            t = (x / width) * 2 % 1.0
            return top + sag * math.sin(t * math.pi)
        prev = (0, wire_y(0))
        for i in range(1, 81):
            x = width * i / 80
            cur = (x, wire_y(x))
            pygame.draw.line(surf, wire, prev, cur, max(1, int(unit * 1.2)))
            prev = cur
        bulbs = ((232, 60, 60), (250, 200, 60), (64, 192, 96), (74, 144, 242))
        count = max(8, int(width / (32 * unit)))
        for i in range(count):
            x = width * (i + 0.5) / count
            y = wire_y(x)
            col = bulbs[i % len(bulbs)]
            br = unit * 3.6
            pygame.draw.circle(surf, tuple(max(0, c - 110) for c in col), (int(x), int(y + br * 1.4)), int(br * 1.9))
            pygame.draw.rect(surf, (90, 90, 96), (int(x - br * 0.45), int(y), max(2, int(br * 0.9)), max(2, int(br * 0.7))))
            pygame.draw.ellipse(surf, col, (int(x - br), int(y + br * 0.4), int(br * 2), int(br * 2.6)))
            pygame.draw.circle(surf, (255, 255, 240), (int(x - br * 0.3), int(y + br * 1.1)), max(1, int(br * 0.35)))
        return surf.convert()

    return texture_cache.get(key, make)


def board_frame(theme: Theme, size: int, cell: int, pad: int) -> pygame.Surface:
    """Рамка + пустые клетки: меняется только при смене темы/размера."""
    key = ("board", theme.id, size, cell, pad)

    def make() -> pygame.Surface:
        px = size * cell + pad * 2
        surf = pygame.Surface((px, px), pygame.SRCALPHA)
        pygame.draw.rect(surf, theme.board_bg, surf.get_rect(), border_radius=max(6, pad * 2))
        gap = block_gap(cell)
        radius = max(2, cell // 9)
        for r in range(size):
            for c in range(size):
                pygame.draw.rect(surf, theme.cell_empty,
                                 (pad + c * cell + gap, pad + r * cell + gap, cell - 2 * gap, cell - 2 * gap),
                                 border_radius=radius)
        return surf.convert_alpha()

    return texture_cache.get(key, make)


def roof(width: int, height: int) -> pygame.Surface:
    """Крыша домиком над полем для темы «Кирпич» (из оригинала)."""
    key = ("roof", width, height)

    def make() -> pygame.Surface:
        surf = pygame.Surface((width, height + 8), pygame.SRCALPHA)
        pygame.draw.polygon(surf, (110, 46, 34), [(0, height), (width // 2, 0), (width, height)])
        pygame.draw.circle(surf, (86, 34, 26), (width // 2, 4), 5)
        pygame.draw.rect(surf, (60, 40, 30), (0, height, width, 8), border_radius=3)
        return surf.convert_alpha()

    return texture_cache.get(key, make)


def flat_square(color: tuple, size: int) -> pygame.Surface:
    key = ("square", color, size)
    return texture_cache.get(key, lambda: _filled(color, size))


def _filled(color: tuple, size: int) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    s.fill(color)
    return s


def overlay(size: tuple[int, int], rgba: tuple) -> pygame.Surface:
    return texture_cache.get(("overlay", size, rgba), lambda: _overlay(size, rgba))


def _overlay(size, rgba) -> pygame.Surface:
    s = pygame.Surface(size, pygame.SRCALPHA)
    s.fill(rgba)
    return s


def rounded_panel(size: tuple[int, int], rgba: tuple, radius: int) -> pygame.Surface:
    key = ("panel", size, rgba, radius)

    def make() -> pygame.Surface:
        s = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(s, rgba, s.get_rect(), border_radius=radius)
        return s

    return texture_cache.get(key, make)


# ---------------- иконки ----------------

def icon(name: str, size: int, color: tuple) -> pygame.Surface:
    key = ("icon", name, int(size), tuple(color))
    return texture_cache.get(key, lambda: _draw_icon(name, int(size), tuple(color)))


def _draw_icon(name: str, size: int, color: tuple) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size / 2
    if name == "pause":
        bw, bh = size * 0.22, size * 0.62
        for x in (c - bw * 1.3, c + bw * 0.3):
            pygame.draw.rect(s, color, (x, c - bh / 2, bw, bh), border_radius=max(1, size // 12))
    elif name == "hint":  # лампочка
        pygame.draw.circle(s, color, (int(c), int(size * 0.4)), int(size * 0.27))
        pygame.draw.rect(s, color, (c - size * 0.13, size * 0.6, size * 0.26, size * 0.18), border_radius=2)
        pygame.draw.rect(s, color, (c - size * 0.1, size * 0.8, size * 0.2, size * 0.08), border_radius=2)
    elif name == "gear":  # из оригинала: нормальная шестерёнка
        pts = []
        for i in range(16):
            rad = math.radians(i * 22.5)
            r = size * (0.47 if i % 2 == 0 else 0.34)
            pts.append((c + math.cos(rad) * r, c + math.sin(rad) * r))
        pygame.draw.polygon(s, color, pts)
        pygame.draw.circle(s, (0, 0, 0, 0), (int(c), int(c)), int(size * 0.16))
    elif name == "crown":
        w = h = size
        pts = [(0, h * 0.85), (0, h * 0.3), (w * 0.25, h * 0.55), (w * 0.5, h * 0.1),
               (w * 0.75, h * 0.55), (w, h * 0.3), (w, h * 0.85)]
        pygame.draw.polygon(s, color, pts)
    elif name == "lock":
        pygame.draw.rect(s, color, (size * 0.2, size * 0.45, size * 0.6, size * 0.45), border_radius=3)
        pygame.draw.circle(s, color, (int(c), int(size * 0.42)), int(size * 0.22), width=max(2, size // 10))
    elif name == "star":
        pts = []
        for i in range(10):
            rad = math.radians(-90 + i * 36)
            r = size * (0.48 if i % 2 == 0 else 0.2)
            pts.append((c + math.cos(rad) * r, c + math.sin(rad) * r))
        pygame.draw.polygon(s, color, pts)
    elif name == "back":
        w = max(2, size // 8)
        pygame.draw.line(s, color, (size * 0.65, size * 0.2), (size * 0.3, c), w)
        pygame.draw.line(s, color, (size * 0.3, c), (size * 0.65, size * 0.8), w)
    return s.convert_alpha()

textures = _namespace("SCALE_STEPS", "block_gap", "cell_variant", "LABELED_STYLES", "block_variant", "block", "ALPHA_STEP", "block_ghost", "piece_with_shadow", "block_scaled", "piece", "piece_ghost", "piece_shadow", "gradient", "flat_background", "draw_background", "background", "_backdrop", "_mix", "_soft_blob", "_space_backdrop", "_ocean_backdrop", "_halloween_backdrop", "_leaf_shape", "_autumn_backdrop", "_easter_backdrop", "_sky_backdrop", "_chalkboard_backdrop", "_bakery_backdrop", "_winter_backdrop", "_sewing_backdrop", "_desk_backdrop", "_windowsill_backdrop", "_junkyard_backdrop", "_stadium_backdrop", "_chess_backdrop", "_watermelon_backdrop", "_violet_backdrop", "_blue_backdrop", "_party_backdrop", "_brick_backdrop", "_meadow_backdrop", "_globe_backdrop", "_frozen_backdrop", "_checker_cloth", "_cookie_backdrop", "_yarn_backdrop", "_mine_backdrop", "_candy_backdrop", "_pizzeria_backdrop", "_bamboo_backdrop", "_forest_backdrop", "_palace_backdrop", "_neon_city_backdrop", "_baseplate_backdrop", "_classic_backdrop", "_foil_backdrop", "BACKDROPS", "newyear_background", "board_frame", "roof", "flat_square", "_filled", "overlay", "_overlay", "rounded_panel", "icon", "_draw_icon")

# ======================================================================
# blockblast/render/layout.py
# ======================================================================

"""Адаптивная раскладка экрана.

В оригинале размеры считались один раз из CELL, а потом CELL/WIDTH/GRID_X
и т.д. пересчитывались второй раз внизу файла (CELL = 78). Всё, что успело
посчитаться между ними (`_fade_scratch`, `_gameover_overlay`, первый set_mode),
жило со старыми значениями, а окно 644×1114 не помещалось на экран 1366×768.
Здесь раскладка — чистая функция от размера окна и размера поля."""

from dataclasses import dataclass

import pygame



@dataclass(frozen=True)
class Layout:
    width: int
    height: int
    portrait: bool
    scale: float
    top_bar: pygame.Rect
    goal_bar: pygame.Rect
    board: pygame.Rect          # вместе с рамкой
    board_size: int
    cell: int
    pad: int
    tray: pygame.Rect
    tray_slots: tuple[pygame.Rect, ...]
    tray_cell: int
    pause_button: pygame.Rect
    hint_button: pygame.Rect

    @property
    def grid_origin(self) -> tuple[int, int]:
        return self.board.x + self.pad, self.board.y + self.pad

    def cell_rect(self, r: int, c: int) -> pygame.Rect:
        ox, oy = self.grid_origin
        return pygame.Rect(ox + c * self.cell, oy + r * self.cell, self.cell, self.cell)

    def px(self, value: float) -> int:
        """Размер из дизайнерских пикселей в реальные."""
        return max(1, int(round(value * self.scale)))


LANDSCAPE_BASE = (1100, 720)


def ui_scale(width: int, height: int) -> float:
    """Единый масштаб интерфейса для всех экранов (портрет и ландшафт)."""
    if height >= width * 1.05:
        scale = min(width / BASE_W, height / BASE_H)
    else:
        scale = min(width / LANDSCAPE_BASE[0], height / LANDSCAPE_BASE[1])
    return max(0.6, min(scale, 4.0))


def compute_layout(width: int, height: int, board_size: int, top_inset: int = 0) -> Layout:
    portrait = height >= width * 1.05
    scale = ui_scale(width, height)

    def px(v: float) -> int:
        return max(1, int(round(v * scale)))

    margin = px(14)
    top_h = px(72)
    goal_h = px(34)
    top_bar = pygame.Rect(margin, margin + top_inset, width - 2 * margin, top_h)
    btn = px(46)
    pause_button = pygame.Rect(top_bar.right - btn, top_bar.centery - btn // 2, btn, btn)
    hint_button = pygame.Rect(pause_button.x - btn - px(10), pause_button.y, btn, btn)

    if portrait:
        goal_bar = pygame.Rect(margin, top_bar.bottom + px(4), width - 2 * margin, goal_h)
        tray_h = max(px(150), int(height * 0.19))
        avail_w = width - 2 * margin
        avail_h = height - goal_bar.bottom - tray_h - px(24) - margin
        side = min(avail_w, avail_h)
        cell = max(8, (side - px(16)) // board_size)
        pad = max(4, cell // 8)
        board_px = cell * board_size + pad * 2
        board = pygame.Rect((width - board_px) // 2, goal_bar.bottom + px(12) + max(0, (avail_h - board_px) // 2),
                            board_px, board_px)
        tray = pygame.Rect(margin, board.bottom + px(12), width - 2 * margin,
                           height - board.bottom - px(12) - margin)
        slot_w = tray.w // TRAY_SLOTS
        slots = tuple(pygame.Rect(tray.x + i * slot_w, tray.y, slot_w, tray.h) for i in range(TRAY_SLOTS))
        tray_cell = max(6, min(int(cell * 0.62), (slot_w - px(16)) // 5, (tray.h - px(16)) // 5))
    else:
        panel_w = max(px(200), int(width * 0.3))
        avail_h = height - top_bar.bottom - px(10) - margin
        avail_w = width - panel_w - 3 * margin
        side = min(avail_w, avail_h)
        cell = max(8, (side - px(8)) // board_size)
        pad = max(4, cell // 8)
        board_px = cell * board_size + pad * 2
        board = pygame.Rect(margin + (avail_w - board_px) // 2, top_bar.bottom + px(10) + (avail_h - board_px) // 2,
                            board_px, board_px)
        panel_x = width - panel_w - margin
        goal_bar = pygame.Rect(panel_x, top_bar.bottom + px(6), panel_w, goal_h)
        tray = pygame.Rect(panel_x, goal_bar.bottom + px(8), panel_w, height - goal_bar.bottom - px(8) - margin)
        slot_h = tray.h // TRAY_SLOTS
        slots = tuple(pygame.Rect(tray.x, tray.y + i * slot_h, tray.w, slot_h) for i in range(TRAY_SLOTS))
        tray_cell = max(6, min(int(cell * 0.62), (slot_h - px(12)) // 5, (tray.w - px(16)) // 5))

    return Layout(width, height, portrait, scale, top_bar, goal_bar, board, board_size, cell, pad,
                  tray, slots, tray_cell, pause_button, hint_button)

# ======================================================================
# blockblast/render/effects.py
# ======================================================================

"""Визуальные эффекты.

Про «утечки» частиц в оригинале: список частиц чистился в finish_clear_animation,
так что утечки как таковой не было, НО на каждую очистку создавалось до
64×4 = 256 новых Surface + convert_alpha(), а при двойной очистке подряд
старый список просто перезаписывался. Здесь:
  * частицы — лёгкие объекты со __slots__ без собственных Surface;
  * рисуются через surface.fill() (самая быстрая операция в pygame);
  * жёсткий лимит MAX_PARTICLES — старые частицы вытесняются;
  * мёртвые частицы удаляются каждый кадр."""

import math
import random
from typing import Optional

import pygame



class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color")

    def __init__(self, x, y, vx, vy, life, size, color):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.size = size
        self.color = color


class ParticleSystem:
    def __init__(self, capacity: int = MAX_PARTICLES, seed: Optional[int] = None):
        self.capacity = capacity
        self.items: list[Particle] = []
        self.rng = random.Random(seed)

    def burst(self, x: float, y: float, color: tuple, count: int, cell: int) -> None:
        rng = self.rng
        for _ in range(count):
            a = rng.uniform(0, math.tau)
            speed = rng.uniform(cell * 1.2, cell * 3.2)
            self.items.append(Particle(
                x, y, math.cos(a) * speed, math.sin(a) * speed - cell * 1.5,
                rng.uniform(0.45, 0.8), max(2, int(rng.uniform(cell * 0.1, cell * 0.24))),
                tuple(min(255, ch + 25) for ch in color)))
        overflow = len(self.items) - self.capacity
        if overflow > 0:
            del self.items[:overflow]

    def update(self, dt: float, gravity: float) -> None:
        alive = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            p.vy += gravity * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            alive.append(p)
        self.items = alive

    def draw(self, surf: pygame.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        ox, oy = offset
        fill = surf.fill
        for p in self.items:
            s = max(1, int(p.size * (p.life / p.max_life)))  # затухаем уменьшением — без альфы
            fill(p.color, (int(p.x - s / 2) + ox, int(p.y - s / 2) + oy, s, s))

    def bounds(self) -> pygame.Rect:
        """Общий прямоугольник всех частиц — чтобы знать, что стирать в следующем кадре."""
        if not self.items:
            return pygame.Rect(0, 0, 0, 0)
        xs = [p.x for p in self.items]
        ys = [p.y for p in self.items]
        pad = max(4, int(max(p.size for p in self.items)) + 2)
        return pygame.Rect(int(min(xs)) - pad, int(min(ys)) - pad,
                           int(max(xs) - min(xs)) + 2 * pad, int(max(ys) - min(ys)) + 2 * pad)

    def __len__(self) -> int:
        return len(self.items)


class Shard:
    """Осколок блока: кусок готовой текстуры, который летит с гравитацией.

    Новых поверхностей не создаём: рисуем прямоугольник исходной текстуры
    через area= в blit. Затухание — сжатием куска к центру, без альфы."""
    __slots__ = ("x", "y", "vx", "vy", "area", "life", "max_life")

    def __init__(self, x, y, vx, vy, area, life):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.area = area                    # (sx, sy, sw, sh) внутри текстуры клетки
        self.life = self.max_life = life

    def visible_area(self):
        """Кусок сжимается к своему центру в последние 60% жизни."""
        sx, sy, sw, sh = self.area
        k = clamp01(self.life / (self.max_life * 0.6))
        w, h = max(1, int(sw * k)), max(1, int(sh * k))
        return sx + (sw - w) // 2, sy + (sh - h) // 2, w, h


SHATTER_AT = 0.18          # доля анимации клетки до раскола: короткое «вспухание»
SHARD_LIFE = 0.55


def shatter_cuts(size: int, rng: random.Random) -> list[tuple[int, int, int, int]]:
    """Режет квадрат size×size на 4–9 кусков разного размера.

    Разрезы ставятся в случайных местах, поэтому куски неравные —
    блок раскалывается, а не распадается на ровную сетку."""
    def cuts() -> list[int]:
        n = rng.choice((1, 2, 2))           # 2 или 3 полосы, чаще 3
        pts = sorted(rng.uniform(0.22, 0.78) for _ in range(n))
        # слишком тонкие полосы выглядят как мусор — раздвигаем
        edges, prev = [0], 0.0
        for q in pts:
            if q - prev >= 0.2:
                edges.append(int(size * q)); prev = q
        edges.append(size)
        return edges
    xs, ys = cuts(), cuts()
    return [(x0, y0, x1 - x0, y1 - y0)
            for x0, x1 in zip(xs, xs[1:]) for y0, y1 in zip(ys, ys[1:])
            if x1 > x0 and y1 > y0]


class ClearWave:
    """Исчезновение очищенных клеток «волной» от места, куда поставили фигуру.

    В полных анимациях клетка коротко вспухает и раскалывается на осколки
    разного размера. Без полных анимаций — простое сжатие, как раньше."""

    def __init__(self, cells: list[tuple], origin: tuple[float, float], full: bool):
        self.cells = []
        self.labels: dict[tuple[int, int], int] = {}     # буквы кубиков для «Алфавита»
        for r, c, color, *rest in cells:
            if rest and rest[0] is not None:
                self.labels[(r, c)] = rest[0]
            dist = math.hypot(r + 0.5 - origin[0], c + 0.5 - origin[1])
            delay = dist * CLEAR_WAVE_DELAY if full else 0.0
            self.cells.append((r, c, color, delay))
        self.full = full
        self.elapsed = 0.0
        self.duration = CLEAR_ANIM if full else CLEAR_ANIM * 0.5
        self.max_delay = max((d for *_, d in self.cells), default=0.0)
        self.burst_done: set[tuple[int, int]] = set()
        self.shattered: set[tuple[int, int]] = set()
        self.shards: list[tuple[Shard, int, int, int]] = []   # осколок, цвет, вариант, размер
        self._gravity = 0.0
        self._last_bounds = pygame.Rect(0, 0, 0, 0)

    def update(self, dt: float) -> None:
        self.elapsed += dt
        alive = []
        for item in self.shards:
            sh = item[0]
            sh.life -= dt
            if sh.life <= 0:
                continue
            sh.vy += self._gravity * dt
            sh.x += sh.vx * dt
            sh.y += sh.vy * dt
            alive.append(item)
        self.shards = alive

    @property
    def done(self) -> bool:
        return self.elapsed >= self.duration + self.max_delay and not self.shards

    def _shatter(self, r, c, color, theme, rect, size, cell):
        """Колем клетку: раскладка кусков зависит только от клетки и цвета,
        поэтому одинакова при любой перерисовке — repaint_test это требует."""
        rng = random.Random((r * 131 + c) * 7919 + color * 31 + size)
        variant = textures.cell_variant(theme, r, c, self.labels.get((r, c)))
        x0 = rect.centerx - size / 2
        y0 = rect.centery - size / 2
        for sx, sy, sw, sh in shatter_cuts(size, rng):
            # летим от центра клетки наружу, с разбросом и толчком вверх
            fx = (sx + sw / 2) / size - 0.5
            fy = (sy + sh / 2) / size - 0.5
            dist = math.hypot(fx, fy) or 1.0
            speed = cell * rng.uniform(1.6, 3.4)
            vx = fx / dist * speed + rng.uniform(-0.4, 0.4) * cell
            vy = fy / dist * speed - cell * rng.uniform(1.6, 2.6)
            life = SHARD_LIFE * rng.uniform(0.8, 1.15)
            self.shards.append((Shard(x0 + sx, y0 + sy, vx, vy, (sx, sy, sw, sh), life),
                                color, variant, size))

    def draw(self, surf, theme: Theme, layout, particles: Optional[ParticleSystem], offset=(0, 0)) -> None:
        gap = textures.block_gap(layout.cell)
        size = layout.cell - 2 * gap
        self._gravity = layout.cell * 16
        ox, oy = offset
        drawn: list[pygame.Rect] = []
        for r, c, color, delay in self.cells:
            t = clamp01((self.elapsed - delay) / self.duration)
            if t >= 1:
                continue
            rect = layout.cell_rect(r, c)
            if t > 0 and particles is not None and (r, c) not in self.burst_done:
                self.burst_done.add((r, c))
                # искр меньше, чем раньше: основную работу делают осколки
                particles.burst(rect.centerx, rect.centery, theme.color(color),
                                2 if self.full else 4, layout.cell)
            if self.full:
                if t >= SHATTER_AT:
                    if (r, c) not in self.shattered:
                        self.shattered.add((r, c))
                        self._shatter(r, c, color, theme, rect, size, layout.cell)
                    continue
                scale = 1.0 + 0.10 * math.sin(t / SHATTER_AT * math.pi)
            else:
                scale = 1.0 + 0.12 * math.sin(min(t * 2.5, 1) * math.pi) if t < 0.4 \
                    else 1 - ease_in_cubic((t - 0.4) / 0.6)
                scale = max(0.0, scale)
                if scale <= 0.02:
                    continue
            variant = textures.cell_variant(theme, r, c, self.labels.get((r, c)))
            tex = textures.block_scaled(theme, color, size, variant, min(scale, 1.0))
            dst = tex.get_rect(center=rect.move(offset).center)
            surf.blit(tex, dst)
            drawn.append(dst)
            if t < 0.35:  # белая вспышка в начале
                alpha = int(170 * (1 - t / 0.35)) // 16 * 16  # квантуем, чтобы не плодить текстуры
                flash = textures.flat_square((255, 255, 255, alpha), max(1, dst.w))
                surf.blit(flash, dst)

        for sh, color, variant, sz in self.shards:
            tex = textures.block(theme, color, sz, variant)
            ax, ay, aw, ah = sh.visible_area()
            sx, sy, sw, shh = sh.area
            px = int(sh.x + (ax - sx)) + ox
            py = int(sh.y + (ay - sy)) + oy
            drawn.append(surf.blit(tex, (px, py), (ax, ay, aw, ah)))
        self._last_bounds = drawn

    def bounds(self) -> list[pygame.Rect]:
        """Что нарисовали в этом кадре — ровно это надо стереть в следующем.

        Осколки улетают далеко за пределы клетки, поэтому прежнее
        «клетка плюс треть» оставило бы на экране хвосты."""
        return list(self._last_bounds) if isinstance(self._last_bounds, list) else []



class Bubbles:
    """Пузыри на фоне темы «Океан»: всплывают и лопаются.

    Живут только в свободных полосах экрана — над полем, между полем и
    лотком, под лотком — и лопаются, не доходя до следующего элемента.
    Иначе при частичной перерисовке пузырь оказался бы поверх поля.
    Своё зерно случайности: одинаковая картина при любой перерисовке."""

    POP_TIME = 0.22
    BALLOON_COLORS = ((236, 60, 64), (250, 150, 40), (250, 210, 50), (70, 184, 90),
                      (60, 130, 230), (160, 90, 220), (246, 110, 176))

    def __init__(self, seed: int = 4242, style: str = "bubble"):
        self.style = style                    # "bubble" — океан, "balloon" — небо, "snow" — зима
        self.rng = random.Random(seed)
        self.items: list[list[float]] = []   # x0, y, r, vy, age, life, phase, popping, zone
        self.zones: list[pygame.Rect] = []
        self.timers: list[float] = []
        self.obstacles: list[pygame.Rect] = []
        self.unit = 1.0
        self._key = None

    def set_obstacles(self, rects: list[pygame.Rect]) -> None:
        """Поле, фигуры в лотке, счёт: пузырь, коснувшись их, лопается."""
        self.obstacles = [r for r in rects if r.w > 2 and r.h > 2]

    def _blocked(self, x: float, y: float, r: float) -> bool:
        if self.style == "balloon":            # овал выше круга, плюс ниточка и брызги конфетти
            box = pygame.Rect(int(x - r * 2.4), int(y - r * 2.4), int(r * 4.8), int(r * 5.4))
        else:
            box = pygame.Rect(int(x - r * 2.2), int(y - r * 2.2), int(r * 4.4), int(r * 4.4))
        return any(box.colliderect(o) for o in self.obstacles)

    def set_zones(self, zones: list[pygame.Rect], unit: float) -> None:
        key = tuple(tuple(z) for z in zones) + (round(unit, 3),)
        if key == self._key:
            return
        self._key = key
        self.unit = unit
        need = 44 if self.style == "balloon" else 30
        self.zones = [z for z in zones if z.h > unit * need and z.w > unit * 30]
        self.timers = [self.rng.uniform(0.1, 0.8) for _ in self.zones]
        self.items.clear()

    def update(self, dt: float) -> None:
        u = self.unit
        for i, zone in enumerate(self.zones):
            self.timers[i] -= dt
            alive = sum(1 for b in self.items if b[8] == i)
            cap = max(2, min(6, zone.w * zone.h // int((70 * u) ** 2)))
            if self.style == "balloon":            # шарики крупные — считаем по их размеру
                cap = max(2, min(4, zone.w * zone.h // int((95 * u) ** 2)))
            elif self.style == "snow":             # снежинки мелкие — их много
                cap = max(4, min(12, zone.w * zone.h // int((48 * u) ** 2)))
            if self.timers[i] <= 0 and alive < cap:
                big = self.style == "balloon"
                snow = self.style == "snow"
                r = u * (self.rng.uniform(9.0, 13.0) if big else self.rng.uniform(1.6, 3.6) if snow
                         else self.rng.uniform(3.0, 6.5))
                for _ in range(14):                    # ищем место, не занятое фигурами
                    x0 = self.rng.uniform(zone.left + r * 2, zone.right - r * 2)
                    if snow:                           # снег появляется сверху и падает вниз
                        y0 = self.rng.uniform(zone.top + r * 2, zone.top + zone.h * 0.5)
                    else:
                        y0 = self.rng.uniform(zone.top + zone.h * 0.45, zone.bottom - r * 2)
                    if not self._blocked(x0, y0, r):
                        speed = self.rng.uniform(16, 28) if big else self.rng.uniform(22, 42)
                        life = self.rng.uniform(2.5, 5.0) if big else self.rng.uniform(1.4, 3.2)
                        vy = -u * speed
                        if snow:
                            vy, life = u * self.rng.uniform(14, 30), self.rng.uniform(2.5, 5.0)
                        self.items.append([x0, y0, r, vy, 0.0, life,
                                           self.rng.uniform(0, math.tau), 0.0, i])
                        break
                self.timers[i] = (self.rng.uniform(0.35, 1.1) if self.style == "bubble"
                                  else self.rng.uniform(0.12, 0.45) if self.style == "snow"
                                  else self.rng.uniform(0.3, 0.8))
        keep = []
        for b in self.items:
            b[4] += dt
            if b[7] > 0:                       # лопается
                b[7] += dt
                if b[7] < self.POP_TIME:
                    keep.append(b)
                continue
            b[1] += b[3] * dt
            zone = self.zones[b[8]]
            x = b[0] + math.sin(b[4] * 2.6 + b[6]) * self.unit * 3
            # лопается от старости, у края своей полосы или ударившись о фигуру
            edge = (b[1] + b[2] * 2.2 >= zone.bottom) if self.style == "snow" else (b[1] - b[2] * 2.4 <= zone.top)
            if b[4] >= b[5] or edge or self._blocked(x, b[1], b[2]):
                b[7] = 1e-6
            keep.append(b)
        self.items = keep

    @property
    def active(self) -> bool:
        return bool(self.zones)

    def _draw_balloon(self, surf, x, y, rr, phase, popping) -> float:
        """Шарик: овал с бликом, узелок и ниточка. Лопается конфетти."""
        u = self.unit
        col = self.BALLOON_COLORS[int(phase * 10) % len(self.BALLOON_COLORS)]
        if popping > 0:
            k = popping / self.POP_TIME
            for n in range(10):
                a = n * math.tau / 10 + phase
                d = rr * (0.6 + k * 1.6)
                c = self.BALLOON_COLORS[(n + int(phase * 10)) % len(self.BALLOON_COLORS)]
                pygame.draw.rect(surf, c, (int(x + math.cos(a) * d), int(y + math.sin(a) * d),
                                           max(2, int(u * 2.5)), max(2, int(u * 2.5))))
            return rr * 2.3 + 3
        bw, bh = rr * 1.6, rr * 2.0
        top = y - bh / 2
        for i in range(5):                                       # ниточка
            t0, t1 = i / 5, (i + 1) / 5
            pygame.draw.line(surf, (70, 80, 100),
                             (x + math.sin(t0 * 5 + phase) * u * 2, y + bh / 2 + t0 * rr * 1.4),
                             (x + math.sin(t1 * 5 + phase) * u * 2, y + bh / 2 + t1 * rr * 1.4), 1)
        pygame.draw.ellipse(surf, tuple(max(0, c - 55) for c in col),
                            (int(x - bw / 2) + 1, int(top) + 1, int(bw), int(bh)))
        pygame.draw.ellipse(surf, col, (int(x - bw / 2), int(top), int(bw), int(bh)))
        pygame.draw.polygon(surf, tuple(max(0, c - 40) for c in col),
                            ((x, y + bh / 2 - 1), (x + u * 2.5, y + bh / 2 + u * 3), (x - u * 2.5, y + bh / 2 + u * 3)))
        pygame.draw.ellipse(surf, tuple(min(255, c + (255 - c) * 3 // 4) for c in col),
                            (int(x - bw * 0.30), int(top + bh * 0.14), int(bw * 0.26), int(bh * 0.28)))
        return max(bw, bh + rr * 1.6) / 2 + rr * 0.9 + 3

    def draw(self, surf: pygame.Surface) -> list[pygame.Rect]:
        u = self.unit
        rim, shine = (176, 228, 246), (236, 250, 255)
        drawn = []
        for x0, y, r, vy, age, life, phase, popping, _ in self.items:
            x = x0 + math.sin(age * 2.6 + phase) * u * 3
            rr = r * (0.7 + 0.3 * min(1.0, age / 0.4))            # «надувается» при появлении
            if self.style == "snow":                              # снежинка тает — уменьшается
                k = popping / self.POP_TIME if popping > 0 else 0.0
                sr = max(1, int(rr * (1 - k)))
                pygame.draw.circle(surf, (246, 250, 255), (int(x), int(y)), sr)
                if rr > u * 2.6 and k == 0:
                    for n in range(3):
                        a = n * math.pi / 3 + phase
                        dx, dy = math.cos(a) * rr * 1.7, math.sin(a) * rr * 1.7
                        pygame.draw.line(surf, (230, 240, 252), (x - dx, y - dy), (x + dx, y + dy), 1)
                reach = rr * 1.8 + 2
                drawn.append(pygame.Rect(int(x - reach), int(y - reach), int(reach * 2) + 1, int(reach * 2) + 1))
                continue
            if self.style == "balloon":
                reach = self._draw_balloon(surf, x, y, rr, phase, popping)
                drawn.append(pygame.Rect(int(x - reach), int(y - reach), int(reach * 2) + 1, int(reach * 2.4) + 1))
                continue
            if popping > 0:
                k = popping / self.POP_TIME
                for n in range(7):                               # брызги во все стороны
                    a = n * math.tau / 7 + phase
                    ca, sa = math.cos(a), math.sin(a)
                    pygame.draw.line(surf, rim, (x + ca * rr * (0.9 + k * 0.5), y + sa * rr * (0.9 + k * 0.5)),
                                     (x + ca * rr * (1.3 + k * 0.7), y + sa * rr * (1.3 + k * 0.7)),
                                     max(1, int(u)))
                reach = rr * 2.1 + 2
            else:
                pygame.draw.circle(surf, rim, (int(x), int(y)), max(2, int(rr)), max(1, int(u)))
                pygame.draw.circle(surf, shine, (int(x - rr * 0.35), int(y - rr * 0.35)), max(1, int(rr * 0.28)))
                reach = rr + 2
            drawn.append(pygame.Rect(int(x - reach), int(y - reach), int(reach * 2) + 1, int(reach * 2) + 1))
        return drawn


class FloatingText:
    def __init__(self, surf: pygame.Surface, x: float, y: float, rise: float, duration: float = 0.9, delay: float = 0.0):
        self.surf = surf
        self.x, self.y, self.rise = x, y, rise
        self.tween = Tween(0, 1, duration, delay=delay)

    def update(self, dt):
        self.tween.update(dt)

    @property
    def done(self):
        return self.tween.done

    def draw(self, target: pygame.Surface, offset=(0, 0)):
        t = self.tween.t
        if self.tween.elapsed < self.tween.delay:
            return None
        pop = ease_out_back(min(1.0, t * 4))
        y = self.y - self.rise * ease_out_cubic(t)
        surf = self.surf
        if pop < 0.99:
            w, h = surf.get_size()
            surf = pygame.transform.smoothscale(surf, (max(1, int(w * pop)), max(1, int(h * pop))))
        alpha = 255 if t < 0.65 else int(255 * (1 - (t - 0.65) / 0.35))
        surf.set_alpha(alpha)
        rect = target.blit(surf, surf.get_rect(center=(self.x + offset[0], y + offset[1])))
        surf.set_alpha(255)
        return rect


class Toast:
    """Всплывающая плашка (достижения)."""

    def __init__(self, surf: pygame.Surface, duration: float = 2.8):
        self.surf = surf
        self.elapsed = 0.0
        self.duration = duration

    def update(self, dt):
        self.elapsed += dt

    @property
    def done(self):
        return self.elapsed >= self.duration

    def offset_y(self, height: int) -> float:
        t_in = ease_out_back(self.elapsed / 0.35)
        t_out = ease_in_cubic((self.elapsed - (self.duration - 0.3)) / 0.3)
        return -height * (1 - t_in) - height * 1.5 * t_out


class Shake:
    def __init__(self):
        self.strength = 0.0
        self.rng = random.Random()

    def add(self, amount: float):
        self.strength = min(self.strength + amount, amount * 2.5)

    def update(self, dt):
        self.strength = max(0.0, self.strength - dt * self.strength * 7 - dt * 2)

    @property
    def offset(self) -> tuple[int, int]:
        if self.strength < 0.5:
            return 0, 0
        s = self.strength
        return int(self.rng.uniform(-s, s)), int(self.rng.uniform(-s, s))


class PlaceFlash:
    """Короткая светлая вспышка на только что поставленных клетках."""

    def __init__(self, cells: list[tuple[int, int]], duration: float = 0.22):
        self.cells = cells
        self.tween = Tween(1, 0, duration)

    def update(self, dt):
        self.tween.update(dt)

    @property
    def done(self):
        return self.tween.done

    def draw(self, surf, layout, offset=(0, 0)):
        a = int(110 * self.tween.value)
        if a <= 0:
            return
        gap = textures.block_gap(layout.cell)
        tex = textures.rounded_panel((layout.cell - 2 * gap,) * 2, (255, 255, 255, a // 8 * 8), max(2, layout.cell // 9))
        for r, c in self.cells:
            surf.blit(tex, layout.cell_rect(r, c).move(offset).inflate(-2 * gap, -2 * gap))

# ======================================================================
# blockblast/render/game_view.py
# ======================================================================

"""Отрисовка игрового экрана. Только чтение состояния игры — никакой логики."""

import math
from typing import Optional

import pygame


PRAISE = {2: "Отлично!", 3: "Супер!", 4: "Невероятно!", 5: "Легендарно!"}


class GameView:
    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self.layout: Optional[Layout] = None
        self.particles = ParticleSystem()
        self.waves: list[ClearWave] = []
        self.bubbles = Bubbles()
        self.flashes: list[PlaceFlash] = []
        self.texts: list[FloatingText] = []
        self.shake = Shake()
        self.score = RollingNumber()
        self.tray_spawn: list[Optional[Tween]] = [None, None, None]
        self.hint: Optional[Move] = None
        self.hint_board_version = -1
        self.time = 0.0
        self._composite: Optional[pygame.Surface] = None
        self._cells: Optional[tuple] = None
        self.always_rebuild_base = False   # только для тестов: всегда собирать слой заново
        self._base: Optional[pygame.Surface] = None
        self._base_key: tuple = ()
        self._prev_dynamic: list[pygame.Rect] = []
        self._force_full = True
        self._tray_state: tuple = ()
        self._tray_rects: list[pygame.Rect] = []
        self.full_animations = True

    # ---------- раскладка ----------

    def set_layout(self, layout: Layout) -> None:
        self.layout = layout
        self.ctx.scale = layout.scale
        self._composite = None
        self._cells = None
        self._base = None
        self._force_full = True

    def force_full(self) -> None:
        """Следующий кадр перерисовать целиком (смена сцены, оверлей, тема)."""
        self._force_full = True

    def reset(self, game: Game) -> None:
        self._cells = None
        self.particles.items.clear()
        self.waves.clear()
        self.flashes.clear()
        self.texts.clear()
        self.hint = None
        self._force_full = True
        self.score.set(game.score, instant=True)
        self.spawn_tray()

    # ---------- реакции на события игры ----------

    def spawn_tray(self) -> None:
        self.tray_spawn = [Tween(0, 1, TRAY_SPAWN_ANIM, ease_out_back, delay=i * 0.06) for i in range(3)]

    def on_event(self, event, game: Game, shake_enabled: bool) -> None:
        L = self.layout
        if L is None:
            return
        theme = self.ctx.theme
        if isinstance(event, ev.PiecePlaced):
            self.flashes.append(PlaceFlash(event.cells))
            self.hint = None
        elif isinstance(event, ev.LinesCleared):
            self.waves.append(ClearWave(event.cells, event.origin, self.full_animations))
            ox, oy = L.grid_origin
            x = ox + event.origin[1] * L.cell
            y = oy + event.origin[0] * L.cell
            lines = event.move.lines
            if lines >= 2:
                word = PRAISE.get(min(lines, 5))
                self.texts.append(FloatingText(self.ctx.text(word, 44, theme.accent, bold=True),
                                               L.board.centerx, L.board.centery, L.cell * 1.2, 1.1))
            if event.move.streak >= 2:
                self.texts.append(FloatingText(self.ctx.text(f"Комбо x{event.move.streak}", 30, (255, 255, 255),
                                                             bold=True), x, y + L.cell * 0.6, L.cell, 1.0, delay=0.08))
            if shake_enabled and lines >= 2:
                self.shake.add(L.cell * 0.08 * lines)
        elif isinstance(event, ev.ScoreGained):
            move = event.move
            if move.lines:
                x = L.grid_origin[0] + L.cell * L.board_size / 2
                self.texts.append(FloatingText(self.ctx.text(f"+{move.total}", 36, theme.accent, bold=True),
                                               x, L.board.centery - L.cell * 1.3, L.cell * 1.5, 1.0))
        elif isinstance(event, ev.PerfectClear):
            self.texts.append(FloatingText(self.ctx.text(f"Поле чисто! +{event.bonus}", 40, (255, 255, 255), bold=True),
                                           L.board.centerx, L.board.centery + L.cell, L.cell * 2, 1.6, delay=0.2))
        elif isinstance(event, ev.TrayRefilled):
            self.spawn_tray()
        elif isinstance(event, ev.LevelUp):
            self.texts.append(FloatingText(self.ctx.text(f"Уровень {event.level}!", 48, theme.accent, bold=True),
                                           L.board.centerx, L.board.centery, L.cell * 1.5, 1.8, delay=0.25))

    def show_hint(self, move: Optional[Move], game: Game) -> None:
        self.hint = move
        self.hint_board_version = game.board.version

    # ---------- обновление ----------

    def update(self, dt: float, game: Game) -> None:
        self.time += dt
        self.score.set(game.score)
        self.score.update(dt)
        self.shake.update(dt)
        if self.layout:
            self.particles.update(dt, self.layout.cell * 14)
            self._sync_bubbles()
            self.bubbles.update(dt)
        for group in (self.waves, self.flashes, self.texts):
            for item in group:
                item.update(dt)
            group[:] = [i for i in group if not i.done]
        for i, t in enumerate(self.tray_spawn):
            if t is not None:
                t.update(dt)
                if t.done:
                    self.tray_spawn[i] = None
        if self.hint and self.hint_board_version != game.board.version:
            self.hint = None

    def _sync_bubbles(self) -> None:
        """Пузыри только в «Океане» с полными анимациями и только в свободных
        полосах экрана: над полем, между полем и лотком, под лотком."""
        L = self.layout
        style = {"ocean": "bubble", "sky": "balloon", "winter": "snow"}.get(self.ctx.theme.decoration)
        if style is None or not self.full_animations:
            self.bubbles.set_zones([], 1.0)
            return
        if self.bubbles.style != style:
            self.bubbles = Bubbles(style=style)
        m = max(4, L.cell // 5)
        top = max(L.top_bar.bottom, L.goal_bar.bottom) + m
        # две полосы фона: над полем и под ним до низа экрана. Фигуры лотка —
        # препятствия: пузырь, коснувшись фигуры, лопается и под неё не заходит
        zones = [pygame.Rect(m, top, L.width - 2 * m, L.board.top - m - top),
                 pygame.Rect(m, L.board.bottom + m, L.width - 2 * m, L.height - m - L.board.bottom - m)]
        self.bubbles.set_zones(zones, max(1.0, L.cell / 44))
        self.bubbles.set_obstacles([L.board.inflate(m, m), L.top_bar, L.goal_bar]
                                   + [r.inflate(m, m) for r in self._tray_rects])

    @property
    def busy(self) -> bool:
        return bool(self.bubbles.active or self.waves or self.texts or self.particles.items or self.flashes
                    or self.score.animating or any(self.tray_spawn) or self.shake.strength > 0.5 or self.hint)

    @property
    def effects_settling(self) -> bool:
        return bool(self.waves or self.texts)

    # ---------- геометрия лотка ----------

    def tray_cell_for(self, piece: Piece) -> int:
        """Фигура масштабируется под слот: мелкие фигуры выглядят крупнее,
        длинная «пятёрка» целиком помещается в слот."""
        L = self.layout
        slot = L.tray_slots[0]
        pad = L.px(18)
        return max(6, int(min(L.cell * 0.8,
                              (slot.w - pad) / piece.shape.cols,
                              (slot.h - pad) / piece.shape.rows)))

    def tray_piece_center(self, index: int) -> tuple[int, int]:
        return self.layout.tray_slots[index].center

    def tray_index_at(self, pos, game: Game) -> Optional[int]:
        L = self.layout
        for i, slot in enumerate(L.tray_slots):
            if slot.collidepoint(pos) and game.tray[i] is not None:
                return i
        # щедрая зона захвата: ближайший слот, если чуть промахнулись
        if L.tray.inflate(L.px(20), L.px(40)).collidepoint(pos):
            best = min(range(len(L.tray_slots)),
                       key=lambda i: math.dist(pos, L.tray_slots[i].center))
            if game.tray[best] is not None:
                return best
        return None

    # ---------- отрисовка ----------

    def _board_snapshot(self, game: Game) -> tuple:
        # вместе с буквами: иначе смена буквы при том же цвете не перерисовала бы клетку
        return tuple(tuple(zip(line, labels)) for line, labels in zip(game.board.cells, game.board.labels))

    def _paint_cell(self, r: int, c: int, color, theme, label=None) -> pygame.Rect:
        """Перерисовывает одну клетку в готовом поле и в фоновом слое."""
        L = self.layout
        gap = textures.block_gap(L.cell)
        size = L.cell - 2 * gap
        frame = textures.board_frame(theme, L.board_size, L.cell, L.pad)
        local = pygame.Rect(L.pad + c * L.cell, L.pad + r * L.cell, L.cell, L.cell)
        self._composite.blit(frame, local, local)          # пустая клетка с рамкой
        if color is not None:
            self._composite.blit(textures.block(theme, color, size, textures.cell_variant(theme, r, c, label)),
                                 (local.x + gap, local.y + gap))
        if self._base is not None:
            dest = local.move(L.board.topleft)
            self._base.blit(self._composite, dest, local)
            return dest
        return pygame.Rect(0, 0, 0, 0)

    def _build_composite(self, game: Game) -> None:
        L, theme, board = self.layout, self.ctx.theme, game.board
        surf = pygame.Surface(L.board.size)                # непрозрачная: быстрый блит
        # подложка под углами поля обязана совпадать с фоном экрана
        if textures.flat_background(theme, self.ctx.simple_bg):
            surf.fill(theme.bg)
        else:
            surf.blit(textures.background((L.width, L.height), theme),
                      (-L.board.x, -L.board.y))
        surf.blit(textures.board_frame(theme, board.size, L.cell, L.pad), (0, 0))
        gap = textures.block_gap(L.cell)
        size = L.cell - 2 * gap
        for r, line in enumerate(board.cells):
            for c, color in enumerate(line):
                if color is not None:
                    variant = textures.cell_variant(theme, r, c, board.labels[r][c])
                    surf.blit(textures.block(theme, color, size, variant),
                              (L.pad + c * L.cell + gap, L.pad + r * L.cell + gap))
        self._composite = surf.convert()

    def _ensure_base(self, game: Game) -> tuple:
        """Готовый непрозрачный слой «фон + поле».

        После хода не пересобираем его целиком (это давало заметную паузу на телефоне),
        а перерисовываем только изменившиеся клетки. Возвращает (слой, собран ли заново,
        список подправленных участков)."""
        L = self.layout
        key = (self.ctx.theme.id, L.cell, L.pad, L.board_size, self.ctx.simple_bg,
               L.board.topleft, (L.width, L.height))
        if self._base is None or key != self._base_key or self.always_rebuild_base:
            self._build_composite(game)
            base = pygame.Surface((L.width, L.height))
            self._paint_static(base, game, (0, 0))
            self._base, self._base_key = base.convert(), key
            self._cells = self._board_snapshot(game)
            return self._base, True, []

        cells = self._board_snapshot(game)
        patches = []
        if cells != self._cells:
            theme = self.ctx.theme
            old = self._cells
            for r in range(L.board_size):
                if old[r] == cells[r]:
                    continue
                for c in range(L.board_size):
                    if old[r][c] != cells[r][c]:
                        color, label = cells[r][c]
                        patches.append(self._paint_cell(r, c, color, theme, label))
            self._cells = cells
        return self._base, False, patches

    def draw_background(self, surf: pygame.Surface) -> None:
        textures.draw_background(surf, self.ctx.theme, self.ctx.simple_bg)

    def _paint_static(self, target: pygame.Surface, game: Game, offset) -> None:
        L, theme = self.layout, self.ctx.theme
        self.draw_background(target)
        if theme.decoration == "roof":
            overhang = L.px(16)
            h = max(L.px(20), min(L.px(50), L.board.y - L.goal_bar.bottom - L.px(4)))
            target.blit(textures.roof(L.board.w + overhang * 2, h),
                        (L.board.x - overhang + offset[0], L.board.y - h + offset[1]))
        target.blit(self._composite, L.board.move(offset))

    def draw(self, surf: pygame.Surface, game: Game, drag, best: int, hints_enabled: bool,
             extra_rects: tuple = ()) -> None:
        """Перерисовываем только то, что изменилось: полноэкранный blit каждый кадр
        съедал почти всё время кадра на телефоне."""
        L = self.layout
        theme = self.ctx.theme
        off = self.shake.offset
        base, rebuilt, patches = self._ensure_base(game)
        full = self._force_full or rebuilt or off != (0, 0)
        # пока экран трясётся, кадр собирается целиком; и ещё один полный кадр нужен
        # после тряски, иначе поле останется нарисованным со сдвигом
        self._force_full = off != (0, 0)

        if full:
            if off != (0, 0):
                self._paint_static(surf, game, off)
            else:
                surf.blit(base, (0, 0))
            restored = [surf.get_rect()]
            self._prev_dynamic = []
        else:
            restored = list(self._prev_dynamic) + patches
            for r in restored:                  # стираем прошлый кадр и показываем новые клетки
                surf.blit(base, r, r)

        # лоток — самый нижний слой динамики: рисуем его сразу после восстановления,
        # иначе он затирает нарисованные выше эффекты и фигуру в руке
        if self._tray_needs_redraw(game, drag, restored):
            if not full:
                # чистим и слоты, и то, что реально закрасили в прошлый раз:
                # анимация появления «перелетает» размер и вылезает за слот
                for zone in list(L.tray_slots) + self._tray_rects:
                    clipped = zone.clip(surf.get_rect())
                    if clipped.w and clipped.h:
                        surf.blit(base, clipped, clipped)
            self._tray_rects = self._draw_tray(surf, game, drag)

        dyn: list[pygame.Rect] = [L.top_bar.copy(), L.goal_bar.copy()]
        # пузыри — фон, поэтому раньше интерфейса; их полосы с ним не пересекаются
        dyn += self.bubbles.draw(surf)
        self._draw_hud(surf, game, best)
        self._draw_goal_bar(surf, game, hints_enabled)

        target = drag.resolve(game, L) if drag.active else None
        if target is not None:
            dyn += self._draw_preview(surf, game, drag.piece, target, off)
        elif self.hint is not None and not drag.active:
            dyn += self._draw_hint(surf, game, off)

        for f in self.flashes:
            f.draw(surf, L, off)
            dyn += [L.cell_rect(r, c).move(off) for r, c in f.cells]
        for w in self.waves:
            w.draw(surf, theme, L, self.particles if self.full_animations else None, off)
            # стираем ровно нарисованное: осколки улетают далеко за клетку
            dyn += [r.inflate(4, 4) for r in w.bounds()]
            dyn += [L.cell_rect(r, c).move(off).inflate(L.cell // 3, L.cell // 3) for r, c, _, _ in w.cells]
        if self.particles.items:
            self.particles.draw(surf, off)
            dyn.append(self.particles.bounds().move(off))

        dyn += self._draw_flying(surf, game, drag)

        for t in self.texts:
            rect = t.draw(surf, off)
            if rect is not None:
                dyn.append(rect)

        dyn += [pygame.Rect(r) for r in extra_rects]
        screen = surf.get_rect()
        self._prev_dynamic = [r.clip(screen) for r in dyn if r.w > 0 and r.h > 0 and r.colliderect(screen)]

    def _draw_hud(self, surf, game: Game, best: int) -> None:
        L, ctx, theme = self.layout, self.ctx, self.ctx.theme
        x = L.top_bar.x
        crown = textures.icon("crown", L.px(20), theme.accent)
        surf.blit(crown, (x, L.top_bar.y + L.px(4)))
        best_txt = ctx.text(str(max(best, game.score)), 22, theme.accent, bold=True)
        surf.blit(best_txt, best_txt.get_rect(midleft=(x + crown.get_width() + L.px(6), L.top_bar.y + L.px(14))))
        score = ctx.text(str(self.score.value), 50, theme.text, bold=True)
        surf.blit(score, (x, L.top_bar.y + L.px(28)))

    def _draw_goal_bar(self, surf, game: Game, hints_enabled: bool) -> None:
        L, ctx, theme = self.layout, self.ctx, self.ctx.theme
        bar = L.goal_bar
        progress = game.mode.progress(game)
        if progress is not None:
            cur, target = progress
            label = ctx.text(f"Ур. {game.mode.level}  ·  {game.mode.goal().text()}", 20, theme.text, bold=True)
            surf.blit(label, label.get_rect(midleft=(bar.x, bar.y + bar.h * 0.32)))
            track = pygame.Rect(bar.x, bar.y + int(bar.h * 0.66), bar.w, max(4, L.px(8)))
            pygame.draw.rect(surf, (0, 0, 0), track, border_radius=track.h // 2)
            fill = track.copy()
            fill.w = int(track.w * cur / max(1, target))
            if fill.w > 0:
                pygame.draw.rect(surf, theme.accent, fill, border_radius=track.h // 2)
            val = ctx.text(f"{cur}/{target}", 18, theme.text)
            surf.blit(val, val.get_rect(midright=(bar.right, bar.y + bar.h * 0.32)))
            return
        combo = game.combo
        if combo.streak >= 1:
            pulse = 1 + 0.06 * math.sin(self.time * 8) if combo.streak >= 2 else 1
            txt = ctx.text(f"Комбо x{combo.streak}", 24 * pulse // 1, theme.accent, bold=True)
            r = surf.blit(txt, txt.get_rect(midleft=(bar.x, bar.centery)))
            pip = L.px(9)
            for i in range(combo.keep_moves):
                color = theme.accent if i < combo.moves_left else (0, 0, 0)
                pygame.draw.circle(surf, color, (r.right + L.px(14) + i * (pip * 2 + L.px(4)), bar.centery), pip)
        elif game.moves == 0:
            txt = ctx.text("Перетащи фигуру на поле", 20, theme.text)
            txt.set_alpha(170)
            surf.blit(txt, txt.get_rect(center=bar.center))
            txt.set_alpha(255)

    def _ghost(self, surf, theme, color: int, r: int, c: int, alpha: int, off, label=None) -> None:
        L = self.layout
        gap = textures.block_gap(L.cell)
        tex = textures.block_ghost(theme, color, L.cell - 2 * gap, textures.cell_variant(theme, r, c, label), alpha)
        surf.blit(tex, L.cell_rect(r, c).move(off).inflate(-2 * gap, -2 * gap))

    def _draw_preview(self, surf, game: Game, piece: Piece, target: tuple[int, int], off) -> list:
        theme = self.ctx.theme
        row, col = target
        rows, cols = game.board.lines_if_placed(piece.shape, row, col)
        # линии, которые закроются, подсвечиваются цветом фигуры — как в оригинальной Block Blast
        n = game.board.size
        highlight = {(r, c) for r in rows for c in range(n)} | {(r, c) for c in cols for r in range(n)}
        for r, c in highlight:
            if game.board.cells[r][c] is not None:
                self._ghost(surf, theme, piece.color, r, c, 235, off, game.board.labels[r][c])
        alpha = 150 if not highlight else 200
        cells = list(highlight)
        for k, (dr, dc) in enumerate(piece.shape.cells):
            label = piece.labels[k] if k < len(piece.labels) else None
            self._ghost(surf, theme, piece.color, row + dr, col + dc, alpha, off, label)
            cells.append((row + dr, col + dc))
        return [self.layout.cell_rect(r, c).move(off) for r, c in cells]

    def _draw_hint(self, surf, game: Game, off) -> list:
        piece = game.piece_at(self.hint.tray_index)
        if piece is None:
            return []
        alpha = int(90 + 80 * (0.5 + 0.5 * math.sin(self.time * 5)))  # квантуется в block_ghost
        L = self.layout
        for k, (dr, dc) in enumerate(piece.shape.cells):
            r, c = self.hint.row + dr, self.hint.col + dc
            label = piece.labels[k] if k < len(piece.labels) else None
            self._ghost(surf, self.ctx.theme, piece.color, r, c, alpha, off, label)
            pygame.draw.rect(surf, (255, 255, 255), L.cell_rect(r, c).move(off).inflate(-2, -2),
                             width=max(1, L.px(2)), border_radius=max(2, L.cell // 9))
        return [L.cell_rect(self.hint.row + dr, self.hint.col + dc).move(off) for dr, dc in piece.shape.cells]

    def _tray_needs_redraw(self, game: Game, drag, damage: list) -> bool:
        """Фигуры в лотке статичны: перерисовываем, только если они изменились
        или поверх них что-то стёрли/нарисовали."""
        state = (tuple(game.tray), tuple(game.playable()), drag.index,
                 tuple(f.index for f in drag.returning), self.ctx.theme.id,
                 self.hint.tray_index if self.hint else -1,
                 tuple(t is not None for t in self.tray_spawn))
        changed = state != self._tray_state
        self._tray_state = state
        if changed or self.hint is not None or any(self.tray_spawn):
            return True
        zones = list(self.layout.tray_slots) + self._tray_rects
        return any(r.colliderect(z) for z in zones for r in damage)

    def _draw_tray(self, surf, game: Game, drag) -> list:
        L, theme = self.layout, self.ctx.theme
        playable = game.playable()
        rects = []
        for i, piece in enumerate(game.tray):
            if piece is None or drag.is_hidden(i):
                continue
            tex = textures.piece(theme, piece.shape, piece.color, self.tray_cell_for(piece), dimmed=not playable[i],
                                 labels=piece.labels)
            center = list(L.tray_slots[i].center)
            spawn = self.tray_spawn[i]
            if spawn is not None:
                s = max(0.01, spawn.value)
                w, h = tex.get_size()
                tex = pygame.transform.smoothscale(tex, (max(1, int(w * s)), max(1, int(h * s))))
            if self.hint is not None and self.hint.tray_index == i:
                center[1] -= int(abs(math.sin(self.time * 6)) * L.px(8))
            rects.append(surf.blit(tex, tex.get_rect(center=center)))
        return rects

    def _scaled_piece(self, piece: Piece, cell: float) -> pygame.Surface:
        L = self.layout
        tex = textures.piece(self.ctx.theme, piece.shape, piece.color, L.cell, labels=piece.labels)
        if abs(cell - L.cell) < 0.5:
            return tex
        k = cell / L.cell  # во время короткой анимации масштабируем одну текстуру, а не строим десятки новых
        return pygame.transform.smoothscale(tex, (max(1, int(tex.get_width() * k)), max(1, int(tex.get_height() * k))))

    def _draw_flying(self, surf, game: Game, drag) -> list:
        L = self.layout
        rects = []
        for f in drag.returning:
            tex = self._scaled_piece(f.piece, f.cell())
            rects.append(surf.blit(tex, tex.get_rect(center=f.center(L.tray_slots[f.index].center))))
        if drag.active:
            if abs(drag.cell - L.cell) < 0.5:   # обычный случай: фигура с тенью одной текстурой
                tex = textures.piece_with_shadow(self.ctx.theme, drag.piece.shape, drag.piece.color,
                                                 L.cell, (L.px(5), L.px(9)), labels=drag.piece.labels)
            else:                               # короткая анимация «подъёма» из лотка
                tex = self._scaled_piece(drag.piece, drag.cell)
            rects.append(surf.blit(tex, tex.get_rect(center=(int(drag.center[0]), int(drag.center[1])))))
        return rects

# ======================================================================
# blockblast/ui/widgets.py
# ======================================================================

"""Простые виджеты интерфейса с hover/press-анимацией."""

from typing import Any, Callable, Optional, Sequence  # noqa: F401

import pygame



class UIContext:
    """Общие зависимости виджетов: шрифты, тема, звук, масштаб."""

    def __init__(self, fonts: Fonts, themes: ThemeManager, audio) -> None:
        self.fonts = fonts
        self.themes = themes
        self.audio = audio
        self.scale = 1.0
        self.safe_top = 0      # отступ под статус-бар на телефоне
        self.touch = False     # сенсорный экран: у пальца нет «наведения»
        self.simple_bg = False # «низкое» качество: сплошной фон вместо градиента
        self.no_bake = False   # только для тестов: рисовать всё напрямую, без кэша виджетов

    @property
    def theme(self):
        return self.themes.current

    def px(self, v: float) -> int:
        return max(1, int(round(v * self.scale)))

    def text(self, s: str, size: float, color: Optional[tuple] = None, bold: bool = False) -> pygame.Surface:
        return self.fonts.render(s, self.px(size), color or self.theme.text, bold)


def lighten(c: tuple, amount: int) -> tuple:
    return tuple(max(0, min(255, v + amount)) for v in c[:3]) + tuple(c[3:])


class BakedDrawable:
    """Элемент, который рисуется одним непрозрачным блитом: полупрозрачные панели
    и текст собираются заранее поверх куска фона и кэшируются."""

    rect = pygame.Rect(0, 0, 0, 0)
    visible = True

    def __init__(self) -> None:
        self._baked: Optional[pygame.Surface] = None
        self._baked_key: tuple = ()

    def render_key(self, ctx: "UIContext") -> tuple:
        """Всё, от чего зависит картинка (кроме положения по вертикали:
        при прокрутке списка оно меняется каждый кадр, а сама картинка — нет)."""
        return (type(self).__name__, self.rect.x, self.rect.size, ctx.theme.id, round(ctx.scale, 3))

    def bake_rect(self, ctx: "UIContext") -> pygame.Rect:
        return self.rect.union(self.rect.move(0, ctx.px(5)))   # запас на тень

    def draw(self, surf: pygame.Surface, ctx: "UIContext") -> None:
        pass

    def needs_redraw(self, ctx: "UIContext") -> bool:
        return self._baked is None or self.render_key(ctx) != self._baked_key[0]

    def draw_baked(self, surf: pygame.Surface, ctx: "UIContext", base: pygame.Surface,
                   bg_color: Optional[tuple] = None) -> pygame.Rect:
        """bg_color задаётся там, где фон однотонный (экраны со списками): тогда кэш
        не зависит от вертикального положения и переживает прокрутку."""
        if not self.visible:
            return pygame.Rect(0, 0, 0, 0)
        area = self.bake_rect(ctx).clip(base.get_rect())
        if not (area.w and area.h):
            return pygame.Rect(0, 0, 0, 0)
        key = (self.render_key(ctx), bg_color or area.y)
        if self._baked is None or key != self._baked_key or self._baked.get_size() != area.size:
            local = pygame.Surface(area.size)
            if bg_color is None:
                local.blit(base, (0, 0), area)
            else:
                local.fill(bg_color)
            saved = self.rect
            self.rect = saved.move(-area.x, -area.y)
            try:
                self.draw(local, ctx)
            finally:
                self.rect = saved
            self._baked, self._baked_key = local.convert(), key
        return surf.blit(self._baked, area)


class Widget(BakedDrawable):
    def __init__(self) -> None:
        super().__init__()
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.visible = True
        self.enabled = True
        self.hover = 0.0
        self._hovered = False
        self._pressed = False
    @property
    def hover_step(self) -> int:
        """Подсветка квантуется: и рисование, и ключ кэша обязаны использовать
        один и тот же шаг, иначе кэш не обновится вовремя."""
        return int(self.hover * 28) // 7

    def render_key(self, ctx: "UIContext") -> tuple:
        return super().render_key(ctx) + (self.hover_step, self._pressed, self.enabled, self.visible)

    def handle(self, event: pygame.event.Event, ctx: UIContext) -> bool:
        if not (self.visible and self.enabled):
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
                self.on_press(event.pos, ctx)
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._pressed:
            self._pressed = False
            if ctx.touch or getattr(event, "touch", False):
                self._hovered = False  # иначе кнопка «залипает» подсвеченной после касания
            # палец почти всегда чуть съезжает к моменту отпускания — даём допуск
            slack = ctx.px(18) if (ctx.touch or getattr(event, "touch", False)) else ctx.px(4)
            if self.rect.inflate(slack * 2, slack * 2).collidepoint(event.pos):
                self.on_click(event.pos, ctx)
            return True
        return False

    def on_press(self, pos, ctx: UIContext) -> None:
        pass

    def on_click(self, pos, ctx: UIContext) -> None:
        pass

    def update(self, dt: float, ctx: UIContext) -> None:
        self.hover = approach(self.hover, 1.0 if self._hovered else 0.0, 14.0, dt)

    @property
    def animating(self) -> bool:
        return 0.01 < self.hover < 0.99

    def draw(self, surf: pygame.Surface, ctx: UIContext) -> None:
        pass


class Button(Widget):
    def __init__(self, text: str, on_click: Callable[[], Any], kind: str = "primary",
                 icon: Optional[str] = None, font_size: float = 26) -> None:
        super().__init__()
        self.text = text
        self.callback = on_click
        self.kind = kind
        self.icon = icon
        self.font_size = font_size

    def render_key(self, ctx: UIContext) -> tuple:
        return super().render_key(ctx) + (self.text, self.kind, self.icon, self.font_size)

    def on_click(self, pos, ctx: UIContext) -> None:
        ctx.audio.play("click")
        self.callback()

    def draw(self, surf: pygame.Surface, ctx: UIContext) -> None:
        if not self.visible:
            return
        theme = ctx.theme
        if self.kind == "primary":
            base = theme.button + (255,)
        elif self.kind == "danger":
            base = (205, 70, 70, 255)
        else:
            base = (0, 0, 0, 70)
        color = lighten(base, self.hover_step * 7)
        rect = self.rect
        if self._pressed:
            rect = rect.inflate(-max(2, rect.w // 30), -max(2, rect.h // 12))
        radius = max(6, min(rect.h // 2, ctx.px(16)))
        if self.kind != "ghost":
            shadow = textures.rounded_panel(rect.size, (0, 0, 0, 50), radius)
            surf.blit(shadow, rect.move(0, ctx.px(3)))
        surf.blit(textures.rounded_panel(rect.size, color, radius), rect)
        if not self.enabled:
            surf.blit(textures.rounded_panel(rect.size, (0, 0, 0, 90), radius), rect)

        label = ctx.text(self.text, self.font_size, (255, 255, 255), bold=True) if self.text else None
        icon = textures.icon(self.icon, int(rect.h * 0.52), (255, 255, 255)) if self.icon else None
        total = (label.get_width() if label else 0) + (icon.get_width() if icon else 0) + \
            (ctx.px(8) if label and icon else 0)
        x = rect.centerx - total // 2
        if icon:
            surf.blit(icon, icon.get_rect(midleft=(x, rect.centery)))
            x += icon.get_width() + ctx.px(8)
        if label:
            surf.blit(label, label.get_rect(midleft=(x, rect.centery)))


class Toggle(Widget):
    def __init__(self, label: str, getter: Callable[[], bool], setter: Callable[[bool], None]) -> None:
        super().__init__()
        self.label, self.getter, self.setter = label, getter, setter
        self.knob = 1.0 if getter() else 0.0

    def on_click(self, pos, ctx: UIContext) -> None:
        ctx.audio.play("click")
        self.setter(not self.getter())

    def render_key(self, ctx: UIContext) -> tuple:
        return super().render_key(ctx) + (self.label, round(self.knob * 8))

    def update(self, dt, ctx):
        super().update(dt, ctx)
        self.knob = approach(self.knob, 1.0 if self.getter() else 0.0, 16.0, dt)

    @property
    def animating(self):
        return super().animating or 0.01 < self.knob < 0.99

    def draw(self, surf, ctx):
        _row_background(surf, self, ctx)
        lbl = ctx.text(self.label, 24)
        surf.blit(lbl, lbl.get_rect(midleft=(self.rect.x + ctx.px(14), self.rect.centery)))
        w, h = ctx.px(52), ctx.px(28)
        track = pygame.Rect(0, 0, w, h)
        track.midright = (self.rect.right - ctx.px(14), self.rect.centery)
        on_color = ctx.theme.button
        off_color = (90, 90, 100)
        color = tuple(int(off_color[i] + (on_color[i] - off_color[i]) * self.knob) for i in range(3))
        pygame.draw.rect(surf, color, track, border_radius=h // 2)
        knob_x = track.x + h // 2 + (w - h) * self.knob
        pygame.draw.circle(surf, (250, 250, 250), (int(knob_x), track.centery), h // 2 - ctx.px(3))


class Slider(Widget):
    def __init__(self, label: str, getter: Callable[[], float], setter: Callable[[float], None],
                 on_release: Optional[Callable[[], None]] = None) -> None:
        super().__init__()
        self.label, self.getter, self.setter = label, getter, setter
        self.on_release = on_release
        self._track = pygame.Rect(0, 0, 0, 0)

    def render_key(self, ctx: UIContext) -> tuple:
        return super().render_key(ctx) + (self.label, round(self.getter() * 100))

    def _set_from(self, x: int) -> None:
        if self._track.w > 0:
            self.setter(max(0.0, min(1.0, (x - self._track.x) / self._track.w)))

    def handle(self, event, ctx):
        if event.type == pygame.MOUSEMOTION and self._pressed:
            self._set_from(event.pos[0])
            return True
        was_pressed = self._pressed
        used = super().handle(event, ctx)
        if was_pressed and not self._pressed:
            if self.on_release:
                self.on_release()
        return used

    def on_press(self, pos, ctx):
        self._set_from(pos[0])

    def draw(self, surf, ctx):
        _row_background(surf, self, ctx)
        lbl = ctx.text(self.label, 24)
        surf.blit(lbl, lbl.get_rect(midleft=(self.rect.x + ctx.px(14), self.rect.centery)))
        value = self.getter()
        pct = ctx.text(f"{int(round(value * 100))}%", 20)
        surf.blit(pct, pct.get_rect(midright=(self.rect.right - ctx.px(14), self.rect.centery)))
        left = self.rect.x + max(lbl.get_width() + ctx.px(28), int(self.rect.w * 0.4))
        right = self.rect.right - ctx.px(24) - pct.get_width()
        self._track = pygame.Rect(left, self.rect.centery - ctx.px(3), max(10, right - left), ctx.px(6))
        pygame.draw.rect(surf, (90, 90, 100), self._track, border_radius=3)
        filled = self._track.copy()
        filled.w = int(self._track.w * value)
        pygame.draw.rect(surf, ctx.theme.button, filled, border_radius=3)
        pygame.draw.circle(surf, (250, 250, 250), (filled.right, self._track.centery), ctx.px(11))


class Selector(Widget):
    def __init__(self, label: str, options: Sequence[tuple[Any, str]], getter: Callable[[], Any],
                 setter: Callable[[Any], None], note: str = "") -> None:
        super().__init__()
        self.label, self.options, self.getter, self.setter = label, list(options), getter, setter
        self.note = note
        # зоны нажатия — расстояние от правого края строки до кромок стрелок.
        # Не абсолютные координаты: во время «запечки» на холст (ListScene)
        # self.rect временно в координатах холста, а не экрана, и абсолютный
        # прямоугольник тогда запоминался неправильно — тап по «<» не совпадал
        # с зоной ни разу и играло только «вперёд».
        self._back_from_right: tuple[int, int] = (0, 0)
        self._forward_from_right: tuple[int, int] = (0, 0)

    def render_key(self, ctx: UIContext) -> tuple:
        return super().render_key(ctx) + (self.label, self.note, self._index())

    def _index(self) -> int:
        values = [v for v, _ in self.options]
        cur = self.getter()
        return values.index(cur) if cur in values else 0

    def on_click(self, pos, ctx):
        ctx.audio.play("click")
        dx = self.rect.right - pos[0]                  # расстояние от правого края — не зависит от того,
        b0, b1 = self._back_from_right                 # в каких координатах сейчас self.rect (экран или холст)
        step = -1 if b0 <= dx <= b1 else 1
        self.setter(self.options[(self._index() + step) % len(self.options)][0])

    def draw(self, surf, ctx):
        _row_background(surf, self, ctx)
        lbl = ctx.text(self.label, 24)
        label_y = self.rect.centery - (ctx.px(8) if self.note else 0)
        lbl_rect = surf.blit(lbl, lbl.get_rect(midleft=(self.rect.x + ctx.px(14), label_y)))
        if self.note:
            note = ctx.text(self.note, 16, (225, 225, 225))
            surf.blit(note, note.get_rect(topleft=(lbl_rect.x, lbl_rect.bottom)))
        # стандартный шрифт pygame может не содержать «‹›», поэтому обычные < >
        value = ctx.text(self.options[self._index()][1], 24, bold=True)
        arrow_l = ctx.text("<", 28, bold=True)
        arrow_r = ctx.text(">", 28, bold=True)
        right = self.rect.right - ctx.px(14)
        r_rect = surf.blit(arrow_r, arrow_r.get_rect(midright=(right, self.rect.centery)))
        vx = right - arrow_r.get_width() - ctx.px(10)
        surf.blit(value, value.get_rect(midright=(vx, self.rect.centery)))
        l_rect = surf.blit(arrow_l, arrow_l.get_rect(
            midright=(vx - value.get_width() - ctx.px(10), self.rect.centery)))
        # палец толще стрелки — расширяем зоны, но так, чтобы они не пересеклись
        pad = ctx.px(16)
        right = self.rect.right
        self._back_from_right = (right - (l_rect.x + l_rect.w + pad), right - (l_rect.x - pad))
        self._forward_from_right = (right - (r_rect.x + r_rect.w + pad + ctx.px(14)), right - (r_rect.x - pad))

    @property
    def _back_rect(self) -> "pygame.Rect":
        x0, x1 = self._back_from_right
        return pygame.Rect(self.rect.right - x1, self.rect.y, x1 - x0, self.rect.h)

    @property
    def _forward_rect(self) -> "pygame.Rect":
        x0, x1 = self._forward_from_right
        return pygame.Rect(self.rect.right - x1, self.rect.y, x1 - x0, self.rect.h)


def _row_background(surf, widget: Widget, ctx: UIContext) -> None:
    alpha = 60 + widget.hover_step * 7
    surf.blit(textures.rounded_panel(widget.rect.size, (0, 0, 0, alpha), ctx.px(12)), widget.rect)

# ======================================================================
# blockblast/ui/drag.py
# ======================================================================

"""Перетаскивание фигур: плавное следование, «подъём» из лотка, магнитная
привязка к ближайшей допустимой позиции и возврат в лоток при промахе."""

from dataclasses import dataclass
from typing import Optional



@dataclass
class ReturnFlight:
    index: int
    piece: Piece
    start: tuple[float, float]
    start_cell: float
    target_cell: float
    tween: Tween

    def center(self, target: tuple[float, float]) -> tuple[float, float]:
        t = self.tween.value
        return lerp(self.start[0], target[0], t), lerp(self.start[1], target[1], t)

    def cell(self) -> float:
        return lerp(self.start_cell, self.target_cell, self.tween.value)


class DragController:
    def __init__(self) -> None:
        self.index: Optional[int] = None
        self.piece: Optional[Piece] = None
        self.pointer = (0.0, 0.0)
        self.center = [0.0, 0.0]
        self.cell_tween = Tween(1, 1, PICKUP_ANIM)
        self.returning: list[ReturnFlight] = []

    @property
    def active(self) -> bool:
        return self.index is not None

    def begin(self, index: int, piece: Piece, pointer, start_center, start_cell: float, board_cell: float) -> None:
        self.index, self.piece = index, piece
        self.pointer = pointer
        self.center = [float(start_center[0]), float(start_center[1])]
        self.cell_tween = Tween(start_cell, board_cell, PICKUP_ANIM, ease_out_cubic)
        self.returning = [f for f in self.returning if f.index != index]

    def move(self, pointer) -> None:
        self.pointer = pointer

    def target_center(self, layout: Layout) -> tuple[float, float]:
        return self.pointer[0], self.pointer[1] - DRAG_LIFT_CELLS * layout.cell

    def update(self, dt: float, layout: Layout) -> None:
        if self.active:
            self.cell_tween.update(dt)
            tx, ty = self.target_center(layout)
            self.center[0] = approach(self.center[0], tx, 35.0, dt)
            self.center[1] = approach(self.center[1], ty, 35.0, dt)
        for f in self.returning:
            f.tween.update(dt)
        self.returning = [f for f in self.returning if not f.tween.done]

    @property
    def cell(self) -> float:
        return self.cell_tween.value

    def resolve(self, game: Game, layout: Layout) -> Optional[tuple[int, int]]:
        """Куда встанет фигура: точная клетка или ближайшая допустимая в радиусе SNAP_RADIUS."""
        if not self.active or self.piece is None:
            return None
        shape = self.piece.shape
        cx, cy = self.target_center(layout)
        if not layout.board.inflate(layout.cell, layout.cell).collidepoint(cx, cy):
            return None
        ox, oy = layout.grid_origin
        rf = (cy - shape.rows * layout.cell / 2 - oy) / layout.cell
        cf = (cx - shape.cols * layout.cell / 2 - ox) / layout.cell
        base_r, base_c = round(rf), round(cf)
        if game.board.can_place(shape, base_r, base_c):
            return base_r, base_c
        candidates = [
            (base_r + dr, base_c + dc)
            for dr in range(-SNAP_RADIUS, SNAP_RADIUS + 1)
            for dc in range(-SNAP_RADIUS, SNAP_RADIUS + 1)
            if dr or dc
        ]
        candidates.sort(key=lambda p: (p[0] - rf) ** 2 + (p[1] - cf) ** 2)
        for r, c in candidates:
            if (r - rf) ** 2 + (c - cf) ** 2 <= 0.85 ** 2 and game.board.can_place(shape, r, c):
                return r, c
        return None

    def drop(self) -> tuple[Optional[int], Optional[Piece]]:
        idx, piece = self.index, self.piece
        self.index, self.piece = None, None
        return idx, piece

    def cancel_to_tray(self, tray_cell: float) -> None:
        if self.index is None or self.piece is None:
            return
        self.returning.append(ReturnFlight(self.index, self.piece, (self.center[0], self.center[1]),
                                           self.cell, tray_cell, Tween(0, 1, RETURN_ANIM, ease_out_cubic)))
        self.index, self.piece = None, None

    def is_hidden(self, index: int) -> bool:
        return index == self.index or any(f.index == index for f in self.returning)

    def clear(self) -> None:
        self.index, self.piece = None, None
        self.returning.clear()

# ======================================================================
# blockblast/scenes/base.py
# ======================================================================

"""Базовые классы сцен."""

from typing import TYPE_CHECKING

import pygame


if TYPE_CHECKING:
    pass


class Scene:
    def __init__(self, app: "App") -> None:
        self.app = app
        self.widgets: list[Widget] = []
        # прямоугольники, которые поверх сцены рисует само приложение
        # (счётчик FPS, плашки достижений) — сцена должна их потом стереть
        self.external_rects: list = []

    @property
    def ui(self):
        return self.app.ui

    def on_enter(self) -> None:
        self.layout()

    def on_exit(self) -> None:
        pass

    def on_quit(self) -> None:
        self.on_exit()

    def layout(self) -> None:
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        for w in reversed(self.widgets):
            if w.handle(event, self.ui):
                break

    def update(self, dt: float) -> None:
        for w in self.widgets:
            w.update(dt, self.ui)

    @property
    def animating(self) -> bool:
        return any(w.animating for w in self.widgets)

    def draw(self, surf: pygame.Surface) -> None:
        textures.draw_background(surf, self.ui.theme, self.ui.simple_bg)
        for w in self.widgets:
            w.draw(surf, self.ui)


class ListScene(Scene):
    """Экран-список с заголовком, кнопкой «назад» и прокруткой (колесо/перетаскивание)."""

    title = ""
    row_height = 64

    def __init__(self, app: "App", back_to: Scene) -> None:
        super().__init__(app)
        self.back_to = back_to
        self.scroll = 0.0
        self.scroll_target = 0.0
        self.content_h = 0
        self.viewport = pygame.Rect(0, 0, 0, 0)
        self._drag_y = None
        self._drag_moved = 0
        self._rows: list = []
        self._base: "pygame.Surface | None" = None
        self._base_key: tuple = ()
        self._canvas: "pygame.Surface | None" = None
        self._canvas_key: tuple = ()
        self._row_keys: dict = {}
        self._drawn_scroll = None
        self._rows_dirty = True
        self._full = True
        self.back_button = Button("", self.go_back, kind="secondary", icon="back")

    @property
    def scroll_slop(self) -> int:
        """Насколько можно сдвинуть палец, чтобы это всё ещё считалось нажатием."""
        return self.ui.px(22)

    def go_back(self) -> None:
        self.app.switch(self.back_to)

    # --- подклассы ---
    def build_rows(self) -> list:
        """Создаёт строки: виджеты или любые объекты с .rect и .draw(surf, ui)."""
        return []

    def rows(self) -> list:
        return self._rows

    def rebuild(self) -> None:
        self._rows = self.build_rows()
        self._full = True
        self._canvas = None
        self._row_keys.clear()
        self.layout()

    def on_enter(self) -> None:
        self.rebuild()

    def header_height(self) -> int:
        return self.ui.px(84)

    # --- раскладка ---
    def layout(self) -> None:
        w, h = self.app.screen.get_size()
        ui = self.ui
        ui.scale = ui_scale(w, h)
        pad = ui.px(16)
        top = pad + ui.safe_top
        content_w = min(w - 2 * pad, ui.px(560))
        left = (w - content_w) // 2
        self.back_button.rect = pygame.Rect(pad, top, ui.px(48), ui.px(48))
        self.viewport = pygame.Rect(left, self.header_height() + top, content_w, h - self.header_height() - top - pad)
        rows = self.rows()
        gap = ui.px(8)
        rh = ui.px(self.row_height)
        self.content_h = len(rows) * (rh + gap)
        self._clamp()
        y = self.viewport.y - int(self.scroll)
        for row in rows:
            row.rect = pygame.Rect(left, y, content_w, rh)
            y += rh + gap
        self.widgets = [r for r in rows if isinstance(r, Widget)] + [self.back_button]

    def _ensure_base(self, surf: pygame.Surface) -> pygame.Surface:
        """Фон + заголовок: меняется только при смене темы или размера окна."""
        ui = self.ui
        key = (surf.get_size(), ui.theme.id, self.title, round(ui.scale, 3), self.header_height())
        if self._base is None or key != self._base_key:
            base = pygame.Surface(surf.get_size())
            # однотонный фон (а не градиент): тогда строки списка можно запечь
            # один раз и двигать при прокрутке, не пересобирая
            base.fill(ui.theme.bg)
            title = ui.text(self.title, 40, ui.theme.text, bold=True)
            base.blit(title, title.get_rect(center=(base.get_width() // 2, self.back_button.rect.centery)))
            self.draw_header_extra(base)
            self._base, self._base_key = base.convert(), key
            self._full = True
        return self._base

    def _clamp(self) -> None:
        max_scroll = max(0, self.content_h - self.viewport.h)
        self.scroll_target = max(0.0, min(self.scroll_target, max_scroll))
        self.scroll = max(0.0, min(self.scroll, max_scroll))

    # --- события ---
    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.go_back()
            return
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_target -= event.y * self.ui.px(60)
            self._clamp()
            return
        if event.type == pygame.MOUSEMOTION and self._drag_y is not None:
            dy = event.pos[1] - self._drag_y
            self._drag_y = event.pos[1]
            self._drag_moved += abs(dy)
            if self.content_h <= self.viewport.h:      # прокручивать нечего — это точно нажатие
                return super().handle_event(event)
            self.scroll_target -= dy
            self.scroll = self.scroll_target
            self._clamp()
            self.layout()
            if self._drag_moved > self.scroll_slop:
                return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # счётчик сдвига сбрасываем на КАЖДОМ нажатии: иначе после прокрутки
            # списка следующее нажатие (например, по кнопке «назад») считалось
            # продолжением прокрутки и пропадало
            self._drag_moved = 0
            self._drag_y = event.pos[1] if self.viewport.collidepoint(event.pos) else None
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            scrolled = self._drag_y is not None and self._drag_moved > self.scroll_slop
            self._drag_y = None
            self._drag_moved = 0
            if scrolled:            # это была прокрутка, а не нажатие
                for w in self.widgets:
                    w._pressed = False
                return
        if event.type == pygame.MOUSEBUTTONDOWN and not (
                self.viewport.collidepoint(event.pos) or self.back_button.rect.collidepoint(event.pos)):
            return
        super().handle_event(event)

    def update(self, dt) -> None:
        if abs(self.scroll - self.scroll_target) > 0.5:
            self.scroll = approach(self.scroll, self.scroll_target, 14.0, dt)
            self.layout()
        super().update(dt)

    @property
    def animating(self) -> bool:
        return super().animating or abs(self.scroll - self.scroll_target) > 0.5

    def _ensure_canvas(self) -> pygame.Surface:
        """Содержимое списка на отдельном холсте: прокрутка — это показ его куска,
        а не перерисовка строк (иначе каждый кадр пересобирается десяток текстур)."""
        ui = self.ui
        rows = self.rows()
        height = max(self.viewport.h, self.content_h + ui.px(8))
        key = (self.viewport.w, height, ui.theme.id, round(ui.scale, 3), len(rows))
        if self._canvas is None or key != self._canvas_key:
            canvas = pygame.Surface((self.viewport.w, height))
            canvas.fill(ui.theme.bg)
            self._canvas, self._canvas_key = canvas.convert(), key
            self._row_keys.clear()

        for row in rows:                       # в холст попадают только изменившиеся строки
            key = row.render_key(ui) if hasattr(row, "render_key") else id(row)
            if self._row_keys.get(id(row)) == key:
                continue
            self._row_keys[id(row)] = key
            self._rows_dirty = True
            local = row.rect.move(-self.viewport.x, -self.viewport.y + int(self.scroll))
            saved, row.rect = row.rect, local
            try:
                self._canvas.fill(ui.theme.bg, local.union(local.move(0, ui.px(6))))
                row.draw(self._canvas, ui)
            finally:
                row.rect = saved
        return self._canvas

    def draw(self, surf) -> None:
        ui = self.ui
        base = self._ensure_base(surf)
        external = [pygame.Rect(r) for r in self.external_rects]
        if self._full or ui.no_bake:
            surf.blit(base, (0, 0))

        if ui.no_bake:                          # эталон для теста: строки рисуются напрямую
            surf.set_clip(self.viewport.inflate(ui.px(8), 0))
            for row in self.rows():
                if row.rect.bottom >= self.viewport.top - ui.px(8) and row.rect.top <= self.viewport.bottom:
                    row.draw(surf, ui)
            surf.set_clip(None)
            self.back_button.draw(surf, ui)
            self._full = False
            return

        if not self._full:
            for r in external:      # стираем то, что приложение рисует поверх сцены
                surf.blit(base, r, r)

        canvas = self._ensure_canvas()
        scroll = int(self.scroll)
        moved = self._full or scroll != self._drawn_scroll
        touched = any(r.colliderect(self.viewport) for r in external)
        if moved or touched or self._rows_dirty:
            src = pygame.Rect(0, scroll, self.viewport.w, self.viewport.h)
            surf.blit(canvas, self.viewport, src)
            self._drawn_scroll = scroll
        self._rows_dirty = False

        if (self._full or self.back_button.needs_redraw(ui)
                or any(r.colliderect(self.back_button.rect) for r in external)):
            self.back_button.draw_baked(surf, ui, base, bg_color=ui.theme.bg)
        self._full = False

    def draw_header_extra(self, surf) -> None:
        pass

# ======================================================================
# blockblast/scenes/menu.py
# ======================================================================

"""Главное меню."""

import math
import random

import pygame



class FallingPiece:
    __slots__ = ("shape", "color", "x", "y", "speed", "angle")

    def __init__(self, rng: random.Random, w: int, h: int, spread: bool):
        self.shape = rng.choice(SHAPES)
        self.color = rng.randrange(PALETTE_SLOTS)
        self.x = rng.uniform(0, w)
        self.y = rng.uniform(-h, h) if spread else rng.uniform(-h * 0.3, -40)
        self.speed = rng.uniform(25, 60)


class MenuScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.rng = random.Random()
        self.falling: list[FallingPiece] = []
        self.time = 0.0
        self.saved = None
        self._base: "pygame.Surface | None" = None
        self._base_key: tuple = ()
        self._prev_rects: list[pygame.Rect] = []
        self._full = True

    def on_enter(self) -> None:
        self.saved = self.app.load_saved_game()
        w, h = self.app.screen.get_size()
        self.falling = [FallingPiece(self.rng, w, h, True) for _ in range(9)]
        super().on_enter()

    def layout(self) -> None:
        w, h = self.app.screen.get_size()
        ui = self.ui
        ui.scale = ui_scale(w, h)
        pass
        pass
        pass
        pass

        buttons = []
        if self.saved is not None:
            saved = self.saved
            buttons.append(Button(f"Продолжить  ·  {saved.score}",
                                  lambda: self.app.switch(GameScene(self.app, saved)), "primary"))
        buttons += [
            Button("Новая игра", lambda: self.app.switch(self.app.new_game()),
                   "secondary" if self.saved else "primary"),
            Button("Рекорды", lambda: self.app.switch(RecordsScene(self.app, self)), "secondary"),
            Button("Достижения", lambda: self.app.switch(AchievementsScene(self.app, self)), "secondary"),
            Button("Настройки", lambda: self.app.switch(SettingsScene(self.app, self)), "secondary"),
            Button("Выход", self.app.quit, "secondary"),
        ]
        bw = min(w - ui.px(60), ui.px(320))
        bh = ui.px(56)
        gap = ui.px(12)
        total = len(buttons) * (bh + gap) - gap
        top = max(int(h * 0.36), (h - total) // 2 + ui.px(60))
        top = min(top, h - total - ui.px(50))
        for i, b in enumerate(buttons):
            b.rect = pygame.Rect((w - bw) // 2, top + i * (bh + gap), bw, bh)
        self.widgets = buttons
        self._full = True
        self.title_y = max(ui.px(40) + ui.safe_top, top - ui.px(150))

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.widgets[0].callback()
                return
            if event.key == pygame.K_ESCAPE:
                self.app.quit()
                return
        super().handle_event(event)

    def update(self, dt: float) -> None:
        super().update(dt)
        self.time += dt
        w, h = self.app.screen.get_size()
        for i, p in enumerate(self.falling):
            p.y += p.speed * dt * self.ui.scale
            if p.y > h + 60:
                self.falling[i] = FallingPiece(self.rng, w, h, False)

    @property
    def animating(self) -> bool:
        return True  # фон постоянно движется

    def _ensure_base(self, surf: pygame.Surface) -> pygame.Surface:
        """Фон, заголовок и подпись снизу — всё, что не двигается."""
        ui, theme = self.ui, self.ui.theme
        s = self.app.settings
        info_text = f"{MODE_NAMES[s.mode]}  ·  {s.board_size}×{s.board_size}  ·  {DIFFICULTY_NAMES[s.difficulty]}"
        key = (surf.get_size(), theme.id, round(ui.scale, 3), self.title_y, info_text, ui.simple_bg)
        if self._base is None or key != self._base_key:
            base = pygame.Surface(surf.get_size())
            textures.draw_background(base, theme, ui.simple_bg)
            title = ui.text("Block Blast", 64, theme.text, bold=True)
            shadow = ui.text("Block Blast", 64, (40, 40, 40), bold=True)
            rect = title.get_rect(center=(base.get_width() // 2, self.title_y))
            base.blit(shadow, rect.move(ui.px(3), ui.px(4)))
            base.blit(title, rect)
            info = ui.text(info_text, 20, theme.text)
            base.blit(info, info.get_rect(center=(base.get_width() // 2,
                                                  self.widgets[-1].rect.bottom + ui.px(26))))
            self._base, self._base_key = base.convert(), key
            self._full = True
        return self._base

    def draw(self, surf: pygame.Surface) -> None:
        ui, theme = self.ui, self.ui.theme
        base = self._ensure_base(surf)
        if self._full or ui.no_bake:
            surf.blit(base, (0, 0))
            self._prev_rects = []
        else:
            for r in self._prev_rects:
                surf.blit(base, r, r)
        damage = list(self._prev_rects) + [pygame.Rect(r) for r in self.external_rects]
        if not self._full:
            for r in self.external_rects:      # стираем счётчик FPS и плашки прошлого кадра
                r = pygame.Rect(r)
                surf.blit(base, r, r)
        self._prev_rects = []

        cell = ui.px(22)
        for p in self.falling:                      # падающие фигуры — единственная анимация
            tex = textures.piece_ghost(theme, p.shape, p.color, cell, 90)
            rect = surf.blit(tex, tex.get_rect(center=(int(p.x), int(p.y))))
            self._prev_rects.append(rect)
        damage += self._prev_rects

        size = ui.px(26)                            # «прыгающие» блоки под заголовком
        blocks_y = self.title_y + ui.px(46)
        for i in range(5):
            bounce = abs(math.sin(self.time * 3 + i * 0.6)) * ui.px(10)
            blk = textures.block(theme, i, size)
            x = surf.get_width() // 2 + (i - 2) * (size + ui.px(6)) - size // 2
            rect = surf.blit(blk, (x, blocks_y - int(bounce)))
            self._prev_rects.append(rect.union(rect.move(0, ui.px(10))))
        damage += self._prev_rects

        for widget in self.widgets:                 # кнопки: один непрозрачный блит каждая
            if ui.no_bake:   # эталон для теста: та же картинка, но без кэша
                area = widget.bake_rect(ui).clip(surf.get_rect())
                surf.blit(base, area, area)
                widget.draw(surf, ui)
            elif (self._full or widget.needs_redraw(ui)
                  or any(r.colliderect(widget.bake_rect(ui)) for r in damage)):
                widget.draw_baked(surf, ui, base)
        self._full = False

# ======================================================================
# blockblast/scenes/settings_scene.py
# ======================================================================

"""Настройки: тема, режим, сложность, размер поля, звук, анимации, экран."""

import time



class SettingsScene(ListScene):
    title = "Настройки"
    row_height = 62

    def __init__(self, app, back_to) -> None:
        super().__init__(app, back_to)
        self._reset_armed_at = 0.0
        self.reset_button: Button | None = None

    def build_rows(self) -> list:
        app, s = self.app, self.app.settings
        in_game = hasattr(self.back_to, "game")
        note = "со следующей игры" if in_game else ""

        def set_theme(value):
            app.themes.set(value)
            s.theme = app.themes.setting
            app.notify_achievements(app.achievements.on_theme(app.themes.current.id))

        def set_attr(name):
            def setter(value):
                setattr(s, name, value)
            return setter

        def set_sfx(v):
            s.sfx_volume = v
            app.audio.set_sfx_volume(v)

        def set_music(v):
            s.music_volume = v
            app.audio.set_music_volume(v)

        self.reset_button = Button("Сбросить рекорды", self._reset_records, "danger", font_size=22)
        rows = [
            Selector("Тема", [(t.id, t.name) for t in THEMES] + [("auto", "Авто")], lambda: app.themes.setting, set_theme),
            Selector("Режим", [(m, MODE_NAMES[m]) for m in MODES], lambda: s.mode, set_attr("mode"), note),
            Selector("Сложность", [(d, DIFFICULTY_NAMES[d]) for d in DIFFICULTIES], lambda: s.difficulty,
                     set_attr("difficulty"), note),
            Selector("Размер поля", [(n, f"{n}×{n}") for n in BOARD_SIZES], lambda: s.board_size,
                     set_attr("board_size"), note),
            Selector("Качество", [(q, QUALITY_NAMES[q]) for q in QUALITY_LEVELS], lambda: s.quality,
                     app.set_quality, "«Родное» — самый чёткий текст, ниже — выше FPS"),
            Slider("Звуки", lambda: s.sfx_volume, set_sfx, on_release=lambda: app.audio.play("place")),
            Slider("Музыка", lambda: s.music_volume, set_music),
            Toggle("Подсказки", lambda: s.hints, set_attr("hints")),
            Toggle("Полные анимации", lambda: s.full_animations, set_attr("full_animations")),
            Toggle("Тряска экрана", lambda: s.screen_shake, set_attr("screen_shake")),
            Toggle("Полноэкранный режим (F11)", lambda: s.fullscreen, app.set_fullscreen),
            Toggle("Показывать FPS", lambda: s.show_fps, set_attr("show_fps")),
            self.reset_button,
        ]
        if IS_ANDROID:  # на телефоне игра и так на весь экран
            rows = [r for r in rows if not (isinstance(r, Toggle) and r.label.startswith("Полноэкранный"))]
        return rows

    def _reset_records(self) -> None:
        now = time.monotonic()
        if now - self._reset_armed_at > 3.0:
            self._reset_armed_at = now
            self.reset_button.text = "Точно? Нажми ещё раз"
            return
        self.app.profile.highscores.clear()
        self.app.storage.save_profile(self.app.profile)
        self.reset_button.text = "Рекорды сброшены"
        self.reset_button.enabled = False

    def update(self, dt: float) -> None:
        super().update(dt)
        if (self.reset_button and self.reset_button.enabled and self._reset_armed_at
                and time.monotonic() - self._reset_armed_at > 3.0):
            self._reset_armed_at = 0.0
            self.reset_button.text = "Сбросить рекорды"

    def on_exit(self) -> None:
        self.app.storage.save_settings(self.app.settings)

# ======================================================================
# blockblast/scenes/records.py
# ======================================================================

"""Таблица рекордов (отдельная для каждого режима, размера поля и сложности)."""

import pygame



class RecordRow(BakedDrawable):
    def __init__(self, rank: int, entry: dict, show_level: bool) -> None:
        super().__init__()
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.rank, self.entry, self.show_level = rank, entry, show_level

    def render_key(self, ctx) -> tuple:
        return super().render_key(ctx) + (self.rank, self.entry["score"], self.show_level)

    def draw(self, surf, ui) -> None:
        theme = ui.theme
        top3 = self.rank <= 3
        surf.blit(textures.rounded_panel(self.rect.size, (0, 0, 0, 90 if top3 else 55), ui.px(12)), self.rect)
        cy = self.rect.centery
        medal = [(255, 205, 60), (210, 215, 225), (205, 140, 80)]
        rank = ui.text(f"{self.rank}", 30, medal[self.rank - 1] if top3 else theme.text, bold=True)
        surf.blit(rank, rank.get_rect(center=(self.rect.x + ui.px(30), cy)))
        score = ui.text(str(self.entry["score"]), 30, theme.accent if top3 else theme.text, bold=True)
        surf.blit(score, score.get_rect(midleft=(self.rect.x + ui.px(64), cy)))
        details = f"Уровень {self.entry.get('level', 0)}" if self.show_level else f"Линий: {self.entry.get('lines', 0)}"
        d = ui.text(details, 18, theme.text)
        date = ui.text(self.entry.get("date", ""), 16, (225, 225, 225))
        right = self.rect.right - ui.px(14)
        surf.blit(d, d.get_rect(bottomright=(right, cy)))
        surf.blit(date, date.get_rect(topright=(right, cy + ui.px(2))))


class EmptyRow(BakedDrawable):
    def __init__(self) -> None:
        super().__init__()
        self.rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surf, ui) -> None:
        t = ui.text("Пока нет результатов. Сыграй!", 24, ui.theme.text)
        surf.blit(t, t.get_rect(center=self.rect.center))


class RecordsScene(ListScene):
    title = "Рекорды"
    row_height = 60

    def __init__(self, app, back_to) -> None:
        super().__init__(app, back_to)
        s = app.settings
        self.mode, self.size, self.difficulty = s.mode, s.board_size, s.difficulty

    def _setter(self, name):
        def set_value(value):
            setattr(self, name, value)
            self.rebuild()
        return set_value

    def build_rows(self) -> list:
        rows: list = [
            Selector("Режим", [(m, MODE_NAMES[m]) for m in MODES], lambda: self.mode, self._setter("mode")),
            Selector("Поле", [(n, f"{n}×{n}") for n in BOARD_SIZES], lambda: self.size, self._setter("size")),
            Selector("Сложность", [(d, DIFFICULTY_NAMES[d]) for d in DIFFICULTIES], lambda: self.difficulty,
                     self._setter("difficulty")),
        ]
        board = self.app.profile.leaderboard(leaderboard_key(self.mode, self.size, self.difficulty))
        if not board:
            rows.append(EmptyRow())
        rows += [RecordRow(i + 1, e, self.mode == "levels") for i, e in enumerate(board)]
        return rows

# ======================================================================
# blockblast/scenes/achievements_scene.py
# ======================================================================

"""Список достижений с прогрессом."""

import pygame



class AchievementRow(BakedDrawable):
    def __init__(self, achievement: Achievement, tracker) -> None:
        super().__init__()
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.a = achievement
        self.tracker = tracker

    def render_key(self, ctx) -> tuple:
        return super().render_key(ctx) + (self.a.id, self.tracker.is_unlocked(self.a),
                                          self.tracker.progress(self.a))

    def draw(self, surf, ui) -> None:
        theme = ui.theme
        unlocked = self.tracker.is_unlocked(self.a)
        surf.blit(textures.rounded_panel(self.rect.size, (0, 0, 0, 95 if unlocked else 55), ui.px(12)), self.rect)
        icon_size = ui.px(34)
        icon = textures.icon("star" if unlocked else "lock", icon_size,
                             (255, 205, 60) if unlocked else (150, 150, 160))
        surf.blit(icon, icon.get_rect(center=(self.rect.x + ui.px(30), self.rect.centery)))

        x = self.rect.x + ui.px(58)
        title = ui.text(self.a.title, 24, theme.text if unlocked else (215, 215, 215), bold=True)
        desc = ui.text(self.a.description, 17, (230, 230, 230) if unlocked else (190, 190, 190))
        surf.blit(title, (x, self.rect.y + ui.px(9)))
        surf.blit(desc, (x, self.rect.y + ui.px(9) + title.get_height()))

        right = self.rect.right - ui.px(14)
        if unlocked:
            date = ui.text(self.tracker.profile.achievements.get(self.a.id, ""), 16, theme.accent)
            surf.blit(date, date.get_rect(midright=(right, self.rect.centery)))
        elif self.a.target > 1:
            cur, target = self.tracker.progress(self.a)
            label = ui.text(f"{cur}/{target}", 16, (220, 220, 220))
            surf.blit(label, label.get_rect(bottomright=(right, self.rect.centery)))
            bar = pygame.Rect(0, 0, ui.px(80), ui.px(6))
            bar.topright = (right, self.rect.centery + ui.px(4))
            pygame.draw.rect(surf, (40, 40, 50), bar, border_radius=3)
            fill = bar.copy()
            fill.w = int(bar.w * cur / target)
            if fill.w:
                pygame.draw.rect(surf, theme.accent, fill, border_radius=3)


class AchievementsScene(ListScene):
    title = "Достижения"
    row_height = 72

    def build_rows(self) -> list:
        tracker = self.app.achievements
        rows = [AchievementRow(a, tracker) for a in ACHIEVEMENTS]
        rows.sort(key=lambda r: not tracker.is_unlocked(r.a))  # полученные сверху
        return rows

    def header_height(self) -> int:
        return self.ui.px(110)

    def draw_header_extra(self, surf) -> None:
        done = len([a for a in ACHIEVEMENTS if self.app.achievements.is_unlocked(a)])
        t = self.ui.text(f"Получено {done} из {len(ACHIEVEMENTS)}", 22, self.ui.theme.accent, bold=True)
        surf.blit(t, t.get_rect(center=(surf.get_width() // 2, self.back_button.rect.bottom + self.ui.px(24))))

# ======================================================================
# blockblast/scenes/game_scene.py
# ======================================================================

"""Игровая сцена: ввод, обработка событий логики, пауза, конец игры, автосохранение."""

from typing import Optional

import pygame



class GameScene(Scene):
    def __init__(self, app, game: Game) -> None:
        super().__init__(app)
        self.game = game
        self.view = GameView(app.ui)
        self.drag = DragController()
        self.best = app.best_for(game)
        self.paused = False
        self.over_timer = 0.0
        self.over_info: Optional[dict] = None
        self.overlay_tween = Tween(0, 1, 0.3, ease_out_back)
        self.save_dirty = False
        self.save_timer = 0.0

        self.pause_btn = Button("", self.pause, "secondary", icon="pause")
        self.hint_btn = Button("", self.request_hint, "secondary", icon="hint")
        self.overlay_buttons: list[Button] = []
        self._overlay: Optional[pygame.Surface] = None
        self._overlay_key: tuple = ()
        self._overlay_base_y: list[int] = []
        self._panel: Optional[pygame.Surface] = None
        self._panel_key: tuple = ()
        self._panel_dest: Optional[pygame.Rect] = None
        self._full = True
        self.view.reset(game)

    # ---------- жизненный цикл ----------

    def on_enter(self) -> None:
        self.view.full_animations = self.app.settings.full_animations
        self.view.force_full()
        # настройки могли поменять тему/режим игры; размер поля берём у самой игры
        self.layout()

    def on_exit(self) -> None:
        self.drag.clear()
        self._save_now(sync=True)      # уходим со сцены — дописываем сразу

    def on_background(self) -> None:
        """Android свернул приложение: ставим на паузу и сохраняем немедленно."""
        if not self.game.over and self.over_info is None:
            if not self.paused:
                self.pause()
            self.save_dirty = True
            self._save_now(sync=True)      # система может убить приложение в любой момент

    def on_focus_lost(self) -> None:
        if self.drag.active:
            self.drag.cancel_to_tray(self.view.tray_cell_for(self.drag.piece))

    def layout(self) -> None:
        w, h = self.app.screen.get_size()
        L = compute_layout(w, h, self.game.board.size, self.ui.safe_top)
        self.view.set_layout(L)
        self.pause_btn.rect = L.pause_button
        self.hint_btn.rect = L.hint_button
        self.hint_btn.visible = self.app.settings.hints
        self._build_overlay()

    # ---------- действия ----------

    def pause(self) -> None:
        if self.game.over:
            return
        self.drag.clear()
        self.paused = True
        self.overlay_tween = Tween(0, 1, 0.25, ease_out_back)
        self._build_overlay()
        self._save_now()

    def resume(self) -> None:
        self.paused = False
        self.view.force_full()
        self._build_overlay()

    def restart(self) -> None:
        self.app.switch(self.app.new_game())

    def to_menu(self) -> None:
        pass
        self.app.switch(MenuScene(self.app))

    def open_settings(self) -> None:
        pass
        self.app.switch(SettingsScene(self.app, self))

    def request_hint(self) -> None:
        if not self.app.settings.hints or self.game.over:
            return
        move = self.game.hint()
        self.view.show_hint(move, self.game)
        if move is None:
            self.app.audio.play("invalid")

    # ---------- оверлеи ----------

    def _build_overlay(self) -> None:
        L = self.view.layout
        if L is None:
            return
        if self.paused:
            spec = [("Продолжить", self.resume, "primary"), ("Заново", self.restart, "secondary"),
                    ("Настройки", self.open_settings, "secondary"), ("В меню", self.to_menu, "secondary")]
        elif self.over_info is not None:
            spec = [("Ещё раз", self.restart, "primary"), ("В меню", self.to_menu, "secondary")]
        else:
            self.overlay_buttons = []
            return
        bw, bh, gap = min(L.width - L.px(80), L.px(280)), L.px(54), L.px(12)
        top = L.height // 2 + (L.px(70) if self.over_info else -L.px(40))
        self.overlay_buttons = []
        self._overlay_base_y = []
        for i, (text, cb, kind) in enumerate(spec):
            b = Button(text, cb, kind)
            b.rect = pygame.Rect((L.width - bw) // 2, top + i * (bh + gap), bw, bh)
            self.overlay_buttons.append(b)
            self._overlay_base_y.append(b.rect.y)
        self._overlay = None
        self._panel = None
        self._panel_dest = None

    def _show_game_over(self) -> None:
        g, p = self.game, self.app.profile
        key = leaderboard_key(g.mode_id, g.board.size, g.difficulty)
        prev_best = p.best(key)
        level = getattr(g.mode, "level", 0)
        rank = p.add_score(key, g.score, g.lines_total, level)
        self.over_info = {"rank": rank, "new_record": g.score > prev_best and g.score > 0,
                          "score": g.score, "lines": g.lines_total, "level": level}
        self.app.storage.save_profile(p)
        self.app.storage.delete_game()
        self.app.audio.play("game_over")
        self.overlay_tween = Tween(0, 1, 0.45, ease_out_back)
        self._build_overlay()

    # ---------- ввод ----------

    def handle_event(self, event) -> None:
        if self.paused or self.over_info is not None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and self.paused:
                    self.resume()
                elif event.key in (pygame.K_r, pygame.K_RETURN) and self.over_info is not None:
                    self.restart()
                return
            for b in self.overlay_buttons:
                if b.handle(event, self.ui):
                    return
            return

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.pause()
            elif event.key == pygame.K_h:
                self.request_hint()
            elif event.key == pygame.K_t:
                self.app.themes.next()
                self.app.settings.theme = self.app.themes.setting
                self.app.notify_achievements(self.app.achievements.on_theme(self.app.themes.current.id))
            return

        for b in (self.pause_btn, self.hint_btn):
            if b.handle(event, self.ui):
                return

        L = self.view.layout
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.drag.active:
            idx = self.view.tray_index_at(event.pos, self.game)
            if idx is not None:
                piece = self.game.tray[idx]
                self.drag.begin(idx, piece, event.pos, L.tray_slots[idx].center,
                                self.view.tray_cell_for(piece), L.cell)
                self.view.hint = None
                self.app.audio.play("pick")
        elif event.type == pygame.MOUSEMOTION and self.drag.active:
            self.drag.move(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.drag.active:
            self.drag.move(event.pos)
            target = self.drag.resolve(self.game, L)
            if target is not None:
                idx, _ = self.drag.drop()
                if self.game.place(idx, *target) is not None:
                    self._process_game_events()
                    return
            if L.board.inflate(L.cell, L.cell).collidepoint(self.drag.target_center(L)):
                self.app.audio.play("invalid")
            self.drag.cancel_to_tray(self.view.tray_cell_for(self.drag.piece))

    # ---------- события логики ----------

    def _process_game_events(self) -> None:
        app, game = self.app, self.game
        unlocked = []
        self.save_dirty = True
        for event in game.drain_events():
            self.view.on_event(event, game, app.settings.screen_shake)
            unlocked += app.achievements.on_event(event, game)
            if isinstance(event, ev.PiecePlaced):
                app.audio.play("place")
            elif isinstance(event, ev.LinesCleared):
                app.audio.play("clear", event.move.lines)
                if event.move.streak >= 2:
                    app.audio.play("combo", event.move.streak)
                if app.themes.on_clear():
                    unlocked += app.achievements.on_theme(app.themes.current.id)
            elif isinstance(event, ev.PerfectClear):
                app.audio.play("perfect")
            elif isinstance(event, ev.LevelUp):
                app.audio.play("level_up")
        app.notify_achievements(unlocked)

    # ---------- обновление ----------

    def update(self, dt: float) -> None:
        L = self.view.layout
        self.view.update(dt, self.game)
        self.drag.update(dt, L)
        for b in (self.pause_btn, self.hint_btn, *self.overlay_buttons):
            b.update(dt, self.ui)
        if self.paused or self.over_info is not None:
            self.overlay_tween.update(dt)

        if self.game.over and self.over_info is None:
            self.over_timer += dt
            if self.over_timer >= GAME_OVER_DELAY and not self.view.effects_settling:
                self._show_game_over()

        self.save_timer += dt
        if self.save_dirty and self.save_timer >= AUTOSAVE_INTERVAL:
            self._save_now()

    def _save_now(self, sync: bool = False) -> None:
        self.save_timer = 0.0
        if self.game.over:
            return
        if self.save_dirty or self.paused:
            self.app.storage.save_game(self.game.to_data(), background=not sync)
            self.save_dirty = False

    @property
    def animating(self) -> bool:
        return (self.view.busy or self.drag.active or bool(self.drag.returning) or self.game.over
                or any(b.animating for b in (self.pause_btn, self.hint_btn, *self.overlay_buttons))
                or not self.overlay_tween.done)

    # ---------- отрисовка ----------

    def draw(self, surf: pygame.Surface) -> None:
        if self.paused or self.over_info is not None:
            self._draw_overlay_screen(surf)
            self._full = False
            return
        self._full = False
        shadow = self.ui.px(4)
        extra = [b.rect.union(b.rect.move(0, shadow)) for b in (self.hint_btn, self.pause_btn) if b.visible]
        extra += list(self.external_rects)
        self.view.draw(surf, self.game, self.drag, self.best, self.app.settings.hints, extra)
        self.hint_btn.draw(surf, self.ui)
        self.pause_btn.draw(surf, self.ui)

    def _overlay_content(self) -> tuple:
        if self.paused:
            return "Пауза", []
        info = self.over_info or {}
        lines = [(f"{info.get('score', 0)}", 64, self.ui.theme.accent)]
        if info.get("new_record"):
            lines.append(("Новый рекорд!", 30, (255, 230, 120)))
        elif info.get("rank"):
            lines.append((f"#{info['rank']} в таблице рекордов", 24, (235, 235, 235)))
        extra = f"Линий: {info.get('lines', 0)}"
        if self.game.mode_id == "levels":
            extra += f"  ·  Уровень: {info.get('level', 0)}"
        lines.append((extra, 22, (220, 220, 220)))
        return "Игра окончена", lines

    def _draw_overlay_screen(self, surf: pygame.Surface) -> None:
        """Пауза и конец игры.

        Раньше каждый кадр заново рисовались вся сцена, затемнение во весь экран
        и панель с кнопками — 170–210 мс на кадр на телефоне, попасть по кнопке было
        почти невозможно. Теперь отдельно кэшируются снимок затемнённой сцены и
        сама панель, а за кадр двигается только панель."""
        ui, L = self.ui, self.view.layout
        title, lines = self._overlay_content()
        slide = int((1 - min(1.0, self.overlay_tween.value)) * L.px(60))
        for b, base_y in zip(self.overlay_buttons, self._overlay_base_y):
            b.rect.y = base_y + slide

        key = (self.paused, self.over_info is not None, surf.get_size(), ui.theme.id,
               title, tuple(t for t, _, _ in lines))
        rebuilt = self._overlay is None or key != self._overlay_key
        if rebuilt:                                   # снимок сцены + затемнение
            base = pygame.Surface(surf.get_size())
            self.view.force_full()
            self.view.draw(base, self.game, self.drag, self.best, self.app.settings.hints)
            self.hint_btn.draw(base, ui)
            self.pause_btn.draw(base, ui)
            base.blit(textures.overlay(base.get_size(), (0, 0, 0, 170)), (0, 0))
            self._overlay, self._overlay_key = base.convert(), key
            self._panel = None

        prev_panel = self._panel
        panel_rect, panel = self._overlay_panel(title, lines)
        dest = panel_rect.move(0, slide)
        external = [pygame.Rect(r) for r in self.external_rects]
        moved = panel is not prev_panel or dest != self._panel_dest
        if rebuilt or self._full:
            surf.blit(self._overlay, (0, 0))
        else:
            restore = external + ([self._panel_dest] if moved and self._panel_dest else [])
            for r in restore:
                surf.blit(self._overlay, r, r)
        if (rebuilt or self._full or moved
                or any(r.colliderect(dest) for r in external)):
            surf.blit(panel, dest)      # панель неподвижна — лишний раз не трогаем
        self._panel_dest = dest

    def _overlay_panel(self, title: str, lines: list) -> tuple:
        """Панель с заголовком, строками и кнопками — одной текстурой."""
        L, ui = self.view.layout, self.ui
        title_s = ui.text(title, 44, (255, 255, 255), bold=True)
        rendered = [ui.text(text, size, color, bold=size >= 30) for text, size, color in lines]
        gap, pad = L.px(6), L.px(22)
        content_h = title_s.get_height() + sum(r.get_height() + gap for r in rendered)
        base_top = self._overlay_base_y[0] if self._overlay_base_y else L.height // 2
        base_bottom = (self._overlay_base_y[-1] + self.overlay_buttons[-1].rect.h
                       if self.overlay_buttons else base_top)
        rect = pygame.Rect(0, 0, min(L.width - L.px(30), L.px(380)), 0)
        rect.top = base_top - content_h - pad * 2
        rect.height = base_bottom + pad - rect.top
        rect.centerx = L.width // 2

        key = (rect.size, ui.theme.id, title, tuple(t for t, _, _ in lines),
               tuple(b.render_key(ui) + (b.rect.x, b.rect.h) for b in self.overlay_buttons))
        if self._panel is None or key != self._panel_key:
            panel = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, (*ui.theme.panel, 235), panel.get_rect(), border_radius=L.px(22))
            y = pad
            panel.blit(title_s, title_s.get_rect(midtop=(rect.w // 2, y)))
            y += title_s.get_height() + gap
            for r in rendered:
                panel.blit(r, r.get_rect(midtop=(rect.w // 2, y)))
                y += r.get_height() + gap
            for b, base_y in zip(self.overlay_buttons, self._overlay_base_y):
                saved = b.rect
                b.rect = saved.move(-rect.x, -(rect.y) + (base_y - saved.y))
                try:
                    b.draw(panel, ui)
                finally:
                    b.rect = saved
            self._panel, self._panel_key = panel.convert_alpha(), key
        return rect, self._panel

# ======================================================================
# blockblast/scenes/diag_scene.py
# ======================================================================

"""Экран диагностики: показывает журнал запуска прямо в игре.

Папка Android/data на новых Android закрыта для файловых менеджеров, поэтому
единственный надёжный способ показать журнал пользователю — нарисовать его.
"""

import pygame



class DiagScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.lines: list[str] = []
        self.button = Button("Продолжить", self.go_on, "primary")

    def go_on(self) -> None:
        pass
        self.app.switch(MenuScene(self.app))

    def on_enter(self) -> None:
        text = diag.read_log()
        self.lines = [ln[:64] for ln in text.splitlines() if ln.strip()]
        self.lines.insert(0, "Прошлый запуск не удался.")
        self.lines.insert(1, "Игра работает без звука и ускорения.")
        self.lines.insert(2, "")
        self.layout()

    def layout(self) -> None:
        w, h = self.app.screen.get_size()
        ui = self.ui
        ui.scale = max(0.6, min(w / 480, h / 860))
        bw, bh = min(w - ui.px(60), ui.px(300)), ui.px(54)
        self.button.rect = pygame.Rect((w - bw) // 2, h - bh - ui.px(24), bw, bh)
        self.widgets = [self.button]

    def draw(self, surf: pygame.Surface) -> None:
        ui = self.ui
        surf.fill((22, 24, 30))
        title = ui.text("Журнал запуска", 32, (255, 255, 255), bold=True)
        surf.blit(title, title.get_rect(midtop=(surf.get_width() // 2, ui.px(16) + ui.safe_top)))
        y = ui.px(60) + ui.safe_top
        for line in self.lines:
            color = (255, 210, 120) if line.startswith(("Прошлый", "Игра работает")) else (225, 225, 225)
            img = ui.text(line, 17, color)
            surf.blit(img, (ui.px(12), y))
            y += img.get_height() + ui.px(3)
            if y > self.button.rect.y - ui.px(20):
                break
        self.button.draw(surf, ui)

# ======================================================================
# blockblast/app.py
# ======================================================================

"""Приложение: окно, главный цикл, переключение сцен, всплывающие уведомления."""

import sys
from time import perf_counter
from typing import Optional

import pygame


# События, которых может не быть в старых версиях pygame — берём через getattr
_K_AC_BACK = getattr(pygame, "K_AC_BACK", -1)
_FOCUS_LOST = getattr(pygame, "WINDOWFOCUSLOST", -1)
_APP_TERMINATING = getattr(pygame, "APP_TERMINATING", -1)
_BACKGROUND_EVENTS = {getattr(pygame, n) for n in ("APP_WILLENTERBACKGROUND", "APP_DIDENTERBACKGROUND")
                      if hasattr(pygame, n)}
_FOREGROUND_EVENTS = {getattr(pygame, n) for n in ("APP_DIDENTERFOREGROUND",) if hasattr(pygame, n)}
_RESIZE_EVENTS = {pygame.VIDEORESIZE} | ({pygame.WINDOWSIZECHANGED} if hasattr(pygame, "WINDOWSIZECHANGED") else set())


class _SilentAudio:
    """Заглушка звука: в безопасном режиме mixer не трогаем вовсе."""

    enabled = False
    loading = False
    paused = False
    sfx_volume = 0.0
    music_volume = 0.0

    def play(self, name, level=0): pass
    def update(self): pass
    def set_sfx_volume(self, v): pass
    def set_music_volume(self, v): pass
    def pause_all(self): pass
    def resume_all(self): pass
    def shutdown(self): pass


class App:
    def __init__(self, data_dir: Optional[str] = None, force_silent: bool = False) -> None:
        # безопасный режим включается сам, если прошлый запуск оборвался
        self.safe_mode = diag.begin() or force_silent
        # На Android порядок важен: сначала только экран (самое простое окно),
        # потом показ журнала, и лишь затем звук и ускорение. Раньше звук
        # инициализировался первым, и падение случалось до любого сообщения.
        if IS_ANDROID:
            diag.log("pygame.display.init()")
            pygame.display.init()
            diag.log("pygame.font.init()")
            pygame.font.init()
        else:
            # В браузере (Web Audio API) маленький буфер даёт потрескивание/шум —
            # там нужен запас побольше, чем на десктопе.
            audio_buffer = 4096 if IS_WEB else 512
            pygame.mixer.pre_init(22050, -16, 2, audio_buffer)
            pygame.init()
        pygame.display.set_caption(TITLE)

        self.storage = Storage(data_dir, legacy_dir=PROJECT_DIR)
        self.settings = self.storage.load_settings()
        self.profile = self.storage.load_profile()
        self._forget_removed_themes()
        self.achievements = AchievementTracker(self.profile)
        self.themes = ThemeManager(self.settings.theme)

        diag.log("создание окна")
        self._windowed_size = (MIN_W, MIN_H) if IS_ANDROID else self._initial_window_size()
        self.window_size = self._windowed_size
        self.screen = self._create_window(self.settings.fullscreen)
        if not IS_ANDROID:
            self.window_size = self.screen.get_size()

        diag.log(f"окно готово: {self.screen.get_size()}")
        self.fonts = Fonts()
        diag.log("шрифты готовы")
        # Звук включаем ПОСЛЕ первого кадра: на Android его запуск — частая причина
        # падения, а так игра успевает показать себя и журнал.
        self.audio = _SilentAudio()
        self._audio_pending = not self.safe_mode
        self.ui = UIContext(self.fonts, self.themes, self.audio)
        self.ui.touch = IS_ANDROID
        self.ui.simple_bg = self.settings.quality == "low"
        self._update_safe_area()
        self.clock = pygame.time.Clock()
        self.toasts: list[Toast] = []
        self.running = True
        self.in_background = False
        self._had_input = True
        self._draw_ms = 0.0
        self._flip_ms = 0.0
        self._fps_text = ""
        self._fps_timer = 0.0
        self._external_rects: list = []
        self._last_tap = (0, 0)
        self._first_frame_done = False

        self.notify_achievements(self.achievements.on_theme(self.themes.current.id))

        pass
        if self.safe_mode:      # показываем, на чём оборвался прошлый запуск
            pass
            self.scene = DiagScene(self)
        else:
            self.scene = MenuScene(self)
        self.scene.on_enter()
        diag.log("меню собрано")

    # ---------- окно ----------

    def _screen_size(self) -> tuple[int, int]:
        try:
            return pygame.display.get_desktop_sizes()[0]
        except (AttributeError, IndexError, pygame.error):
            info = pygame.display.Info()
            return (info.current_w or 1280, info.current_h or 800)

    def _render_size(self, native: tuple[int, int]) -> tuple[int, int]:
        """Логический размер кадра: длинная сторона ограничена настройкой качества.

        Пропорции обязаны совпадать с окном до пикселя, иначе SDL добавит чёрные
        поля по краям («письмо в конверте»)."""
        nw, nh = native
        limit = QUALITY_LEVELS.get(self.settings.quality, 1600)
        k = min(1.0, limit / max(nw, nh))
        if nw >= nh:
            w = max(MIN_W, round(nw * k))
            h = max(MIN_H, round(w * nh / nw))
        else:
            h = max(MIN_H, round(nh * k))
            w = max(MIN_W, round(h * nw / nh))
        return w, h

    def _initial_window_size(self) -> tuple[int, int]:
        saved = self.settings.window_size
        try:
            desk_w, desk_h = pygame.display.get_desktop_sizes()[0]
        except (AttributeError, IndexError, pygame.error):
            desk_w, desk_h = 1280, 800
        if saved and MIN_W <= saved[0] <= desk_w and MIN_H <= saved[1] <= desk_h:
            return saved[0], saved[1]
        h = max(MIN_H, min(860, int(desk_h * 0.88)))
        w = max(MIN_W, min(desk_w, int(h * 0.56)))
        return w, h

    def _create_window(self, fullscreen: bool) -> pygame.Surface:
        if IS_WEB:
            # В браузере холст задаёт страница: полноэкранный режим и SCALED
            # там не нужны, а FULLSCREEN приводит к чёрному кадру.
            surface = pygame.display.set_mode(self._web_canvas_size())
            self.window_size = surface.get_size()
            diag.log(f"холст браузера: {self.window_size}")
            return surface
        if IS_ANDROID:
            # Окно создаём ПЕРВЫМ делом и самым простым способом.
            # Любой опрос экрана до появления окна (display.Info, get_desktop_sizes)
            # на Android может уронить приложение в системном коде, откуда
            # Python уже ничего не сообщит.
            last_error = None
            variants = (
                ((0, 0), pygame.FULLSCREEN, {}),
                ((0, 0), 0, {}),
                ((720, 1280), 0, {}),
                ((1080, 1920), 0, {}),
                ((480, 800), 0, {}),
            )
            for mode_size, flags, kwargs in variants:
                try:
                    diag.log(f"set_mode {mode_size} flags={flags}")
                    surface = pygame.display.set_mode(mode_size, flags, **kwargs)
                    self.window_size = surface.get_size()
                    diag.log(f"окно создано: {self.window_size}")
                    return self._apply_quality(surface)
                except Exception as exc:
                    last_error = exc
                    print(f"[display] {mode_size} flags={flags}: {exc}", file=sys.stderr)
                    diag.log(f"не вышло: {exc}")
            raise pygame.error(f"не удалось создать окно: {last_error}")
        if fullscreen:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        return pygame.display.set_mode(self._windowed_size, pygame.RESIZABLE)

    @staticmethod
    def _browser_window() -> tuple[int, int] | None:
        """Размер окна браузера, если игра крутится в pygbag.

        В pygbag модуль platform подменён и содержит объект window.
        На компьютере и телефоне это обычный platform из стандартной
        библиотеки, где такого нет — тогда возвращаем None."""
        try:
            import platform as _platform

            width = int(_platform.window.innerWidth)
            height = int(_platform.window.innerHeight)
        except Exception:
            return None
        if width < 100 or height < 100:
            return None
        return (width, height)

    def _web_canvas_size(self, window: tuple[int, int] | None = None) -> tuple[int, int]:
        """Холст под пропорции окна браузера, а не жёсткие 480x860.

        Иначе на телефоне игра висит маленьким прямоугольником с серыми
        полями сверху и снизу. Длинную сторону ограничиваем настройкой
        качества: рисовать 2400 пикселей в WebAssembly слишком дорого."""
        window = window or self._browser_window()
        if window is None:
            return (BASE_W, BASE_H)
        width, height = self._render_size(window)
        return (max(width, MIN_W), max(height, MIN_H))

    def _apply_quality(self, surface: pygame.Surface) -> pygame.Surface:
        """Кадр меньше экрана: рисуем меньше пикселей, растягивает SDL (флаг SCALED).

        Раньше настройка качества на Android не делала ничего: окно всегда
        создавалось во весь экран, и игра рисовала все 1080x2400 программно.

        В безопасном режиме не трогаем вовсе. Если SCALED не поддерживается —
        остаёмся на уже работающем окне: оно важнее качества."""
        native = surface.get_size()
        wanted = self._render_size(native)
        # Первый запуск после установки идёт самым простым путём: окно во весь
        # экран и больше ничего. SCALED включается со второго запуска, когда
        # известно, что игра вообще доезжает до кадра.
        if self.safe_mode or wanted == native or not diag.launched_ok():
            if wanted != native:
                diag.log("первый запуск: кадр не уменьшаем")
            return surface
        try:
            diag.log(f"кадр {wanted} через SCALED (экран {native})")
            scaled = pygame.display.set_mode(wanted, pygame.FULLSCREEN | pygame.SCALED)
            self.window_size = native      # окно по-прежнему во весь экран
            diag.log(f"кадр уменьшен: {scaled.get_size()}")
            return scaled
        except Exception as exc:
            print(f"[display] SCALED недоступен: {exc}", file=sys.stderr)
            diag.log(f"SCALED не вышло: {exc}")
            fallback = pygame.display.get_surface()
            if fallback is None or fallback.get_size() != native:
                fallback = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.window_size = fallback.get_size()
            return fallback

    def set_quality(self, value: str) -> None:
        if value == self.settings.quality or value not in QUALITY_LEVELS:
            return
        self.settings.quality = value
        self.ui.simple_bg = value == "low"
        if IS_ANDROID:
            self.screen = self._create_window(True)
        self._after_resize()

    def set_fullscreen(self, value: bool) -> None:
        if IS_ANDROID or value == self.settings.fullscreen:
            return
        if value:
            self._windowed_size = self.screen.get_size()
        self.settings.fullscreen = value
        self.screen = self._create_window(value)
        self._after_resize()

    def _on_resize(self, w: int, h: int) -> None:
        if IS_ANDROID:  # поворот экрана: пересоздаём кадр под новую ориентацию
            if (w, h) != self.window_size:
                self.screen = self._create_window(True)
            self._after_resize()
            return
        if self.settings.fullscreen:
            return
        w, h = max(MIN_W, w), max(MIN_H, h)
        surf = pygame.display.get_surface()
        if surf is None or surf.get_size() != (w, h):
            surf = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        self.screen = surf
        self._windowed_size = (w, h)
        self._after_resize()

    def _update_safe_area(self) -> None:
        """Отступ под статус-бар нужен, только если окно реально занимает весь экран.
        Если система уже вынесла свои панели за пределы окна, место не резервируем."""
        if not IS_ANDROID:
            self.ui.safe_top = 0
            return
        desktop = self._screen_size()
        covered = self.window_size[1] >= desktop[1] - 8 and self.window_size[0] >= desktop[0] - 8
        self.ui.safe_top = int(self.screen.get_height() * SAFE_TOP_FRACTION) if covered else 0

    def _after_resize(self) -> None:
        # Не забываем, где были строка FPS и тосты: кадр после смены размера
        # рисует их заново, и если сцена не знает их область, в следующем кадре
        # старый текст не сотрётся — один кадр висит «призрак». Обрезаем по экрану.
        bounds = self.screen.get_rect()
        self._external_rects = [pygame.Rect(r).clip(bounds) for r in self._external_rects]
        if hasattr(self.scene, "view"):
            self.scene.view.force_full()
        self._update_safe_area()
        texture_cache.clear()  # старые размеры больше не нужны — сразу освобождаем память
        self.fonts.clear()
        self.scene.layout()

    # ---------- сцены ----------

    def switch(self, scene) -> None:
        self._had_input = True      # новая сцена — нужен перерисованный кадр
        self.scene.on_exit()
        self.scene = scene
        scene.on_enter()

    def new_game(self):
        pass
        s = self.settings
        self.storage.delete_game()
        return GameScene(self, Game(s.board_size, s.difficulty, s.mode))

    def load_saved_game(self) -> Optional[Game]:
        data = self.storage.load_game()
        if not data:
            return None
        try:
            game = Game.from_data(data)
        except (KeyError, ValueError, TypeError, IndexError) as exc:
            print(f"[save] сохранение повреждено, игнорируем: {exc}", file=sys.stderr)
            self.storage.delete_game()
            return None
        if game.over:
            self.storage.delete_game()
            return None
        return game

    def best_for(self, game: Game) -> int:
        return self.profile.best(leaderboard_key(game.mode_id, game.board.size, game.difficulty))

    # ---------- уведомления ----------

    def notify_achievements(self, unlocked: list[Achievement]) -> None:
        if not unlocked:
            return
        self.storage.save_profile(self.profile)
        for a in unlocked:
            self.notify(f"Достижение: {a.title}", a.description)
        self.audio.play("achievement")

    def notify(self, title: str, subtitle: str) -> None:
        ui = self.ui
        t1 = ui.text(title, 22, (255, 220, 90), bold=True)
        t2 = ui.text(subtitle, 18, (240, 240, 240))
        icon = textures.icon("star", ui.px(30), (255, 210, 60))
        pad = ui.px(12)
        w = max(t1.get_width(), t2.get_width()) + icon.get_width() + pad * 3
        h = t1.get_height() + t2.get_height() + pad
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (25, 25, 35, 235), surf.get_rect(), border_radius=ui.px(14))
        surf.blit(icon, icon.get_rect(midleft=(pad, h // 2)))
        surf.blit(t1, (icon.get_width() + pad * 2, pad // 2))
        surf.blit(t2, (icon.get_width() + pad * 2, pad // 2 + t1.get_height()))
        self.toasts.append(Toast(surf.convert_alpha()))

    def _force_scene_full(self) -> None:
        if hasattr(self.scene, "view"):
            self.scene.view.force_full()
        if hasattr(self.scene, "_full"):
            self.scene._full = True

    def _draw_toasts(self):
        if not self.toasts:
            return None
        t = self.toasts[0]
        h = t.surf.get_height()
        margin = self.ui.px(12) + self.ui.safe_top
        y = margin + t.offset_y(h + margin)
        return self.screen.blit(t.surf, t.surf.get_rect(midtop=(self.screen.get_width() // 2, int(y))))

    # ---------- цикл ----------

    def quit(self) -> None:
        self.running = False

    def _enter_background(self) -> None:
        """Android: приложение свернули. Сохраняем всё сразу — система может его убить."""
        if self.in_background:
            return
        self.in_background = True
        if hasattr(self.scene, "on_background"):
            self.scene.on_background()
        self.save_all()
        self.audio.pause_all()

    def _enter_foreground(self) -> None:
        if not self.in_background:
            return
        self.in_background = False
        self.audio.resume_all()
        surf = pygame.display.get_surface()
        if surf is not None and surf.get_size() != self.screen.get_size():
            self.screen = surf
            self._after_resize()
        self._had_input = True

    def _translate(self, event: pygame.event.Event) -> pygame.event.Event:
        """Кнопка «Назад» на Android ведёт себя как Esc."""
        if event.type == pygame.KEYDOWN and event.key == _K_AC_BACK:
            return pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0)
        return event

    def process_event(self, event: pygame.event.Event) -> None:
        event = self._translate(event)
        t = event.type
        if t == pygame.MOUSEBUTTONDOWN:     # для диагностики: куда пришло касание
            self._last_tap = tuple(int(v) for v in event.pos)
        if t == pygame.QUIT or t == _APP_TERMINATING:
            self.quit()
        elif t in _BACKGROUND_EVENTS:
            self._enter_background()
        elif t in _FOREGROUND_EVENTS:
            self._enter_foreground()
        elif t in _RESIZE_EVENTS:
            w, h = (event.w, event.h) if hasattr(event, "w") else (event.x, event.y)
            self._on_resize(w, h)
        elif t == pygame.KEYDOWN and event.key == pygame.K_F11:
            self.set_fullscreen(not self.settings.fullscreen)
        else:
            if t == _FOCUS_LOST and hasattr(self.scene, "on_focus_lost"):
                self.scene.on_focus_lost()
            self.scene.handle_event(event)

    def frame(self, dt: float, redraw: bool = True) -> None:
        if self._first_frame_done and self._audio_pending:
            self._audio_pending = False
            diag.log("включаем звук")
            try:
                self.audio = AudioManager(self.settings.sfx_volume, self.settings.music_volume)
                self.ui.audio = self.audio
                diag.log("звук готов")
            except Exception as exc:          # без звука играть можно, падать — нельзя
                print(f"[audio] не удалось запустить: {exc}", file=sys.stderr)
                diag.log(f"звук не запустился: {exc}")
        self.audio.update()
        if self.in_background:
            return
        t0 = perf_counter()
        self.scene.update(dt)
        if self.toasts:
            self.toasts[0].update(dt)
            if self.toasts[0].done:
                self.toasts.pop(0)
        if not redraw:
            return          # на экране ничего не меняется — не тратим кадр впустую
        self.scene.external_rects = self._external_rects
        if self.toasts:      # плашка достижения ползёт по экрану — проще перерисовать всё
            self._force_scene_full()
        self.scene.draw(self.screen)
        external = []
        toast_rect = self._draw_toasts()
        if toast_rect is not None:
            external.append(toast_rect)
        if self.settings.show_fps:
            w, h = self.screen.get_size()
            self._fps_timer += dt
            if not self._fps_text or self._fps_timer > 0.25:   # текст рисуем 4 раза в секунду,
                self._fps_timer = 0.0                          # иначе сама диагностика съедает кадр
                self._fps_text = (f"{self.clock.get_fps():.0f} FPS · кадр {self._draw_ms:.0f}мс "
                                  f"(рисуем {self._draw_ms - self._flip_ms:.0f} / выводим {self._flip_ms:.0f}) "
                                  f"· кадр {w}x{h} в окне {self.window_size[0]}x{self.window_size[1]} "
                                  f"· касание {self._last_tap[0]},{self._last_tap[1]}")
            fps = self.ui.text(self._fps_text, 15, (255, 255, 255))
            self.screen.blit(fps, (4, h - fps.get_height() - 4))
            # сцене отдаём ПОСТОЯННУЮ область под строку: её ширина меняется вместе с
            # текстом, а сцена узнаёт о ней только на следующем кадре
            external.append(pygame.Rect(0, h - fps.get_height() - 8, w, fps.get_height() + 8))
        self._external_rects = external
        t1 = perf_counter()
        pygame.display.flip()
        t2 = perf_counter()
        # сглаженные замеры: видно, что именно тормозит — отрисовка или вывод кадра
        self._flip_ms += ((t2 - t1) * 1000 - self._flip_ms) * 0.1
        self._draw_ms += ((t2 - t0) * 1000 - self._draw_ms) * 0.1
        # Метку неудачного запуска снимаем ТОЛЬКО здесь: кадр действительно
        # нарисован и выведен. Раньше это делалось до scene.draw(), поэтому
        # падение на первой отрисовке считалось успехом — и ни безопасный
        # режим, ни «лестница запуска» не включались.
        if not self._first_frame_done:
            self._first_frame_done = True
            diag.success()

    def run(self) -> None:
        active = True
        while self.running:
            fps = 10 if self.in_background else (FPS if active else IDLE_FPS)
            dt = min(self.clock.tick(fps) / 1000.0, MAX_DT)
            self._had_input = False
            for event in pygame.event.get():
                self._had_input = True
                self.process_event(event)
            was_active = active
            active = bool(self._had_input or self.scene.animating or self.toasts or self.audio.loading)
            self.frame(dt, redraw=active or was_active)
        self.shutdown()

    def _forget_removed_themes(self) -> None:
        """Темы иногда убираются (так ушёл «Комикс»). В старом сохранении
        удалённая тема может быть выбрана и засчитана в «Коллекционера» —
        выбираем существующую и не считаем того, чего больше нет."""
        pass
        if self.settings.theme not in THEME_IDS and self.settings.theme != "auto":
            self.settings.theme = "watermelon"      # менеджер тем создаётся позже и возьмёт её
        seen = [t for t in self.profile.themes_seen if t in THEME_IDS]
        if seen != self.profile.themes_seen:
            self.profile.themes_seen = seen
            self.profile.stats["themes_seen"] = len(seen)

    async def run_async(self) -> None:
        """Тот же цикл, но с передачей управления браузеру между кадрами.

        pygbag/WebAssembly работает в одном потоке с отрисовкой страницы:
        без await вкладка замирает и игра не показывает ничего."""
        import asyncio

        active = True
        while self.running:
            fps = 10 if self.in_background else (FPS if active else IDLE_FPS)
            dt = min(self.clock.tick(fps) / 1000.0, MAX_DT)
            self._had_input = False
            for event in pygame.event.get():
                self._had_input = True
                self.process_event(event)
            was_active = active
            active = bool(self._had_input or self.scene.animating or self.toasts or self.audio.loading)
            self.frame(dt, redraw=active or was_active)
            await asyncio.sleep(0)
        self.shutdown()

    def save_all(self) -> None:
        if not self.settings.fullscreen and not IS_ANDROID:
            self.settings.window_size = list(self.screen.get_size())
        self.settings.theme = self.themes.setting
        self.storage.save_settings(self.settings)
        self.storage.save_profile(self.profile, background=False)
        self.storage.flush()

    def shutdown(self) -> None:
        self.scene.on_quit()
        self.save_all()
        self.audio.shutdown()
        pygame.quit()

# ======================================================================
# Точка входа
# ======================================================================

def main() -> None:
    app = App()
    if IS_WEB:
        # pygbag/Emscripten: цикл обязан быть асинхронным и отдавать управление браузеру.
        import asyncio
        asyncio.run(app.run_async())
    else:
        app.run()


if __name__ == "__main__":
    main()
