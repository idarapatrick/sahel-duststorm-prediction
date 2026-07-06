/**
 * Wraps a screen's content with the layered "dusty sky" backdrop, per the
 * glassmorphism spec. This applies the background directly to the wrapping
 * element (children render as normal descendants) rather than as a separate
 * fixed sibling -- simpler, and avoids relying on `background-attachment:
 * fixed`, which mobile Safari doesn't support reliably.
 */
export function DustySky({
  glow = "right",
  scanlines = false,
  children,
}: {
  glow?: "left" | "right";
  scanlines?: boolean;
  children: React.ReactNode;
}) {
  const glowPos = glow === "right" ? "74% 11%" : "26% 11%";
  const glowAlpha = glow === "right" ? 0.14 : 0.12;

  const layers = [
    scanlines
      ? "repeating-linear-gradient(179deg, rgba(230,222,205,.03) 0 3px, rgba(0,0,0,0) 3px 26px)"
      : null,
    "linear-gradient(180deg,rgba(0,0,0,0) 62%, rgba(10,8,6,.28) 100%)",
    `radial-gradient(58% 32% at ${glowPos}, rgba(255,235,195,${glowAlpha}) 0%, rgba(255,230,190,0) 62%)`,
    "url(/backgrounds/dusty-dusk.jpg)",
  ].filter(Boolean);

  return (
    <div
      className="relative flex flex-1 flex-col"
      style={{
        backgroundImage: layers.join(", "),
        backgroundSize: layers.map(() => "cover").join(", "),
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
      }}
    >
      {children}
    </div>
  );
}
