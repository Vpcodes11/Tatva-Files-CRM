# Tatva CRM · Files module

A small web app for the Tatva team: site visits, clients, plots, holds, bookings, payments, site expenses, contractors, incentives and an edit history, with sign-in and roles.

- **Website (frontend):** `public/index.html`
- **Server (backend):** `src/worker.js`, a Cloudflare Worker
- **Database:** Cloudflare D1 (SQLite). Tables are in `schema.sql`.
- **Your sheet data:** `data/seed.sql`, built from your Excel sheets. It holds client names and phone numbers, so **never upload the `data` folder to a public place** such as a public GitHub repository.

Hosting runs on Cloudflare's free plan (Workers + D1). That allows 100,000 requests and 5 million database row reads a day, which is plenty for a team of 2–10.

## Roles

| | Agent | Admin | Super admin |
|---|---|---|---|
| See and edit everything in Files | ✓ | ✓ | ✓ |
| Change a **Converted** visit or booking | – | ✓ | ✓ |
| Add, edit or switch off users | – | ✓ (not Super admins) | ✓ |
| Make someone Super admin | – | – | ✓ |

The server checks these rules on every change, not only the screen.

## Put it online (one time, about 15 minutes)

You need a free Cloudflare account (cloudflare.com) and Node.js 22 or newer on your computer.

```bash
# 1. In this folder
npm install

# 2. Sign in to Cloudflare (opens the browser)
npx wrangler login

# 3. Create the database. Copy the "database_id" it prints into wrangler.toml
npx wrangler d1 create tatva-crm

# 4. Create the tables and load your sheet data
npm run db:remote

# 5. Put the app online. It prints your web address, e.g. https://tatva-crm.<your-name>.workers.dev
npm run deploy
```

Open the web address. The first screen asks you to **create the first Super admin**. After that, go to **Admin → Users** to add the team.

Run step 4 **only once**. Running it again would replace the data with the sheet data.

## Try it on your own computer first (optional)

```bash
npm install
npm run db:local     # creates a local test database with your sheet data
npm run dev          # open http://localhost:8787
```

## Updating the app later

Change the files, then run `npm run deploy` again. Your data stays in the database. Deploying never touches it.

## Backups

Cloudflare D1 keeps 30 days of history automatically ("Time Travel"). To also download a copy:

```bash
npx wrangler d1 export tatva-crm --remote --output backup.sql
```

## Not included yet

- **Uploading documents** (PDFs, photos). This needs Cloudflare R2 storage, which is free up to 10 GB but asks for a payment card on the Cloudflare account.
- The leads / inquiries part of the old CRM.
