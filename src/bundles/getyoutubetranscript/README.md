# lfx-getyoutubetranscript

GetYouTubeTranscript YouTube transcript component as a standalone Langflow Extension Bundle.

The bundle ships a single component, `GetYouTubeTranscriptComponent`, which
fetches the transcript of a YouTube video through the
[GetYouTubeTranscript API](https://getyoutubetranscript.com). It calls the
transcript endpoint directly with `httpx` and needs only a user-supplied API
key, so it carries no vendor SDK dependency. See the
[API docs](https://getyoutubetranscript.com/docs) for the API details.

## Install

```bash
pip install lfx-getyoutubetranscript
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the
`GetYouTubeTranscriptComponent` will appear in the palette's **Bundles** section
under **GetYouTubeTranscript**.

## Configure

Set the **GetYouTubeTranscript API Key** input to your own key from
[getyoutubetranscript.com](https://getyoutubetranscript.com). The component is
optional and does nothing until a key is supplied, so it changes nothing for
anyone who does not use it. Language and Include Timestamps are optional
advanced inputs.

In tool mode, the component exposes a single tool named `get_youtube_transcript`.

## Develop

```bash
cd src/bundles/getyoutubetranscript
pip install -e .
lfx extension validate src/lfx_getyoutubetranscript
```

## Manifest

The extension manifest is shipped at `src/lfx_getyoutubetranscript/extension.json`
and points at the bundle at `components/getyoutubetranscript`. The component
registers under the canonical namespaced ID
`ext:getyoutubetranscript:GetYouTubeTranscriptComponent@official`.
