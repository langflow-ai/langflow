import { expect } from "../../fixtures";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

const LOOPBACK_YOUTUBE_COMMENTS_CODE = `
import pandas as pd
from lfx.custom import Component
from lfx.io import BoolInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.dataframe import DataFrame

class YouTubeCommentsComponent(Component):
    display_name = "YouTube Comments"
    inputs = [
        MessageTextInput(name="video_url", display_name="Video URL", required=True),
        SecretStrInput(name="api_key", display_name="YouTube API Key", required=True),
        IntInput(name="max_results", display_name="Max Results", value=20),
        BoolInput(name="include_replies", display_name="Include Replies", value=False),
        BoolInput(name="include_metrics", display_name="Include Metrics", value=True),
    ]
    outputs = [Output(name="comments", display_name="Comments", method="get_video_comments")]

    def get_video_comments(self) -> DataFrame:
        return DataFrame(pd.DataFrame([
            {"author": "loopback-user", "text": "LOOPBACK_YOUTUBE_COMMENTS_USED Clear and useful Langflow walkthrough", "like_count": 7},
            {"author": "fixture-user", "text": "The practical workflow example was helpful", "like_count": 4},
        ]))
`;

const LOOPBACK_YOUTUBE_TRANSCRIPTS_CODE = `
from lfx.custom import Component
from lfx.io import MultilineInput, Output
from lfx.schema import Data

class YouTubeTranscriptsComponent(Component):
    display_name = "YouTube Transcripts"
    inputs = [
        MultilineInput(
            name="url",
            display_name="Video URL",
            tool_mode=True,
            required=True,
        ),
    ]
    outputs = [Output(name="data_output", display_name="Transcript + Source", method="youtube_transcript")]

    def youtube_transcript(self) -> Data:
        return Data(data={
            "marker": "LOOPBACK_YOUTUBE_TRANSCRIPT_USED",
            "transcript": "A deterministic Langflow workflow demonstration with practical component examples.",
            "video_url": self.url,
        })
`;

async function configureLoopbackYouTubeComponents(
  page: Parameters<typeof configureLoopbackOpenAI>[0],
) {
  const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
  expect(flowId).toBeTruthy();
  const response = await page.request.get(`/api/v1/flows/${flowId}`);
  expect(response.ok()).toBeTruthy();
  const flow = await response.json();
  const commentsNode = flow.data.nodes.find(
    (node: { data?: { type?: string } }) =>
      node.data?.type === "YouTubeCommentsComponent",
  );
  expect(commentsNode).toBeTruthy();
  const transcriptsNode = flow.data.nodes.find(
    (node: { data?: { type?: string } }) =>
      node.data?.type === "YouTubeTranscripts",
  );
  expect(transcriptsNode).toBeTruthy();
  commentsNode.data.node.template.code.value = LOOPBACK_YOUTUBE_COMMENTS_CODE;
  commentsNode.data.node.template.api_key.value = "youtube-loopback-key";
  transcriptsNode.data.node.template.code.value =
    LOOPBACK_YOUTUBE_TRANSCRIPTS_CODE;
  const update = await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: flow.data },
  });
  expect(update.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByTestId("react-flow-id")).toBeVisible({
    timeout: 30_000,
  });
}

withEventDeliveryModes(
  "YouTube Analysis",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await page.goto("/");
    await openStarterProject(page, "YouTube Analysis");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await configureLoopbackOpenAI(page);
    await configureLoopbackYouTubeComponents(page);

    await page.getByTestId("button_run_chat output").last().click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 120_000,
    });

    await page.getByTestId("playground-btn-flow-io").click();
    await expect(page.getByText("Finished", { exact: true })).toBeVisible({
      timeout: 120_000,
    });

    const output = await page.locator(".markdown").last().innerText();
    expect(output).toContain("Recommendations");
    expect(output).toContain("Synthesis");
    expect(output).toContain("Audience Reception");
    expect(output).toContain("Content Summary");
    expect(output).toContain("LOOPBACK_YOUTUBE_COMMENTS_USED");
    expect(output).toContain("LOOPBACK_YOUTUBE_TRANSCRIPT_USED");
  },
);
