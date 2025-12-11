import sys
import logging
from utils import is_admin, setup_logging, load_config, check_windivert
from network_manager import NetworkManager
from tray_app import TrayApp

def main():
    # Check admin rights
    if not is_admin():
        # Re-run the program with admin rights
        # 0 = SW_HIDE (Hide window)
        # 1 = SW_SHOWNORMAL (Show window)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 0)
        sys.exit()
    
    # Hide console window if it exists (even if started as admin)
    kernel32 = ctypes.WinDLL('kernel32')
    user32 = ctypes.WinDLL('user32')
    hWnd = kernel32.GetConsoleWindow()
    if hWnd:
        user32.ShowWindow(hWnd, 0) # SW_HIDE = 0

    # Load config
    config = load_config()
    if not config:
        print("Config file not found or invalid.")
        sys.exit(1)

    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    logger.info("Application starting...")

    # Check WinDivert
    if not check_windivert():
        logger.warning("WinDivert files missing. Application may fail to start interception.")

    # Initialize Network Manager
    nm = NetworkManager(config)

    # Initialize Tray App
    app = TrayApp(nm)
    
    # Link status callback
    nm.status_callback = app.update_status

    # Run Tray App (blocking)
    try:
        app.run()
    except Exception as e:
        logger.critical(f"Application crashed: {e}")
    finally:
        nm.stop()

if __name__ == "__main__":
    import ctypes
    main()
