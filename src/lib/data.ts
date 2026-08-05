import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

/** A single language ranking entry */
export interface LanguageRank {
  rank: number;
  name: string;
  count: number;
}

/** The full daily data file shape */
export interface DailyData {
  date: string;
  generated_at: string;
  total_repos: number;
  languages: LanguageRank[];
}

/** Result shape when data is available */
export interface PageData {
  data: DailyData;
  /** The latest data file date, e.g. "2026-08-05" */
  dateStr: string;
  /** Human-friendly "last updated" string */
  updatedAt: string;
}

/** Regex to match YYYY-MM-DD.json data files */
const DATA_FILE_RE = /^\d{4}-\d{2}-\d{2}\.json$/;

const DATA_DIR = join(process.cwd(), "data");

/**
 * Load the latest daily data file from data/.
 * Returns `null` when no data file exists yet.
 */
export async function loadLatestData(): Promise<PageData | null> {
  let files: string[];
  try {
    files = (await readdir(DATA_DIR)).filter((f) => DATA_FILE_RE.test(f));
  } catch {
    return null;
  }

  if (files.length === 0) return null;

  // Sort descending: newest date first
  files.sort().reverse();
  const latest = files[0];

  const raw = await readFile(join(DATA_DIR, latest), "utf-8");
  const data: DailyData = JSON.parse(raw);

  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  const d = new Date(data.date + "T12:00:00");
  const updatedAt = `${days[d.getUTCDay()]}, ${months[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;

  return { data, dateStr: latest.replace(/\.json$/, ""), updatedAt };
}
