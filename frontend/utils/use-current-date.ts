import { useSyncExternalStore } from "react";

const subscribe = () => () => undefined;

function getCurrentDateKey(): string {
  const date = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}`;
}

export function useCurrentDateKey(): string {
  return useSyncExternalStore(subscribe, getCurrentDateKey, () => "");
}

export function dateFromKey(key: string): Date {
  return key ? new Date(`${key}:00:00`) : new Date(2000, 0, 1);
}