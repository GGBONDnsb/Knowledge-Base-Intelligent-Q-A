<!--
云启科技知识库文档元数据

文档编号: YQ-TECH-LANGCHAIN-027
类别: 技术文档类
来源: langchain 官方文档
获取方式: GitHub/官网下载
更新日期: 2026-08-18
权限级别: 全员
负责人: 资料管理组
状态: 已清洗
原始来源: https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/agentic-rag.mdx
许可证: MIT
-->
Build a [retrieval](/oss/deepagents/retrieval) agent with LangGraph that decides when to search a vector store versus answering the user directly.

LangChain offers built-in [agent](/oss/langchain/agents) implementations built on [LangGraph](/oss/langgraph/overview) primitives. When you need deeper customization, implement the agent directly in LangGraph. This tutorial walks through one retrieval-agent pattern.

In this tutorial you will:

1. Fetch and preprocess documents for retrieval.
2. Index those documents for semantic search and create a retriever tool for the agent.
3. Build an agentic RAG system that can decide when to use the retriever tool.

![Hybrid RAG](/images/langgraph-hybrid-rag-tutorial.png)

### Concepts

This tutorial covers the following concepts:

- [Retrieval](/oss/deepagents/retrieval) using
  - [document loaders](/oss/integrations/document_loaders),
  - [text splitters](/oss/integrations/splitters), [embeddings](/oss/integrations/embeddings), and
  - [vector stores](/oss/integrations/vectorstores)
- The LangGraph [Graph API](/oss/langgraph/graph-api), including state, nodes, edges, and conditional edges.

## Setup

Install the required packages and set your API keys:

```python
pip install -U langgraph langchain langchain-openai langchain-text-splitters beautifulsoup4 requests
```

```bash npm
npm install @langchain/langgraph @langchain/openai @langchain/textsplitters cheerio
```

```bash pnpm
pnpm install @langchain/langgraph @langchain/openai @langchain/textsplitters cheerio
```

```bash yarn
yarn add @langchain/langgraph @langchain/openai @langchain/textsplitters cheerio
```

```bash bun
bun add @langchain/langgraph @langchain/openai @langchain/textsplitters cheerio
```

### Set up LangSmith

RAG applications run retrieval and generation in sequence. When you run the examples in this tutorial, [LangSmith](/langsmith/observability) logs a trace for each query so you can inspect retrieval, tool calls, and model responses.
After you [sign up for LangSmith](https://smith.langchain.com), set your environment variables to start logging traces:

```shell
export LANGSMITH_TRACING="true"
export LANGSMITH_API_KEY="..."
```

Or, set them in Python:

```python
import getpass
import os

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = getpass.getpass()
```

If you are building a production agent, we also recommend you set up [LangSmith Engine](/langsmith/engine) which monitors your traces, detects issues, and proposes fixes.

## Preprocess documents

Use three posts from [Lilian Weng's blog](https://lilianweng.github.io/). Fetch page content with a minimal helper built on `requests` and `BeautifulSoup`.

Split the fetched documents into smaller chunks for indexing into the vector store:

Use three recent posts from [Lilian Weng's blog](https://lilianweng.github.io/). Fetch page content with a minimal helper built on `fetch` and `cheerio`:

Split the fetched documents into smaller chunks for indexing into the vector store:

## Create a retriever tool

Index the split documents into a vector store for semantic search.

Use an in-memory vector store and OpenAI embeddings:

Create a retriever tool using the `@tool` decorator:

Use an in-memory vector store and OpenAI embeddings, then create a retriever tool with LangChain's prebuilt `createRetrieverTool`:

## Generate a query or respond

With the retriever tool ready, start building the agent as a LangGraph graph. In the [Graph API](/oss/langgraph/graph-api), a graph is made of:

- **[State](/oss/langgraph/graph-api#state)**: Shared data that nodes read and update. This tutorial uses [`MessagesState`](/oss/langgraph/graph-api#messagesstate), which stores a `messages` list of [chat messages](/oss/langchain/messages).

- **[State](/oss/langgraph/graph-api#state)**: Shared data that nodes read and update. This tutorial uses [`MessagesAnnotation`](/oss/langgraph/graph-api#using-messages-in-your-graph), which stores a `messages` list of [chat messages](/oss/langchain/messages).

- **[Nodes](/oss/langgraph/graph-api#nodes)**: Functions that take the current state, run a step (for example, call a model or a tool), and return state updates.
- **[Edges](/oss/langgraph/graph-api#edges)**: Connections that define which node runs next, including [conditional edges](/oss/langgraph/graph-api#conditional-edges) that branch based on the state.

The first node is the agent decision point. Given the conversation so far, the model either answers the user directly or calls the retriever tool when the question needs blog context. That choice is what makes the system agentic rather than a fixed retrieve-then-generate pipeline: retrieval runs only when the model requests it.

Build a `generate_query_or_respond` node that calls the model on the current messages and binds the `retriever_tool` with `.bind_tools`:

**Output:**

```text wrap
================================== Ai Message ==================================

Hello! How can I help you today?
```

Ask a question that requires semantic search:

**Output:**

```text wrap
================================== Ai Message ==================================
Tool Calls:
retrieve_blog_posts (call_tYQxgfIlnQUDMdtAhdbXNwIM)
Call ID: call_tYQxgfIlnQUDMdtAhdbXNwIM
Args:
    query: types of reward hacking
```

Build a `generateQueryOrRespond` node that calls the model on the current messages and binds the `tools` with `.bindTools`:

```typescript

const input = { messages: [new HumanMessage("hello!")] };
const result = await generateQueryOrRespond(input);
console.log(result.messages[0]);
```

**Output:**

```text wrap
AIMessage {
  content: "Hello! How can I help you today?",
  tool_calls: []
}
```

Ask a question that requires semantic search:

```typescript
const input = {
  messages: [
    new HumanMessage("What does Lilian Weng say about types of reward hacking?")
  ]
};
const result = await generateQueryOrRespond(input);
console.log(result.messages[0]);
```

**Output:**

```text wrap
AIMessage {
  content: "",
  tool_calls: [
    {
      name: "retrieve_blog_posts",
      args: { query: "types of reward hacking" },
      id: "call_...",
      type: "tool_call"
    }
  ]
}
```

## Grade documents

A normal edge always sends the graph to the same next node. A [conditional edge](/oss/langgraph/graph-api#conditional-edges) chooses the next node at runtime by running a function over the current state. After retrieval, use that pattern to grade whether the documents are relevant: continue to answer generation if they are, or rewrite the question and try again if they are not.

Add a `grade_documents` routing function that uses a model with a structured output schema `GradeDocuments`. It returns the name of the next node based on the grading decision (`generate_answer` or `rewrite_question`):

Run this with irrelevant documents in the tool response:

Confirm that relevant documents are classified as such:

Add a `gradeDocuments` node that uses a model with structured output (Zod), and falls back to a plain yes or no response if structured parsing fails. Route with a conditional edge according to the result (`generate` or `rewrite`):

Run this with irrelevant documents in the tool response:

```typescript

const input = {
  messages: [
    new HumanMessage("What does Lilian Weng say about types of reward hacking?"),
    new AIMessage({
      tool_calls: [
        {
          type: "tool_call",
          name: "retrieve_blog_posts",
          args: { query: "types of reward hacking" },
          id: "1",
        }
      ]
    }),
    new ToolMessage({
      content: "meow",
      tool_call_id: "1",
    })
  ]
}
const result = await gradeDocuments(input);
```

Confirm that relevant documents are classified as such:

```typescript
const input = {
  messages: [
    new HumanMessage("What does Lilian Weng say about types of reward hacking?"),
    new AIMessage({
      tool_calls: [
        {
          type: "tool_call",
          name: "retrieve_blog_posts",
          args: { query: "types of reward hacking" },
          id: "1",
        }
      ]
    }),
    new ToolMessage({
      content: "reward hacking can be categorized into two types: environment or goal misspecification, and reward tampering",
      tool_call_id: "1",
    })
  ]
}
const result = await gradeDocuments(input);
```

## Rewrite the question

If the grader marks the retrieved documents as irrelevant, the graph should not answer from that context. Instead, rewrite the original user question into a clearer search query, then send control back to the generate-query-or-respond node so the agent can retrieve again. This retry loop is how the agent recovers from a weak first retrieval instead of stopping or hallucinating an answer.

Build the `rewrite_question` node to improve the original user question when retrieval misses:

**Output:**

```text wrap
What are the different types of reward hacking described by Lilian Weng, and how does she explain them?
```

Build the `rewrite` node to improve the original user question when retrieval misses:

```typescript

const input = {
  messages: [
    new HumanMessage("What does Lilian Weng say about types of reward hacking?"),
    new AIMessage({
      content: "",
      tool_calls: [
        {
          id: "1",
          name: "retrieve_blog_posts",
          args: { query: "types of reward hacking" },
          type: "tool_call"
        }
      ]
    }),
    new ToolMessage({ content: "meow", tool_call_id: "1" })
  ]
};

const response = await rewrite(input);
console.log(response.messages[0].content);
```

**Output:**

```text wrap
What are the different types of reward hacking described by Lilian Weng, and how does she explain them?
```

## Generate an answer

When the grader accepts the retrieved documents, the graph moves to answer generation. This node is the classic RAG step: combine the original user question with the tool message that holds the retrieved context, then ask the model to produce a grounded reply. Keep the prompt tight so the model answers from the provided context instead of inventing details.

Build the `generate_answer` node to produce the final reply from the question and retrieved context:

**Output:**

```text wrap
================================== Ai Message ==================================

Lilian Weng categorizes reward hacking into two types: environment or goal misspecification, and reward tampering. She considers reward hacking as a broad concept that includes both of these categories. Reward hacking occurs when an agent exploits flaws or ambiguities in the reward function to achieve high rewards without performing the intended behaviors.
```

Build the `generate` node to produce the final reply from the question and retrieved context:

```typescript

const input = {
  messages: [
    new HumanMessage("What does Lilian Weng say about types of reward hacking?"),
    new AIMessage({
      content: "",
      tool_calls: [
        {
          id: "1",
          name: "retrieve_blog_posts",
          args: { query: "types of reward hacking" },
          type: "tool_call"
        }
      ]
    }),
    new ToolMessage({
      content: "reward hacking can be categorized into two types: environment or goal misspecification, and reward tampering",
      tool_call_id: "1"
    })
  ]
};

const response = await generate(input);
console.log(response.messages[0].content);
```

**Output:**

```text wrap
Lilian Weng categorizes reward hacking into two types: environment or goal misspecification, and reward tampering. She considers reward hacking as a broad concept that includes both of these categories. Reward hacking occurs when an agent exploits flaws or ambiguities in the reward function to achieve high rewards without performing the intended behaviors.
```

## Assemble the graph

Assemble the nodes and edges into a complete graph:

- Start with `generate_query_or_respond` and determine whether to call `retriever_tool`.
- Route to the next step based on whether the model made tool calls:
  - If `generate_query_or_respond` returned `tool_calls`, call `retriever_tool` to retrieve context.
  - Otherwise, respond directly to the user.
- Grade retrieved document content for relevance to the question (`grade_documents`) and route to the next step:
  - If not relevant, rewrite the question using `rewrite_question` and then call `generate_query_or_respond` again.
  - If relevant, proceed to `generate_answer` and generate the final response using the @[ToolMessage] with the retrieved document context.

Visualize the graph:

<img
  src="/oss/images/agentic-rag-output.png"
  alt="Agentic RAG graph"
  style={{ height: "800px" }}
/>

- Start with `generateQueryOrRespond` and determine whether to call the retriever tool.
- Route to the next step using a conditional edge:
  - If `generateQueryOrRespond` returned `tool_calls`, call the retriever tool to retrieve context.
  - Otherwise, respond directly to the user.
- Grade retrieved document content for relevance to the question (`gradeDocuments`) and route to the next step:
  - If not relevant, rewrite the question using `rewrite` and then call `generateQueryOrRespond` again.
  - If relevant, proceed to `generate` and generate the final response using the @[ToolMessage] with the retrieved document context.

## Run the agentic RAG

Test the complete graph by running it with a question:

## See also

- [Retrieval](/oss/langchain/retrieval)
- [Graph API](/oss/langgraph/graph-api)
- [Agents](/oss/langchain/agents)
- [Build a RAG agent](/oss/deepagents/rag)
- [Build a semantic search engine](/oss/langchain/knowledge-base)
