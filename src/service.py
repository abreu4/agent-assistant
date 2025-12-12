"""Main CLI service for Agent Assistant."""
import asyncio
import signal
import sys
from queue import Queue, Empty
from threading import Thread, Event

from .agent.workflow import HybridAgent
from .gui.loading import LoadingSpinner
from .gui.streaming import ProgressiveDisplay
from .utils.config import config
from .utils.logging import setup_logging, get_logger


class AgentService:
    """Main CLI service for the agent."""

    def __init__(self):
        """Initialize the service."""
        # Setup logging - use WARNING level if debug is false
        debug_mode = config.get('service.debug', False)
        log_level = 'DEBUG' if debug_mode else 'WARNING'
        use_systemd = config.get('logging.use_systemd', False)  # Default to False for CLI
        self.logger = setup_logging(log_level=log_level, use_systemd=use_systemd)

        self.logger.debug("Initializing Agent Assistant CLI Service")

        # Create components
        self.stop_event = Event()
        self.task_queue = Queue()

        self.agent = HybridAgent()

        # Task processor thread
        self.task_thread = None

        # Event loop for async operations
        self.loop = None

        self.logger.debug("Service initialized")

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

                        # Display result in CLI
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

                    except Exception as e:
                        self.logger.error(f"Task processing error: {e}")
                        RED = '\033[1;31m'
                        CYAN = '\033[1;36m'
                        RESET = '\033[0m'
                        BOLD = '\033[1m'

                        print(f"\n{CYAN}{'=' * 60}{RESET}")
                        print(f"{BOLD}{RED}❌ Error{RESET}")
                        print(f"{CYAN}{'=' * 60}{RESET}")
                        print(f"Error processing request:\n\n{e}")
                        print(f"{CYAN}{'=' * 60}{RESET}")

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
        Main service loop - runs in CLI mode.

        Starts the task processor and runs the interactive CLI.
        """
        self.logger.debug("=" * 60)
        self.logger.debug("Agent Assistant CLI Service Starting")
        self.logger.debug("=" * 60)

        # Setup signal handlers
        self.setup_signal_handlers()

        # Check if accounts exist (required for email functionality)
        if not self._check_accounts():
            # User refused to add account, exit gracefully
            self.logger.info("Service stopped: No email accounts configured")
            return

        try:
            # Start task processor thread
            self.task_thread = Thread(target=self.process_tasks, daemon=False)
            self.task_thread.start()

            self.logger.debug("Task processor started successfully")
            self.logger.debug("Service is ready!")

            # Run in CLI mode
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
        print(f"  {YELLOW}local{RESET} / {YELLOW}remote{RESET} / {YELLOW}auto{RESET} - Set model mode (persists)")
        print(f"  {YELLOW}models{RESET}           - List available remote models")
        print(f"  {YELLOW}switch <number>{RESET}  - Switch to a different remote model")
        print(f"  {YELLOW}current{RESET}          - Show current remote model")
        print(f"  {YELLOW}sticky{RESET}           - Show sticky model status")
        print(f"  {YELLOW}reset-sticky{RESET}     - Reset sticky model preferences")
        print(f"  {YELLOW}accounts{RESET}         - List all configured email accounts")
        print(f"  {YELLOW}account add{RESET}      - Add a new email account")
        print(f"  {YELLOW}account remove <email>{RESET} - Remove an email account")
        print(f"  {YELLOW}account switch <email>{RESET} - Switch current account")
        print(f"  {YELLOW}account disable <email>{RESET} - Disable account from syncing")
        print(f"  {YELLOW}account enable <email>{RESET}  - Re-enable account for syncing")
        print(f"  {YELLOW}sync{RESET}             - Sync emails from all enabled accounts")
        print(f"  {YELLOW}jobs{RESET}             - List tracked job postings")
        print(f"  {YELLOW}job <id>{RESET}         - Show details for a specific job")
        print(f"  {YELLOW}documents{RESET}        - List indexed documents")

        print(f"\n{CYAN}{'=' * 60}{RESET}")

        # Load persisted user preference (default to "local")
        force_model = config.get_user_force_model() or "local"

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
                    config.set_user_force_model('local')
                    print("\033[1;32m✓ Mode: Local models only (persisted)\033[0m")
                    continue

                if prompt.lower() == 'remote':
                    force_model = 'remote'
                    config.set_user_force_model('remote')
                    print("\033[1;32m✓ Mode: Remote models only (persisted)\033[0m")
                    continue

                if prompt.lower() == 'auto':
                    force_model = None
                    config.set_user_force_model(None)
                    print("\033[1;32m✓ Mode: Auto routing (persisted)\033[0m")
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


                if prompt.lower() == 'sticky':
                    self._show_sticky_status()
                    continue

                if prompt.lower() in ['reset-sticky', 'reset']:
                    self._reset_sticky_models()
                    continue

                if prompt.lower() == 'accounts':
                    self._list_accounts()
                    continue

                if prompt.lower() == 'account add':
                    self._add_account()
                    continue

                if prompt.lower().startswith('account remove '):
                    try:
                        email = prompt.split('account remove ', 1)[1].strip()
                        self._remove_account(email)
                    except IndexError:
                        print(f"Invalid command. Use: account remove <email>")
                    continue

                if prompt.lower().startswith('account switch '):
                    try:
                        email = prompt.split('account switch ', 1)[1].strip()
                        self._switch_account(email)
                    except IndexError:
                        print(f"Invalid command. Use: account switch <email>")
                    continue

                if prompt.lower().startswith('account disable '):
                    try:
                        email = prompt.split('account disable ', 1)[1].strip()
                        self._disable_account(email)
                    except IndexError:
                        print(f"Invalid command. Use: account disable <email>")
                    continue

                if prompt.lower().startswith('account enable '):
                    try:
                        email = prompt.split('account enable ', 1)[1].strip()
                        self._enable_account(email)
                    except IndexError:
                        print(f"Invalid command. Use: account enable <email>")
                    continue

                if prompt.lower() in ['check-emails', 'sync-emails', 'sync']:
                    import asyncio
                    asyncio.run(self._sync_emails())
                    continue

                if prompt.lower() == 'jobs':
                    self._list_jobs()
                    continue

                if prompt.lower() == 'documents':
                    self._list_documents()
                    continue

                if prompt.lower().startswith('job '):
                    try:
                        job_id = int(prompt.split()[1])
                        self._show_job_details(job_id)
                    except (ValueError, IndexError):
                        print(f"Invalid command. Use: job <id>")
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
                print(f"{BOLD}{GREEN}🎯 Current Configuration{RESET}")
                print(f"{CYAN}{'=' * 60}{RESET}\n")
                print(f"{BOLD}Remote Model:{RESET}")
                print(f"  {current_model['name']}")
                print(f"  {GRAY}ID:{RESET} {current_model['id']}")
                print(f"  {GRAY}{current_model['description']}{RESET}")
            else:
                print(f"{BOLD}{GREEN}🎯 Current Configuration{RESET}")
                print(f"{CYAN}{'=' * 60}{RESET}\n")
                print(f"{BOLD}Remote Model:{RESET} {current_id}")

            # Show current force_model mode
            force_mode = config.get_user_force_model() or "auto"
            mode_display = {
                "local": f"{GREEN}local{RESET} (all queries use local models)",
                "remote": f"{GREEN}remote{RESET} (all queries use remote models)",
                "auto": f"{GREEN}auto{RESET} (intelligent routing)"
            }.get(force_mode, force_mode)
            print(f"\n{BOLD}Mode:{RESET} {mode_display}")
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


    def _show_sticky_status(self):
        """Show the current sticky model and locked model status."""
        try:
            # ANSI color codes
            CYAN = '\033[1;36m'
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            GRAY = '\033[0;37m'
            MAGENTA = '\033[1;35m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            sticky_enabled = config.get_sticky_model_enabled()
            locked_models = self.agent.llm_system.get_all_locked_models()

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{GREEN}📌 Model Lock Status{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            # Show locked models (current session)
            print(f"{BOLD}{MAGENTA}🔒 Currently Locked Models (This Session):{RESET}\n")

            local_locked = locked_models.get('local')
            remote_locked = locked_models.get('remote')

            if local_locked:
                print(f"  💻 Local : {GREEN}✓{RESET} {local_locked}")
            else:
                print(f"  💻 Local : {YELLOW}⚠{RESET} {GRAY}Not locked{RESET}")

            if remote_locked:
                print(f"  🌐 Remote: {GREEN}✓{RESET} {remote_locked}")
            else:
                print(f"  🌐 Remote: {YELLOW}⚠{RESET} {GRAY}Not locked{RESET}")

            # Show sticky models (persisted across sessions)
            print(f"\n{CYAN}{'-' * 60}{RESET}\n")
            print(f"{BOLD}Sticky Model:{RESET} {GREEN}Enabled{RESET}" if sticky_enabled else f"{BOLD}Sticky Model:{RESET} {YELLOW}Disabled{RESET}")
            print()

            if sticky_enabled:
                print(f"{BOLD}💾 Saved for Next Session:{RESET}\n")

                saved_local = config.get_last_successful_model('local')
                saved_remote = config.get_last_successful_model('remote')

                if saved_local:
                    print(f"  💻 Local : {saved_local}")
                else:
                    print(f"  💻 Local : {GRAY}None{RESET}")

                if saved_remote:
                    print(f"  🌐 Remote: {saved_remote}")
                else:
                    print(f"  🌐 Remote: {GRAY}None{RESET}")
            else:
                print(f"{YELLOW}Sticky model is disabled. Models will be re-tested each session.{RESET}")

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{GRAY}💡 Locked models are selected during warmup and used for all requests.{RESET}")
            print(f"{GRAY}   If a locked model fails, a new one is automatically tested and locked.{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}")
        except Exception as e:
            self.logger.error(f"Error showing sticky status: {e}")
            print(f"\033[1;31mError:\033[0m {e}")

    def _reset_sticky_models(self):
        """Reset sticky model preferences."""
        try:
            # ANSI color codes
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            CYAN = '\033[1;36m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            print(f"\n{YELLOW}⏳ Resetting sticky model preferences...{RESET}")

            # Reset preferences
            config.set_last_successful_model('local', None)
            config.set_last_successful_model('remote', None)

            print(f"{GREEN}✓ Sticky model preferences have been reset{RESET}")
            print(f"{CYAN}The agent will test models in priority order during next warmup.{RESET}")

            self.logger.info("Sticky model preferences reset")

        except Exception as e:
            self.logger.error(f"Error resetting sticky models: {e}")
            print(f"\n\033[1;31mError:\033[0m {e}")

    def _check_accounts(self) -> bool:
        """Check if email accounts are configured, prompt to add if none exist.

        Returns:
            bool: True if accounts exist or were added, False if user refused
        """
        from .agent.email import get_account_manager

        account_manager = get_account_manager()
        accounts = account_manager.get_accounts()

        if accounts:
            self.logger.info(f"Found {len(accounts)} configured email account(s)")
            return True

        # No accounts configured - prompt user
        CYAN = '\033[1;36m'
        YELLOW = '\033[1;33m'
        GREEN = '\033[1;32m'
        RED = '\033[1;31m'
        RESET = '\033[0m'
        BOLD = '\033[1m'

        print(f"\n{CYAN}{'=' * 60}{RESET}")
        print(f"{BOLD}{YELLOW}⚠️  No Email Accounts Configured{RESET}")
        print(f"{CYAN}{'=' * 60}{RESET}\n")
        print(f"The agent requires at least one email account for job monitoring.")
        print(f"Would you like to add an email account now?\n")

        response = input(f"{BOLD}Add email account? (y/n):{RESET} ").strip().lower()

        if response not in ['y', 'yes']:
            print(f"\n{RED}✗ Cannot start without an email account{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")
            return False

        # User wants to add account - run interactive flow
        print(f"\n{GREEN}✓ Starting account setup...{RESET}\n")

        try:
            import asyncio

            # Create event loop for async account addition
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            account = loop.run_until_complete(
                account_manager.add_account_interactive()
            )

            loop.close()

            print(f"\n{GREEN}✓ Successfully added account: {account.email}{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            return True

        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}✗ Account setup cancelled{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")
            return False

        except Exception as e:
            self.logger.error(f"Failed to add account: {e}")
            print(f"\n{RED}✗ Failed to add account: {e}{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")
            return False

    def _list_accounts(self):
        """List all configured email accounts."""
        try:
            from .agent.email import get_account_manager

            # ANSI color codes
            CYAN = '\033[1;36m'
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            GRAY = '\033[0;37m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            account_manager = get_account_manager()
            accounts = account_manager.get_accounts()
            current = account_manager.get_current_account()

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{CYAN}📧 Configured Email Accounts{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            if not accounts:
                print(f"{YELLOW}No accounts configured{RESET}")
            else:
                for i, account in enumerate(accounts, 1):
                    is_current = f" {GREEN}✓ [CURRENT]{RESET}" if current and account.email == current.email else ""
                    status = f" {GREEN}✓ [ENABLED]{RESET}" if account.enabled else f" {GRAY}[DISABLED]{RESET}"
                    print(f"{YELLOW}{i}.{RESET} {BOLD}{account.email}{RESET}{is_current}{status}")
                    print(f"   {GRAY}Provider:{RESET} {account.provider_type.upper()}")
                    print(f"   {GRAY}Name:{RESET} {account.display_name}")
                    print(f"   {GRAY}Added:{RESET} {account.added_date.strftime('%Y-%m-%d %H:%M')}")
                    if account.last_sync:
                        print(f"   {GRAY}Last Sync:{RESET} {account.last_sync.strftime('%Y-%m-%d %H:%M')}")
                    print()

            print(f"{CYAN}{'=' * 60}{RESET}")

        except Exception as e:
            self.logger.error(f"Error listing accounts: {e}")
            print(f"\033[1;31mError:\033[0m {e}")

    def _add_account(self):
        """Add a new email account via browser OAuth."""
        try:
            from .agent.email import get_account_manager
            import asyncio

            # ANSI color codes
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            RED = '\033[1;31m'
            CYAN = '\033[1;36m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{CYAN}➕ Add Email Account{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            account_manager = get_account_manager()

            print(f"{YELLOW}⏳ Opening browser for authentication...{RESET}\n")

            # Create event loop for async account addition
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            account = loop.run_until_complete(
                account_manager.add_account_interactive()
            )

            loop.close()

            print(f"\n{GREEN}✓ Successfully added account: {BOLD}{account.email}{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            self.logger.info(f"Added email account: {account.email}")

        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}✗ Account setup cancelled{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

        except Exception as e:
            self.logger.error(f"Failed to add account: {e}")
            print(f"\n{RED}✗ Failed to add account: {e}{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

    def _remove_account(self, email: str):
        """Remove an email account.

        Args:
            email: Email address to remove
        """
        try:
            from .agent.email import get_account_manager

            # ANSI color codes
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            RED = '\033[1;31m'
            CYAN = '\033[1;36m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            account_manager = get_account_manager()

            # Check if account exists
            accounts = account_manager.get_accounts()
            if not any(acc.email == email for acc in accounts):
                print(f"\n{RED}✗ Account not found: {email}{RESET}\n")
                return

            # Confirm removal
            print(f"\n{YELLOW}⚠️  Remove account: {BOLD}{email}{RESET}")
            response = input(f"{BOLD}Are you sure? (y/n):{RESET} ").strip().lower()

            if response not in ['y', 'yes']:
                print(f"{CYAN}✗ Cancelled{RESET}\n")
                return

            # Remove account
            if account_manager.remove_account(email):
                print(f"\n{GREEN}✓ Successfully removed account: {BOLD}{email}{RESET}\n")
                self.logger.info(f"Removed email account: {email}")
            else:
                print(f"\n{RED}✗ Failed to remove account{RESET}\n")

        except Exception as e:
            self.logger.error(f"Error removing account: {e}")
            print(f"\n{RED}✗ Error: {e}{RESET}\n")

    def _switch_account(self, email: str):
        """Switch to a different email account.

        Args:
            email: Email address to switch to
        """
        try:
            from .agent.email import get_account_manager

            # ANSI color codes
            GREEN = '\033[1;32m'
            RED = '\033[1;31m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            account_manager = get_account_manager()

            # Check if account exists
            accounts = account_manager.get_accounts()
            if not any(acc.email == email for acc in accounts):
                print(f"\n{RED}✗ Account not found: {email}{RESET}\n")
                return

            # Switch account
            if account_manager.set_current_account(email):
                print(f"\n{GREEN}✓ Switched to account: {BOLD}{email}{RESET}\n")
                self.logger.info(f"Switched to email account: {email}")
            else:
                print(f"\n{RED}✗ Failed to switch account{RESET}\n")

        except Exception as e:
            self.logger.error(f"Error switching account: {e}")
            print(f"\n{RED}✗ Error: {e}{RESET}\n")

    def _disable_account(self, email: str):
        """Disable account from syncing without removing it.

        Args:
            email: Email address to disable
        """
        try:
            from .agent.email import get_account_manager

            # ANSI color codes
            GREEN = '\033[1;32m'
            RED = '\033[1;31m'
            GRAY = '\033[90m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            account_manager = get_account_manager()

            if account_manager.disable_account(email):
                print(f"\n{GREEN}✓ Disabled account: {BOLD}{email}{RESET}")
                print(f"{GRAY}This account will be skipped during sync{RESET}\n")
                self.logger.info(f"Disabled account: {email}")
            else:
                print(f"\n{RED}✗ Failed to disable account{RESET}\n")

        except Exception as e:
            self.logger.error(f"Error disabling account: {e}")
            print(f"\n{RED}✗ Error: {e}{RESET}\n")

    def _enable_account(self, email: str):
        """Re-enable account for syncing.

        Args:
            email: Email address to enable
        """
        try:
            from .agent.email import get_account_manager

            # ANSI color codes
            GREEN = '\033[1;32m'
            RED = '\033[1;31m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            account_manager = get_account_manager()

            if account_manager.enable_account(email):
                print(f"\n{GREEN}✓ Enabled account: {BOLD}{email}{RESET}\n")
                self.logger.info(f"Enabled account: {email}")
            else:
                print(f"\n{RED}✗ Failed to enable account{RESET}\n")

        except Exception as e:
            self.logger.error(f"Error enabling account: {e}")
            print(f"\n{RED}✗ Error: {e}{RESET}\n")

    async def _sync_emails(self):
        """Sync emails and detect job postings."""
        try:
            from .agent.tracking.manager import get_job_manager

            # ANSI color codes
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            RED = '\033[1;31m'
            CYAN = '\033[1;36m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{CYAN}📧 Syncing Emails{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            print(f"{YELLOW}⏳ Fetching emails and detecting job postings...{RESET}\n")

            manager = get_job_manager()

            # Run sync in executor to not block
            import asyncio
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(None, manager.sync_emails)

            if stats and 'error' not in stats:
                accounts_synced = stats.get('accounts_synced', 0)
                total_emails = stats.get('total_emails_processed', 0)
                total_jobs = stats.get('total_jobs_found', 0)

                print(f"{GREEN}✓ Email sync complete{RESET}")
                print(f"  Accounts synced: {BOLD}{accounts_synced}{RESET}")
                print(f"  Total emails: {BOLD}{total_emails}{RESET}")
                print(f"  Total jobs found: {BOLD}{total_jobs}{RESET}\n")

                # Show per-account results
                if stats.get('by_account'):
                    print(f"{BOLD}Per-account results:{RESET}")
                    for email, account_stats in stats['by_account'].items():
                        if 'error' in account_stats:
                            print(f"  {RED}✗{RESET} {email}: {account_stats['error']}")
                        else:
                            emails_proc = account_stats.get('emails_processed', 0)
                            jobs_proc = account_stats.get('jobs_found', 0)
                            print(f"  {GREEN}✓{RESET} {email}: {emails_proc} emails, {jobs_proc} jobs")
                    print()

                self.logger.info(f"Email sync: {accounts_synced} accounts, {total_emails} emails, {total_jobs} jobs")
            elif stats and 'error' in stats:
                print(f"{YELLOW}⚠{RESET}  {stats['error']}\n")
            else:
                print(f"{GREEN}✓ Email sync complete (no new jobs){RESET}\n")

            print(f"{CYAN}{'=' * 60}{RESET}\n")

        except Exception as e:
            self.logger.error(f"Email sync failed: {e}")
            print(f"\n{RED}✗ Email sync failed: {e}{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

    def _list_jobs(self, status: str = "new", limit: int = 20):
        """List tracked job postings.

        Args:
            status: Filter by status (default: new)
            limit: Maximum number of jobs (default: 20)
        """
        try:
            from .agent.tracking import get_job_database

            # ANSI color codes
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            RED = '\033[1;31m'
            CYAN = '\033[1;36m'
            GRAY = '\033[90m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            db = get_job_database()
            jobs = db.get_jobs(status=status, limit=limit)

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{CYAN}💼 Job Postings ({status.upper()}){RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            if not jobs:
                print(f"{YELLOW}No jobs found with status: {status}{RESET}\n")
            else:
                for job in jobs:
                    print(f"{YELLOW}[ID: {job['id']}]{RESET} {BOLD}{job['position']}{RESET}")
                    print(f"  {GRAY}Company:{RESET} {job['company'] or 'N/A'}")
                    print(f"  {GRAY}Location:{RESET} {job['location'] or 'N/A'}")
                    print(f"  {GRAY}Status:{RESET} {job['status']}")
                    print(f"  {GRAY}Found:{RESET} {job['found_date']}")
                    if job['application_link']:
                        print(f"  {GRAY}Link:{RESET} {job['application_link']}")
                    print()

            print(f"{CYAN}{'=' * 60}{RESET}\n")

        except Exception as e:
            self.logger.error(f"Error listing jobs: {e}")
            print(f"\n{RED}✗ Error: {e}{RESET}\n")

    def _list_documents(self):
        """List indexed job application documents."""
        try:
            from .agent.document_rag import get_document_rag

            # ANSI color codes
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            CYAN = '\033[1;36m'
            GRAY = '\033[90m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            rag = get_document_rag()
            summary = rag.get_document_summary()

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{CYAN}📄 Indexed Documents{RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            print(summary)

            print(f"\n{CYAN}{'=' * 60}{RESET}\n")

        except Exception as e:
            self.logger.error(f"Error listing documents: {e}")
            print(f"\n{RED}✗ Error: {e}{RESET}\n")

    def _show_job_details(self, job_id: int):
        """Show detailed information for a specific job.

        Args:
            job_id: Job ID from database
        """
        try:
            from .agent.tracking import get_job_database

            # ANSI color codes
            GREEN = '\033[1;32m'
            YELLOW = '\033[1;33m'
            RED = '\033[1;31m'
            CYAN = '\033[1;36m'
            GRAY = '\033[90m'
            RESET = '\033[0m'
            BOLD = '\033[1m'

            db = get_job_database()
            job = db.get_job_by_id(job_id)

            print(f"\n{CYAN}{'=' * 60}{RESET}")
            print(f"{BOLD}{CYAN}💼 Job Details (ID: {job_id}){RESET}")
            print(f"{CYAN}{'=' * 60}{RESET}\n")

            if not job:
                print(f"{RED}✗ Job not found with ID: {job_id}{RESET}\n")
            else:
                print(f"{BOLD}Position:{RESET} {job['position']}")
                print(f"{BOLD}Company:{RESET} {job['company'] or 'N/A'}")
                print(f"{BOLD}Location:{RESET} {job['location'] or 'N/A'}")
                print(f"{BOLD}Job Type:{RESET} {job['job_type'] or 'N/A'}")
                print(f"{BOLD}Salary:{RESET} {job['salary'] or 'N/A'}")
                print(f"{BOLD}Status:{RESET} {job['status']}")
                print(f"{BOLD}Found Date:{RESET} {job['found_date']}")
                print(f"{BOLD}Email Date:{RESET} {job['email_date']}")
                print(f"{BOLD}Account:{RESET} {job['account_email']}")

                if job['application_link']:
                    print(f"\n{BOLD}Application Link:{RESET}")
                    print(f"{CYAN}{job['application_link']}{RESET}")

                if job['notes']:
                    print(f"\n{BOLD}Notes:{RESET}")
                    print(f"{job['notes']}")

            print(f"\n{CYAN}{'=' * 60}{RESET}\n")

        except Exception as e:
            self.logger.error(f"Error showing job details: {e}")
            print(f"\n{RED}✗ Error: {e}{RESET}\n")

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
