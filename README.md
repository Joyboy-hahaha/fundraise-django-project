# FundRaise — Django Crowdfunding/Donation Platform

A crowdfunding web app built with Django, with real payment integration via
**eSewa** (Nepal's payment gateway, in sandbox/test mode) and an
**admin-approval workflow** for new campaigns.

## Features included
- Sign up / Login / Logout (Django's built-in auth system)
- **Campaign approval workflow**: when a user creates a campaign, it goes
  into **Pending Review** status. It is only visible to its creator (and
  admins) until an admin approves it from the Django Admin panel. Once
  approved, it appears publicly on the home page and can accept donations.
  If an admin rejects it, the creator sees the rejection (and reason, if
  given) on their dashboard and can edit + resubmit.
- **Real payment integration with eSewa** (ePay v2, sandbox/test mode —
  no real money moves, but the actual payment flow, signature verification,
  and status-check API calls are all real).
- Home page — search + category filter + pagination (approved campaigns only)
- Campaign detail page — progress bar, donor list, donate button
- User dashboard — "My Campaigns" (with status badges) and "My Donations"
- Django Admin panel — approve/reject campaigns with one click (bulk actions),
  manage users and donations
- Bootstrap 5 styling

## How the approval workflow works
1. A logged-in user clicks "Start a Campaign" and fills the form.
2. The campaign is saved with `status = pending` and is **not** shown on the
   home page. Only the creator (or an admin) can open its detail page.
3. An admin logs into `/admin/`, opens **Campaigns**, and either:
   - Selects one or more pending campaigns and uses the **"Approve selected
     campaigns"** action, or
   - Opens a single campaign and changes its **Status** field to Approved
     (optionally filling in a Rejection reason if rejecting instead).
4. Once approved, the campaign appears on the home page and can accept
   donations. If edited again afterwards, it automatically goes back to
   Pending Review (so a creator can't sneak in changes after approval).
5. The creator can see their campaign's current status (Pending / Approved /
   Rejected) any time on their Dashboard.

## How the eSewa payment integration works
This uses eSewa's official **ePay v2** flow with their publicly published
**UAT/sandbox test credentials** (safe to use for a college project demo —
no real merchant account or real money is involved):

1. User clicks "Donate with eSewa" on an approved campaign → a `Donation`
   record is created with `payment_status = pending` and a unique
   `transaction_uuid`.
2. The app builds a signed payment request (HMAC-SHA256, using eSewa's test
   secret key) and renders a page that **auto-submits a form directly to
   eSewa's payment page** — this is genuinely how eSewa's integration works
   (a real browser form submission, not a background API call).
3. The user logs into eSewa using the **test credentials below** and
   confirms the payment.
4. eSewa redirects back to our `success_url` with a base64-encoded result.
5. Our code **decodes it, verifies the signature, and independently calls
   eSewa's own status-check API** to confirm the payment really went
   through (never trusting the redirect alone — this is the standard
   "defence in depth" approach and a good point to mention in your viva).
6. Only after that double-check passes do we mark the donation `completed`
   and add the amount to the campaign's raised total.

### eSewa test/sandbox login credentials (for your demo)
When redirected to eSewa during testing, log in with:
```
eSewa ID:  9806800001   (or 9806800002 / 9806800003 / 9806800004 / 9806800005)
Password:  Nepal@123
MPIN:      1122
```
No real money is involved — this is eSewa's officially published UAT
(sandbox) test account.

**Note:** these are eSewa's shared, publicly documented test credentials —
fine to keep in code for a demo project. If you ever apply for a real eSewa
merchant account, replace `ESEWA_SECRET_KEY` and `ESEWA_PRODUCT_CODE` in
`fundraiser/settings.py` with your real ones, and move them to environment
variables instead of hardcoding them.

## Project structure
```
fundraiser/            -> Django project settings & main urls
campaigns/              -> The main app (models, views, forms, admin, urls)
  esewa_utils.py         -> Signature generation/verification, status-check helpers
templates/              -> All HTML templates (base.html, campaigns/, registration/)
static/css/style.css    -> Custom styling on top of Bootstrap
media/                  -> Uploaded campaign images (created at runtime)
requirements.txt        -> Python dependencies
manage.py               -> Django's command-line utility
db.sqlite3              -> SQLite database (already migrated, empty — ready to use)
```

## How to run this project

### 1. Prerequisites
- Python 3.10+ installed on your machine

### 2. Extract the zip and open a terminal in the project folder
The folder containing `manage.py` is the one you work in.

### 3. Create a virtual environment
**Windows:**
```
python -m venv venv
venv\Scripts\activate
```
**Mac/Linux:**
```
python3 -m venv venv
source venv/bin/activate
```
You'll know it worked when your prompt shows `(venv)`.

### 4. Install dependencies
```
pip install -r requirements.txt
```

### 5. Apply database migrations
```
python manage.py migrate
```

### 6. Create an admin (superuser) account
This is the account you'll use to approve/reject campaigns.
```
python manage.py createsuperuser
```

### 7. Run the development server
```
python manage.py runserver
```

### 8. Try the full flow
1. Go to `http://127.0.0.1:8000/`, click **Sign Up**, create a normal account.
2. Click **Start a Campaign** and submit one — notice it's *not* on the
   home page yet.
3. Open a **new/incognito browser tab**, go to
   `http://127.0.0.1:8000/admin/`, log in with your superuser account.
4. Click **Campaigns**, select your new campaign's checkbox, choose
   **"Approve selected campaigns"** from the action dropdown, click **Go**.
5. Back on the normal tab, refresh the home page — the campaign now appears.
6. Open the campaign and click **"Donate with eSewa"** — you'll be
   redirected to eSewa's real sandbox login page.
7. Log in with the test eSewa credentials above and confirm the payment.
8. You'll be redirected back, and the campaign's raised amount updates.

## Common issues

**"python: command not found"**
Try `python3` instead (common on Mac/Linux).

**"No module named django"**
Your virtual environment isn't activated — re-run the activate command from
Step 3 (look for `(venv)` in your prompt).

**Port 8000 already in use**
```
python manage.py runserver 8080
```
Then visit `http://127.0.0.1:8080/`.

**eSewa redirect doesn't come back to my site**
Make sure you're running the server with `python manage.py runserver`
(default port 8000, or whatever port you chose) and that you didn't close
the browser tab mid-payment. Since this is a browser-side redirect (not a
server-to-server webhook), `localhost` URLs work fine for eSewa's
success/failure redirect — no tunnelling tool needed for this part of the
flow.

**I want to reject a campaign with a reason**
In the Django Admin, open the individual campaign (don't use the bulk
action), set **Status** to "Rejected", type your reason in
**Rejection reason**, and save. The creator will see this reason on their
dashboard and campaign page.

## Ideas to extend this further (good for your report/viva)
- Add email notifications when a campaign is approved/rejected
- Add Khalti as a second payment option alongside eSewa
- Add a public "donation receipt" page/PDF after a successful payment
- Add campaign categories as a separate model instead of fixed choices
- Add comments/updates section on each campaign

Good luck with your project!
