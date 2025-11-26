import type { Meta, StoryContext, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import { MemoryRouter } from "react-router-dom";
import { v5 as uuidv5 } from "uuid";
import { useDarkStore } from "@/stores/darkStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { AllNodeType, FlowType } from "@/types/flow";
import type { FlowStoreType } from "@/types/zustand/flow";
import PlaygroundPage from "./index";

type StoryArgs = { darkMode?: boolean; flowId?: string };

const withDarkMode = (
  Story: React.ComponentType,
  context: StoryContext<StoryArgs>,
) => {
  const DarkModeWrapper = () => {
    const dark = context.args?.darkMode ?? false;
    const prevDark = useRef<boolean | undefined>(undefined);

    useEffect(() => {
      // Only update if dark mode actually changed
      if (prevDark.current === dark) return;
      prevDark.current = dark;

      const body = document.getElementById("body") || document.body;
      const currentDark = useDarkStore.getState().dark;

      if (dark && !currentDark) {
        body.classList.add("dark");
        useDarkStore.setState({ dark: true });
      } else if (!dark && currentDark) {
        body.classList.remove("dark");
        useDarkStore.setState({ dark: false });
      }
    }, [dark]);
    return <Story />;
  };
  return <DarkModeWrapper />;
};

const withRouter = (
  Story: React.ComponentType,
  context: StoryContext<StoryArgs>,
) => {
  const flowId = context.args?.flowId || "test-flow-id";
  return (
    <MemoryRouter initialEntries={[`/playground/${flowId}`]}>
      <Story />
    </MemoryRouter>
  );
};

const withQueryClient = (
  Story: React.ComponentType,
  context: StoryContext<StoryArgs>,
) => {
  const QueryClientWrapper = () => {
    const flowId = context.args?.flowId || "test-flow-id";
    const queryClient = useMemo(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: Infinity },
            mutations: { retry: false },
          },
        }),
      [],
    );

    useEffect(() => {
      const clientId = "test-client-id";
      const computedFlowId = uuidv5(`${clientId}_${flowId}`, uuidv5.DNS);

      queryClient.setQueryData(
        [
          "useGetMessagesQuery",
          {
            mode: "union",
            id: computedFlowId,
            params: { session_id: computedFlowId },
          },
        ],
        { data: { messages: [] } },
      );
      queryClient.setQueryData(
        ["useGetSessionsFromFlowQuery", { id: flowId }],
        {
          data: { sessions: [computedFlowId] },
        },
      );
    }, [flowId, queryClient]);

    return (
      <QueryClientProvider client={queryClient}>
        <Story />
      </QueryClientProvider>
    );
  };
  return <QueryClientWrapper />;
};

const withHidePublishElements = (Story: React.ComponentType) => {
  const HideElementsWrapper = () => {
    useEffect(() => {
      const style = document.createElement("style");
      style.id = "hide-publish-elements";
      style.textContent = `
        .absolute.bottom-2.left-0.flex.w-full.flex-col.gap-8 { display: none !important; }
        .absolute.bottom-6.left-4.hidden.transition-all.md\\:block { display: none !important; }
        div.flex.h-full.w-full.flex-col.justify-between.px-4.pb-4.pt-2 > div.flex.h-10.shrink-0.items-center.text-base.font-semibold > div.truncate.text-center.font-semibold {
          position: absolute !important; left: 50% !important; transform: translateX(-50%) !important;
        }
      `;
      document.head.appendChild(style);
      return () => {
        const existingStyle = document.getElementById("hide-publish-elements");
        if (existingStyle) document.head.removeChild(existingStyle);
      };
    }, []);
    return <Story />;
  };
  return <HideElementsWrapper />;
};

const withPlaygroundPageSetup = (
  Story: React.ComponentType,
  context: StoryContext<StoryArgs>,
) => {
  const PlaygroundPageWrapper = () => {
    const flowId = context.args?.flowId || "test-flow-id";
    const setupDone = useRef<string | null>(null);

    useEffect(() => {
      // Prevent re-setup if already done for this flowId
      if (setupDone.current === flowId) return;
      setupDone.current = flowId;
      const mockNodes: AllNodeType[] = [
        {
          id: "chat-input-1",
          type: "genericNode",
          position: { x: 0, y: 0 },
          data: {
            type: "ChatInput",
            id: "chat-input-1",
            node: {
              display_name: "Chat Input",
              description: "",
              documentation: "",
              tool_mode: false,
              frozen: false,
              template: {
                input_value: {
                  type: "str",
                  required: false,
                  placeholder: "",
                  list: false,
                  show: true,
                  readonly: false,
                  value: "",
                },
              },
            },
          },
        },
        {
          id: "chat-output-1",
          type: "genericNode",
          position: { x: 0, y: 0 },
          data: {
            type: "ChatOutput",
            id: "chat-output-1",
            node: {
              display_name: "Chat Output",
              description: "",
              documentation: "",
              tool_mode: false,
              frozen: false,
              template: {},
            },
          },
        },
      ];

      const mockFlow: FlowType = {
        id: flowId,
        name: "Playground",
        description: "A test chat flow",
        data: {
          nodes: mockNodes,
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
        is_component: false,
        access_type: "PUBLIC",
        updated_at: new Date().toISOString(),
      };

      useFlowsManagerStore.setState({
        currentFlowId: flowId,
        currentFlow: mockFlow,
        isLoading: false,
      });

      const mockBuildFlow: FlowStoreType["buildFlow"] = async ({
        input_value,
        session,
        files,
        startNodeId,
        stopNodeId,
        silent,
        stream,
        eventDelivery,
      }) => {
        if (!input_value?.trim()) return;
        const realFlowId =
          useFlowsManagerStore.getState().currentFlowId || flowId;
        const clientId =
          useUtilityStore.getState().clientId || "test-client-id";
        const playgroundPage = useFlowStore.getState().playgroundPage;
        const computedFlowId = playgroundPage
          ? uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS)
          : realFlowId;
        const sessionId = session || computedFlowId;

        useFlowStore.setState({ isBuilding: true });
        useMessagesStore.getState().addMessage({
          id: `msg-user-${Date.now()}`,
          text: input_value,
          sender: "User",
          sender_name: "User",
          flow_id: computedFlowId,
          session_id: sessionId,
          timestamp: new Date().toISOString(),
          files: files || [],
          edit: false,
          background_color: "",
          text_color: "",
          content_blocks: [],
          properties: {},
        });

        setTimeout(() => {
          useMessagesStore.getState().addMessage({
            id: `msg-bot-${Date.now()}`,
            text: `This is a simulated response to: "${input_value}"`,
            sender: "Machine",
            sender_name: "Assistant",
            flow_id: computedFlowId,
            session_id: sessionId,
            timestamp: new Date().toISOString(),
            files: [],
            edit: false,
            background_color: "",
            text_color: "",
            content_blocks: [],
            properties: {},
          });
          useFlowStore.setState({ isBuilding: false });
        }, 500);
      };

      useFlowStore.getState().setNodes(mockNodes);
      useFlowStore.setState({
        currentFlow: mockFlow,
        edges: [],
        isBuilding: false,
        playgroundPage: true,
        buildFlow: mockBuildFlow,
      });

      useMessagesStore.setState({ messages: [], displayLoadingMessage: false });
      useUtilityStore.setState({
        clientId: "test-client-id",
        chatValueStore: "",
        currentSessionId: flowId,
      });
    }, [flowId]);

    return <Story />;
  };
  return <PlaygroundPageWrapper />;
};

const meta: Meta<typeof PlaygroundPage> = {
  title: "Pages/PlaygroundPage",
  component: PlaygroundPage,
  decorators: [
    withQueryClient,
    (Story) => (
      <div style={{ height: "100vh", width: "100vw" }}>
        <Story />
      </div>
    ),
    withHidePublishElements,
    withPlaygroundPageSetup,
    withRouter,
    withDarkMode,
  ],
  parameters: {
    layout: "fullscreen",
    docs: {
      description: {
        component:
          "The PlaygroundPage component displays a chat interface for testing flows.",
      },
    },
  },
  tags: ["autodocs"],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Playground: Story = {
  argTypes: {
    darkMode: {
      control: "boolean",
      description: "Toggle dark mode",
      table: { category: "Theme" },
    },
    flowId: {
      control: "text",
      description: "Flow ID for the playground",
      table: { category: "Configuration" },
    },
  },
  args: {
    flowId: "test-flow-id",
    darkMode: false,
  } as StoryArgs & Record<string, unknown>,
};
