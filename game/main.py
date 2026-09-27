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
        return mix((0, tone(rate, 200, 0.09, "sine", 0.7, slide_to=110, decay=7)),
                   (0, noise(rate, 0.05, 0.25, decay=12)), rate=rate)
    if name == "invalid":
        return tone(rate, 220, 0.14, "square", 0.25, slide_to=150, decay=4)
    if name == "click":
        return tone(rate, 1200, 0.025, "tri", 0.25, decay=10)
    if name == "clear":
        # арпеджио растёт с количеством линий
        steps = [0, 4, 7, 12, 16, 19][: min(6, 2 + level)]
        parts = [(0.045 * i, tone(rate, note(3 + s), 0.18, "tri", 0.4, decay=5)) for i, s in enumerate(steps)]
        parts.append((0, noise(rate, 0.25, 0.18, decay=6, seed=level)))
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
            for detune in (0.998, 1.002):
                ph_step = f * detune / rate
                for i in range(length):
                    t = i / length
                    env = min(1.0, t * 8) * min(1.0, (1 - t) * 8)
                    out[start + i] += math.sin(2 * math.pi * ph_step * i) * 0.05 * env
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

        target = 11025 if IS_ANDROID else 16000
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
        pygame.draw.line(s, rib_l
