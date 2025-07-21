import type { ColDef, NewValueParams } from 'ag-grid-community';
import ForwardedIconComponent from '@/components/common/genericIconComponent';
import { Button } from '@/components/ui/button';
import { formatFileSize } from '@/utils/stringManipulation';
import {
  formatAverageChunkSize,
  formatNumber,
} from '../utils/knowledgeBaseUtils';

export const createKnowledgeBaseColumns = (
  onRename?: (params: NewValueParams<any, any>) => void,
  onDelete?: (knowledgeBase: any) => void
): ColDef[] => {
  const baseCellClass =
    'text-muted-foreground cursor-pointer select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none';

  return [
    {
      headerName: 'Name',
      field: 'name',
      flex: 2,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      editable: true,
      filter: 'agTextColumnFilter',
      cellClass: baseCellClass,
      cellRenderer: params => (
        <div className="flex items-center gap-3 font-medium">
          <div className="flex flex-col">
            <div className="text-sm font-medium">{params.value}</div>
          </div>
        </div>
      ),
    },
    {
      headerName: 'Embedding Model',
      field: 'embedding_provider',
      flex: 1.2,
      filter: 'agTextColumnFilter',
      editable: false,
      cellClass: baseCellClass,
      tooltipValueGetter: params => params.data.embedding_model || 'Unknown',
      valueGetter: params => params.data.embedding_model || 'Unknown',
    },
    {
      headerName: 'Size',
      field: 'size',
      flex: 0.8,
      valueFormatter: params => formatFileSize(params.value),
      editable: false,
      cellClass: baseCellClass,
    },
    {
      headerName: 'Words',
      field: 'words',
      flex: 0.8,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: params => formatNumber(params.value),
    },
    {
      headerName: 'Characters',
      field: 'characters',
      flex: 1,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: params => formatNumber(params.value),
    },
    {
      headerName: 'Chunks',
      field: 'chunks',
      flex: 0.7,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: params => formatNumber(params.value),
    },
    {
      headerName: 'Avg Chunks',
      field: 'avg_chunk_size',
      flex: 1,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: params => formatAverageChunkSize(params.value),
    },
    {
      maxWidth: 60,
      editable: false,
      resizable: false,
      cellClass: 'cursor-default',
      cellRenderer: params => {
        const handleDeleteClick = () => {
          if (onDelete) {
            onDelete(params.data);
          }
        };

        return (
          <div className="flex h-full cursor-default items-center justify-center">
            <Button
              variant="ghost"
              size="iconMd"
              onClick={handleDeleteClick}
              className="hover:bg-destructive/10"
            >
              <ForwardedIconComponent
                name="Trash2"
                className="h-4 w-4 text-destructive"
              />
            </Button>
          </div>
        );
      },
    },
  ];
};
