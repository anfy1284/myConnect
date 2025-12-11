import ctypes
import sys
import os
import logging
import json

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def setup_logging(config):
    log_file = config.get('log_file', 'client.log')
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    # Add console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

def load_config(path='config.json'):
    if not os.path.isabs(path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, path)

    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)

def check_windivert():
    # Check if WinDivert dll/sys files exist in current directory or path
    cwd = os.getcwd()
    
    if not os.path.exists(os.path.join(cwd, 'WinDivert.dll')):
        logging.warning("WinDivert.dll not found in application directory.")
        return False

    # Check for at least one driver (32-bit or 64-bit)
    if not (os.path.exists(os.path.join(cwd, 'WinDivert.sys')) or os.path.exists(os.path.join(cwd, 'WinDivert64.sys'))):
        logging.warning("WinDivert driver (WinDivert.sys or WinDivert64.sys) not found.")
        return False
    
    return True

def cleanup_logs(config):
    import time
    log_file = config.get('log_file', 'client.log')
    retention_days = config.get('log_retention_days', 7)
    
    if not os.path.exists(log_file):
        return

    # This is a simple file rotation or truncation. 
    # Real log rotation is better handled by logging.handlers.TimedRotatingFileHandler
    # But since we already configured basicConfig, we can't easily switch without re-setup.
    # We will just check file age? No, we need to delete OLD lines or rotate files.
    # For this task, let's assume we just want to ensure the file doesn't grow infinitely.
    # We can check if file is too old/large and archive it.
    pass
