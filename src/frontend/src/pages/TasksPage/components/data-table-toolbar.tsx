"use client";

import { Input } from "@/components/ui/input";
import React from "react";

interface DataTableToolbarProps {
  value: string;
  onChange: (value: string) => void;
}

export function DataTableToolbar({ value, onChange }: DataTableToolbarProps) {
  return (
    <div className="flex items-center justify-between">
      <Input
        placeholder="Filter tasks..."
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 w-[150px] lg:w-[250px]"
      />
    </div>
  );
}
