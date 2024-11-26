export default function resetGrid(ref, initialColumnDefs) {
  if (ref?.current && ref?.current.api) {
    ref.current.api.resetColumnState();
    if (initialColumnDefs.current) {
      const resetColumns = ref.current.api.applyColumnState({
        state: initialColumnDefs.current,
        applyOrder: true,
      });
      return resetColumns;
    }
  }
}
