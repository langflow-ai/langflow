export const sortFlows = (flows, type) => {
  const isComponent = type === "component";

  const sortByDate = (a, b) => {
    const dateA = a?.updated_at || a?.date_created;
    const dateB = b?.updated_at || b?.date_created;

    if (dateA && dateB) {
      return new Date(dateB).getTime() - new Date(dateA).getTime();
    } else if (dateA) {
      return 1;
    } else if (dateB) {
      return -1;
    } else {
      return 0;
    }
  };

  const filteredFlows =
    type === "all"
      ? flows
      : flows?.filter((f) => (f?.is_component ?? false) === isComponent);

  return filteredFlows?.sort(sortByDate) ?? [];
};
