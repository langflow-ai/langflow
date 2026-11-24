import { act, renderHook } from "@testing-library/react";
import { useIsOwnedByCurrentUser } from "@/hooks/use-is-owned-by-current-user";
import useAuthStore from "@/stores/authStore";
import type { Users } from "@/types/api";

const signInAs = (id: string | null) =>
  act(() => {
    useAuthStore.setState({
      userData: id === null ? null : ({ id } as Users),
    });
  });

describe("useIsOwnedByCurrentUser", () => {
  afterEach(() => signInAs(null));

  it("should_return_true_when_the_owner_is_the_signed_in_user", () => {
    signInAs("me");
    const { result } = renderHook(() => useIsOwnedByCurrentUser());

    expect(result.current("me")).toBe(true);
  });

  it("should_return_false_when_another_user_owns_the_resource", () => {
    signInAs("me");
    const { result } = renderHook(() => useIsOwnedByCurrentUser());

    expect(result.current("someone-else")).toBe(false);
  });

  it.each([undefined, null, ""])(
    "should_treat_a_missing_owner_id_%p_as_owned",
    (ownerId) => {
      signInAs("me");
      const { result } = renderHook(() => useIsOwnedByCurrentUser());

      expect(result.current(ownerId)).toBe(true);
    },
  );

  it("should_treat_every_resource_as_owned_while_the_user_is_not_loaded", () => {
    signInAs(null);
    const { result } = renderHook(() => useIsOwnedByCurrentUser());

    expect(result.current("someone-else")).toBe(true);
  });

  it("should_follow_the_signed_in_user_when_it_changes", () => {
    signInAs("me");
    const { result } = renderHook(() => useIsOwnedByCurrentUser());
    expect(result.current("other")).toBe(false);

    signInAs("other");

    expect(result.current("other")).toBe(true);
  });
});
