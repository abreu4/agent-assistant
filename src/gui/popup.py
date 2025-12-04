"""GUI popup window for agent interaction."""
import tkinter as tk
from tkinter import ttk, scrolledtext
from queue import Queue
from typing import Optional

from ..utils.config import config
from ..utils.logging import get_logger

logger = get_logger("popup")


class PopupManager:
    """Manages the agent popup window."""

    def __init__(self, task_queue: Queue):
        """
        Initialize popup manager.

        Args:
            task_queue: Queue for submitting tasks to the agent
        """
        self.task_queue = task_queue
        self.root: Optional[tk.Tk] = None
        self.entry: Optional[tk.Entry] = None
        self.model_var: Optional[tk.StringVar] = None

        # Get configuration
        self.window_width = config.get('gui.window_width', 600)
        self.window_height = config.get('gui.window_height', 200)  # Increased for toggle
        self.font_family = config.get('gui.font_family', 'Arial')
        self.font_size = config.get('gui.font_size', 12)
        self.always_on_top = config.get('gui.always_on_top', True)

    def show(self):
        """Show the popup window."""
        # If window already exists and is visible, just focus it
        if self.root and self.root.winfo_exists():
            logger.info("Popup already visible, focusing")
            self.root.focus_force()
            self.entry.focus_set()
            self.entry.select_range(0, tk.END)
            return

        logger.info("Showing popup window")

        # Create new window
        self.root = tk.Tk()
        self.root.title("Agent Assistant")
        self.root.geometry(f"{self.window_width}x{self.window_height}")

        # Always on top
        if self.always_on_top:
            self.root.attributes('-topmost', True)

        # Center on screen
        self._center_window()

        # Build UI
        self._build_ui()

        # Focus entry
        self.entry.focus_set()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Start event loop
        self.root.mainloop()

    def _center_window(self):
        """Center window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def _build_ui(self):
        """Build the popup UI."""
        # Main frame with padding
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Label
        label = ttk.Label(
            frame,
            text="What can I help with?",
            font=(self.font_family, self.font_size + 2, 'bold')
        )
        label.pack(pady=(0, 10))

        # Entry field
        self.entry = ttk.Entry(frame, font=(self.font_family, self.font_size))
        self.entry.pack(fill=tk.X, pady=(0, 10))

        # Bind keys
        self.entry.bind('<Return>', self._on_submit)
        self.entry.bind('<Escape>', lambda e: self._on_close())

        # Model selection frame
        model_frame = ttk.LabelFrame(frame, text="Model Selection", padding="10")
        model_frame.pack(fill=tk.X, pady=(0, 10))

        # Model selection variable
        self.model_var = tk.StringVar(value="auto")

        # Radio buttons
        radio_frame = ttk.Frame(model_frame)
        radio_frame.pack()

        ttk.Radiobutton(
            radio_frame,
            text="Auto (Smart Routing)",
            variable=self.model_var,
            value="auto"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Radiobutton(
            radio_frame,
            text="Local Only (Fast & Free)",
            variable=self.model_var,
            value="local"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Radiobutton(
            radio_frame,
            text="Remote (Kimi K2)",
            variable=self.model_var,
            value="remote"
        ).pack(side=tk.LEFT, padx=5)

        # Button frame
        button_frame = ttk.Frame(frame)
        button_frame.pack()

        # Submit button
        submit_btn = ttk.Button(
            button_frame,
            text="Submit",
            command=self._on_submit
        )
        submit_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_close
        )
        cancel_btn.pack(side=tk.LEFT)

    def _on_submit(self, event=None):
        """Handle form submission."""
        prompt = self.entry.get().strip()

        if not prompt:
            logger.info("Empty prompt, ignoring")
            return

        # Get model selection
        model_selection = self.model_var.get() if self.model_var else "auto"
        force_model = None if model_selection == "auto" else model_selection

        logger.info(f"Submitting prompt: {prompt[:50]}... (model: {model_selection})")

        # Add task to queue
        self.task_queue.put({
            'type': 'prompt',
            'content': prompt,
            'force_model': force_model
        })

        # Close window
        self._on_close()

    def _on_close(self):
        """Handle window close."""
        if self.root:
            logger.info("Closing popup window")
            self.root.destroy()
            self.root = None

    def display_result(self, result: str, model_used: str = ""):
        """
        Display agent result in a new window.

        Args:
            result: Result text to display
            model_used: Model that was used
        """
        logger.info("Displaying result window")

        # Create result window
        result_window = tk.Toplevel()
        result_window.title("Agent Result")
        result_window.geometry("800x600")

        if self.always_on_top:
            result_window.attributes('-topmost', True)

        # Center window
        result_window.update_idletasks()
        width = result_window.winfo_width()
        height = result_window.winfo_height()
        x = (result_window.winfo_screenwidth() // 2) - (width // 2)
        y = (result_window.winfo_screenheight() // 2) - (height // 2)
        result_window.geometry(f'{width}x{height}+{x}+{y}')

        # Main frame
        frame = ttk.Frame(result_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # Model info label
        if model_used:
            info_label = ttk.Label(
                frame,
                text=f"Model: {model_used}",
                font=(self.font_family, self.font_size - 2)
            )
            info_label.pack(anchor=tk.W, pady=(0, 5))

        # Text widget with scrollbar
        text_widget = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            font=(self.font_family, self.font_size)
        )
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_widget.insert('1.0', result)
        text_widget.config(state=tk.DISABLED)

        # Button frame
        button_frame = ttk.Frame(frame)
        button_frame.pack()

        # Copy button
        def copy_to_clipboard():
            result_window.clipboard_clear()
            result_window.clipboard_append(result)
            copy_btn.config(text="Copied!")
            result_window.after(2000, lambda: copy_btn.config(text="Copy"))

        copy_btn = ttk.Button(
            button_frame,
            text="Copy",
            command=copy_to_clipboard
        )
        copy_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Close button
        close_btn = ttk.Button(
            button_frame,
            text="Close",
            command=result_window.destroy
        )
        close_btn.pack(side=tk.LEFT)

        # Focus window
        result_window.focus_force()
