import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import PaginatorComponent from "@/components/common/paginatorComponent";
import {
  useDeleteTextAnnotationProject,
  useGetTextAnnotationProjects,
  usePatchTextAnnotationProject,
  usePostTextAnnotationProject,
} from "@/controllers/API/queries/text-annotation";
import CustomLoader from "@/customization/components/custom-loader";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import type {
  TextAnnotationProjectCreateType,
  TextAnnotationProjectType,
} from "@/types/text-annotation";
import IconComponent from "../../components/common/genericIconComponent";
import ShadTooltip from "../../components/common/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import {
  PAGINATION_PAGE,
  PAGINATION_ROWS_COUNT,
  PAGINATION_SIZE,
} from "../../constants/constants";
import ConfirmationModal from "../../modals/confirmationModal";
import AnnotationEditor from "./AnnotationEditor";
import CreateProjectModal from "./CreateProjectModal";

export default function TextAnnotationPage() {
  const { t } = useTranslation();
  const { projectId } = useParams();
  const navigate = useCustomNavigate();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const [inputValue, setInputValue] = useState("");
  const [size, setPageSize] = useState(PAGINATION_SIZE);
  const [index, setPageIndex] = useState(PAGINATION_PAGE);

  const { data: projects = [], isLoading } = useGetTextAnnotationProjects({});
  const { mutate: createProject } = usePostTextAnnotationProject({});
  const { mutate: patchProject } = usePatchTextAnnotationProject({});
  const { mutate: deleteProject } = useDeleteTextAnnotationProject({});

  const filteredProjects = useMemo(() => {
    if (!inputValue.trim()) return projects;
    const q = inputValue.trim().toLowerCase();
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.description ?? "").toLowerCase().includes(q),
    );
  }, [projects, inputValue]);

  const totalRowsCount = filteredProjects.length;
  const pageProjects = useMemo(() => {
    const start = size * (index - 1);
    return filteredProjects.slice(start, start + size);
  }, [filteredProjects, index, size]);

  function handleChangePagination(pageIndex: number, pageSize: number) {
    setPageSize(pageSize);
    setPageIndex(pageIndex);
  }

  function handleCreate(input: TextAnnotationProjectCreateType) {
    createProject(input, {
      onSuccess: () =>
        setSuccessData({ title: t("textAnnotation.success.projectCreated") }),
      onError: (error) =>
        setErrorData({
          title: t("textAnnotation.errors.createProject"),
          list: [error.message],
        }),
    });
  }

  function handleEdit(
    projectId: string,
    input: TextAnnotationProjectCreateType,
  ) {
    patchProject(
      { projectId, ...input },
      {
        onSuccess: () =>
          setSuccessData({ title: t("textAnnotation.success.projectUpdated") }),
        onError: (error) =>
          setErrorData({
            title: t("textAnnotation.errors.updateProject"),
            list: [error.message],
          }),
      },
    );
  }

  function handleDelete(project: TextAnnotationProjectType) {
    deleteProject(
      { projectId: project.id },
      {
        onSuccess: () =>
          setSuccessData({ title: t("textAnnotation.success.projectDeleted") }),
        onError: (error) =>
          setErrorData({
            title: t("textAnnotation.errors.deleteProject"),
            list: [error.message],
          }),
      },
    );
  }

  if (projectId) {
    return <AnnotationEditor projectId={projectId} />;
  }

  return (
    <div className="admin-page-panel flex h-full flex-col pb-8">
      <div className="main-page-nav-arrangement">
        <span className="main-page-nav-title">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <IconComponent name="ChevronLeft" className="w-5" />
          </Button>
          <IconComponent name="FileText" className="w-6" />
          {t("textAnnotation.title")}
        </span>
      </div>
      <span className="admin-page-description-text">
        {t("textAnnotation.description")}
      </span>
      <div className="flex w-full justify-between">
        <div className="flex w-96 items-center gap-4">
          <Input
            placeholder={t("textAnnotation.searchPlaceholder")}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              setPageIndex(PAGINATION_PAGE);
            }}
          />
          {inputValue.length > 0 ? (
            <div
              className="cursor-pointer"
              onClick={() => {
                setInputValue("");
                setPageIndex(PAGINATION_PAGE);
              }}
            >
              <IconComponent name="X" className="w-6 text-foreground" />
            </div>
          ) : (
            <div>
              <IconComponent name="Search" className="w-6 text-foreground" />
            </div>
          )}
        </div>
        <div>
          <CreateProjectModal
            title={t("textAnnotation.newProjectTitle")}
            titleHeader={t("textAnnotation.newProjectHeader")}
            cancelText={t("textAnnotation.cancelButton")}
            confirmationText={t("textAnnotation.saveButton")}
            icon="FilePlus2"
            onConfirm={(input) => handleCreate(input)}
            asChild
          >
            <Button variant="primary">
              <IconComponent name="Plus" className="h-4 w-4" />
              {t("textAnnotation.newProjectButton")}
            </Button>
          </CreateProjectModal>
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-full w-full items-center justify-center">
          <CustomLoader remSize={12} />
        </div>
      ) : pageProjects.length === 0 ? (
        <div className="m-4 flex items-center justify-between text-sm">
          {t("textAnnotation.noProjects")}
        </div>
      ) : (
        <div className="flex flex-1 flex-col">
          <div className="my-4 flex-1 overflow-x-hidden overflow-y-scroll rounded-md border bg-background custom-scroll">
            <Table className="table-fixed outline-1">
              <TableHeader className="table-fixed bg-muted outline-1">
                <TableRow>
                  <TableHead className="h-10">
                    {t("textAnnotation.columnName")}
                  </TableHead>
                  <TableHead className="h-10">
                    {t("textAnnotation.columnDescription")}
                  </TableHead>
                  <TableHead className="h-10 w-[100px]">
                    {t("textAnnotation.columnType")}
                  </TableHead>
                  <TableHead className="h-10 w-[80px]">
                    {t("textAnnotation.columnTasks")}
                  </TableHead>
                  <TableHead className="h-10 w-[120px]">
                    {t("textAnnotation.columnProgress")}
                  </TableHead>
                  <TableHead className="h-10">
                    {t("textAnnotation.columnCreatedAt")}
                  </TableHead>
                  <TableHead className="h-10">
                    {t("textAnnotation.columnUpdatedAt")}
                  </TableHead>
                  <TableHead className="h-10 w-[120px] text-right"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="border-b">
                {pageProjects.map((project) => {
                  const pct =
                    project.task_count === 0
                      ? 0
                      : Math.round(
                          (project.labeled_count / project.task_count) * 100,
                        );
                  return (
                    <TableRow key={project.id}>
                      <TableCell className="truncate py-2 font-medium">
                        <ShadTooltip content={project.name}>
                          <span className="cursor-default">{project.name}</span>
                        </ShadTooltip>
                      </TableCell>
                      <TableCell className="truncate py-2">
                        <ShadTooltip content={project.description ?? ""}>
                          <span className="cursor-default text-muted-foreground">
                            {project.description || "-"}
                          </span>
                        </ShadTooltip>
                      </TableCell>
                      <TableCell className="truncate py-2">
                        <span className="text-xs text-muted-foreground">
                          {project.task_type === "ner"
                            ? t("textAnnotation.projectTaskTypeNer")
                            : t("textAnnotation.projectTaskTypeClassification")}
                        </span>
                      </TableCell>
                      <TableCell className="truncate py-2">
                        {project.task_count}
                      </TableCell>
                      <TableCell className="truncate py-2">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-12 overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full bg-primary"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {project.labeled_count}/{project.task_count}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="truncate py-2">
                        {project.created_at.split("T")[0]}
                      </TableCell>
                      <TableCell className="truncate py-2">
                        {project.updated_at.split("T")[0]}
                      </TableCell>
                      <TableCell className="flex w-[120px] py-2 text-right">
                        <div className="flex">
                          <ShadTooltip
                            content={t("textAnnotation.openProjectTitle")}
                          >
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() =>
                                navigate(`/text-annotation/${project.id}`)
                              }
                            >
                              <IconComponent
                                name="ExternalLink"
                                className="h-4 w-4 cursor-pointer"
                              />
                            </Button>
                          </ShadTooltip>
                          <CreateProjectModal
                            title={t("textAnnotation.editProjectTitle")}
                            titleHeader={project.name}
                            cancelText={t("textAnnotation.cancelButton")}
                            confirmationText={t("textAnnotation.saveButton")}
                            icon="Pencil"
                            data={project}
                            onConfirm={(input) => handleEdit(project.id, input)}
                            asChild
                          >
                            <Button variant="ghost" size="icon">
                              <IconComponent
                                name="Pencil"
                                className="h-4 w-4 cursor-pointer"
                              />
                            </Button>
                          </CreateProjectModal>
                          <ConfirmationModal
                            size="x-small"
                            title={t("textAnnotation.deleteProjectTitle")}
                            titleHeader={t(
                              "textAnnotation.deleteProjectHeader",
                            )}
                            modalContentTitle={t("textAnnotation.title")}
                            cancelText={t("textAnnotation.cancelButton")}
                            confirmationText={t(
                              "textAnnotation.deleteProjectTitle",
                            )}
                            icon="Trash2"
                            data={project}
                            onConfirm={() => handleDelete(project)}
                          >
                            <ConfirmationModal.Content>
                              <span>
                                {t("textAnnotation.deleteProjectConfirm")}
                              </span>
                            </ConfirmationModal.Content>
                            <ConfirmationModal.Trigger>
                              <Button variant="ghost" size="icon">
                                <IconComponent
                                  name="Trash2"
                                  className="h-4 w-4 cursor-pointer text-destructive"
                                />
                              </Button>
                            </ConfirmationModal.Trigger>
                          </ConfirmationModal>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          <div className="mt-auto">
            <PaginatorComponent
              pageIndex={index}
              pageSize={size}
              totalRowsCount={totalRowsCount}
              paginate={handleChangePagination}
              rowsCount={PAGINATION_ROWS_COUNT}
            />
          </div>
        </div>
      )}
    </div>
  );
}
