from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config= SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Generator (writes code) ---
    openai_api_key: str= ""
    generator_provider: str ="openai"
    generator_model: str= "gpt-4.1-nano"

    # --- Reviewer (critiques code, MUST differ in provider from generator) ---
    anthropic_api_key: str= ""
    reviewer_provider: str= "anthropic"
    reviewer_model: str= "claude-sonnet-4-6"

    # --- Orchestration loop ---
    max_iterations: int = 5 
    # Stop early if the reviewer approves twice in a row with nothing new, or flips a previous verdict without new evidence
    require_consecutive_approvals: int = 1

    # --- Sandbox ---
    sandbox_timeout_seconds: int = 15

    # --- MCP transport (stdio) ---
    mcp_server_cmd: str = "python"
    mcp_server_args: str = "-m mcp_server.server"
    mcp_call_timeout_seconds: int = 120

    # --- Standards retrieval ---
    coding_standard_path: str = str(PROJECT_ROOT / "standards" / "coding_standard.md")

    def validate_providers_distinct(self) -> None:
        if self.generator_provider.strip().lower() == self.reviewer_provider.strip().lower():
            raise ValueError(
                "ggenerator_provider and reviewer_provider must be different"
                f"Both are {self.generator_provider}"
            )


settings = Settings()
settings.validate_providers_distinct()