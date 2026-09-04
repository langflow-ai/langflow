import { render } from "@testing-library/react";
import ModelProviderModal from "../index";

// ``ModelProvidersContent`` owns ``useProviderConfiguration``. The modal keys
// it on the authorization scope, so this stub only has to report when React
// mounts and unmounts an instance.
const mountEvents: string[] = [];

jest.mock("../components/ModelProvidersContent", () => ({
  __esModule: true,
  default: ({ flowId, projectId }: { flowId?: string; projectId?: string }) => {
    const { useEffect, useRef } = jest.requireActual("react");
    // Capture the scope this instance was born with. An empty dependency list
    // is what makes the assertion meaningful: it records mounts, not prop
    // changes, so the test fails if the ``key`` stops forcing a remount.
    const mountScopeRef = useRef(`${flowId ?? ""}:${projectId ?? ""}`);
    useEffect(() => {
      mountEvents.push(`mount:${mountScopeRef.current}`);
      return () => {
        mountEvents.push(`unmount:${mountScopeRef.current}`);
      };
    }, []);
    return <div data-testid="model-providers-content" />;
  },
}));

jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({ refreshAllModelInputs: jest.fn() }),
}));

describe("ModelProviderModal authorization scope key", () => {
  beforeEach(() => {
    mountEvents.length = 0;
  });

  it("remounts the provider content when the authorization scope changes", () => {
    const { rerender } = render(
      <ModelProviderModal
        open
        onClose={jest.fn()}
        modelType="all"
        flowId="flow-one"
        projectId="project-one"
      />,
    );

    rerender(
      <ModelProviderModal
        open
        onClose={jest.fn()}
        modelType="all"
        flowId="flow-two"
        projectId="project-one"
      />,
    );

    // A scope change destroys the hook instance instead of handing it new
    // props, so ``useProviderConfiguration`` can never observe a scope change
    // from inside a mounted instance. Anything that has to react to a scope
    // change belongs on mount, not in a scope-identity comparison.
    expect(mountEvents).toEqual([
      "mount:flow-one:project-one",
      "unmount:flow-one:project-one",
      "mount:flow-two:project-one",
    ]);
  });

  it("keeps the provider content mounted when only the model type changes", () => {
    const { rerender } = render(
      <ModelProviderModal
        open
        onClose={jest.fn()}
        modelType="all"
        flowId="flow-one"
        projectId="project-one"
      />,
    );

    rerender(
      <ModelProviderModal
        open
        onClose={jest.fn()}
        modelType="embeddings"
        flowId="flow-one"
        projectId="project-one"
      />,
    );

    expect(mountEvents).toEqual(["mount:flow-one:project-one"]);
  });
});
