"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { KNOWN_LOCATIONS, type KnownLocation } from "@/lib/locations";

export function LocationSearch({
  onSelect,
  placeholder = "Search a town...",
}: {
  onSelect: (location: KnownLocation) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");

  const matches = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return KNOWN_LOCATIONS.filter((loc) => loc.name.toLowerCase().includes(q)).slice(0, 6);
  }, [query]);

  return (
    <div className="relative">
      <div
        className="flex items-center gap-[10px] rounded-[18px] border px-[14px] py-3"
        style={{ background: "rgba(20,26,32,.58)", borderColor: "rgba(255,255,255,.13)" }}
      >
        <Search className="size-[18px] shrink-0 text-sd-muted" />
        <Input
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-auto border-0 bg-transparent p-0 text-sm font-medium text-sd-strong placeholder:text-sd-muted focus-visible:ring-0"
        />
      </div>
      {query.trim() && matches.length === 0 && (
        <Card className="absolute z-10 mt-1 w-full p-3">
          <p className="text-xs font-medium text-sd-muted">Location is not within African Sahel</p>
        </Card>
      )}
      {matches.length > 0 && (
        <Card className="absolute z-10 mt-1 max-h-[240px] w-full overflow-y-auto py-1">
          {matches.map((loc) => (
            <button
              key={loc.name}
              className="flex w-full flex-col px-4 py-2 text-left hover:bg-accent"
              onClick={() => {
                onSelect(loc);
                setQuery("");
              }}
            >
              <span className="text-sm font-medium text-sd-strong">{loc.name}</span>
              <span className="text-xs text-sd-muted">{loc.country}</span>
            </button>
          ))}
        </Card>
      )}
    </div>
  );
}
