import { act, render } from "@testing-library/react";
import TableAutoCellRender, { TABLE_LOAD_FROM_DB_FIELDS } from "..";

const mockInputGlobalComponent = jest.fn().mockReturnValue(null);

jest.mock(
  "@/components/core/parameterRenderComponent/components/inputGlobalComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) => {
      mockInputGlobalComponent(props);
      return null;
    },
  }),
);

describe("TableAutoCellRender", () => {
  const renderGlobalVariableCell = ({
    data = {},
    value = "",
  }: {
    data?: Record<string, unknown>;
    value?: string;
  } = {}) => {
    const setValue = jest.fn();
    const props = {
      value,
      setValue,
      colDef: {
        field: "value",
        context: { globalVariable: true },
      },
      api: {
        getGridOption: jest.fn(() => jest.fn()),
      },
      data,
    } as unknown as Parameters<typeof TableAutoCellRender>[0];

    render(<TableAutoCellRender {...props} />);

    const inputProps =
      mockInputGlobalComponent.mock.calls[
        mockInputGlobalComponent.mock.calls.length - 1
      ][0];

    return { data, inputProps, setValue };
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("passes the cell-level global-variable state to the input", () => {
    const { inputProps } = renderGlobalVariableCell({
      data: {
        [TABLE_LOAD_FROM_DB_FIELDS]: { value: true },
      },
      value: "AUTH_HEADER",
    });

    expect(inputProps.load_from_db).toBe(true);
  });

  it("marks selected variables and literal text per cell", () => {
    const { data, inputProps, setValue } = renderGlobalVariableCell({
      data: { value: "" },
    });

    act(() => {
      inputProps.handleOnNewValue({
        value: "AUTH_HEADER",
        load_from_db: true,
      });
    });

    expect(data[TABLE_LOAD_FROM_DB_FIELDS]).toEqual({ value: true });
    expect(setValue).toHaveBeenCalledWith("AUTH_HEADER");
    expect(setValue).toHaveBeenCalledTimes(1);

    act(() => {
      inputProps.handleOnNewValue({
        value: "AUTH_HEADER",
        load_from_db: false,
      });
    });

    expect(data[TABLE_LOAD_FROM_DB_FIELDS]).toEqual({ value: false });
    expect(data.value).toBe("AUTH_HEADER");
    expect(setValue).toHaveBeenCalledTimes(1);
  });
});
