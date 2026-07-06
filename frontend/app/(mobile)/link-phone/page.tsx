"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PhoneStep } from "@/components/auth/PhoneStep";
import { CodeStep } from "@/components/auth/CodeStep";
import { DustySky } from "@/components/layout/DustySky";
import { linkPhone } from "@/lib/phoneLink";
import { toast } from "sonner";

function LinkPhoneForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/alerts";
  const [phone, setPhone] = useState<string | null>(null);

  if (!phone) {
    return (
      <PhoneStep
        title="Link your phone"
        subtitle="Verify your number to turn on dust alerts. We'll text you a code."
        onSubmit={setPhone}
      />
    );
  }

  return (
    <CodeStep
      phone={phone}
      onVerified={() => {
        linkPhone(phone);
        toast.success("Phone verified");
        router.push(redirectTo);
      }}
    />
  );
}

export default function LinkPhonePage() {
  return (
    <DustySky glow="right">
      <div className="flex flex-1 flex-col items-center justify-center px-5 py-10">
        <div className="w-full max-w-sm">
          <Suspense fallback={null}>
            <LinkPhoneForm />
          </Suspense>
        </div>
      </div>
    </DustySky>
  );
}
