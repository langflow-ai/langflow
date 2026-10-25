import { BASENAME } from "../config-constants";

export function customA2aPublishOrigin(): string {
  return `${window.location.origin}${BASENAME}`;
}
