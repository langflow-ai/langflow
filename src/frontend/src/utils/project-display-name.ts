import type { FolderType, ProjectListType } from "@/pages/MainPage/entities";

export const getProjectDisplayName = (
  project: Pick<FolderType, "id" | "name" | "owner_username" | "is_owner">,
): string => {
  if (project.is_owner !== false) {
    return project.name;
  }

  return `${project.name} — ${project.owner_username ?? project.id ?? "unknown owner"}`;
};

export const getDefaultProjectId = (
  projects: ProjectListType[],
  defaultProjectName: string,
): string => {
  return (
    (
      projects.find(
        (project) => project.is_owner && project.name === defaultProjectName,
      ) ??
      projects.find((project) => project.is_owner) ??
      projects[0]
    )?.id ?? ""
  );
};
