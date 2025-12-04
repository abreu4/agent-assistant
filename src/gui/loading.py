"""Loading spinner for CLI mode."""
import sys
import time
import threading
from typing import Optional


class LoadingSpinner:
    """Animated loading spinner for CLI."""

    # Unicode spinner frames
    SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    # Alternative spinners
    DOTS_FRAMES = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']
    SIMPLE_FRAMES = ['|', '/', '-', '\\']
    DOTS_SIMPLE = ['.  ', '.. ', '...', ' ..', '  .', '   ']

    def __init__(self, message: str = "Processing", style: str = "spinner"):
        """
        Initialize loading spinner.

        Args:
            message: Text to display next to spinner
            style: Spinner style - "spinner", "dots", "simple", or "dots_simple"
        """
        self.message = message
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

        # Select spinner style
        if style == "dots":
            self.frames = self.DOTS_FRAMES
        elif style == "simple":
            self.frames = self.SIMPLE_FRAMES
        elif style == "dots_simple":
            self.frames = self.DOTS_SIMPLE
        else:
            self.frames = self.SPINNER_FRAMES

        # ANSI colors
        self.CYAN = '\033[1;36m'
        self.GRAY = '\033[0;37m'
        self.RESET = '\033[0m'

    def _spin(self):
        """Run the spinner animation."""
        idx = 0
        while self.is_running:
            frame = self.frames[idx % len(self.frames)]

            # Build the loading line
            line = f"\r{self.CYAN}{frame}{self.RESET} {self.GRAY}{self.message}{self.RESET}"

            # Write to stdout
            sys.stdout.write(line)
            sys.stdout.flush()

            # Next frame
            idx += 1
            time.sleep(0.1)

    def start(self, message: Optional[str] = None):
        """
        Start the spinner.

        Args:
            message: Optional new message to display
        """
        if message:
            self.message = message

        if self.is_running:
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def update(self, message: str):
        """
        Update the spinner message while running.

        Args:
            message: New message to display
        """
        self.message = message

    def stop(self, final_message: Optional[str] = None):
        """
        Stop the spinner.

        Args:
            final_message: Optional message to display after stopping
        """
        if not self.is_running:
            return

        self.is_running = False

        if self.thread:
            self.thread.join(timeout=0.5)

        # Clear the line
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        sys.stdout.flush()

        # Display final message if provided
        if final_message:
            print(final_message)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False
