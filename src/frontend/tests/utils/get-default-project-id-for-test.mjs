function isProjectSummary(project) {
  return (
    typeof project === "object" &&
    project !== null &&
    typeof project.id === "string" &&
    project.id.length > 0 &&
    typeof project.is_owner === "boolean"
  );
}

export async function getDefaultProjectIdForTest(page) {
  const response = await page.request.get("/api/v1/projects/");
  if (!response.ok()) {
    throw new Error(
      `GET /api/v1/projects/ failed with ${response.status()} ${response.statusText()}`,
    );
  }

  const projects = await response.json();
  if (!Array.isArray(projects)) {
    throw new Error("GET /api/v1/projects/ returned a non-array payload");
  }

  const candidates = projects.filter(isProjectSummary);
  const project =
    candidates.find(({ is_owner }) => is_owner === true) ?? candidates[0];
  if (!project) {
    throw new Error("GET /api/v1/projects/ returned no valid projects");
  }

  return project.id;
}
