# lfx-scavio

[Scavio](https://scavio.dev) real-time search as a standalone Langflow
Extension Bundle.

## What it ships

Seventeen components, registered under the `scavio` bundle group, covering all
97 live Scavio endpoints across ten platforms:

| Component | Endpoints | Covers |
|---|---|---|
| **Scavio Search** (`ScavioSearch`) | 1 | Google web search (v2) |
| **Scavio Google AI Mode** | 1 | Google's AI-generated answer with cited sources |
| **Scavio Google Maps** | 3 | Place search, place detail, reviews |
| **Scavio Google Shopping** | 3 | Product search, product detail, seller listings |
| **Scavio Google News** | 1 | News results |
| **Scavio Google Trends** | 2 | Interest over time, trending now |
| **Scavio Google Flights** | 1 | Flight search |
| **Scavio Google Hotels** | 2 | Hotel search and property detail |
| **Scavio YouTube** | 15 | Search, shorts, video, comments, transcript, channel feeds, streams |
| **Scavio Amazon** | 3 | Product search, product detail, seller offers |
| **Scavio Walmart** | 2 | Product search, product detail |
| **Scavio Reddit** | 12 | Search, post, comments, subreddit and user feeds, popular, trending |
| **Scavio TikTok** | 11 | Profile, posts, video, comments, search, hashtags, follow graph |
| **Scavio TikTok Shop** | 8 | Product search, detail, reviews, categories, shop catalog |
| **Scavio Instagram** | 12 | Profile, posts, reels, stories, comments, search, follow graph |
| **Scavio X** | 11 | Search, post, comments, user timelines, follow graph, trending |
| **Scavio LinkedIn** | 9 | Person, company, their posts, job search and detail, post comments |

Components that serve several endpoints use a **Endpoint** dropdown with
`real_time_refresh`, so only the fields the selected endpoint accepts are shown
and required.

## Setup

Create a free key at the [Scavio Dashboard](https://dashboard.scavio.dev) — new
accounts get 50 one-time credits and no card is required. Set it on the
component, or export it:

```bash
export SCAVIO_API_KEY=sk_live_your_key
```

## Credits

Cost is per endpoint and **not** uniform. Every component states its own cost.

| Call | Credits |
|---|---|
| Google (all verticals), Amazon, Walmart, Reddit, TikTok, TikTok Shop, X | 1 |
| YouTube search, shorts search | 2 |
| YouTube streams | 3 |
| YouTube transcript | 8 |
| Instagram user posts | 2 |
| Instagram post, comment replies | 8 |
| Instagram everything else | 10 |
| LinkedIn person, company, post | 1 |
| LinkedIn posts feeds, job search, post comments | 10 |
| LinkedIn job detail | 30 |

## Deliberately not exposed

- `POST /api/v1/google` — Google v1 was retired on 2026-08-04 and returns 410.
  Every Google component targets `/api/v2/google*`, whose parameters are `gl`,
  `hl`, `start`, `google_domain` and `device`. Note `start` is a 0-based result
  offset, not a page number: page 2 is `start=10`.
- `POST /api/v1/youtube/metadata` — a deprecated alias of
  `/api/v1/youtube/video`. The Video Details endpoint targets `/video` directly
  rather than shipping a duplicate.
- Five LinkedIn endpoints whose upstream dataset was withdrawn and which now
  answer 410 unbilled: `/person/contact`, `/company/people`, `/company/jobs`,
  `/search/people`, `/search/posts`. Use `/linkedin/company`, which returns a
  small `featured_employees` sample, and `/linkedin/search/jobs` instead.

## Response shapes worth knowing

- Google v2 returns its payload **flat**; every other product nests it under
  `data`.
- `/reddit/search` returns `data.results` with `next_cursor` and `has_more`.
  `/reddit/post` returns a **flat post object with no comments** — use the
  Post Comments endpoint for those. Subreddit and user feeds return `data.posts`.
- TikTok and Instagram responses are raw upstream passthrough, so their exact
  keys vary with which provider leg answered. The Raw JSON output is the
  reliable surface there.
- TikTok `cursor` is a **string**, not a number.

## Tests

```bash
uv run pytest src/bundles/scavio/tests -q
```
