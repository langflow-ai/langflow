export const sortFlows = (flows, is_component) => {
  return flows
    .filter((f) => (f.is_component ?? false) === is_component)
    .sort((a, b) => {
      if (a?.updated_at && b?.updated_at) {
        return (
          new Date(b?.updated_at!).getTime() -
          new Date(a?.updated_at!).getTime()
        );
      } else if (a?.updated_at && !b?.updated_at) {
        return 1;
      } else if (!a?.updated_at && b?.updated_at) {
        return -1;
      } else {
        return (
          new Date(b?.date_created!).getTime() -
          new Date(a?.date_created!).getTime()
        );
      }
    });
};
