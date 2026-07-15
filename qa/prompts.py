RAG_SYSTEM_PROMPT = """You answer questions using only the provided document excerpts.
If the excerpts don't contain the answer, say so clearly instead of guessing.
Cite which excerpt number(s) support each claim."""


def build_user_prompt(question, chunks):
    excerpts = "\n\n".join(
        f"[Excerpt {i + 1}]\n{chunk.text}" for i, chunk in enumerate(chunks)
    )
    return f"Document excerpts:\n\n{excerpts}\n\nQuestion: {question}"
