import { getBundleComponentLabel } from "../get-bundle-component-label";

describe("getBundleComponentLabel", () => {
  it.each([
    ["Slack", "Slack: On Message", "On Message"],
    ["Microsoft 365", "Microsoft 365: Calendar Event", "Calendar Event"],
    ["slack", "Slack: On Reaction", "On Reaction"],
  ])("shortens %s / %s to %s", (bundle, component, expected) => {
    expect(getBundleComponentLabel(bundle, component)).toBe(expected);
  });

  it.each([
    ["OpenAI", "OpenAI Embeddings"],
    ["Exa", "Exa Search"],
    ["DuckDuckGo", "DuckDuckGo Search"],
    ["Azure", "Azure OpenAI Embeddings"],
    ["Google", "Google Drive Loader"],
    ["Microsoft 365", "Outlook: Send Mail"],
    ["Slack", "Slacker"],
    ["Slack", "Slack:"],
  ])("keeps %s / %s as it is", (bundle, component) => {
    expect(getBundleComponentLabel(bundle, component)).toBe(component);
  });
});
