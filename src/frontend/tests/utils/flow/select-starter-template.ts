import {
  expect,
  type Page,
  type Request,
  type Response,
} from "@playwright/test";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

type ObservedResponse = {
  response: Response;
  sequence: number;
};

function requestDeletesFlow(request: Request, flowId: string): boolean {
  if (
    request.method() !== "DELETE" ||
    new URL(request.url()).pathname !== "/api/v1/flows/"
  ) {
    return false;
  }

  try {
    const body = request.postDataJSON();
    return Array.isArray(body) && body.includes(flowId);
  } catch {
    return false;
  }
}

function isHeaderFlowRefresh(response: Response): boolean {
  const url = new URL(response.url());
  return (
    response.request().method() === "GET" &&
    url.pathname === "/api/v1/flows/" &&
    url.searchParams.get("header_flows") === "true"
  );
}

async function assertResponseFinished(
  response: Response,
  description: string,
): Promise<void> {
  expect(
    response.ok(),
    `${description} returned ${response.status()} ${response.statusText()}`,
  ).toBeTruthy();
  expect(await response.finished(), `${description} did not finish`).toBeNull();
}

export async function selectStarterTemplate(
  page: Page,
  templateName: string,
): Promise<string> {
  await page.getByTestId(TID.sideNavAllTemplates).click();
  const template = page
    .getByRole("dialog")
    .getByTestId(`template-${templateName.replace(/ /g, "-").toLowerCase()}`);
  await expect(template).toBeVisible({ timeout: TIMEOUTS.standard });

  const placeholderFlowId = new URL(page.url()).pathname.match(
    /\/flow\/([^/?#]+)/,
  )?.[1];
  expect(
    placeholderFlowId,
    "A starter template must be selected from its blank placeholder flow",
  ).toBeTruthy();

  let sequence = 0;
  const responseSequences = new Map<Response, number>();
  const cleanupResponses: ObservedResponse[] = [];
  const headerRefreshResponses: ObservedResponse[] = [];
  const observeResponse = (response: Response) => {
    const observed = { response, sequence: sequence++ };
    responseSequences.set(response, observed.sequence);
    if (requestDeletesFlow(response.request(), placeholderFlowId!)) {
      cleanupResponses.push(observed);
    }
    if (isHeaderFlowRefresh(response)) {
      headerRefreshResponses.push(observed);
    }
  };
  page.on("response", observeResponse);

  try {
    const [createResponse] = await Promise.all([
      page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname === "/api/v1/flows/",
      ),
      template.click(),
    ]);
    expect(
      createResponse.ok(),
      `Creating starter template ${templateName} returned ${createResponse.status()}`,
    ).toBe(true);

    const createdFlow = await createResponse.json();
    const createdFlowId = (createdFlow as { id?: unknown })?.id;
    expect(
      typeof createdFlowId === "string" && createdFlowId.length > 0,
      `Creating starter template ${templateName} returned no flow id`,
    ).toBe(true);

    await page.waitForURL(
      (url) =>
        new RegExp(`^/flow/${createdFlowId}(?:/folder/[^/?#]+)?/?$`).test(
          url.pathname,
        ),
      { timeout: TIMEOUTS.standard },
    );

    const createSequence = responseSequences.get(createResponse) ?? -1;
    await expect
      .poll(
        () => {
          const cleanupResponse = cleanupResponses.find(
            (observed) => observed.sequence > createSequence,
          );
          return (
            cleanupResponse !== undefined &&
            headerRefreshResponses.some(
              (observed) => observed.sequence > cleanupResponse.sequence,
            )
          );
        },
        {
          message:
            "Starter flow navigation must finish placeholder cleanup and refresh the flow inventory",
          timeout: TIMEOUTS.standard,
        },
      )
      .toBe(true);

    const cleanupResponse = cleanupResponses.find(
      (observed) => observed.sequence > createSequence,
    )!;
    const headerRefreshResponse = headerRefreshResponses.find(
      (observed) => observed.sequence > cleanupResponse.sequence,
    )!.response;
    await Promise.all([
      assertResponseFinished(
        cleanupResponse.response,
        "Deleting starter placeholder",
      ),
      assertResponseFinished(
        headerRefreshResponse,
        "Refreshing flow inventory",
      ),
    ]);

    return createdFlowId as string;
  } finally {
    page.off("response", observeResponse);
  }
}
