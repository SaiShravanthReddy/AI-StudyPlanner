const appTimeZone = import.meta.env.VITE_APP_TIMEZONE || "America/New_York";

export function todayIsoDate(timeZone = appTimeZone) {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  });
  const parts = formatter.formatToParts(new Date());
  const values = Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function getAppTimeZone() {
  return appTimeZone;
}
