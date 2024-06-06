const useSelectAll = (flowsFromFolder, getValues, setValue) => {
  const handleSelectAll = (select) => {
    const flowsFromFolderIds = flowsFromFolder?.map((f) => f.id);
    if (select) {
      Object.keys(getValues()).forEach((key) => {
        if (!flowsFromFolderIds?.includes(key)) return;
        setValue(key, true);
      });
      return;
    }

    Object.keys(getValues()).forEach((key) => {
      setValue(key, false);
    });
  };

  return handleSelectAll;
};

export default useSelectAll;
