"""typer CLI for video ASR pipeline."""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer

app = typer.Typer(help="Vision video ASR pipeline CLI")


@app.command()
def run(
    sources: Path = typer.Option(None, "--sources"),
    url: str = typer.Option(None, "--url"),
) -> None:
    """Run the pipeline for a sources.yaml or a single URL."""
    from vision_intelligence.video_asr.runner import run_cli_job
    asyncio.run(run_cli_job(sources_yaml=sources, url=url))


@app.command()
def status(job_id: str) -> None:
    """Show the status of all videos in a job."""
    from vision_intelligence.video_asr.runner import show_status
    asyncio.run(show_status(job_id))


@app.command()
def rerun(
    video_id: str,
    stages: str = typer.Option(None, "--stages"),
    from_stage: str = typer.Option(None, "--from-stage"),
) -> None:
    """Re-run a video from a given stage or specific stages."""
    from vision_intelligence.video_asr.runner import rerun_video
    asyncio.run(rerun_video(video_id, stages=stages, from_stage=from_stage))


@app.command()
def search(q: str, limit: int = 50) -> None:
    """Full-text search across transcript segments."""
    from vision_intelligence.video_asr.runner import search_fts
    asyncio.run(search_fts(q, limit=limit))


@app.command()
def export(
    format: str = typer.Option("jsonl", "--format"),
) -> None:
    """Export all transcript segments."""
    from vision_intelligence.video_asr.runner import export_all
    asyncio.run(export_all(format))


@app.command()
def download(
    sources: Path = typer.Option(None, "--sources"),
    url: str = typer.Option(None, "--url"),
    concurrency: int = typer.Option(3, "--concurrency"),
) -> None:
    """Download audio only (ingest stage) — no transcription."""
    from vision_intelligence.video_asr.runner import download_sources
    asyncio.run(download_sources(sources_yaml=sources, url=url, concurrency=concurrency))


if __name__ == "__main__":
    app()
