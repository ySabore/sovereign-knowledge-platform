# Stripe billing for Sovereign Knowledge Platform

This platform uses **Stripe Checkout** (new subscriptions), **Stripe Customer Portal** (payment methods, invoices, cancel/switch where you allow it), and **webhooks** (keep the database in sync). List prices shown in the app are **marketing copy** unless you set `BILLING_PLAN_PRICE_LABELS_JSON`; **actual charges** always come from the **Price** objects you attach in Stripe.

---

## 1. Create a Stripe account and API keys

1. Open [Stripe Dashboard](https://dashboard.stripe.com/) (use **Test mode** until you are ready for production).
2. Go to **Developers → API keys**.
3. Copy the **Secret key** (`sk_test_…` or `sk_live_…`) into `STRIPE_SECRET_KEY` in `.env`.
4. The SPA detects billing when the secret key is present (`GET /config/public` → `features.stripe_billing`).

**Docker:** both `docker-compose.prod.yml` and `docker-compose.gpu.yml` pass Stripe variables from your runtime `.env` into the `api` container. `docker-compose` does not read `.env.example`; copy values into `.env`, then rebuild/restart `api` after changes.

---

## 2. Products and recurring Prices

Create **one Product per plan tier** you sell (or one product with multiple prices). Each tier must be a **recurring monthly Price** (or the interval you want).

Suggested mapping to internal plans:

| Internal plan | Typical use | Env var for Price ID |
|---------------|-------------|----------------------|
| `starter` | Small teams | `STRIPE_PRICE_STARTER` |
| `team` | Department | `STRIPE_PRICE_TEAM` |
| `business` | Company-wide | `STRIPE_PRICE_BUSINESS` |
| `scale` | High volume | `STRIPE_PRICE_SCALE` |

Steps in Dashboard:

1. **Product catalog → Add product**.
2. Set **Pricing** to **Recurring**, choose **Monthly** (or your billing period).
3. Save the product.
4. **Where to find the Price ID** (`price_…`):
   - Stay on the product’s detail page (or open **Product catalog** and click the product).
   - In the **Pricing** section, each row is one Price. Stripe shows an **API ID** (or **Price ID**) column — it always starts with `price_`. Use **Copy** next to that value if the UI offers it, or select and copy the text.
   - If you only see the amount/currency, expand the price row or open the price’s detail view; the ID is labeled **API ID** or appears in the URL when you edit the price (`.../prices/price_xxxx`).
5. Paste that value into the matching env var (e.g. `STRIPE_PRICE_STARTER`).

The API maps subscription line items back to internal plans using these env vars (`app/services/billing.py` → `price_id_to_plan`).

---

## 3. Checkout flow (upgrade / subscribe)

- Org **owners** use **Usage & Billing** (`/home?panel=billing` or `/billing`).
- **Choose plan** calls `POST /organizations/{org_id}/billing/checkout` with a `price_id` and redirects to Stripe Checkout.
- On success, Stripe sends **`checkout.session.completed`**; the webhook handler links the Stripe Customer and Subscription to the organization and updates `org.plan`.

Ensure the **org owner** has an email in the database (Checkout uses it for `customer_email` when there is no `stripe_customer_id` yet).

---

## 4. Customer Portal (“billing portal”)

The **hosted Customer Portal** is Stripe’s UI for:

- Payment methods  
- Invoices and receipts  
- Subscription cancel / update (depending on your Portal configuration)

**In Dashboard:**

1. Go to **Settings → Billing → Customer portal**.
2. Turn on the portal and choose what customers can do (cancel plan, switch plans, update payment method, etc.).
3. Optional: create a **Portal configuration** and copy its ID (`bpc_…`) to `STRIPE_BILLING_PORTAL_CONFIGURATION_ID`. The API passes this to `stripe.billing_portal.Session.create` so branding and allowed actions match your settings.

**In the app:**

- **Billing portal** / **Manage subscription in Stripe** calls `POST /organizations/{org_id}/billing/portal` with `return_url` set to the current page.
- Requires an existing `stripe_customer_id` (normally after the first successful Checkout).

---

## 5. Webhooks

Stripe's Dashboard wording varies by UI version:

- Legacy wording: **Developers → Webhooks → Add endpoint**
- Newer wording: **Create → Event destination → Webhook endpoint**
- Direct pages: [test webhooks](https://dashboard.stripe.com/test/webhooks) and [live webhooks](https://dashboard.stripe.com/webhooks)

Configure endpoint:

1. URL: `https://<your-api-host>/webhooks/stripe` (local dev: use Stripe CLI forwarding below).
2. Subscribe at minimum to events handled in `app/routers/webhooks_stripe.py`: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, and `invoice.payment_failed`.
3. Copy the **Signing secret** (`whsec_…`) into `STRIPE_WEBHOOK_SECRET`.

**Local testing with Stripe CLI:**

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

Use the printed webhook secret as `STRIPE_WEBHOOK_SECRET` for that session.

**End-to-end local verification**

```bash
stripe trigger checkout.session.completed
```

If forwarding is active, `stripe listen` should show `POST http://localhost:8000/webhooks/stripe` with `200` for delivered events.

---

## 6. Display pricing vs charged pricing

- **Charged amount:** Always the **Stripe Price** (amount, currency, tax, coupons).
- **UI labels:** Default copy in the API (`DEFAULT_PLAN_PRICE_DISPLAY` in `app/services/billing.py`) follows common **SMB / mid-market** positioning for bundled team SaaS and AI search–style products. Override any tier with `BILLING_PLAN_PRICE_LABELS_JSON` (JSON object, plan key → string).

---

## 7. Quick checklist

- [ ] `STRIPE_SECRET_KEY` set (`sk_test_…` or `sk_live_…`).
- [ ] Four recurring Prices created; IDs in `STRIPE_PRICE_*`.
- [ ] Webhook endpoint live; `STRIPE_WEBHOOK_SECRET` set.
- [ ] Customer portal enabled; optional `STRIPE_BILLING_PORTAL_CONFIGURATION_ID`.
- [ ] Optional: `CONTACT_SALES_EMAIL`, `BILLING_PLAN_PRICE_LABELS_JSON`.
- [ ] Restart API (and Docker `api` service) after env changes.

---

## 8. In-app entry points

- **Billing hub:** [http://localhost:8080/billing](http://localhost:8080/billing) (redirects to `?panel=billing` on Home) when authenticated.
- **API:** `GET /organizations/{id}/billing/plan`, `/billing/plans`, `/billing/invoices`; `POST /billing/checkout`, `/billing/portal`.

For environment variable names and defaults, see `app/config.py` and [configuration.md](../configuration.md).

---

## 9. Troubleshooting

- `features.stripe_billing` is `false` in `GET /config/public`: `STRIPE_SECRET_KEY` is missing/invalid in runtime `.env`, or `api` was not restarted.
- Stripe trigger succeeds but app does not update: ensure `stripe listen --forward-to localhost:8000/webhooks/stripe` is running in the same test account/mode as your keys.
- Webhook requests not visible in app logs: no listener forwarding or wrong endpoint URL.
- Signature errors (`Invalid signature`): `STRIPE_WEBHOOK_SECRET` does not match the currently running listener/endpoint secret.

---

## 10. Billing operations runbook

### A) Sandbox test checklist (no real card required)

1. Keep Stripe in **Test mode** and use `sk_test_...`.
2. Ensure prices are test-mode `price_...` values in `STRIPE_PRICE_*`.
3. Start webhook forwarding:
   - `stripe listen --forward-to localhost:8000/webhooks/stripe`
4. In app as org owner/admin:
   - Billing -> **Choose plan** (first-time subscription)
   - Use test card `4242 4242 4242 4242`
   - Open **Billing portal**
5. Verify:
   - `checkout.session.completed` delivered with `200`
   - org has `stripe_customer_id` and `stripe_subscription_id`
   - invoices appear in Billing screen / portal

### B) Expected org billing lifecycle

1. **First subscription:** Checkout creates customer + subscription.
2. **Plan changes after subscribe:** use **Billing portal** to switch plan.
3. **Webhooks sync app state:** subscription updates/deletes/payment failures update org billing fields and plan limits.

Implementation note: checkout is now guarded to prevent creating a second active subscription for an org that already has one.

### C) Duplicate subscription cleanup (if legacy duplicates exist)

If a customer already has multiple active subscriptions from earlier test flows:

1. Identify all subscriptions for the customer in Stripe.
2. Keep only the intended active plan subscription.
3. Cancel older duplicate subscriptions.
4. Ensure app DB points to the kept subscription:
   - `organizations.stripe_subscription_id` = kept subscription id
   - `organizations.plan` matches the kept plan tier
5. Refresh Billing and Customer Portal; only one active subscription should remain.
