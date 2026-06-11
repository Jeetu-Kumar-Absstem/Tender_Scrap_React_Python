/**
 * server/routes/hospital.ts
 * ──────────────────────────
 * Endpoints:
 *   POST /api/hospitals/scrape   → triggers nabh_scraper.py (Haryana only)
 *   GET  /api/hospitals/cities   → proxies NABH API for city dropdown
 *   GET  /api/hospitals          → returns data from Supabase (with filters)
 */

import { Router, Request, Response } from "express";
import { spawn }                     from "child_process";
import path                          from "path";
import fs                            from "fs";
import { fileURLToPath }             from "url";
import { createClient }              from "@supabase/supabase-js";

const router    = Router();
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ── NABH state order (mirrors HospitalPage.tsx) ───────────────
const NABH_STATES = [
  'Ahmedabad','Andhra Pradesh','Arunachal Pradesh','Assam',
  'Bagmati Zone','Bangalore','Bihar','Biratnagar','Chandigarh',
  'Chattisgarh','Chhattisgarh','Chitwan','Delhi','Gandaki Zone',
  'Goa','Gujarat','Gwarko','Haryana','Himachal Pradesh','Hyderabad',
  'Jammu and Kashmir','Jharkhand','Kanchanbari','Karnataka','Kathmandu',
  'Kerala','Kolkata','Koshi Zone','Lumbini','Lumbini Zone',
  'Madhya Pradesh','Maharashtra','Manipur','Mechi Zone','Meghalaya',
  'Mizoram','Morang','Nagaland','Narayani Zone','Nepalgunj',
  'New Delhi','Odisha','Orissa','Pokhara','Pondicherry','Puducherry',
  'Punjab','Rajasthan','Rani Gaon','Sikkim','Srinagar','Tamil Nadu',
  'Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal',
]

function getStateRank(address: string | null): number {
  if (!address) return 999
  const addr = address.toLowerCase()
  const idx = NABH_STATES.findIndex(s => addr.includes(s.toLowerCase()))
  return idx === -1 ? 999 : idx
}
const ROOT_DIR  = path.resolve(__dirname, "../..");

// ── Resolve venv Python (mirrors index.ts logic) ──────────────
function resolvePython(): string {
  const isWindows = process.platform === "win32";
  const candidates = isWindows
    ? [
        path.join(ROOT_DIR, "venv", "Scripts", "python.exe"),
        path.join(ROOT_DIR, ".venv", "Scripts", "python.exe"),
        "python",
      ]
    : [
        path.join(ROOT_DIR, "venv", "bin", "python"),
        path.join(ROOT_DIR, ".venv", "bin", "python"),
        "/opt/render/project/src/venv/bin/python",
        "python3",
        "python",
      ];

  for (const c of candidates) {
    if (c.startsWith("/") || c.includes("\\")) {
      if (fs.existsSync(c)) return c;
    } else {
      return c;
    }
  }
  return "python";
}

const PYTHON_EXE = resolvePython();

// ── Supabase (service_role key) ───────────────────────────────
const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!,
);

// ── POST /api/hospitals/scrape ────────────────────────────────
// Hardcoded to Haryana. Runs synchronously and returns count.
router.post("/scrape", async (req: Request, res: Response) => {
  const targetState = "Haryana";

  console.log(`[hospitals] Starting scraper — python: ${PYTHON_EXE}`);

  const child = spawn(
    PYTHON_EXE,
    ["-m", "scraper.nabh_scraper"],
    {
      cwd:   ROOT_DIR,
      env:   { ...process.env },
      stdio: "pipe",
    }
  );

  let stderrBuf = "";
  child.stdout?.on("data", (d: Buffer) => process.stdout.write(`[nabh] ${d}`));
  child.stderr?.on("data", (d: Buffer) => { stderrBuf += d.toString(); });

  const exitCode = await new Promise<number>((resolve) => {
    child.on("close", resolve);
    child.on("error", (err: Error) => {
      console.error("[hospitals] spawn error:", err.message);
      resolve(-1);
    });
  });

  if (exitCode !== 0) {
    console.error("[hospitals] Scraper stderr:", stderrBuf);
    return res.status(500).json({ error: "Scraper failed", detail: stderrBuf.slice(0, 500) });
  }

  const { count } = await supabase
    .from("nabh_hospitals")
    .select("*", { count: "exact", head: true })
    .ilike("address", `%${targetState}%`);

  return res.json({
    ok:      true,
    state:   targetState,
    inserted: count,
    message: `Done — ${count ?? "?"} Haryana hospitals upserted`,
  });
});

// ── GET /api/hospitals/cities ─────────────────────────────────
// Proxies NABH AJAX endpoint to avoid CORS issues in browser.
// Returns plain string[]  e.g. ["Ambala","Faridabad","Gurugram",...]
router.get("/cities", async (req: Request, res: Response) => {
  const state = (req.query.state as string | undefined)?.trim();
  if (!state) return res.status(400).json({ error: "state query param is required" });

  try {
    const nabh_url =
      `https://nabh.co/wp-admin/admin-ajax.php` +
      `?action=get_cities_by_state&state=${encodeURIComponent(state)}`;

    const upstream = await fetch(nabh_url, {
      method:  "POST",
      headers: {
        "User-Agent":       "Mozilla/5.0",
        "Referer":          "https://nabh.co/find-a-healthcare-organisation/",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin":           "https://nabh.co",
      },
    });

    if (!upstream.ok) throw new Error(`NABH API returned ${upstream.status}`);

    const cities: string[] = await upstream.json();

    res.setHeader("Cache-Control", "public, s-maxage=3600, stale-while-revalidate=600");
    return res.json(cities);

  } catch (err) {
    console.error("[/api/hospitals/cities]", err);
    return res.status(502).json({ error: "Failed to fetch cities from NABH" });
  }
});

// ── GET /api/hospitals ────────────────────────────────────────
// Optional server-side proxy — frontend queries Supabase directly.
router.get("/", async (req: Request, res: Response) => {
  const state     = (req.query.state    as string | undefined) || "";
  const city      = (req.query.city     as string | undefined) || "";
  const q         = (req.query.q        as string | undefined) || "";
  const sortState = req.query.sortState === "true";
  const page      = Math.max(1, parseInt((req.query.page  as string) || "1",  10));
  const limit     = Math.min(200, parseInt((req.query.limit as string) || "50", 10));
  const offset    = (page - 1) * limit;

  let query = supabase
    .from("nabh_hospitals")
    .select("id,name,address,phone,email,website,accreditation_no,scraped_at", { count: "exact" });

  if (state) query = query.ilike("address", `%${state}%`);
  if (city)  query = query.ilike("address", `%${city}%`);
  if (q)     query = query.ilike("name",    `%${q}%`);

  // When sortState is off, use DB-level name sort + pagination as before.
  // When sortState is on, fetch all matching rows so we can sort by NABH_STATES order.
  if (sortState) {
    query = query.order("name")  // secondary sort by name
  } else {
    query = query.order("name").range(offset, offset + limit - 1);
  }

  const { data, error, count } = await query;
  if (error) return res.status(500).json({ error: error.message });

  let rows = (data ?? []) as Array<{ address: string | null; name: string; [key: string]: unknown }>

  if (sortState) {
    // Sort client-side by NABH_STATES index order, then by name within same state
    rows = rows.sort((a, b) => {
      const rankA = getStateRank(a.address)
      const rankB = getStateRank(b.address)
      if (rankA !== rankB) return rankA - rankB
      return a.name.localeCompare(b.name)
    })
    // Apply pagination after sort
    rows = rows.slice(offset, offset + limit)
  }

  return res.json({
    data:       rows,
    total:      count,
    page,
    limit,
    totalPages: Math.ceil((count ?? 0) / limit),
  });
});

export default router;