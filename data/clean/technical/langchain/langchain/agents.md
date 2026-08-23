<!--
云启科技知识库文档元数据

文档编号: YQ-TECH-LANGCHAIN-007
类别: 技术文档类
来源: langchain 官方文档
获取方式: GitHub/官网下载
更新日期: 2026-08-18
权限级别: 全员
负责人: 资料管理组
状态: 已清洗
原始来源: https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/agents.mdx
许可证: MIT
-->
An agent is a model calling tools in a loop until a given task is complete.

<img
    src="/oss/images/core_agent_loop.svg"
    alt="Core agent loop diagram"
    style={{height: "300px", width: "auto", justifyContent: "center"}}
    className="rounded-lg block mx-auto"
/>

A harness is everything around that loop: the prompt, the tools, and any middleware that shapes the model's behavior.

**Agent = Model + Harness**

The job of a harness: get the model the right context at the right time for the given task.

@[`create_agent`] is a highly configurable harness. At its simplest, you can create one with:

Building on that, you can configure the basics directly with the `model=`, `tools=`, and `system_prompt=` parameters. For more advanced capabilities, extend the harness with [middleware](#configure-the-harness).

[Deep Agents](/oss/deepagents/overview) builds on `create_agent` and comes with commonly useful capabilities already assembled, such as planning, file system tools, subagents, and memory. Use `create_agent` when you need to configure the harness yourself.

## Core components

<img
    src="/oss/images/agent_model_harness.svg"
    alt="Agent model and harness components diagram"
    style={{height: "280px", width: "auto", justifyContent: "center"}}
    className="rounded-lg block mx-auto"
/>

### Model

Pass a model identifier string (`"provider:model"`) or an initialized model instance to select the model for your agent. See [Models](/oss/langchain/models) for parameters, provider setup, and dynamic model selection.

### Tools

To provide the agent with tools, pass any Python callable, LangChain tool, or tool dict. See [Tools](/oss/langchain/tools) for tool definition, context access, and dynamic tool selection.

### System prompt

Shape how the agent approaches tasks. The system prompt parameter accepts a string or `SystemMessage`. For dynamic prompts at runtime, use [middleware](/oss/langchain/middleware).

### Structured output

Return a validated schema from the agent using `response_format=`. See [Structured output](/oss/langchain/structured-output) for strategies and examples.

### Agent state

Every agent manages its execution context through @[`AgentState`], a typed dictionary that holds the current conversation history and any custom fields your tools and middleware need.

The built-in field is:

| Field | Type | Description |
|-------|------|-------------|
| `messages` | `list[BaseMessage]` | The full conversation history for the current thread. Append-only: new messages are added, never replaced. |

`AgentState` is also the type signature for every node-style middleware hook (`before_model`, `after_model`, and similar). Hooks receive the current state and can return a dict of updates to merge back into it.

To add custom fields (for example, a `user_id` or a counter), subclass `AgentState` and pass the subclass to `create_agent` via `state_schema=`:

For full details, examples, and middleware-level state schemas, see [Short-term memory](/oss/langchain/short-term-memory#customizing-agent-memory) and [Custom middleware](/oss/langchain/middleware/custom#state-updates).

Every agent manages its execution context through an `AgentState` object that holds the current conversation history and any custom fields your tools and middleware need.

The built-in field is:

| Field | Type | Description |
|-------|------|-------------|
| `messages` | `BaseMessage[]` | The full conversation history for the current thread. Append-only: new messages are added, never replaced. |

`AgentState` is also the type passed to every node-style middleware hook (`beforeModel`, `afterModel`, and similar). Hooks receive the current state and can return an object of updates to merge back into it.

To add custom fields, define a state schema on your middleware using `stateSchema` with a `StateSchema` or Zod object:

For full details, examples, and middleware-level state schemas, see [Short-term memory](/oss/langchain/short-term-memory#customizing-agent-memory) and [Custom middleware](/oss/langchain/middleware/custom#state-updates).

## Invocation

Trace each step of this loop, debug tool calls, and evaluate agent outputs with [LangSmith](https://smith.langchain.com). Follow the [tracing quickstart](/langsmith/trace-with-langchain) to get set up. We recommend you also set up [LangSmith Engine](/langsmith/engine) which monitors your traces, detects issues, and proposes fixes.

You can invoke an agent with a message. Behind the scenes that passes an update to the agent's [`State`](/oss/langgraph/graph-api#state). All agents include a [sequence of messages](/oss/langgraph/use-graph-api#messagesstate) in their state; to invoke the agent, pass a new message along with a `thread_id` so the agent can persist and resume conversation history:
You can invoke an agent with a message. Behind the scenes that passes an update to the agent's [`State`](/oss/langgraph/graph-api#state). All agents include a [sequence of messages](/oss/langgraph/use-graph-api#messagesvalue) in their state; to invoke the agent, pass a new message along with a `thread_id` so the agent can persist and resume conversation history:

Persisting conversation history with `thread_id` requires the agent to be configured with a [checkpointer](/oss/langchain/long-term-memory). When deployed on [LangSmith](/langsmith/deployment), a checkpointer is provisioned automatically. Locally, pass one explicitly, for example `create_agent(..., checkpointer=InMemorySaver())`.

If you also need to pass per-run configuration (such as a user ID, API keys, or feature flags) to tools and middleware, pass it as `context` alongside `config`. Define the shape of that data with `context_schema` and access it through `runtime.context`:

`thread_id` scopes the *conversation* (message history, checkpoints), while `context` carries *per-run* data your tools and middleware read at invocation time. Both are commonly passed together. See [tool context](/oss/langchain/tools#context) and [Runtime](/oss/langchain/runtime) for more.
If you also need to pass per-run configuration (such as a user ID, API keys, or feature flags) to tools and middleware, pass it as `context` alongside the config. Define the shape of that data with `contextSchema` and access it through `runtime.context`:

`thread_id` scopes the *conversation* (message history, checkpoints), while `context` carries *per-run* data your tools and middleware read at invocation time. Both are commonly passed together. See [tool context](/oss/langchain/tools#context) and [Runtime](/oss/langchain/runtime) for more.

## Streaming

`invoke` returns the final response at the end of a run. If an agent executes multiple tool calls, users often need progress updates before completion. Use streaming to surface intermediate messages and tool activity as they happen.

For streaming modes, event types, and UI patterns, see [Streaming](/oss/langchain/streaming).

## Configure the harness

`create_agent` is highly extensible. Middleware is the primitive for customization: each piece handles one concern, hooks into the agent loop at the right moment, and composes freely with any other. Take exactly what your use case needs and skip the rest.

Common patterns are prebuilt as first-class middleware. You can build anything else as [custom middleware](/oss/langchain/middleware/custom).

<img
    src="/oss/images/agent_harness_capabilities.svg"
    alt="Agent harness capabilities by category"
    style={{height: "300px", width: "auto", justifyContent: "center"}}
    className="rounded-lg block mx-auto"
/>

As agents take on complex work, they need support across a few key areas. The middleware ecosystem provides:

    Tools, filesystem, sandboxes, and code execution
    Summarization, memory, skills, and prompt caching
    Todo lists and subagents for parallel, isolated work
    Retries, fallbacks, and call limits
    PII detection and content controls
    Human-in-the-loop approval before high-impact actions

`create_deep_agent` pre-assembles this stack for long-running coding and research tasks (filesystem, summarization, subagents, and prompt caching included by default). See [Deep Agents](/oss/deepagents/harness) for the full prebuilt harness.

### Execution environment

Agents are especially useful when they can take action rather than just generate text. The execution environment gives the agent a workspace: tools it can call, a filesystem for reading and writing files across turns, and code execution for running scripts or shell commands.

See @[`FilesystemMiddleware`], [Sandboxes](/oss/deepagents/sandboxes), [Interpreters](/oss/deepagents/interpreters).

This example imports from the `deepagents` package. Install it with:

  ```bash pip
  pip install deepagents
  ```

  ```bash uv
  uv add deepagents
  ```
  ```bash npm
  npm install deepagents
  ```

  ```bash yarn
  yarn add deepagents
  ```

  ```bash pnpm
  pnpm add deepagents
  ```

### Context management

Every model call has a fixed context window. As an agent runs, that window fills with accumulating history, tool results, and intermediate steps. Summarization compresses history before overflow hits; memory loads persistent instructions at startup so knowledge carries across sessions; skills surface domain knowledge on demand rather than loading everything upfront.

See @[`SummarizationMiddleware`], @[`MemoryMiddleware`], [Skills](/oss/langchain/multi-agent/skills), [Context engineering](/oss/deepagents/context-engineering).

This example imports from the `deepagents` package. Install it with:

  ```bash pip
  pip install deepagents
  ```

  ```bash uv
  uv add deepagents
  ```
  ```bash npm
  npm install deepagents
  ```

  ```bash yarn
  yarn add deepagents
  ```

  ```bash pnpm
  pnpm add deepagents
  ```

### Planning and delegation

Complex tasks often exceed what one context window can handle. Delegation lets the main agent break work into pieces, hand them to subagents that each run in their own isolated context, and stay focused on coordination rather than execution. Work can run in parallel; the main agent's context stays clean.

See [Subagents](/oss/langchain/multi-agent/subagents).

This example imports from the `deepagents` package. Install it with:

  ```bash pip
  pip install deepagents
  ```

  ```bash uv
  uv add deepagents
  ```
  ```bash npm
  npm install deepagents
  ```

  ```bash yarn
  yarn add deepagents
  ```

  ```bash pnpm
  pnpm add deepagents
  ```

### Name your agent

Optionally use an identifier for the agent. This is especially useful when embedding the agent as a subgraph in [multi-agent](/oss/langchain/multi-agent) systems.

### Fault tolerance

Agents in production encounter failures that rarely appear in development: rate limits, model timeouts, transient API errors. Fault tolerance middleware handles these at the infrastructure level so your tools and business logic don't need try/catch around every call.

See @[`ModelRetryMiddleware`], @[`ToolRetryMiddleware`], [Prebuilt middleware](/oss/langchain/middleware/built-in).

See @[`modelRetryMiddleware`], @[`toolRetryMiddleware`], [Prebuilt middleware](/oss/langchain/middleware/built-in).

### Guardrails

Some policies can't live in a prompt—they need to be enforced deterministically regardless of what the model does. Guardrails intercept data as it flows through the agent loop, applying compliance rules or content policies before tool results reach the model's context.

See @[`PIIMiddleware`], [Prebuilt middleware](/oss/langchain/middleware/built-in).

See @[`piiMiddleware`], [Prebuilt middleware](/oss/langchain/middleware/built-in).

### Steering

Full autonomy isn't always appropriate. Steering lets you place humans at specific decision points—before destructive writes, expensive API calls, or anything requiring judgment—without restructuring your agent. The agent pauses and waits; a human approves, edits, or rejects; execution continues.

See @[`HumanInTheLoopMiddleware`], [Human-in-the-loop](/oss/langchain/human-in-the-loop).

See @[`humanInTheLoopMiddleware`], [Human-in-the-loop](/oss/langchain/human-in-the-loop).

### Middleware resources

    How the middleware stack works and when hooks fire
    Full reference with configuration examples
    Write your own hooks for business logic, PII scrubbing, and more
