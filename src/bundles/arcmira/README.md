# lfx-arcmira

Find the moment something was said on YouTube, including podcasts on YouTube: the exact quote, often who said it, the channel, the date and a watch link cued to the second. Filter by who is speaking, by the person or company discussed, and by sponsored or organic passages. Use one topic per call, and resolve names to ids before filtering. An empty result does not prove something was never said.

## Install

```bash
uv pip install lfx-arcmira
```

## Components

- **Arcmira Search** returns the passages that match a topic, including podcasts on YouTube, with the channel, the publish date and often who said it.
- **Arcmira Resolve** turns a name into an id for the search filters.

Both take one secret API key input.

[Arcmira](https://arcmira.com) · [API documentation](https://arcmira.com/docs)
