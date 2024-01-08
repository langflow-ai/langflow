export type SSEStoreType = {
  updateSSEData: (sseData: object) => void,
  sseData: object,
  isBuilding: boolean,
  setIsBuilding: (isBuilding: boolean) => void,
}