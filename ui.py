from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                             QListWidget, QProgressBar, QSystemTrayIcon, QMenu,
                             QTabWidget, QLineEdit, QSpinBox, QMessageBox,
                             QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                             QTextEdit, QStyle, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QPalette, QColor, QFont, QTextCursor
import sys
import os
import threading
from pathlib import Path
import main as utils
import datetime
import pandas as pd
import sqlite3
import pyperclip
import matplotlib.pyplot as plt
from collections import defaultdict
from settings import Settings
from logger import Logger

# Initialize logger and settings
logger = Logger()
settings = Settings()

# Color scheme
COLORS = {
    'bg_primary': '#FFFAEC',
    'bg_secondary': '#F5ECD5',
    'accent': '#578E7E',
    'text': '#3D3D3D'
}

class StyleSheet:
    @staticmethod
    def get_style():
        return f"""
        QMainWindow, QWidget {{
            background-color: {COLORS['bg_primary']};
            color: {COLORS['text']};
        }}
        
        QPushButton {{
            background-color: {COLORS['accent']};
            color: {COLORS['bg_primary']};
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        QPushButton:hover {{
            background-color: {COLORS['text']};
        }}
        
        QLabel {{
            color: {COLORS['text']};
            font-size: 14px;
        }}
        
        QListWidget, QTableWidget, QTextEdit {{
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['accent']};
            border-radius: 4px;
            padding: 4px;
            font-family: monospace;
        }}
        
        QTabWidget::pane {{
            border: 1px solid {COLORS['accent']};
            border-radius: 4px;
            background-color: {COLORS['bg_secondary']};
        }}
        
        QTabBar::tab {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text']};
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {COLORS['accent']};
            color: {COLORS['bg_primary']};
        }}
        
        QLineEdit, QSpinBox {{
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['accent']};
            padding: 4px;
            border-radius: 4px;
        }}
        
        QProgressBar {{
            border: 1px solid {COLORS['accent']};
            border-radius: 4px;
            text-align: center;
        }}
        
        QProgressBar::chunk {{
            background-color: {COLORS['accent']};
        }}
        """

class ClipboardThread(QThread):
    clip_added = pyqtSignal(str)
    
    def __init__(self):
        super().__init__() 
        self._is_running = True
    
    def stop(self):
        """Safely stop the thread"""
        self._is_running = False
    
    def run(self):
        try:
            last_clip = ""
            while self._is_running:
                try:
                    clip = pyperclip.paste()
                    if clip and clip != last_clip and not clip.startswith("*****"):
                        self.clip_added.emit(clip)
                        last_clip = clip
                except Exception as e:
                    logger.error(f"Error monitoring clipboard: {e}")
                
                if self._is_running:  # Check again before sleep
                    QThread.msleep(100)  # Small delay to prevent high CPU usage
                    
        except Exception as e:
            logger.error(f"Critical error in clipboard monitor: {e}")
            
        finally:
            self._is_running = False

class SpeedTestThread(QThread):
    speed_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self._is_running = True
    
    def stop(self):
        """Safely stop the thread"""
        self._is_running = False
    
    def run(self):
        def log_callback(message):
            # Only emit progress if thread is still running
            if not self._is_running:
                raise InterruptedError("Speed test stopped by user")
            
            try:
                # Update progress based on message content
                progress = 0
                if "Finding best server" in message:
                    progress = 10
                elif "Testing download speed" in message:
                    progress = 30
                elif "Download speed:" in message:
                    progress = 60
                elif "Testing upload speed" in message:
                    progress = 70
                elif "Upload speed:" in message:
                    progress = 90
                elif "Speed test complete" in message:
                    progress = 100
                
                if progress > 0:
                    self.progress_updated.emit(progress)
                    
            except RuntimeError:
                # Handle case where thread is being stopped during emit
                raise InterruptedError("Thread stopping")
        
        try:
            if self._is_running:
                result = utils.internet_speed_blamer(log_callback)
                if self._is_running:  # Check again before emitting result
                    if result is not None:
                        self.speed_updated.emit(result)
                    else:
                        self.error_occurred.emit("Speed test failed - Check your internet connection")
                        
        except InterruptedError as e:
            logger.info(f"Speed test interrupted: {e}")
            
        except Exception as e:
            if self._is_running:  # Only emit error if thread wasn't stopped
                error_msg = str(e)
                logger.error(f"Speed Test Error: {error_msg}")
                self.error_occurred.emit(error_msg)
            
        finally:
            self._is_running = False

class DuplicateFinderThread(QThread):
    progress_updated = pyqtSignal(int)
    duplicates_found = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self._is_running = True
    
    def stop(self):
        """Safely stop the thread"""
        self._is_running = False
    
    def run(self):
        try:
            if not os.path.exists(self.directory):
                raise FileNotFoundError(f"Directory not found: {self.directory}")
            
            def progress_callback(value):
                if not self._is_running:
                    raise InterruptedError("Scan stopped by user")
                try:
                    self.progress_updated.emit(value)
                except RuntimeError:
                    # Handle case where thread is being stopped during emit
                    raise InterruptedError("Thread stopping")
            
            # Run the duplicate finder with progress tracking
            duplicates = utils.duplicate_file_finder(self.directory, progress_callback)
            
            # Only emit results if the thread wasn't stopped
            if self._is_running:
                self.duplicates_found.emit(duplicates)
                
        except InterruptedError as e:
            logger.info(f"Duplicate scan interrupted: {e}")
            self.duplicates_found.emit([])
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Duplicate Finder Error: {error_msg}")
            self.error_occurred.emit(error_msg)
            self.duplicates_found.emit([])
            
        finally:
            self._is_running = False

class ExtensionMappingDialog(QDialog):
    def __init__(self, parent=None, mappings=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Extension Mappings")
        self.setMinimumWidth(400)
        self.mappings = mappings or {}
        
        layout = QVBoxLayout(self)
        
        # Table for mappings
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Extension", "Folder"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # Add mapping inputs
        input_layout = QHBoxLayout()
        self.ext_input = QLineEdit()
        self.ext_input.setPlaceholderText(".ext")
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Folder Name")
        add_btn = QPushButton("Add Mapping")
        add_btn.clicked.connect(self.add_mapping)
        
        input_layout.addWidget(self.ext_input)
        input_layout.addWidget(self.folder_input)
        input_layout.addWidget(add_btn)
        layout.addLayout(input_layout)
        
        # Template buttons
        template_layout = QHBoxLayout()
        save_template_btn = QPushButton("Save Template")
        load_template_btn = QPushButton("Load Template")
        save_template_btn.clicked.connect(self.save_template)
        load_template_btn.clicked.connect(self.load_template)
        template_layout.addWidget(save_template_btn)
        template_layout.addWidget(load_template_btn)
        layout.addLayout(template_layout)
        
        # Dialog buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        # Load existing mappings
        self.load_mappings()
    
    def load_mappings(self):
        for folder, extensions in self.mappings.items():
            for ext in extensions:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(ext))
                self.table.setItem(row, 1, QTableWidgetItem(folder))
    
    def add_mapping(self):
        ext = self.ext_input.text().strip()
        folder = self.folder_input.text().strip()
        
        if ext and folder:
            if not ext.startswith('.'):
                ext = '.' + ext
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(ext))
            self.table.setItem(row, 1, QTableWidgetItem(folder))
            
            self.ext_input.clear()
            self.folder_input.clear()
    
    def get_mappings(self):
        mappings = {}
        for row in range(self.table.rowCount()):
            ext = self.table.item(row, 0).text()
            folder = self.table.item(row, 1).text()
            mappings.setdefault(folder, []).append(ext)
        return mappings
    
    def save_template(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Template", "", "JSON Files (*.json)")
        if filepath:
            if settings.export_template(filepath):
                QMessageBox.information(self, "Success", "Template saved successfully")
            else:
                QMessageBox.warning(self, "Error", "Failed to save template")
    
    def load_template(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Template", "", "JSON Files (*.json)")
        if filepath:
            if settings.import_template(filepath):
                self.mappings = settings.get_extension_mappings()
                self.table.setRowCount(0)
                self.load_mappings()
                QMessageBox.information(self, "Success", "Template loaded successfully")
            else:
                QMessageBox.warning(self, "Error", "Failed to load template")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chun's Random Utilities")
        self.setMinimumSize(800, 600)
        
        # Set application icon
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Initialize logs first
        self._setup_logs()
        
        # Set up the central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Add tabs
        tabs.addTab(self.create_downloads_tab(), "Downloads Organizer")
        tabs.addTab(self.create_clipboard_tab(), "Clipboard History")
        tabs.addTab(self.create_duplicates_tab(), "Duplicate Finder")
        tabs.addTab(self.create_speed_tab(), "Internet Speed")
        tabs.addTab(self.create_log_tab(), "Activity Log")
        
        # Set up system tray
        self.setup_tray()
        
        # Start clipboard monitoring
        self.clipboard_thread = ClipboardThread()
        self.clipboard_thread.clip_added.connect(self.on_new_clip)
        self.clipboard_thread.start()
        
        # Apply styles
        self.setStyleSheet(StyleSheet.get_style())
        
        # Initialize extension mappings
        self.extension_mappings = settings.get_extension_mappings()
        
        # Set up refresh timer for clipboard
        self.clipboard_timer = QTimer()
        self.clipboard_timer.timeout.connect(self.load_clips)
        self.clipboard_timer.start(1000)  # Refresh every second
        
        # Connect logger signals
        logger.signals.log_added.connect(self.update_log)
        
        self.threads = []  # Keep track of running threads

    def closeEvent(self, event):
        """Handle application closing with proper thread cleanup"""
        # Show loading cursor to indicate cleanup in progress
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            # Stop special threads first
            if hasattr(self, 'duplicate_thread') and self.duplicate_thread.isRunning():
                self.duplicate_thread.stop()
                
            if hasattr(self, 'speed_thread') and self.speed_thread.isRunning():
                self.speed_thread.stop()
                
            if hasattr(self, 'clipboard_thread'):
                self.clipboard_thread.stop()
            
            # Clear timers
            if hasattr(self, 'clipboard_timer'):
                self.clipboard_timer.stop()
            
            # Give threads a chance to stop gracefully
            QApplication.processEvents()
            
            # Wait for threads with timeout
            threads_to_wait = []
            # Add special threads if they're still running
            for thread_name in ['duplicate_thread', 'speed_thread', 'clipboard_thread']:
                if hasattr(self, thread_name):
                    thread = getattr(self, thread_name)
                    if thread.isRunning():
                        threads_to_wait.append(thread)
            
            # Add any other tracked threads
            threads_to_wait.extend([t for t in self.threads if t.isRunning()])
            
            # Wait for each thread with timeout
            for thread in threads_to_wait:
                if not thread.wait(2000):  # 2 second timeout
                    logger.warning(f"Force terminating thread: {thread}")
                    thread.terminate()
                    thread.wait()  # Ensure terminated thread is finished
            
            # Clear thread tracking list
            self.threads.clear()
            
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
            
        finally:
            # Always restore cursor and accept close event
            QApplication.restoreOverrideCursor()
            event.accept()
    
    def create_downloads_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Folder selection
        folder_layout = QHBoxLayout()
        self.folder_path = QLineEdit()
        self.folder_path.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.folder_path)
        folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)
        
        # Configure mappings button
        config_btn = QPushButton("Configure Extension Mappings")
        config_btn.clicked.connect(self.configure_mappings)
        layout.addWidget(config_btn)
        
        # Status label
        self.downloads_status = QLabel("Ready to organize files")
        layout.addWidget(self.downloads_status)
        
        # Organize button
        organize_btn = QPushButton("Organize Files")
        organize_btn.clicked.connect(self.organize_files)
        layout.addWidget(organize_btn)
        
        return widget
    

    def create_clipboard_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Clips list
        self.clips_list = QTableWidget()
        self.clips_list.setColumnCount(4)  # Added column for rowid
        self.clips_list.setHorizontalHeaderLabels(["Row ID", "Time", "Content", "Favorite"])
        self.clips_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.clips_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy Selected")
        copy_btn.clicked.connect(self.copy_selected_clip)
        favorite_btn = QPushButton("Toggle Favorite")
        favorite_btn.clicked.connect(self.toggle_favorite)
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(self.clear_clips)
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(favorite_btn)
        btn_layout.addWidget(clear_btn)
        layout.addLayout(btn_layout)
        
        # Load existing clips
        self.load_clips()
        
        return widget

    def create_duplicates_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Directory selection group
        select_group = QWidget()
        select_layout = QHBoxLayout(select_group)
        self.duplicate_dir_path = QLineEdit()
        self.duplicate_dir_path.setReadOnly(True)
        browse_dup_btn = QPushButton("Browse")
        browse_dup_btn.clicked.connect(self.browse_duplicate_directory)
        select_layout.addWidget(self.duplicate_dir_path)
        select_layout.addWidget(browse_dup_btn)
        layout.addWidget(select_group)
        
        # Progress group
        progress_group = QWidget()
        progress_layout = QVBoxLayout(progress_group)
        
        # Find duplicates button
        find_dup_btn = QPushButton("Find Duplicates")
        find_dup_btn.clicked.connect(self.find_duplicates)
        progress_layout.addWidget(find_dup_btn)
        
        # Progress bar
        self.duplicate_progress = QProgressBar()
        self.duplicate_progress.setValue(0)
        self.duplicate_progress.setTextVisible(True)
        progress_layout.addWidget(self.duplicate_progress)
        
        layout.addWidget(progress_group)
        
        # Results group
        results_group = QWidget()
        results_layout = QVBoxLayout(results_group)

        # Status label
        self.duplicates_status = QLabel("Ready to scan for duplicates")
        results_layout.addWidget(self.duplicates_status)
        
        # Results table
        self.duplicates_table = QTableWidget()
        self.duplicates_table.setColumnCount(4)
        self.duplicates_table.setHorizontalHeaderLabels(["Select", "File Name", "Size (MB)", "Location"])
        self.duplicates_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.duplicates_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        results_layout.addWidget(self.duplicates_table)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Delete button
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected_duplicates)
        buttons_layout.addWidget(delete_btn)
        
        # Visualize button
        visualize_btn = QPushButton("Visualize")
        visualize_btn.clicked.connect(self.visualize_duplicates)
        buttons_layout.addWidget(visualize_btn)
        
        results_layout.addLayout(buttons_layout)
        
        layout.addWidget(results_group)
        return widget

    def create_speed_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Results group
        results_group = QWidget()
        results_layout = QVBoxLayout(results_group)
        
        # Speed test button
        speed_test_btn = QPushButton("Run Speed Test")
        speed_test_btn.clicked.connect(self.run_speed_test)
        results_layout.addWidget(speed_test_btn)
        
        # Progress bar
        self.speed_progress = QProgressBar()
        self.speed_progress.setValue(0)
        self.speed_progress.setTextVisible(True)
        results_layout.addWidget(self.speed_progress)
        
        # Speed results - make it a QTextEdit for better multi-line display
        self.speed_result_label = QTextEdit()
        self.speed_result_label.setReadOnly(True)
        self.speed_result_label.setMaximumHeight(100)
        results_layout.addWidget(self.speed_result_label)
        
        layout.addWidget(results_group)
        return widget

    def create_log_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Buttons to clear and save logs
        btn_layout = QHBoxLayout()
        clear_log_btn = QPushButton("Clear Logs")
        clear_log_btn.clicked.connect(self.clear_logs)
        save_log_btn = QPushButton("Save Logs")
        save_log_btn.clicked.connect(self.save_logs)
        btn_layout.addWidget(clear_log_btn)
        btn_layout.addWidget(save_log_btn)
        layout.addLayout(btn_layout)
        
        return widget

    def setup_tray(self):
        # Modified to use the same icon as the main window
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else self.style().standardIcon(QStyle.SP_ComputerIcon)
        system_tray = QSystemTrayIcon(icon, self)
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        quit_action = tray_menu.addAction("Quit")
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(QApplication.instance().quit)
        system_tray.setContextMenu(tray_menu)
        system_tray.show()

    def update_log(self, log_entry):
        self.log_text.append(log_entry)

    def load_clips(self):
        """Refresh clipboard history display"""
        try:
            conn = sqlite3.connect('clipboard_history.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Get recent clips with proper ordering
            c.execute("""
                SELECT rowid, timestamp, content, favorite 
                FROM history 
                ORDER BY timestamp DESC 
                LIMIT 50
            """)
            clips = c.fetchall()
            
            self.clips_list.setRowCount(len(clips))
            for row, clip in enumerate(clips):
                # Row ID
                id_item = QTableWidgetItem(str(clip['rowid']))
                self.clips_list.setItem(row, 0, id_item)
                
                # Timestamp
                try:
                    timestamp = datetime.datetime.fromisoformat(clip['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    timestamp = clip['timestamp']
                time_item = QTableWidgetItem(timestamp)
                self.clips_list.setItem(row, 1, time_item)
                
                # Content
                content = clip['content']
                if len(content) > 100:
                    display_content = content[:97] + "..."
                else:
                    display_content = content
                content_item = QTableWidgetItem(display_content)
                content_item.setToolTip(content)  # Show full content on hover
                self.clips_list.setItem(row, 2, content_item)
                
                # Favorite
                fav_item = QTableWidgetItem("Yes" if clip['favorite'] else "No")
                self.clips_list.setItem(row, 3, fav_item)
            
            # Adjust column widths
            self.clips_list.resizeColumnsToContents()
            self.clips_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            
        except sqlite3.Error as e:
            logger.error(f"Database error in load_clips: {e}")
        except Exception as e:
            logger.error(f"Error loading clipboard history: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    def copy_selected_clip(self):
        selected_items = self.clips_list.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            content = self.clips_list.item(row, 2).text()
            pyperclip.copy(content)
            logger.info("Copied selected clipboard content to clipboard")

    def toggle_favorite(self):
        selected_items = self.clips_list.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            snippet_id = int(self.clips_list.item(row, 0).text())
            current = self.clips_list.item(row, 3).text()
            new_favorite = not (current == "Yes")
            success = utils.save_favorite_snippet(snippet_id)
            if success:
                self.clips_list.setItem(row, 3, QTableWidgetItem("Yes" if new_favorite else "No"))
                logger.info(f"Toggled favorite status for snippet {snippet_id}")

    def clear_clips(self):
        try:
            conn = sqlite3.connect('clipboard_history.db')
            c = conn.cursor()
            c.execute("DELETE FROM history")
            conn.commit()
            conn.close()
            self.clips_list.setRowCount(0)
            logger.info("Cleared clipboard history")
        except Exception as e:
            logger.error(f"Failed to clear clipboard history: {e}")

    def browse_folder(self):
        """Browse for downloads directory with proper error handling"""
        try:
            # Get last used directory or default to home directory
            last_dir = settings.get_last_folder('downloads') or str(Path.home())
            folder = QFileDialog.getExistingDirectory(
                self,
                "Select Folder",
                last_dir,
                QFileDialog.ShowDirsOnly | QFileDialog.DontUseNativeDialog
            )
            if folder:
                self.folder_path.setText(folder)
                settings.set_last_folder('downloads', folder)
        except Exception as e:
            logger.error(f"Error in browse dialog: {e}")
            QMessageBox.warning(self, "Error", "Failed to open directory browser")

    def configure_mappings(self):
        dialog = ExtensionMappingDialog(self, mappings=self.extension_mappings)
        if dialog.exec_() == QDialog.Accepted:
            mappings = dialog.get_mappings()
            settings.set_extension_mappings(mappings)
            self.extension_mappings = mappings
            logger.info("Extension mappings updated")

    def organize_files(self):
        folder = self.folder_path.text()
        if folder:
            try:
                # Run organize_downloads with the already selected path instead of asking again
                def organize():
                    utils.organize_downloads(folder_path=folder)  # Pass folder path directly
                    self.downloads_status.setText("Organization complete")
                
                threading.Thread(target=organize, daemon=True).start()
                self.downloads_status.setText("Organizing...")
                logger.info(f"Started organizing files in folder: {folder}")
            except Exception as e:
                logger.error(f"Error in organize_files: {e}")
                self.downloads_status.setText("Organization failed")
        else:
            logger.warning("No folder selected to organize")

    def browse_duplicate_directory(self):
        """Browse for duplicate files directory with proper error handling"""
        try:
            # Get last used directory or default to home directory
            last_dir = settings.get_last_folder('duplicates') or str(Path.home())
            directory = QFileDialog.getExistingDirectory(
                self,
                "Select Directory for Duplicate Scan",
                last_dir,
                QFileDialog.ShowDirsOnly | QFileDialog.DontUseNativeDialog
            )
            if directory:
                self.duplicate_dir_path.setText(directory)
                settings.set_last_folder('duplicates', directory)
        except Exception as e:
            logger.error(f"Error in browse dialog: {e}")
            QMessageBox.warning(self, "Error", "Failed to open directory browser")

    def find_duplicates(self):
        """Start duplicate file scan with proper thread management"""
        directory = self.duplicate_dir_path.text()
        if not directory:
            logger.warning("No directory selected for duplicate scan")
            return
        
        try:
            # Clean up any existing thread
            if hasattr(self, 'duplicate_thread') and self.duplicate_thread.isRunning():
                self.duplicate_thread.stop()
                self.duplicate_thread.wait(1000)  # Wait up to 1 second
                if self.duplicate_thread.isRunning():
                    self.duplicate_thread.terminate()
                try:
                    self.threads.remove(self.duplicate_thread)
                except ValueError:
                    pass
            
            # Reset UI state
            self.duplicates_table.setRowCount(0)
            self.duplicate_progress.setValue(0)
            self.find_duplicates_btn = self.sender()
            if self.find_duplicates_btn:
                self.find_duplicates_btn.setEnabled(False)
            
            # Create and configure new thread
            self.duplicate_thread = DuplicateFinderThread(directory)
            self.duplicate_thread.progress_updated.connect(self.update_duplicate_progress)
            self.duplicate_thread.duplicates_found.connect(self.display_duplicates)
            self.duplicate_thread.error_occurred.connect(self.handle_duplicate_error)
            
            # Add to thread tracking and start
            self.threads.append(self.duplicate_thread)
            self.duplicate_thread.start()
            
            logger.info(f"Started duplicate scan in directory: {directory}")
            
        except Exception as e:
            logger.error(f"Failed to start duplicate scan: {e}")
            if hasattr(self, 'find_duplicates_btn') and self.find_duplicates_btn:
                self.find_duplicates_btn.setEnabled(True)
            QMessageBox.warning(self, "Error", f"Failed to start duplicate scan: {e}")

    def update_duplicate_progress(self, value):
        self.duplicate_progress.setValue(value)

    def handle_duplicate_error(self, error_msg):
        """Handle errors from the duplicate finder thread"""
        QMessageBox.warning(self, "Error", f"Error during duplicate scan: {error_msg}")
        if hasattr(self, 'find_duplicates_btn') and self.find_duplicates_btn:
            self.find_duplicates_btn.setEnabled(True)

    def handle_duplicate_log(self, message):
        # Don't log progress messages to avoid recursion
        pass

    def display_duplicates(self, duplicates):
        """Handle displaying duplicate files with proper cleanup and error handling"""
        try:
            # Update UI elements in a safe manner
            def update_ui():
                try:
                    # Re-enable the button before any potential UI freezes
                    if hasattr(self, 'find_duplicates_btn'):
                        self.find_duplicates_btn.setEnabled(True)
                    
                    # Update progress bar first
                    self.duplicate_progress.setValue(100)
                    
                    # Clear the table before adding new items
                    self.duplicates_table.setRowCount(0)
                    
                    # Add duplicate groups with group headers
                    current_group = 0
                    total_wasted_space = 0
                    
                    for group in duplicates:
                        # Add a group header row with "Select All" checkbox
                        header_row = self.duplicates_table.rowCount()
                        self.duplicates_table.insertRow(header_row)
                        
                        # Create group header checkbox
                        header_checkbox = QCheckBox()
                        header_widget = QWidget()
                        header_layout = QHBoxLayout(header_widget)
                        header_layout.addWidget(header_checkbox)
                        header_layout.setAlignment(Qt.AlignCenter)
                        header_layout.setContentsMargins(0, 0, 0, 0)
                        self.duplicates_table.setCellWidget(header_row, 0, header_widget)
                        
                        # Group header text (spans 3 columns)
                        size_mb = group['size'] / (1024 * 1024)  # Convert to MB
                        header_text = f"Duplicate Group {current_group + 1} - {len(group['paths'])} files - {size_mb:.2f} MB each"
                        header_item = QTableWidgetItem(header_text)
                        header_item.setBackground(QColor(COLORS['bg_secondary']))
                        header_item.setFont(QFont("", -1, QFont.Bold))
                        self.duplicates_table.setSpan(header_row, 1, 1, 3)
                        self.duplicates_table.setItem(header_row, 1, header_item)
                        
                        # Calculate wasted space (size * (number of copies - 1))
                        wasted_space = group['size'] * (len(group['paths']) - 1)
                        total_wasted_space += wasted_space
                        
                        # Connect header checkbox to all items in group
                        checkbox_group = []
                        
                        # Add files in the group
                        for file_path in group['paths']:
                            filename = os.path.basename(file_path)
                            directory = os.path.dirname(file_path)
                            row = self.duplicates_table.rowCount()
                            self.duplicates_table.insertRow(row)
                            
                            # Checkbox
                            checkbox = QCheckBox()
                            checkbox_widget = QWidget()
                            checkbox_layout = QHBoxLayout(checkbox_widget)
                            checkbox_layout.addWidget(checkbox)
                            checkbox_layout.setAlignment(Qt.AlignCenter)
                            checkbox_layout.setContentsMargins(0, 0, 0, 0)
                            self.duplicates_table.setCellWidget(row, 0, checkbox_widget)
                            checkbox_group.append(checkbox)
                            
                            # File Name
                            self.duplicates_table.setItem(row, 1, QTableWidgetItem(filename))
                            # Size
                            self.duplicates_table.setItem(row, 2, QTableWidgetItem(f"{size_mb:.2f}"))
                            # Location
                            self.duplicates_table.setItem(row, 3, QTableWidgetItem(directory))
                        
                        # Connect header checkbox to group items
                        def make_group_toggle(header_cb, item_cbs):
                            def toggle_group(state):
                                for cb in item_cbs:
                                    cb.setChecked(state)
                            return toggle_group
                        
                        header_checkbox.stateChanged.connect(
                            make_group_toggle(header_checkbox, checkbox_group))
                        
                        current_group += 1
                        
                        # Add separator row
                        separator_row = self.duplicates_table.rowCount()
                        self.duplicates_table.insertRow(separator_row)
                        for col in range(4):
                            item = QTableWidgetItem()
                            item.setBackground(QColor(COLORS['accent']))
                            self.duplicates_table.setItem(separator_row, col, item)
                    
                    # Update the status label with total wasted space
                    wasted_mb = total_wasted_space / (1024 * 1024)
                    status_text = f"Found {len(duplicates)} duplicate groups. Total space that could be freed: {wasted_mb:.2f} MB"
                    self.duplicates_status.setText(status_text)
        
                except Exception as e:
                    logger.error(f"Error updating duplicate results UI: {e}")
            
            # Disconnect log handler before UI updates
            try:
                logger.signals.log_added.disconnect(self.handle_duplicate_log)
            except (TypeError, RuntimeError):
                pass  # Ignore if already disconnected
            
            # Perform UI updates
            update_ui()
            
            # Remove thread from tracking after UI is updated
            if hasattr(self, 'duplicate_thread'):
                try:
                    self.threads.remove(self.duplicate_thread)
                    delattr(self, 'duplicate_thread')
                except (ValueError, AttributeError):
                    pass
            
            logger.info(f"Duplicate scan completed - Found {len(duplicates)} duplicate groups")
            
        except Exception as e:
            logger.error(f"Critical error in display_duplicates: {e}")
            QMessageBox.warning(self, "Error", "Failed to display duplicate files. Check logs for details.")

    def delete_selected_duplicates(self):
        """Delete selected duplicate files with confirmation"""
        try:
            files_to_delete = []
            for row in range(self.duplicates_table.rowCount()):
                checkbox_widget = self.duplicates_table.cellWidget(row, 0)
                if checkbox_widget:
                    checkbox = checkbox_widget.findChild(QCheckBox)
                    if checkbox and checkbox.isChecked():
                        filename = self.duplicates_table.item(row, 1).text()
                        size = self.duplicates_table.item(row, 2).text()
                        location = self.duplicates_table.item(row, 3).text()
                        file_path = os.path.join(location, filename)
                        files_to_delete.append(file_path)
            
            if not files_to_delete:
                QMessageBox.information(self, "No Selection", "No duplicate files selected for deletion.")
                return
            
            reply = QMessageBox.question(
                self, 'Confirm Deletion',
                f"Are you sure you want to delete the selected {len(files_to_delete)} file(s)?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                deleted_files = []
                failed_deletions = []
                for file_path in files_to_delete:
                    try:
                        os.remove(file_path)
                        deleted_files.append(file_path)
                        logger.info(f"Deleted duplicate file: {file_path}")
                    except Exception as e:
                        failed_deletions.append((file_path, str(e)))
                        logger.error(f"Failed to delete {file_path}: {e}")
                
                # Refresh duplicates table
                self.find_duplicates()
                
                message = f"Deleted {len(deleted_files)} file(s)."
                if failed_deletions:
                    message += f"\nFailed to delete {len(failed_deletions)} file(s). Check logs for details."
                QMessageBox.information(self, "Deletion Complete", message)
                
        except Exception as e:
            logger.error(f"Error during file deletion: {e}")
            QMessageBox.warning(self, "Error", f"An error occurred while deleting files: {e}")

    def run_speed_test(self):
        """Start speed test with proper signal management"""
        self.speed_result_label.setText("Testing...")
        self.speed_progress.setValue(0)
        
        self.speed_test_btn = self.sender()
        if self.speed_test_btn:
            self.speed_test_btn.setEnabled(False)
        
        self.speed_thread = SpeedTestThread()
        self.speed_thread.speed_updated.connect(self.update_speed_result)
        self.speed_thread.error_occurred.connect(self.handle_speed_test_error)
        self.speed_thread.progress_updated.connect(self.update_speed_progress)
        self.speed_thread.finished.connect(self.speed_test_completed)
        
        self.speed_thread.start()
        self.threads.append(self.speed_thread)
        logger.signals.log_added.connect(self.handle_speed_test_log)
        logger.info("Started internet speed test")

    def handle_speed_test_error(self, error_message):
        """Handle speed test failures"""
        self.speed_result_label.setText(error_message)
        logger.error(error_message)
        if hasattr(self, 'speed_test_btn') and self.speed_test_btn:
            self.speed_test_btn.setEnabled(True)
        logger.signals.log_added.disconnect(self.handle_speed_test_log)

    def speed_test_completed(self):
        """Re-enable the speed test button and cleanup signals"""
        if hasattr(self, 'speed_test_btn') and self.speed_test_btn:
            self.speed_test_btn.setEnabled(True)
        
        # Safely disconnect the log signal if it was connected
        try:
            logger.signals.log_added.disconnect(self.handle_speed_test_log)
        except (TypeError, RuntimeError):
            pass  # Ignore disconnection errors

    def update_speed_result(self, result):
        self.speed_result_label.setText(
            f"Download: {result['download']:.2f} Mbps\n"
            f"Upload: {result['upload']:.2f} Mbps\n"
            f"Ping: {result['ping']} ms\n"
            f"Server: {result['server_name']} ({result['server_country']})"
        )
        logger.info(f"Speed test complete - Download: {result['download']:.2f} Mbps, "
                    f"Upload: {result['upload']:.2f} Mbps, Ping: {result['ping']} ms, "
                    f"Server: {result['server_name']} ({result['server_country']})")

    def update_speed_progress(self, value):
        """Update the speed test progress bar"""
        self.speed_progress.setValue(value)

    def handle_speed_test_log(self, message):
        # Don't log progress messages to avoid recursion
        pass

    def visualize_duplicates(self):
        """Create visualization of duplicate files using cluster plot"""
        try:
            # Extract data from table
            data_points = []
            labels = []
            
            for row in range(self.duplicates_table.rowCount()):
                # Skip separator rows and empty cells
                if (not self.duplicates_table.item(row, 1) or 
                    not self.duplicates_table.item(row, 2) or 
                    self.duplicates_table.columnSpan(row, 1) > 1):
                    continue
                
                try:
                    filename = self.duplicates_table.item(row, 1).text()
                    size_str = self.duplicates_table.item(row, 2).text()
                    if size_str and filename:  # Only process non-empty cells
                        size = float(size_str)
                        location = self.duplicates_table.item(row, 3).text()
                        data_points.append([size])
                        labels.append(filename)
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Skipping invalid row {row}: {e}")
                    continue
            
            if not data_points:
                QMessageBox.information(self, "No Data", "No valid duplicate files to visualize")
                return
            
            # Create cluster plot
            plt.figure(figsize=(12, 6))
            
            # Convert to numpy array for clustering
            import numpy as np
            from sklearn.cluster import KMeans
            
            X = np.array(data_points)
            
            # Determine optimal number of clusters (max 5 clusters)
            n_clusters = min(5, len(X))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            cluster_labels = kmeans.fit_predict(X)
            
            # Create scatter plot with clusters
            scatter = plt.scatter(X[:, 0], np.zeros_like(X[:, 0]), 
                                c=cluster_labels, cmap='viridis', 
                                s=100, alpha=0.6)
            
            # Add file names as annotations
            for i, label in enumerate(labels):
                plt.annotate(label, (X[i, 0], 0),
                            xytext=(0, 10), textcoords='offset points',
                            ha='center', va='bottom',
                            rotation=45)
            
            plt.title('Duplicate Files Clustered by Size')
            plt.xlabel('File Size (MB)')
            plt.yticks([])  # Hide y-axis
            
            # Add legend for clusters
            legend1 = plt.legend(*scatter.legend_elements(),
                                title="Clusters")
            plt.gca().add_artist(legend1)
            
            plt.tight_layout()
            plt.show()
            
        except Exception as e:
            logger.error(f"Error visualizing duplicates: {e}")
            QMessageBox.warning(self, "Error", 
                              "Failed to create visualization. Check logs for details.")

    def save_logs(self):
        """Save logs with proper error handling"""
        try:
            filepath, _ = QFileDialog.getSaveFileName(
                self, 
                "Save Logs",
                str(Path.home() / "logs.log"),
                "Log Files (*.log)",
                options=QFileDialog.DontUseNativeDialog
            )
            if filepath:
                if logger.save_logs(filepath):
                    QMessageBox.information(self, "Success", "Logs saved successfully")
                else:
                    QMessageBox.warning(self, "Error", "Failed to save logs")
        except Exception as e:
            logger.error(f"Error in save dialog: {e}")
            QMessageBox.warning(self, "Error", "Failed to open save dialog")

    def clear_logs(self):
        logger.clear_logs()
        self.log_text.clear()

    def on_new_clip(self, clip):
        """Handle new clipboard content"""
        try:
            if clip and len(clip.strip()) > 0:
                conn = sqlite3.connect('clipboard_history.db')
                c = conn.cursor()
                
                # Insert new clip with current timestamp
                c.execute("""
                    INSERT INTO history (timestamp, content, favorite)
                    VALUES (?, ?, 0)
                """, (datetime.datetime.now().isoformat(), clip))
                
                conn.commit()
                self.load_clips()  # Refresh display
                
        except sqlite3.Error as e:
            logger.error(f"Database error in on_new_clip: {e}")
        except Exception as e:
            logger.error(f"Error saving clipboard content: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    def _setup_logs(self):
        """Initialize log text areas"""
        # Progress logs style
        log_style = """
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #578E7E;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                color: #3D3D3D;
            }
        """
        
        # Main activity log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(log_style)

def main():
    app = QApplication(sys.argv)
    
    # Set application-wide icon
    icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
