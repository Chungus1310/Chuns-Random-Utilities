# Chun's Random Utilities 🛠️

A friendly multi-tool to keep your digital life organized! Automatically sort downloads, track clipboard history, find duplicates, test internet speed, and more – all in one place.

[![Python 3.6+](https://img.shields.io/badge/python-3.6%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

![image](https://github.com/user-attachments/assets/7e5e7bb8-9020-4011-b9ff-ac7b579cb4b3)


## Features 🌟

### 🗂️ Smart Downloads Organizer
- Auto-sort files into folders by type (Images/Documents/Archives)
- Customizable file-type rules
- Conflict-free file naming

### 📋 Clipboard History Tracker
- Stores last 50 clipboard entries
- Favorite important snippets
- System tray background monitoring

### 🔍 Duplicate File Finder
- Visualize duplicates with cluster charts
- Bulk delete functionality
- Wasted space calculator

### 🌐 Internet Speed Blamer
- Test download/upload speeds
- Historical CSV logging
- Server location tracking

### 💖 User-Friendly UI
- Clean tabbed interface
- Real-time progress bars
- Dark/Light mode support

## Installation 📦

1. **Clone the repository**
   ```bash
   git clone https://github.com/Chungus1310/Chuns-Random-Utilities.git
   cd Chuns-Random-Utilities
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the app**
   ```bash
   python launcher.py
   ```

*Requires Python 3.6+*

## Usage 🚀

### Organizing Downloads
1. Click "Browse" to select a folder
2. Use default categories or configure custom rules
3. Hit "Organize Files" – let the magic happen!

### Clipboard History
- Runs automatically in system tray
- Double-click entries to copy
- Star ⭐ frequently used items

### Speed Testing
- Get instant speed metrics
- View historical trends in `internet_speed_log.csv`

## Configuration ⚙️

Customize via `config.json`:
```json
{
  "extension_mappings": {
    "Music": [".mp3", ".wav", ".flac"],
    "Videos": [".mp4", ".mov", ".avi"]
  }
}
```
*Use the GUI's "Configure Extension Mappings" for easy editing!*

## Contributing 🤝

We welcome contributions! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

Found a bug? [Open an issue](https://github.com/Chungus1310/Chuns-Random-Utilities/issues)

## License 📄

MIT Licensed - Feel free to use and modify!

## Acknowledgments 💐

Special thanks to:
- The Python community for awesome libraries
- PyQt5 developers for the GUI framework
- Coffee ☕ – the real MVP

---

**Happy organizing!** 😊  
*Let's make digital clutter a thing of the past!*
