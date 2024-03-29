import { Group, ToyBrick } from "lucide-react";
import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import DropdownButton from "../../components/DropdownButtonComponent";
import NewFlowCardComponent from "../../components/NewFLowCard2";
import IconComponent from "../../components/genericIconComponent";
import PageLayout from "../../components/pageLayout";
import SidebarNav from "../../components/sidebarComponent";
import { Button } from "../../components/ui/button";
import UndrawCardComponent from "../../components/undrawCards";
import { CONSOLE_ERROR_MSG } from "../../constants/alerts_constants";
import {
  MY_COLLECTION_DESC,
  USER_PROJECTS_HEADER,
} from "../../constants/constants";
import BaseModal from "../../modals/baseModal";
import useAlertStore from "../../stores/alertStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { downloadFlows } from "../../utils/reactflowUtils";
export default function HomePage(): JSX.Element {
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId
  );
  const uploadFlows = useFlowsManagerStore((state) => state.uploadFlows);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const location = useLocation();
  const pathname = location.pathname;
  const [openModal, setOpenModal] = useState(false);
  const examples = useFlowsManagerStore((state) => state.examples);
  const is_component = pathname === "/components";
  const dropdownOptions = [
    {
      name: "Import from JSON",
      onBtnClick: () => {
        uploadFlow({
          newProject: true,
          isComponent: is_component,
        })
          .then((id) => {
            setSuccessData({
              title: `${
                is_component ? "Component" : "Flow"
              } uploaded successfully`,
            });
            if (!is_component) navigate("/flow/" + id);
          })
          .catch((error) => {
            setErrorData({
              title: CONSOLE_ERROR_MSG,
              list: [error],
            });
          });
      },
    },
  ];
  const sidebarNavItems = [
    {
      title: "Flows",
      href: "/flows",
      icon: <Group className="w-5 stroke-[1.5]" />,
    },
    {
      title: "Components",
      href: "/components",
      icon: <ToyBrick className="mx-[0.08rem] w-[1.1rem] stroke-[1.5]" />,
    },
  ];

  // Set a null id
  useEffect(() => {
    setCurrentFlowId("");
  }, [pathname]);

  const navigate = useNavigate();

  // Personal flows display
  return (
    <PageLayout
      title={USER_PROJECTS_HEADER}
      description={MY_COLLECTION_DESC}
      button={
        <div className="flex gap-2">
          <Button
            variant="primary"
            onClick={() => {
              downloadFlows();
            }}
          >
            <IconComponent name="Download" className="main-page-nav-button" />
            Download Collection
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              uploadFlows();
            }}
          >
            <IconComponent name="Upload" className="main-page-nav-button" />
            Upload Collection
          </Button>
          <DropdownButton
            firstButtonName="New Project"
            onFirstBtnClick={() => setOpenModal(true)}
            options={dropdownOptions}
            plusButton={true}
            dropdownOptions={false}
          />
        </div>
      }
    >
      <div className="flex h-full w-full space-y-8 lg:flex-row lg:space-x-8 lg:space-y-0">
        <aside className="flex h-full flex-col space-y-6 lg:w-1/5">
          <SidebarNav items={sidebarNavItems} />
        </aside>
        <div className="h-full w-full flex-1">
          <Outlet />
        </div>
      </div>
      <BaseModal size="three-cards" open={openModal} setOpen={setOpenModal}>
        <BaseModal.Header description={"Select a template below"}>
          <span className="pr-2" data-testid="modal-title">
            Get Started
          </span>
          {/* <IconComponent
            name="Group"
            className="h-6 w-6 stroke-2 text-primary "
            aria-hidden="true"
          /> */}
        </BaseModal.Header>
        <BaseModal.Content>
          <div className=" grid h-full w-full grid-cols-3 gap-3 overflow-auto p-4 custom-scroll">
            <NewFlowCardComponent />
            {examples.map((example, idx) => {
              return <UndrawCardComponent key={idx} flow={example} />;
            })}
          </div>
        </BaseModal.Content>
      </BaseModal>
    </PageLayout>
  );
}
