import { fireEvent, render, screen } from "@testing-library/react";
import {
  MetadataEditor,
  type MetadataPair,
  metadataPairsToFormValue,
} from "../MetadataEditor";

const renderEditor = (pairs: MetadataPair[]) => {
  const onChange = jest.fn();
  const utils = render(
    <MetadataEditor pairs={pairs} onPairsChange={onChange} />,
  );
  return { ...utils, onChange };
};

describe("MetadataEditor", () => {
  it("renders an empty placeholder when no pairs", () => {
    renderEditor([]);
    expect(screen.getByTestId("kb-metadata-empty")).toBeInTheDocument();
  });

  it("calls onPairsChange when a row is added", () => {
    const { onChange } = renderEditor([]);
    fireEvent.click(screen.getByTestId("kb-metadata-add"));
    expect(onChange).toHaveBeenCalledWith([{ key: "", value: "" }]);
  });

  it("propagates key/value edits as a fresh array", () => {
    const { onChange } = renderEditor([{ key: "", value: "" }]);
    fireEvent.change(screen.getByTestId("kb-metadata-key-0"), {
      target: { value: "tag" },
    });
    expect(onChange).toHaveBeenCalledWith([{ key: "tag", value: "" }]);
  });

  it("flags an invalid key on blur", () => {
    renderEditor([{ key: "BadKey", value: "x" }]);
    fireEvent.blur(screen.getByTestId("kb-metadata-key-0"));
    expect(
      screen.getByText(/1-32 lowercase letters, digits, or underscores/i),
    ).toBeInTheDocument();
  });

  it("removes a row via the remove button", () => {
    const { onChange } = renderEditor([{ key: "tag", value: "x" }]);
    fireEvent.click(screen.getByTestId("kb-metadata-remove-0"));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  describe("metadataPairsToFormValue", () => {
    it("returns empty string when no populated pairs", () => {
      expect(metadataPairsToFormValue([])).toBe("");
      expect(metadataPairsToFormValue([{ key: "", value: "x" }])).toBe("");
    });

    it("serializes populated pairs to JSON", () => {
      const out = metadataPairsToFormValue([
        { key: "tag", value: "invoice" },
        { key: "year", value: "2026" },
      ]);
      expect(JSON.parse(out)).toEqual({ tag: "invoice", year: "2026" });
    });

    it("drops rows with malformed keys", () => {
      const out = metadataPairsToFormValue([
        { key: "BadKey", value: "x" },
        { key: "ok", value: "y" },
      ]);
      expect(JSON.parse(out)).toEqual({ ok: "y" });
    });
  });
});
