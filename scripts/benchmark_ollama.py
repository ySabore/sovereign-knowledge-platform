"""
Benchmark Ollama HTTP latency (tags, embeddings, /api/generate).

Usage (from repo root, against host Ollama):
  python scripts/benchmark_ollama.py --iterations 10
  python scripts/benchmark_ollama.py --runs 2 --iterations 5 --prompt-mode long

``--prompt-mode long`` builds a RAG-sized prompt (rules + optional chat history + many
evidence lines) similar to ``app.services.rag.prompts.build_ollama_grounded_prompt``.
Suggested ``OLLAMA_HTTP_TIMEOUT_SECONDS`` uses **long**-prompt generate max + slack.

``--prompt-mode short`` uses a tiny prompt (legacy smoke test).

Models default from ``.env`` (``ANSWER_GENERATION_MODEL`` / ``EMBEDDING_MODEL``).
``OLLAMA_BASE_URL`` defaults to http://127.0.0.1:11434 when unset (host Ollama).
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _stats_ms(samples: list[float]) -> dict[str, float]:
    if not samples:
        return {}
    return {
        "n": float(len(samples)),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "mean_ms": statistics.mean(samples),
        "median_ms": statistics.median(samples),
        "stdev_ms": statistics.stdev(samples) if len(samples) > 1 else 0.0,
    }


FALLBACK_NO_EVIDENCE = (
    "I don't know based on the documents in this workspace."
)


def _synthetic_quote(seed: int, length: int = 380) -> str:
    """Repeatable pseudo-text ~length chars (simulates chunk quotes)."""
    base = (
        "The parties agree that confidential information disclosed under this agreement "
        "must be protected for five years. Remedies include injunctive relief. "
        "Governing law: Delaware. "
    )
    s = (base * ((length // len(base)) + 3))[:length]
    return f"{s} [segment {seed}]"


def build_rag_like_prompt(
    *,
    evidence_lines: int = 14,
    quote_chars: int = 360,
    history_turns: int = 2,
) -> str:
    """
    Mirror structure of ``build_ollama_grounded_prompt`` (no app import).
    Typical size: ~10–25k chars depending on evidence_lines / quote_chars.
    """
    rules = (
        "You are a precise knowledge assistant. Answer using ONLY the Evidence block below.\n"
        "Rules:\n"
        f"1. If the Evidence is insufficient, reply exactly: {FALLBACK_NO_EVIDENCE}\n"
        "2. Every factual claim must cite Evidence using inline markers [1], [2], … matching the Evidence numbers.\n"
        "3. Do not invent facts or use general knowledge beyond what Evidence supports.\n"
        "4. Be concise: a few sentences for simple questions; more only when Evidence requires it.\n"
        "5. When a source line includes a page number, you may write e.g. [1] or refer to page in the sentence.\n"
        "6. On the last line after your answer, output exactly one line: "
        "<confidence>high</confidence>, <confidence>medium</confidence>, or <confidence>low</confidence> "
        "based on how directly Evidence answers the question.\n"
    )
    history_lines: list[str] = []
    for t in range(history_turns):
        history_lines.append(
            f"User: Prior question {t} about indemnity and liability caps?\n"
            f"Assistant: Per [1] and [3], the cap is described in the MSA schedule; "
            f"citations must follow Evidence only. {'x' * 120}"
        )
    history_block = ""
    if history_lines:
        history_block = (
            "Recent conversation (context only; prefer Evidence over prior assistant replies):\n"
            + "\n".join(history_lines)
            + "\n\n"
        )
    ev: list[str] = []
    for i in range(evidence_lines):
        fn = "Vendor_MSA_Indemnity_Reference.pdf" if i % 2 == 0 else "Clause_Bank_Confidentiality_2025.pdf"
        page = str((i % 12) + 1)
        quote = _synthetic_quote(i, quote_chars)
        ev.append(f"[{i + 1}] {fn}, page {page}: {quote}")
    evidence_block = "\n".join(ev)
    query = (
        "Summarize the indemnity and confidentiality obligations that apply to our team, "
        "including time limits and governing law, with citations."
    )
    return (
        f"{rules}\n"
        f"{history_block}"
        f"Question: {query}\n\n"
        "Evidence:\n"
        f"{evidence_block}\n\n"
        "Respond with a concise answer, inline citations [n] as above, then the confidence line."
    )


def fmt_stats(label: str, s: dict[str, float]) -> str:
    return (
        f"{label:22}  n={int(s['n']):3}  min={s['min_ms']:8.1f}  "
        f"p50={s['median_ms']:8.1f}  mean={s['mean_ms']:8.1f}  "
        f"max={s['max_ms']:8.1f}  stdev={s['stdev_ms']:7.1f} ms"
    )


def main() -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(description="Benchmark Ollama endpoints")
    p.add_argument(
        "--url",
        default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        help="Ollama base URL (host: use 127.0.0.1:11434)",
    )
    p.add_argument(
        "--embedding-model",
        default=os.environ.get("EMBEDDING_MODEL", "nomic-embed-text"),
        help="Default: EMBEDDING_MODEL from .env",
    )
    p.add_argument(
        "--generate-model",
        default=os.environ.get("ANSWER_GENERATION_MODEL", "llama3.2"),
        help="Default: ANSWER_GENERATION_MODEL from .env (e.g. qwen3:32b)",
    )
    p.add_argument("--iterations", type=int, default=15, help="Samples per endpoint per run (1–500)")
    p.add_argument("--warmup", type=int, default=1, help="Extra generate calls before timing (0–5)")
    p.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("OLLAMA_HTTP_TIMEOUT_SECONDS", "300")),
        help="HTTP timeout seconds",
    )
    p.add_argument("--runs", type=int, default=1, help="Repeat full benchmark N times (aggregate stats)")
    p.add_argument(
        "--prompt-mode",
        choices=("short", "long"),
        default="long",
        help="Generate prompt: short smoke test or long RAG-like (default: long, for timeout tuning)",
    )
    p.add_argument(
        "--evidence-lines",
        type=int,
        default=14,
        help="With --prompt-mode long: number of evidence lines (default 14)",
    )
    p.add_argument(
        "--quote-chars",
        type=int,
        default=360,
        help="With --prompt-mode long: approximate chars per evidence quote (default 360)",
    )
    args = p.parse_args()

    if not 1 <= args.iterations <= 500:
        print("iterations must be 1–500", file=sys.stderr)
        return 2
    if not 0 <= args.warmup <= 5:
        print("warmup must be 0–5", file=sys.stderr)
        return 2
    if not 1 <= args.runs <= 20:
        print("runs must be 1–20", file=sys.stderr)
        return 2
    if not 1 <= args.evidence_lines <= 80:
        print("evidence-lines must be 1–80", file=sys.stderr)
        return 2
    if not 80 <= args.quote_chars <= 4000:
        print("quote-chars must be 80–4000", file=sys.stderr)
        return 2

    base = args.url.rstrip("/")
    timeout = httpx.Timeout(args.timeout)

    if args.prompt_mode == "long":
        gen_prompt = build_rag_like_prompt(
            evidence_lines=args.evidence_lines,
            quote_chars=args.quote_chars,
        )
    else:
        gen_prompt = "Reply with exactly: OK"

    print(f"Ollama base: {base}")
    print(f"Embedding model: {args.embedding_model}")
    print(f"Generate model:  {args.generate_model}")
    print(f"Prompt mode:     {args.prompt_mode}  ({len(gen_prompt):,} chars)")
    print(f"Iterations/run: {args.iterations}  runs: {args.runs}  timeout: {args.timeout}s")
    print()

    all_tags: list[float] = []
    all_embed: list[float] = []
    all_gen: list[float] = []

    for run in range(args.runs):
        if args.runs > 1:
            print(f"--- run {run + 1}/{args.runs} ---")

        tags_ms: list[float] = []
        embed_ms: list[float] = []
        gen_ms: list[float] = []

        with httpx.Client(timeout=timeout) as client:
            # Tags
            for _ in range(args.iterations):
                t0 = time.perf_counter()
                r = client.get(f"{base}/api/tags")
                r.raise_for_status()
                tags_ms.append((time.perf_counter() - t0) * 1000.0)

            # Embeddings
            emb_body = {"model": args.embedding_model, "input": "benchmark probe text for latency"}
            for _ in range(args.iterations):
                t0 = time.perf_counter()
                r = client.post(f"{base}/api/embeddings", json=emb_body)
                r.raise_for_status()
                embed_ms.append((time.perf_counter() - t0) * 1000.0)

            # Generate — warmup loads model (same prompt shape as timed calls)
            gen_body = {
                "model": args.generate_model,
                "prompt": gen_prompt,
                "stream": False,
            }
            for _ in range(args.warmup):
                client.post(f"{base}/api/generate", json=gen_body).raise_for_status()

            for _ in range(args.iterations):
                t0 = time.perf_counter()
                r = client.post(f"{base}/api/generate", json=gen_body)
                r.raise_for_status()
                gen_ms.append((time.perf_counter() - t0) * 1000.0)

        all_tags.extend(tags_ms)
        all_embed.extend(embed_ms)
        all_gen.extend(gen_ms)

        if args.runs > 1:
            print(fmt_stats("GET /api/tags", _stats_ms(tags_ms)))
            print(fmt_stats("POST /api/embeddings", _stats_ms(embed_ms)))
            print(fmt_stats("POST /api/generate", _stats_ms(gen_ms)))
            print()

    print("=== Aggregate (all runs) ===")
    print(fmt_stats("GET /api/tags", _stats_ms(all_tags)))
    print(fmt_stats("POST /api/embeddings", _stats_ms(all_embed)))
    gen_stats = _stats_ms(all_gen)
    gen_label = "POST /api/generate" + (" (long RAG-like prompt)" if args.prompt_mode == "long" else " (short prompt)")
    print(fmt_stats(gen_label, gen_stats))

    if all_gen:
        mx = max(all_gen)
        mx_s = mx / 1000.0
        if args.prompt_mode == "long":
            # Already measured a large prompt; add fixed slack for load spikes / occasional slower runs.
            suggested = min(600, max(120, int(mx_s + 150)))
            detail = (
                f"long-prompt generate max {mx:.1f} ms; min(600, max(120, int(max_s+150)))"
            )
        else:
            # Short prompt is not representative of chat; large multiplier + slack.
            suggested = min(600, max(120, int(mx_s * 35 + 90)))
            detail = f"short-prompt max {mx:.1f} ms; min(600, max(120, int(max_s*35+90))) — prefer --prompt-mode long for tuning"
        print()
        print(f"Suggested OLLAMA_HTTP_TIMEOUT_SECONDS: {suggested}")
        print(f"  ({detail})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
