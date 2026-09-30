import { useExtensionEvents } from "@/hooks/extensions/use-extension-events";

export function ExtensionEventsListener() {
  useExtensionEvents();
  return null;
}

export default ExtensionEventsListener;
