import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { StepperProvider, useStepper } from "../../StepperProvider";
import type { StepperStepConfig } from "../../types";
import { useStepperState } from "../useStepperState";

const step = (
  id: string,
  canNext?: boolean | (() => boolean),
): StepperStepConfig => ({ id, canNext });

const THREE_STEPS = [step("source"), step("configuration"), step("review")];
const FOUR_STEPS = [
  step("provider"),
  step("type"),
  step("flows"),
  step("review"),
];

describe("useStepperState", () => {
  describe("initial state", () => {
    it("starts at step 1 by default", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: THREE_STEPS }),
      );
      expect(result.current.currentStep).toBe(1);
      expect(result.current.currentStepIndex).toBe(0);
      expect(result.current.currentStepId).toBe("source");
      expect(result.current.totalSteps).toBe(3);
      expect(result.current.isFirstStep).toBe(true);
      expect(result.current.isLastStep).toBe(false);
    });

    it("starts at a custom initialStep", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: FOUR_STEPS, initialStep: 2 }),
      );
      expect(result.current.currentStep).toBe(2);
      expect(result.current.currentStepId).toBe("type");
    });

    it("clamps initialStep into the step list", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: THREE_STEPS, initialStep: 9 }),
      );
      expect(result.current.currentStep).toBe(3);
    });

    it("degrades without crashing on an empty step list", () => {
      const { result } = renderHook(() => useStepperState({ steps: [] }));
      expect(result.current.currentStep).toBe(0);
      expect(result.current.currentStepId).toBe("");
      expect(result.current.totalSteps).toBe(0);
      expect(result.current.canGoNext).toBe(false);
      expect(result.current.canGoBack).toBe(false);
    });
  });

  describe("next", () => {
    it("advances one step", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: THREE_STEPS }),
      );
      act(() => result.current.next());
      expect(result.current.currentStep).toBe(2);
      expect(result.current.currentStepId).toBe("configuration");
    });

    it("is a no-op on the last step", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: THREE_STEPS, initialStep: 3 }),
      );
      act(() => result.current.next());
      expect(result.current.currentStep).toBe(3);
    });

    it("is gated by a boolean canNext on the current step", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: [step("one", false), step("two")] }),
      );
      expect(result.current.canGoNext).toBe(false);
      act(() => result.current.next());
      expect(result.current.currentStep).toBe(1);
    });

    it("is gated by a function canNext and re-evaluates it per render", () => {
      let valid = false;
      const steps = [step("one", () => valid), step("two")];
      const { result, rerender } = renderHook(() => useStepperState({ steps }));
      expect(result.current.canGoNext).toBe(false);
      act(() => result.current.next());
      expect(result.current.currentStep).toBe(1);

      valid = true;
      rerender();
      expect(result.current.canGoNext).toBe(true);
      act(() => result.current.next());
      expect(result.current.currentStep).toBe(2);
    });

    it("only gates the step that declares canNext", () => {
      const { result } = renderHook(() =>
        useStepperState({
          steps: [step("one"), step("two", false), step("three")],
        }),
      );
      act(() => result.current.next());
      expect(result.current.currentStep).toBe(2);
      expect(result.current.canGoNext).toBe(false);
      act(() => result.current.next());
      expect(result.current.currentStep).toBe(2);
    });
  });

  describe("back", () => {
    it("goes back one step down to the default floor of 1", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: THREE_STEPS, initialStep: 2 }),
      );
      act(() => result.current.back());
      expect(result.current.currentStep).toBe(1);
      act(() => result.current.back());
      expect(result.current.currentStep).toBe(1);
    });

    it("respects a custom minStep floor (preselected opening)", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: FOUR_STEPS, initialStep: 2, minStep: 2 }),
      );
      expect(result.current.canGoBack).toBe(false);
      expect(result.current.isFirstStep).toBe(true);
      act(() => result.current.back());
      expect(result.current.currentStep).toBe(2);
    });

    it("allows going back below the initial step when minStep stays 1 (auto-skip)", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: THREE_STEPS, initialStep: 2 }),
      );
      expect(result.current.canGoBack).toBe(true);
      act(() => result.current.back());
      expect(result.current.currentStep).toBe(1);
    });
  });

  describe("goTo", () => {
    it("jumps to a step by 1-based number", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: FOUR_STEPS }),
      );
      act(() => result.current.goTo(3));
      expect(result.current.currentStepId).toBe("flows");
    });

    it("jumps to a step by id", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: FOUR_STEPS }),
      );
      act(() => result.current.goTo("review"));
      expect(result.current.currentStep).toBe(4);
    });

    it("ignores an unknown step id", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: FOUR_STEPS, initialStep: 2 }),
      );
      act(() => result.current.goTo("nope"));
      expect(result.current.currentStep).toBe(2);
    });

    it("clamps numeric targets into [minStep, totalSteps]", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: FOUR_STEPS, minStep: 2, initialStep: 3 }),
      );
      act(() => result.current.goTo(99));
      expect(result.current.currentStep).toBe(4);
      act(() => result.current.goTo(1));
      expect(result.current.currentStep).toBe(2);
    });
  });

  describe("conditional steps (computed list)", () => {
    it("clamps the exposed step when the list shrinks and restores when it grows back", () => {
      const { result, rerender } = renderHook(
        ({ steps }: { steps: StepperStepConfig[] }) =>
          useStepperState({ steps }),
        { initialProps: { steps: FOUR_STEPS } },
      );
      act(() => result.current.goTo(4));
      expect(result.current.currentStep).toBe(4);

      rerender({ steps: FOUR_STEPS.slice(0, 2) });
      expect(result.current.currentStep).toBe(2);
      expect(result.current.currentStepId).toBe("type");
      expect(result.current.isLastStep).toBe(true);

      rerender({ steps: FOUR_STEPS });
      expect(result.current.currentStep).toBe(4);
    });

    it("navigates from the clamped step, not the stale one", () => {
      const { result, rerender } = renderHook(
        ({ steps }: { steps: StepperStepConfig[] }) =>
          useStepperState({ steps }),
        { initialProps: { steps: FOUR_STEPS } },
      );
      act(() => result.current.goTo(4));
      rerender({ steps: FOUR_STEPS.slice(0, 3) });
      expect(result.current.currentStep).toBe(3);
      act(() => result.current.back());
      expect(result.current.currentStep).toBe(2);
    });
  });

  describe("busy gating (busy finish)", () => {
    it("gates next/back/goTo and reports canGoNext/canGoBack false while busy", () => {
      const { result, rerender } = renderHook(
        ({ isBusy }: { isBusy: boolean }) =>
          useStepperState({ steps: THREE_STEPS, initialStep: 2, isBusy }),
        { initialProps: { isBusy: true } },
      );
      expect(result.current.isBusy).toBe(true);
      expect(result.current.canGoNext).toBe(false);
      expect(result.current.canGoBack).toBe(false);

      act(() => result.current.next());
      act(() => result.current.back());
      act(() => result.current.goTo(1));
      expect(result.current.currentStep).toBe(2);

      rerender({ isBusy: false });
      expect(result.current.canGoNext).toBe(true);
      act(() => result.current.next());
      expect(result.current.currentStep).toBe(3);
    });

    it("still resets while busy (cancel + reopen fresh)", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: THREE_STEPS, initialStep: 3, isBusy: true }),
      );
      act(() => result.current.goTo(1));
      expect(result.current.currentStep).toBe(3);
      act(() => result.current.reset());
      expect(result.current.currentStep).toBe(3);

      const movable = renderHook(() =>
        useStepperState({ steps: THREE_STEPS, isBusy: true }),
      );
      act(() => movable.result.current.reset());
      expect(movable.result.current.currentStep).toBe(1);
    });
  });

  describe("onStepChange", () => {
    it("fires with (from, to) on committed next/back/goTo", () => {
      const onStepChange = jest.fn();
      const { result } = renderHook(() =>
        useStepperState({ steps: FOUR_STEPS, onStepChange }),
      );
      act(() => result.current.next());
      expect(onStepChange).toHaveBeenLastCalledWith(1, 2);
      act(() => result.current.goTo("review"));
      expect(onStepChange).toHaveBeenLastCalledWith(2, 4);
      act(() => result.current.back());
      expect(onStepChange).toHaveBeenLastCalledWith(4, 3);
      expect(onStepChange).toHaveBeenCalledTimes(3);
    });

    it("does not fire on gated or same-step transitions", () => {
      const onStepChange = jest.fn();
      const { result } = renderHook(() =>
        useStepperState({
          steps: [step("one", false), step("two")],
          onStepChange,
        }),
      );
      act(() => result.current.next());
      act(() => result.current.back());
      act(() => result.current.goTo(1));
      expect(onStepChange).not.toHaveBeenCalled();
    });
  });

  describe("reset", () => {
    it("returns to the initial step", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: FOUR_STEPS, initialStep: 2 }),
      );
      act(() => result.current.goTo(4));
      act(() => result.current.reset());
      expect(result.current.currentStep).toBe(2);
    });
  });

  describe("progress", () => {
    it("uses the indicators' (current-1)/(total-1) formula", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: FOUR_STEPS, initialStep: 3 }),
      );
      expect(result.current.progressPercent).toBeCloseTo((2 / 3) * 100);
    });

    it("reports 100 for a single-step list instead of dividing by zero", () => {
      const { result } = renderHook(() =>
        useStepperState({ steps: [step("only")] }),
      );
      expect(result.current.progressPercent).toBe(100);
      expect(result.current.isLastStep).toBe(true);
    });
  });
});

describe("StepperProvider / useStepper", () => {
  it("provides the transition state to descendants", () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <StepperProvider steps={THREE_STEPS} initialStep={1}>
        {children}
      </StepperProvider>
    );
    const { result } = renderHook(() => useStepper(), { wrapper });
    expect(result.current.currentStepId).toBe("source");
    act(() => result.current.next());
    expect(result.current.currentStep).toBe(2);
  });

  it("throws when used outside a StepperProvider", () => {
    const consoleError = jest
      .spyOn(console, "error")
      .mockImplementation(() => {});
    expect(() => renderHook(() => useStepper())).toThrow(
      "useStepper must be used within a StepperProvider",
    );
    consoleError.mockRestore();
  });
});
