import { Listbox, Transition } from "@headlessui/react";
import { Fragment, useContext, useEffect, useState } from "react";
import { DropDownComponentType } from "../../types/components";
import { classNames } from "../../utils";
import { INPUT_STYLE } from "../../constants";
import { ChevronsUpDown, Check } from "lucide-react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import { DropdownNode } from "./dropDownNodeComponent/index";

export default function Dropdown({
  value,
  options,
  onSelect,
  editNode = false,
  numberOfOptions = 0,
}) {
  return (
    <DropdownNode value={value} options={options} onSelect={onSelect} />
  );
}