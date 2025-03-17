import { Card, CardContent, CardHeader, CardTitle } from "../../../../../../components/ui/card";
import { Skeleton } from "../../../../../../components/ui/skeleton";
import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";

interface StatusCardProps {
  title: string;
  value: string;
  icon: string;
  description?: string;
  variant?: "default" | "success" | "destructive";
  isLoading?: boolean;
}

export default function StatusCard({
  title,
  value,
  icon,
  description,
  variant = "default",
  isLoading = false,
}: StatusCardProps) {
  const getVariantClasses = () => {
    switch (variant) {
      case "success":
        return "text-green-500";
      case "destructive":
        return "text-red-500";
      default:
        return "text-primary";
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <ForwardedIconComponent
          name={icon}
          className="h-4 w-4 text-muted-foreground"
        />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-full" />
        ) : (
          <div className={`text-2xl font-bold ${getVariantClasses()}`}>
            {value}
          </div>
        )}
        {description && (
          <p className="text-xs text-muted-foreground mt-1">
            {description}
          </p>
        )}
      </CardContent>
    </Card>
  );
} 