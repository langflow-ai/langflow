import { ALL_LANGUAGES } from "@/constants/constants";
import IconComponent from "../../../../../../../../../../components/common/genericIconComponent";
import ShadTooltip from "../../../../../../../../../../components/common/shadTooltipComponent";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../../../../../../../../components/ui/select";

interface LanguageSelectProps {
  language: string;
  handleSetLanguage: (value: string) => void;
}

const LanguageSelect = ({
  language,
  handleSetLanguage,
}: LanguageSelectProps) => {
  return (
    <div className="grid w-full items-center gap-2">
      <span className="flex w-full items-center text-sm">
        Preferred Language
        <ShadTooltip content="Select the language for speech recognition">
          <div>
            <IconComponent
              name="Info"
              strokeWidth={2}
              className="relative -top-[3px] left-1 h-[14px] w-[14px] text-placeholder"
            />
          </div>
        </ShadTooltip>
      </span>

      <Select value={language} onValueChange={handleSetLanguage}>
        <SelectTrigger className="h-9 w-full">
          <SelectValue placeholder="Select language" />
        </SelectTrigger>
        <SelectContent className="max-h-[200px]">
          <SelectGroup>
            {ALL_LANGUAGES?.map((lang) => (
              <SelectItem key={lang?.value} value={lang?.value}>
                <div className="max-w-[220px] truncate text-left">
                  {lang?.name}
                </div>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
};

export default LanguageSelect;
