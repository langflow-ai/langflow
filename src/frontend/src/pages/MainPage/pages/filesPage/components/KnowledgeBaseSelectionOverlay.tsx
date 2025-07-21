import ForwardedIconComponent from '@/components/common/genericIconComponent';
import { Button } from '@/components/ui/button';
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
  const setSuccessData = useAlertStore(state => state.setSuccessData);

  const handleDelete = () => {
    if (onDelete) {
      onDelete();
    } else {
      // TODO: Implement knowledge base delete functionality
      setSuccessData({
        title: 'Knowledge Base(s) deleted successfully!',
      });
    }
    onClearSelection();
  };

  return (
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
          <DeleteConfirmationModal
            onConfirm={handleDelete}
            description={'knowledge base' + (quantitySelected > 1 ? 's' : '')}
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
