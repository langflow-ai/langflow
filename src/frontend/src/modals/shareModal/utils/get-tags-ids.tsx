export default function getTagsIds(
  tags: string[],
  tagListId: { name: string; id: string }[],
) {
  return tags
    .map((tag) => tagListId.find((tagObj) => tagObj.name === tag))!
    .map((tag) => tag!.id);
}
