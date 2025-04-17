import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";

const GeneralPageHeaderComponent = () => {
  return (
    <>
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            General
            <ForwardedIconComponent
              name="SlidersHorizontal"
              className="text-primary ml-2 h-5 w-5"
            />
          </h2>
          <p className="text-muted-foreground text-sm">
            Manage settings related to Langflow and your account.
          </p>
        </div>
      </div>
    </>
  );
};
export default GeneralPageHeaderComponent;
