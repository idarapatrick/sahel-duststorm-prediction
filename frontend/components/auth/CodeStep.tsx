"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { isValidCode } from "@/lib/phoneLink";
import { toast } from "sonner";

export function CodeStep({
  phone,
  onVerified,
}: {
  phone: string;
  onVerified: () => void;
}) {
  const [code, setCode] = useState("");

  function verify() {
    if (!isValidCode(code)) {
      toast.error("Enter the 6-digit code");
      return;
    }
    onVerified();
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Enter the code</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          We sent a 6-digit code to {phone}. (This is a prototype — any 6 digits work.)
        </p>
      </div>
      <Input
        inputMode="numeric"
        placeholder="123456"
        maxLength={6}
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
      />
      <Button onClick={verify}>Verify</Button>
    </div>
  );
}
