"use client";

import { useState } from "react";
import { MapPin, Search } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { LocationSearch } from "@/components/forecast/LocationSearch";
import { useSelectedLocation } from "@/components/providers/LocationProvider";
import { cn } from "@/lib/utils";

export function LocationPill({ variant = "plain" }: { variant?: "plain" | "field" }) {
  const { location, setLocation } = useSelectedLocation();
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label={`Change location, currently ${location.name}`}
        className={cn(
          "flex items-center gap-[8px]",
          variant === "field"
            ? "w-full rounded-[14px] border px-[13px] py-3"
            : "rounded-full border py-[6px] pl-[5px] pr-3"
        )}
        style={{
          background: variant === "field" ? "rgba(12,16,20,.62)" : "rgba(12,16,20,.5)",
          borderColor: variant === "field" ? "rgba(255,255,255,.1)" : "rgba(255,255,255,.16)",
        }}
      >
        <span
          className={cn(
            "flex shrink-0 items-center justify-center rounded-full",
            variant === "plain" && "size-[26px]"
          )}
          style={variant === "plain" ? { background: "rgba(242,193,78,.18)" } : undefined}
        >
          <MapPin className={cn("size-[17px] text-[#F2C14E]", variant === "plain" && "size-[14px] sky-icon")} />
        </span>
        <span
          className={cn(
            "font-bold text-sd-strong",
            variant === "field" ? "flex-1 text-left text-[14px] font-semibold" : "text-[15px] sky-text"
          )}
        >
          {location.name}
          {variant === "field" && location.country ? `, ${location.country}` : ""}
        </span>
        <Search className={cn("size-[15px] shrink-0 text-sd-muted", variant === "plain" && "sky-icon")} />
      </button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="bottom" className="border-border bg-background/95 backdrop-blur-2xl">
          <SheetHeader>
            <SheetTitle>Choose a location</SheetTitle>
          </SheetHeader>
          <div className="px-4 pb-6">
            <LocationSearch
              onSelect={(loc) => {
                setLocation(loc);
                setOpen(false);
              }}
            />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
