import type { Page } from "@playwright/test";
import { execFileSync } from "child_process";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// The exact response headers the backend's guard middleware sends with
// LANGFLOW_GUARD_SECURITY_HEADERS on, taken from a live request rather than
// copied here, so the check follows any change to the backend policy.
const GUARD_HEADER_PROBE = `
import asyncio, json, os
os.environ["LANGFLOW_GUARD_ENABLED"] = "true"
os.environ["LANGFLOW_GUARD_SECURITY_HEADERS"] = "true"
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langflow.services.security import attach_guard

app = FastAPI()
app.get("/")(lambda: {})
attach_guard(app)

async def main():
    transport = ASGITransport(app=app, client=("127.0.0.1", 50000))
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")
    print(json.dumps(dict(response.headers)))

asyncio.run(main())
`;

function guardSecurityHeaders(): Record<string, string> {
  const output = execFileSync(
    "uv",
    ["run", "--no-sync", "python", "-c", GUARD_HEADER_PROBE],
    { cwd: path.join(__dirname, "../../../../.."), encoding: "utf8" },
  );
  const headers: Record<string, string> = JSON.parse(
    output.trim().split("\n").pop()!,
  );
  delete headers["content-length"];
  delete headers["content-type"];
  return headers;
}

test.use({
  launchOptions: {
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
    ],
  },
  permissions: ["microphone"],
});

async function microphoneAccessUnder(
  page: Page,
  securityHeaders: Record<string, string>,
) {
  await page.route("**/*", async (route) => {
    if (route.request().resourceType() !== "document") {
      await route.continue();
      return;
    }
    const response = await route.fetch();
    await route.fulfill({
      response,
      headers: { ...response.headers(), ...securityHeaders },
    });
  });
  await awaitBootstrapTest(page);
  // The same call the voice assistant makes (use-start-recording.ts).
  return page.evaluate(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      stream.getTracks().forEach((track) => track.stop());
      return "granted";
    } catch (error) {
      return (error as DOMException).name;
    }
  });
}

test(
  "guard security headers keep the voice assistant's microphone",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const headers = guardSecurityHeaders();
    expect(headers["permissions-policy"]).toContain("microphone=(self)");
    expect(await microphoneAccessUnder(page, headers)).toBe("granted");
  },
);

test(
  "a Permissions-Policy without microphone blocks the voice assistant",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const headers = {
      ...guardSecurityHeaders(),
      "permissions-policy": "geolocation=(), microphone=(), camera=()",
    };
    expect(await microphoneAccessUnder(page, headers)).toBe("NotAllowedError");
  },
);
