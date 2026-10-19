"""Knowledge base loader for DRC domain guidelines.

Discovers and loads Markdown knowledge files from a directory, providing structured context
to guide LLM generation of layout repair scripts.
"""

from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_KNOWLEDGE_DIR, DRCConfigurationError


@dataclass(frozen=True)
class KnowledgeDocument:
    """A loaded knowledge base markdown file."""
    title: str
    filename: str
    content: str


class KnowledgeLoader:
    """Discovers and merges domain knowledge markdown documents."""

    def __init__(self, knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR):
        self.knowledge_dir = Path(knowledge_dir).resolve()

    def load_documents(self) -> list[KnowledgeDocument]:
        """Load all markdown files from the knowledge directory in deterministic order."""
        if not self.knowledge_dir.exists():
            raise DRCConfigurationError(
                f"Knowledge directory does not exist: {self.knowledge_dir}"
            )

        md_files = sorted(self.knowledge_dir.glob("*.md"))
        documents: list[KnowledgeDocument] = []

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                # Determine title from first H1 header or filename
                title = md_file.stem.replace("_", " ").title()
                for line in content.splitlines():
                    if line.startswith("# "):
                        title = line.lstrip("#").strip()
                        break

                documents.append(
                    KnowledgeDocument(
                        title=title,
                        filename=md_file.name,
                        content=content.strip(),
                    )
                )
            except OSError as e:
                raise DRCConfigurationError(
                    f"Failed to read knowledge file '{md_file}': {e}"
                ) from e

        return documents

    def format_as_text(self) -> str:
        """Format all loaded knowledge documents into a consolidated prompt context block."""
        docs = self.load_documents()

        lines = [
            "=== Domain Knowledge Base ===",
            f"Source Directory: {self.knowledge_dir.name}/",
            f"Documents Loaded: {len(docs)}",
            "",
        ]

        if not docs:
            lines.append("(No knowledge documents found in directory)")
            return "\n".join(lines)

        for doc in docs:
            lines.append(f"--- Document: {doc.title} ({doc.filename}) ---")
            lines.append(doc.content)
            lines.append("")

        return "\n".join(lines).strip()
