import { Wind, Loader2 } from "lucide-react";

export default function RootLoading() {
  return (
    <div
      className="flex min-h-dvh flex-1 flex-col items-center justify-center gap-4 px-8"
      style={{ background: "linear-gradient(165deg,#F6CD5B,#F0883E,#E5533B)" }}
    >
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <div className="flex size-32 items-center justify-center rounded-[32px] bg-[#FFF4DE]/95 shadow-[0_16px_40px_rgba(0,0,0,0.25)]">
          <Wind className="size-14 text-[#E5533B]" />
        </div>
        <div className="text-center">
          <p className="text-2xl font-extrabold text-[#20272e]">SahelDust</p>
          <p className="mt-1 text-sm font-semibold text-[#20272e]/80">
            Simple dust-storm warnings for the Sahel.
          </p>
        </div>
      </div>
      <Loader2 className="mb-10 size-6 animate-spin text-[#20272e]/70" />
    </div>
  );
}
