import { useState } from "react";
import { useTranslation } from "react-i18next";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { ShowMoreSessions } from "@/components/core/playgroundComponent/chat-view/chat-header/components/show-more-sessions";
import { Button } from "@/components/ui/button";
import IconComponent from "../../../components/common/genericIconComponent";
import type { SidebarOpenViewProps } from "../types/sidebar-open-view";
import SessionSelector from "./IOFieldView/components/session-selector";

export const SidebarOpenView = ({
  onNewSession,
  pendingSessionIds,
  sessions,
  sessionsPagination,
  setSelectedViewField,
  setvisibleSession,
  handleDeleteSession,
  visibleSession,
  selectedViewField,
  playgroundPage,
  setActiveSession,
}: SidebarOpenViewProps) => {
  const { t } = useTranslation();
  const [openMenuSession, setOpenMenuSession] = useState<string | null>(null);

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
              <div className="text-mmd font-normal">Chat</div>
            </div>
            <ShadTooltip styleClasses="z-50" content={t("chat.newChat")}>
              <div>
                <Button
                  data-testid="new-chat"
                  variant="ghost"
                  className="flex h-8 w-8 items-center justify-center !p-0 hover:bg-secondary-hover"
                  aria-label={t("chat.newChat")}
                  onClick={onNewSession}
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
              canRename={!pendingSessionIds?.has(session)}
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
              menuOpen={openMenuSession === session}
              onMenuOpenChange={(open) => {
                setOpenMenuSession(open ? session : null);
              }}
            />
          ))}
          <ShowMoreSessions pagination={sessionsPagination} />
        </div>
      </div>
    </>
  );
};
