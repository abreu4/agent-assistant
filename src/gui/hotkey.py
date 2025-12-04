"""Global hotkey listener for triggering agent popup."""
import keyboard
import threading
from typing import Callable
from threading import Event

from ..utils.config import config
from ..utils.logging import get_logger

logger = get_logger("hotkey")


class HotkeyListener:
    """Listens for global hotkey and triggers callback."""

    def __init__(self, callback: Callable, stop_event: Event):
        """
        Initialize hotkey listener.

        Args:
            callback: Function to call when hotkey is pressed
            stop_event: Event to signal shutdown

        Note:
            The keyboard library requires root/sudo privileges on Linux.
            Run with: sudo setcap cap_net_admin+ep $(which python3)
        """
        self.callback = callback
        self.stop_event = stop_event

        # Get hotkey from config
        self.hotkey = config.hotkey_combination
        self.enabled = config.get('hotkey.enabled', True)

        logger.info(f"HotkeyListener initialized with: {self.hotkey}")

    def start(self):
        """
        Start listening for hotkey (blocking).

        This method blocks until stop_event is set.
        """
        if not self.enabled:
            logger.info("Hotkey disabled in configuration")
            self.stop_event.wait()
            return

        try:
            logger.info(f"Starting hotkey listener for: {self.hotkey}")

            # Register hotkey
            keyboard.add_hotkey(self.hotkey, self._on_hotkey_pressed)

            logger.info("Hotkey listener active")

            # Block until stop event
            self.stop_event.wait()

            # Cleanup
            keyboard.remove_hotkey(self.hotkey)
            logger.info("Hotkey listener stopped")

        except Exception as e:
            logger.error(f"Hotkey listener error: {e}")

            if "permission" in str(e).lower() or "access" in str(e).lower():
                logger.error(
                    "Permission denied. On Linux, run:\n"
                    "  sudo setcap cap_net_admin+ep $(which python3)\n"
                    "Or run the service with sudo"
                )

            raise

    def _on_hotkey_pressed(self):
        """Internal callback when hotkey is pressed."""
        logger.info("Hotkey pressed")

        try:
            # Call the callback in a separate thread to avoid blocking
            thread = threading.Thread(target=self.callback, daemon=True)
            thread.start()

        except Exception as e:
            logger.error(f"Error in hotkey callback: {e}")

    def stop(self):
        """Stop the hotkey listener."""
        logger.info("Stopping hotkey listener")
        self.stop_event.set()
