"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function PhoneStep({
  title,
  subtitle,
  onSubmit,
}: {
  title: string;
  subtitle: string;
  onSubmit: (phone: string) => void;
}) {
  const [phone, setPhone] = useState("");

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
      </div>
      <Input
        type="tel"
        placeholder="+227 90 00 00 00"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
      />
      <Button disabled={phone.trim().length < 6} onClick={() => onSubmit(phone.trim())}>
        Send code
      </Button>
    </div>
  );
}
