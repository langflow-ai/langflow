import IconComponent from "../../../components/common/genericIconComponent";

export const HeaderRender = ({ title, showIcon }) => {
  return (
    <>
      <span className="pr-2">{title}</span>
      {showIcon && (
        <IconComponent
          name="Key"
          className="text-foreground h-6 w-6 pl-1"
          aria-hidden="true"
        />
      )}
    </>
  );
};
