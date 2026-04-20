## Cold Start Benchmark: regression detected (1 scenario(s) failed)

Baseline ref: `12750/merge@eb2272ccc711768ecb11a3c0982aa419852bb17a` captured 2026-04-20 on ubuntu-latest (GitHub Actions). Allowed regression: 15%. Measurement mode: `bytecode_compile_delta`.

| scenario | baseline_ms | current_ms | delta_pct | allowed_pct | status |
|---|---:|---:|---:|---:|:-:|
| lfx_bare | 10549.9 | 18195.7 | +72.5% | 15% | FAIL |

Hyperfine JSON artifacts: see the `cold-start-benchmark-reports` workflow artifact. Local paths: `reports/<scenario>.json`.

Per D-16: to merge anyway, apply the `benchmarks:override` label AND document the justification in the PR description.

Measurement mode: bytecode_compile_delta