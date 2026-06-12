import { readFileSync } from "node:fs";
import { join } from "node:path";

const iconDirectory = join(__dirname, "..");

describe("Jungle Grid icon", () => {
  it("keeps the theme-aware stroke after externally supplied SVG props", () => {
    const source = readFileSync(
      join(iconDirectory, "JungleGridIcon.jsx"),
      "utf8",
    );

    expect(source.indexOf("{...props}")).toBeLessThan(
      source.indexOf("stroke={props.isdark"),
    );
  });

  it("keeps the wrapper-controlled ref and theme after general props", () => {
    const source = readFileSync(join(iconDirectory, "index.tsx"), "utf8");

    expect(source).toContain(
      "<JungleGridIconSvg {...props} ref={ref} isdark={isdark} />",
    );
  });
});
