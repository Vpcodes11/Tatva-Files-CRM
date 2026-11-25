# Tatva CRM · Files module — notes for Claude

## What this is
An in-house web app for **Tatva by Tradeprop** (real estate: plots and weekend villas at Nal Village / Nalsarovar, near Ahmedabad; one project, "TATVA Villas & Plots", 415 plots). It replaces the company's Excel sheets for site visits, client holds/bookings/payments, plots, sold plots, the land partner (Anjanee Infraspace), contractors, site expenses and agent incentives. The owner is Vaibhav Pamnani (GitHub `Vpcodes11`). Reply to him in **English**, plainly; he is not a developer.

Live: https://tatva-crm.vaistack-cs.workers.dev — every push to `main` deploys automatically (Cloudflare Workers Builds, worker name `tatva-crm`, Cloudflare account vaistack.cs@gmail.com). There is no other deploy step.

## Stack (free Cloudflare plan)
- `public/index.html` — the whole website: one file, plain JS, no framework, no build. Hash routes (`#/visits`, `#/client/<id>`, …).
- `src/worker.js` — the server (Cloudflare Worker): JSON API under `/api/*`, sign-in, roles, and all writes.
- Cloudflare **D1** database `tatva-crm` (id in `wrangler.toml`). Tables are created automatically by `ensureSchema()` in the worker; `schema.sql` mirrors them.
- `data/` (not in git — client phone numbers): `seed.sql` / `tatva-data.json` = the original Excel data, only for local testing and the one-time import. The live data is in D1; **pushing code never touches it**.

## Data model
- Table `records(coll, id, sr, data JSON)` holds every business record. Collections: `visits, clients, bookings, payments, plots, expenses, landowners` (Dastavej register = "Sold plots" register), `advances, incentives, registry, dastavej, ledger` (contractor ledger lines), `contractors`, `plotOwners` (plot → client id), `meta` (summary).
- `edits` = every pencil change (old/new, who, when; used for Undo). `steps` = holds, bookings, payments, lapses, new visits/expenses, deletes. `trash` = deleted records (Super admin), restorable. `users`, `sessions`, `meta` (`version` counter for the "someone else made changes" notice; one-time migration flags).
- The browser loads everything with `GET /api/data` and writes with `POST /api/ops` (ops: `patch` a field, `put` a whole record, `del` to trash, `step` log). Multi-record actions (hold, book, pay, lapse, delete) change records in the browser, then send the changed records (`snap()` / `diffOps()` in index.html).

## Business rules (agreed with the owner — keep them)
- Roles: **Agent** (everything in Files except changing a Converted visit/booking), **Admin** (+ users, export), **Super admin** (+ delete/restore, other Super admins). The server enforces these, not only the screen.
- Flow: site visit → Hold (₹1,100 default, creates the client folder, plot = Hold) → Book (final amount, down payment; plot = Sold, visit = Converted, doc status "MOU not done") → payments → or Hold lapsed (plot back to Unsold, refund yes/no).
- **One source of truth**: a plot's status and owner come from its booking (Converted → Sold & owned; active hold → Hold). A visit linked to a client folder takes the folder's status (Booked → Converted, On hold → Hold, Lapsed → Lapsed); the one exception is a lapsed client's visit put back on Follow up (`reopened` on the visit; a new hold clears it). Lists, menu counts and modules must always agree — the owner checks this closely.
- Visit statuses: Follow up 1–4, Hold, Converted, Lapsed ("Not interested" was renamed Lapsed; old `NOT INTERESTED` values show as Lapsed). One Remark per visit (old follow-up notes were folded into it, "FU1 dd/mm/yy: …"). Visits can have several agents ("A, B").
- Clients list: newest first; Booked / On hold / Lapsed buttons. Site visits has two tabs: **Follow up** (every visit that isn't Lapsed; = the menu count) and **Lapsed** (visits marked Lapsed + visits of lapsed clients). Setting a visit to Lapsed moves it to the Lapsed tab; setting it to a Follow up moves it back.
- Plots: TRPL plots and "Before TRPL" plots have separate Sr. series. Pratik is not shown in Incentives.
- Export (Excel/CSV, per list and "Export all") is Admin/Super admin only — files contain client phone numbers.
- Don't add file uploads yet (needs R2 + payment card). Don't add Meta/99acres/newsletters.

## How to work
1. Make the change locally.
2. Test: `npm install`, then `npm run db:local` (fresh local D1 from `data/seed.sql`) and `npm run dev` (http://localhost:8787), then `npm run test` (Playwright browser tests in `tests/`, all must pass; `__dbg` is a localhost-only hook the tests use). Add tests for new behaviour.
3. **Push straight to `main` yourself** as soon as all tests pass — don't wait for approval and don't use branches or pull requests (the owner wants every change on GitHub and live right away). Use clear commit messages; one commit per change.
4. About 1 minute after pushing, check the live site, then tell the owner in plain English what changed and where to see it.
Data fixes on live data go in the worker as a one-time migration guarded by a `meta` flag (see `migrateVisitRemarks`), never by editing data by hand.
