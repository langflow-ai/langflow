import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";

const HeaderMessagesComponent = () => {
  return (
    <>
      <div className="flex w-full items-center justify-between gap-4">
        <div className="flex flex-col w-full">
          <h2 className="text-primary-font flex gap-2 items-center text-lg font-medium">
            Messages
            <ForwardedIconComponent
              name="MessagesSquare"
              className="ml-2 h-5 w-5 text-menu"
            />
          </h2>
          <p className="text-sm text-secondary-font">
            Inspect, edit and remove messages to explore and refine model
            behaviors.
          </p>
        </div>
      </div>
    </>
  );
};
export default HeaderMessagesComponent;
