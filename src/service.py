"""Main background service for Agent Assistant."""
import asyncio
import signal
import sys
from queue import Queue, Empty
from threading import Thread, Event

from .agent.workflow import HybridAgent
from .gui.popup import PopupManager
from .gui.hotkey import HotkeyListener
from .gui.loading import LoadingSpinner
from .gui.streaming import ProgressiveDisplay
from .utils.config import config
from .utils.logging import setup_logging, get_logger


class AgentService:
    """Main service orchestrating agent, GUI, and hotkey."""

    def __init__(self):
        """Initialize the service."""
        # Setup logging
        log_level = config.get('service.log_level', 'INFO')
        use_systemd = config.get('logging.use_systemd', True)
        self.logger = setup_logging(log_level=log_level, use_systemd=use_systemd)

        self.logger.debug("Initializing Agent Assistant Service")

        # Create components
        self.stop_event = Event()
        self.task_queue = Queue()
        self.cli_mode = False  # Track if running in CLI mode

        self.agent = HybridAgent()
        self.popup_manager = PopupManager(self.task_queue)
        self.hotkey_listener = HotkeyListener(
            self.on_hotkey_triggered,
            self.stop_event
        )

        # Task processor thread
        self.task_thread = None

        # Event loop for async operations
        self.loop = None

        self.logger.debug("Service initialized")

    def on_hotkey_triggered(self):
        """Called when global hotkey is pressed."""
        self.logger.info("Hotkey triggered, showing popup")

        try:
            self.popup_manager.show()
        except Exception as e:
            self.logger.error(f"Error showing popup: {e}")

    def process_tasks(self):
        """
        Background thread for processing agent tasks.

        This runs in a separate thread and processes tasks from the queue.
        """
        self.logger.debug("Task processor started")

        # Create event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Initialize agent
        self.loop.run_until_complete(self.agent.initialize())

        while not self.stop_event.is_set():
            try:
                # Get task from queue with timeout
                task = self.task_queue.get(timeout=1)

                if task['type'] == 'prompt':
                    force_model = task.get('force_model')
                    model_info = f" (force: {force_model})" if force_model else ""
                    self.logger.debug(f"Processing task: {task['content'][:50]}...{model_info}")

                    try:
                        # Run agent with optional force_model override
                        result = self.loop.run_until_complete(
                            self.agent.run(task['content'], force_model=force_model)
                        )

                        # Extract response
                        response = self.agent.get_final_response(result)
                        model_used = result.get('model_used', 'unknown')

                        self.logger.debug(f"Task completed with model: {model_used}")

                        # Display result
                        if self.cli_mode:
                            # Print to console in CLI mode with progressive display
                            display = ProgressiveDisplay()
                            display.start("Response", model=model_used)

                            # Display the response progressively
                            # Split into words for progressive effect
                            words = response.split()
                            for i, word in enumerate(words):
                                if i == 0:
                                    display.add_text(word)
                                else:
                                    display.add_text(' ' + word)

                            # Add final newline before footer
                            print()

                            display.finish()
                        else:
                            # Show popup in GUI mode
                            self.popup_manager.display_result(response, model_used)

                    except Exception as e:
                        self.logger.error(f"Task processing error: {e}")
                        if self.cli_mode:
                            RED = '\033[1;31m'
                            CYAN = '\033[1;36m'
                            RESET = '\033[0m'
                            BOLD = '\033[1m'

                            print(f"\n{CYAN}{'=' * 60}{RESET}")
                            print(f"{BOLD}{RED}❌ Error{RESET}")
                            print(f"{CYAN}{'=' * 60}{RESET}")
                            print(f"Error processing request:\n\n{e}")
                            print(f"{CYAN}{'=' * 60}{RESET}")
                        else:
                            self.popup_manager.display_result(
                                f"Error processing request:\n\n{e}",
                                "error"
                            )

                self.task_queue.task_done()

            except Empty:
                # No task, continue
                continue

            except Exception as e:
                self.logger.error(f"Task processor error: {e}")

        self.logger.info("Task processor stopped")

        # Cleanup event loop
        self.loop.close()

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            signal_name = {
                signal.SIGTERM: "SIGTERM",
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGTSTP: "SIGTSTP (Ctrl+Z)"
            }.get(signum, f"signal {signum}")

            print(f"\n\n\033[1;33m⚠️  Received {signal_name}\033[0m")
            self.logger.info(f"Received {signal_name}, shutting down...")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTSTP, signal_handler)  # Handle Ctrl+Z

    def run(self):
        """
        Main service loop.

        Starts all components and blocks until shutdown.
        """
        self.logger.debug("=" * 60)
        self.logger.debug("Agent Assistant Service Starting")
        self.logger.debug("=" * 60)

        # Setup signal handlers
        self.setup_signal_handlers()

        try:
            # Start task processor thread
            self.task_thread = Thread(target=self.process_tasks, daemon=False)
            self.task_thread.start()

            self.logger.debug("All components started successfully")
            self.logger.debug(f"Hotkey: {config.hotkey_combination}")
            self.logger.debug("Service is ready!")

            # Try to start hotkey listener (blocking)
            try:
                self.hotkey_listener.start()
            except Exception as e:
                self.logger.warning(f"Hotkey listener failed to start: {e}")
                self.logger.warning("Falling back to CLI mode")

                # Run in CLI mode instead
                self.run_cli_mode()

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")

        except Exception as e:
            self.logger.error(f"Service error: {e}", exc_info=True)

        finally:
            self.shutdown()

    def run_cli_mode(self):
        """
        Run service in CLI mode for direct interaction.

        Allows user to type prompts directly and see responses.
        """
        self.cli_mode = True  # Enable CLI mode

        # ANSI color codes
        CYAN = '\033[1;36m'
        GREEN = '\033[1;32m'
        YELLOW = '\033[1;33m'
        RESET = '\033[0m'
        BOLD = '\033[1m'

        print(f"\n{CYAN}{'=' * 60}{RESET}")
        print(f"{BOLD}{CYAN}✨ Agent Assistant - CLI Mode ✨{RESET}")
        print(f"{CYAN}{'=' * 60}{RESET}\n")

        print(f"{GREEN}Commands:{RESET}")
        print(f"  {YELLOW}exit{RESET} or {YELLOW}quit{RESET}     - Stop the service")
        print(f"  {YELLOW}local{RESET} or {YELLOW}remote{RESET}  - Force a specific model tier")
        print(f"  {YELLOW}models{RESET}           - List available remote models")
        print(f"  {YELLOW}switch <number>{RESET}  - Switch to a different remote model")
        print(f"  {YELLOW}current{RESET}          - Show current remote model")
        print(f"  {YELLOW}mode <type>{RESET}      - Switch mode (default/code)")
        print(f"  {YELLOW}showmode{RESET}         - Show current local mode")

        print(f"\n{CYAN}{'=' * 60}{RESET}")

        force_model = None

        while not self.stop_event.is_set():
            try:
                # Get user input with styled prompt
                # ANSI codes: \033[1;36m = bold cyan, \033[0m = reset
                prompt = input("\n\033[1;36m❯\033[0m ").strip()

                if not prompt:
                    continue

                # Check for commands
                if prompt.lower() in ['exit', 'quit', 'q']:
                    break

                if prompt.lower() == 'local':
                    force_model = 'local'
                    print("\033[1;33m🔧 Forcing local model for next prompt\033[0m")
                    continue

                if prompt.lower() == 'remote':
                    force_model = 'remote'
                    print("\033[1;33m🔧 Forcing remote model for next prompt\033[0m")
                    continue

                if prompt.lower() == 'auto':
                    force_model = None
                    print("\033[1;32m✓ Automatic model selection enabled\033[0m")
                    continue

                if prompt.lower() in ['models', 'list-models', 'list']:
                    self._list_all_models()
                    continue

                if prompt.lower() in ['current', 'current-model']:
                    self._show_current_model()
                    continue

                if prompt.lower().startswith('switch '):
                    try:
                        model_num = int(prompt.split()[1])
                        self._switch_remote_model(model_num)
                    except (ValueError, IndexError) as e:
                        print(f"Invalid command. Use: switch <number>")
                    continue

                if prompt.lower().startswith('mode '):
                    try:
                        mode = prompt.split()[1].lower()
                        self._switch_local_mode(mode)
                    except (ValueError, IndexError) as e:
                        print(f"Invalid command. Use: mode <default|code>")
                    continue

                if prompt.lower() in ['showmode', 'show-mode']:
                    self._show_local_mode()
                    continue

                # Submit task
                task = {
                    'type': 'prompt',
                    'content': prompt,
                    'force_model': force_model
                }

                self.task_queue.put(task)

                # Show loading spinner while processing
                spinner = LoadingSpinner("Thinking...", style="spinner")
                spinner.start()

                # Wait for task completion
                self.task_queue.join()

                # Stop spinner
                spinner.stop()

                # Reset force_model after use
                if force_model:
                    force_model = None

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'exit' to quit.")
                continue

            except EOFError:
                print("\n")  # Just add newline, goodbye message will be shown by shutdown
                break

            except Exception as e:
                self.logger.error(f"CLI error: {e}")
                print(f"\nError: {e}")

    def _list_all_models(self):
        """List all available models (local and remote)."""
        try:
            # ANSI color codes
            CYAN = '\033[1;36m'
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            GRAY = '\033[0;37m'
            RESET = '\033[0m'
            BOLD = '\033[1m'
            MAGENTA = '\033[1;35m'

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{CYAN}📋 Available Models{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            # Local models - Default mode
            local_config = config.get_llm_config('local')
            all_local_models = local_config.get('available_models', {})
            current_mode = config.get_local_mode()

            if isinstance(all_local_models, dict):
                # Show default models
                print(f"{BOLD}{MAGENTA}💻 Local Models (Default Mode):{RESET}")
                default_models = all_local_models.get('default', [])
                for i, model in enumerate(default_models, 1):
                    mode_indicator = f" {GREEN}✓ [ACTIVE MODE]{RESET}" if current_mode == 'default' else ""
                    print(f"  {YELLOW}{i}.{RESET} {BOLD}{model['name']}{RESET}{mode_indicator}")
                    print(f"     {GRAY}ID:{RESET} {model['id']}")
                    print(f"     {GRAY}{model['description']}{RESET}")

                print()

                # Show code models
                print(f"{BOLD}{MAGENTA}💻 Local Models (Code Mode):{RESET}")
                code_models = all_local_models.get('code', [])
                for i, model in enumerate(code_models, 1):
                    mode_indicator = f" {GREEN}✓ [ACTIVE MODE]{RESET}" if current_mode == 'code' else ""
                    print(f"  {YELLOW}{i}.{RESET} {BOLD}{model['name']}{RESET}{mode_indicator}")
                    print(f"     {GRAY}ID:{RESET} {model['id']}")
                    print(f"     {GRAY}{model['description']}{RESET}")

                print()

            # Remote models
            print(f"{BOLD}{MAGENTA}🌐 Remote Models (OpenRouter):{RESET}")
            remote_models = self.agent.llm_system.get_available_remote_models()
            current_remote = self.agent.llm_system.get_current_remote_model()

            for i, model in enumerate(remote_models, 1):
                is_current = f" {GREEN}✓ [CURRENT]{RESET}" if model['id'] == current_remote else ""
                print(f"  {YELLOW}{i}.{RESET} {BOLD}{model['name']}{RESET}{is_current}")
                print(f"     {GRAY}ID:{RESET} {model['id']}")
                print(f"     {GRAY}{model['description']}{RESET}")

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{GRAY}Use 'mode default' or 'mode code' to switch local model modes{RESET}")
            print(f"{GRAY}Use 'switch <number>' to change remote model{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}")

        except Exception as e:
            self.logger.error(f"Error listing models: {e}")
            print(f"\033[1;31mError:\033[0m {e}")

    def _list_remote_models(self):
        """List all available remote models."""
        try:
            # ANSI color codes
            CYAN = '\033[1;36m'
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            GRAY = '\033[0;37m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            models = self.agent.llm_system.get_available_remote_models()
            current = self.agent.llm_system.get_current_remote_model()

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{CYAN}🌐 Available Remote Models{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            for i, model in enumerate(models, 1):
                is_current = f" {GREEN}✓ [CURRENT]{RESET}" if model['id'] == current else ""
                print(f"{YELLOW}{i}.{RESET} {BOLD}{model['name']}{RESET}{is_current}")
                print(f"   {GRAY}ID:{RESET} {model['id']}")
                print(f"   {GRAY}{model['description']}{RESET}")
                print()

            print(f"{CYAN}{'=' * 60}{RESET}")
        except Exception as e:
            self.logger.error(f"Error listing models: {e}")
            print(f"\033[1;31mError:\033[0m {e}")

    def _show_current_model(self):
        """Show the current active remote model."""
        try:
            # ANSI color codes
            CYAN = '\033[1;36m'
            GREEN = '\033[1;32m'
            GRAY = '\033[0;37m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            current_id = self.agent.llm_system.get_current_remote_model()
            models = self.agent.llm_system.get_available_remote_models()

            # Find the model details
            current_model = next((m for m in models if m['id'] == current_id), None)

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            if current_model:
                print(f"{BOLD}{GREEN}🎯 Current Remote Model{RESET}")
                print(f"{CYAN}{'=' * 60}{RESET}\n")
                print(f"{BOLD}{current_model['name']}{RESET}")
                print(f"{GRAY}ID:{RESET} {current_model['id']}")
                print(f"{GRAY}{current_model['description']}{RESET}")
            else:
                print(f"{BOLD}{GREEN}🎯 Current Remote Model{RESET}")
                print(f"{CYAN}{'=' * 60}{RESET}\n")
                print(f"{current_id}")
            print(f"\n{CYAN}{'=' * 60}{RESET}")
        except Exception as e:
            self.logger.error(f"Error showing current model: {e}")
            print(f"\033[1;31mError:\033[0m {e}")

    def _switch_remote_model(self, model_num: int):
        """
        Switch to a different remote model by number.

        Args:
            model_num: 1-based model number from the list
        """
        try:
            # ANSI color codes
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            RED = '\033[1;31m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            models = self.agent.llm_system.get_available_remote_models()

            if model_num < 1 or model_num > len(models):
                print(f"\n{RED}Invalid model number. Choose 1-{len(models)}{RESET}")
                return

            selected_model = models[model_num - 1]
            print(f"\n{YELLOW}⏳ Switching to: {BOLD}{selected_model['name']}{RESET}...")

            self.agent.llm_system.switch_remote_model(selected_model['id'])

            print(f"{GREEN}✓ Successfully switched to {BOLD}{selected_model['name']}{RESET}")
            self.logger.info(f"Switched remote model to: {selected_model['id']}")

        except Exception as e:
            self.logger.error(f"Error switching model: {e}")
            print(f"\n{RED}Error:{RESET} {e}")

    def _show_local_mode(self):
        """Show the current local model mode."""
        try:
            # ANSI color codes
            CYAN = '\033[1;36m'
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            current_mode = config.get_local_mode()

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{GREEN}🎯 Current Local Mode{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")
            print(f"{BOLD}{current_mode.upper()}{RESET} mode")

            if current_mode == 'code':
                print(f"{YELLOW}Using code-focused models{RESET}")
            else:
                print(f"{YELLOW}Using general-purpose models{RESET}")

            print(f"\n{CYAN}{'=' * 60}{RESET}")
        except Exception as e:
            self.logger.error(f"Error showing mode: {e}")
            print(f"\033[1;31mError:\033[0m {e}")

    def _switch_local_mode(self, mode: str):
        """
        Switch local model mode.

        Args:
            mode: Mode to switch to ('default' or 'code')
        """
        try:
            # ANSI color codes
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            RED = '\033[1;31m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            if mode not in ['default', 'code']:
                print(f"\n{RED}Invalid mode. Use: mode default{RESET} or {RED}mode code{RESET}")
                return

            print(f"\n{YELLOW}⏳ Switching to {BOLD}{mode}{RESET}{YELLOW} mode...{RESET}")

            config.set_local_mode(mode)

            print(f"{GREEN}✓ Switched to {BOLD}{mode.upper()}{RESET}{GREEN} mode{RESET}")

            if mode == 'code':
                print(f"{YELLOW}Now using code-focused models (CodeLlama, DeepSeek Coder, etc.){RESET}")
            else:
                print(f"{YELLOW}Now using general-purpose models (Llama, Mistral, etc.){RESET}")

            self.logger.info(f"Switched local mode to: {mode}")

        except Exception as e:
            self.logger.error(f"Error switching mode: {e}")
            print(f"\n{RED}Error:{RESET} {e}")

    def shutdown(self):
        """Graceful shutdown of all components."""
        self.logger.info("Shutting down service...")

        # Signal stop
        self.stop_event.set()

        # Wait for task thread
        if self.task_thread and self.task_thread.is_alive():
            self.logger.info("Waiting for task processor to finish...")
            self.task_thread.join(timeout=5)

        # Display goodbye message
        CYAN = '\033[1;36m'
        GREEN = '\033[1;32m'
        RESET = '\033[0m'
        BOLD = '\033[1m'

        print(f"\n{CYAN}{'=' * 60}{RESET}")
        print(f"{BOLD}{GREEN}👋 Thanks for using Agent Assistant!{RESET}")
        print(f"{CYAN}{'=' * 60}{RESET}\n")

        self.logger.debug("=" * 60)
        self.logger.debug("Agent Assistant Service Stopped")
        self.logger.debug("=" * 60)


def main():
    """Main entry point."""
    service = AgentService()

    try:
        service.run()
    except Exception as e:
        service.logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
