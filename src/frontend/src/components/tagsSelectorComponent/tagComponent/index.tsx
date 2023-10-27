import { useState } from "react";
import { Badge } from "../../ui/badge";

export default function TagComponent({
  tag,
  handleClick,
  selected,
}: {
  tag: string;
  handleClick: (tag: string) => void;
  selected: boolean;
}) {
  const [selectedTag, setSelectedTag] = useState(selected);
  return (
    <button
      onClick={() => {
        setSelectedTag((prev) => !prev);
        handleClick(tag);
      }}
    >
      <Badge
        size="md"
        className={selectedTag ? "shadow-md" : ""}
        variant={selectedTag ? "gray" : "secondary"}
      >
        {tag}
      </Badge>
    </button>
  );
}
