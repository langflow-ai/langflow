import { useState } from "react";
import ForwardedIconComponent from "../../../../../../../components/genericIconComponent";
import FileCard from "../../../fileComponent";
import formatFileName from "../../../filePreviewChat/utils/format-file-name";

export default function FileCardWrapper({
  index,
  name,
  type,
  path,
}: {
  index: number;
  name: string;
  type: string;
  path: string;
}) {
  const [show, setShow] = useState<boolean>(true);
  return (
    <div key={index} className="flex flex-col gap-2">
      <span
        onClick={() => setShow(!show)}
        className="flex cursor-pointer gap-2 text-sm text-muted-foreground"
      >
        {formatFileName(name, 50)}
        <ForwardedIconComponent name={show ? "ChevronDown" : "ChevronRight"} />
      </span>
      <FileCard
        showFile={show}
        fileName={name}
        fileType={type}
        content={path}
      />
    </div>
  );
}
