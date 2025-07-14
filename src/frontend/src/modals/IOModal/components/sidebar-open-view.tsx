import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import { useVoiceStore } from "@/stores/voiceStore";
import IconComponent from "../../../components/common/genericIconComponent";
import { SidebarOpenViewProps } from "../types/sidebar-open-view";
import SessionSelector from "./IOFieldView/components/session-selector";

export const SidebarOpenView = ({
  sessions,
  setSelectedViewField,
  setvisibleSession,
  handleDeleteSession,
  visibleSession,
  selectedViewField,
  playgroundPage,
  setActiveSession,
}: SidebarOpenViewProps) => {
  const setNewSessionCloseVoiceAssistant = useVoiceStore(
    (state) => state.setNewSessionCloseVoiceAssistant,
  );

  const setNewChatOnPlayground = useFlowStore(
    (state) => state.setNewChatOnPlayground,
  );

  return (
    <>
      <div className="flex flex-col pl-3">
        <div className="flex flex-col gap-2 pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <IconComponent
                name="MessagesSquare"
                className="text-ring h-[18px] w-[18px]"
              />
              <div className="text-mmd font-normal">Chat</div>
            </div>
            <ShadTooltip styleClasses="z-50" content="New Chat">
              <div>
                <Button
                  data-testid="new-chat"
                  variant="ghost"
                  className="hover:bg-secondary-hover flex h-8 w-8 items-center justify-center p-0!"
                  onClick={(_) => {
                    setvisibleSession(undefined);
                    setSelectedViewField(undefined);
                    setNewSessionCloseVoiceAssistant(true);
                    setNewChatOnPlayground(true);
                  }}
                >
                  <IconComponent
                    name="Plus"
                    className="text-ring h-[18px] w-[18px]"
                  />
                </Button>
              </div>
            </ShadTooltip>
          </div>
        </div>
        <div className="flex flex-col">
          {sessions.map((session, index) => (
            <SessionSelector
              setSelectedView={setSelectedViewField}
              selectedView={selectedViewField}
              key={index}
              session={session}
              playgroundPage={playgroundPage}
              deleteSession={(session) => {
                handleDeleteSession(session);
                if (selectedViewField?.id === session) {
                  setSelectedViewField(undefined);
                }
              }}
              updateVisibleSession={(session) => {
                setvisibleSession(session);
              }}
              toggleVisibility={() => {
                setvisibleSession(session);
              }}
              isVisible={visibleSession === session}
              inspectSession={(session) => {
                setSelectedViewField({
                  id: session,
                  type: "Session",
                });
              }}
              setActiveSession={(session) => {
                setActiveSession(session);
              }}
            />
          ))}
        </div>
      </div>
    </>
  );
};
