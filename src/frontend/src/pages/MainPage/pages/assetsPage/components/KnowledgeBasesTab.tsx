import type {
  ColDef,
  NewValueParams,
  SelectionChangedEvent,
} from 'ag-grid-community';
import type { AgGridReact } from 'ag-grid-react';
import { useMemo, useRef, useState } from 'react';
import ForwardedIconComponent from '@/components/common/genericIconComponent';
import ShadTooltip from '@/components/common/shadTooltipComponent';
import TableComponent from '@/components/core/parameterRenderComponent/components/tableComponent';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Loading from '@/components/ui/loading';
import DeleteConfirmationModal from '@/modals/deleteConfirmationModal';
import useAlertStore from '@/stores/alertStore';
import { formatFileSize } from '@/utils/stringManipulation';
import { cn } from '@/utils/utils';
import { sortByDate } from '../../../utils/sort-flows';

interface KnowledgeBasesTabProps {
  quickFilterText: string;
  setQuickFilterText: (text: string) => void;
  selectedFiles: any[];
  setSelectedFiles: (files: any[]) => void;
  quantitySelected: number;
  setQuantitySelected: (quantity: number) => void;
  isShiftPressed: boolean;
}

const KnowledgeBasesTab = ({
  quickFilterText,
  setQuickFilterText,
  selectedFiles,
  setSelectedFiles,
  quantitySelected,
  setQuantitySelected,
  isShiftPressed,
}: KnowledgeBasesTabProps) => {
  const tableRef = useRef<AgGridReact<any>>(null);
  const setErrorData = useAlertStore(state => state.setErrorData);
  const setSuccessData = useAlertStore(state => state.setSuccessData);

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
  }, [setSuccessData]);

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

  return (
    <div className="flex h-full flex-col pb-4">
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

      <div className="flex h-full flex-col pt-4">
        {!mockKnowledgeBases || !Array.isArray(mockKnowledgeBases) ? (
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
                isShiftPressed && quantitySelected > 0 && 'no-select-cells'
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
                selectedFiles.length > 0 ? 'opacity-100' : 'opacity-0'
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
                        title: 'Knowledge Base(s) deleted successfully!',
                      });
                      setQuantitySelected(0);
                      setSelectedFiles([]);
                    }}
                    description={
                      'knowledge base' + (quantitySelected > 1 ? 's' : '')
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
              <h3 className="text-2xl font-semibold">No knowledge bases</h3>
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
    </div>
  );
};

export default KnowledgeBasesTab;
