# lfx-fastaf

Ten FastAF components as a standalone, opt-in Langflow Extension Bundle.
Uses [`httpx`](https://www.python-httpx.org/) directly with the
[FastAF API](https://fastaf.co/docs/); no vendor SDK is required.

## Install

From a source checkout containing this bundle:

```bash
uv pip install -e src/bundles/fastaf
lfx extension validate src/bundles/fastaf/src/lfx_fastaf
```

After publication, install the distribution with `uv pip install lfx-fastaf`.
Restart Langflow; **FastAF** appears in the palette's **Bundles** section.
`lfx extension list` can confirm discovery. The `langflow.extensions` entry point
finds `lfx_fastaf/extension.json`, whose bundle path is `components/fastaf`.

This is an opt-in `langflow[bundles]` integration, not a new default dependency.
The initial release targets the current `release-1.14.0` candidate and LFX bundle
API `1` (`lfx>=1.14.0.dev0,<2.0.0`). It has not been published by this change.

## Authenticate

1. Create and verify an account at <https://fastaf.co/signup/>.
2. Create an API key at <https://fastaf.co/dashboard/>.
3. Set **FastAF API Key**, a `SecretStrInput`, on the component or use a Langflow
   credential global variable. Raw strings and wrapped secret values are supported.

The key is sent only as `Authorization: Bearer <key>` to the fixed
`https://api.fastaf.co` origin. No paid request occurs on import, construction,
discovery or tool creation. Credentials and upstream error bodies are not logged
or included in error outputs.

## Components

| Component | Tool / output method | Endpoint | Reference credits |
| --- | --- | --- | --- |
| `FastAFScrapeComponent` | `fastaf_scrape` | `POST /v1/scrape` | 1 static; selected modes cost more |
| `FastAFSearchComponent` | `fastaf_search` | `POST /v1/serp` | 5; advanced search 10 |
| `FastAFExtractComponent` | `fastaf_extract` | `POST /v1/scrape` | Scrape base + 10 AI credits |
| `FastAFScreenshotComponent` | `fastaf_screenshot` | `POST /v1/screenshot` | 5 |
| `FastAFAmazonComponent` | `fastaf_amazon` | `POST /v1/amazon` | 1 search/product; 5 offers/bestsellers |
| `FastAFMapsComponent` | `fastaf_maps` | `POST /v1/maps` | 5 |
| `FastAFLinkedInComponent` | `fastaf_linkedin` | `POST /v1/linkedin` | 60, including premium mode |
| `FastAFYouTubeComponent` | `fastaf_youtube` | `POST /v1/youtube` | 1 transcript; 5 search |
| `FastAFNewsComponent` | `fastaf_news` | `POST /v1/news` | 5 |
| `FastAFJobsComponent` | `fastaf_jobs` | `POST /v1/jobs` | 5 |

See [FastAF's documentation](https://fastaf.co/docs/) for current pricing and
limits. Each component has one output and one unique `fastaf_*` tool name to
avoid collisions and accidental duplicate paid calls from multiple output ports.
A canonical component ID is `ext:fastaf:FastAFSearchComponent@official`.

## Inputs and behavior

- Scrape/Extract accept public HTTP(S) URLs. Optional rendering and proxy booleans
  use **Default / true / false**: Default omits the parameter, retaining site-specific
  defaults (including Booking rendering). Challenge Mode cannot combine with
  rendering, premium proxies or a proxy country.
- Optional numeric fields use integer text with blank meaning omitted. Native LFX
  integer inputs coerce blank to zero, which would override site wait defaults or
  create invalid screenshot dimensions. The component validates integer ranges
  before making a request; explicit zero/false values are preserved.
- Extract accepts a prompt and/or an instruction dictionary; rules become the
  scalar JSON string `ai_extract_rules` on `/v1/scrape`. There is no `/v1/extract`.
- Search/news page numbers start at 0. Maps offsets are 0, 20, ..., 100; provide
  coordinates for pagination. Amazon pages start at 1. Jobs/YouTube accept the
  API's continuation/filter tokens. Each run fetches only one paid page.
- Amazon exposes search, product, offers and bestsellers, not reviews. Query/ASIN
  requirements and resource-specific field omissions follow the API reference.
- LinkedIn expects a public person-profile slug, not a full URL or company page.
  YouTube transcripts need a video ID and available captions; search needs a query.

## Outputs and errors

Nine components return a `DataFrame` built from `Data` records, like Serping.
Search/list endpoints select their primary result array if present; otherwise
single resources/envelopes become flat records. Nested object keys use underscores,
nested arrays become JSON strings, and missing columns are filled with `None`.
An empty result array stays empty. Tool consumers receive the same data.

Screenshot returns `Data` containing `file_path`, MIME type, byte count and
HTTP/credit metadata. The image is checked against its PNG/JPG/WebP signature and
saved with a generated filename through Langflow's configured storage service,
under the flow namespace (or a generated namespace outside a graph). No base64
image is dumped into the output. Configure persistent storage for durable files;
local paths refer to the Langflow host, not the browser machine.

Errors return a single safe error row/Data record with HTTP/credit metadata.
Missing or malformed credit headers remain `None`, not a fabricated zero.
The transport verifies TLS, disables redirects and environment proxy inheritance,
limits responses to 64 MiB, and uses 120-second I/O timeouts plus a checked read
deadline. There are **no automatic retries, pagination or discovery API calls**.
A timeout or failed storage write can follow a billed request; do not retry blindly.

## Develop and test

From the repository root (use its release branch and lockfile):

```bash
uv sync --frozen --package lfx-fastaf --no-dev
uv run --frozen --package lfx-fastaf --no-dev --with pytest --with pytest-asyncio --with pytest-timeout \
  python -m pytest src/bundles/fastaf/tests -q
uv run --no-project --with ruff==0.13.3 ruff format --check src/bundles/fastaf
uv run --no-project --with ruff==0.13.3 ruff check src/bundles/fastaf
uv run --frozen --package lfx-fastaf --no-dev lfx extension validate src/bundles/fastaf/src/lfx_fastaf
```

Tests use real Langflow components/Data/DataFrame and mocked HTTP, covering all
10 operations, tools, authentication, optional/conditional mappings, safe errors,
response limits and file storage. They do not read credentials or spend credits.
Live validation is an explicit separate opt-in harness, not part of pytest or CI.

Authored by **FastAF <dev@fastaf.co>**. MIT licensed.
