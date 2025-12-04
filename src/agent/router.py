"""Intelligent routing system for hybrid LLM architecture."""
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from .llm_system import HybridLLMSystem, ModelTier
from ..utils.config import config
from ..utils.logging import get_logger

logger = get_logger("router")


class TaskComplexity(str, Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    CODE = "code"


class TaskClassification(BaseModel):
    """Classification of task complexity and requirements."""

    complexity: TaskComplexity = Field(
        description="Task complexity level: simple, medium, complex, or code"
    )
    reasoning: str = Field(
        description="Brief explanation for the classification"
    )
    requires_tools: bool = Field(
        description="Whether the task requires external tools (search, calculator, etc.)"
    )
    estimated_tokens: int = Field(
        description="Estimated output tokens needed (rough estimate)"
    )


class Router:
    """Intelligent routing system for hybrid LLM architecture."""

    def __init__(self, llm_system: HybridLLMSystem):
        """
        Initialize router.

        Args:
            llm_system: Hybrid LLM system instance
        """
        self.llm_system = llm_system

        self.classification_prompt = ChatPromptTemplate.from_messages([
            ("system", """Classify the user's request into one of these complexity levels:

**Complexity Levels:**
- **simple**: Greetings, basic facts, simple definitions, quick questions (< 100 tokens output)
- **medium**: General questions, explanations, summaries, basic analysis (100-500 tokens)
- **complex**: Deep analysis, multi-step reasoning, creative writing, detailed reports (> 500 tokens)
- **code**: Programming tasks, debugging, technical implementation, code generation

**Consider:**
1. Does this need external tools? (web search, calculator, file access, etc.)
2. How many output tokens will likely be needed?
3. Does it require advanced reasoning or just fact recall?

Respond with your classification."""),
            ("human", "{query}")
        ])

    async def classify_task(self, query: str) -> TaskClassification:
        """
        Classify task complexity using fast local LLM.

        Args:
            query: User query to classify

        Returns:
            Task classification

        Raises:
            Exception: If classification fails
        """
        try:
            classifier = self.llm_system.get_classifier()

            chain = self.classification_prompt | classifier.with_structured_output(
                TaskClassification
            )

            classification = await chain.ainvoke({"query": query})
            logger.info(f"Classified query as: {classification.complexity.value}")

            return classification

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, using fallback")
            return self._simple_classify(query)

    def _simple_classify(self, query: str) -> TaskClassification:
        """
        Fallback simple keyword-based classification.

        Args:
            query: User query

        Returns:
            Task classification
        """
        query_lower = query.lower()
        length = len(query.split())

        # Simple patterns
        simple_keywords = ['hello', 'hi', 'hey', 'what is', 'define', 'who is', 'when was']
        if length < 10 and any(kw in query_lower for kw in simple_keywords):
            complexity = TaskComplexity.SIMPLE
            estimated_tokens = 50

        # Code patterns
        elif any(kw in query_lower for kw in ['code', 'function', 'debug', 'implement', 'script', 'program']):
            complexity = TaskComplexity.CODE
            estimated_tokens = 300

        # Complex patterns
        elif length > 50 or any(kw in query_lower for kw in ['analyze', 'explain in detail', 'compare', 'evaluate', 'design', 'create a']):
            complexity = TaskComplexity.COMPLEX
            estimated_tokens = 800

        # Default to medium
        else:
            complexity = TaskComplexity.MEDIUM
            estimated_tokens = 200

        # Check for tool requirements
        requires_tools = any(kw in query_lower for kw in [
            'search', 'find', 'look up', 'browse', 'calculate', 'run', 'execute', 'file'
        ])

        return TaskClassification(
            complexity=complexity,
            reasoning="Fallback keyword-based classification",
            requires_tools=requires_tools,
            estimated_tokens=estimated_tokens
        )

    def route(
        self,
        classification: TaskClassification,
        context_tokens: int = 0,
        force_model: str = None
    ) -> ModelTier:
        """
        Determine which model tier to use based on classification.

        Routing Strategy:
        1. Simple tasks → Local (fast, free)
        2. Medium tasks → Local first
        3. Complex reasoning → Remote (better quality)
        4. Code tasks → Local if no tools, else consider remote
        5. Long context (> 1000 tokens) → Remote
        6. Tool-heavy tasks → Remote (better reliability)

        Args:
            classification: Task classification
            context_tokens: Number of context tokens
            force_model: Override automatic routing - "local", "remote", or None for auto

        Returns:
            Model tier to use ('local' or 'remote')
        """
        # Check for force_model override (parameter takes precedence over config)
        force = force_model or config.get('llm.routing.force_model')
        if force in ['local', 'remote']:
            logger.info(f"Force model override: {force}")
            # Verify the forced model is available
            if force == 'local' and self.llm_system.is_local_available():
                return "local"
            elif force == 'remote' and self.llm_system.is_remote_available():
                return "remote"
            else:
                logger.warning(f"Forced model '{force}' not available, falling back to auto routing")

        total_tokens = classification.estimated_tokens + context_tokens

        # Check if local is available
        if not self.llm_system.is_local_available():
            logger.info("Local model not available, routing to remote")
            return "remote"

        # Check if remote is available
        if not self.llm_system.is_remote_available():
            logger.info("Remote model not available, routing to local")
            return "local"

        # Respect configuration preference
        prefer_local = config.prefer_local

        # Long context always goes to remote (better context handling)
        if total_tokens > 1000:
            logger.info(f"Long context ({total_tokens} tokens), routing to remote")
            return "remote"

        # Route based on complexity
        if classification.complexity == TaskComplexity.SIMPLE:
            logger.info("Simple task, routing to local")
            return "local"

        elif classification.complexity == TaskComplexity.CODE:
            # Code tasks: local is decent, but remote is better with tools
            if classification.requires_tools:
                logger.info("Code task with tools, routing to remote")
                return "remote"
            else:
                logger.info("Code task without tools, routing to local")
                return "local"

        elif classification.complexity == TaskComplexity.COMPLEX:
            # Complex reasoning: prefer remote for better quality
            logger.info("Complex task, routing to remote for better quality")
            return "remote"

        else:  # MEDIUM
            # Medium tasks: prefer local if configured, else remote
            if prefer_local:
                logger.info("Medium task, prefer_local=True, routing to local")
                return "local"
            else:
                logger.info("Medium task, prefer_local=False, routing to remote")
                return "remote"

    def should_escalate(self, current_tier: ModelTier, error: str) -> ModelTier:
        """
        Determine if we should escalate to a higher tier after failure.

        Args:
            current_tier: Current model tier that failed
            error: Error message

        Returns:
            New tier to try, or same if no escalation
        """
        if current_tier == "local" and self.llm_system.is_remote_available():
            logger.info("Escalating from local to remote after failure")
            return "remote"

        logger.warning("No higher tier available for escalation")
        return current_tier
