import { useContext } from "react";
import { TabsContext } from "../../contexts/tabsContext";
import { gradients } from "../../utils/styleUtils";
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
    imageUrl: string;
    creator: {
      name: string;
      id: string;
      imageUrl: string;
    };
    categories: string[];
    type: string;
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
          <div className="absolute bottom-2 right-2 flex items-center gap-2 rounded-lg bg-black/30 p-1 px-2 text-xs text-background">
            <IconComponent name="Download" className="h-3 w-3" />
            {nFormatter(data.downloads, 2)}
          </div>
          <img className={"h-20 w-20 rounded-full"} src={data.imageUrl}></img>
        </div>
        <CardHeader>
          {/* 
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
          </div> */}
          <div>
            <CardTitle className="card-component-title-display text-xl">
              <span className="card-component-title-size flex items-center gap-2">
                {data.name}{" "}
                {data.categories.map((category) => (
                  <IconComponent name={category} className="h-5 w-5" />
                ))}
              </span>
            </CardTitle>
            <span className="inline-flex items-center text-sm">
              <img
                className="mr-2 h-4 w-4 rounded-full"
                src={data.creator.imageUrl}
              />
              {data.creator.name}
            </span>
          </div>
          <CardDescription className="card-component-desc">
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
