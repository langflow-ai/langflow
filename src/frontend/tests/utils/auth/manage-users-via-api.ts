import type { APIRequestContext, Page } from "@playwright/test";
import { expect } from "../../fixtures";

export type ApiUser = {
  id: string;
  username: string;
  is_active: boolean;
};

async function assertOk(
  response: Awaited<ReturnType<APIRequestContext["post"]>>,
  action: string,
): Promise<void> {
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`${action} failed (${response.status()}): ${body}`);
  }
}

/**
 * Create a user and mark them active via the admin user APIs.
 *
 * The OSS Admin Page UI was removed; these endpoints remain available to an
 * authenticated superuser session (cookies from the current page context).
 */
export async function createActiveUserViaApi(
  page: Page,
  { username, password }: { username: string; password: string },
): Promise<ApiUser> {
  const createResponse = await page.request.post("/api/v1/users/", {
    data: { username, password },
  });
  await assertOk(createResponse, "Create user");
  const created = (await createResponse.json()) as ApiUser;

  const patchResponse = await page.request.patch(
    `/api/v1/users/${created.id}`,
    {
      data: { is_active: true },
    },
  );
  await assertOk(patchResponse, "Activate user");
  const activated = (await patchResponse.json()) as ApiUser;
  expect(activated.is_active).toBe(true);
  expect(activated.username).toBe(username);
  return activated;
}

export async function updateUserViaApi(
  page: Page,
  userId: string,
  data: { username?: string; is_active?: boolean },
): Promise<ApiUser> {
  const response = await page.request.patch(`/api/v1/users/${userId}`, {
    data,
  });
  await assertOk(response, "Update user");
  return (await response.json()) as ApiUser;
}

export async function deleteUserViaApi(
  page: Page,
  userId: string,
): Promise<void> {
  const response = await page.request.delete(`/api/v1/users/${userId}`);
  await assertOk(response, "Delete user");
}
