import { useContext } from "react";
import { TabsContext } from "../../contexts/tabsContext";
import { nFormatter } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Badge } from "../ui/badge";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../ui/card";

export const MarketCardComponentComponent = ({
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
    isChat: boolean;
  };
  onAdd: () => void;
}) => {
  const { removeFlow } = useContext(TabsContext);

  return (
    <Card className="group relative cursor-pointer overflow-hidden">
      <div>
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
            <CardTitle className="card-component-title-display justify-between text-xl">
              <span className="card-component-title-size flex items-center gap-2">
                {data.name}{" "}
                <IconComponent name="Component" className="h-5 w-5" />
              </span>
              <div className="flex items-center gap-2 rounded-lg bg-black/5 p-1 px-2 text-xs text-foreground transition-all hover:bg-black/20">
                <IconComponent name="Download" className="h-3 w-3" />
                {nFormatter(data.downloads, 2)}
              </div>
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
          <div className="card-component-footer w-full justify-between">
            <div className=" flex gap-2 rounded-xl">
              <span className="flex items-center gap-1.5 text-xs text-foreground">
                Output:{" "}
                <IconComponent name={data.categories[0]} className="h-4 w-4" />
              </span>
            </div>
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
        </div>
      </CardFooter>
    </Card>
  );
};
