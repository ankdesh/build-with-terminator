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

    def __init__(self, knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR, profile_name: str = "legacy_mini"):
        self.knowledge_dir = Path(knowledge_dir).resolve()
        from .profile import DRCProfileManager
        self.profile = DRCProfileManager().get_profile(profile_name)

    def load_documents(self) -> list[KnowledgeDocument]:
        """Load Markdown and supply the canonical API document exactly once."""
        if not self.knowledge_dir.exists():
            raise DRCConfigurationError(
                f"Knowledge directory does not exist: {self.knowledge_dir}"
            )

        md_files = sorted(self.knowledge_dir.glob("*.md"))
        documents: list[KnowledgeDocument] = []
        from .api_reference import render_api_reference
        reference = render_api_reference()

        for md_file in md_files:
            try:
                # This reserved document is generated from tested package code.
                # A custom directory cannot replace it with stale API guidance.
                content = reference if md_file.name == 'klayout_api_patterns.md' else md_file.read_text(encoding="utf-8")
                replacements = {
                    "{{M1_LAYER}}": str(self.profile.layers["M1"][0]),
                    "{{V1_LAYER}}": str(self.profile.layers["V1"][0]),
                    "{{PROFILE}}": self.profile.name,
                }
                for token, value in replacements.items():
                    content = content.replace(token, value)
                if md_file.name == "asap7_rules_guide.md":
                    content += "\n" + self._technology_facts()
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
                        content=content if md_file.name == 'klayout_api_patterns.md' else content.strip(),
                    )
                )
            except OSError as e:
                raise DRCConfigurationError(
                    f"Failed to read knowledge file '{md_file}': {e}"
                ) from e

        if not any(doc.filename == 'klayout_api_patterns.md' for doc in documents):
            documents.append(KnowledgeDocument('KLayout Python API: layout repair and hierarchy',
                                               'klayout_api_patterns.md', reference))
        return sorted(documents, key=lambda doc: (doc.filename != 'klayout_api_patterns.md', doc.filename))

    def format_as_text(self) -> str:
        """Format all loaded knowledge documents into a consolidated prompt context block."""
        docs = self.load_documents()

        lines = [
            "=== Domain Knowledge Base ===",
            self._technology_facts(),
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

        return "\n".join(lines).rstrip('\n') + '\n'

    def _technology_facts(self):
        profile = self.profile
        layers = "; ".join(f"{name}={layer}/{datatype}" for name, (layer, datatype) in profile.layers.items())
        return (f"# ASAP7 Process Design Kit: active profile {profile.name}\n"
                f"Layers: {layers}\n"
                f"Profile DBU: {profile.dbu_um:.12g} um; manufacturing grid: {profile.manufacturing_grid_um:.12g} um. "
                "Read actual layout.dbu for conversions. Never infer physical layers from examples.\n"
                "Rule thresholds and units come from the active decoded deck context. "
                "No net ownership or electrical correctness is established. Preserve clean inputs.\n")
