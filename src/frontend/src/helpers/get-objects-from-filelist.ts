export async function getObjectsFromFilelist<T>(files: File[]): Promise<T[]> {
  const objects: T[] = [];
  for (const file of files) {
    const text = await file.text();
    const fileData = await JSON.parse(text);
    objects.push(fileData as T);
  }
  return objects;
}
