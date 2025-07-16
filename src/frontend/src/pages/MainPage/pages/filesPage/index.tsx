import type {
  ColDef,
  NewValueParams,
  SelectionChangedEvent,
} from 'ag-grid-community';
import type { AgGridReact } from 'ag-grid-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import ForwardedIconComponent from '@/components/common/genericIconComponent';
import ShadTooltip from '@/components/common/shadTooltipComponent';
import CardsWrapComponent from '@/components/core/cardsWrapComponent';
import TableComponent from '@/components/core/parameterRenderComponent/components/tableComponent';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Loading from '@/components/ui/loading';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useGetFilesV2 } from '@/controllers/API/queries/file-management';
import { useDeleteFilesV2 } from '@/controllers/API/queries/file-management/use-delete-files';
import { usePostRenameFileV2 } from '@/controllers/API/queries/file-management/use-put-rename-file';
import { useCustomHandleBulkFilesDownload } from '@/customization/hooks/use-custom-handle-bulk-files-download';
import { customPostUploadFileV2 } from '@/customization/hooks/use-custom-post-upload-file';
import useUploadFile from '@/hooks/files/use-upload-file';
import DeleteConfirmationModal from '@/modals/deleteConfirmationModal';
import FilesContextMenuComponent from '@/modals/fileManagerModal/components/filesContextMenuComponent';
import useAlertStore from '@/stores/alertStore';
import { formatFileSize } from '@/utils/stringManipulation';
import { FILE_ICONS } from '@/utils/styleUtils';
import { cn } from '@/utils/utils';
import { sortByDate } from '../../utils/sort-flows';
import DragWrapComponent from './components/dragWrapComponent';

export const FilesPage = () => {
  const tableRef = useRef<AgGridReact<any>>(null);
  const { data: files } = useGetFilesV2();
  const setErrorData = useAlertStore(state => state.setErrorData);
  const setSuccessData = useAlertStore(state => state.setSuccessData);

  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);
  const [quantitySelected, setQuantitySelected] = useState(0);
  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const CreateKnowledgeBaseButtonComponent = useMemo(() => {
    return (
      <ShadTooltip content="Create Knowledge Base" side="bottom">
        <Button
          className="!px-3 md:!px-4 md:!pl-3.5"
          onClick={() => {
            // TODO: Implement create knowledge base functionality
            setSuccessData({
              title: 'Knowledge Base creation coming soon!',
            });
          }}
          id="create-kb-btn"
          data-testid="create-kb-btn"
        >
          <ForwardedIconComponent
            name="Plus"
            aria-hidden="true"
            className="h-4 w-4"
          />
          <span className="hidden whitespace-nowrap font-semibold md:inline">
            Create KB
          </span>
        </Button>
      </ShadTooltip>
    );
  }, []);

  const [quickFilterText, setQuickFilterText] = useState('');
  const [tabValue, setTabValue] = useState('files');

  // Mock data for Knowledge Bases
  const mockKnowledgeBases = [
    {
      id: '1',
      name: 'Langflow Documentation',
      description:
        'Complete API documentation, component guides, and tutorials',
      type: 'Technical Documentation',
      entries: 142,
      size: 8388608, // 8MB
      created_at: '2024-01-15T10:30:00',
      updated_at: '2024-01-22T14:45:00',
      status: 'Active',
    },
    {
      id: '2',
      name: 'Machine Learning Papers',
      description: 'Research papers on LLMs, RAG, and AI architectures',
      type: 'Research Papers',
      entries: 89,
      size: 125829120, // 120MB
      created_at: '2024-01-10T09:15:00',
      updated_at: '2024-01-21T16:20:00',
      status: 'Active',
    },
    {
      id: '3',
      name: 'Customer Support Conversations',
      description: 'Historical chat logs and support ticket resolutions',
      type: 'Conversational Data',
      entries: 1247,
      size: 15728640, // 15MB
      created_at: '2024-01-08T11:00:00',
      updated_at: '2024-01-20T13:30:00',
      status: 'Active',
    },
    {
      id: '4',
      name: 'Python Code Examples',
      description: 'Code snippets, best practices, and implementation guides',
      type: 'Code Repository',
      entries: 567,
      size: 5242880, // 5MB
      created_at: '2024-01-05T14:20:00',
      updated_at: '2024-01-19T10:15:00',
      status: 'Active',
    },
    {
      id: '5',
      name: 'Product Changelogs',
      description: 'Release notes, feature updates, and version history',
      type: 'Release Notes',
      entries: 78,
      size: 2097152, // 2MB
      created_at: '2024-01-12T16:45:00',
      updated_at: '2024-01-18T11:30:00',
      status: 'Active',
    },
    {
      id: '6',
      name: 'OpenAI API Reference',
      description: 'Complete OpenAI API documentation and examples',
      type: 'API Documentation',
      entries: 234,
      size: 12582912, // 12MB
      created_at: '2024-01-03T08:20:00',
      updated_at: '2024-01-17T15:45:00',
      status: 'Active',
    },
    {
      id: '7',
      name: 'AI Safety Guidelines',
      description:
        'Best practices for responsible AI development and deployment',
      type: 'Policy Documents',
      entries: 45,
      size: 3145728, // 3MB
      created_at: '2024-01-14T13:10:00',
      updated_at: '2024-01-16T09:20:00',
      status: 'Draft',
    },
    {
      id: '8',
      name: 'Vector Database Tutorials',
      description: 'Guides for Pinecone, Weaviate, and Qdrant integration',
      type: 'Tutorial Content',
      entries: 156,
      size: 18874368, // 18MB
      created_at: '2024-01-02T10:30:00',
      updated_at: '2024-01-15T14:15:00',
      status: 'Active',
    },
  ];

  // Column definitions for Knowledge Bases
  const knowledgeBaseColDefs: ColDef[] = [
    {
      headerName: 'Name',
      field: 'name',
      flex: 2,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      editable: true,
      filter: 'agTextColumnFilter',
      cellClass:
        'cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
      cellRenderer: params => {
        // Map knowledge base types to appropriate icons
        const getKBIcon = (type: string) => {
          switch (type) {
            case 'Technical Documentation':
              return { icon: 'BookOpen', color: 'text-blue-500' };
            case 'Research Papers':
              return { icon: 'GraduationCap', color: 'text-purple-500' };
            case 'Conversational Data':
              return { icon: 'MessageCircle', color: 'text-green-500' };
            case 'Code Repository':
              return { icon: 'Code', color: 'text-orange-500' };
            case 'Release Notes':
              return { icon: 'GitBranch', color: 'text-indigo-500' };
            case 'API Documentation':
              return { icon: 'Webhook', color: 'text-cyan-500' };
            case 'Policy Documents':
              return { icon: 'Shield', color: 'text-red-500' };
            case 'Tutorial Content':
              return { icon: 'PlayCircle', color: 'text-pink-500' };
            default:
              return { icon: 'Database', color: 'text-gray-500' };
          }
        };

        const iconInfo = getKBIcon(params.data.type);

        return (
          <div className="flex items-center gap-4 font-medium">
            <div className="file-icon pointer-events-none relative">
              <ForwardedIconComponent
                name={iconInfo.icon}
                className={cn('h-6 w-6 shrink-0', iconInfo.color)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <div className="text-sm font-medium">{params.value}</div>
            </div>
          </div>
        );
      },
    },
    {
      headerName: 'Type',
      field: 'type',
      flex: 1,
      filter: 'agTextColumnFilter',
      editable: false,
      cellClass:
        'text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
    },
    {
      headerName: 'Entries',
      field: 'entries',
      flex: 0.5,
      editable: false,
      cellClass:
        'text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
      valueFormatter: params => {
        return `${params.value} items`;
      },
    },
    {
      headerName: 'Size',
      field: 'size',
      flex: 1,
      valueFormatter: params => {
        return formatFileSize(params.value);
      },
      editable: false,
      cellClass:
        'text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
    },
    {
      headerName: 'Status',
      field: 'status',
      flex: 0.5,
      editable: false,
      cellClass:
        'cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
      cellRenderer: params => {
        const isActive = params.value === 'Active';
        return (
          <div
            className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
              isActive
                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
                : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300'
            }`}
          >
            {params.value}
          </div>
        );
      },
    },
    {
      headerName: 'Modified',
      field: 'updated_at',
      valueFormatter: params => {
        return new Date(params.value + 'Z').toLocaleString();
      },
      editable: false,
      flex: 1,
      resizable: false,
      cellClass:
        'text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
    },
    {
      maxWidth: 60,
      editable: false,
      resizable: false,
      cellClass: 'cursor-default',
      cellRenderer: params => {
        return (
          <div className="flex h-full cursor-default items-center justify-center">
            <Button variant="ghost" size="iconMd">
              <ForwardedIconComponent name="EllipsisVertical" />
            </Button>
          </div>
        );
      },
    },
  ];

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Shift') {
        setIsShiftPressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Shift') {
        setIsShiftPressed(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  const handleSelectionChanged = (event: SelectionChangedEvent) => {
    const selectedRows = event.api.getSelectedRows();
    setSelectedFiles(selectedRows);
    if (selectedRows.length > 0) {
      setQuantitySelected(selectedRows.length);
    } else {
      setTimeout(() => {
        setQuantitySelected(0);
      }, 300);
    }
  };

  const { mutate: rename } = usePostRenameFileV2();

  const { mutate: deleteFiles, isPending: isDeleting } = useDeleteFilesV2();
  const { handleBulkDownload } = useCustomHandleBulkFilesDownload();

  const handleRename = (params: NewValueParams<any, any>) => {
    rename({
      id: params.data.id,
      name: params.newValue,
    });
  };

  const handleOpenRename = (id: string, name: string) => {
    if (tableRef.current) {
      tableRef.current.api.startEditingCell({
        rowIndex: files?.findIndex(file => file.id === id) ?? 0,
        colKey: 'name',
      });
    }
  };

  const uploadFile = useUploadFile({ multiple: true });

  const handleUpload = async (files?: File[]) => {
    try {
      const filesIds = await uploadFile({
        files: files,
      });
      setSuccessData({
        title: `File${filesIds.length > 1 ? 's' : ''} uploaded successfully`,
      });
    } catch (error: any) {
      setErrorData({
        title: 'Error uploading file',
        list: [error.message || 'An error occurred while uploading the file'],
      });
    }
  };

  const { mutate: uploadFileDirect } = customPostUploadFileV2();

  useEffect(() => {
    if (files) {
      setQuantitySelected(0);
      setSelectedFiles([]);
    }
  }, [files]);

  const colDefs: ColDef[] = [
    {
      headerName: 'Name',
      field: 'name',
      flex: 2,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      editable: true,
      filter: 'agTextColumnFilter',
      cellClass:
        'cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
      cellRenderer: params => {
        const type = params.data.path.split('.')[1]?.toLowerCase();
        return (
          <div className="flex items-center gap-4 font-medium">
            {params.data.progress !== undefined &&
            params.data.progress !== -1 ? (
              <div className="flex h-6 items-center justify-center text-xs font-semibold text-muted-foreground">
                {Math.round(params.data.progress * 100)}%
              </div>
            ) : (
              <div className="file-icon pointer-events-none relative">
                <ForwardedIconComponent
                  name={FILE_ICONS[type]?.icon ?? 'File'}
                  className={cn(
                    '-mx-[3px] h-6 w-6 shrink-0',
                    params.data.progress !== undefined
                      ? 'text-placeholder-foreground'
                      : FILE_ICONS[type]?.color ?? undefined
                  )}
                />
              </div>
            )}
            <div
              className={cn(
                'flex items-center gap-2 text-sm font-medium',
                params.data.progress !== undefined &&
                  params.data.progress === -1 &&
                  'pointer-events-none text-placeholder-foreground'
              )}
            >
              {params.value}.{type}
            </div>
            {params.data.progress !== undefined &&
            params.data.progress === -1 ? (
              <span className="text-xs text-primary">
                Upload failed,{' '}
                <span
                  className="cursor-pointer text-accent-pink-foreground underline"
                  onClick={e => {
                    e.stopPropagation();
                    if (params.data.file) {
                      uploadFileDirect({ file: params.data.file });
                    }
                  }}
                >
                  try again?
                </span>
              </span>
            ) : (
              <></>
            )}
          </div>
        );
      }, //This column will be twice as wide as the others
    }, //This column will be twice as wide as the others
    {
      headerName: 'Type',
      field: 'path',
      flex: 1,
      filter: 'agTextColumnFilter',
      editable: false,
      valueFormatter: params => {
        return params.value.split('.')[1]?.toUpperCase();
      },
      cellClass:
        'text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
    },
    {
      headerName: 'Size',
      field: 'size',
      flex: 1,
      valueFormatter: params => {
        return formatFileSize(params.value);
      },
      editable: false,
      cellClass:
        'text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
    },
    {
      headerName: 'Modified',
      field: 'updated_at',
      valueFormatter: params => {
        return params.data.progress
          ? ''
          : new Date(params.value + 'Z').toLocaleString();
      },
      editable: false,
      flex: 1,
      resizable: false,
      cellClass:
        'text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none',
    },
    {
      maxWidth: 60,
      editable: false,
      resizable: false,
      cellClass: 'cursor-default',
      cellRenderer: params => {
        return (
          <div className="flex h-full cursor-default items-center justify-center">
            {!params.data.progress && (
              <FilesContextMenuComponent
                file={params.data}
                handleRename={handleOpenRename}
              >
                <Button variant="ghost" size="iconMd">
                  <ForwardedIconComponent name="EllipsisVertical" />
                </Button>
              </FilesContextMenuComponent>
            )}
          </div>
        );
      },
    },
  ];

  const onFileDrop = async (e: React.DragEvent) => {
    e.preventDefault;
    e.stopPropagation();
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      await handleUpload(droppedFiles);
    }
  };

  const handleDownload = () => {
    handleBulkDownload(
      selectedFiles,
      setSuccessData,
      setErrorData,
      setIsDownloading
    );
  };

  const handleDelete = () => {
    deleteFiles(
      {
        ids: selectedFiles.map(file => file.id),
      },
      {
        onSuccess: data => {
          setSuccessData({ title: data.message });
          setQuantitySelected(0);
          setSelectedFiles([]);
        },
        onError: error => {
          setErrorData({
            title: 'Error deleting files',
            list: [
              error.message || 'An error occurred while deleting the files',
            ],
          });
        },
      }
    );
  };

  const UploadButtonComponent = useMemo(() => {
    return (
      <ShadTooltip content="Upload File" side="bottom">
        <Button
          className="!px-3 md:!px-4 md:!pl-3.5"
          onClick={async () => {
            await handleUpload();
          }}
          id="upload-file-btn"
          data-testid="upload-file-btn"
        >
          <ForwardedIconComponent
            name="Plus"
            aria-hidden="true"
            className="h-4 w-4"
          />
          <span className="hidden whitespace-nowrap font-semibold md:inline">
            Upload
          </span>
        </Button>
      </ShadTooltip>
    );
  }, [uploadFile]);

  return (
    <div
      className="flex h-full w-full flex-col overflow-y-auto"
      data-testid="cards-wrapper"
    >
      <div className="flex h-full w-full flex-col xl:container">
        <div className="flex flex-1 flex-col justify-start px-5 pt-10">
          <div className="flex h-full flex-col justify-start">
            <div
              className="flex items-center pb-8 text-xl font-semibold"
              data-testid="mainpage_title"
            >
              <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
                <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
                  <SidebarTrigger>
                    <ForwardedIconComponent
                      name="PanelLeftOpen"
                      aria-hidden="true"
                      className=""
                    />
                  </SidebarTrigger>
                </div>
              </div>
              Assets
            </div>

            <Tabs
              defaultValue="files"
              className="flex h-full flex-col"
              onValueChange={setTabValue}
            >
              <TabsList className="mb-4 w-fit">
                <TabsTrigger value="files">Files</TabsTrigger>
                <TabsTrigger value="knowledge-bases">
                  Knowledge Bases
                </TabsTrigger>
              </TabsList>
              {tabValue === 'files' && (
                <TabsContent
                  hidden={true}
                  value="files"
                  className="flex h-full flex-col"
                >
                  {files && files.length !== 0 ? (
                    <div className="flex justify-between">
                      <div className="flex w-full xl:w-5/12">
                        <Input
                          icon="Search"
                          data-testid="search-store-input"
                          type="text"
                          placeholder={`Search files...`}
                          className="mr-2 w-full"
                          value={quickFilterText || ''}
                          onChange={event => {
                            setQuickFilterText(event.target.value);
                          }}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        {UploadButtonComponent}
                        {/* <ImportButtonComponent /> */}
                      </div>
                    </div>
                  ) : (
                    <></>
                  )}

                  <div className="flex h-full flex-col py-4">
                    {!files || !Array.isArray(files) ? (
                      <div className="flex h-full w-full items-center justify-center">
                        <Loading />
                      </div>
                    ) : files.length > 0 ? (
                      <DragWrapComponent onFileDrop={onFileDrop}>
                        <div className="relative h-full">
                          <TableComponent
                            rowHeight={45}
                            headerHeight={45}
                            cellSelection={false}
                            tableOptions={{
                              hide_options: true,
                            }}
                            suppressRowClickSelection={!isShiftPressed}
                            editable={[
                              {
                                field: 'name',
                                onUpdate: handleRename,
                                editableCell: true,
                              },
                            ]}
                            rowSelection="multiple"
                            onSelectionChanged={handleSelectionChanged}
                            columnDefs={colDefs}
                            rowData={files.sort((a, b) => {
                              return sortByDate(
                                a.updated_at ?? a.created_at,
                                b.updated_at ?? b.created_at
                              );
                            })}
                            className={cn(
                              'ag-no-border group w-full',
                              isShiftPressed &&
                                quantitySelected > 0 &&
                                'no-select-cells'
                            )}
                            pagination
                            ref={tableRef}
                            quickFilterText={quickFilterText}
                            gridOptions={{
                              stopEditingWhenCellsLoseFocus: true,
                              ensureDomOrder: true,
                              colResizeDefault: 'shift',
                            }}
                          />

                          <div
                            className={cn(
                              'pointer-events-none absolute top-1.5 z-50 flex h-8 w-full transition-opacity',
                              selectedFiles.length > 0
                                ? 'opacity-100'
                                : 'opacity-0'
                            )}
                          >
                            <div
                              className={cn(
                                'ml-12 flex h-full flex-1 items-center justify-between bg-background',
                                selectedFiles.length > 0
                                  ? 'pointer-events-auto'
                                  : 'pointer-events-none'
                              )}
                            >
                              <span className="text-xs text-muted-foreground">
                                {quantitySelected} selected
                              </span>
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="outline"
                                  size="iconMd"
                                  onClick={handleDownload}
                                  loading={isDownloading}
                                  data-testid="bulk-download-btn"
                                >
                                  <ForwardedIconComponent name="Download" />
                                </Button>

                                <DeleteConfirmationModal
                                  onConfirm={handleDelete}
                                  description={
                                    'file' + (quantitySelected > 1 ? 's' : '')
                                  }
                                >
                                  <Button
                                    variant="destructive"
                                    size="iconMd"
                                    className="px-2.5 !text-mmd"
                                    loading={isDeleting}
                                    data-testid="bulk-delete-btn"
                                  >
                                    <ForwardedIconComponent name="Trash2" />
                                    Delete
                                  </Button>
                                </DeleteConfirmationModal>
                              </div>
                            </div>
                          </div>
                        </div>
                      </DragWrapComponent>
                    ) : (
                      <CardsWrapComponent
                        onFileDrop={onFileDrop}
                        dragMessage="Drop files to upload"
                      >
                        <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
                          <div className="flex flex-col items-center gap-2">
                            <h3 className="text-2xl font-semibold">No files</h3>
                            <p className="text-lg text-secondary-foreground">
                              Upload files or import from your preferred cloud.
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {UploadButtonComponent}
                            {/* <ImportButtonComponent /> */}
                          </div>
                        </div>
                      </CardsWrapComponent>
                    )}
                  </div>
                </TabsContent>
              )}

              {tabValue === 'knowledge-bases' && (
                <TabsContent
                  hidden={true}
                  value="knowledge-bases"
                  className="flex h-full flex-col pb-4"
                >
                  {mockKnowledgeBases && mockKnowledgeBases.length !== 0 ? (
                    <div className="flex justify-between">
                      <div className="flex w-full xl:w-5/12">
                        <Input
                          icon="Search"
                          data-testid="search-kb-input"
                          type="text"
                          placeholder="Search knowledge bases..."
                          className="mr-2 w-full"
                          value={quickFilterText || ''}
                          onChange={event => {
                            setQuickFilterText(event.target.value);
                          }}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        {CreateKnowledgeBaseButtonComponent}
                      </div>
                    </div>
                  ) : (
                    <></>
                  )}

                  <div className="flex h-full flex-col py-4">
                    {!mockKnowledgeBases ||
                    !Array.isArray(mockKnowledgeBases) ? (
                      <div className="flex h-full w-full items-center justify-center">
                        <Loading />
                      </div>
                    ) : mockKnowledgeBases.length > 0 ? (
                      <div className="relative h-full">
                        <TableComponent
                          rowHeight={45}
                          headerHeight={45}
                          cellSelection={false}
                          tableOptions={{
                            hide_options: true,
                          }}
                          suppressRowClickSelection={!isShiftPressed}
                          editable={[
                            {
                              field: 'name',
                              onUpdate: (params: NewValueParams<any, any>) => {
                                // TODO: Implement knowledge base rename functionality
                                setSuccessData({
                                  title: 'Knowledge Base renamed successfully!',
                                });
                              },
                              editableCell: true,
                            },
                          ]}
                          rowSelection="multiple"
                          onSelectionChanged={handleSelectionChanged}
                          columnDefs={knowledgeBaseColDefs}
                          rowData={mockKnowledgeBases.sort((a, b) => {
                            return sortByDate(
                              a.updated_at ?? a.created_at,
                              b.updated_at ?? b.created_at
                            );
                          })}
                          className={cn(
                            'ag-no-border group w-full',
                            isShiftPressed &&
                              quantitySelected > 0 &&
                              'no-select-cells'
                          )}
                          pagination
                          ref={tableRef}
                          quickFilterText={quickFilterText}
                          gridOptions={{
                            stopEditingWhenCellsLoseFocus: true,
                            ensureDomOrder: true,
                            colResizeDefault: 'shift',
                          }}
                        />

                        <div
                          className={cn(
                            'pointer-events-none absolute top-1.5 z-50 flex h-8 w-full transition-opacity',
                            selectedFiles.length > 0
                              ? 'opacity-100'
                              : 'opacity-0'
                          )}
                        >
                          <div
                            className={cn(
                              'ml-12 flex h-full flex-1 items-center justify-between bg-background',
                              selectedFiles.length > 0
                                ? 'pointer-events-auto'
                                : 'pointer-events-none'
                            )}
                          >
                            <span className="text-xs text-muted-foreground">
                              {quantitySelected} selected
                            </span>
                            <div className="flex items-center gap-2">
                              <Button
                                variant="outline"
                                size="iconMd"
                                onClick={() => {
                                  // TODO: Implement knowledge base export functionality
                                  setSuccessData({
                                    title: 'Knowledge Base export coming soon!',
                                  });
                                }}
                                data-testid="bulk-export-kb-btn"
                              >
                                <ForwardedIconComponent name="Download" />
                              </Button>

                              <DeleteConfirmationModal
                                onConfirm={() => {
                                  // TODO: Implement knowledge base delete functionality
                                  setSuccessData({
                                    title:
                                      'Knowledge Base(s) deleted successfully!',
                                  });
                                  setQuantitySelected(0);
                                  setSelectedFiles([]);
                                }}
                                description={
                                  'knowledge base' +
                                  (quantitySelected > 1 ? 's' : '')
                                }
                              >
                                <Button
                                  variant="destructive"
                                  size="iconMd"
                                  className="px-2.5 !text-mmd"
                                  data-testid="bulk-delete-kb-btn"
                                >
                                  <ForwardedIconComponent name="Trash2" />
                                  Delete
                                </Button>
                              </DeleteConfirmationModal>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
                        <div className="flex flex-col items-center gap-2">
                          <h3 className="text-2xl font-semibold">
                            No knowledge bases
                          </h3>
                          <p className="text-lg text-secondary-foreground">
                            Create your first knowledge base to get started.
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {CreateKnowledgeBaseButtonComponent}
                        </div>
                      </div>
                    )}
                  </div>
                </TabsContent>
              )}
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FilesPage;
