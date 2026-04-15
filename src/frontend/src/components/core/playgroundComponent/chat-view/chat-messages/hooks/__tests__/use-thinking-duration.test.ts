import { act, renderHook } from "@testing-library/react";
import {
  useThinkingDurationStore,
  useTrackThinkingDuration,
} from "../use-thinking-duration";

describe("useThinkingDurationStore", () => {
  beforeEach(() => {
    // Reset the store before each test
    useThinkingDurationStore.setState({
      startTime: null,
      duration: null,
    });
  });

  it("initializes with null values", () => {
    const state = useThinkingDurationStore.getState();
    expect(state.startTime).toBeNull();
    expect(state.duration).toBeNull();
  });

  it("sets start time and clears duration", () => {
    const { setStartTime } = useThinkingDurationStore.getState();
    const now = Date.now();

    act(() => {
      setStartTime(now);
    });

    const state = useThinkingDurationStore.getState();
    expect(state.startTime).toBe(now);
    expect(state.duration).toBeNull();
  });

  it("sets duration and clears start time", () => {
    const { setDuration } = useThinkingDurationStore.getState();

    act(() => {
      setDuration(5000);
    });

    const state = useThinkingDurationStore.getState();
    expect(state.duration).toBe(5000);
    expect(state.startTime).toBeNull();
  });

  it("resets both values", () => {
    const { setStartTime, setDuration, reset } =
      useThinkingDurationStore.getState();

    act(() => {
      setStartTime(Date.now());
      setDuration(5000);
    });

    act(() => {
      reset();
    });

    const state = useThinkingDurationStore.getState();
    expect(state.startTime).toBeNull();
    expect(state.duration).toBeNull();
  });
});

describe("useTrackThinkingDuration", () => {
  beforeEach(() => {
    useThinkingDurationStore.setState({
      startTime: null,
      duration: null,
    });
  });

  it("sets start time when building starts", () => {
    const { result, rerender } = renderHook(
      ({ isBuilding }) => useTrackThinkingDuration(isBuilding),
      { initialProps: { isBuilding: false } },
    );

    // Start building
    rerender({ isBuilding: true });

    const state = useThinkingDurationStore.getState();
    expect(state.startTime).not.toBeNull();
    expect(state.duration).toBeNull();
  });

  it("sets duration when building stops", () => {
    const { rerender } = renderHook(
      ({ isBuilding }) => useTrackThinkingDuration(isBuilding),
      { initialProps: { isBuilding: false } },
    );

    // Start building
    rerender({ isBuilding: true });

    // Wait a bit to accumulate some time
    const startTime = useThinkingDurationStore.getState().startTime;
    expect(startTime).not.toBeNull();

    // Stop building
    rerender({ isBuilding: false });

    const state = useThinkingDurationStore.getState();
    expect(state.duration).not.toBeNull();
    expect(state.duration).toBeGreaterThanOrEqual(0);
    expect(state.startTime).toBeNull();
  });

  it("does not set duration if building never started", () => {
    const { rerender } = renderHook(
      ({ isBuilding }) => useTrackThinkingDuration(isBuilding),
      { initialProps: { isBuilding: false } },
    );

    // Toggle without ever starting
    rerender({ isBuilding: false });

    const state = useThinkingDurationStore.getState();
    expect(state.startTime).toBeNull();
    expect(state.duration).toBeNull();
  });
});
