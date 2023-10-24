import { Link, ToyBrick } from "lucide-react";
import { useState } from "react";
import IconComponent from "../../../components/genericIconComponent";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { FlowComponent } from "../../../types/store";

export const MarketCardComponent = ({
  data,
  onAdd,
}: {
  data: FlowComponent;
  onAdd: () => void;
}) => {
  const [added, setAdded] = useState(false);

  return (
    <Card className="group relative flex cursor-pointer flex-col justify-between overflow-hidden transition-all hover:shadow-md">
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
            <CardTitle className="flex w-full items-center justify-between gap-3 text-xl">
              <span className="flex w-full items-center gap-2 word-break-break-word">
                {data.name}
              </span>
              <Badge size="sm" variant="gray">
                Free
              </Badge>
            </CardTitle>
            {/* <span className="inline-flex items-center text-sm">
              <img
                className="mr-2 h-4 w-4 rounded-full"
                src={data.image}
              />
              {data.creator.name}
            </span>
            <span className="flex text-xs items-center gap-2 text-ring">
              <Download className="h-3 w-3" />
              {nFormatter(data.downloads, 2)}
            </span> */}
          </div>
          <CardDescription className="pb-2 pt-2">
            <div className="truncate-doubleline">{data.description}</div>
          </CardDescription>
        </CardHeader>
      </div>

      <CardFooter>
        <div className="flex w-full items-center justify-between gap-2">
          <div className="flex w-full flex-wrap items-end justify-between gap-2">
            <div className=" flex items-center gap-3">
              <Badge size="md" variant="outline">
                chain
                <Link className="ml-1.5 w-3 text-green-700" />
              </Badge>
              <span className="flex items-center gap-1.5 text-xs text-foreground">
                <ToyBrick className="h-4 w-4" />
                123
              </span>
            </div>
            {/* {data.isChat ? (
              <Button size="sm" variant="outline">
                <Plus className="h-4 mr-2" />
                Add
              </Button>
            ) : (
              <Button size="sm" variant="success">
                <Check className="h-4 mr-2" />
                Added
              </Button>
            )} */}
            <Button
              variant="outline"
              size="sm"
              className="whitespace-nowrap "
              onClick={() => {
                if (!added) {
                  setAdded(true);
                } else {
                  //download
                }
                onAdd();
              }}
            >
              <IconComponent
                name={added ? "GitBranchPlus" : "BookmarkPlus"}
                className="main-page-nav-button"
              />
              {added ? "Install Localy" : "Add to Account"}
            </Button>
          </div>
        </div>
      </CardFooter>
    </Card>
  );
};
