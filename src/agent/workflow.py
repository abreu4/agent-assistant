"""LangGraph workflow for hybrid agent with intelligent routing."""
from typing import TypedDict, Literal, Optional, Annotated, Sequence
from operator import add

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from .llm_system import HybridLLMSystem, ModelTier
from .router import Router, TaskClassification
from .tools import get_agent_tools
from ..utils.config import config
from ..utils.logging import get_logger

logger = get_logger("workflow")


class AgentState(TypedDict):
    """State for the agent workflow."""

    messages: Annotated[Sequence[BaseMessage], add]
    query: str
    classification: Optional[TaskClassification]
    model_tier: Optional[ModelTier]
    model_used: str
    retry_count: int
    error: Optional[str]
    tool_calls_made: int
    force_model: Optional[str]  # Override: "local", "remote", or None
    remote_models_tried: list  # Track which remote models have been tried
    remote_retry_count: int  # Count of remote model retries


class HybridAgent:
    """LangGraph-based hybrid agent with intelligent routing."""

    def __init__(self):
        """Initialize the hybrid agent."""
        self.llm_system = HybridLLMSystem()
        self.router = Router(self.llm_system)
        self.tools = get_agent_tools()
        self.graph = None

        logger.info("HybridAgent initialized")

    async def initialize(self):
        """Initialize and warm up models."""
        logger.debug("Warming up models...")
        await self.llm_system.warmup()
        self.graph = self._build_graph()
        logger.debug("Agent ready")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("route", self._route_node)
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("tools", ToolNode(self.tools))

        # Set entry point
        workflow.set_entry_point("classify")

        # Define edges
        workflow.add_edge("classify", "route")
        workflow.add_edge("route", "agent")

        # Conditional edges from agent
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools",
                "end": END,
                "retry": "route",
                "error": END
            }
        )

        # Tools always go back to agent
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    async def _classify_node(self, state: AgentState) -> AgentState:
        """Classify the query for routing."""
        logger.debug(f"Classifying query: {state['query'][:50]}...")

        try:
            classification = await self.router.classify_task(state['query'])
            state["classification"] = classification

            logger.debug(
                f"Classification: {classification.complexity.value}, "
                f"tools={classification.requires_tools}, "
                f"tokens~{classification.estimated_tokens}"
            )

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            # Use fallback
            state["classification"] = self.router._simple_classify(state['query'])

        return state

    def _route_node(self, state: AgentState) -> AgentState:
        """Determine which model to use."""
        # Check if we're retrying after failure
        if state.get("retry_count", 0) > 0:
            logger.debug(f"Retry attempt {state['retry_count']}")

            current_tier = state.get("model_tier", "local")
            remote_retry_count = state.get("remote_retry_count", 0)

            # If current tier is remote and we haven't tried 3 models yet
            if current_tier == "remote" and remote_retry_count < 3:
                # Try next remote model
                logger.info(f"⚠️  Model failed, trying alternative remote model ({remote_retry_count + 1}/3)")
                state["model_tier"] = "remote"
                state["remote_retry_count"] = remote_retry_count + 1
            else:
                # Either we tried 3 remote models or current was local
                # Escalate to higher tier or fall back to local
                if current_tier == "remote":
                    logger.warning("⚠️  All remote models failed, falling back to local model")
                    state["model_tier"] = "local"
                else:
                    # Try escalating from local to remote
                    new_tier = self.router.should_escalate(current_tier, state.get("error", ""))
                    state["model_tier"] = new_tier

        else:
            # Normal routing
            context_tokens = sum(
                len(msg.content.split()) for msg in state.get("messages", [])
            )

            # Get force_model override if specified
            force_model = state.get("force_model")

            tier = self.router.route(
                state["classification"],
                context_tokens,
                force_model=force_model
            )
            state["model_tier"] = tier

        logger.debug(f"Routing to: {state['model_tier']}")
        return state

    async def _agent_node(self, state: AgentState) -> AgentState:
        """Execute query with selected model."""
        model_tier = state["model_tier"]

        try:
            # If using remote, potentially switch to a different remote model
            if model_tier == "remote":
                remote_models_tried = state.get("remote_models_tried", [])
                available_models = self.llm_system.get_available_remote_models()
                current_model = self.llm_system.get_current_remote_model()

                # If this is a retry and we've tried the current model, switch to next
                if state.get("retry_count", 0) > 0 and current_model in remote_models_tried:
                    # Find next untried model
                    for model in available_models:
                        if model['id'] not in remote_models_tried:
                            logger.info(f"🔄 Switching to: {model['name']}")
                            self.llm_system.switch_remote_model(model['id'])
                            current_model = model['id']
                            break

                # Track this model
                if current_model not in remote_models_tried:
                    remote_models_tried.append(current_model)
                    state["remote_models_tried"] = remote_models_tried

                # Find model name for logging
                model_info = next((m for m in available_models if m['id'] == current_model), None)
                model_display = model_info['name'] if model_info else current_model

                logger.debug(f"Using remote model: {model_display} ({len(remote_models_tried)}/3 tried)")

            logger.debug(f"Executing with {model_tier} model")

            # Get appropriate model
            model = self.llm_system.get_model(model_tier)

            # Bind tools to model
            model_with_tools = model.bind_tools(self.tools)

            # Invoke model
            messages = state.get("messages", [])
            if not messages:
                messages = [HumanMessage(content=state["query"])]

            response = await model_with_tools.ainvoke(messages)

            # Update state
            state["messages"] = messages + [response]

            # Track which specific model was used
            if model_tier == "remote":
                model_name = self.llm_system.get_current_remote_model()
                state["model_used"] = f"remote ({model_name})"
            else:
                # For local, track the actual model that was used
                local_model_name = self.llm_system._current_local_model or "unknown"
                state["model_used"] = f"local ({local_model_name})"

            state["error"] = None

            # Track tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                state["tool_calls_made"] = state.get("tool_calls_made", 0) + len(response.tool_calls)

            logger.debug(f"Execution successful with {model_tier}")

        except Exception as e:
            logger.error(f"Execution failed with {model_tier}: {e}")
            state["error"] = str(e)
            state["retry_count"] = state.get("retry_count", 0) + 1

        return state

    def _should_continue(self, state: AgentState) -> Literal["continue", "end", "retry", "error"]:
        """Determine next step based on agent output."""
        # Check for error
        if state.get("error"):
            retry_count = state.get("retry_count", 0)
            max_retries = config.get('agent.max_iterations', 10) // 2

            if retry_count < max_retries:
                logger.debug(f"Error encountered, will retry (attempt {retry_count + 1})")
                return "retry"
            else:
                logger.error(f"Max retries ({max_retries}) exceeded")
                return "error"

        # Check for tool calls
        messages = state.get("messages", [])
        if not messages:
            return "end"

        last_message = messages[-1]

        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Check iteration limit
            tool_calls_made = state.get("tool_calls_made", 0)
            max_iterations = config.get('agent.max_iterations', 10)

            if tool_calls_made >= max_iterations:
                logger.warning(f"Max tool calls ({max_iterations}) reached")
                return "end"

            logger.debug(f"Continuing to tools ({tool_calls_made}/{max_iterations})")
            return "continue"

        return "end"

    async def run(self, query: str, force_model: str = None) -> dict:
        """
        Run the agent with a query.

        Args:
            query: User query
            force_model: Override automatic routing - "local", "remote", or None for auto

        Returns:
            Result dict with messages, model_used, etc.
        """
        if not self.graph:
            await self.initialize()

        logger.debug(f"Running agent with query: {query[:100]}...")

        initial_state = {
            "messages": [],
            "query": query,
            "classification": None,
            "model_tier": None,
            "model_used": "",
            "retry_count": 0,
            "error": None,
            "tool_calls_made": 0,
            "force_model": force_model,
            "remote_models_tried": [],
            "remote_retry_count": 0
        }

        try:
            result = await self.graph.ainvoke(initial_state)

            logger.debug(
                f"Agent complete. Model: {result.get('model_used')}, "
                f"Tool calls: {result.get('tool_calls_made', 0)}"
            )

            return result

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {
                **initial_state,
                "error": str(e),
                "messages": [AIMessage(content=f"Error: {e}")]
            }

    def get_final_response(self, result: dict) -> str:
        """
        Extract final response from agent result.

        Args:
            result: Agent result dict

        Returns:
            Final response text
        """
        messages = result.get("messages", [])

        if not messages:
            if result.get("error"):
                return f"Error: {result['error']}"
            return "No response generated"

        # Get last AI message
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content

        return "No response generated"
