# health_llm.py
from app.agent.llm import translate_and_summarize

r = translate_and_summarize(
    "Test Title",
    "Short summary text.",
    "Full article body for translation test."
)
print(r)
