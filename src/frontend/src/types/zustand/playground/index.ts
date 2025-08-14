export type PlaygroundStoreType = {
  selectedSession: string | undefined;
  setSelectedSession: (selectedSession: string | undefined) => void;
  isPlayground: boolean;
  setIsPlayground: (isPlayground: boolean) => void;
};
