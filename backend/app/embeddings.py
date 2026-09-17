from __future__ import annotations

from typing import TYPE_CHECKING
from sentence_transformers import SentenceTransformer

if TYPE_CHECKING:
    from app.models import GraphNode

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load sentence-transformers model as a worker/process singleton."""
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    """Embed a single query string for request-time search."""
    model = get_embedding_model()
    return model.encode(text, show_progress_bar=False).tolist()


def embed_texts(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Batch-embed a list of strings."""
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    return [e.tolist() for e in embeddings]


def build_node_embedding_text(node: GraphNode) -> str:
    """Construct an information-rich representation of a GraphNode for embedding."""
    parts = [f"{node.node_type} {node.name}"]
    if node.qualified_name:
        parts.append(f"defined in {node.qualified_name}")
    if node.signature:
        parts.append(f"signature: {node.signature}")
    if node.docstring:
        parts.append(f"docstring: {node.docstring}")
    return "\n".join(parts)
