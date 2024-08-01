export default function handleClass(isDropdown: boolean): string {
  return isDropdown ? "mx-2 mb-2 flex rounded-md p-3" : "mt-6 w-96 rounded-md p-4 shadow-xl noflow nowheel nopan nodelete nodrag flex"
}
