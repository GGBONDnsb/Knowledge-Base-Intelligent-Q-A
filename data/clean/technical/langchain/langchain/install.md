<!--
云启科技知识库文档元数据

文档编号: YQ-TECH-LANGCHAIN-006
类别: 技术文档类
来源: langchain 官方文档
获取方式: GitHub/官网下载
更新日期: 2026-08-18
权限级别: 全员
负责人: 资料管理组
状态: 已清洗
原始来源: https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/install.mdx
许可证: MIT
-->
To install the LangChain package:

    ```bash pip
    pip install -U langchain
    # Requires Python 3.10+
    ```

    ```bash uv
    uv add langchain
    # Requires Python 3.10+
    ```

    ```bash npm
    npm install langchain @langchain/core
    # Requires Node.js 22+
    ```

    ```bash pnpm
    pnpm add langchain @langchain/core
    # Requires Node.js 22+
    ```

    ```bash yarn
    yarn add langchain @langchain/core
    # Requires Node.js 22+
    ```

    ```bash bun
    bun add langchain @langchain/core
    # Requires Bun v1.0.0+
    ```

LangChain provides integrations to hundreds of LLMs and thousands of other integrations. These live in independent provider packages.

    ```bash pip
    # Installing the OpenAI integration
    pip install -U langchain-openai

    # Installing the Anthropic integration
    pip install -U langchain-anthropic
    ```
    ```bash uv
    # Installing the OpenAI integration
    uv add langchain-openai

    # Installing the Anthropic integration
    uv add langchain-anthropic
    ```

    ```bash npm
    # Installing the OpenAI integration
    npm install @langchain/openai
    # Installing the Anthropic integration
    npm install @langchain/anthropic
    ```

    ```bash pnpm
    # Installing the OpenAI integration
    pnpm install @langchain/openai
    # Installing the Anthropic integration
    pnpm install @langchain/anthropic
    ```

    ```bash yarn
    # Installing the OpenAI integration
    yarn add @langchain/openai
    # Installing the Anthropic integration
    yarn add @langchain/anthropic
    ```

    ```bash bun
    # Installing the OpenAI integration
    bun add @langchain/openai
    # Installing the Anthropic integration
    bun add @langchain/anthropic
    ```

See the [Integrations tab](/oss/integrations/providers/overview) for a full list of available integrations.

Now that you have LangChain installed, you can get started by following the [Quickstart guide](/oss/langchain/quickstart).

Set up [LangSmith](https://smith.langchain.com) tracing to debug your first LangChain app. Follow the [tracing quickstart](/langsmith/trace-with-langchain) to get started. We recommend you also set up [LangSmith Engine](/langsmith/engine) which monitors your traces, detects issues, and proposes fixes.
