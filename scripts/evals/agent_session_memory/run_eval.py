"""Eval of chat history policies for the Agent component.

Runs the scripted sessions of `sessions.py` against each history policy with a real model, and
writes one JSON file per (variant, session) plus a Markdown report. One run for each case.

    uv run python scripts/evals/agent_session_memory/run_eval.py --out <dir> --variants lastn100,lastn10,pr16515
    uv run python scripts/evals/agent_session_memory/run_eval.py --out <dir> --report

The Agent loop is `langchain.agents.create_agent`, as in the Agent component, and the history goes
through the Agent's own `build_initial_messages`. The message table is an in-memory list (`memstore.py`).
OPENAI_API_KEY must be set in the environment.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import memstore
import pr16515_compressor as pr
from langchain.agents import create_agent
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from lfx.components.models_and_agents.agent_helpers.messages_input_builder import build_initial_messages
from sessions import Session, all_sessions, tool_log

MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = "You are a helpful support engineering assistant. Answer clearly and practically."
TURN_TIMEOUT_SECONDS = 300
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return -(-len(text) // CHARS_PER_TOKEN)


class UsageRecorder(AsyncCallbackHandler):
    """Collect usage for each chat model call. Calls tagged `lc_source=summarization` count as compaction."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._compaction_runs: set[Any] = set()

    async def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs) -> None:  # noqa: ARG002
        if (metadata or {}).get("lc_source") == "summarization":
            self._compaction_runs.add(run_id)

    async def on_llm_end(self, response, *, run_id, **kwargs) -> None:  # noqa: ARG002
        for generations in response.generations:
            for generation in generations:
                usage = getattr(getattr(generation, "message", None), "usage_metadata", None) or {}
                details = usage.get("input_token_details") or {}
                self.calls.append(
                    {
                        "input": usage.get("input_tokens", 0),
                        "cached": details.get("cache_read", 0) or 0,
                        "output": usage.get("output_tokens", 0),
                        "compaction": run_id in self._compaction_runs,
                    }
                )


@dataclass
class Prepared:
    """History for one turn, and the fold to run beside the answer (None when no fold is due)."""

    history: list
    fold: Any = None


class Policy:
    """A chat history policy. Subclasses build the history and the middleware."""

    name = "base"

    async def prepare(self, store: memstore.MemStore, user_message) -> Prepared:
        raise NotImplementedError

    def middleware(self, llm) -> list:  # noqa: ARG002
        return []

    def describe_state(self, store: memstore.MemStore) -> dict:  # noqa: ARG002
        return {}


class LastN(Policy):
    """Today's Agent: the newest `n` stored messages."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.name = f"lastn{n}"

    async def prepare(self, store, user_message) -> Prepared:
        return Prepared(store.between(None, user_message.id, self.n, newest_first=True))


class PR16515(Policy):
    """PR #16515: the newest `n` messages plus a free-text summary of older ones, folded 20 at a time."""

    def __init__(self, llm, n: int = 10) -> None:
        self.n = n
        self.llm = llm
        self.name = "pr16515"

    async def prepare(self, store, user_message) -> Prepared:
        window = store.between(None, user_message.id, self.n, newest_first=True)
        scope = {"flow_id": "f", "user_id": "u", "session_id": store.session_id, "context_id": ""}
        loaded = await pr.load_history_with_summary(
            window=window, n_messages=self.n, scope=scope, current_input_id=user_message.id
        )
        fold = None
        if loaded.fold_batch:
            fold = FoldRun()

            async def summarize(previous, messages):
                response = await self.llm.ainvoke(
                    pr.format_fold_prompt(previous, messages), config={"callbacks": [fold.usage]}
                )
                return pr.clip_words(str(response.content).strip()) or None

            fold.coro = pr.fold_batch(
                scope=scope, state=loaded.state, batch=loaded.fold_batch, summarize=summarize, summary_model=MODEL
            )
        return Prepared(loaded.history, fold)

    def describe_state(self, store) -> dict:
        return {"summary": store.state.summary, "folded_count": store.state.folded_count}


@dataclass
class FoldRun:
    """One background fold: its coroutine and the usage of its model call."""

    coro: Any = None
    usage: UsageRecorder = field(default_factory=UsageRecorder)


@dataclass
class TurnResult:
    turn: int
    history_messages: int
    history_tokens_est: int
    model_calls: int
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    compaction_calls: int
    fold_calls: int
    fold_input_tokens: int
    answer_seconds: float
    added_seconds: float
    error: str | None = None
    answer: str = ""


@tool
def fetch_service_log(service: str) -> str:
    """Return the full log of one service, for example svc-1."""
    match = re.search(r"(\d+)", service)
    return tool_log(int(match.group(1)) if match else 1)


def make_llm() -> ChatOpenAI:
    return ChatOpenAI(model=MODEL, temperature=0, max_retries=2, timeout=120)


async def run_session(policy: Policy, session: Session, run_tag: str) -> dict:
    """Run every turn of `session` under `policy`. Returns the per-turn results and the score."""
    session_id = f"{run_tag}-{policy.name}-{session.name}"
    store = memstore.MemStore(session_id)
    memstore.STORES[session_id] = store
    llm = make_llm()
    tools = [fetch_service_log] if session.tool_answer else []
    agent = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT, middleware=policy.middleware(llm))
    results: list[TurnResult] = []
    for index, text in enumerate(session.turns, start=1):
        user_message = store.add(text, "User")
        prepared = await policy.prepare(store, user_message)
        messages = build_initial_messages(input_value=user_message, chat_history=prepared.history)
        history_tokens = sum(estimate_tokens(str(m.content)) for m in messages[:-1]) + max(
            0, estimate_tokens(str(messages[-1].content)) - estimate_tokens(text)
        )
        usage = UsageRecorder()
        fold_task = asyncio.create_task(prepared.fold.coro) if prepared.fold else None
        start = time.perf_counter()
        error = None
        answer = ""
        try:
            result = await asyncio.wait_for(
                agent.ainvoke({"messages": messages}, config={"callbacks": [usage], "recursion_limit": 120}),
                TURN_TIMEOUT_SECONDS,
            )
            answer = str(result["messages"][-1].content)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {str(exc)[:300]}"
        answer_done = time.perf_counter()
        if fold_task:
            await fold_task
        added = time.perf_counter() - answer_done
        if answer:
            store.add(answer, "Machine")
        fold_calls = prepared.fold.usage.calls if prepared.fold else []
        results.append(
            TurnResult(
                turn=index,
                history_messages=len(messages) - 1,
                history_tokens_est=history_tokens,
                model_calls=sum(not c["compaction"] for c in usage.calls),
                input_tokens=sum(c["input"] for c in usage.calls if not c["compaction"]),
                cached_tokens=sum(c["cached"] for c in usage.calls if not c["compaction"]),
                output_tokens=sum(c["output"] for c in usage.calls),
                compaction_calls=sum(c["compaction"] for c in usage.calls),
                fold_calls=len(fold_calls),
                fold_input_tokens=sum(c["input"] for c in fold_calls),
                answer_seconds=round(answer_done - start, 2),
                added_seconds=round(added, 2),
                error=error,
                answer=answer if index == len(session.turns) else answer[:200],
            )
        )
        print(f"[{policy.name}/{session.name}] turn {index}/{len(session.turns)} err={bool(error)}", flush=True)
    final = results[-1]
    return {
        "variant": policy.name,
        "session": session.name,
        "turns": [asdict(r) for r in results],
        "score": score(session, final.answer, final.error),
        "state": policy.describe_state(store),
    }


def _parse_lines(answer: str) -> dict[str, str]:
    parsed = {}
    for line in answer.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            parsed[key.strip().strip("-* `").lower()] = value.strip().strip("`")
    return parsed


def score(session: Session, answer: str, error: str | None) -> dict:
    """Score the final turn. Chat sessions: each key is correct, unknown or wrong. Tool session: pass or fail."""
    if error:
        return {"error": error, "correct": 0, "total": len(session.probe.expected) if session.probe else 1}
    parsed = _parse_lines(answer)
    if session.tool_answer:
        root = parsed.get("root_cause", "").lower()
        path = re.findall(r"svc-(\d+)", parsed.get("path", ""))
        hops = len(dict.fromkeys(path))
        ok_root = session.tool_answer["root_cause"] in root
        ok_path = hops == int(session.tool_answer["path_hops"])
        return {"correct": int(ok_root) + int(ok_path), "total": 2, "root_ok": ok_root, "path_hops": hops}
    keys = {}
    for key, expected in session.probe.expected.items():
        value = parsed.get(key, "unknown")
        if expected.lower() in value.lower():
            keys[key] = "correct"
        elif value.lower() in {"", "unknown"}:
            keys[key] = "unknown"
        else:
            stale = any(s.lower() in value.lower() for s in session.probe.stale.get(key, []))
            keys[key] = "stale" if stale else "wrong"
    correct = sum(v == "correct" for v in keys.values())
    wrong = sum(v in {"wrong", "stale"} for v in keys.values())
    return {"correct": correct, "total": len(keys), "wrong": wrong, "keys": keys}


def build_policies(names: list[str]) -> list[Policy]:
    fold_llm = make_llm()
    factories = {
        "lastn100": lambda: LastN(100),
        "lastn10": lambda: LastN(10),
        "pr16515": lambda: PR16515(fold_llm),
    }
    try:
        import auto_policy  # added with the Auto mode

        factories.update(auto_policy.factories(fold_llm))
    except ImportError:
        pass
    return [factories[name]() for name in names]


async def main_run(out: Path, variants: list[str], sessions: list[str] | None, parallel: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    run_tag = time.strftime("%H%M%S")
    chosen = [s for s in all_sessions() if not sessions or s.name in sessions]
    semaphore = asyncio.Semaphore(parallel)

    async def one(policy: Policy, session: Session) -> None:
        async with semaphore:
            data = await run_session(policy, session, run_tag)
            (out / f"{policy.name}__{session.name}.json").write_text(json.dumps(data, indent=2))

    # A fresh policy for each session: policies hold no state across sessions, but keep them apart anyway.
    jobs = [one(build_policies([v])[0], s) for v in variants for s in chosen]
    await asyncio.gather(*jobs)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def report(out: Path) -> str:
    """Render the Markdown tables from the JSON results in `out`."""
    rows = [json.loads(p.read_text()) for p in sorted(out.glob("*__*.json"))]
    variants = list(dict.fromkeys(r["variant"] for r in rows))
    sessions = list(dict.fromkeys(r["session"] for r in rows))
    by = {(r["variant"], r["session"]): r for r in rows}
    lines: list[str] = []

    def table(title: str, cell) -> None:
        lines.extend([f"### {title}", "", "| Session | " + " | ".join(variants) + " |"])
        lines.append("|---" * (len(variants) + 1) + "|")
        for s in sessions:
            cells = [cell(by[(v, s)]) if (v, s) in by else "-" for v in variants]
            lines.append(f"| {s} | " + " | ".join(cells) + " |")
        lines.append("")

    def recall(r):
        sc = r["score"]
        if "error" in sc:
            return "failed"
        wrong = f", {sc['wrong']} wrong" if sc.get("wrong") else ""
        return f"{sc['correct']}/{sc['total']}{wrong}"

    def tokens(r):
        values = [t["input_tokens"] for t in r["turns"]]
        return f"mean {_mean(values):,.0f} / max {max(values):,} / total {sum(values):,}"

    def cached(r):
        total_in = sum(t["input_tokens"] for t in r["turns"])
        total_cached = sum(t["cached_tokens"] for t in r["turns"])
        share = total_cached / total_in if total_in else 0
        return f"mean {_mean([t['cached_tokens'] for t in r['turns']]):,.0f} ({share:.0%} of input)"

    def latency(r):
        added = [t["added_seconds"] for t in r["turns"]]
        answer = [t["answer_seconds"] for t in r["turns"]]
        return f"answer {_mean(answer):.1f}s, added mean {_mean(added):.2f}s / max {max(added):.1f}s"

    def calls(r):
        folds = sum(t["fold_calls"] for t in r["turns"])
        compactions = sum(t["compaction_calls"] for t in r["turns"])
        fold_in = sum(t["fold_input_tokens"] for t in r["turns"])
        return f"{folds} fold / {compactions} compaction ({fold_in:,} fold input tokens)"

    def history(r):
        return f"max {max(t['history_tokens_est'] for t in r['turns']):,}"

    table("Recall of early facts (correct/total; tool session: root cause + full path)", recall)
    table("Input tokens for each turn (answer calls only)", tokens)
    table("Cached input tokens for each turn", cached)
    table("Latency: answer time and time added by the fold wait", latency)
    table("Summary calls", calls)
    table("History tokens sent, estimated at 4 characters for each token", history)
    errors = [
        f"- {r['variant']}/{r['session']} turn {t['turn']}: {t['error']}"
        for r in rows
        for t in r["turns"]
        if t["error"]
    ]
    if errors:
        lines.extend(["### Errors", "", *errors, ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variants", default="lastn100,lastn10,pr16515")
    parser.add_argument("--sessions", default="")
    parser.add_argument("--parallel", type=int, default=6)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if not args.report:
        asyncio.run(
            main_run(args.out, args.variants.split(","), [s for s in args.sessions.split(",") if s], args.parallel)
        )
    text = report(args.out)
    (args.out / "REPORT.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
