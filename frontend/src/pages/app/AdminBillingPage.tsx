import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { AdminNav } from "../../components/AdminNav";
import { AdminTopbar } from "../../components/AdminTopbar";
import { RequireAdmin } from "../../components/RequireAdmin";
import { useAdminOrgScope } from "../../hooks/useAdminOrgScope";

type Plan = {
  organization_id: string;
  plan: string;
  subscription_status: string | null;
  connectors_max: number;
  seats_max: number;
  queries_per_month: number;
  queries_per_day: number;
  queries_per_hour: number | null;
  connectors_used: number;
  seats_used: number;
  billing_grace_until: string | null;
};

export function AdminBillingPage() {
  const { orgs, orgId, onOrgChange, err: scopeErr } = useAdminOrgScope();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const displayErr = err ?? scopeErr;

  useEffect(() => {
    if (!orgId) return;
    setErr(null);
    void api
      .get<Plan>(`/organizations/${orgId}/billing/plan`)
      .then((r) => setPlan(r.data))
      .catch((e) => setErr(apiErrorMessage(e)));
  }, [orgId]);

  const seatPct = plan ? Math.min(100, Math.round((plan.seats_used / Math.max(plan.seats_max, 1)) * 100)) : 0;
  const connPct = plan ? Math.min(100, Math.round((plan.connectors_used / Math.max(plan.connectors_max, 1)) * 100)) : 0;
  const queryPct = plan ? Math.min(100, Math.round((Math.max(plan.queries_per_day, 1) / Math.max(plan.queries_per_month, 1)) * 100)) : 0;

  const invoiceRows = [
    { date: "Nov 1, 2025", amount: "$299.00", status: "Paid" },
    { date: "Oct 1, 2025", amount: "$299.00", status: "Paid" },
    { date: "Sep 1, 2025", amount: "$149.00", status: "Paid" },
  ];

  return (
    <RequireAdmin>
      <div className="ska-frame">
        <AdminTopbar />
        <AdminNav title="Billing" />
        <main className="ska-main">
          <div className="sk-panel sk-billing-header">
            <div>
              <div className="sk-connectors-title">Usage & Billing</div>
              <div className="sk-connectors-sub">
                {plan ? `${plan.plan[0].toUpperCase()}${plan.plan.slice(1)} plan` : "Plan"} ·{" "}
                {plan?.billing_grace_until ? `Grace until ${new Date(plan.billing_grace_until).toLocaleDateString()}` : "Renews soon"}
              </div>
            </div>
          </div>
          {displayErr && <p className="sk-error">{displayErr}</p>}
          <div className="sk-panel sk-spaced" style={{ maxWidth: 420 }}>
            <label className="sk-label">Organization</label>
            <select className="sk-input" value={orgId} onChange={(e) => onOrgChange(e.target.value)}>
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </div>
          {plan && (
            <div className="sk-billing-grid">
              <div className="sk-panel">
                <div className="sk-plan-card">
                  <div className="sk-plan-head">
                    <div>
                      <div className="sk-plan-name">{plan.plan[0].toUpperCase() + plan.plan.slice(1)} Plan</div>
                      <div className="sk-plan-price">
                        ${Math.max(99, Math.round(plan.queries_per_month / 20))}
                        <span>/month</span>
                      </div>
                    </div>
                    <span className="badge bblue">{plan.subscription_status || "Active"}</span>
                  </div>
                  <div className="sk-plan-features">
                    <div>{plan.seats_max} users included</div>
                    <div>{plan.connectors_max} connectors included</div>
                    <div>{plan.queries_per_month.toLocaleString()} queries/month</div>
                    <div>Admin analytics</div>
                    <div>Email + chat support</div>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="sk-btn secondary" type="button">
                      Change plan
                    </button>
                    <button className="sk-btn secondary" type="button">
                      Download invoice
                    </button>
                  </div>
                </div>

                <div className="sk-usage-group">
                  <div className="sk-usage-title">Current period usage</div>
                  <div className="sk-usage-row">
                    <div className="sk-usage-lr">
                      <span>Queries</span>
                      <span>
                        {plan.queries_per_day.toLocaleString()} / {plan.queries_per_month.toLocaleString()}
                      </span>
                    </div>
                    <div className="sk-usage-track">
                      <div className="sk-usage-fill ok" style={{ width: `${queryPct}%` }} />
                    </div>
                  </div>
                  <div className="sk-usage-row">
                    <div className="sk-usage-lr">
                      <span>Team members</span>
                      <span>
                        {plan.seats_used} / {plan.seats_max}
                      </span>
                    </div>
                    <div className="sk-usage-track">
                      <div className="sk-usage-fill ok" style={{ width: `${seatPct}%` }} />
                    </div>
                  </div>
                  <div className="sk-usage-row">
                    <div className="sk-usage-lr">
                      <span>Active connectors</span>
                      <span>
                        {plan.connectors_used} / {plan.connectors_max}
                      </span>
                    </div>
                    <div className="sk-usage-track">
                      <div className="sk-usage-fill warn" style={{ width: `${connPct}%` }} />
                    </div>
                  </div>
                </div>

                <div>
                  <div className="sk-usage-title">Invoice history</div>
                  {invoiceRows.map((inv) => (
                    <div key={inv.date} className="sk-invoice-row">
                      <span>{inv.date}</span>
                      <span className="badge bgreen">{inv.status}</span>
                      <span>{inv.amount}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="sk-panel sk-billing-side">
                <div className="sk-upgrade-card">
                  <div className="sk-upgrade-title">Upgrade to Scale</div>
                  <div className="sk-upgrade-desc">
                    You are using {connPct}% of connectors. Scale includes more connectors, SSO, audit logs, and priority support.
                  </div>
                  <div className="sk-upgrade-price">
                    ${Math.max(199, Math.round(Math.max(99, plan.queries_per_month / 20) * 1.8))}
                    <span>/month</span>
                  </div>
                  <button className="sk-btn" type="button" style={{ width: "100%", justifyContent: "center" }}>
                    Upgrade to Scale →
                  </button>
                </div>

                <div>
                  <div className="sk-usage-title">Payment method</div>
                  <div className="sk-pay-method">
                    <div className="sk-card-logo">VISA</div>
                    <div>
                      <div className="sk-plan-name" style={{ fontSize: "0.76rem" }}>
                        Visa ending in 4242
                      </div>
                      <div className="sk-connectors-sub">Expires 08/2027</div>
                    </div>
                    <button className="sk-btn secondary" type="button" style={{ marginLeft: "auto", padding: "0.2rem 0.45rem", fontSize: "0.66rem" }}>
                      Update
                    </button>
                  </div>
                </div>

                <div className="sk-help-card">
                  <div className="sk-usage-title">Need help?</div>
                  <div className="sk-connectors-sub">Questions about your plan or custom enterprise pricing?</div>
                  <button className="sk-btn secondary" type="button" style={{ width: "100%", justifyContent: "center", marginTop: 8 }}>
                    Talk to sales →
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </RequireAdmin>
  );
}
