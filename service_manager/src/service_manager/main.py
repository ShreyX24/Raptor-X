"""
Main application entry point
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from .ui.main_window import MainWindow


def main():
    """Launch the Service Manager application"""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("Gemma Service Manager")
    app.setOrganizationName("Gemma")
    
    # Set default font
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    # Apply dark theme stylesheet
    app.setStyleSheet(get_stylesheet())
    
    window = MainWindow()
    window.showMaximized()  # Open in fullscreen/maximized mode
    
    sys.exit(app.exec())


def get_stylesheet() -> str:
    """Get the application stylesheet"""
    return """
        QMainWindow {
            background-color: #1e1e1e;
        }
        QWidget {
            background-color: #252526;
            color: #cccccc;
        }
        QTreeWidget {
            background-color: #252526;
            border: none;
            outline: none;
        }
        QTreeWidget::item {
            padding: 4px;
            border-radius: 3px;
        }
        QTreeWidget::item:selected {
            background-color: #094771;
        }
        QTreeWidget::item:hover {
            background-color: #2a2d2e;
        }
        QTreeWidget::branch {
            background-color: #252526;
        }
        QHeaderView::section {
            background-color: #333333;
            color: #cccccc;
            padding: 4px;
            border: none;
        }
        QToolBar {
            background-color: #333333;
            border: none;
            spacing: 4px;
            padding: 4px;
        }
        QToolButton {
            background-color: transparent;
            border: none;
            border-radius: 3px;
            padding: 4px 8px;
            color: #cccccc;
        }
        QToolButton:hover {
            background-color: #404040;
        }
        QToolButton:pressed {
            background-color: #505050;
        }
        QPushButton {
            background-color: #0e639c;
            border: none;
            border-radius: 3px;
            padding: 6px 14px;
            color: white;
        }
        QPushButton:hover {
            background-color: #1177bb;
        }
        QPushButton:pressed {
            background-color: #094771;
        }
        QPushButton:disabled {
            background-color: #3a3a3a;
            color: #6a6a6a;
        }
        QStatusBar {
            background-color: #007acc;
            color: white;
        }
        QSplitter::handle {
            background-color: #333333;
        }
        QSplitter::handle:horizontal {
            width: 2px;
        }
        QSplitter::handle:vertical {
            height: 2px;
        }
        QPlainTextEdit {
            background-color: #1e1e1e;
            color: #d4d4d4;
            border: none;
            font-family: Consolas, monospace;
            font-size: 9pt;
        }
        QLabel {
            color: #cccccc;
        }
        QMenu {
            background-color: #252526;
            border: 1px solid #454545;
        }
        QMenu::item {
            padding: 5px 25px;
        }
        QMenu::item:selected {
            background-color: #094771;
        }
        QScrollBar:vertical {
            background-color: #1e1e1e;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #424242;
            min-height: 20px;
            border-radius: 3px;
            margin: 2px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #525252;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
    """


if __name__ == "__main__":
    main()
