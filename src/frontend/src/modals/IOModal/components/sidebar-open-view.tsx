import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
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
}: SidebarOpenViewProps) => {
  return (
    <>
      <div className="flex flex-col pl-3">
        <div className="flex flex-col gap-2 pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <IconComponent
                name="MessagesSquare"
                className="h-[18px] w-[18px] text-ring"
              />
              <div className="text-[13px] font-normal">Chat</div>
            </div>
            <ShadTooltip styleClasses="z-50" content="New Chat">
              <div>
                <Button
                  data-testid="new-chat"
                  variant="ghost"
                  className="flex h-8 w-8 items-center justify-center !p-0 hover:bg-secondary-hover"
                  onClick={(_) => {
                    setvisibleSession(undefined);
                    setSelectedViewField(undefined);
                  }}
                >
                  <IconComponent
                    name="Plus"
                    className="h-[18px] w-[18px] text-ring"
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
            />
          ))}
        </div>
      </div>
    </>
  );
};
