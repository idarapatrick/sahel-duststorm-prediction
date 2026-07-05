import { MobileNav } from "@/components/layout/MobileNav";

export default function MobileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col bg-background">
      <main className="flex flex-1 flex-col pb-20">{children}</main>
      <MobileNav />
    </div>
  );
}
