"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { hasOnboarded } from "@/lib/onboarding";

/** Sends first-time visitors (no saved location yet) to /onboarding before they see the dashboard. */
export function OnboardingGate() {
  const router = useRouter();

  useEffect(() => {
    if (!hasOnboarded()) {
      router.replace("/onboarding");
    }
    // Only ever needs to run once, on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
