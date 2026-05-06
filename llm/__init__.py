from dotenv import load_dotenv

# override=True: .env is authoritative. Avoids the trap where stale shell
# exports (e.g. an OPENAI_API_KEY from a prior session in ~/.zshrc) silently
# shadow the values in the local .env file.
load_dotenv(override=True)

from llm.base import LLMClient, LLMResponse  # noqa: E402

__all__ = ["LLMClient", "LLMResponse"]
