import { useEffect, useState } from 'react';
import ForwardedIconComponent from '@/components/common/genericIconComponent';
import { SidebarTrigger } from '@/components/ui/sidebar';
import type { KnowledgeBaseInfo } from '@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases';
import KnowledgeBasesTab from '../filesPage/components/KnowledgeBasesTab';
import KnowledgeBaseDrawer from '../filesPage/components/KnowledgeBaseDrawer';

export const KnowledgePage = () => {
  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);
  const [quantitySelected, setQuantitySelected] = useState(0);
  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [quickFilterText, setQuickFilterText] = useState('');

  // State for drawer
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [selectedKnowledgeBase, setSelectedKnowledgeBase] =
    useState<KnowledgeBaseInfo | null>(null);

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

  const handleRowClick = (knowledgeBase: KnowledgeBaseInfo) => {
    setSelectedKnowledgeBase(knowledgeBase);
    setIsDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false);
    setSelectedKnowledgeBase(null);
  };

  const tabProps = {
    quickFilterText,
    setQuickFilterText,
    selectedFiles,
    setSelectedFiles,
    quantitySelected,
    setQuantitySelected,
    isShiftPressed,
    onRowClick: handleRowClick,
  };

  return (
    <div className="flex h-full w-full" data-testid="cards-wrapper">
      {/* Main Content */}
      <div
        className={`flex h-full w-full flex-col overflow-y-auto transition-all duration-200 ${
          isDrawerOpen ? 'mr-80' : ''
        }`}
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
                Knowledge
              </div>
              <div className="flex h-full flex-col">
                <KnowledgeBasesTab {...tabProps} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Drawer - Fixed position, flush right */}
      {isDrawerOpen && (
        <div className="fixed right-0 top-12 z-50 h-[calc(100vh-48px)]">
          <KnowledgeBaseDrawer
            isOpen={isDrawerOpen}
            onClose={handleCloseDrawer}
            knowledgeBase={selectedKnowledgeBase}
          />
        </div>
      )}
    </div>
  );
};

export default KnowledgePage;
