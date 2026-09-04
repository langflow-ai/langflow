import { useInitializeAudio } from "../use-initialize-audio";

describe("useInitializeAudio", () => {
  it("does not start a stale conversation after audio resume settles", async () => {
    let resolveResume: (() => void) | undefined;
    const resume = jest.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveResume = resolve;
        }),
    );
    const audioContextRef = {
      current: { state: "suspended", resume } as unknown as AudioContext,
    };
    const startConversation = jest.fn();
    let isCurrent = true;

    const initialization = useInitializeAudio(
      audioContextRef,
      jest.fn(),
      startConversation,
      () => isCurrent,
    );
    isCurrent = false;
    resolveResume?.();
    await initialization;

    expect(startConversation).not.toHaveBeenCalled();
  });
});
