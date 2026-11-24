import { workletUrl } from "../streamProcessor";

it("resolves the packaged worklet import to a URL in Jest", () => {
  expect(workletUrl).toBe("/assets/audio-worklet-processor.js");
});
