import { readFileSync } from "node:fs";
import path from "node:path";
import { expect } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";
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
  await waitForFlowEditorReady(page);
}

async function openCheckedInYouTubeAnalysis(
  page: Parameters<typeof configureLoopbackOpenAI>[0],
) {
  await awaitBootstrapTest(page, {
    skipModal: true,
    seedFlowIfEmpty: false,
  });
  const templatePath = path.resolve(
    "..",
    "bundles",
    "lfx-bundles",
    "src",
    "lfx_bundles",
    "youtube",
    "starter_projects",
    "Youtube Analysis.json",
  );
  const template = JSON.parse(readFileSync(templatePath, "utf8")) as {
    data: { nodes: unknown[]; edges: unknown[]; viewport?: unknown };
    description?: string;
    tags?: string[];
  };
  const created = await page.request.post("/api/v1/flows/", {
    data: {
      name: `YouTube Analysis E2E ${Date.now()}`,
      description: template.description,
      data: template.data,
      tags: template.tags,
    },
  });
  if (created.status() !== 201) {
    throw new Error(
      `Creating the checked-in YouTube Analysis flow returned ${created.status()} ${await created.text()}`,
    );
  }
  const flow = (await created.json()) as { id: string };
  await page.goto(`/flow/${flow.id}`);
  await waitForFlowEditorReady(page);
}

withEventDeliveryModes(
  "YouTube Analysis",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await openCheckedInYouTubeAnalysis(page);

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await configureLoopbackOpenAI(page);
    await configureLoopbackYouTubeComponents(page);

    const [buildResponse] = await Promise.all([
      page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname === "/api/v2/workflows",
      ),
      page.getByTestId("button_run_chat output").last().click(),
    ]);
    expect(buildResponse.ok()).toBeTruthy();
    expect(await buildResponse.finished()).toBeNull();

    await page.getByTestId("playground-btn-flow-io").click();
    await expect(page.locator(".markdown").last()).toContainText(
      "Recommendations",
      {
        timeout: TIMEOUTS.buildComplete,
      },
    );

    const output = await page.locator(".markdown").last().innerText();
    expect(output).toContain("Synthesis");
    expect(output).toContain("Audience Reception");
    expect(output).toContain("Content Summary");
    expect(output).toContain("LOOPBACK_YOUTUBE_COMMENTS_USED");
    expect(output).toContain("LOOPBACK_YOUTUBE_TRANSCRIPT_USED");
  },
);
