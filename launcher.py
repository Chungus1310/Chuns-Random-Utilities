import os
import sqlite3
from logger import Logger
import ui

def init_database():
    """Initialize the database and tables if they don't exist"""
    try:
        conn = sqlite3.connect('clipboard_history.db')
        c = conn.cursor()
        
        # Create the history table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS history
                    (timestamp TEXT NOT NULL,
                     content TEXT NOT NULL,
                     favorite INTEGER DEFAULT 0,
                     hash TEXT UNIQUE)''')
        
        # Create necessary indexes
        c.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON history(timestamp)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_favorite ON history(favorite)')
        
        conn.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def init_files():
    """Initialize required files and directories"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Create internet speed log if it doesn't exist
    if not os.path.exists('internet_speed_log.csv'):
        with open('internet_speed_log.csv', 'w') as f:
            f.write("timestamp,download_mbps,upload_mbps,ping_ms,server_name,server_country\n")
    
    # Create config.json if it doesn't exist
    if not os.path.exists('config.json'):
        from settings import Settings
        settings = Settings()
        settings.save()

if __name__ == '__main__':
    # Initialize files and database before starting the application
    init_files()
    init_database()
    
    # Start the application
    ui.main()
