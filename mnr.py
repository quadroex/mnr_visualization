import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


SAMPLE_PROGRAM = """1: J(1, 2, 6)
2: S(0)
3: S(2)
4: J(0, 0, 1)
5: Z(9)
"""

APP_STYLE = """
QMainWindow {
    background: #070b12;
}

QWidget {
    color: #e5e7eb;
    font-family: "Segoe UI", Arial;
    font-size: 13px;
}

QSplitter::handle {
    background: #070b12;
    width: 8px;
}

QFrame#Panel {
    background: #0b111c;
    border: 1px solid #1d2735;
    border-radius: 18px;
}

QFrame#SoftPanel {
    background: #0f1623;
    border: 1px solid #222d3d;
    border-radius: 16px;
}

QFrame#HeroPanel {
    background: #101827;
    border: 1px solid #253246;
    border-radius: 16px;
}

QFrame#RegisterCard {
    background: #111827;
    border: 1px solid #293548;
    border-radius: 14px;
}

QWidget#RegisterCanvas {
    background: #151a22;
    border: 1px solid #232c3a;
    border-radius: 14px;
}

QFrame#CurrentCommandCard {
    background: #0f172a;
    border: 1px solid #2a3a52;
    border-radius: 16px;
}

QLabel#Title {
    color: #f8fafc;
    font-size: 21px;
    font-weight: 800;
}

QLabel#SubTitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#SectionTitle {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 750;
}

QLabel#Muted {
    color: #94a3b8;
}

QLabel#Tiny {
    color: #7f8ea3;
    font-size: 11px;
    font-weight: 650;
}

QLabel#RegisterName {
    color: #93a4bb;
    font-size: 12px;
    font-weight: 750;
}

QLabel#RegisterValue {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 800;
}

QLabel#CommandCode {
    color: #f8fafc;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 22px;
    font-weight: 800;
}

QPushButton {
    background: #2563eb;
    color: white;
    border: none;
    min-height: 23px;
    padding: 10px 14px;
    border-radius: 11px;
    font-weight: 750;
}

QPushButton:hover {
    background: #3b82f6;
}

QPushButton:pressed {
    background: #1d4ed8;
}

QPushButton:disabled {
    background: #1b2533;
    color: #64748b;
}

QPushButton#Secondary {
    background: #172033;
    color: #dbeafe;
    border: 1px solid #263548;
}

QPushButton#Secondary:hover {
    background: #202c42;
}

QPushButton#Danger {
    background: #dc2626;
}

QPushButton#Danger:hover {
    background: #ef4444;
}

QLineEdit {
    background: #070b12;
    border: 1px solid #263548;
    border-radius: 12px;
    padding: 10px 12px;
    selection-background-color: #2563eb;
}

QTableWidget {
    background: #070b12;
    alternate-background-color: #0d1420;
    border: 1px solid #1d2735;
    border-radius: 14px;
    gridline-color: transparent;
    padding: 6px;
    selection-background-color: #1e3a5f;
    selection-color: #ffffff;
}

QTableWidget::item {
    border: none;
    border-bottom: 1px solid #141d2b;
    padding: 9px 10px;
}

QTableWidget::item:selected {
    background: #1e3a5f;
    color: #ffffff;
}

QHeaderView::section {
    background: #111827;
    color: #dbeafe;
    padding: 10px 9px;
    border: none;
    border-bottom: 1px solid #253246;
    font-weight: 800;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 6px 2px;
}

QScrollBar::handle:vertical {
    background: #263548;
    min-height: 28px;
    border-radius: 5px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
    border: none;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #253246;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #e5e7eb;
    border: 2px solid #3b82f6;
    width: 18px;
    margin: -7px 0;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    background: #ffffff;
}
"""


@dataclass(frozen=True)
class Instruction:
    address: int
    op: str
    args: tuple[int, ...]
    raw: str


@dataclass
class StepResult:
    step_number: int
    pc_before: int | None
    pc_after: int | None
    instruction: Instruction | None
    reads: list[int]
    writes: list[int]
    description: str
    halted: bool


def parse_program(text: str) -> dict[int, Instruction]:
    commands: dict[int, Instruction] = {}
    pattern = re.compile(r"^\s*(\d+)\s*:\s*([ZSJT])\s*\(([^)]*)\)\s*$")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = pattern.match(line)
        if not match:
            raise ValueError(f"Неправильний рядок програми: {raw_line}")

        address = int(match.group(1))
        op = match.group(2)
        arg_text = match.group(3).strip()
        args = tuple(int(part.strip()) for part in arg_text.split(",") if part.strip())

        expected_count = {"Z": 1, "S": 1, "T": 2, "J": 3}[op]
        if len(args) != expected_count:
            raise ValueError(f"Команда {line} має мати {expected_count} аргумент(и).")

        commands[address] = Instruction(address, op, args, line)

    if not commands:
        raise ValueError("Файл не містить жодної МНР-команди.")

    return commands


def parse_initial_registers(text: str) -> dict[int, int]:
    result: dict[int, int] = {}
    normalized = text.replace(";", ",").replace("\n", ",")

    for token in normalized.split(","):
        token = token.strip()
        if not token:
            continue

        match = re.match(r"^R?\s*(\d+)\s*=\s*(\d+)\s*$", token, re.IGNORECASE)
        if not match:
            raise ValueError(f"Неправильний формат початкового регістру: {token}")

        result[int(match.group(1))] = int(match.group(2))

    return result


def command_meaning(instruction: Instruction) -> str:
    op = instruction.op
    a = instruction.args

    if op == "Z":
        return f"R{a[0]} := 0"
    if op == "S":
        return f"R{a[0]} := R{a[0]} + 1"
    if op == "T":
        return f"R{a[1]} := R{a[0]}"
    if op == "J":
        return f"if R{a[0]} == R{a[1]} then goto {a[2]} else next"

    return ""


def register_indexes_used(program: dict[int, Instruction]) -> set[int]:
    indexes: set[int] = {0}

    for instruction in program.values():
        if instruction.op in {"Z", "S"}:
            indexes.add(instruction.args[0])
        elif instruction.op == "T":
            indexes.add(instruction.args[0])
            indexes.add(instruction.args[1])
        elif instruction.op == "J":
            indexes.add(instruction.args[0])
            indexes.add(instruction.args[1])

    return indexes


class MNRMachine:
    def __init__(self, program: dict[int, Instruction], initial_registers: dict[int, int] | None = None):
        self.program = program
        self.addresses = sorted(program.keys())
        self.next_by_address: dict[int, int | None] = {}

        for index, address in enumerate(self.addresses):
            self.next_by_address[address] = self.addresses[index + 1] if index + 1 < len(self.addresses) else address + 1

        self.initial_registers = initial_registers or {}
        self.registers: defaultdict[int, int] = defaultdict(int)
        self.pc: int | None = None
        self.step_count = 0
        self.halted = False
        self.history: list[tuple[int | None, dict[int, int], int, bool]] = []
        self.reset(self.initial_registers)

    def reset(self, initial_registers: dict[int, int] | None = None) -> None:
        if initial_registers is not None:
            self.initial_registers = dict(initial_registers)

        self.registers = defaultdict(int)
        for index, value in self.initial_registers.items():
            self.registers[index] = value

        self.pc = self.addresses[0] if self.addresses else None
        self.step_count = 0
        self.halted = self.pc not in self.program
        self.history.clear()

    def current_instruction(self) -> Instruction | None:
        if self.pc is None:
            return None
        return self.program.get(self.pc)

    def step(self) -> StepResult:
        if self.halted or self.pc not in self.program:
            self.halted = True
            return StepResult(
                step_number=self.step_count,
                pc_before=self.pc,
                pc_after=self.pc,
                instruction=None,
                reads=[],
                writes=[],
                description="Програма вже зупинена: поточна адреса не містить команди.",
                halted=True,
            )

        self.history.append((self.pc, dict(self.registers), self.step_count, self.halted))

        instruction = self.program[self.pc]
        pc_before = self.pc
        reads: list[int] = []
        writes: list[int] = []
        description = ""

        if instruction.op == "Z":
            reg = instruction.args[0]
            old = self.registers[reg]
            self.registers[reg] = 0
            self.pc = self.next_by_address[pc_before]
            writes = [reg]
            description = f"R{reg}: {old} → 0"

        elif instruction.op == "S":
            reg = instruction.args[0]
            old = self.registers[reg]
            self.registers[reg] = old + 1
            self.pc = self.next_by_address[pc_before]
            reads = [reg]
            writes = [reg]
            description = f"R{reg}: {old} → {self.registers[reg]}"

        elif instruction.op == "T":
            source, target = instruction.args
            old = self.registers[target]
            copied = self.registers[source]
            self.registers[target] = copied
            self.pc = self.next_by_address[pc_before]
            reads = [source]
            writes = [target]
            description = f"R{target} := R{source} = {copied}; було {old}"

        elif instruction.op == "J":
            left, right, target = instruction.args
            left_value = self.registers[left]
            right_value = self.registers[right]
            reads = [left, right]

            if left_value == right_value:
                self.pc = target
                description = f"R{left} = {left_value}, R{right} = {right_value}; умова істинна → перехід до {target}"
            else:
                self.pc = self.next_by_address[pc_before]
                description = f"R{left} = {left_value}, R{right} = {right_value}; умова хибна → наступна команда"

        self.step_count += 1

        if self.pc not in self.program:
            self.halted = True
            description += f". Адреси {self.pc} немає у програмі → STOP"

        return StepResult(
            step_number=self.step_count,
            pc_before=pc_before,
            pc_after=self.pc,
            instruction=instruction,
            reads=reads,
            writes=writes,
            description=description,
            halted=self.halted,
        )

    def back(self) -> bool:
        if not self.history:
            return False

        pc, registers, step_count, halted = self.history.pop()
        self.pc = pc
        self.registers = defaultdict(int, registers)
        self.step_count = step_count
        self.halted = halted
        return True


class RegisterCard(QFrame):
    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.setObjectName("RegisterCard")
        self.setMinimumSize(78, 78)
        self.setMaximumHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        self.name_label = QLabel(f"R{index}")
        self.name_label.setObjectName("RegisterName")

        self.state_dot = QLabel("●")
        self.state_dot.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.state_dot.setStyleSheet("color:#334155; font-size:11px;")

        top.addWidget(self.name_label)
        top.addStretch()
        top.addWidget(self.state_dot)

        self.value_label = QLabel("0")
        self.value_label.setObjectName("RegisterValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))

        layout.addLayout(top)
        layout.addStretch()
        layout.addWidget(self.value_label)
        layout.addStretch()

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))

    def set_state(self, state: str) -> None:
        styles = {
            "normal": (
                "QFrame#RegisterCard {"
                "background:#111827;"
                "border:1px solid #293548; border-radius:14px;}"
            ),
            "read": (
                "QFrame#RegisterCard {"
                "background:#111827;"
                "border:2px solid #60a5fa; border-radius:14px;}"
            ),
            "write": (
                "QFrame#RegisterCard {"
                "background:#111827;"
                "border:2px solid #22c55e; border-radius:14px;}"
            ),
            "readwrite": (
                "QFrame#RegisterCard {"
                "background:#111827;"
                "border:2px solid #f59e0b; border-radius:14px;}"
            ),
        }

        dot_colors = {
            "normal": "#334155",
            "read": "#60a5fa",
            "write": "#22c55e",
            "readwrite": "#f59e0b",
        }

        self.setStyleSheet(styles.get(state, styles["normal"]))
        self.state_dot.setStyleSheet(f"color:{dot_colors.get(state, '#334155')}; font-size:11px;")


class MNRVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("МНР Visualizer")
        self.resize(1500, 880)
        self.setStyleSheet(APP_STYLE)

        self.program: dict[int, Instruction] = parse_program(SAMPLE_PROGRAM)
        self.machine = MNRMachine(self.program, {0: 4, 1: 3, 2: 0})
        self.program_path: Path | None = None
        self.register_cards: dict[int, RegisterCard] = {}
        self.animations: list[QPropertyAnimation] = []
        self.timeline: list[tuple[int | None, dict[int, int], int, bool]] = []
        self.step_results: list[StepResult] = []
        self.current_timeline_index = 0
        self.last_reads: list[int] = []
        self.last_writes: list[int] = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step_once)

        self.build_ui()
        self.try_autoload_program_file()
        self.refresh_all()

    def build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        self.setCentralWidget(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

        splitter.addWidget(self.build_left_panel())
        splitter.addWidget(self.build_center_panel())
        splitter.addWidget(self.build_right_panel())
        splitter.setSizes([380, 760, 390])

    def panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        return frame

    def build_left_panel(self) -> QWidget:
        panel = self.panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(13)

        title = QLabel("МНР-програма")
        title.setObjectName("Title")
        layout.addWidget(title)

        self.path_label = QLabel("Файл: вбудований приклад")
        self.path_label.setObjectName("SubTitle")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)

        self.open_button = QPushButton("Відкрити файл")
        self.open_button.clicked.connect(self.open_program_file)

        # self.reload_button = QPushButton("Оновити")
        # self.reload_button.setObjectName("Secondary")
        # self.reload_button.clicked.connect(self.reload_program)

        buttons.addWidget(self.open_button)
        # buttons.addWidget(self.reload_button)
        layout.addLayout(buttons)

        self.program_table = QTableWidget()
        self.program_table.setColumnCount(2)
        self.program_table.setHorizontalHeaderLabels(["#", "Команда"])
        self.program_table.verticalHeader().setVisible(False)
        self.program_table.setAlternatingRowColors(True)
        self.program_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.program_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.program_table.setShowGrid(False)
        self.program_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.program_table.setWordWrap(False)
        self.program_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.program_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.program_table.verticalHeader().setDefaultSectionSize(40)
        layout.addWidget(self.program_table, stretch=1)

        return panel

    def build_center_panel(self) -> QWidget:
        panel = self.panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("Виконання")
        title.setObjectName("Title")
        subtitle = QLabel("Стан машини, поточна команда і регістри")
        subtitle.setObjectName("SubTitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)

        title_row.addLayout(title_block)
        title_row.addStretch()

        self.status_label = QLabel("READY")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumWidth(86)
        self.status_label.setStyleSheet(
            "background:#172554; color:#bfdbfe; border-radius:10px; padding:7px 12px; font-weight:800;"
        )
        title_row.addWidget(self.status_label)
        layout.addLayout(title_row)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.pc_label = self.stat_card("PC", "1")
        self.step_label = self.stat_card("Крок", "0")
        self.next_label = self.stat_card("Поточна команда", "—")
        stats.addWidget(self.pc_label)
        stats.addWidget(self.step_label)
        stats.addWidget(self.next_label, stretch=1)
        layout.addLayout(stats)

        self.command_banner = QFrame()
        self.command_banner.setObjectName("CurrentCommandCard")
        banner_layout = QHBoxLayout(self.command_banner)
        banner_layout.setContentsMargins(16, 13, 16, 13)
        banner_layout.setSpacing(14)

        command_text_block = QVBoxLayout()
        command_text_block.setSpacing(3)

        self.command_title = QLabel("Поточна команда")
        self.command_title.setObjectName("Tiny")

        self.command_value = QLabel("—")
        self.command_value.setObjectName("CommandCode")
        self.command_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        command_text_block.addWidget(self.command_title)
        command_text_block.addWidget(self.command_value)

        self.command_arrow = QLabel("→")
        self.command_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.command_arrow.setFixedSize(34, 34)
        self.command_arrow.setStyleSheet(
            "background:#172033; color:#60a5fa; border:1px solid #263548; "
            "border-radius:17px; font-size:21px; font-weight:850;"
        )

        banner_layout.addLayout(command_text_block)
        banner_layout.addStretch()
        banner_layout.addWidget(self.command_arrow)
        layout.addWidget(self.command_banner)

        register_header = QHBoxLayout()
        register_header.setSpacing(10)

        section = QLabel("Регістри")
        section.setObjectName("SectionTitle")
        register_header.addWidget(section)

        register_header.addStretch()
        layout.addLayout(register_header)

        self.registers_panel = QFrame()
        self.registers_panel.setObjectName("SoftPanel")
        registers_layout = QVBoxLayout(self.registers_panel)
        registers_layout.setContentsMargins(14, 14, 14, 14)
        registers_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.register_widget = QWidget()
        self.register_widget.setObjectName("RegisterCanvas")
        self.register_grid = QGridLayout(self.register_widget)
        self.register_grid.setContentsMargins(12, 12, 12, 12)
        self.register_grid.setHorizontalSpacing(12)
        self.register_grid.setVerticalSpacing(12)
        self.register_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.register_widget)
        registers_layout.addWidget(scroll)
        layout.addWidget(self.registers_panel, stretch=1)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("Secondary")
        self.back_button.clicked.connect(self.go_back)

        self.step_button = QPushButton("Forward")
        self.step_button.setObjectName("Secondary")
        self.step_button.clicked.connect(self.step_once)

        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.toggle_run)

        self.reset_button = QPushButton("Reset")
        self.reset_button.setObjectName("Danger")
        self.reset_button.clicked.connect(self.reset_machine)

        controls.addWidget(self.back_button)
        controls.addWidget(self.step_button)
        controls.addWidget(self.run_button)
        controls.addWidget(self.reset_button)
        layout.addLayout(controls)

        speed_panel = QFrame()
        speed_panel.setObjectName("SoftPanel")
        speed_layout = QVBoxLayout(speed_panel)
        speed_layout.setContentsMargins(13, 10, 13, 10)
        speed_layout.setSpacing(6)

        speed_top = QHBoxLayout()
        speed_label = QLabel("Затримка між кроками")
        speed_label.setObjectName("Muted")
        self.speed_value_label = QLabel("200 мс")
        self.speed_value_label.setObjectName("Muted")
        self.speed_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        speed_top.addWidget(speed_label)
        speed_top.addStretch()
        speed_top.addWidget(self.speed_value_label)
        speed_layout.addLayout(speed_top)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 40)
        self.speed_slider.setSingleStep(1)
        self.speed_slider.setPageStep(1)
        self.speed_slider.setTickInterval(1)
        self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.speed_slider.setValue(4)
        self.speed_slider.valueChanged.connect(self.update_speed_label)
        speed_layout.addWidget(self.speed_slider)

        layout.addWidget(speed_panel)

        return panel

    def build_right_panel(self) -> QWidget:
        panel = self.panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(13)

        title = QLabel("Деталі кроку")
        title.setObjectName("Title")
        layout.addWidget(title)

        init_label = QLabel("Початкові регістри")
        init_label.setObjectName("SectionTitle")
        layout.addWidget(init_label)

        self.initial_line = QLineEdit()
        self.initial_line.setPlaceholderText("Наприклад: R0=3, R1=2, R2=0")
        self.initial_line.setText("R0=3, R1=2")
        self.initial_line.returnPressed.connect(self.reset_machine)
        layout.addWidget(self.initial_line)

        hint = QLabel("Усі незадані регістри автоматично дорівнюють 0.")
        hint.setObjectName("SubTitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.detail_card = QFrame()
        self.detail_card.setObjectName("HeroPanel")
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(18, 16, 18, 16)
        detail_layout.setSpacing(10)

        self.detail_label = QLabel(
            "<b style='font-size:16px'>Готово до виконання</b><br>"
            "<span style='color:#8ca0bc'>Натисніть Forward, щоб виконати першу команду.</span>"
        )
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextFormat(Qt.TextFormat.RichText)
        detail_layout.addWidget(self.detail_label)
        layout.addWidget(self.detail_card)

        log_title = QLabel("Журнал виконання")
        log_title.setObjectName("SectionTitle")
        layout.addWidget(log_title)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["Крок", "PC", "Команда"])
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.log_table.setShowGrid(False)
        self.log_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log_table.setWordWrap(False)
        self.log_table.cellClicked.connect(self.jump_to_log_row)
        self.log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.log_table.verticalHeader().setDefaultSectionSize(40)
        layout.addWidget(self.log_table, stretch=1)

        return panel

    def stat_card(self, title: str, value: str) -> QLabel:
        label = QLabel(
            f"<span style='color:#94a3b8; font-size:12px; font-weight:700'>{title}</span>"
            f"<br><b style='font-size:20px; color:#f8fafc'>{value}</b>"
        )
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setMinimumHeight(72)
        label.setStyleSheet(
            "background:#0f1623; border:1px solid #222d3d; border-radius:14px; padding:11px;"
        )
        return label

    def try_autoload_program_file(self) -> None:
        default_file = Path.cwd() / "example.txt"
        if default_file.exists():
            self.load_program_from_path(default_file)

    def open_program_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Відкрити МНР-програму",
            str(Path.cwd()),
            "TXT files (*.txt);;All files (*.*)",
        )
        if path:
            self.load_program_from_path(Path(path))

    def reload_program(self) -> None:
        if self.program_path is None:
            self.load_program_from_text(SAMPLE_PROGRAM, None)
        else:
            self.load_program_from_path(self.program_path)

    def load_program_from_path(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
            self.load_program_from_text(text, path)
        except Exception as error:
            QMessageBox.critical(self, "Помилка читання файлу", str(error))

    def load_program_from_text(self, text: str, path: Path | None) -> None:
        try:
            self.program = parse_program(text)
            self.program_path = path
            initial = parse_initial_registers(self.initial_line.text()) if hasattr(self, "initial_line") else {}
            self.machine = MNRMachine(self.program, initial)
            self.clear_log()
            self.path_label.setText(f"Файл: {path}" if path else "Файл: вбудований приклад")
            self.refresh_all()
        except Exception as error:
            QMessageBox.critical(self, "Помилка програми", str(error))

    def reset_machine(self) -> None:
        try:
            initial = parse_initial_registers(self.initial_line.text())
            self.machine.reset(initial)
            self.clear_log()
            self.timer.stop()
            self.run_button.setText("Run")
            self.detail_label.setText(
                "<b style='font-size:16px'>Стан скинуто</b><br>"
                "<span style='color:#8ca0bc'>Натисніть Forward, щоб виконати першу команду.</span>"
            )
            self.refresh_all()
        except Exception as error:
            QMessageBox.critical(self, "Помилка початкових регістрів", str(error))

    def step_once(self) -> None:
        if self.current_timeline_index < len(self.timeline) - 1:
            self.jump_to_timeline_index(self.current_timeline_index + 1)
            if self.machine.halted:
                self.timer.stop()
                self.run_button.setText("Run")
                self.refresh_status()
            return

        if self.machine.halted:
            self.timer.stop()
            self.run_button.setText("Run")
            self.refresh_status()
            return

        result = self.machine.step()

        if (
            result.instruction is not None
            and not result.halted
            and result.pc_before == result.pc_after
        ):
            self.machine.halted = True
            result.halted = True
            result.description += ". Виявлено нескінченний цикл: та сама команда виконується повторно без зміни PC."

        self.append_log(result)
        self.update_detail(result)
        self.refresh_all(result.reads, result.writes)

        if result.halted:
            self.timer.stop()
            self.run_button.setText("Run")

    def go_back(self) -> None:
        if self.current_timeline_index <= 0:
            return

        self.jump_to_timeline_index(self.current_timeline_index - 1)

    def toggle_run(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.run_button.setText("Run")
            self.refresh_status()
        else:
            can_move_forward_in_log = self.current_timeline_index < len(self.timeline) - 1
            if self.machine.halted and not can_move_forward_in_log:
                return

            self.timer.start(self.current_delay_ms())
            self.run_button.setText("Pause")
            self.refresh_status()

    def current_delay_ms(self) -> int:
        return self.speed_slider.value() * 50

    def update_speed_label(self) -> None:
        value = self.current_delay_ms()
        self.speed_value_label.setText(f"{value} мс")
        if self.timer.isActive():
            self.timer.setInterval(value)

    def snapshot_machine(self) -> tuple[int | None, dict[int, int], int, bool]:
        return (
            self.machine.pc,
            dict(self.machine.registers),
            self.machine.step_count,
            self.machine.halted,
        )

    def restore_machine_snapshot(self, snapshot: tuple[int | None, dict[int, int], int, bool]) -> None:
        pc, registers, step_count, halted = snapshot
        self.machine.pc = pc
        self.machine.registers = defaultdict(int, registers)
        self.machine.step_count = step_count
        self.machine.halted = halted

    def rebuild_machine_history_for_current_position(self) -> None:
        self.machine.history = [
            (pc, dict(registers), step_count, halted)
            for pc, registers, step_count, halted in self.timeline[: self.current_timeline_index]
        ]

    def clear_log(self) -> None:
        self.log_table.setRowCount(0)
        self.timeline = [self.snapshot_machine()]
        self.step_results = []
        self.current_timeline_index = 0
        self.last_reads = []
        self.last_writes = []

    def append_log(self, result: StepResult) -> None:
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)

        command_text = result.instruction.raw if result.instruction else "STOP"
        values = [str(result.step_number), str(result.pc_before), command_text]

        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setForeground(QColor("#e6edf7"))
            if result.halted:
                item.setForeground(QColor("#fecaca"))
            self.log_table.setItem(row, column, item)

        self.timeline.append(self.snapshot_machine())
        self.step_results.append(result)
        self.current_timeline_index = len(self.timeline) - 1
        self.log_table.selectRow(row)
        self.log_table.scrollToBottom()

    def jump_to_log_row(self, row: int, column: int) -> None:
        self.jump_to_timeline_index(row + 1)

    def jump_to_timeline_index(self, index: int) -> None:
        if index < 0 or index >= len(self.timeline):
            return

        self.current_timeline_index = index
        self.restore_machine_snapshot(self.timeline[index])
        self.rebuild_machine_history_for_current_position()

        if index == 0:
            self.log_table.clearSelection()
            self.detail_label.setText(
                "<b style='font-size:16px'>Початковий стан</b><br>"
                "<span style='color:#8ca0bc'>Це стан машини до виконання першої команди.</span>"
            )
            self.refresh_all()
            return

        row = index - 1
        result = self.step_results[row] if row < len(self.step_results) else None
        if result is not None:
            self.update_detail(result)
            self.refresh_all(result.reads, result.writes)
        else:
            self.refresh_all()

        self.log_table.selectRow(row)
        self.log_table.scrollToItem(self.log_table.item(row, 0))

    def update_detail(self, result: StepResult) -> None:
        if result.instruction is None:
            self.detail_label.setText(
                "<b style='font-size:17px'>STOP</b><br>"
                f"<span style='color:#e6edf7'>{result.description}</span>"
            )
            return

        involved = sorted(set(result.reads) | set(result.writes))
        involved_text = ", ".join(f"R{i}" for i in involved) or "—"

        self.detail_label.setText(
            f"<b style='font-size:17px'>Крок {result.step_number}</b><br>"
            f"<span style='color:#8ca0bc'>PC:</span> <b>{result.pc_before}</b> → <b>{result.pc_after}</b><br>"
            f"<span style='color:#8ca0bc'>Команда:</span> <b style='font-family:Consolas'>{result.instruction.raw}</b><br>"
            f"<span style='color:#8ca0bc'>Сенс:</span> {command_meaning(result.instruction)}<br>"
            f"<span style='color:#8ca0bc'>Задіяні регістри:</span> {involved_text}<br><br>"
            f"<span style='color:#f8fafc'>{result.description}</span>"
            f"{'<br><br><span style=\"color:#fca5a5; font-weight:800\">Зупинка виконання.</span>' if result.halted and result.pc_before == result.pc_after else ''}"
            f"{'<br><br><span style=\"color:#fca5a5; font-weight:800\">Програма зупинилася.</span>' if result.halted and result.pc_before != result.pc_after else ''}"
        )

    def refresh_all(self, reads: list[int] | None = None, writes: list[int] | None = None) -> None:
        reads = reads or []
        writes = writes or []
        self.last_reads = list(reads)
        self.last_writes = list(writes)
        self.refresh_program_table()
        self.refresh_status()
        self.refresh_command_banner()
        self.refresh_registers(reads, writes)
        self.back_button.setEnabled(self.current_timeline_index > 0)
        can_move_forward_in_log = self.current_timeline_index < len(self.timeline) - 1
        self.step_button.setEnabled(can_move_forward_in_log or not self.machine.halted)
        self.run_button.setEnabled(can_move_forward_in_log or not self.machine.halted)

    def refresh_program_table(self) -> None:
        addresses = sorted(self.program.keys())
        self.program_table.setRowCount(len(addresses))

        for row, address in enumerate(addresses):
            instruction = self.program[address]
            values = [str(address), instruction.raw.split(":", 1)[1].strip()]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setForeground(QColor("#e6edf7"))
                if column == 1:
                    item.setFont(QFont("Consolas", 11))

                if address == self.machine.pc and not self.machine.halted:
                    item.setBackground(QColor("#f59e0b"))
                    item.setForeground(QColor("#07111f"))
                    item.setFont(QFont("Consolas" if column == 1 else "Segoe UI", 11, QFont.Weight.Bold))

                self.program_table.setItem(row, column, item)

            if address == self.machine.pc and not self.machine.halted:
                self.program_table.setCurrentCell(row, 0)
                self.program_table.scrollToItem(self.program_table.item(row, 0))

    def refresh_status(self) -> None:
        pc = self.machine.pc
        current = self.machine.current_instruction()

        self.pc_label.setText(
            f"<span style='color:#94a3b8; font-size:12px; font-weight:700'>PC</span><br>"
            f"<b style='font-size:20px; color:#f8fafc'>{pc}</b>"
        )
        self.step_label.setText(
            f"<span style='color:#94a3b8; font-size:12px; font-weight:700'>Крок</span><br>"
            f"<b style='font-size:20px; color:#f8fafc'>{self.machine.step_count}</b>"
        )

        next_text = current.raw if current else "STOP"
        self.next_label.setText(
            f"<span style='color:#94a3b8; font-size:12px; font-weight:700'>Поточна команда</span><br>"
            f"<b style='font-size:15px; color:#f8fafc'>{next_text}</b>"
        )

        if self.machine.halted:
            self.status_label.setText("HALTED")
            self.status_label.setStyleSheet(
                "background:#7f1d1d; color:#fecaca; border-radius:10px; padding:7px 12px; font-weight:800;"
            )
        elif self.timer.isActive():
            self.status_label.setText("RUNNING")
            self.status_label.setStyleSheet(
                "background:#14532d; color:#bbf7d0; border-radius:10px; padding:7px 12px; font-weight:800;"
            )
        else:
            self.status_label.setText("READY")
            self.status_label.setStyleSheet(
                "background:#172554; color:#bfdbfe; border-radius:10px; padding:7px 12px; font-weight:800;"
            )

    def refresh_command_banner(self) -> None:
        current = self.machine.current_instruction()
        if current is None:
            self.command_title.setText("Стан")
            self.command_value.setText("STOP")
            self.command_arrow.setText("■")
            return

        self.command_title.setText(f"PC {current.address}")
        self.command_value.setText(current.raw.split(":", 1)[1].strip())
        self.command_arrow.setText("")

    def refresh_registers(self, reads: list[int], writes: list[int]) -> None:
        used = register_indexes_used(self.program) | set(self.machine.registers.keys()) | set(reads) | set(writes)
        max_index = max(used) if used else 0
        indexes = list(range(max_index + 1))

        while self.register_grid.count():
            item = self.register_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        self.register_cards.clear()

        available_width = self.registers_panel.width() - 58 if hasattr(self, "registers_panel") else 760
        target_card_width = 88
        columns = max(1, min(10, available_width // target_card_width))
        if len(indexes) <= columns:
            columns = len(indexes)

        for column in range(12):
            self.register_grid.setColumnStretch(column, 0)
            self.register_grid.setColumnMinimumWidth(column, 0)

        for column in range(columns):
            self.register_grid.setColumnStretch(column, 1)

        for position, index in enumerate(indexes):
            card = RegisterCard(index)
            card.set_value(self.machine.registers[index])

            is_read = index in reads
            is_write = index in writes
            if is_read and is_write:
                card.set_state("readwrite")
                self.animate_card(card)
            elif is_write:
                card.set_state("write")
                self.animate_card(card)
            elif is_read:
                card.set_state("read")
                self.animate_card(card)
            else:
                card.set_state("normal")

            self.register_cards[index] = card
            self.register_grid.addWidget(card, position // columns, position % columns)

    def animate_card(self, card: RegisterCard) -> None:
        effect = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(360)
        animation.setStartValue(0.35)
        animation.setKeyValueAt(0.45, 1.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: card.setGraphicsEffect(None))
        animation.start()

        self.animations.append(animation)
        self.animations = [item for item in self.animations if item.state() == QPropertyAnimation.State.Running]

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "register_grid"):
            QTimer.singleShot(0, lambda: self.refresh_registers(self.last_reads, self.last_writes))


def main() -> None:
    app = QApplication(sys.argv)
    window = MNRVisualizer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
