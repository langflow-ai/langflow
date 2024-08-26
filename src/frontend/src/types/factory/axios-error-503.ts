import { AxiosError, AxiosHeaders } from "axios";

export const createNewError503 = (): AxiosError => {
  const headers = new AxiosHeaders({
    "Content-Type": "application/json",
  });

  const config = {
    url: "/",
    method: "get",
    headers: headers,
  };

  const error = new AxiosError("Server Busy", "ECONNABORTED", config, null, {
    status: 503,
    statusText: "Service Unavailable",
    data: "Server is currently busy, please try again later.",
    headers: {},
    config: config,
  });

  return error;
};
