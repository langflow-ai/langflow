import type { AllNodeType } from "@/types/flow";

jest.mock("@xyflow/react", () => ({
  addEdge: jest.fn(),
  applyEdgeChanges: jest.fn((_changes, edges) => edges),
  applyNodeChanges: jest.fn((_changes, nodes) => nodes),
}));

jest.mock("../../i18n", () => ({
  __esModule: true,
  default: { t: jest.fn((key: string) => key) },
}));

jest.mock("../alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ setErrorData: jest.fn(), setSuccessData: jest.fn() }),
  },
}));

jest.mock("../flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ currentFlowId: "flow-1", setCurrentFlow: jest.fn() }),
  },
}));

jest.mock("../tweaksStore", () => ({
  useTweaksStore: { getState: () => ({ initialSetup: jest.fn() }) },
}));

jest.mock("@/CustomNodes/helpers/check-code-validity", () => ({
  checkCodeValidity: jest.fn(() => null),
}));

import useFlowStore, { syncNodeTranslations } from "../flowStore";
import { useTypesStore } from "../typesStore";

const scheduleField = (labels?: Record<string, string>) => ({
  type: "str",
  display_name: "Schedule type",
  options: ["Daily", "Weekly"],
  value: "Weekly",
  ...(labels && { option_labels: labels }),
});

const savedNode = (labels?: Record<string, string>): AllNodeType =>
  ({
    id: "ScheduleTrigger-1",
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id: "ScheduleTrigger-1",
      type: "ScheduleTrigger",
      node: {
        display_name: "Schedule",
        description: "",
        template: { schedule_type: scheduleField(labels) },
      },
    },
  }) as unknown as AllNodeType;

const loadTypes = (labels?: Record<string, string>) => {
  useTypesStore.setState({
    data: {
      triggers: {
        ScheduleTrigger: {
          display_name: "Schedule",
          description: "",
          template: { schedule_type: scheduleField(labels) },
        },
      },
    },
    types: { ScheduleTrigger: "triggers" },
    templates: {},
    componentDisplayNames: {},
  } as never);
};

const labelsOnCanvas = () =>
  useFlowStore.getState().nodes[0].data.node?.template.schedule_type
    .option_labels;

describe("syncNodeTranslations option labels", () => {
  it("should_give_a_saved_node_the_option_labels_of_the_current_language", () => {
    useFlowStore.setState({ nodes: [savedNode()] });
    loadTypes({ Daily: "每天", Weekly: "每周" });

    syncNodeTranslations();

    expect(labelsOnCanvas()).toEqual({ Daily: "每天", Weekly: "每周" });
  });

  it("should_drop_old_labels_when_the_language_sends_none", () => {
    useFlowStore.setState({ nodes: [savedNode({ Daily: "每天" })] });
    loadTypes();

    syncNodeTranslations();

    expect(labelsOnCanvas()).toBeUndefined();
  });
});
