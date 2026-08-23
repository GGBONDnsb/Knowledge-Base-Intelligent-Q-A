<!--
云启科技知识库文档元数据

文档编号: YQ-TECH-LANGCHAIN-019
类别: 技术文档类
来源: langchain 官方文档
获取方式: GitHub/官网下载
更新日期: 2026-08-18
权限级别: 全员
负责人: 资料管理组
状态: 已清洗
原始来源: https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/middleware/overview.mdx
许可证: MIT
-->
Middleware provides a way to more tightly control what happens inside the agent. Middleware is useful for the following:

- Tracking agent behavior with logging, analytics, and debugging.
- Transforming prompts, [tool selection](/oss/langchain/middleware/built-in#llm-tool-selector), and output formatting.
- Adding [retries](/oss/langchain/middleware/built-in#tool-retry), [fallbacks](/oss/langchain/middleware/built-in#model-fallback), and early termination logic.
- Applying [rate limits](/oss/langchain/middleware/built-in#model-call-limit), guardrails, and [PII detection](/oss/langchain/middleware/built-in#pii-detection).

Add middleware by passing them to @[`create_agent`]:

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware, HumanInTheLoopMiddleware

agent = create_agent(
    model="gpt-5.5",
    tools=[...],
    middleware=[
        SummarizationMiddleware(...),
        HumanInTheLoopMiddleware(...)
    ],
)
```

Add middleware by passing them to `createAgent`:

```typescript
import {
  createAgent,
  summarizationMiddleware,
  humanInTheLoopMiddleware,
} from "langchain";

const agent = createAgent({
  model: "gpt-5.5",
  tools: [...],
  middleware: [summarizationMiddleware, humanInTheLoopMiddleware],
});
```

## The agent loop

The core agent loop involves calling a model, letting it choose tools to execute, and then finishing when it calls no more tools:

<img
    src="/oss/images/core_agent_loop.png"
    alt="Core agent loop diagram"
    style={{height: "200px", width: "auto", justifyContent: "center"}}
    className="rounded-lg block mx-auto"
/>

Middleware exposes hooks before and after each of those steps:

<img
    src="/oss/images/middleware_final.png"
    alt="Middleware flow diagram"
    style={{height: "300px", width: "auto", justifyContent: "center"}}
    className="rounded-lg mx-auto"
/>

## Use middleware inside a LangGraph workflow

Middleware is not a separate runtime: hooks run inside the compiled [LangGraph](/oss/langgraph/overview) that @[`create_agent`] returns. You can drop the whole agent (middleware and all) into a larger @[StateGraph] as a node or subgraph, and every middleware hook continues to run.

Reach for this pattern when the surrounding topology is more than a standard "loop until done": classifying input before routing to one of several agents, fanning out work in parallel, or stitching agent calls together with deterministic steps.

`HumanInTheLoopMiddleware` matches against each tool's `.name`.

`@tool`-decorated functions take their name from the function, so the key below is `"send_email"`.

```python
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.graph import START, StateGraph

# Assumes read_email, send_email, classify_node, and route are defined elsewhere.
email_agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[read_email, send_email],
    middleware=[HumanInTheLoopMiddleware(interrupt_on={"send_email": True})],
)

graph = (
    StateGraph(AgentState)
    .add_node("classify", classify_node)
    .add_node("email_agent", email_agent)
    .add_edge(START, "classify")
    .add_conditional_edges("classify", route)
    .compile()
)
```

The key matches the `name` you pass to `tool({...}, { name })`.

```typescript

// Assumes readEmail, sendEmail, classifyNode, and route are defined elsewhere.
// readEmail / sendEmail are registered with name: "read_email" / "send_email".
const emailAgent = createAgent({
  model: "claude-sonnet-4-6",
  tools: [readEmail, sendEmail],
  middleware: [humanInTheLoopMiddleware({ interruptOn: { send_email: true } })],
});

const graph = new StateGraph(AgentState)
  .addNode("classify", classifyNode)
  .addNode("emailAgent", emailAgent)
  .addEdge(START, "classify")
  .addConditionalEdges("classify", route)
  .compile();
```

The HITL interrupt, summarization, PII redaction, retries, and any custom hooks all travel with the agent node. See [Use subgraphs](/oss/langgraph/use-subgraphs) for the full set of composition patterns, including subgraph checkpointer scoping (per-invocation versus per-thread).

## Additional resources

        Explore built-in middleware for common use cases.
        Build your own middleware with hooks and decorators.
        Complete API reference for middleware.
        Provider-specific middleware for Anthropic, AWS, OpenAI, and more.
        Test your agents with LangSmith.
