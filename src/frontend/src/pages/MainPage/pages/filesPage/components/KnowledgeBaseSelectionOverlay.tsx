import ForwardedIconComponent from '@/components/common/genericIconComponent';
import { Button } from '@/components/ui/button';
import { useDeleteKnowledgeBases } from '@/controllers/API/queries/knowledge-bases/use-delete-knowledge-bases';
import DeleteConfirmationModal from '@/modals/deleteConfirmationModal';
import useAlertStore from '@/stores/alertStore';
import { cn } from '@/utils/utils';

interface KnowledgeBaseSelectionOverlayProps {
  selectedFiles: any[];
  quantitySelected: number;
  onDelete?: () => void;
  onClearSelection: () => void;
}

const KnowledgeBaseSelectionOverlay = ({
  selectedFiles,
  quantitySelected,
  onDelete,
  onClearSelection,
}: KnowledgeBaseSelectionOverlayProps) => {
  const { setSuccessData, setErrorData } = useAlertStore(state => ({
    setSuccessData: state.setSuccessData,
    setErrorData: state.setErrorData,
  }));

  const deleteMutation = useDeleteKnowledgeBases({
    onSuccess: data => {
      setSuccessData({
        title: `${data.deleted_count} Knowledge Base(s) deleted successfully!`,
      });
      onClearSelection();
    },
    onError: (error: any) => {
      setErrorData({
        title: 'Failed to delete knowledge bases',
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            'An unknown error occurred',
        ],
      });
      onClearSelection();
    },
  });

  const handleBulkDelete = () => {
    if (onDelete) {
      onDelete();
    } else {
      const knowledgeBaseIds = selectedFiles.map(file => file.id);
      if (knowledgeBaseIds.length > 0 && !deleteMutation.isPending) {
        deleteMutation.mutate({ kb_names: knowledgeBaseIds });
      }
    }
  };

  const isVisible = selectedFiles.length > 0;
  const pluralSuffix = quantitySelected > 1 ? 's' : '';

  return (
    <div
      className={cn(
        'pointer-events-none absolute top-1.5 z-50 flex h-8 w-full transition-opacity',
        isVisible ? 'opacity-100' : 'opacity-0'
      )}
    >
      <div
        className={cn(
          'ml-12 flex h-full flex-1 items-center justify-between bg-background',
          isVisible ? 'pointer-events-auto' : 'pointer-events-none'
        )}
      >
        <span className="text-xs text-muted-foreground">
          {quantitySelected} selected
        </span>
        <div className="flex items-center gap-2">
          <DeleteConfirmationModal
            onConfirm={handleBulkDelete}
            description={`knowledge base${pluralSuffix}`}
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
  );
};

export default KnowledgeBaseSelectionOverlay;
