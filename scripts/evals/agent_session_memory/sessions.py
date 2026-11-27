"""Scripted sessions for the Agent session-memory eval.

Each session is a list of user turns. The last turn of a chat session is a probe: it asks for
facts in a fixed `key=value` form, so the score is an exact compare and not a model judge.
The text is fixed, so every variant sees the same input.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PROBE_RULES = (
    "Use only what I told you earlier in this conversation. "
    "Reply with exactly one line per key in the form key=value and nothing else. "
    "Write value=unknown when you do not know it."
)

_TOPICS = [
    ("payments-api", "pods restart with exit code 137", "kubectl describe pod payments-api-7f9c"),
    ("checkout-web", "p95 latency went from 220 ms to 1.4 s", "the Grafana latency panel"),
    ("orders-db", "replication lag reached 45 seconds", "pg_stat_replication"),
    ("auth-service", "token refresh returns HTTP 401 for some users", "the auth-service logs"),
    ("search-indexer", "the nightly reindex job takes 3 hours instead of 40 minutes", "the job history"),
    ("notifications", "push messages arrive twice", "the SNS delivery logs"),
    ("inventory-sync", "stock counts drift by about 2% per day", "the reconciliation report"),
    ("gateway", "about 0.5% of requests get HTTP 502", "the ingress controller metrics"),
    ("billing-worker", "the queue backlog grows to 80,000 jobs at 09:00", "the RabbitMQ dashboard"),
    ("media-cdn", "image cache hit rate dropped to 61%", "the CDN analytics page"),
]

# Plausible noise: other ids, environments and names that a summary could confuse with the real facts.
_DISTRACTORS = [
    "A colleague mentioned ticket INC-4471 from another team, but it is not ours.",
    "The staging cluster AP-South shows the same symptom, but we do not own staging.",
    "Someone from the Contoso account asked about this in Slack. They are not our customer.",
    "The old runbook still names project PRJ-090, which was archived last year.",
    "The vendor contact Marcus Lee replied to an old email thread. He is not on call.",
    "",
    "",
    "",
]


def _filler_turn(index: int) -> str:
    service, symptom, source = _TOPICS[index % len(_TOPICS)]
    distractor = _DISTRACTORS[index % len(_DISTRACTORS)]
    step = index + 1
    return (
        f"Next issue (step {step}): on {service}, {symptom}. I checked {source} and saw nothing obvious. "
        f"We changed the resource limits two days ago and the deploy pipeline ran {3 + index % 5} times since. "
        f"{distractor} What are the three most likely causes, and what should I check first?"
    ).replace("  ", " ")


@dataclass
class Probe:
    """Expected values for the probe turn. `stale` holds values that are no longer true."""

    expected: dict[str, str]
    stale: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Session:
    """One scripted session. `probe` is None for the tool session, which is scored by `tool_answer`."""

    name: str
    turns: list[str]
    probe: Probe | None = None
    tool_answer: dict[str, str] = field(default_factory=dict)


def _probe_text(keys: list[str], extra: str = "") -> str:
    return f"{extra}Keys: {', '.join(keys)}. {PROBE_RULES}"


def long_session(turns: int = 60) -> Session:
    """The issue scenario: facts in turn 1, then a long troubleshooting session, then a probe."""
    first = (
        "Hi. Some context first: I'm working on project PRJ-123 on the EU-West cluster for customer "
        "ACME Corp. Our on-call engineer this week is Dana Whitfield. Please keep that in mind."
    )
    body = [_filler_turn(i) for i in range(turns - 2)]
    keys = ["project", "cluster", "customer", "oncall"]
    probe = _probe_text(keys, "Quick check before I write the incident report. ")
    return Session(
        name=f"long_{turns}",
        turns=[first, *body, probe],
        probe=Probe(
            expected={"project": "PRJ-123", "cluster": "EU-West", "customer": "ACME", "oncall": "Dana Whitfield"}
        ),
    )


def _pasted_log(lines: int = 1500) -> str:
    rows = [
        "2026-11-20T00:00:00Z orders-api INFO service=orders version=4.2.1 build=8c1f2a region=ap-southeast-2 start"
    ]
    rows.extend(
        f"2026-11-20T{(i // 3600) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d}Z orders-api INFO "
        f"request_id=r{i:06d} route=/v1/orders/{i % 97} status=200 duration_ms={40 + i % 90} cache=miss"
        for i in range(1, lines - 1)
    )
    rows.append("2026-11-20T03:14:07Z orders-db FATAL could not extend file base/16384/2619: No space left on device")
    return "\n".join(rows)


def pasted_log_session() -> Session:
    """A session where the user pastes a log of about 40,000 tokens in turn 3."""
    turns = [
        "Context: project PRJ-77, region ap-southeast-2, customer Globex. The orders service went down at 03:14 UTC.",
        "I have the full log from the orders host. I'll paste it next.",
        "Here is the log:\n\n" + _pasted_log(),
        "What does the last line of that log tell us?",
        *[_filler_turn(i) for i in range(10)],
        _probe_text(["project", "region", "customer", "log_error"], "Before I close the incident. "),
    ]
    return Session(
        name="pasted_log",
        turns=turns,
        probe=Probe(
            expected={
                "project": "PRJ-77",
                "region": "ap-southeast-2",
                "customer": "Globex",
                "log_error": "no space left on device",
            }
        ),
    )


def fact_change_session() -> Session:
    """A fact set in turn 1 changes in turn 12. The probe must return the new value, not the old one."""
    first = (
        "Setup: we run on the EU-West cluster with Postgres 14, and the customer is Initech. "
        "Keep these in mind for the rest of the session."
    )
    change = (
        "Update: last night we migrated everything to the US-East cluster and upgraded to Postgres 16. "
        "EU-West is decommissioned now. The customer did not change."
    )
    turns = [
        first,
        *[_filler_turn(i) for i in range(10)],
        change,
        *[_filler_turn(i + 10) for i in range(11)],
        _probe_text(["cluster", "postgres_version", "customer"], "For the change log. "),
    ]
    return Session(
        name="fact_change",
        turns=turns,
        probe=Probe(
            expected={"cluster": "US-East", "postgres_version": "16", "customer": "Initech"},
            stale={"cluster": ["EU-West"], "postgres_version": ["14"]},
        ),
    )


TOOL_HOPS = 12
TOOL_RESULT_CHARS = 52_000  # about 13,000 tokens at 4 characters for each token


def tool_log(service: int) -> str:
    """The log of `service` in the tool session: large, with the pointer to the next service at the tail."""
    head = f"LOG FOR svc-{service}\nservice=svc-{service} owner=team-{service % 4}\n"
    filler_line = f"svc-{service} DEBUG heartbeat ok queue_depth=12 gc_pause_ms=3 conn_pool=42/50\n"
    body = filler_line * ((TOOL_RESULT_CHARS - 200) // len(filler_line))
    if service >= TOOL_HOPS:
        tail = f"svc-{service} ERROR ROOT CAUSE: certificate for db-proxy expired at 02:00 UTC\nEND OF LOG\n"
    else:
        tail = f"svc-{service} WARN upstream errors come from svc-{service + 1}\nNEXT_SERVICE: svc-{service + 1}\n"
    return head + body + tail


def tool_session() -> Session:
    """One run with many large tool results. Without a cap it passes the model window of 128,000 tokens."""
    prompt = (
        "Find the root cause of the outage. Call fetch_service_log for svc-1. Each log ends with "
        "NEXT_SERVICE: <name>; then fetch that service's log. Fetch one log at a time. Continue until a log "
        "contains ROOT CAUSE. Then reply with two lines: root_cause=<text> and path=<the services you "
        "visited, in order, separated by >>."
    )
    return Session(
        name="tool_heavy",
        turns=[prompt],
        tool_answer={"root_cause": "certificate", "path_hops": str(TOOL_HOPS)},
    )


def all_sessions() -> list[Session]:
    return [long_session(), pasted_log_session(), fact_change_session(), tool_session()]
