import { MobileNav } from "@/components/layout/MobileNav";
import { LocationProvider } from "@/components/providers/LocationProvider";
import { PredictionProvider } from "@/components/providers/PredictionProvider";
import { OnboardingGate } from "@/components/providers/OnboardingGate";

export default function MobileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <LocationProvider>
      <PredictionProvider>
        <OnboardingGate />
        <div className="flex flex-1 flex-col">
          <main className="flex flex-1 flex-col pb-24">{children}</main>
          <MobileNav />
        </div>
      </PredictionProvider>
    </LocationProvider>
  );
}
