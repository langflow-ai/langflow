import DictAreaModal from "../../modals/dictAreaModal";

export default function ObjectRender({
  object,
  setValue,
}: {
  object: any;
  setValue?: (value: any) => void;
}): JSX.Element {
  let preview =
    object === null || object === undefined ? "‎" : JSON.stringify(object);
  if (object === null || object === undefined) {
  }
  return (
    <DictAreaModal onChange={setValue} value={object ?? {}}>
      <div className="flex h-full w-full items-center align-middle transition-all">
        <div className="truncate">{preview}</div>
      </div>
    </DictAreaModal>
  );
}
