import { ENABLE_FETCH_CREDENTIALS } from "../feature-flags";

/**
 * Returns the credentials option for fetch requests based on the ENABLE_FETCH_CREDENTIALS flag.
 * When enabled, returns "include" to send cookies and credentials with cross-origin requests.
 * When disabled, returns undefined (default fetch behavior).
 *
 * @returns {RequestCredentials | undefined} The credentials option for fetch requests
 */
export function getFetchCredentials(): RequestCredentials | undefined {
  return ENABLE_FETCH_CREDENTIALS ? "include" : undefined;
}

/**
 * Returns the withCredentials option for axios requests based on the ENABLE_FETCH_CREDENTIALS flag.
 * When enabled, returns true to send cookies and credentials with cross-origin requests.
 * When disabled, returns false (default axios behavior).
 *
 * @returns {boolean} The withCredentials option for axios requests
 */
export function getAxiosWithCredentials(): boolean {
  return ENABLE_FETCH_CREDENTIALS;
}
