import type { TemplateExample } from "@/types/templates/types";
import { canDeleteTeamTemplate } from "../team-template-permissions";

const template = {
  id: "template-1",
  name: "Template",
  description: "Description",
  data: null,
  source: "team",
  created_by: "owner-1",
} as TemplateExample;

describe("canDeleteTeamTemplate", () => {
  it("allows a superuser to delete another user's team template", () => {
    expect(
      canDeleteTeamTemplate(template, {
        id: "another-user",
        username: "admin",
        is_superuser: true,
      }),
    ).toBe(true);
  });

  it("allows the langflow user to delete a team template", () => {
    expect(
      canDeleteTeamTemplate(template, {
        id: "another-user",
        username: "langflow",
        is_superuser: false,
      }),
    ).toBe(true);
  });

  it("does not allow an unrelated regular user", () => {
    expect(
      canDeleteTeamTemplate(template, {
        id: "another-user",
        username: "regular-user",
        is_superuser: false,
      }),
    ).toBe(false);
  });
});
