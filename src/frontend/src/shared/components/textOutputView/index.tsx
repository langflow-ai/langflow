import { Textarea } from "../../../components/ui/textarea";

const TextOutputView = ({
  left,
  value,
}: {
  left: boolean | undefined;
  value: any;
}) => {
  if (typeof value === "object" && Object.keys(value).includes("text")) {
    value = value.text;
  }

  const isTruncated = value?.length > 20000;

  return (
    <>
      {" "}
      <Textarea
        className={`custom-scroll w-full resize-none ${left ? "min-h-32" : "h-full"}`}
        placeholder={"Empty"}
        readOnly
        value={value}
      />
      {isTruncated && (
        <div className="text-muted-foreground mt-2 text-xs">
          This output has been truncated due to its size.
        </div>
      )}
    </>
  );
};

export default TextOutputView;
