import TagComponent from "./tagComponent";

export function TagsSelector({
  tags,
  selectedTags,
  setSelectedTags,
}: {
  tags: string[];
  selectedTags: Set<string>;
  setSelectedTags: (tag: string) => void;
}) {
  return (
    <div className=" flex h-full w-full flex-row flex-wrap gap-3 align-middle">
      {tags.map((tag, index) => {
        return (
          <TagComponent
            tag={tag}
            selected={selectedTags.has(tag)}
            key={index}
            handleClick={setSelectedTags}
          />
        );
      })}
    </div>
  );
}
