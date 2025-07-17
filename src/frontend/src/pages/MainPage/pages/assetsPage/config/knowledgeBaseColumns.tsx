import type { ColDef, NewValueParams } from 'ag-grid-community';
import ForwardedIconComponent from '@/components/common/genericIconComponent';
import { Button } from '@/components/ui/button';
import { formatFileSize } from '@/utils/stringManipulation';
import {
  formatNumber,
  formatAverageChunkSize,
} from '../utils/knowledgeBaseUtils';

export const createKnowledgeBaseColumns = (
  onRename?: (params: NewValueParams<any, any>) => void
): ColDef[] => {
  const cellClassStyles =
    'text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none';

  return [
    {
      headerName: 'Name',
      field: 'name',
      flex: 2,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      editable: true,
      filter: 'agTextColumnFilter',
      cellClass: cellClassStyles,
      cellRenderer: params => {
        return (
          <div className="flex items-center gap-3 font-medium">
            <div className="flex flex-col">
              <div className="text-sm font-medium">{params.value}</div>
            </div>
          </div>
        );
      },
    },
    {
      headerName: 'Embedding Provider',
      field: 'embedding_provider',
      flex: 1.2,
      filter: 'agTextColumnFilter',
      editable: false,
      cellClass: cellClassStyles,
      cellRenderer: params => {
        return (
          <div className="flex items-center gap-2">
            <span className="text-sm">{params.value || 'Unknown'}</span>
          </div>
        );
      },
    },
    {
      headerName: 'Size',
      field: 'size',
      flex: 0.8,
      valueFormatter: params => {
        return formatFileSize(params.value);
      },
      editable: false,
      cellClass: cellClassStyles,
    },
    {
      headerName: 'Words',
      field: 'words',
      flex: 0.8,
      editable: false,
      cellClass: cellClassStyles,
      valueFormatter: params => {
        return formatNumber(params.value);
      },
    },
    {
      headerName: 'Characters',
      field: 'characters',
      flex: 1,
      editable: false,
      cellClass: cellClassStyles,
      valueFormatter: params => {
        return formatNumber(params.value);
      },
    },
    {
      headerName: 'Chunks',
      field: 'chunks',
      flex: 0.7,
      editable: false,
      cellClass: cellClassStyles,
      valueFormatter: params => {
        return formatNumber(params.value);
      },
    },
    {
      headerName: 'Avg Chunks',
      field: 'avg_chunk_size',
      flex: 1,
      editable: false,
      cellClass: cellClassStyles,
      valueFormatter: params => {
        return formatAverageChunkSize(params.value);
      },
    },
    {
      maxWidth: 60,
      editable: false,
      resizable: false,
      cellClass: 'cursor-default',
      cellRenderer: () => {
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
};
