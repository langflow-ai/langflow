import { Textarea } from "../../../components/ui/textarea";

const TextOutputView = ({ left, value }) => {
  return (
    <>
      <Textarea
        className={`w-full custom-scroll ${left ? " min-h-32" : " h-full"}`}
        placeholder={"Empty"}
        // update to real value on flowPool
        value={value}
        readOnly
      />
    </>
  );
};

export default TextOutputView;
