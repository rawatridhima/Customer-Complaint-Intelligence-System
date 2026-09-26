from pathlib import Path

from app.core.config import settings


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LLMService:
    """Generate complaint-related content using versioned prompts."""

    def __init__(self) -> None:
        self.model = settings.LLM_MODEL
        self.prompt_version = settings.PROMPT_VERSION

    def _load_prompt(self, name: str) -> str:
        prompt_file = (
            PROMPTS_DIR
            / f"{name}_{self.prompt_version}.txt"
        )

        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_file}"
            )

        return prompt_file.read_text(encoding="utf-8")

    def build_summary_prompt(self, complaint_text: str) -> str:
        template = self._load_prompt("summarise")
        return template.format(
            complaint_text=complaint_text
        )

    def build_resolution_prompt(self, complaint_text: str) -> str:
        template = self._load_prompt("suggest_resolution")
        return template.format(
            complaint_text=complaint_text
        )

    def build_response_prompt(
        self,
        complaint_text: str,
        suggested_resolution: str,
    ) -> str:
        template = self._load_prompt("draft_response")
        return template.format(
            complaint_text=complaint_text,
            suggested_resolution=suggested_resolution,
        )

    def generate_summary(self, complaint_text: str) -> str:
        prompt = self.build_summary_prompt(complaint_text)
        return self._generate(prompt)

    def generate_resolution(self, complaint_text: str) -> str:
        prompt = self.build_resolution_prompt(complaint_text)
        return self._generate(prompt)

    def generate_response(
        self,
        complaint_text: str,
        suggested_resolution: str,
    ) -> str:
        prompt = self.build_response_prompt(
            complaint_text,
            suggested_resolution,
        )
        return self._generate(prompt)

    def _generate(self, prompt: str) -> str:
        """
        Temporary fallback until the LLM provider is configured.

        Keeping this behind one method means the provider can be
        replaced later without changing the rest of the application.
        """
        if not self.model or not settings.LLM_API_KEY.get_secret_value():
            return (
                "LLM is not configured yet. "
                "Please review this complaint manually."
            )

        # Provider-specific LLM call will be added here.
        raise NotImplementedError(
            "LLM provider integration is not configured yet."
        )


llm_service = LLMService()