# Coverage Report & Collections Automation Center — Architecture

The page in this directory (`index.html`) is a fully working, client-side implementation of
the Automation Center: import, classification, the outreach engine, follow-up sequencing,
AI reply classification, escalation tasks, dashboards, compliance scoring and audit logging
all run in the browser with localStorage persistence. It doubles as the operator UI and as a
living spec for the production build described below.

## Production event-driven architecture

```
                       ┌─────────────────────────────────────────────┐
  CSV/XLSX upload ──►  │                 Ingestion API               │
  Emailed sheets  ──►  │  (inbound-parse webhook for reports@ and    │──► events
  PMS auto-reports ─►  │   collections@tenantpropertyprotection.com) │
                       └─────────────────────────────────────────────┘
                                          │
                                    Event bus (topics)
        account.imported · account.classified · outreach.due · email.sent
        email.received · reply.classified · payment.reported · account.escalated
                                          │
     ┌───────────────┬────────────────────┼───────────────────┬───────────────┐
     ▼               ▼                    ▼                   ▼               ▼
 Classifier     Sequencer            AI services         Task service     Analytics
 (rules from    (Day 0/3/7/14/21     (reply intent,      (CSM/Collections  (dashboard
  Settings)      timers, pause on     attachment→record   escalations,     metrics,
                 reply/resolution)    matching, insights) disputes)        compliance
                                                                            scores)
```

### Components

| Component | Responsibility | Notes |
|---|---|---|
| **Ingestion API** | Accepts CSV/XLSX uploads; receives inbound email via an email-provider webhook (SendGrid Inbound Parse / SES + S3 / Postmark). Normalizes rows using the tolerant header mapping in `index.html`. | Emits `account.imported`, `email.received`. |
| **Classifier** | Applies configurable rules: missing report (no report this month, or last report age > threshold), past due (balance > 0), both → Priority Follow-Up Queue. | Pure function of the record + settings; re-runs whenever settings change. |
| **Sequencer** | Durable timers per open workflow: initial → Day 3 → Day 7 → Day 14 → Day 21 escalate. Pauses on any classified reply; resumes on ticket close; pushes 3 days on out-of-office. | A scheduled job (or step-function/temporal workflow) replaces the demo's "+1 day" button. |
| **Outreach service** | Renders templates (`{{CustomerName}}`, `{{AmountDue}}`, …), sends via transactional email, records message IDs for reply threading. | DKIM/SPF on both mailboxes; per-account rate limiting. |
| **AI reply service** | Classifies replies into the seven intents (Coverage Report Submitted, Need Assistance, Payment Sent, Dispute Balance, Wrong Contact, Out of Office, General Question) using an LLM with the keyword ruleset as fallback; extracts attachments and matches them to accounts by sender, account name, and property. | The demo's regex classifier defines the label set and the state transitions per intent. |
| **Task service** | Creates internal tasks (Customer Success Manager, Collections Team, Accounting, Operations) on Day-21 escalation, disputes, wrong contacts and assistance requests. | Slack/email notification per team. |
| **Analytics** | Materializes the four dashboard metric groups and the Customer Compliance Score (reports 40 / payments 30 / responsiveness 20 / interventions 10). | Score weights match `scoreOf()` in `index.html`. |
| **Audit log** | Append-only record of every classification, send, reply, status change, permission denial and settings edit. | Demo keeps 800 entries in localStorage; production writes to an append-only store. |

### Role-based permissions

Mirrors the `PERMS` map in `index.html`:

- **Admin** — everything, including settings and workspace resets.
- **Customer Success** — import, coverage outreach, resolve reports, tasks.
- **Accounting** — import, collections outreach, payment verification, tasks.
- **Operations** — tasks and PMS onboarding only.
- **Viewer** — read-only; every blocked attempt is audit-logged.

### Configurable automation rules

All live in Settings and re-classify on save: reporting threshold (days), overdue
multiplier, follow-up cadence (Day 3/7/14/21 defaults), and the three email templates.

### What the static demo simulates

- **Sending** — the demo drafts every message and marks it sent (or hands it to your mail
  client); production wires the same queue to a transactional email provider.
- **Mailbox monitoring** — the demo's Inbox panel simulates the inbound-parse webhook: the
  same matching, classification, status updates and workflow closure run on real messages
  in production.
- **The clock** — the "+1 day" control stands in for the nightly automation sweep.
