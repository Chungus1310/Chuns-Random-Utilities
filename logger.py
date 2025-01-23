import logging
from datetime import datetime
from pathlib import Path
import sys
from queue import Queue
from PyQt5.QtCore import QObject, pyqtSignal
import threading

class LogSignals(QObject):
    log_added = pyqtSignal(str)

class Logger:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not Logger._initialized:
            Logger._initialized = True
            self.log_file = 'utility.log'
            self.signals = LogSignals()
            # Queue for real-time log updates
            self.log_queue = Queue()
            self.lock = threading.Lock()  # Add thread lock
            self.setup_logger()
    
    def setup_logger(self):
        self.logger = logging.getLogger('UtilityLogger')
        self.logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Custom handler for GUI updates
        class QueueHandler(logging.Handler):
            def __init__(self, queue, signals):
                super().__init__()
                self.queue = queue
                self.signals = signals
            
            def emit(self, record):
                log_entry = self.format(record)
                self.queue.put(log_entry)
                self.signals.log_added.emit(log_entry)
        
        queue_handler = QueueHandler(self.log_queue, self.signals)
        queue_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        queue_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(queue_handler)
    
    def info(self, message):
        self.logger.info(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def get_logs(self):
        try:
            with open(self.log_file, 'r') as f:
                return f.readlines()
        except Exception:
            return []
    
    def write_log(self, message):
        """Thread-safe log writing"""
        with self.lock:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(message + '\n')
            except Exception as e:
                print(f"Failed to write to log file: {e}")
    
    def clear_logs(self):
        """Thread-safe log clearing"""
        with self.lock:
            try:
                Path(self.log_file).write_text('')
                self.info("Log file cleared")
            except Exception as e:
                print(f"Failed to clear logs: {e}")
    
    def save_logs(self, filepath):
        try:
            from shutil import copy2
            copy2(self.log_file, filepath)
            self.info(f"Logs saved to {filepath}")
            return True
        except Exception as e:
            self.error(f"Failed to save logs: {e}")
            return False
