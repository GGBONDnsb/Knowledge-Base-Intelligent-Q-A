from openai import OpenAI

from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME

SYSTEM_PROMPT = (
    "你是企业知识库问答助手。请只根据提供的参考资料回答用户问题。\n"
    "回答要简洁、准确，不要编造参考资料之外的内容。\n"
    "如果参考资料不足以回答问题，请明确说明无法从知识库中找到答案。\n"
    "回答使用中文。"
)


def build_context(chunks: list[dict]) -> str:
    parts = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[{index}] 文档：{chunk['title']}\n"
            f"章节：{chunk['heading']}\n"
            f"内容：{chunk['content']}"
        )
    return "\n\n".join(parts)


def build_messages(question: str, chunks: list[dict]) -> list[dict]:
    context = build_context(chunks)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"问题：{question}\n\n参考资料：\n{context}"},
    ]


def call_deepseek(messages: list[dict]) -> str:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()
