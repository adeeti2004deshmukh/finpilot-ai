"use client";



import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import SimulatorView from "@/components/simulator/simulator-view";
import { LoadingSkeleton } from "@/components/ui/states";

const validModes = ["sip", "rd", "fd", "compound-growth"] as const;

export default function SimulatorPage() {
  return <Suspense fallback={<LoadingSkeleton rows={3} />}><SimulatorRoute /></Suspense>;
}

function SimulatorRoute() {
  const mode = useSearchParams().get("mode");
  const initialMode = validModes.find((item) => item === mode) ?? "sip";
  return <SimulatorView key={initialMode} initialMode={initialMode} />;
}