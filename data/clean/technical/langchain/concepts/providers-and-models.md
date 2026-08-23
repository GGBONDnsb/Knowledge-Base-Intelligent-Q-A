<!--
云启科技知识库文档元数据

文档编号: YQ-TECH-LANGCHAIN-003
类别: 技术文档类
来源: langchain 官方文档
获取方式: GitHub/官网下载
更新日期: 2026-08-18
权限级别: 全员
负责人: 资料管理组
状态: 已清洗
原始来源: https://github.com/langchain-ai/docs/blob/main/src/oss/concepts/providers-and-models.mdx
许可证: MIT
-->
LangChain gives you a single, unified API to work with models from any provider. Install a provider package, pick a model name, and start building—the same code works whether you use OpenAI, Anthropic, Google, or any other supported provider.

```mermaid
graph LR
    subgraph "Your code"
        A["LangChain API<br/>(invoke, stream, bind_tools)"]
    end

    subgraph "Providers"
        B["OpenAI"]
        C["Anthropic"]
        D["Google"]
        E["AWS Bedrock"]
        F["...and more"]
    end

    A --> B
    A --> C
    A --> D
    A --> E
    A --> F

    classDef code fill:#E5F4FF,stroke:#006DDD,stroke-width:2px,color:#030710
    classDef provider fill:#EBD0F0,stroke:#885270,stroke-width:2px,color:#441E33

    class A code
    class B,C,D,E,F provider
```

## One API for any model

Every LangChain chat model, regardless of provider, implements the same interface. This means you can:

- **Swap providers** without rewriting application logic
- **Compare models** side-by-side with identical code
- **Use advanced features** like [tool calling](/oss/langchain/tools), [structured output](/oss/langchain/structured-output), and [streaming](/oss/langchain/streaming) across all providers

```python
from langchain.chat_models import init_chat_model

openai_model = init_chat_model("openai:gpt-5.5")
anthropic_model = init_chat_model("anthropic:claude-opus-4-8")
google_model = init_chat_model("google-genai:gemini-3.1-pro-preview")

for model in [openai_model, anthropic_model, google_model]:
    response = model.invoke("Explain quantum computing in one sentence.")
    print(response.text)
```

```typescript

const openaiModel = await initChatModel("openai:gpt-5.5");
const anthropicModel = await initChatModel("anthropic:claude-opus-4-8");
const googleModel = await initChatModel("google-genai:gemini-3.1-pro-preview");

for (const model of [openaiModel, anthropicModel, googleModel]) {
    const response = await model.invoke("Explain quantum computing in one sentence.");
    console.log(response.text);
}
```

## What is a provider?

A **provider** is a company or platform that hosts AI models and exposes them through an API. Examples include OpenAI, Anthropic, Google, and AWS Bedrock.

In LangChain, each provider has a dedicated **integration package** (for example `langchain-openai`, `langchain-anthropic`) that implements the standard LangChain interface for that provider's models. This means:

- **Dedicated packages** for each provider with proper versioning and dependency management
- **Provider-specific features** are available when you need them (for example OpenAI's Responses API, Anthropic's extended thinking)
- **Automatic API key handling** through environment variables

```shell
uv add langchain-openai       # For OpenAI models
uv add langchain-anthropic    # For Anthropic models
uv add langchain-google-genai # For Google models
```

```bash
npm install @langchain/openai       # For OpenAI models
npm install @langchain/anthropic    # For Anthropic models
npm install @langchain/google-genai # For Google models
```

For a full list of provider packages, see the [integrations page](/oss/integrations/providers/overview).

## Find model names

Each provider supports specific model names that you pass when initializing a chat model. There are two ways to specify a model:

    ```python Provider prefix format
    from langchain.chat_models import init_chat_model

    model = init_chat_model("openai:gpt-5.5")
    ```

    ```python Direct class instantiation
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(model="gpt-5.5")
    ```

    ```typescript Provider prefix format

    const model = await initChatModel("openai:gpt-5.5");
    ```

    ```typescript Direct class instantiation

    const model = new ChatOpenAI({ model: "gpt-5.5" });
    ```

When using @[`init_chat_model`] with the `provider:model` format, LangChain automatically resolves the provider and loads the correct integration package. You can also omit the provider prefix if the model name is unambiguous (e.g., `"gpt-5.5"` resolves to OpenAI).

To find available model names for a provider, refer to the provider's own documentation. Here are some popular providers:

| Provider | Where to find model names |
| :--- | :--- |
| [OpenAI](/oss/integrations/providers/openai) | [OpenAI models page](https://platform.openai.com/docs/models) |
| [Anthropic](/oss/integrations/providers/anthropic) | [Anthropic models page](https://docs.anthropic.com/en/docs/about-claude/models) |
| [Google](/oss/integrations/providers/google) | [Google AI models page](https://ai.google.dev/gemini-api/docs/models) |
| [AWS Bedrock](/oss/integrations/providers/aws) | [Bedrock supported models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html) |
| [Ollama](/oss/integrations/providers/ollama) | [Ollama model library](https://ollama.com/library) |
| [Groq](/oss/integrations/providers/groq) | [Groq supported models](https://console.groq.com/docs/models) |

## Use new models immediately

Because LangChain provider packages pass model names directly to the provider's API, you can use new models the moment a provider releases them (no LangChain update required). Simply pass the new model name:

```python
model = init_chat_model("google_genai:gemini-mythos")
```

```typescript
const model = await initChatModel("google_genai:gemini-mythos");
```

New model names work immediately as long as your provider package version supports the API version the model requires. In most cases, model releases are backward-compatible and require no package update.

## Model capabilities

Different providers and models support different features.
For a list of the chat model integrations and their capabilities, see the [chat models integrations page](/oss/integrations/chat).

## Routers and proxies

**Routers** (also called proxies or gateways) give you access to models from multiple providers through a single API and credential. They can simplify billing, let you switch between models without changing integrations, and offer features like automatic fallbacks and load balancing.

| Provider | Integration | Description |
| :------- | :---------- | :---------- |
| [OpenRouter](https://openrouter.ai/) | [`ChatOpenRouter`](/oss/integrations/chat/openrouter) | Unified access to models from OpenAI, Anthropic, Google, Meta, and more |
| [FuturMix](https://futurmix.ai/) | [`ChatOpenAI`](https://futurmix.ai/) | Unified AI gateway for 22+ models with OpenAI-compatible API and 99.99% SLA |
| [LiteLLM](https://www.litellm.ai/) | [`ChatLiteLLM`](/oss/integrations/chat/litellm) | Unified interface for 100+ providers with routing, fallbacks, and spend tracking |

Routers are useful when you want to:

- **Access many providers** with a single API key and billing account
- **Switch models dynamically** without managing multiple provider credentials
- **Use fallback models** that automatically retry with a different model if the primary one fails

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("openrouter:anthropic/claude-sonnet-4-6")
response = model.invoke("Hello!")
```

```typescript

const model = await initChatModel("openrouter:anthropic/claude-sonnet-4-6");
const response = await model.invoke("Hello!");
```

## OpenAI-compatible endpoints

Many providers offer endpoints compatible with OpenAI's [Chat Completions API](https://platform.openai.com/docs/api-reference/chat). You can connect to these using [`ChatOpenAI`](/oss/integrations/chat/openai) with a custom `base_url`:

```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    base_url="https://your-provider.com/v1",
    api_key="your-api-key",
    model="provider-model-name",
)
```

```typescript

const model = new ChatOpenAI({
    configuration: { baseURL: "https://your-provider.com/v1" },
    apiKey: "your-api-key",
    model: "provider-model-name",
});
```

    `ChatOpenAI` targets [official OpenAI API specifications](https://github.com/openai/openai-openapi) only. Non-standard response fields from third-party providers are not extracted or preserved. Use a dedicated provider package or router when you need access to non-standard features.

## Next steps

        Learn how to use models: invoke, stream, batch, tool calling, and more.
        Browse all chat model integrations and their capabilities.
        See the full list of provider packages and integrations.
        Build agents that use models as their reasoning engine.
