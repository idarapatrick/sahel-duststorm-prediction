"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, Info, ShieldCheck, Wind } from "lucide-react";
import { Card } from "@/components/ui/card";
import { DustySky } from "@/components/layout/DustySky";
import { getLinkedPhone, unlinkPhone } from "@/lib/phoneLink";
import { toast } from "sonner";

export default function SettingsPage() {
  const [linkedPhone, setLinkedPhone] = useState<string | null>(null);

  useEffect(() => {
    setLinkedPhone(getLinkedPhone());
  }, []);

  function handleUnlink() {
    unlinkPhone();
    setLinkedPhone(null);
    toast.success("Phone unlinked");
  }

  return (
    <DustySky glow="left">
      <div className="flex flex-1 flex-col gap-4 px-[18px] pt-2">
        <div className="mt-1 flex items-center gap-3">
          <div
            className="flex size-[46px] items-center justify-center rounded-[15px] shadow-[0_8px_20px_rgba(229,83,59,0.32)]"
            style={{ background: "linear-gradient(150deg,#F2C14E,#E5533B)" }}
          >
            <Wind className="size-6 text-[#20272e]" />
          </div>
          <div className="sky-text">
            <p className="text-[22px] font-extrabold text-sd-strong">SahelDust</p>
            <p className="mt-[1px] text-[13px] font-medium text-sd-primary">
              Simple dust-storm warnings for the Sahel.
            </p>
          </div>
        </div>

        <Card className="mt-1 gap-2 p-5">
          <p className="text-[13px] font-bold text-sd-primary">Phone for alerts</p>
          {linkedPhone ? (
            <>
              <p className="flex items-center gap-2 text-sm text-sd-secondary">
                <ShieldCheck className="size-4 text-[#6FCF97]" />
                {linkedPhone}
              </p>
              <div className="mt-1 flex gap-4 text-sm">
                <Link href="/link-phone?redirect=/settings" className="font-bold text-[#F2C14E]">
                  Change number
                </Link>
                <button onClick={handleUnlink} className="font-bold text-[#E5533B]">
                  Unlink
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-sd-secondary">
                No phone linked yet. Link one to turn on alerts.
              </p>
              <Link href="/link-phone?redirect=/settings" className="mt-1 text-sm font-bold text-[#F2C14E]">
                Link phone number
              </Link>
            </>
          )}
        </Card>

        <Link href="/about">
          <Card className="flex-row items-center justify-between p-5">
            <span className="flex items-center gap-2 text-[13px] font-bold text-sd-primary">
              <Info className="size-4 text-sd-muted" />
              About SahelDust
            </span>
            <ChevronRight className="size-4 text-sd-faint" />
          </Card>
        </Link>

        <p className="mt-2 text-center text-[11px] font-medium text-sd-faint">
          Built for Sahel communities &middot; v1.0
        </p>
      </div>
    </DustySky>
  );
}
