import sys
import os
import sqlite3
import pandas as pd
import parser_rnf
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QFrame,
    QComboBox, QFileDialog, QMessageBox, QStackedWidget,
    QDialog, QFormLayout, QTextEdit, QGridLayout, QSizePolicy, QCheckBox,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor

DB_NAME = "grants.db"

# ─────────────────────────── Цвета тёмной темы ───────────────────────────

BG       = "#1e1e2e"
BG2      = "#2a2a3e"
BG3      = "#313145"
BORDER   = "#44445a"
TEXT     = "#cdd6f4"
TEXT_DIM = "#7f849c"
ACCENT   = "#89b4fa"
GREEN    = "#3b82f6"   
BLUE_UI  = "#3b82f6"
RED      = "#6c6f85"   
TRUE_RED = "#f38ba8"
STAR     = "#f9e2af"
BTN_BG   = "#313145"
BTN_HOV  = "#45475a"

DARK_SS = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QDialog, QFrame {{ background: {BG}; }}
QLineEdit, QTextEdit, QComboBox {{
    background: {BG2}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 5px;
    padding: 5px 8px; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QTextEdit:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {BG2}; color: {TEXT};
    border: 1px solid {BORDER}; selection-background-color: {BG3};
}}
QPushButton {{
    background: {BTN_BG}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 5px; padding: 6px 14px;
}}
QPushButton:hover {{ background: {BTN_HOV}; border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BG3}; }}
QScrollArea {{ border: none; background: {BG}; }}
QScrollBar:vertical {{ background: {BG2}; width: 8px; border-radius: 4px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QLabel {{ background: transparent; color: {TEXT}; }}
QCheckBox {{ background: transparent; color: {TEXT}; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {BORDER}; border-radius: 3px; background: {BG2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}
"""

def apply_dark_palette(app):
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(BG))
    p.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Base, QColor(BG2))
    p.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Button, QColor(BTN_BG))
    p.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    app.setPalette(p)

# ─────────────────────────── БД ───────────────────────────

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT "user"
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS grants (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        title        TEXT NOT NULL,
        organizer    TEXT NOT NULL,
        max_amount   TEXT,
        deadline     TEXT,
        target       TEXT,
        description  TEXT,
        requirements TEXT,
        url          TEXT,
        status       TEXT NOT NULL DEFAULT "Прием заявок"
    )''')
    # Таблица связи "Многие-ко-многим" (Избранное)
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER,
        grant_id INTEGER,
        PRIMARY KEY (user_id, grant_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(grant_id) REFERENCES grants(id) ON DELETE CASCADE
    )''')
    
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO users (username,password,role) VALUES (?,?,?)",[
            ('admin', 'admin123', 'admin'),
            ('user',  'user123',  'user'),
        ])
    c.execute("SELECT COUNT(*) FROM grants")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO grants (title,organizer,max_amount,deadline,target,"
            "description,requirements,url,status) VALUES (?,?,?,?,?,?,?,?,?)",[
            ('Президентская программа исследовательских проектов', 'РНФ',
             'до 6 млн руб./год', '15.09.2025', 'Научные группы',
             'Поддержка фундаментальных и поисковых научных исследований.',
             'Наличие публикаций в РИНЦ, возраст руководителя до 35 лет.',
             'https://rscf.ru', 'Прием заявок'),
            ('Конкурс малых отдельных научных групп', 'РНФ',
             'до 1.5 млн руб./год', '01.10.2025', 'Малые группы (2-4 чел.)',
             'Поддержка малых групп для проведения инициативных исследований.',
             'Публикации в Web of Science / Scopus за последние 5 лет.',
             'https://rscf.ru', 'Экспертиза'),
            ('Конкурс на лучшие проекты фундаментальных исследований', 'РФФИ',
             'до 700 тыс. руб./год', '28.02.2025', 'Индивидуальные исследователи',
             'Поддержка инициативных проектов фундаментальных исследований.',
             'Степень кандидата или доктора наук.',
             'https://www.rfbr.ru', 'Завершенные'),
            ('Грант для молодых учёных', 'Минобрнауки',
             'до 2 млн руб.', '30.11.2025', 'Молодые учёные до 35 лет',
             'Поддержка молодых исследователей в области ИТ и ИБ.',
             'Возраст до 35 лет, наличие публикаций.',
             'https://minobrnauki.gov.ru', 'Прием заявок'),
        ])
    conn.commit()
    conn.close()

# ─────────────────────────── Диалог: детали гранта ───────────────────────────

class GrantDetailDialog(QDialog):
    def __init__(self, g, parent=None):
        super().__init__(parent)
        self.g = g
        self.setWindowTitle(g['title'])
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        sc = GREEN if g['status'] != 'Завершенные' else RED
        badge = QLabel(g['status'])
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(28)
        badge.setStyleSheet(
            f"background:transparent; color:{sc}; border:1px solid {sc}; "
            f"border-radius:4px; font-weight:bold; padding:2px 10px;"
        )
        layout.addWidget(badge)

        t = QLabel(g['title'])
        t.setFont(QFont("Sans", 12, QFont.Weight.Bold))
        t.setWordWrap(True)
        layout.addWidget(t)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{BORDER};")
        layout.addWidget(sep)

        for label, value in [
            ("Организатор",    g['organizer']),
            ("Макс. сумма",    g['max_amount']),
            ("Дедлайн",        g['deadline']),
            ("Целевая группа", g['target']),
        ]:
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 2, 0, 2)
            lbl = QLabel(label + ":")
            lbl.setFixedWidth(150)
            lbl.setStyleSheet(f"color:{TEXT_DIM};")
            val = QLabel(str(value) if value else "—")
            val.setWordWrap(True)
            h.addWidget(lbl)
            h.addWidget(val, 1)
            layout.addWidget(w)

        for section, text in [("Описание", g['description']), ("Требования", g['requirements'])]:
            lbl = QLabel(section)
            lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
            layout.addWidget(lbl)
            box = QLabel(text or "—")
            box.setWordWrap(True)
            box.setStyleSheet(f"color:{TEXT}; background:{BG2}; border-radius:5px; padding:8px;")
            layout.addWidget(box)

        if g.get('url'):
            url = QLabel(f'<a href="{g["url"]}" style="color:{ACCENT};">{g["url"]}</a>')
            url.setOpenExternalLinks(True)
            layout.addWidget(url)

        # Панель кнопок (добавление в избранное прямо из режима просмотра)
        btn_layout = QHBoxLayout()
        
        self.btn_fav_dialog = QPushButton()
        self.btn_fav_dialog.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_fav_btn_ui()
        self.btn_fav_dialog.clicked.connect(self._toggle_fav)
        
        btn_close = QPushButton("Закрыть")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_fav_dialog)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)

    def _update_fav_btn_ui(self):
        """Обновление внешнего вида кнопки избранного в деталях."""
        if self.g.get('is_fav'):
            self.btn_fav_dialog.setText("★ Убрать из избранного")
            self.btn_fav_dialog.setStyleSheet(f"background: transparent; color: {STAR}; border: 1px solid {STAR}; font-weight: bold;")
        else:
            self.btn_fav_dialog.setText("☆ Добавить в избранное")
            self.btn_fav_dialog.setStyleSheet(f"background: transparent; color: {TEXT}; border: 1px solid {BORDER}; font-weight: bold;")

    def _toggle_fav(self):
        """Переключает статус через родительскую карточку."""
        if isinstance(self.parent(), GrantCard):
            self.parent().toggle_fav()
            self._update_fav_btn_ui()


# ─────────────────────────── Диалог: редактирование ───────────────────────────

class GrantEditDialog(QDialog):
    def __init__(self, grant_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить грант" if not grant_data else "Редактировать грант")
        self.setMinimumWidth(500)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.f_title  = QLineEdit()
        self.f_org    = QLineEdit()
        self.f_amount = QLineEdit()
        self.f_dead   = QLineEdit()
        self.f_dead.setPlaceholderText("ДД.ММ.ГГГГ")
        self.f_target = QLineEdit()
        self.f_desc   = QTextEdit()
        self.f_desc.setFixedHeight(80)
        self.f_req    = QTextEdit()
        self.f_req.setFixedHeight(80)
        self.f_url    = QLineEdit()
        self.f_status = QComboBox()
        self.f_status.addItems(["Прием заявок", "Экспертиза", "Завершенные"])

        if grant_data:
            self.f_title.setText(grant_data.get('title', ''))
            self.f_org.setText(grant_data.get('organizer', ''))
            self.f_amount.setText(grant_data.get('max_amount', '') or '')
            self.f_dead.setText(grant_data.get('deadline', '') or '')
            self.f_target.setText(grant_data.get('target', '') or '')
            self.f_desc.setPlainText(grant_data.get('description', '') or '')
            self.f_req.setPlainText(grant_data.get('requirements', '') or '')
            self.f_url.setText(grant_data.get('url', '') or '')
            idx = self.f_status.findText(grant_data.get('status', ''))
            if idx >= 0:
                self.f_status.setCurrentIndex(idx)

        layout.addRow("Название *",     self.f_title)
        layout.addRow("Организатор *",  self.f_org)
        layout.addRow("Макс. сумма",    self.f_amount)
        layout.addRow("Дедлайн",        self.f_dead)
        layout.addRow("Целевая группа", self.f_target)
        layout.addRow("Описание",       self.f_desc)
        layout.addRow("Требования",     self.f_req)
        layout.addRow("Ссылка",         self.f_url)
        layout.addRow("Статус",         self.f_status)

        btn = QPushButton("Сохранить")
        btn.setStyleSheet(f"background:{ACCENT}; color:{BG}; font-weight:bold; border:none;")
        btn.clicked.connect(self._save)
        layout.addRow(btn)

    def _save(self):
        if not self.f_title.text().strip() or not self.f_org.text().strip():
            QMessageBox.warning(self, "Ошибка", "Заполните обязательные поля (*)!")
            return
        self.accept()

    def get_data(self):
        return {
            'title':        self.f_title.text().strip(),
            'organizer':    self.f_org.text().strip(),
            'max_amount':   self.f_amount.text().strip(),
            'deadline':     self.f_dead.text().strip(),
            'target':       self.f_target.text().strip(),
            'description':  self.f_desc.toPlainText().strip(),
            'requirements': self.f_req.toPlainText().strip(),
            'url':          self.f_url.text().strip(),
            'status':       self.f_status.currentText(),
        }

# ─────────────────────────── Карточка гранта ───────────────────────────

class GrantCard(QFrame):
    def __init__(self, grant, is_admin, on_edit, on_delete, on_fav_toggle, parent=None):
        super().__init__(parent)
        self.grant = grant
        self.on_fav_toggle = on_fav_toggle
        self.setFixedHeight(200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        sc = BLUE_UI if grant['status'] != 'Завершенные' else RED
        self.setStyleSheet(f"""
            GrantCard {{
                background: {BG2}; border-radius: 8px;
                border: 1px solid {sc}; border-left: 4px solid {sc};
            }}
            GrantCard:hover {{ background: {BG3}; border: 1px solid {sc}; border-left: 4px solid {sc}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)

        # Заголовок + Звездочка + Чекбокс выделения (для удаления)
        top = QHBoxLayout()
        
        self.chk_sel = QCheckBox()
        self.chk_sel.setToolTip("Выделить карточку")
        self.chk_sel.setVisible(is_admin)
        self.chk_sel.setStyleSheet(f"QCheckBox::indicator {{ width: 20px; height: 20px; }} QCheckBox::indicator:unchecked {{ border: 2px solid {BORDER}; }}")
        top.addWidget(self.chk_sel)
        
        title = QLabel(grant['title'])
        title.setFont(QFont("Sans", 10, QFont.Weight.Bold))
        title.setWordWrap(True)
        title.setStyleSheet("background:transparent;")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.btn_fav = QPushButton("★" if grant['is_fav'] else "☆")
        self.btn_fav.setFixedSize(28, 28)
        self.btn_fav.setCursor(Qt.CursorShape.PointingHandCursor)
        fav_color = STAR if grant['is_fav'] else TEXT_DIM
        self.btn_fav.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {fav_color}; font-size: 18px; border: none; }}
            QPushButton:hover {{ color: {STAR}; }}
        """)
        self.btn_fav.clicked.connect(self.toggle_fav)
        
        top.addWidget(title, 1)
        top.addWidget(self.btn_fav)
        layout.addLayout(top)

        # Инфо-поля
        grid = QGridLayout()
        grid.setSpacing(2)
        fields =[
            ("Организатор", grant['organizer']),
            ("Сумма",       grant['max_amount'] or "—"),
            ("Дедлайн",     grant['deadline'] or "—"),
            ("Кому",        grant['target'] or "—"),
        ]
        for i, (lbl, val) in enumerate(fields):
            r, col = divmod(i, 2)
            cell = QLabel(f'<span style="color:{TEXT_DIM};font-size:10px;">{lbl}: </span>'
                          f'<span style="color:{TEXT};font-size:10px;">{val}</span>')
            cell.setWordWrap(True)
            cell.setStyleSheet("background:transparent;")
            grid.addWidget(cell, r, col)
        layout.addLayout(grid)

        desc = grant['description'] or ''
        preview = desc[:110] + ('…' if len(desc) > 110 else '')
        dlbl = QLabel(preview)
        dlbl.setWordWrap(True)
        dlbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; background:transparent;")
        layout.addWidget(dlbl)
        layout.addStretch()

        # Кнопки для админа
        if is_admin:
            brow = QHBoxLayout()
            brow.addStretch()
            be = QPushButton("Изменить")
            be.setFixedHeight(24)
            be.setStyleSheet(f"""
                QPushButton {{ font-size: 11px; padding: 0 12px; border: 1px solid {ACCENT}; color: {ACCENT}; }}
                QPushButton:hover {{ background: {ACCENT}; color: {BG}; }}
            """)
            be.clicked.connect(lambda: on_edit(grant))
            
            bd = QPushButton("Удалить")
            bd.setFixedHeight(24)
            bd.setStyleSheet(f"""
                QPushButton {{ font-size: 11px; padding: 0 12px; border: 1px solid {TRUE_RED}; color: {TRUE_RED}; }}
                QPushButton:hover {{ background: {TRUE_RED}; color: {BG}; }}
            """)
            bd.clicked.connect(lambda: on_delete(grant['id']))
            brow.addWidget(be); brow.addWidget(bd)
            layout.addLayout(brow)

    def toggle_fav(self):
        new_state = not self.grant['is_fav']
        self.grant['is_fav'] = new_state
        fav_color = STAR if new_state else TEXT_DIM
        self.btn_fav.setText("★" if new_state else "☆")
        self.btn_fav.setStyleSheet(f"QPushButton {{ background: transparent; color: {fav_color}; font-size: 18px; border: none; }} QPushButton:hover {{ color: {STAR}; }}")
        self.on_fav_toggle(self.grant['id'], new_state)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            GrantDetailDialog(self.grant, self).exec()

# ─────────────────────────── Оверлей загрузки ───────────────────────────

class LoadingOverlay(QWidget):
    """Полупрозрачный оверлей поверх дашборда во время парсинга."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet(f"background: rgba(20, 20, 35, 200); border-radius: 0px;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setFixedSize(340, 130)
        card.setStyleSheet(f"""
            QFrame {{
                background: {BG2};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(20, 20, 20, 20)

        spinner_lbl = QLabel("⟳")
        spinner_lbl.setFont(QFont("Sans", 28))
        spinner_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent; border: none;")
        card_layout.addWidget(spinner_lbl)

        self.status_lbl = QLabel("Идёт сбор данных с сайта РНФ…")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px; background: transparent; border: none;")
        self.status_lbl.setWordWrap(True)
        card_layout.addWidget(self.status_lbl)

        hint_lbl = QLabel("Пожалуйста, подождите")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        card_layout.addWidget(hint_lbl)

        layout.addWidget(card)

        # Анимация точек
        from PyQt6.QtCore import QTimer
        self._dot_count = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate_spinner)
        self._timer.start(400)

    def _animate_spinner(self):
        frames = ["⟳", "↻", "⟲", "↺"]
        self._dot_count = (self._dot_count + 1) % len(frames)
        # Обновляем текст статуса с анимированными точками
        dots = "." * (self._dot_count + 1)
        self.status_lbl.setText(f"Идёт сбор данных с сайта РНФ{dots}")

    def show_over(self, parent_widget):
        self.setParent(parent_widget)
        self.resize(parent_widget.size())
        self.raise_()
        self.show()

    def hide_overlay(self):
        self._timer.stop()
        self.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.resize(self.parent().size())

# ─────────────────────────── Дашборд ───────────────────────────

class DashboardWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._loading_overlay = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # Шапка
        hdr = QHBoxLayout()
        ttl = QLabel("База грантов и конкурсов")
        ttl.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        hdr.addWidget(ttl)
        hdr.addStretch()
        self.user_label = QLabel()
        self.user_label.setStyleSheet(f"color:{TEXT_DIM};")
        hdr.addWidget(self.user_label)
        btn_out = QPushButton("Выйти")
        btn_out.clicked.connect(self.main_window.show_login)
        hdr.addWidget(btn_out)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{BORDER};")
        root.addWidget(sep)

        # ── Строка 1: фильтры ──
        filters_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по названию...")
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(self.load_grants)

        self.f_status = QComboBox()
        self.f_status.addItems(["Все", "Прием заявок", "Экспертиза", "Завершенные"])
        self.f_status.currentIndexChanged.connect(self.load_grants)

        self.f_org = QComboBox()
        self.f_org.addItem("Все организаторы")
        self.f_org.currentIndexChanged.connect(self.load_grants)

        self.chk_fav = QCheckBox("Только избранные ★")
        self.chk_fav.stateChanged.connect(self.load_grants)

        filters_row.addWidget(QLabel("Статус:"))
        filters_row.addWidget(self.f_status)
        filters_row.addWidget(QLabel("Организатор:"))
        filters_row.addWidget(self.f_org)
        filters_row.addWidget(self.search)
        filters_row.addWidget(self.chk_fav)
        filters_row.addStretch()
        root.addLayout(filters_row)

        # ── Строка 2: кнопки действий ──
        actions_row = QHBoxLayout()

        self.btn_add = QPushButton("+ Добавить грант")
        self.btn_add.setStyleSheet(f"background:{ACCENT}; color:{BG}; font-weight:bold; border:none;")
        self.btn_add.clicked.connect(self.add_grant)

        # "Выбрать все" — видна только для admin, когда есть карточки
        self.btn_sel_all = QPushButton("Выбрать все")
        self.btn_sel_all.setStyleSheet(f"QPushButton {{ color:{TEXT}; border:1px solid {BLUE_UI}; }} QPushButton:hover {{ border:1px solid {BLUE_UI}; color:{TEXT}; }}")
        self.btn_sel_all.clicked.connect(self.select_all_cards)
        self.btn_sel_all.setVisible(False)

        # "Удалить выбранные" — видна только когда хотя бы одна карточка отмечена
        self.btn_del_multi = QPushButton("Удалить выбранные")
        self.btn_del_multi.setStyleSheet(f"QPushButton {{ color:{TRUE_RED}; border:1px solid {TRUE_RED}; }} QPushButton:hover {{ border:1px solid {TRUE_RED}; color:{TRUE_RED}; }}")
        self.btn_del_multi.clicked.connect(self.delete_selected_grants)
        self.btn_del_multi.setVisible(False)

        self.btn_export = QPushButton("Экспорт Excel")
        self.btn_export.setStyleSheet(f"QPushButton {{ color:{TEXT}; border:1px solid {BLUE_UI}; }} QPushButton:hover {{ border:1px solid {BLUE_UI}; color:{TEXT}; }}")
        self.btn_export.clicked.connect(self.export_excel)

        self.btn_parse = QPushButton("⟳ Обновить (РНФ)")
        self.btn_parse.setStyleSheet(f"QPushButton {{ color:{TEXT}; border:1px solid {BLUE_UI}; }} QPushButton:hover {{ border:1px solid {BLUE_UI}; color:{TEXT}; }}")
        self.btn_parse.clicked.connect(self.run_parser)

        actions_row.addWidget(self.btn_add)
        actions_row.addWidget(self.btn_sel_all)
        actions_row.addWidget(self.btn_del_multi)
        actions_row.addStretch()
        actions_row.addWidget(self.btn_parse)
        actions_row.addWidget(self.btn_export)
        root.addLayout(actions_row)

        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        root.addWidget(self.count_lbl)

        # Сетка
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.container)
        root.addWidget(scroll)

    def setup(self):
        u = self.main_window.current_user
        self.user_label.setText(f"{u['username']}  [{u['role']}]")
        self.btn_add.setVisible(u['role'] == 'admin')
        # "Выбрать все" показываем для admin — видимость уточнится в load_grants/update_multi_sel_ui
        self.btn_sel_all.setVisible(False)
        self.btn_del_multi.setVisible(False)
        self.btn_parse.setVisible(u['role'] == 'admin')
        self.chk_fav.setChecked(False)
        self._refresh_orgs()
        self.load_grants()

    def _refresh_orgs(self):
        conn = sqlite3.connect(DB_NAME)
        orgs = [r[0] for r in conn.execute("SELECT DISTINCT organizer FROM grants ORDER BY organizer").fetchall()]
        conn.close()
        cur = self.f_org.currentText()
        self.f_org.blockSignals(True)
        self.f_org.clear()
        self.f_org.addItem("Все организаторы")
        self.f_org.addItems(orgs)
        self.f_org.setCurrentIndex(max(0, self.f_org.findText(cur)))
        self.f_org.blockSignals(False)

    def load_grants(self, *args):
        u_id = self.main_window.current_user['id']
        conn = sqlite3.connect(DB_NAME)
        
        # JOIN для связи "Многие-ко-многим" (Избранное)
        q = """
            SELECT g.id, g.title, g.organizer, g.max_amount, g.deadline, g.target,
                   g.description, g.requirements, g.url, g.status,
                   CASE WHEN f.grant_id IS NOT NULL THEN 1 ELSE 0 END as is_fav
            FROM grants g
            LEFT JOIN favorites f ON g.id = f.grant_id AND f.user_id = ?
            WHERE 1=1
        """
        params = [u_id]
        
        if self.chk_fav.isChecked():
            q += " AND is_fav = 1"
        status_map = {
            "Прием заявок": "Прием заявок",
            "Экспертиза": "Экспертиза",
            "Завершенные": "Завершенные",
        }
        selected_status = self.f_status.currentText()
        if selected_status in status_map:
            q += " AND g.status=?"; params.append(status_map[selected_status])
        if self.f_org.currentText() != "Все организаторы":
            q += " AND g.organizer=?"; params.append(self.f_org.currentText())
        
        s = self.search.text().strip()
        if s:
            q += " AND g.title LIKE ?"; params.append(f"%{s}%")
            
        q += " ORDER BY g.status DESC, g.deadline"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        keys =['id','title','organizer','max_amount','deadline','target',
                'description','requirements','url','status', 'is_fav']
        grants =[dict(zip(keys, r)) for r in rows]

        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        is_admin = self.main_window.current_user['role'] == 'admin'
        cols = 2
        for i, g in enumerate(grants):
            card = GrantCard(g, is_admin, self.edit_grant, self.delete_grant, self.toggle_fav_db)
            if is_admin:
                card.chk_sel.toggled.connect(self.update_multi_sel_ui)
            self.grid.addWidget(card, i // cols, i % cols)

        # "Выбрать все" показываем для админа только если есть карточки
        if is_admin:
            self.btn_sel_all.setVisible(len(grants) > 0)

        self.update_multi_sel_ui()

        if not grants:
            lbl = QLabel("Ничего не найдено")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:14px; padding:40px;")
            self.grid.addWidget(lbl, 0, 0, 1, cols)

        self.count_lbl.setText(f"Найдено: {len(grants)}")

    def toggle_fav_db(self, grant_id, is_fav):
        u_id = self.main_window.current_user['id']
        conn = sqlite3.connect(DB_NAME)
        if is_fav:
            conn.execute("INSERT OR IGNORE INTO favorites (user_id, grant_id) VALUES (?,?)", (u_id, grant_id))
        else:
            conn.execute("DELETE FROM favorites WHERE user_id=? AND grant_id=?", (u_id, grant_id))
        conn.commit()
        conn.close()

    def add_grant(self):
        dlg = GrantEditDialog(parent=self)
        if dlg.exec():
            d = dlg.get_data()
            conn = sqlite3.connect(DB_NAME)
            conn.execute(
                "INSERT INTO grants (title,organizer,max_amount,deadline,target,description,requirements,url,status) VALUES (?,?,?,?,?,?,?,?,?)",
                (d['title'],d['organizer'],d['max_amount'],d['deadline'],d['target'],d['description'],d['requirements'],d['url'],d['status']))
            conn.commit(); conn.close()
            self._refresh_orgs(); self.load_grants()

    def edit_grant(self, grant):
        dlg = GrantEditDialog(grant_data=grant, parent=self)
        if dlg.exec():
            d = dlg.get_data()
            conn = sqlite3.connect(DB_NAME)
            conn.execute(
                "UPDATE grants SET title=?,organizer=?,max_amount=?,deadline=?,target=?,description=?,requirements=?,url=?,status=? WHERE id=?",
                (d['title'],d['organizer'],d['max_amount'],d['deadline'],d['target'],d['description'],d['requirements'],d['url'],d['status'],grant['id']))
            conn.commit(); conn.close()
            self._refresh_orgs(); self.load_grants()

    def delete_grant(self, gid):
        if QMessageBox.question(self, "Удаление", "Удалить этот грант?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM grants WHERE id=?", (gid,))
            conn.commit(); conn.close()
            self.load_grants()

    def update_multi_sel_ui(self):
        """Показывает/скрывает 'Удалить выбранные' в зависимости от наличия отмеченных карточек."""
        if self.main_window.current_user['role'] != 'admin':
            return
        has_sel = any(
            isinstance(self.grid.itemAt(i).widget(), GrantCard) and self.grid.itemAt(i).widget().chk_sel.isChecked() 
            for i in range(self.grid.count()) if self.grid.itemAt(i)
        )
        self.btn_del_multi.setVisible(has_sel)
        
    def select_all_cards(self):
        for i in range(self.grid.count()):
            w = self.grid.itemAt(i)
            if w and isinstance(w.widget(), GrantCard):
                w.widget().chk_sel.setChecked(True)

    def delete_selected_grants(self):
        to_delete = []
        for i in range(self.grid.count()):
            w = self.grid.itemAt(i)
            if w:
                widget = w.widget()
                if isinstance(widget, GrantCard) and widget.chk_sel.isChecked():
                    to_delete.append(widget.grant['id'])
                
        if not to_delete:
            QMessageBox.warning(self, "Пусто", "Сначала выделите карточки галочками (в левом верхнем углу карточки)!")
            return
            
        if QMessageBox.question(self, "Массовое удаление", f"Удалить {len(to_delete)} выделенных грантов?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executemany("DELETE FROM grants WHERE id=?", [(gid,) for gid in to_delete])
            conn.commit(); conn.close()
            self.load_grants()

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", "grants_report.xlsx", "Excel Files (*.xlsx)")
        if not path: return
        conn = sqlite3.connect(DB_NAME)
        
        # Если включен фильтр избранного, выгружаем только избранные
        if self.chk_fav.isChecked():
            u_id = self.main_window.current_user['id']
            query = """
                SELECT g.title AS 'Название', g.organizer AS 'Организатор', 
                g.max_amount AS 'Макс. сумма', g.deadline AS 'Дедлайн', 
                g.target AS 'Целевая группа', g.status AS 'Статус', g.url AS 'Ссылка'
                FROM grants g
                JOIN favorites f ON g.id = f.grant_id
                WHERE f.user_id = ?
                ORDER BY g.status DESC, g.deadline
            """
            df = pd.read_sql_query(query, conn, params=(u_id,))
        else:
            df = pd.read_sql_query("SELECT title AS 'Название', organizer AS 'Организатор', max_amount AS 'Макс. сумма', deadline AS 'Дедлайн', target AS 'Целевая группа', status AS 'Статус', url AS 'Ссылка' FROM grants ORDER BY status DESC, deadline", conn)
        conn.close()
        try:
            df.to_excel(path, index=False)
            QMessageBox.information(self, "Готово", f"Отчёт сохранён:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def run_parser(self):
        dlg = RnfFilterDialog(self)
        if not dlg.exec():
            return
            
        settings = dlg.get_settings()

        main_win = self.main_window
        self._loading_overlay = LoadingOverlay(main_win)
        self._loading_overlay.show_over(main_win)
        
        # Блокируем кнопки управления на время загрузки
        self.btn_parse.setEnabled(False)
        self.btn_add.setEnabled(False)
        
        self.thread = ParserThread(settings['target_status'], settings['date_start'], settings['date_end'])
        self.thread.finished_signal.connect(self.on_parser_finished)
        self.thread.start()
        
    def on_parser_finished(self, grants_parsed, error_str):
        # Скрываем оверлей и разблокируем кнопки
        if self._loading_overlay:
            self._loading_overlay.hide_overlay()
            self._loading_overlay = None
        self.btn_parse.setEnabled(True)
        self.btn_add.setEnabled(True)

        if error_str:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при парсинге:\n{error_str}")
            return
            
        if not grants_parsed:
            QMessageBox.warning(self, "Парсер", "Не удалось извлечь данные или конкурсов для вашего фильтра нет.")
            return
        
        conn = sqlite3.connect(DB_NAME)
        added = 0
        for g in grants_parsed:
            cur = conn.execute("SELECT id FROM grants WHERE title=?", (g['title'],)).fetchone()
            if not cur:
                conn.execute(
                    "INSERT INTO grants (title,organizer,max_amount,deadline,target,description,requirements,url,status) VALUES (?,?,?,?,?,?,?,?,?)",
                    (g['title'], g['organizer'], g['max_amount'], g['deadline'], g['target'], g['description'], g['requirements'], g['url'], g['status'])
                )
                added += 1
        conn.commit()
        conn.close()
        QMessageBox.information(self, "Готово", f"Обработано конкурсов: {len(grants_parsed)}\nДобавлено новых в БД: {added}")
        self._refresh_orgs()
        self.load_grants()

class ParserThread(QThread):
    finished_signal = pyqtSignal(list, str)
    
    def __init__(self, target_status, date_start, date_end):
        super().__init__()
        self.target_status = target_status
        self.date_start = date_start
        self.date_end = date_end
        
    def run(self):
        try:
            grants = parser_rnf.parse_rnf_grants(
                target_status=self.target_status,
                date_start=self.date_start,
                date_end=self.date_end
            )
            self.finished_signal.emit(grants, "")
        except Exception as e:
            self.finished_signal.emit([], str(e))

class RnfFilterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cбор данных РНФ")
        self.setFixedWidth(400)
        layout = QVBoxLayout(self)
        
        lbl = QLabel("Фильтрация конкурсных программ")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(lbl)
        
        from PyQt6.QtWidgets import QComboBox, QDateEdit, QGroupBox, QFormLayout
        from PyQt6.QtCore import QDate
        
        # 1. Группа "Статус"
        group_status = QGroupBox("Статус (Этап конкурса)")
        status_layout = QVBoxLayout()
        self.combo_status = QComboBox()
        self.combo_status.addItems(["Все", "Прием заявок", "Экспертиза", "Завершенные"])
        status_layout.addWidget(self.combo_status)
        group_status.setLayout(status_layout)
        layout.addWidget(group_status)
        
        # 2. Группа "Календарные рамки"
        group_dates = QGroupBox("Ограничение по срокам приёма")
        dates_vbox = QVBoxLayout()
        
        lbl_date_desc = QLabel("Будут загруженны только те конкурсы,\nдедлайн которых попадает в указанный диапазон.")
        lbl_date_desc.setStyleSheet(f"color:{TEXT_DIM}; font-size: 11px;")
        dates_vbox.addWidget(lbl_date_desc)
        
        form_dates = QFormLayout()
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addMonths(-6))
        form_dates.addRow("С:", self.date_start)
        
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate().addMonths(12))
        form_dates.addRow("По:", self.date_end)
        
        dates_vbox.addLayout(form_dates)
        group_dates.setLayout(dates_vbox)
        layout.addWidget(group_dates)
        
        # Кнопки
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def get_settings(self):
        d_start = self.date_start.date().toPyDate()
        d_end = self.date_end.date().toPyDate()
        
        status_val = self.combo_status.currentText()
        if "Все" in status_val:
            status_val = "Все"
            
        return {
            'target_status': status_val,
            'date_start': d_start,
            'date_end': d_end
        }

# ─────────────────────────── Экран входа / Регистрации ───────────────────────────

class LoginWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        outer = QVBoxLayout(self)
        
        card = QFrame()
        card.setFixedWidth(360)
        card.setStyleSheet(f"QFrame {{ background:{BG2}; border-radius:12px; border:1px solid {BORDER}; }}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(32, 32, 32, 32)
        cl.setSpacing(14)

        logo = QLabel("🎓")
        logo.setFont(QFont("Sans", 36))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background:transparent; border:none;")
        cl.addWidget(logo)

        ttl = QLabel("База грантов и конкурсов")
        ttl.setFont(QFont("Sans", 13, QFont.Weight.Bold))
        ttl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ttl.setStyleSheet(f"color:{TEXT}; background:transparent; border:none;")
        cl.addWidget(ttl)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Логин")
        self.username_input.setFixedHeight(38)
        cl.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(38)
        cl.addWidget(self.password_input)

        btn_box = QHBoxLayout()
        self.btn_login = QPushButton("Войти")
        self.btn_login.setFixedHeight(38)
        self.btn_login.setStyleSheet(f"background:{ACCENT}; color:{BG}; border:none; font-weight:bold;")
        self.btn_login.clicked.connect(self.login)
        
        self.btn_reg = QPushButton("Регистрация")
        self.btn_reg.setFixedHeight(38)
        self.btn_reg.setStyleSheet(f"background:{BG3}; color:{TEXT}; border:1px solid {BORDER};")
        self.btn_reg.clicked.connect(self.register)
        
        btn_box.addWidget(self.btn_login, 1)
        btn_box.addWidget(self.btn_reg, 1)
        cl.addLayout(btn_box)

        hint = QLabel("admin / admin123   •   user / user123")
        hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; background:transparent; border:none;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(hint)

        row = QHBoxLayout()
        row.addStretch(); row.addWidget(card); row.addStretch()
        outer.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def login(self):
        conn = sqlite3.connect(DB_NAME)
        row = conn.execute("SELECT id,role FROM users WHERE username=? AND password=?",
            (self.username_input.text(), self.password_input.text())).fetchone()
        conn.close()
        if row:
            self.main_window.current_user = {'id': row[0], 'role': row[1], 'username': self.username_input.text()}
            self.main_window.show_dashboard()
        else:
            QMessageBox.warning(self, "Ошибка", "Неверный логин или пароль!")

    def register(self):
        u, p = self.username_input.text().strip(), self.password_input.text().strip()
        if not u or not p:
            QMessageBox.warning(self, "Ошибка", "Введите логин и пароль для регистрации!")
            return
        try:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'user')", (u, p))
            conn.commit()
            QMessageBox.information(self, "Успех", "Регистрация прошла успешно! Теперь вы можете войти.")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Ошибка", "Такой пользователь уже существует!")
        finally:
            conn.close()

# ─────────────────────────── Главное окно ───────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("База грантов и конкурсов")
        self.setGeometry(100, 100, 1100, 700)
        self.current_user = None
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.login_w     = LoginWidget(self)
        self.dashboard_w = DashboardWidget(self)
        self.stack.addWidget(self.login_w)
        self.stack.addWidget(self.dashboard_w)

    def show_login(self):
        self.current_user = None
        self.stack.setCurrentWidget(self.login_w)

    def show_dashboard(self):
        self.dashboard_w.setup()
        self.stack.setCurrentWidget(self.dashboard_w)

# ─────────────────────────── Запуск ───────────────────────────

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_dark_palette(app)
    app.setStyleSheet(DARK_SS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
