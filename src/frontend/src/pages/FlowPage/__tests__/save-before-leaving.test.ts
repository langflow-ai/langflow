import { saveBeforeLeaving } from "../save-before-leaving";

describe("saveBeforeLeaving", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it("returns to the editor when an explicit save fails", async () => {
    const proceed = jest.fn();
    const reset = jest.fn();
    const onSaved = jest.fn();

    await saveBeforeLeaving({
      saveFlow: jest.fn().mockRejectedValue(new Error("Forbidden")),
      autoSaving: false,
      proceed,
      reset,
      onSaved,
    });

    expect(proceed).not.toHaveBeenCalled();
    expect(reset).toHaveBeenCalledTimes(1);
    expect(onSaved).not.toHaveBeenCalled();

    jest.advanceTimersByTime(1200);
    expect(proceed).not.toHaveBeenCalled();
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("proceeds without reporting success when autosaving fails", async () => {
    const proceed = jest.fn();
    const reset = jest.fn();
    const onSaved = jest.fn();

    await saveBeforeLeaving({
      saveFlow: jest.fn().mockRejectedValue(new Error("Forbidden")),
      autoSaving: true,
      proceed,
      reset,
      onSaved,
    });

    expect(proceed).toHaveBeenCalledTimes(1);
    expect(reset).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();

    jest.advanceTimersByTime(1200);
    expect(proceed).toHaveBeenCalledTimes(1);
  });

  it("proceeds immediately and only once after a manual save", async () => {
    const proceed = jest.fn();
    const reset = jest.fn();
    const onSaved = jest.fn();

    await saveBeforeLeaving({
      saveFlow: jest.fn().mockResolvedValue(undefined),
      autoSaving: false,
      proceed,
      reset,
      onSaved,
    });

    expect(proceed).toHaveBeenCalledTimes(1);
    expect(reset).not.toHaveBeenCalled();
    expect(onSaved).toHaveBeenCalledTimes(1);

    jest.advanceTimersByTime(1200);
    expect(proceed).toHaveBeenCalledTimes(1);
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it("keeps the minimum delay before leaving after a quick autosave", async () => {
    const proceed = jest.fn();
    const reset = jest.fn();
    const onSaved = jest.fn();

    await saveBeforeLeaving({
      saveFlow: jest.fn().mockResolvedValue(undefined),
      autoSaving: true,
      proceed,
      reset,
      onSaved,
    });

    expect(proceed).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1199);
    expect(proceed).not.toHaveBeenCalled();

    jest.advanceTimersByTime(1);
    expect(proceed).toHaveBeenCalledTimes(1);
    expect(reset).not.toHaveBeenCalled();
    expect(onSaved).toHaveBeenCalledTimes(1);
  });
});
