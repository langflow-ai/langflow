# lfx-scavio

[Scavio](https://scavio.dev) real-time search as a standalone Langflow
Extension Bundle.

## What it ships

Thirty-nine components, registered under the `scavio` bundle group, covering all
188 live Scavio endpoints across 32 platforms.

### Search

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
| **Scavio Extract** | 1 | Read any URL back as HTML, Markdown or plain text |

### Retail and marketplaces

| Component | Endpoints | Covers |
|---|---|---|
| **Scavio Amazon** | 3 | Product search, product detail, seller offers |
| **Scavio Walmart** | 7 | Search, product, reviews, category, offers, seller, seller catalogue |
| **Scavio eBay** | 3 | Live and **sold** listing search, listing detail, seller profile |
| **Scavio Target** | 4 | Search, category, product, reviews |
| **Scavio Home Depot** | 3 | Search, product, reviews |

### Real estate, travel and local

| Component | Endpoints | Covers |
|---|---|---|
| **Scavio Zillow** | 3 | Listing search, property detail, agent reviews |
| **Scavio Redfin** | 3 | Listing search, property detail, market stats |
| **Scavio Booking.com** | 3 | Property search, hotel detail, reviews |
| **Scavio Airbnb** | 3 | Listing search, listing detail, reviews |
| **Scavio TripAdvisor** | 4 | Location lookup, search, location detail, reviews |
| **Scavio Yelp** | 3 | Business search, business detail, reviews |

### Jobs, companies and software

| Component | Endpoints | Covers |
|---|---|---|
| **Scavio Indeed** | 4 | Job search, job detail, company, company reviews |
| **Scavio Glassdoor** | 4 | Company search, company, reviews, salaries |
| **Scavio SEC EDGAR** | 6 | Ticker lookup, company, filings, XBRL concept and facts, full-text search |
| **Scavio Companies House** | 4 | UK company search, company, officers, filing history |
| **Scavio G2** | 3 | Software search, product, reviews |
| **Scavio Capterra** | 3 | Software search, product, reviews |

### App stores and advertising

| Component | Endpoints | Covers |
|---|---|---|
| **Scavio App Store** | 3 | Search, app detail, reviews |
| **Scavio Google Play** | 3 | Search, app detail, reviews |
| **Scavio Google Ads** | 3 | Ads Transparency search, advertiser lookup, creative |
| **Scavio Meta Ad Library** | 3 | Ad search, advertiser, single ad |

### Social

| Component | Endpoints | Covers |
|---|---|---|
| **Scavio YouTube** | 15 | Search, shorts, video, comments, transcript, channel feeds, streams |
| **Scavio Reddit** | 12 | Search, post, comments, subreddit and user feeds, popular, trending |
| **Scavio TikTok** | 11 | Profile, posts, video, comments, search, hashtags, follow graph |
| **Scavio TikTok Shop** | 8 | Product search, detail, reviews, categories, shop catalog |
| **Scavio Instagram** | 12 | Profile, posts, reels, stories, comments, search, follow graph |
| **Scavio Threads** | 6 | Profile, posts, replies, post, comments, user search |
| **Scavio X** | 11 | Search, post, comments, user timelines, follow graph, trending |
| **Scavio LinkedIn** | 9 | Person, company, their posts, job search and detail, post comments |
| **Scavio Kuaishou** | 14 | Profile, posts, video, comments, search, tag feed, trending |

Components that serve several endpoints use an **Endpoint** dropdown with
`real_time_refresh`, so only the fields the selected endpoint accepts are shown
and required. Every component has a **Table** output and a **Raw JSON** output;
the raw output is the untouched response body, credit counters included.

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
| Google (all verticals), Google Ads Transparency, Meta Ad Library | 1 |
| Amazon, eBay, Target, Zillow, Redfin, Booking, Airbnb, Glassdoor, App Store | 1 |
| SEC EDGAR, Companies House, Reddit, TikTok, TikTok Shop, X | 1 |
| Home Depot, TripAdvisor, Yelp, Indeed, Google Play, Capterra | 2 |
| G2 | 5 |
| YouTube search and shorts search | 2 |
| YouTube streams | 3 |
| YouTube transcript | 8 |
| Instagram user posts | 2 |
| Instagram post, comment replies | 8 |
| Instagram everything else | 10 |
| LinkedIn person, company, post | 1 |
| LinkedIn posts feeds, job search, post comments | 10 |
| LinkedIn job detail | 30 |
| Threads | 2 by `user_id`, 4 by `username` |
| Kuaishou | 1, 2, 10 or 40 depending on the endpoint |

Three surfaces are priced from the **request body** rather than the path, and
say so instead of quoting a flat number:

- **Walmart** search and category — 1 credit on `domain` `com`/`ca`, 2 on `com.mx`.
- **Threads** profile, user posts and user replies — 2 credits addressed by
  `user_id`, 4 by `username`, because the handle needs a second upstream lookup.
- **Extract** — 1 credit in `normal` or `advanced` mode, 2 in `ultra`, and billed
  only on a successful extraction.

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
- The Meta Ad Library lives at `/api/v1/meta-ads/*` — hyphenated. Do not derive
  that URL from the platform name.
- `/reddit/search` returns `data.results` with `next_cursor` and `has_more`.
  `/reddit/post` returns a **flat post object with no comments** — use the
  Post Comments endpoint for those. Subreddit and user feeds return `data.posts`.
- eBay's sold-listing view publishes no headline count, so `total_results` is
  null there. Listing a seller's whole catalogue is done with a keyword-less
  search scoped by `seller`, not through the seller profile endpoint.
- Meta Ad Library `spend`, `reach` and `impressions` are null on commercial ads;
  only political and issue ads carry them.
- TikTok, Instagram and Kuaishou responses are raw upstream passthrough, so their
  exact keys vary with which provider leg answered. The Raw JSON output is the
  reliable surface there.
- TikTok `cursor` is a **string**, not a number.

## Notes on input names

Two API fields cannot be used as input names because `Component` already owns the
attribute: `start` is a method and `user_id` is set by the runtime. They are
exposed as **Start Offset** (`start_offset`) and **User ID** (`target_user_id`)
and mapped back to their wire names through `Endpoint.wire`, so the API still
receives `start` and `user_id`.

## Tests

```bash
uv run pytest src/bundles/scavio/tests -q
uv run lfx extension validate src/bundles/scavio/src/lfx_scavio
uv run ruff check src/bundles/scavio && uv run ruff format --check src/bundles/scavio
```

The suite is fully offline (`httpx.Client` is patched) and guards endpoint
coverage, per-endpoint credit costs, the body-priced endpoints, the wire quirks
above, the flat-vs-`data` envelope split, and that no input name is shadowed by a
`Component` attribute.
