import { fireEvent, render, screen } from "@testing-library/react";
import type { NoteDataType } from "@/types/flow";
import { ColorPickerButtons } from "../color-picker-buttons";

// Mock the color utilities
jest.mock("../../color-utils", () => ({
  isHexColor: jest.fn(),
  getHexFromPreset: jest.fn(),
}));

import { getHexFromPreset, isHexColor } from "../../color-utils";

const mockIsHexColor = isHexColor as jest.MockedFunction<typeof isHexColor>;
const mockGetHexFromPreset = getHexFromPreset as jest.MockedFunction<
  typeof getHexFromPreset
>;

// Mock COLOR_OPTIONS
jest.mock("@/constants/constants", () => ({
  COLOR_OPTIONS: {
    blue: "hsl(var(--note-blue))",
    red: "hsl(var(--note-red))",
    green: "#00FF00",
    transparent: null,
  },
}));

describe("ColorPickerButtons", () => {
  const mockSetNode = jest.fn();
  const mockData: NoteDataType = {
    id: "test-note-id",
    type: "NoteNode",
    position: { x: 0, y: 0 },
    data: {
      node: {
        template: {
          backgroundColor: "blue",
        },
      },
    },
  };

  const defaultProps = {
    bgColor: "blue",
    data: mockData,
    setNode: mockSetNode,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockIsHexColor.mockReturnValue(false);
    mockGetHexFromPreset.mockReturnValue("#3b82f6");
  });

  describe("Rendering", () => {
    it("should render all preset color buttons", () => {
      render(<ColorPickerButtons {...defaultProps} />);

      expect(
        screen.getByTestId("color_picker_button_blue"),
      ).toBeInTheDocument();
      expect(screen.getByTestId("color_picker_button_red")).toBeInTheDocument();
      expect(
        screen.getByTestId("color_picker_button_green"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("color_picker_button_transparent"),
      ).toBeInTheDocument();
    });

    it("should render native color picker", () => {
      render(<ColorPickerButtons {...defaultProps} />);

      const nativePicker = screen.getByTestId("native_color_picker");
      expect(nativePicker).toBeInTheDocument();
      expect(nativePicker).toHaveAttribute("type", "color");
      expect(nativePicker).toHaveStyle({ display: "none" });
    });

    it("should render custom color section", () => {
      render(<ColorPickerButtons {...defaultProps} />);

      expect(screen.getByText("Custom Color")).toBeInTheDocument();
    });

    it("should show selected color with border", () => {
      render(<ColorPickerButtons {...defaultProps} />);

      const selectedButton = screen.getByTestId("color_picker_button_blue");
      const colorDiv = selectedButton.querySelector("div");
      expect(colorDiv).toHaveClass("border-2", "border-blue-500");
    });

    it("should show transparent color with border when null", () => {
      render(<ColorPickerButtons {...defaultProps} bgColor="transparent" />);

      const transparentButton = screen.getByTestId(
        "color_picker_button_transparent",
      );
      const colorDiv = transparentButton.querySelector("div");
      expect(colorDiv).toHaveClass("border");
    });
  });

  describe("Color Resolution", () => {
    it("should use hex color directly when bgColor is hex", () => {
      mockIsHexColor.mockReturnValue(true);

      render(<ColorPickerButtons {...defaultProps} bgColor="#FF5733" />);

      const nativePicker = screen.getByTestId("native_color_picker");
      expect(nativePicker).toHaveValue("#ff5733");
      expect(mockGetHexFromPreset).not.toHaveBeenCalled();
    });

    it("should convert preset color to hex for native picker", () => {
      mockIsHexColor.mockReturnValue(false);
      mockGetHexFromPreset.mockReturnValue("#3b82f6");

      render(<ColorPickerButtons {...defaultProps} bgColor="blue" />);

      const nativePicker = screen.getByTestId("native_color_picker");
      expect(nativePicker).toHaveValue("#3b82f6");
      expect(mockGetHexFromPreset).toHaveBeenCalledWith("blue");
    });

    it("should fallback to white when preset conversion fails", () => {
      mockIsHexColor.mockReturnValue(false);
      mockGetHexFromPreset.mockReturnValue(null);

      render(<ColorPickerButtons {...defaultProps} bgColor="blue" />);

      const nativePicker = screen.getByTestId("native_color_picker");
      expect(nativePicker).toHaveValue("#ffffff");
    });

    it("should handle SSR environment gracefully", () => {
      const originalWindow = global.window;
      // @ts-ignore
      delete global.window;

      mockIsHexColor.mockReturnValue(false);
      mockGetHexFromPreset.mockReturnValue("#FFFFFF");

      render(<ColorPickerButtons {...defaultProps} bgColor="blue" />);

      const nativePicker = screen.getByTestId("native_color_picker");
      expect(nativePicker).toHaveValue("#ffffff");

      // Restore window
      global.window = originalWindow;
    });
  });

  describe("User Interactions", () => {
    it("should call setNode when preset color is clicked", () => {
      render(<ColorPickerButtons {...defaultProps} />);

      const blueButton = screen.getByTestId("color_picker_button_blue");
      fireEvent.click(blueButton);

      expect(mockSetNode).toHaveBeenCalledWith(
        "test-note-id",
        expect.any(Function),
      );
    });

    it("should call setNode with correct updater function for preset color", () => {
      render(<ColorPickerButtons {...defaultProps} />);

      const redButton = screen.getByTestId("color_picker_button_red");
      fireEvent.click(redButton);

      expect(mockSetNode).toHaveBeenCalledWith(
        "test-note-id",
        expect.any(Function),
      );

      // Test the updater function
      const updater = mockSetNode.mock.calls[0][1];
      const oldData = {
        data: {
          node: {
            template: {
              backgroundColor: "old-color",
            },
          },
        },
      };

      const result = updater(oldData);
      expect(result.data.node.template.backgroundColor).toBe("red");
    });

    it("should call setNode when native color picker changes", () => {
      render(<ColorPickerButtons {...defaultProps} />);

      const nativePicker = screen.getByTestId("native_color_picker");
      fireEvent.change(nativePicker, { target: { value: "#FF5733" } });

      expect(mockSetNode).toHaveBeenCalledWith(
        "test-note-id",
        expect.any(Function),
      );
    });

    it("should call setNode with correct updater function for native picker", () => {
      render(<ColorPickerButtons {...defaultProps} />);

      const nativePicker = screen.getByTestId("native_color_picker");
      fireEvent.change(nativePicker, { target: { value: "#FF5733" } });

      expect(mockSetNode).toHaveBeenCalledWith(
        "test-note-id",
        expect.any(Function),
      );

      // Test the updater function
      const updater = mockSetNode.mock.calls[0][1];
      const oldData = {
        data: {
          node: {
            template: {
              backgroundColor: "old-color",
            },
          },
        },
      };

      const result = updater(oldData);
      expect(result.data.node.template.backgroundColor).toBe("#ff5733");
    });

    it("should trigger native color picker when custom color section is clicked", () => {
      render(<ColorPickerButtons {...defaultProps} />);

      const customColorSection = screen
        .getByText("Custom Color")
        .closest("div");
      const nativePicker = screen.getByTestId("native_color_picker");

      // Mock the click method
      const mockClick = jest.fn();
      nativePicker.click = mockClick;

      fireEvent.click(customColorSection!);

      expect(mockClick).toHaveBeenCalled();
    });
  });

  describe("Memoization", () => {
    it("should memoize currentHexColor based on bgColor", () => {
      const { rerender } = render(
        <ColorPickerButtons {...defaultProps} bgColor="blue" />,
      );

      expect(mockIsHexColor).toHaveBeenCalledWith("blue");
      expect(mockGetHexFromPreset).toHaveBeenCalledWith("blue");

      // Clear mocks
      jest.clearAllMocks();

      // Rerender with same bgColor
      rerender(<ColorPickerButtons {...defaultProps} bgColor="blue" />);

      // Should not call functions again due to memoization
      expect(mockIsHexColor).not.toHaveBeenCalled();
      expect(mockGetHexFromPreset).not.toHaveBeenCalled();
    });

    it("should recalculate when bgColor changes", () => {
      const { rerender } = render(
        <ColorPickerButtons {...defaultProps} bgColor="blue" />,
      );

      jest.clearAllMocks();

      // Change bgColor
      rerender(<ColorPickerButtons {...defaultProps} bgColor="red" />);

      expect(mockIsHexColor).toHaveBeenCalledWith("red");
      expect(mockGetHexFromPreset).toHaveBeenCalledWith("red");
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty data gracefully", () => {
      const emptyData = {
        id: "test-id",
        type: "NoteNode" as const,
        position: { x: 0, y: 0 },
        data: {
          node: {
            template: {
              backgroundColor: "blue",
            },
          },
        },
      };

      render(<ColorPickerButtons {...defaultProps} data={emptyData} />);

      expect(
        screen.getByTestId("color_picker_button_blue"),
      ).toBeInTheDocument();
    });

    it("should handle missing template gracefully", () => {
      const dataWithoutTemplate = {
        id: "test-id",
        type: "NoteNode" as const,
        position: { x: 0, y: 0 },
        data: {
          node: {},
        },
      };

      render(
        <ColorPickerButtons {...defaultProps} data={dataWithoutTemplate} />,
      );

      expect(
        screen.getByTestId("color_picker_button_blue"),
      ).toBeInTheDocument();
    });

    it("should handle invalid color values", () => {
      mockIsHexColor.mockReturnValue(false);
      mockGetHexFromPreset.mockReturnValue(null);

      render(<ColorPickerButtons {...defaultProps} bgColor="invalid-color" />);

      const nativePicker = screen.getByTestId("native_color_picker");
      expect(nativePicker).toHaveValue("#ffffff");
    });
  });
});
