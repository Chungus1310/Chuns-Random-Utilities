import os
import shutil
from pathlib import Path
import argparse
import hashlib
import pyperclip
import sqlite3
import time
import speedtest
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from multiprocessing import Pool, cpu_count
from collections import defaultdict
import threading
from queue import Queue
import tkinter as tk
from tkinter import filedialog
from settings import Settings
from logger import Logger
import re

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

def choose_folder():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    folder_path = filedialog.askdirectory(title="Select Folder")
    return folder_path

def organize_downloads(folder_path=None, custom_rules=None):
    try:
        # Use provided folder_path instead of asking
        if not folder_path:
            folder_path = choose_folder()
            if not folder_path:
                logger.warning("No folder selected")
                return

        folder_path = Path(folder_path)
        if not folder_path.exists():
            logger.error(f"Selected folder does not exist at {folder_path}")
            return

        if not os.access(folder_path, os.R_OK | os.W_OK):
            logger.error(f"Insufficient permissions for folder: {folder_path}")
            return

        # If no custom rules provided, use saved mappings
        if not custom_rules:
            folder_mappings = settings.get_extension_mappings()
        else:
            # Process provided custom rules
            folder_mappings = {}
            for rule in custom_rules:
                try:
                    extension, folder = rule.split(':')
                    folder_mappings.setdefault(folder.strip(), []).append(extension.strip().lower())
                except ValueError:
                    logger.error(f"Invalid custom rule format: {rule}. Use .ext:FolderName")
                    continue

        items_processed = 0
        for item in folder_path.iterdir():
            try:
                if item.is_file():
                    moved = False
                    for folder, extensions in folder_mappings.items():
                        if item.suffix.lower() in extensions:
                            target_folder = folder_path / folder
                            target_folder.mkdir(exist_ok=True)
                            
                            # Handle existing file with same name
                            target_path = target_folder / item.name
                            if target_path.exists():
                                base = target_folder / item.stem
                                counter = 1
                                while (target_path := base.with_name(
                                    f"{item.stem}_{counter}{item.suffix}")).exists():
                                    counter += 1
                            
                            shutil.move(str(item), str(target_path))
                            moved = True
                            items_processed += 1
                            logger.info(f"Moved {item.name} to {folder}")
                            break
                            
                    if not moved:
                        # Move to Others
                        target_folder = folder_path / "Others"
                        target_folder.mkdir(exist_ok=True)
                        target_path = target_folder / item.name
                        
                        if target_path.exists():
                            base = target_folder / item.stem
                            counter = 1
                            while (target_path := base.with_name(
                                f"{item.stem}_{counter}{item.suffix}")).exists():
                                counter += 1
                        
                        shutil.move(str(item), str(target_path))
                        items_processed += 1
                        logger.info(f"Moved {item.name} to Others")
            except PermissionError:
                logger.error(f"Permission denied for file: {item}")
                continue
            except OSError as e:
                logger.error(f"Error processing file {item}: {e}")
                continue
                
        logger.info(f"Organization complete. Processed {items_processed} files.")
    except Exception as e:
        logger.error(f"Error during organization: {e}")

class ClipboardManager:
    DB_FILE = 'clipboard_history.db'
    POOL_SIZE = 5
    
    def __init__(self):
        self.queue = Queue()
        self.db_lock = threading.Lock()
        self.running = True
        self.connection_pool = Queue(maxsize=self.POOL_SIZE)
        self.setup_database()
        self._init_connection_pool()
    
    def _init_connection_pool(self):
        """Initialize the connection pool with database connections"""
        for _ in range(self.POOL_SIZE):
            conn = sqlite3.connect(self.DB_FILE, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.connection_pool.put(conn)
    
    def _get_connection(self):
        """Get a connection from the pool"""
        return self.connection_pool.get()
    
    def _return_connection(self, conn):
        """Return a connection to the pool"""
        if conn:
            self.connection_pool.put(conn)
    
    def setup_database(self):
        """Initialize the database schema"""
        conn = None
        try:
            conn = sqlite3.connect(self.DB_FILE)
            c = conn.cursor()
            # Drop table if it exists to ensure proper schema
            c.execute('DROP TABLE IF EXISTS history')
            c.execute('''CREATE TABLE history
                        (timestamp TEXT NOT NULL,
                         content TEXT NOT NULL,
                         favorite INTEGER DEFAULT 0,
                         hash TEXT UNIQUE)''')
            # Add indexes for better performance
            c.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON history(timestamp)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_favorite ON history(favorite)')
            conn.commit()
            logger.info("Clipboard history database initialized")
        except sqlite3.Error as e:
            logger.error(f"Database setup error: {e}")
        finally:
            if conn:
                conn.close()

    def monitor_clipboard(self):
        """Monitor clipboard for changes"""
        last_clip = ""
        while self.running:
            try:
                clip = pyperclip.paste()
                if clip and clip != last_clip and not clip.startswith("*****"):
                    clip_hash = hashlib.md5(clip.encode()).hexdigest()
                    self.queue.put((clip, clip_hash))
                    last_clip = clip
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error monitoring clipboard: {e}")
                time.sleep(1)

    def process_queue(self):
        """Process queued clipboard entries"""
        while self.running:
            try:
                if self.queue.empty():
                    time.sleep(0.1)
                    continue
                    
                clip, clip_hash = self.queue.get_nowait()
                conn = self._get_connection()
                
                try:
                    with conn:
                        c = conn.cursor()
                        # Check for duplicates using hash
                        c.execute("SELECT 1 FROM history WHERE hash = ?", (clip_hash,))
                        if not c.fetchone():
                            c.execute("""
                                INSERT INTO history (timestamp, content, hash)
                                VALUES (?, ?, ?)
                            """, (datetime.now().isoformat(), clip, clip_hash))
                            logger.info(f"New clipboard entry saved: {clip[:50]}...")
                finally:
                    self._return_connection(conn)
                    
            except Queue.Empty:
                continue
            except sqlite3.Error as e:
                logger.error(f"Database error while processing clipboard: {e}")
            except Exception as e:
                logger.error(f"Error processing clipboard data: {e}")

    def cleanup(self):
        """Cleanup resources"""
        self.running = False
        
        # Clear the queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except Queue.Empty:
                break
        
        # Close all database connections
        while not self.connection_pool.empty():
            try:
                conn = self.connection_pool.get_nowait()
                conn.close()
            except Queue.Empty:
                break

def clipboard_history_tracker():
    manager = ClipboardManager()
    logger.info("Starting clipboard history tracker")
    
    monitor_thread = threading.Thread(target=manager.monitor_clipboard, daemon=True)
    process_thread = threading.Thread(target=manager.process_queue, daemon=True)
    
    try:
        monitor_thread.start()
        process_thread.start()
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Stopping clipboard tracker...")
        manager.cleanup()
        
    finally:
        # Ensure cleanup is called even if interrupted
        manager.cleanup()

def show_recent_clips():
    """Get recent clipboard entries with proper error handling"""
    try:
        conn = sqlite3.connect('clipboard_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Ensure table exists
        c.execute('''CREATE TABLE IF NOT EXISTS history
                    (timestamp TEXT NOT NULL,
                     content TEXT NOT NULL,
                     favorite INTEGER DEFAULT 0)''')
        
        # Get clips ordered by timestamp
        c.execute("""
            SELECT rowid, timestamp, content, favorite
            FROM history 
            ORDER BY timestamp DESC
            LIMIT 50
        """)
        clips = [dict(row) for row in c.fetchall()]
        return clips
        
    except sqlite3.Error as e:
        logger.error(f"Error retrieving clipboard history: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def save_favorite_snippet(snippet_id):
    """Update favorite status with proper error handling"""
    try:
        conn = sqlite3.connect(ClipboardManager.DB_FILE)
        c = conn.cursor()
        
        with conn:  # Use transaction
            # Verify snippet exists first
            c.execute("SELECT 1 FROM history WHERE rowid = ?", (snippet_id,))
            if not c.fetchone():
                logger.error(f"Snippet with ID {snippet_id} not found")
                return False
                
            c.execute("""
                UPDATE history 
                SET favorite = CASE 
                    WHEN favorite = 0 THEN 1 
                    ELSE 0 
                END 
                WHERE rowid = ?
            """, (snippet_id,))
            
            if c.rowcount > 0:
                logger.info(f"Toggled favorite status for snippet {snippet_id}")
                return True
            return False
            
    except sqlite3.Error as e:
        logger.error(f"Database error while updating favorite status: {e}")
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()

class FileInfo:
    CHUNK_SIZE = 8192
    MAX_QUICK_READ_SIZE = 1024 * 1024  # 1MB limit for quick hash
    
    def __init__(self, path):
        self.path = Path(path)
        self._size = None
        self._quick_hash = None
        self._full_hash = None
    
    @property
    def size(self):
        """Get file size with caching"""
        if self._size is None:
            try:
                self._size = os.path.getsize(self.path)
            except (OSError, PermissionError) as e:
                logger.error(f"Error getting size for {self.path}: {e}")
                self._size = 0
        return self._size
    
    @property
    def quick_hash(self):
        """Get hash of first chunk with size limit"""
        if self._quick_hash is None:
            try:
                md5 = hashlib.md5()
                bytes_read = 0
                with open(self.path, 'rb') as f:
                    while bytes_read < self.MAX_QUICK_READ_SIZE:
                        chunk = f.read(min(self.CHUNK_SIZE, 
                                         self.MAX_QUICK_READ_SIZE - bytes_read))
                        if not chunk:
                            break
                        md5.update(chunk)
                        bytes_read += len(chunk)
                self._quick_hash = md5.hexdigest()
            except (OSError, PermissionError) as e:
                logger.error(f"Error quick hashing {self.path}: {e}")
                self._quick_hash = ''
        return self._quick_hash
    
    def full_hash(self):
        """Calculate full file hash using chunks"""
        if self._full_hash is None:
            try:
                md5 = hashlib.md5()
                with open(self.path, 'rb') as f:
                    while chunk := f.read(self.CHUNK_SIZE):
                        md5.update(chunk)
                self._full_hash = md5.hexdigest()
            except (OSError, PermissionError) as e:
                logger.error(f"Error full hashing {self.path}: {e}")
                self._full_hash = ''
        return self._full_hash

def scan_directory(directory, progress_callback=None):
    """Scan directory for files with progress tracking"""
    files_by_size = defaultdict(list)
    files_by_directory = defaultdict(list)
    
    # Count total files first
    total_files = sum(len(files) for _, _, files in os.walk(directory))
    if total_files == 0:
        logger.warning("No files found in directory")
        return files_by_size, files_by_directory
    
    processed_files = 0
    chunk_size = max(1, total_files // 100)  # Update progress every 1%
    
    for root, _, files in os.walk(directory):
        for name in files:
            try:
                filepath = os.path.join(root, name)
                file_info = FileInfo(filepath)
                if file_info.size > 0:
                    files_by_size[file_info.size].append(file_info)
                    files_by_directory[root].append(file_info)
                
                processed_files += 1
                if progress_callback and processed_files % chunk_size == 0:
                    progress = (processed_files / total_files) * 50
                    progress_callback(int(progress))
                    
            except Exception as e:
                logger.error(f"Error processing {filepath}: {e}")
                continue
    
    return files_by_size, files_by_directory

def get_normalized_name(filename: str) -> str:
    """
    Remove common copy patterns (e.g. 'file(1)', 'copy of file').
    Returns a normalized base name without these patterns.
    """
    # Match 'copy of ' prefix or '(digits)' suffix in parentheses
    # e.g., 'copy of file.txt', 'file (1).txt', 'file(2).txt'
    # We'll keep the extension intact.
    basename, ext = os.path.splitext(filename.lower())
    basename = re.sub(r'^(copy of\s+)', '', basename)        # remove 'copy of '
    basename = re.sub(r'\s*\(\d+\)\s*$', '', basename)       # remove '(1)', '(2)', etc.
    return basename.strip() + ext

def find_duplicates(files_by_size, files_by_directory, progress_callback=None):
    """Find duplicate files with updated logic: list similar named files, check hashes, group by folders"""
    duplicate_groups = []
    
    # Create a list of similar named files in the selected folder
    for directory, files in files_by_directory.items():
        name_dict = defaultdict(list)
        for file in files:
            normalized_name = get_normalized_name(file.path.name)
            name_dict[normalized_name].append(file)
        
        # Check hashes of listed files to identify duplicates
        for normalized_name, similar_files in name_dict.items():
            if len(similar_files) > 1:
                hash_dict = defaultdict(list)
                for file in similar_files:
                    file_hash = file.full_hash()
                    hash_dict[file_hash].append(file)
                
                for hash_value, duplicates in hash_dict.items():
                    if len(duplicates) > 1:
                        duplicate_groups.append({
                            'paths': [f.path for f in duplicates],
                            'size': duplicates[0].size,
                            'directory': directory
                        })
    
    return duplicate_groups

def visualize_duplicates(duplicates):
    """Visualize duplicate files using a cluster plot"""
    if not duplicates:
        logger.warning("No duplicate files to visualize")
        return
    
    try:
        # Prepare data for clustering
        data = []
        labels = []
        for group in duplicates:
            if group['size'] > 0:  # Only include files with valid size
                size_mb = group['size'] / (1024 * 1024)  # Convert to MB
                for file_path in group['paths']:
                    data.append([size_mb])
                    labels.append(os.path.basename(file_path))
        
        if not data:
            logger.warning("No valid files to visualize")
            return
        
        import matplotlib.pyplot as plt
        from sklearn.cluster import KMeans
        import numpy as np
        
        # Convert data to numpy array
        X = np.array(data)
        
        # Determine optimal number of clusters (max 5)
        n_clusters = min(5, len(X))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        cluster_labels = kmeans.fit_predict(X)
        
        # Create scatter plot with clusters
        plt.figure(figsize=(10, 6))
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

def ensure_csv_exists():
    """Ensure the speed log CSV exists with headers"""
    csv_file = 'internet_speed_log.csv'
    if not os.path.exists(csv_file):
        with open(csv_file, 'w') as f:
            f.write("timestamp,download_mbps,upload_mbps,ping_ms,server_name,server_country\n")
    return csv_file

def format_speed(speed_bps):
    """Convert speed from bits/s to appropriate unit"""
    speed_mbps = speed_bps / 1_000_000
    if speed_mbps < 1:
        return f"{speed_mbps * 1000:.1f} Kbps"
    elif speed_mbps < 1000:
        return f"{speed_mbps:.1f} Mbps"
    else:
        return f"{speed_mbps / 1000:.2f} Gbps"

def internet_speed_blamer(log_callback=None):
    """Test internet speed with detailed logging and error handling"""
    def log_progress(message):
        logger.info(message)
        if log_callback:
            log_callback(message)
            
    log_progress("Starting internet speed test")
    csv_file = ensure_csv_exists()
    
    try:
        # Verify internet connectivity first
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
        except OSError:
            log_progress("No internet connection available")
            return None

        # Initialize speedtest with timeout
        st = speedtest.Speedtest(timeout=30)
        
        # Get best server
        log_progress("Finding best server...")
        server = st.get_best_server()
        server_name = server.get('host', 'Unknown')
        server_country = server.get('country', 'Unknown')
        log_progress(f"Selected server: {server_name} ({server_country})")
        
        # Test download
        log_progress("Testing download speed...")
        download_bps = st.download()
        download_speed = format_speed(download_bps)
        log_progress(f"Download speed: {download_speed}")
        
        # Test upload
        log_progress("Testing upload speed...")
        upload_bps = st.upload()
        upload_speed = format_speed(upload_bps)
        log_progress(f"Upload speed: {upload_speed}")
        
        # Get ping
        ping = st.results.ping
        log_progress(f"Ping: {ping:.0f}ms")
        
        # Convert speeds to Mbps for storage
        download_mbps = download_bps / 1_000_000
        upload_mbps = upload_bps / 1_000_000
        
        # Store result
        result = {
            'download': download_mbps,
            'upload': upload_mbps,
            'ping': ping,
            'server_name': server_name,
            'server_country': server_country,
            'timestamp': datetime.now().isoformat()
        }
        
        # Log to CSV with error handling
        try:
            with open(csv_file, 'a') as f:
                f.write(f"{result['timestamp']},"
                       f"{result['download']:.2f},"
                       f"{result['upload']:.2f},"
                       f"{result['ping']:.0f},"
                       f"{result['server_name']},"
                       f"{result['server_country']}\n")
        except IOError as e:
            logger.error(f"Failed to write to CSV file: {e}")
        
        log_progress("Speed test complete\n"
                   f"Download: {download_speed}\n"
                   f"Upload: {upload_speed}\n"
                   f"Ping: {ping:.0f}ms\n"
                   f"Server: {server_name} ({server_country})")
        
        return result
        
    except speedtest.ConfigRetrievalError:
        logger.error("Failed to retrieve speedtest configuration. Check your internet connection.")
        return None
    except speedtest.NoMatchedServers:
        logger.error("No suitable speedtest servers found.")
        return None
    except speedtest.SpeedtestBestServerFailure:
        logger.error("Failed to find the best speedtest server.")
        return None
    except speedtest.InvalidServerIDType:
        logger.error("Invalid server ID type.")
        return None
    except Exception as e:
        logger.error(f"Speed test failed: {str(e)}")
        return None

def duplicate_file_finder(directory, progress_callback=None):
    """Find duplicate files with progress tracking and folder-level consideration"""
    try:
        def safe_progress_callback(value):
            """Safely call the progress callback if provided"""
            if progress_callback:
                try:
                    progress_callback(value)
                except Exception as e:
                    logger.error(f"Progress callback error: {e}")
                    
        logger.info("Starting duplicate file scan")
        safe_progress_callback(0)  # Initial progress
        
        files_by_size, files_by_directory = scan_directory(directory, safe_progress_callback)
        safe_progress_callback(50)  # Halfway progress
        
        # Compare files and find duplicates within the same directory
        duplicates = find_duplicates(files_by_size, files_by_directory, safe_progress_callback)
        
        logger.info(f"Found {len(duplicates)} duplicate groups")
        return duplicates
        
    except Exception as e:
        logger.error(f"Error during duplicate scan: {e}")
        raise  # Re-raise to be caught by the thread

def main():
    parser = argparse.ArgumentParser(description="Multi Utility Tool")
    subparsers = parser.add_subparsers(dest='command')

    # Organize Downloads
    parser_organize = subparsers.add_parser('organize_downloads', 
                                          help='Automatically sorts files in selected folder')
    parser_organize.add_argument('--custom_rule', action='append', 
                               help='Custom rule in the format .ext:FolderName')

    # Clipboard History Tracker
    parser_clipboard = subparsers.add_parser('clipboard_history_tracker', 
                                           help='Start clipboard history tracker')

    # Show Recent Clips
    parser_show = subparsers.add_parser('show_clips', help='Show recent clipboard clips')

    # Save Favorite Snippet
    parser_save = subparsers.add_parser('save_favorite', 
                                       help='Save a favorite clipboard snippet')
    parser_save.add_argument('snippet_id', type=int, help='ID of the snippet to save')

    # Duplicate File Finder
    parser_duplicates = subparsers.add_parser('duplicate_file_finder', 
                                             help='Find duplicate files in a directory')
    parser_duplicates.add_argument('directory', help='Directory to scan for duplicates')
    parser_duplicates.add_argument('--visualize', action='store_true', 
                                 help='Visualize duplicates with a cluster plot')
    parser_duplicates.add_argument('--delete', action='store_true',
                                 help='Delete selected duplicate files')

    # Internet Speed Blamer
    parser_speed = subparsers.add_parser('internet_speed_blamer', 
                                        help='Log internet speed to CSV')

    args = parser.parse_args()

    if args.command == 'organize_downloads':
        organize_downloads(custom_rules=args.custom_rule)
    elif args.command == 'clipboard_history_tracker':
        clipboard_history_tracker()
    elif args.command == 'show_clips':
        for clip in show_recent_clips():
            print(f"{clip['rowid']}: {clip['timestamp']} - {clip['content']} - Favorite: {'Yes' if clip['favorite'] else 'No'}")
    elif args.command == 'save_favorite':
        save_favorite_snippet(args.snippet_id)
    elif args.command == 'duplicate_file_finder':
        duplicates = duplicate_file_finder(args.directory)
        if duplicates:
            print("\nDuplicate file groups found:")
            for group in duplicates:
                print("Group:")
                for file in group['paths']:
                    print(f"  {file}")
                print()
            if args.visualize:
                visualize_duplicates(duplicates)
            # Deletion handled via UI, not command line
        else:
            print("No duplicate files found.")
    elif args.command == 'internet_speed_blamer':
        internet_speed_blamer()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()

