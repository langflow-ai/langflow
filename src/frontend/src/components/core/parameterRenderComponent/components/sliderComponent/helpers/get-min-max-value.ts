export const getMinOrMaxValue = (
  valueAsNumber: number,
  min: number,
  max: number,
) => {
  if (valueAsNumber < min) {
    return min;
  }
  if (valueAsNumber > max) {
    return max;
  }
  if (valueAsNumber >= min && valueAsNumber <= max) {
    return valueAsNumber;
  }
  return min;
};
