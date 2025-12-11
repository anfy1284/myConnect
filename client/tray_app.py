import pystray
from PIL import Image, ImageDraw
import threading
import logging
import sys

logger = logging.getLogger(__name__)

class TrayApp:
    def __init__(self, network_manager):
        self.network_manager = network_manager
        self.icon = None
        self.running = False

    def update_status(self, connected):
        if self.icon:
            color = 'green' if connected else 'red'
            self.icon.icon = self.create_image(color)

    def create_image(self, color):
        # Generate an image for the icon
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color)
        dc = ImageDraw.Draw(image)
        dc.rectangle((width // 2, 0, width, height // 2), fill=color)
        return image

    def on_start(self, icon, item):
        logger.info("Starting network manager...")
        self.network_manager.start()
        icon.icon = self.create_image('green')
        icon.notify("Service started", "MyConnect")

    def on_stop(self, icon, item):
        logger.info("Stopping network manager...")
        self.network_manager.stop()
        icon.icon = self.create_image('red')
        icon.notify("Service stopped", "MyConnect")

    def on_exit(self, icon, item):
        logger.info("Exiting...")
        self.network_manager.stop()
        icon.stop()
        sys.exit(0)

    def on_open_log(self, icon, item):
        import os
        import subprocess
        log_file = 'client.log'
        if os.path.exists(log_file):
            try:
                os.startfile(log_file)
            except AttributeError:
                subprocess.call(['xdg-open', log_file])
        else:
            logger.warning("Log file not found")

    def on_toggle_console(self, icon, item):
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        hWnd = kernel32.GetConsoleWindow()
        if hWnd:
            if user32.IsWindowVisible(hWnd):
                user32.ShowWindow(hWnd, 0) # SW_HIDE
            else:
                user32.ShowWindow(hWnd, 5) # SW_SHOW

    def run(self):
        logger.info("Auto-starting service...")
        self.network_manager.start()
        image = self.create_image('red') # Start with red (disconnected)
        
        menu = pystray.Menu(
            pystray.MenuItem('Start', self.on_start),
            pystray.MenuItem('Stop', self.on_stop),
            pystray.MenuItem('Open Log', self.on_open_log),
            pystray.MenuItem('Show/Hide Console', self.on_toggle_console),
            pystray.MenuItem('Exit', self.on_exit)
        )
        self.icon = pystray.Icon("MyConnect", image, "MyConnect Client", menu)
        self.icon.run()
