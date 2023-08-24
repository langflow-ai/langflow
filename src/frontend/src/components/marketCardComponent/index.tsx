import { useContext } from "react";
import { TabsContext } from "../../contexts/tabsContext";
import {
  gradients,
  nodeColors,
  nodeNames,
  tagGradients,
  tagText,
} from "../../utils/styleUtils";
import { nFormatter } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../ui/card";

export const MarketCardComponent = ({
  data,
  onAdd,
}: {
  data: {
    name: string;
    description: string;
    id: string;
    creator: string;
    creatorId: string;
    creatorImageUrl: string;
    imageUrl: string;
    tags: string[];
    category: string;
    usesNumber: string;
    downloads: string;
    isFree: boolean;
  };
  onAdd: () => void;
}) => {
  const { removeFlow } = useContext(TabsContext);

  return (
    <Card className="group overflow-hidden">
      <div>
        <div
          className={
            "relative flex h-40 w-full items-center justify-center " +
            gradients[parseInt(data.id, 35) % gradients.length]
          }
        >
          <div className="absolute bottom-2 left-2 flex items-center gap-2 rounded-lg bg-black/30 p-1 px-2 text-xs text-background">
            <img className="h-4 w-4 rounded-full" src={data.creatorImageUrl} />
            {data.creator}
          </div>
          <div className="absolute bottom-2 right-2 flex items-center gap-2 rounded-lg bg-black/30 p-1 px-2 text-xs text-background">
            <IconComponent name="Download" className="h-3 w-3" />
            {nFormatter(data.downloads, 2)}
          </div>
          <div
            className={
              "absolute left-0 top-0 flex items-center gap-2 rounded-br-lg p-1 px-2 text-xs text-background"
            }
            style={{ backgroundColor: nodeColors[data.category] }}
          >
            <IconComponent name={data.category} className="h-3 w-3" />
            {nodeNames[data.category]}
          </div>

          <img className={"h-20 w-20 rounded-full"} src={data.imageUrl}></img>
        </div>
        <CardHeader>
          <div className="mb-2 flex flex-wrap gap-1">
            {data.tags.map((tag) => (
              <Badge
                size="sm"
                className={
                  tagGradients[parseInt(tag, 35) % tagGradients.length] +
                  " " +
                  tagText[parseInt(tag, 35) % tagText.length]
                }
              >
                {tag}
              </Badge>
            ))}
          </div>
          <CardTitle className="card-component-title-display text-xl">
            <span className="card-component-title-size">{data.name}</span>
          </CardTitle>
          <CardDescription className="card-component-desc pt-0">
            <div className="card-component-desc-text">{data.description}</div>
          </CardDescription>
        </CardHeader>
      </div>

      <CardFooter>
        <div className="card-component-footer-arrangement items-center">
          <div className="card-component-footer">
            {data.isFree ? (
              <Badge size="md" variant="free">
                Free
              </Badge>
            ) : (
              <Badge size="md" variant="paid">
                Pro
              </Badge>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="whitespace-nowrap "
            onClick={onAdd}
          >
            <IconComponent name="Plus" className="main-page-nav-button" />
            Add Component
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
};
