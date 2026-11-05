# Decision routing evaluation

Measures how decision models route a labelled set of messages, for the v1.14 release evidence (LE-3117). Each case runs through the real **Smart Router** component, the same code a flow runs. Thresholds, ties, per-route minimums, Score rounding and error handling are the component's own, not reimplemented here.

For every target it records:
- model versions
- wrong-route rate
- coverage (the share routed automatically)
- Else rate
- error rate by category
- latency
- tokens and cost

A target is a decision model, or a language model as the existing-flow baseline. Release targets are checked only when you supply them.

## What a run needs

| Input | Who provides it | Status |
|---|---|---|
| A labelled suite | The dataset owner, agreed with product | `suites/support_ticket_routing.json` is a **seed** of 40 cases mirroring the Support Ticket Routing starter. It exercises the harness. It is not the agreed dataset. |
| API keys | Whoever runs it | `TYPESAFE_API_KEY`, `PERPLEXITY_API_KEY`, `OPENAI_API_KEY` in the environment, read the way a flow reads them. Keys are never written to the output. |
| Prices | Whoever runs it, from each provider's current price list | Optional. Without them, cost is reported as "unpriced". |
| Release targets | Product, with the dataset owner | Optional. Without them, the report gives measurements and makes no pass or fail claim. |

## Run it

```bash
# Check a suite and the harness offline. Fake answers, no keys, no cost:
uv run python -m scripts.eval.decision_routing.run run \
    scripts/eval/decision_routing/suites/support_ticket_routing.json --fake

# Live: every mandatory provider plus a language model baseline. Billed, so --yes is required:
uv run python -m scripts.eval.decision_routing.run run SUITE.json \
    --target TypeSafe:jev-latest \
    --target Perplexity:pplx-decider-latest --target Perplexity:pplx-decider-flash-latest \
    --target OpenAI:gpt-6-luna \
    --baseline OpenAI:gpt-4o-mini \
    --pricing pricing.json --targets targets.json --yes

# Rebuild the report, sweep and target checks from a past run, with no new requests:
uv run python -m scripts.eval.decision_routing.run report scripts/eval/decision_routing/runs/<run> \
    --pricing pricing.json --targets targets.json
```

**Run behaviour:**
- **Targets:** without `--target`, every decision model in the catalog runs.
- **Billing guard:** a live run prints its plan (cases × targets requests) and refuses to start without `--yes`. It also refuses more than `--max-requests` requests (default 500).
- **Fatal errors:** a rejected key, an exhausted account, a policy denial or invalid settings stop that target at once rather than billing on. The report marks the target as stopped, with the reason.
- **Measured errors:** timeouts, rate limits, server errors and malformed answers don't stop the run. They are recorded as errors, as with Evaluation Error Action set to Route to Else.
- **Baseline:** routes in Language Model mode, as an existing flow does. It needs the provider's package and key, so run it from the full Langflow environment.

### pricing.json

```json
{
  "TypeSafe:jev-latest": {"input_per_million": 0.0, "output_per_million": 0.0, "per_request": 0.0},
  "OpenAI:gpt-4o-mini": {"input_per_million": 0.0, "output_per_million": 0.0}
}
```

Prices are per million tokens, plus an optional flat price per request. Fill them in from each provider's price list on the day of the run.

A target is "unpriced" if it has no price, or if any of its answers reported no token usage. That way a total is never quietly undercounted.

### targets.json

```json
{"max_wrong_route_rate": 0.02, "min_coverage": 0.8, "max_error_rate": 0.01, "max_p95_latency_ms": 1500, "max_cost_per_1000": 1.0}
```

The values above are only an example of the format. Supported keys:
- `max_wrong_route_rate`
- `min_coverage`
- `max_else_rate`
- `max_error_rate`
- `max_p95_latency_ms`
- `max_cost_per_1000`

A value that wasn't measured never passes, for example latency on a replayed run. A failed target makes the command exit 1.

## Suites

A suite is a JSON file that points to a JSON Lines file of cases:

```json
{
  "name": "support-ticket-routing",
  "kind": "choice",
  "question": "Which team should handle this customer message?",
  "minimum_probability": 0.7,
  "routes": [{"name": "Billing", "description": "Payments, invoices, refunds...", "minimum_probability": null}],
  "cases": "support_ticket_routing.jsonl"
}
```

```json
{"id": "billing-001", "text": "I was charged twice for my October invoice.", "expected": "Billing", "tags": ["clear"]}
```

What `expected` can be depends on the suite's kind:

| Kind | Table | `expected` |
|---|---|---|
| `choice` | `routes` | A route name, or `Else` |
| `boolean` | none | `Yes`, `No` or `Else` |
| `score` | `levels` (2–10, lowest first) | A level name |

`Else` marks a message no route should take: greetings, off-topic text, or a message that needs a person. **Agree with product how ambiguous messages are labelled.** The seed labels mixed-intent messages as `Else`, which is a product decision, not a fact.

To compare a model with the shipped experience, give the suite the same question, routes and minimum probability as the flow it stands for.

## Output

Each run writes a directory, `runs/<suite>-<UTC time>/` by default, which git ignores:

| File | Contents |
|---|---|
| `run.json` | The suite, its cases' SHA-256, the lfx version, the time, and any stopped targets. |
| `records.jsonl` | One record per case and target: <ul><li>expected and routed</li><li>outcome and the router's reason</li><li>error category</li><li>latency</li><li>reported model and where the name came from</li><li>request ID and tokens</li><li>the full decision result, kept so the run can be replayed</li></ul> |
| `summary.json` | The metrics, the sweep and the target checks, as data. |
| `report.md` | The same, for the release ticket. |

## Metrics

Every rate is over all cases. Correct, wrong route, Else and errors add up to 100%.

| Metric | Meaning |
|---|---|
| Wrong route | Sent to a route other than the expected one. This includes an `Else` case sent to any route. |
| Coverage | Sent to any route without a person: correct plus wrong route. |
| Accuracy when routed | Correct ÷ coverage. |
| Else | Went to Else because the top answer was below the minimum probability, or tied. |
| Errors | An operational error or a refusal, by category (`timeout`, `transport`, `http_error`, `input_too_large`, `invalid_response`, `refusal`). |
| False accepts | Cases labelled `Else` that went to a route anyway. |
| Latency | Wall time around the router's decision, including Langflow's own work. Requests overlap up to `--concurrency`, so rate limits can show up as latency. |
| Model versions | The model each answer reports, and whether that name came from the provider's `response` or echoes the `request`. Perplexity echoes the requested alias. |

The **minimum probability sweep** feeds each recorded answer back through the router at minimums from 0.50 to 0.95. This shows the trade-off between wrong routes and coverage without new requests, which is the input for agreeing a threshold and its target.

## Tests

```bash
uv run pytest scripts/eval/decision_routing/tests
```
