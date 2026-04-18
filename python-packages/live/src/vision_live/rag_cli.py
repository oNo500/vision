"""RAG CLI — build / query / info / clear a per-plan talk-point index.

Usage:
    uv run python -m vision_live.rag_cli build <plan_id>
    uv run python -m vision_live.rag_cli query <plan_id> "<query text>"
    uv run python -m vision_live.rag_cli info <plan_id>
    uv run python -m vision_live.rag_cli clear <plan_id>

Source layout (relative to project root):
    data/talk_points/<plan_id>/scripts/*.md|txt
    data/talk_points/<plan_id>/competitor_clips/*.md|txt
    data/talk_points/<plan_id>/product_manual/*.md|txt
    data/talk_points/<plan_id>/qa_log/*.md|txt

Index layout:
    .rag/<plan_id>/chroma.sqlite3   (ChromaDB)
    .rag/<plan_id>/meta.json        (incremental build bookkeeping)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vision_live.rag_chunking import chunk_markdown

logger = logging.getLogger(__name__)

KNOWN_CATEGORIES = ("scripts", "competitor_clips", "product_manual", "qa_log")
ALLOWED_SUFFIXES = (".md", ".txt")

DATA_ROOT = Path("data/talk_points")
INDEX_ROOT = Path(".rag")


@dataclass
class SourceFile:
    """One file discovered under data/talk_points/<plan_id>/<category>/."""

    path: Path         # absolute path
    rel_path: str      # e.g. "scripts/opening.md"
    category: str      # one of KNOWN_CATEGORIES


# ---------------------------------------------------------------------------
# pure helpers (unit-tested)
# ---------------------------------------------------------------------------


def scan_sources(plan_root: Path) -> list[SourceFile]:
    """Walk data/talk_points/<plan_id>/ and return known-category files."""
    result: list[SourceFile] = []
    for category in KNOWN_CATEGORIES:
        cat_dir = plan_root / category
        if not cat_dir.is_dir():
            continue
        for path in sorted(cat_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            rel = path.relative_to(plan_root).as_posix()
            result.append(SourceFile(path=path, rel_path=rel, category=category))
    return result


def compute_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_meta(meta_path: Path) -> dict:
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _save_meta(meta_path: Path, data: dict) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def diff_sources(
    prev_meta_sources: dict,
    current_hashes: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Compare prev meta against current file hashes.

    Returns (added_or_changed, removed) rel_path lists.
    """
    added_or_changed = [
        rel for rel, h in current_hashes.items()
        if prev_meta_sources.get(rel, {}).get("sha256") != h
    ]
    removed = [rel for rel in prev_meta_sources if rel not in current_hashes]
    return added_or_changed, removed


# ---------------------------------------------------------------------------
# status (shared by CLI `info` and /live/plans/<id>/rag GET)
# ---------------------------------------------------------------------------


def get_plan_status(plan_id: str) -> dict:
    """Return the full status payload for a plan.

    Shape matches the HTTP contract of GET /live/plans/{plan_id}/rag/.
    """
    plan_root = DATA_ROOT / plan_id
    index_root = INDEX_ROOT / plan_id
    meta = load_meta(index_root / "meta.json")
    meta_sources = meta.get("sources", {})

    sources_on_disk: list[dict] = []
    current_hashes: dict[str, str] = {}
    if plan_root.is_dir():
        for src in scan_sources(plan_root):
            h = compute_file_hash(src.path)
            current_hashes[src.rel_path] = h
            indexed_entry = meta_sources.get(src.rel_path)
            sources_on_disk.append({
                "rel_path": src.rel_path,
                "category": src.category,
                "chunks": (indexed_entry or {}).get("chunks", 0),
                "sha256": h,
                "indexed": bool(indexed_entry and indexed_entry.get("sha256") == h),
            })

    indexed = bool(meta) and (index_root / "chroma.sqlite3").exists()
    added_or_changed, removed = diff_sources(meta_sources, current_hashes)

    return {
        "indexed": indexed,
        "dirty": bool(added_or_changed or removed),
        "chunk_count": meta.get("chunk_count", 0),
        "build_time": meta.get("build_time"),
        "file_count": len(sources_on_disk),
        "sources": sources_on_disk,
    }


# ---------------------------------------------------------------------------
# commands (integration path, imports chromadb + sentence-transformers lazily)
# ---------------------------------------------------------------------------


def cmd_build(plan_id: str) -> int:
    plan_root = DATA_ROOT / plan_id
    index_root = INDEX_ROOT / plan_id
    meta_path = index_root / "meta.json"

    if not plan_root.is_dir():
        print(f"error: {plan_root} does not exist", file=sys.stderr)
        return 2

    sources = scan_sources(plan_root)
    if not sources:
        print(f"warning: no files found under {plan_root}", file=sys.stderr)
        return 1

    current_hashes = {s.rel_path: compute_file_hash(s.path) for s in sources}
    prev_meta = load_meta(meta_path)
    prev_sources = prev_meta.get("sources", {})

    added_or_changed, removed = diff_sources(prev_sources, current_hashes)

    if not added_or_changed and not removed:
        print(f"up to date ({len(sources)} files, {prev_meta.get('chunk_count', 0)} chunks)")
        return 0

    # lazy imports keep rag_cli importable without these heavy deps
    import chromadb
    from sentence_transformers import SentenceTransformer

    index_root.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_root))
    collection_name = f"talkpoints_{plan_id}"
    collection = client.get_or_create_collection(
        collection_name, metadata={"hnsw:space": "cosine"},
    )

    # delete chunks belonging to removed or changed files
    to_purge = set(removed) | set(added_or_changed)
    if to_purge:
        collection.delete(where={"source": {"$in": list(to_purge)}})

    embedder = SentenceTransformer("BAAI/bge-base-zh-v1.5")

    new_sources_meta = dict(prev_sources)
    for rel in removed:
        new_sources_meta.pop(rel, None)

    total_chunks = 0
    for src in sources:
        if src.rel_path not in added_or_changed:
            total_chunks += prev_sources.get(src.rel_path, {}).get("chunks", 0)
            continue

        text = src.path.read_text(encoding="utf-8")
        chunks = chunk_markdown(text)
        if not chunks:
            new_sources_meta[src.rel_path] = {
                "sha256": current_hashes[src.rel_path], "chunks": 0,
            }
            continue

        ids = [f"{src.rel_path}::{i}" for i in range(len(chunks))]
        embeddings = embedder.encode(chunks, normalize_embeddings=True)
        metadatas = [
            {
                "id": ids[i],
                "source": src.rel_path,
                "category": src.category,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        collection.add(
            ids=ids,
            embeddings=[e.tolist() for e in embeddings],
            documents=chunks,
            metadatas=metadatas,
        )
        total_chunks += len(chunks)
        new_sources_meta[src.rel_path] = {
            "sha256": current_hashes[src.rel_path], "chunks": len(chunks),
        }
        print(f"  indexed {src.rel_path} → {len(chunks)} chunks")

    # recount chunks for unchanged files (not updated above)
    total_chunks = sum(meta.get("chunks", 0) for meta in new_sources_meta.values())

    _save_meta(meta_path, {
        "build_time": datetime.now(timezone.utc).isoformat(),
        "chunk_count": total_chunks,
        "embedder": "BAAI/bge-base-zh-v1.5",
        "sources": new_sources_meta,
    })

    print(f"done: {len(sources)} files, {total_chunks} chunks total")
    return 0


def cmd_query(plan_id: str, query_text: str, k: int = 5) -> int:
    from vision_live.rag import load_rag_for_plan

    rag = load_rag_for_plan(plan_id)
    if rag is None:
        print(f"error: no index for plan {plan_id} (run `build` first)", file=sys.stderr)
        return 2

    points = rag.query(query_text, [], k=k)
    if not points:
        print("(no hits above threshold)")
        return 0
    for p in points:
        snippet = p.text[:120].replace("\n", " ")
        print(f"[{p.source} #{p.chunk_index}] {snippet}")
    return 0


def cmd_info(plan_id: str) -> int:
    meta_path = INDEX_ROOT / plan_id / "meta.json"
    meta = load_meta(meta_path)
    if not meta:
        print(f"no index for plan {plan_id}")
        return 1
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


def cmd_clear(plan_id: str) -> int:
    index_root = INDEX_ROOT / plan_id
    if not index_root.exists():
        print(f"nothing to clear for plan {plan_id}")
        return 0
    shutil.rmtree(index_root)
    print(f"cleared {index_root}")
    return 0


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="rebuild the index for a plan")
    b.add_argument("plan_id")

    q = sub.add_parser("query", help="run a test query against the index")
    q.add_argument("plan_id")
    q.add_argument("text")
    q.add_argument("-k", type=int, default=5)

    i = sub.add_parser("info", help="print index metadata")
    i.add_argument("plan_id")

    c = sub.add_parser("clear", help="remove the index for a plan")
    c.add_argument("plan_id")

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "build":
        return cmd_build(args.plan_id)
    if args.cmd == "query":
        return cmd_query(args.plan_id, args.text, k=args.k)
    if args.cmd == "info":
        return cmd_info(args.plan_id)
    if args.cmd == "clear":
        return cmd_clear(args.plan_id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
