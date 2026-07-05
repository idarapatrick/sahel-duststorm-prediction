import { Card } from "@/components/ui/card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function AboutPage() {
  return (
    <div className="flex flex-1 flex-col gap-6 px-5 pt-6 pb-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">About SahelDust</h1>
        <p className="text-sm text-muted-foreground">
          Forecasting dust events across the Sahel using a dual-encoder model
        </p>
      </div>

      <Card className="flex flex-col gap-2 border-border/60 bg-white/80 p-4">
        <p className="text-sm font-medium">How it works</p>
        <p className="text-sm text-muted-foreground">
          A dual-encoder neural network combines a 72-hour window of atmospheric
          variables (wind, temperature, pressure, boundary layer height, precipitation,
          dewpoint) with surface conditions (soil moisture, vegetation water content,
          recent aerosol optical depth) to estimate the probability of a dust event.
        </p>
      </Card>

      <Card className="flex flex-col gap-2 border-border/60 bg-white/80 p-4">
        <p className="text-sm font-medium">Data sources</p>
        <ul className="list-disc pl-4 text-sm text-muted-foreground">
          <li>Open-Meteo &mdash; real-time atmospheric forecast data</li>
          <li>NASA SMAP (via Google Earth Engine) &mdash; soil moisture</li>
          <li>MODIS (via Google Earth Engine) &mdash; aerosol optical depth</li>
          <li>OpenStreetMap Nominatim &mdash; location names</li>
        </ul>
      </Card>

      <Card className="flex flex-col gap-2 border-border/60 bg-white/80 p-4">
        <p className="text-sm font-medium">Progressive predictions</p>
        <p className="text-sm text-muted-foreground">
          Predictions for a future date are re-checked over time. As the target date
          approaches, more of the atmospheric window shifts from forecast data to real
          observations, so confidence increases the closer you get to the event.
        </p>
      </Card>

      <Card className="flex flex-col gap-2 border-border/60 bg-white/80 p-4">
        <p className="text-sm font-medium">API</p>
        <p className="text-sm text-muted-foreground">
          The backend is a FastAPI service.{" "}
          <a
            href={`${API_BASE_URL}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline"
          >
            View the interactive API docs
          </a>
          .
        </p>
      </Card>
    </div>
  );
}
