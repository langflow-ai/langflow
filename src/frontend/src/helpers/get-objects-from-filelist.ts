export async function getObjectsFromFilelist<T>(files: File[]): Promise<T[]> {
  let objects: T[] = [];
  for (const file of files) {
    let text = await file.text();
    let fileData = await JSON.parse(text);
    objects.push(fileData as T);
  }
  return objects;
}
