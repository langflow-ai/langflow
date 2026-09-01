import { expect, type Page } from "@playwright/test";

type FlowNode = {
  id?: string;
  data?: { node?: unknown };
};

type FlowRead = {
  data?: { nodes?: FlowNode[] };
};

function currentFlowId(page: Page): string {
  const match = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/);
  if (!match) throw new Error(`Expected a flow URL, received ${page.url()}`);
  return match[1];
}

function nodeSnapshotsById(nodes: FlowNode[]): Map<string, string> {
  return new Map(
    nodes.flatMap((node) =>
      node.id ? [[node.id, JSON.stringify(node.data?.node ?? null)]] : [],
    ),
  );
}

export async function updateOldComponents(page: Page) {
  const hasUpdateAllButton = await page
    .getByTestId("update-all-button")
    .count();
  if (hasUpdateAllButton === 0) {
    return;
  }
  const flowId = currentFlowId(page);
  const updateNodeIds = await page
    .locator(
      '.react-flow__node:has([data-testid="update-button"], [data-testid="review-button"])',
    )
    .evaluateAll((nodes) =>
      nodes.flatMap((node) => {
        const id = node.getAttribute("data-id");
        return id ? [id] : [];
      }),
    );
  if (updateNodeIds.length === 0) {
    throw new Error(
      "Update All is visible but no updatable canvas nodes exist",
    );
  }

  const beforeResponse = await page.request.get(`/api/v1/flows/${flowId}`);
  expect(beforeResponse.ok(), `GET flow ${flowId} before update`).toBeTruthy();
  const before = (await beforeResponse.json()) as FlowRead;
  const beforeSnapshots = nodeSnapshotsById(before.data?.nodes ?? []);

  // Updating the nodes schedules a debounced autosave after the success toast.
  // Wait for the PATCH containing every refreshed node so a later test helper
  // cannot be overwritten by that stale editor snapshot.
  const persistedUpdate = page.waitForResponse((response) => {
    const request = response.request();
    if (
      request.method() !== "PATCH" ||
      new URL(response.url()).pathname !== `/api/v1/flows/${flowId}`
    ) {
      return false;
    }
    const body = request.postDataJSON() as
      | { data?: { nodes?: FlowNode[] } }
      | undefined;
    const updatedSnapshots = nodeSnapshotsById(body?.data?.nodes ?? []);
    return updateNodeIds.every((id) => {
      const beforeSnapshot = beforeSnapshots.get(id);
      const updatedSnapshot = updatedSnapshots.get(id);
      return (
        beforeSnapshot !== undefined &&
        updatedSnapshot !== undefined &&
        updatedSnapshot !== beforeSnapshot
      );
    });
  });

  await page.getByTestId("update-all-button").click();
  await page.waitForSelector("text=successfully updated", { timeout: 10000 });
  const updateResponse = await persistedUpdate;
  expect(
    updateResponse.ok(),
    `Persisting updated components in flow ${flowId} returned ${updateResponse.status()}`,
  ).toBeTruthy();
}
