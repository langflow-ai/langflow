export default function resetGrid(ref) {
  if (ref?.current && ref?.current.api) {
    ref.current.api.resetColumnState();
  }
}
