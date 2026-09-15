jest.mock("@/controllers/API/api", () => ({ api: { get: jest.fn() } }));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));
jest.mock("@/controllers/API/queries/folders/use-get-folders", () => ({
  useGetFoldersQuery: () => mockFolders,
}));

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { api } from "@/controllers/API/api";
import { CapabilityPackPicker } from "../components/capability-pack-picker";
import { SkillDefinitionsEditor } from "../components/skill-definitions-editor";
import {
  type SkillDefinition,
  type SkillPackManifest,
  validSkills,
} from "../skills";

const mockFolders = {
  data: [
    { id: "skills", name: "Research skills", project_type: "skill-pack" },
    { id: "tools", name: "Lookup tools", project_type: "tool-pack" },
  ],
  isLoading: false,
  isError: false,
  refetch: jest.fn(),
};
const definition: SkillDefinition = {
  name: "research",
  description: "Research a question",
  instructions: "Read primary sources.",
  tool_packs: [],
};
const manifest: SkillPackManifest = {
  name: "Research skills",
  reference: {
    project_id: "skills",
    expected_type: "skill-pack",
    revision: "a".repeat(64),
  },
  skills: [definition],
};
const request = jest.mocked(api.get);

function wrap(children: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {children}
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  request.mockResolvedValue({ data: manifest });
});

it("shows instructions before accepting a reviewed Skill Pack", async () => {
  const change = jest.fn();
  wrap(
    <CapabilityPackPicker
      kind="skill-pack"
      projectId="harness"
      value={[]}
      onChange={change}
    />,
  );
  expect(
    screen.queryByRole("option", { name: "Lookup tools" }),
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Choose a Skill Pack"), {
    target: { value: "skills" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Review" }));
  expect(await screen.findByText("Read primary sources.")).toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /use this revision/i }));
  expect(change).toHaveBeenCalledWith([manifest.reference]);
});

it("cannot accept a pack whose dependencies cannot be loaded", async () => {
  request.mockRejectedValue(new Error("unavailable"));
  const change = jest.fn();
  wrap(
    <CapabilityPackPicker
      kind="skill-pack"
      projectId="harness"
      value={[]}
      onChange={change}
    />,
  );
  fireEvent.change(screen.getByLabelText("Choose a Skill Pack"), {
    target: { value: "skills" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Review" }));
  await screen.findByRole("alert");
  expect(
    screen.queryByRole("button", { name: /use this revision/i }),
  ).not.toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
});

it("edits skill instructions and validates names without losing the other fields", () => {
  const change = jest.fn();
  function Editor() {
    const [value, setValue] = useState([definition]);
    return (
      <SkillDefinitionsEditor
        value={value}
        projectId="skills"
        onOpen={jest.fn()}
        onChange={(next) => {
          change(next);
          setValue(next);
        }}
      />
    );
  }
  wrap(<Editor />);
  fireEvent.change(screen.getByLabelText("Instructions"), {
    target: { value: "Check every claim." },
  });
  expect(change).toHaveBeenLastCalledWith([
    { ...definition, instructions: "Check every claim." },
  ]);
  fireEvent.change(screen.getByLabelText("Skill name"), {
    target: { value: "Bad Name" },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("unique valid name");
});

it("rejects duplicate names and empty instruction bodies", () => {
  expect(validSkills([definition])).toBe(true);
  expect(validSkills([definition, definition])).toBe(false);
  expect(validSkills([{ ...definition, instructions: " " }])).toBe(false);
});
