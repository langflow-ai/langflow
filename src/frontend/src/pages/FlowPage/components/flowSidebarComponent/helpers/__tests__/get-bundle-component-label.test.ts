import { getBundleComponentLabel } from "../get-bundle-component-label";

describe("getBundleComponentLabel", () => {
  it.each([
    ["Slack", "Slack: On Message", "On Message"],
    ["Google", "Google Drive Loader", "Drive Loader"],
    ["Microsoft 365", "Microsoft 365: Calendar Event", "Calendar Event"],
    ["Microsoft 365", "Outlook: Send Mail", "Outlook: Send Mail"],
    ["Google", "Google", "Google"],
    ["Slack", "Slacker", "Slacker"],
  ])("shows %s / %s as %s", (bundle, component, expected) => {
    expect(getBundleComponentLabel(bundle, component)).toBe(expected);
  });
});
