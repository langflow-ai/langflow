import { cn } from "../../../utils/utils";
import { Badge } from "../../ui/badge";
import HorizontalScrollFadeComponent from "../horizontalScrollFadeComponent";

export function TagsSelector({
  tags,
  disabled = false,
  loadingTags,
  selectedTags,
  setSelectedTags,
}: {
  tags: { id: string; name: string }[];
  disabled?: boolean;
  loadingTags: boolean;
  selectedTags: any[];
  setSelectedTags: (tags: any[]) => void;
}) {
  const updateTags = (tagName: string) => {
    const index = selectedTags.indexOf(tagName);
    const newArray =
      index === -1
        ? [...selectedTags, tagName]
        : selectedTags.filter((_, i) => i !== index);
    setSelectedTags(newArray);
  };

  return (
    <HorizontalScrollFadeComponent isFolder={false}>
      {!loadingTags
        ? tags.map((tag, idx) => (
            <button
              disabled={disabled}
              className={
                disabled
                  ? "cursor-not-allowed"
                  : "overflow-hidden whitespace-nowrap"
              }
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                updateTags(tag.name);
              }}
              key={idx}
              data-testid={`tag-selector-${tag.name}`}
            >
              <Badge
                key={idx}
                variant="outline"
                size="sq"
                className={cn(
                  selectedTags.some((category) => category === tag.name)
                    ? "min-w-min bg-beta-foreground text-background hover:bg-beta-foreground"
                    : "",
                )}
              >
                {tag.name}
              </Badge>
            </button>
          ))
        : []}
    </HorizontalScrollFadeComponent>
  );
}
