import { readFileSync } from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";
import { expect } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";
import {
  applyLoopbackToFlowData,
  type LoopbackFlowData,
  type LoopbackNode,
} from "../../utils/loopback-provider-policy.mjs";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";
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

const LOOPBACK_YOUTUBE_TRANSCRIPTS_TOOL_METADATA = [
  {
    args: {
      url: {
        description: "Enter the YouTube video URL to get transcripts from.",
        title: "Url",
        type: "string",
      },
    },
    description: "Returns a deterministic transcript for a YouTube video.",
    display_description:
      "Returns a deterministic transcript for a YouTube video.",
    display_name: "youtube_transcript",
    name: "youtube_transcript",
    readonly: false,
    status: true,
    tags: ["youtube_transcript"],
  },
];

type TemplateField = { value?: unknown };

function templateField(node: LoopbackNode, name: string): TemplateField {
  const field = node.data?.node?.template?.[name];
  expect(field, `${node.data?.type} is missing template.${name}`).toBeTruthy();
  return field as TemplateField;
}

function configureLoopbackYouTubeAnalysis(
  sourceData: LoopbackFlowData,
): LoopbackFlowData {
  const { data, targetNodeIds } = applyLoopbackToFlowData(sourceData);
  expect(
    targetNodeIds.length,
    "YouTube Analysis must contain an OpenAI-compatible model input",
  ).toBeGreaterThan(0);

  const commentsNode = data.nodes?.find(
    (node) => node.data?.type === "YouTubeCommentsComponent",
  );
  expect(commentsNode).toBeTruthy();
  const transcriptsNode = data.nodes?.find(
    (node) => node.data?.type === "YouTubeTranscripts",
  );
  expect(transcriptsNode).toBeTruthy();

  templateField(commentsNode!, "code").value = LOOPBACK_YOUTUBE_COMMENTS_CODE;
  templateField(commentsNode!, "api_key").value = "youtube-loopback-key";
  templateField(transcriptsNode!, "code").value =
    LOOPBACK_YOUTUBE_TRANSCRIPTS_CODE;
  templateField(transcriptsNode!, "tools_metadata").value =
    LOOPBACK_YOUTUBE_TRANSCRIPTS_TOOL_METADATA;

  return data;
}

async function openCheckedInYouTubeAnalysis(page: Page) {
  await seedLoopbackProvider(page);
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
    data: LoopbackFlowData;
    description?: string;
    tags?: string[];
  };
  // Seed every deterministic dependency before the editor mounts. Patching and
  // reloading after mount races model/component refreshes and their autosaves on
  // slower runners, which can restore the live model or submit stale tool metadata.
  const data = configureLoopbackYouTubeAnalysis(template.data);
  const created = await page.request.post("/api/v1/flows/", {
    data: {
      name: `YouTube Analysis E2E ${Date.now()}`,
      description: template.description,
      data,
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

    await configureLoopbackOpenAI(page, { skipUpdateOldComponents: true });

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
