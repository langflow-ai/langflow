import React, { useEffect, useState, useContext } from "react";
import { Button } from "../../components/ui/button";
import BaseModal from "../baseModal";
import { readTemplatesFromDatabase } from "../../controllers/API";
import { TabsContext } from "../../contexts/tabsContext";
import { useNavigate } from "react-router-dom";
import IconComponent from "../../components/genericIconComponent";
import { FlowType } from "../../types/flow";

type ViewType = 'options' | 'templates'; 

type NewProjectModalProps = {
  children: React.ReactNode;
  view?: ViewType;
  open?: boolean;
  flow?: FlowType;
};


const NewProjectModal: React.FC<NewProjectModalProps> = ({
  children, view: propView, open: propOpen, flow
}) => {
  const navigate = useNavigate();
  const { addFlow, saveFlow } = useContext(TabsContext);
  const [open, setOpen] = useState(propOpen || false);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<ViewType>(propView || "options");  // Initialize the view to "options"

  useEffect(() => {
    if (open && view === "templates") {
      setLoading(true);
      readTemplatesFromDatabase()
        .then(data => {
          setTemplates(data);
          setLoading(false);
        })
        .catch(error => {
          console.error("Error fetching templates:", error);
          setLoading(false);
        });
    }
  }, [open, view]);

  const handleTemplateSelection = async (template) => {
    const url = template.url;

    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const json = await response.json();

      // If the modal was opened with a flow passed in, update that flow
      if (flow) {
        saveFlow({...flow, data: json.data})
        window.location.reload();
      }
      else {
        addFlow(json, true, true)
          .then(id => {
            navigate("/form/" + id);
          })
          .catch(error => {
            console.error("Error while adding flow:", error);
          });
      }
    } catch (error) {
      console.error("There was a problem with the fetch operation:", error.message);
    }
  };

  return (
    <BaseModal size="small" open={open} setOpen={setOpen}>
      <BaseModal.Trigger>
        {children}
      </BaseModal.Trigger>

        {view === "options" ? (
                <BaseModal.Header description={"Create a new project"}>
                    <span className="pr-2">{"New Project"}</span>
                    <IconComponent
                    name="Plus"
                    className="h-6 w-6 pl-1 text-foreground"
                    aria-hidden="true"
                    />
                </BaseModal.Header>
            ) : (
                <BaseModal.Header description={"Choose a template as the base of your project"}>
                    <span className="pr-2">{"Templates"}</span>
                    <IconComponent
                    name="Clipboard"
                    className="h-6 w-6 pl-1 text-foreground"
                    aria-hidden="true"
                    />
                </BaseModal.Header>

            )
        }
      

      <BaseModal.Content>
        {view === "options" && (
          <div className="flex justify-between p-6 space-x-6">

            {/* Simple Mode */}
            <div className="flex flex-col items-center w-1/2 border p-4 rounded-lg">
                <IconComponent
                    name="Clipboard"
                    className="h-8 w-8 mb-2 text-foreground"
                    aria-hidden="true"
                />
                <h3 className="font-bold text-md mb-2">Simple Mode</h3>
                <p className="text-center mb-4">Start with a template and use our form-based editor to get started quickly.</p>
                <Button onClick={() => setView("templates")}>Choose Template</Button>
            </div>

            {/* Advanced Mode */}
            <div className="flex flex-col items-center w-1/2 border p-4 rounded-lg">
                <IconComponent
                    name="Gear"
                    className="h-8 w-8 mb-2 text-foreground"
                    aria-hidden="true"
                />
                <h3 className="font-bold text-md mb-2">Advanced Mode</h3>
                <p className="text-center mb-4">Dive into our diagram editor for advanced project configurations.</p>
                <Button onClick={() => {
                    addFlow(null, true).then((id) => {
                        navigate("/flow/" + id);
                    });
                }}>Configure Diagram Editor</Button>
            </div>

        </div>
        )}

        {view === "templates" && (
          <div>
            <Button onClick={() => setView("options")} className="mb-4">
              Back to Options
            </Button>

            <div className="template-cards-container">
              {loading && <p>Loading templates...</p>}
              {templates.map(template => (
                <div
                  key={template.id}
                  className="template-card"
                  onClick={() => handleTemplateSelection(template)}
                >
                  <h3 className="font-bold text-sm">{template.name}</h3>
                  <p className="text-xs">{template.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </BaseModal.Content>
    </BaseModal>
  );
};

export default NewProjectModal;
