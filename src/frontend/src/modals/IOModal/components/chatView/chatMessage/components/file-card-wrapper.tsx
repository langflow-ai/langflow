import { useState } from "react";
import { extractFileInfo } from "@/components/core/playgroundComponent/chat-view/utils/file-utils";
import CustomFileCard from "@/customization/components/custom-file-card";
import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import formatFileName from "../../fileComponent/utils/format-file-name";

export default function FileCardWrapper({
  index,
  path,
}: {
  index: number;
  path: { path: string; type: string; name: string } | string;
}) {
  const [show, setShow] = useState<boolean>(true);
  let name: string = "";
  let type: string = "";
  let pathString: string = "";
  if (typeof path === "string") {
    name = extractFileInfo(path).name;
    type = path.split(".").pop() || "";
    pathString = path;
  } else {
    name = path.name;
    type = path.type;
    pathString = path.path;
  }

  return (
    <div key={index} className="flex flex-col gap-2">
      <button
        type="button"
        aria-expanded={show}
        onClick={() => setShow(!show)}
        className="flex cursor-pointer gap-2 text-sm text-muted-foreground"
      >
        {formatFileName(name, 50)}
        <ForwardedIconComponent name={show ? "ChevronDown" : "ChevronRight"} />
      </button>
      <CustomFileCard
        showFile={show}
        fileName={name}
        fileType={type}
        path={pathString}
      />
    </div>
  );
}
