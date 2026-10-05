from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .copilot import CopilotAdapter

REGISTRY = {
    "claude-code": ClaudeCodeAdapter,
    "codex": CodexAdapter,
    "copilot": CopilotAdapter,
}
