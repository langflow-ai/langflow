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
<<<<<<< HEAD
    <Textarea
      className={`custom-scroll w-full ${left ? "min-h-32" : "h-full"}`}
      placeholder={"Empty"}
      readOnly
      // update to real value on flowPool
      value={value}
    />
=======
    <>
      {" "}
      <Textarea
        className={`w-full custom-scroll ${left ? "min-h-32" : "h-full"}`}
        placeholder={"Empty"}
        readOnly
        // update to real value on flowPool
        value={value}
      />
      {isTruncated && (
        <div className="mt-2 text-xs text-muted-foreground">
          This output has been truncated due to its size.
        </div>
      )}
    </>
>>>>>>> dc35b4ec9ed058b980c89065484fdbfc1fd4cc9b
  );
};

export default TextOutputView;
