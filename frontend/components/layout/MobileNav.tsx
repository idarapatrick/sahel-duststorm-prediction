"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sun, MapPin, Activity, Bell } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/", label: "Today", icon: Sun },
  { href: "/location", label: "My area", icon: MapPin },
  { href: "/progressive", label: "Tracking", icon: Activity },
  { href: "/alerts", label: "Alerts", icon: Bell },
];

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed left-3.5 right-3.5 bottom-3.5 z-50 mx-auto flex h-16 max-w-3xl items-stretch justify-around rounded-[26px] border border-border shadow-[0_12px_30px_rgba(0,0,0,0.32)] backdrop-blur-xl backdrop-saturate-[140%]"
      style={{ background: "rgba(16,21,26,.72)" }}
    >
      {TABS.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-1 text-[10px]",
              active ? "font-bold text-[#F2C14E]" : "font-semibold text-sd-faint"
            )}
          >
            <Icon className="size-[22px]" strokeWidth={2} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
