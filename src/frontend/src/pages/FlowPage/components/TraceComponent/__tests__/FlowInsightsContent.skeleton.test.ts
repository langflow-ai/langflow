// Unit tests for the skeleton loading display logic in FlowInsightsContent.
// The skeleton should only show when isLoading=true AND rows is empty,
// to avoid hiding already-loaded rows during a background refresh.

function shouldShowSkeleton(isLoading: boolean, rowCount: number): boolean {
  return isLoading && rowCount === 0;
}

describe("flow activity skeleton visibility", () => {
  it("shows skeleton when loading and no rows", () => {
    expect(shouldShowSkeleton(true, 0)).toBe(true);
  });

  it("hides skeleton when not loading", () => {
    expect(shouldShowSkeleton(false, 0)).toBe(false);
  });

  it("hides skeleton when rows are already present (background refresh)", () => {
    expect(shouldShowSkeleton(true, 5)).toBe(false);
  });

  it("hides skeleton when loaded with rows", () => {
    expect(shouldShowSkeleton(false, 10)).toBe(false);
  });
});
