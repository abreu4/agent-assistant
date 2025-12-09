"""Memory management system for conversation context."""
from typing import List, Optional, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from ..utils.config import config
from ..utils.logging import get_logger

logger = get_logger("memory")


class MemoryManager:
    """Manages conversation memory within model context limits."""

    def __init__(self):
        """Initialize memory manager."""
        self.strategy = config.get('agent.memory.strategy', 'sliding_window')
        self.max_messages = config.get('agent.memory.max_messages', 20)
        self.reserve_tokens = config.get('agent.memory.reserve_tokens', 1000)
        self.summarize_threshold = config.get('agent.memory.summarize_threshold', 0.8)

    def get_model_limits(self, model_id: str, tier: str) -> Tuple[int, int]:
        """
        Get context window and max output tokens for a model.

        Args:
            model_id: Model ID
            tier: 'local' or 'remote'

        Returns:
            Tuple of (context_window, max_output_tokens)
        """
        # Get model configuration
        if tier == 'local':
            local_config = config.get_llm_config('local')
            all_models = local_config.get('available_models', {})

            if isinstance(all_models, dict):
                # Search in all modes for local models
                models = []
                for mode_models in all_models.values():
                    if isinstance(mode_models, list):
                        models.extend(mode_models)
            else:
                models = all_models

        else:  # remote
            models = config.get_available_remote_models()

        # Find the model
        for model in models:
            if model.get('id') == model_id:
                context = model.get('context_window', 8192)
                max_output = model.get('max_output_tokens', 2048)
                logger.debug(f"Found limits for {model_id}: {context}/{max_output}")
                return context, max_output

        # Default fallback
        logger.warning(f"No context limits found for {model_id}, using defaults")
        return 8192, 2048

    def estimate_tokens(self, messages: List[BaseMessage]) -> int:
        """
        Estimate token count for messages (rough approximation).

        Uses ~1.3 tokens per word as estimation.

        Args:
            messages: List of messages

        Returns:
            Estimated token count
        """
        total_words = 0
        for msg in messages:
            if hasattr(msg, 'content') and msg.content:
                total_words += len(str(msg.content).split())

            # Add tokens for tool calls
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    total_words += 50  # Rough estimate per tool call

        # 1.3 tokens per word (average for English)
        return int(total_words * 1.3)

    def truncate_messages(
        self,
        messages: List[BaseMessage],
        context_window: int,
        max_output_tokens: int
    ) -> List[BaseMessage]:
        """
        Truncate messages to fit within context window.

        Strategy depends on configured memory strategy:
        - sliding_window: Keep most recent N messages
        - summarize: Summarize old messages (not yet implemented)
        - hybrid: Combination of both

        Args:
            messages: List of messages
            context_window: Model's context window size
            max_output_tokens: Model's max output tokens

        Returns:
            Truncated message list
        """
        if not messages:
            return messages

        # Calculate available tokens for input
        available_tokens = context_window - max_output_tokens - self.reserve_tokens

        if available_tokens <= 0:
            logger.error(f"Invalid context calculation: window={context_window}, "
                        f"output={max_output_tokens}, reserve={self.reserve_tokens}")
            return messages[:1]  # Keep at least the first message

        # Estimate current token usage
        current_tokens = self.estimate_tokens(messages)

        # If we're within limits, return as-is
        if current_tokens <= available_tokens:
            return messages

        logger.info(f"Memory exceeds limit: {current_tokens} > {available_tokens} tokens")

        # Apply strategy
        if self.strategy == 'sliding_window':
            return self._sliding_window_truncate(messages, available_tokens)
        elif self.strategy == 'summarize':
            logger.warning("Summarization not yet implemented, using sliding window")
            return self._sliding_window_truncate(messages, available_tokens)
        elif self.strategy == 'hybrid':
            logger.warning("Hybrid strategy not yet implemented, using sliding window")
            return self._sliding_window_truncate(messages, available_tokens)
        else:
            logger.warning(f"Unknown strategy '{self.strategy}', using sliding window")
            return self._sliding_window_truncate(messages, available_tokens)

    def _sliding_window_truncate(
        self,
        messages: List[BaseMessage],
        target_tokens: int
    ) -> List[BaseMessage]:
        """
        Truncate using sliding window - keep most recent messages.

        Always preserves:
        1. System messages
        2. Most recent user-assistant pairs

        Args:
            messages: List of messages
            target_tokens: Target token count

        Returns:
            Truncated messages
        """
        # Separate system messages from conversation
        system_msgs = [msg for msg in messages if isinstance(msg, SystemMessage)]
        conversation = [msg for msg in messages if not isinstance(msg, SystemMessage)]

        # Start with system messages
        result = system_msgs.copy()
        system_tokens = self.estimate_tokens(system_msgs)

        # Add conversation messages from most recent
        remaining_tokens = target_tokens - system_tokens
        conversation_reversed = list(reversed(conversation))

        for msg in conversation_reversed:
            msg_tokens = self.estimate_tokens([msg])

            if msg_tokens <= remaining_tokens:
                result.insert(len(system_msgs), msg)  # Insert after system messages
                remaining_tokens -= msg_tokens
            else:
                # Can't fit more messages
                break

        # Ensure result is in correct order
        final_result = system_msgs + list(reversed([m for m in result if m not in system_msgs]))

        # Log truncation
        removed_count = len(messages) - len(final_result)
        if removed_count > 0:
            logger.info(f"Truncated {removed_count} messages using sliding window")
            logger.debug(f"Kept {len(final_result)} messages (~{self.estimate_tokens(final_result)} tokens)")

        return final_result

    def manage_context(
        self,
        messages: List[BaseMessage],
        model_id: str,
        tier: str
    ) -> List[BaseMessage]:
        """
        Main entry point for memory management.

        Args:
            messages: Current message history
            model_id: Model being used
            tier: 'local' or 'remote'

        Returns:
            Managed message list that fits within context
        """
        # Get model limits
        context_window, max_output_tokens = self.get_model_limits(model_id, tier)

        logger.debug(f"Managing memory for {model_id}: "
                    f"context={context_window}, max_output={max_output_tokens}")

        # Apply message limit if configured
        if self.max_messages and len(messages) > self.max_messages:
            # Keep system messages + recent N messages
            system_msgs = [msg for msg in messages if isinstance(msg, SystemMessage)]
            other_msgs = [msg for msg in messages if not isinstance(msg, SystemMessage)]
            messages = system_msgs + other_msgs[-self.max_messages:]
            logger.info(f"Limited to {len(messages)} messages (max_messages={self.max_messages})")

        # Truncate to fit context window
        return self.truncate_messages(messages, context_window, max_output_tokens)
