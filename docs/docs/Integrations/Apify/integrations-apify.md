---
title: Apify
slug: /integrations-apify
---

# Integrate Apify with Langflow

[Apify](https://apify.com/) is a platform that enables you to automate web scraping, data extraction, and other tasks using Apify Actors.

The Apify components allow you to run Apify Actors in your flow to accomplish tasks such as:

- Crawling websites and extracting text content
- Scraping social media platforms like Instagram and Facebook
- Extracting data from Google Maps
- Inserting data into a PostgreSQL/MySQL/MSSQL database
- Running various other automation tasks

More info about Apify:

- [Website](https://apify.com/)
- [Apify Store](https://apify.com/store)
- [Actor Whitepaper](https://whitepaper.actor/)

## Prerequisites

You need an **Apify API token**. You can create a free account on [Apify](https://apify.com/) and generate your API key in the Apify Console. [Get a Free API key here](https://docs.apify.com/platform/integrations/api).

Enter the key in the *Apify Token* field in all components that require the key.

## Example flow

This example flow demonstrates the use of multiple Apify Actors to complete a comprehensive web scraping task. The flow includes a Google Search Results Scraper Actor that extracts search results from Google and a TikTok Data Extractor Actor that gathers data from TikTok. Initially, the agent collects social media links related to an entity (person, company, etc.) from Google. It then utilizes the TikTok Data Extractor to retrieve data and videos from the corresponding TikTok profile.
![Apify Agent Flow](./apify_agent_flow.png)

## Components

### Apify Actors

This component allows you to run Apify Actors in your flow. It can be used manually by providing run input or integrated as a tool for an AI Agent. When used with an AI Agent, the agent can leverage the Apify Actors to perform various tasks.

- **Input**:
    - Apify Token: Your API key.
    - Actor: The Apify Actor to run. Example: `apify/website-content-crawler`.
    - Run Input: The JSON input for configuring the Actor run.

- **Output**:
    - Actor Run Result: The JSON response containing the output of the Actor run.

- **Manual Usage**:
    - Create the Apify Actors component.
    - Input the Apify Token, an Actor ID, and configure the Run Input JSON.
      - Example input can be obtained from the Actor documentation Input section in the JSON Example tab. See [Website Content Crawler](https://apify.com/apify/website-content-crawler/input-schema).
    - Run the component manually to retrieve data.

- **AI Agent Integration**:
    - Create the Apify Actors component.
    - Input the Apify Token and an Actor ID.
    - Connect the component Tool output to the Agent, allowing it to trigger the Actor as needed.

## Popular Apify Actors

### Website Content Crawler
**Actor ID:** `apify/website-content-crawler`
Crawl websites and extract text content to feed AI models, LLM applications, vector databases, or RAG pipelines. Supports rich formatting using Markdown, cleans HTML, downloads files, and integrates with tools like LangChain and LlamaIndex.

### Instagram Scraper
**Actor ID:** `apify/instagram-scraper`
Scrape and download Instagram posts, profiles, places, hashtags, photos, and comments. Get data from Instagram using URLs or search queries. Export scraped data, run the scraper via API, and integrate with other tools.

### Google Maps Extractor
**Actor ID:** `compass/google-maps-extractor`
Extract business data from Google Maps, including addresses, contact info, opening hours, prices, and more. Scrape by keyword, category, location, URLs, and other filters. Export data, schedule runs, and integrate with other platforms.

### TikTok Data Extractor
**Actor ID:** `clockworks/free-tiktok-scraper`
Extract data about videos, users, and channels based on hashtags or scrape full user profiles including posts, total likes, name, nickname, number of comments, shares, followers, following, and more.

### Facebook Posts Scraper
**Actor ID:** `apify/facebook-posts-scraper`
Scrape hundreds of Facebook posts from pages and profiles. Extract post text, URLs, timestamps, number of likes, shares, comments, and more. Download the data in JSON, CSV, or Excel formats.

For more Actors, explore the [Apify Store](https://apify.com/store).
