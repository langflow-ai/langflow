export const buildColorByName = (
  accentIndigoForeground: string,
  accentPinkForeground: string,
  percentage: number,
) => {
  const startHue = parseInt(accentIndigoForeground.split(" ")[0]);
  const endHue = parseInt(accentPinkForeground.split(" ")[0]);

  const startSaturation = parseInt(
    accentIndigoForeground.split(" ")[1].replace("%", ""),
  );
  const endSaturation = parseInt(
    accentPinkForeground.split(" ")[1].replace("%", ""),
  );

  const startLightness = parseInt(
    accentIndigoForeground.split(" ")[2].replace("%", ""),
  );
  const endLightness = parseInt(
    accentPinkForeground.split(" ")[2].replace("%", ""),
  );

  const hue = startHue + (endHue - startHue) * (percentage / 100);
  const saturation =
    startSaturation + (endSaturation - startSaturation) * (percentage / 100);
  const lightness =
    startLightness + (endLightness - startLightness) * (percentage / 100);

  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
};
