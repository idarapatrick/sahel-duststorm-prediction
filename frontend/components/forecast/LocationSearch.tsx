"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { KNOWN_LOCATIONS, type KnownLocation } from "@/lib/locations";

export function LocationSearch({
  onSelect,
  placeholder = "Search a location...",
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
      <Input placeholder={placeholder} value={query} onChange={(e) => setQuery(e.target.value)} />
      {matches.length > 0 && (
        <Card className="absolute z-10 mt-1 w-full overflow-hidden border-border/60 py-1">
          {matches.map((loc) => (
            <button
              key={loc.name}
              className="flex w-full flex-col px-4 py-2 text-left hover:bg-accent"
              onClick={() => {
                onSelect(loc);
                setQuery("");
              }}
            >
              <span className="text-sm font-medium">{loc.name}</span>
              <span className="text-xs text-muted-foreground">{loc.country}</span>
            </button>
          ))}
        </Card>
      )}
    </div>
  );
}
