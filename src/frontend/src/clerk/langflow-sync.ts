import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { CLERK_DUMMY_PASSWORD } from "@/constants/clerk";

export async function ensureLangflowUser(token: string, username: string) {
  try {
    await api.get(`${getURL("USERS")}/whoami`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (err: any) {
    if (err?.response?.status === 404) {
      await api.post(
        `${getURL("USERS")}/`,
        { username, password: CLERK_DUMMY_PASSWORD },
        { headers: { Authorization: `Bearer ${token}` } },
      );
    } else {
      throw err;
    }
  }
}

export async function backendLogin(username: string) {
  const res = await api.post(
    `${getURL("LOGIN")}`,
    new URLSearchParams({
      username,
      password: CLERK_DUMMY_PASSWORD,
    }).toString(),
    {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    },
  );
  return res.data;
}
