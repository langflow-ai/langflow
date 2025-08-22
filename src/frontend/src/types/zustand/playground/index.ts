export type PlaygroundStoreType = {
  selectedSession: string | undefined;
  setSelectedSession: (selectedSession: string | undefined) => void;
  isPlayground: boolean;
  setIsPlayground: (isPlayground: boolean) => void;
  isFullscreen: boolean;
  toggleFullscreen: () => void;
  setIsFullscreen: (isFullscreen: boolean) => void;
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  reset: (flowId: string) => void;
};
