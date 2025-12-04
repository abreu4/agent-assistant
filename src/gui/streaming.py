"""Streaming output display for CLI mode."""
import sys
import time
from typing import Optional


class StreamingDisplay:
    """Display streaming text updates in the terminal, Claude-style."""

    def __init__(self):
        """Initialize streaming display."""
        self.current_content = ""
        self.is_active = False

        # ANSI codes
        self.CYAN = '\033[1;36m'
        self.GREEN = '\033[1;32m'
        self.GRAY = '\033[0;37m'
        self.RESET = '\033[0m'
        self.BOLD = '\033[1m'

        # ANSI control codes
        self.CLEAR_LINE = '\033[2K'
        self.MOVE_UP = '\033[F'
        self.SAVE_CURSOR = '\033[s'
        self.RESTORE_CURSOR = '\033[u'

    def start(self, header: str = "Response"):
        """
        Start streaming display.

        Args:
            header: Header text to display
        """
        self.is_active = True
        self.current_content = ""

        # Print header
        print(f"\n{self.CYAN}{'=' * 60}{self.RESET}")
        print(f"{self.BOLD}{self.GREEN}🤖 {header}{self.RESET}")
        print(f"{self.CYAN}{'=' * 60}{self.RESET}\n")

    def update(self, text: str, append: bool = True):
        """
        Update the displayed content.

        Args:
            text: New text to display
            append: If True, append to existing content; if False, replace it
        """
        if not self.is_active:
            return

        if append:
            self.current_content += text
        else:
            self.current_content = text

        # Print the update (just append, terminal handles scrolling)
        sys.stdout.write(text)
        sys.stdout.flush()

    def finish(self):
        """Finish streaming and show footer."""
        if not self.is_active:
            return

        self.is_active = False

        # Print footer
        print(f"\n{self.CYAN}{'=' * 60}{self.RESET}\n")

    def clear(self):
        """Clear the current content."""
        self.current_content = ""


class TypewriterDisplay:
    """Display text with typewriter effect for simulation."""

    def __init__(self, delay: float = 0.03):
        """
        Initialize typewriter display.

        Args:
            delay: Delay between characters in seconds
        """
        self.delay = delay

        # ANSI codes
        self.CYAN = '\033[1;36m'
        self.GREEN = '\033[1;32m'
        self.RESET = '\033[0m'
        self.BOLD = '\033[1m'

    def display(self, text: str, header: str = "Response"):
        """
        Display text with typewriter effect.

        Args:
            text: Text to display
            header: Header text
        """
        # Print header
        print(f"\n{self.CYAN}{'=' * 60}{self.RESET}")
        print(f"{self.BOLD}{self.GREEN}🤖 {header}{self.RESET}")
        print(f"{self.CYAN}{'=' * 60}{self.RESET}\n")

        # Type out the text
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(self.delay)

        # Print footer
        print(f"\n{self.CYAN}{'=' * 60}{self.RESET}\n")


class ProgressiveDisplay:
    """Display text progressively as it becomes available."""

    def __init__(self):
        """Initialize progressive display."""
        self.lines_printed = 0
        self.buffer = []

        # ANSI codes
        self.CYAN = '\033[1;36m'
        self.GREEN = '\033[1;32m'
        self.RESET = '\033[0m'
        self.BOLD = '\033[1m'

    def start(self, header: str = "Response", model: Optional[str] = None):
        """
        Start progressive display.

        Args:
            header: Header text
            model: Model name to display in header
        """
        self.lines_printed = 0
        self.buffer = []

        # Build header with optional model info
        if model:
            header_text = f"🤖 {header} {self.CYAN}(model: {model}){self.RESET}"
        else:
            header_text = f"🤖 {header}"

        # Print header
        print(f"\n{self.CYAN}{'=' * 60}{self.RESET}")
        print(f"{self.BOLD}{self.GREEN}{header_text}{self.RESET}")
        print(f"{self.CYAN}{'=' * 60}{self.RESET}")

        self.lines_printed += 3

    def add_text(self, text: str):
        """
        Add text to the display.

        Args:
            text: Text to add
        """
        # Print the text immediately
        print(text, end='', flush=True)
        self.buffer.append(text)

    def add_line(self, line: str):
        """
        Add a complete line to the display.

        Args:
            line: Line to add
        """
        print(line)
        self.buffer.append(line + '\n')
        self.lines_printed += 1

    def finish(self):
        """Finish progressive display and show footer."""
        # Print footer
        print(f"{self.CYAN}{'=' * 60}{self.RESET}\n")
        self.lines_printed += 2

    def get_content(self) -> str:
        """
        Get all displayed content.

        Returns:
            Complete content as string
        """
        return ''.join(self.buffer)
