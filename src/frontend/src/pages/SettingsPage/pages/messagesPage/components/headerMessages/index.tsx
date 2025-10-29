import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";

const HeaderMessagesComponent = () => {
  return (
    <>
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            Messages
            <ForwardedIconComponent
              name="MessagesSquare"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Inspect, edit and remove messages to explore and refine model
            behaviors.
          </p>
        </div>
      </div>
    </>
  );
};
export default HeaderMessagesComponent;
