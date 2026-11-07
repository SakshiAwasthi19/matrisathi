# D06: WhatsApp provider for the pilot

**Status:** Proposed. **Decides:** manager (team lead + tech lead). **Written:** 2026-11-07 (W1-B5).
**Spec:** M007, D06, G09, T011. **Needed by:** Phase 2 (Week 3, restarted 23–27 Nov).

**All prices and rules were checked on 7 Nov 2026** from the sources linked in section 8. Anything marked **(unverified)** comes from a third-party blog or could not be confirmed on the provider's own page. Confirm those with the provider before signing. Prices exclude 18% GST unless stated.

---

## 1. The short answer

**Recommendation: Meta's WhatsApp Cloud API directly, with Gupshup as the fallback.**

- It is the **cheapest**: an estimated **₹600–700 a month** for the pilot (section 5), against about ₹1,200 (Gupshup) and ₹4,000–5,500 (AiSensy, Interakt).
- It is the **only option with documented webhook signing**, which the system needs to reject forged messages (W3-A1). For all three providers this could not be confirmed.
- We are building our own staff inbox anyway (W3-B1), so the providers' dashboards and inboxes would go unused.
- Data can be **stored in India** with Meta's Local Storage option.

**The manager needs to start business verification this week** (section 7). It takes days to about two weeks, and messaging cannot go live without it.

---

## 2. What the pilot needs

- Reminders and follow-ups to mothers, sent as **approved templates** (Meta's "utility" category). No marketing.
- Mothers' replies (**text, voice notes, photos**) arriving in a staffed inbox.
- **Signed webhooks**, so a forged message is rejected (G09, T011).
- Media downloaded straight into private storage (W3-A2).
- Real tests on **consenting staff phone numbers**; a mock does not pass the gate (Phase 2).
- Volume: about **200 messages a day** (pilot profile).

---

## 3. How Meta charges (applies to every option)

All providers pass on Meta's charges, so these rules apply to every option.

- **Per delivered message**, by category: marketing, utility, authentication (templates); service (free-form replies). Messages from mothers to the business are free. *(Meta pricing page.)*
- **Since 1 Oct 2026:**
  - **Utility messages are charged even inside the 24-hour window** after a mother writes. They were free from July 2025 to September 2026. *(Meta pricing page.)*
  - **Service messages:** 1,000 free per business phone number per month; beyond that they are charged. *(Meta pricing page.)*
  - **Exception:** service messages stay free beyond 1,000 for **eligible government and non-profit organizations**, including community non-profits in public health. Meta decides eligibility itself; there is no application process yet. *(Meta pricing page.)* If the account is owned by an eligible NGO, this lowers the cost.
  - A payment method must be on the account, or service messages may stop being delivered. *(Meta pricing page.)*
- **India rates per message** (Meta's INR rate card is linked from its pricing page but could not be read directly; these figures are consistent across several third-party sources):
  - Marketing: **₹0.8631** (unverified)
  - Utility: **₹0.115** (unverified)
  - Authentication: **₹0.115** (unverified)
  - Service beyond the free 1,000: charged at the utility rate (unverified)
- **Messaging limit:** a new account can message **250** different people a day outside the 24-hour window. **Business verification** is one way to raise it to **2,000**; higher limits follow automatically with good message quality. Limits are shared by all numbers on the account. *(Meta messaging-limits page.)* 250 is enough for the pilot's first days; verification removes the constraint.

---

## 4. Comparison

| | **Meta Cloud API (direct)** | **Gupshup** | **AiSensy** | **Interakt** (Jio Haptik) |
|---|---|---|---|---|
| **Onboarding** | Meta developer app, business portfolio, WhatsApp account, phone number, system-user token, webhook. Done by the developer. | Self-serve sign-up; prepaid wallet. | Self-serve sign-up; dashboard. | Self-serve sign-up; dashboard. |
| **Business verification** | Meta Business Verification, same for all options. Typically a few days to about two weeks (unverified; no Meta-published timeline found). GST/PAN/incorporation documents; names and addresses must match exactly. | Same; GST may be required by the provider (unverified). | Same (unverified). | Same (unverified). |
| **Template approval** | Submitted to Meta; Meta reviews. | Submitted through Gupshup to Meta. | Through AiSensy to Meta. | Through Interakt to Meta. |
| **Platform fee** | None. | ₹0/month on pay-as-you-go. | Plan required: Basic ₹1,500/month, Pro ₹3,200/month (AiSensy's July 2025 announcement; current page did not show plan prices, unverified). | Growth ₹2,799/month; Advanced ₹3,799/month. |
| **Per-message price (India)** | Meta's rates only (section 3). | Meta's rate + about **US$0.001** per message; +6% on marketing via the regular API (unverified; Gupshup's rate card was not readable). | Utility/service ₹0.145; marketing ₹1.09 (AiSensy pricing page; appears to include Meta's fee). | Growth: utility ₹0.150, service ₹0.128; Advanced: utility ₹0.140, service ₹0.127 (Interakt pricing page; appears to include Meta's fee). |
| **Webhook signing** | **Documented:** HMAC-SHA256 of the raw body with the app secret, in the `X-Hub-Signature-256` header. | **Not found** in public docs (unverified). | **Not found** (unverified). | **Not found** (unverified). |
| **API and incoming-message webhooks** | Yes, full API. | Yes (API product). | Full API/webhooks appear to need the Pro plan (unverified). | Public API on all plans; the **incoming-messages** webhook is listed for Advanced and unclear on Growth (Interakt pricing page). |
| **Media (voice, photos)** | Media ID in the webhook; download with a token; URL valid **5 minutes**; media IDs expire after **7 days**; audio up to 16 MB, images up to 5 MB. *(Meta media docs.)* | Through Gupshup (details unverified). | Through AiSensy (unverified). | Through Interakt (unverified). |
| **Where data is stored** | Default Meta storage (US). **Local Storage: India** can be selected per phone number; content may be processed outside India for up to about 60 minutes. *(Meta Local Storage docs; provider docs.)* | Meta storage plus Gupshup's platform (location unverified). | Meta plus AiSensy (unverified). | Meta plus Interakt (unverified). |
| **Sandbox / test numbers** | Test number in the Meta app dashboard; send a test message, reply to open a 24-hour window. *(Meta get-started docs.)* | Not stated on the pricing page (unverified). | Not stated (unverified). | Not stated (unverified). |
| **Support** | Developer documentation and Meta support channels; no account manager at this volume. | Provider support (level unverified). | Provider support (unverified). | Provider support (unverified). |

---

## 5. Pilot budget estimate (monthly)

**Assumptions** (to be confirmed by the manager):
- 200 messages a day sent by the system or staff, about 6,000 a month.
- 150 a day are **utility** templates (reminders, follow-ups): **4,500 a month**.
- 50 a day are **service** replies by staff inside the 24-hour window: **1,500 a month**, of which 1,000 are free.
- No marketing or authentication messages. Mothers' messages are free.
- Exchange rate about ₹88 per US$ (assumption). GST 18% added at the end.
- The account is **not** treated as an eligible non-profit (if it is, the 500 paid service messages become free).

| Option | Calculation | Before GST | With GST |
|---|---|---|---|
| **Meta direct** | 4,500 × ₹0.115 + 500 × ₹0.115 | **₹575** | **≈ ₹680** |
| **Gupshup** | Meta ₹575 + 6,000 × US$0.001 (≈ ₹528) | ≈ ₹1,100 | ≈ ₹1,300 (unverified fee) |
| **AiSensy (Pro)** | ₹3,200 + 5,000 × ₹0.145 | ≈ ₹3,925 | ≈ ₹4,630 (unverified plan price) |
| **Interakt (Advanced)** | ₹3,799 + 4,500 × ₹0.140 + 500 × ₹0.127 | ≈ ₹4,490 | ≈ ₹5,300 |

At 200 a day all options are small sums. The difference is mostly the provider plan fee, which buys a dashboard and inbox this project does not use.

**Other costs:** a dedicated phone number (a SIM, or a provider's virtual number; AiSensy lists ₹2,000 + GST a year). Meta charges nothing for setup.

---

## 6. Recommendation and risks

**Choose Meta's WhatsApp Cloud API directly.**

| Risk | Mitigation |
|---|---|
| No provider to call when onboarding stalls | Gupshup as the fallback: pay-as-you-go, no platform fee, close to Meta's cost. Confirm Gupshup's webhook signing before switching. |
| The developer does all setup | It is mostly done already in W3-A1 (provider adapter); the setup steps go into a checklist like `staging.md`. |
| Rates change (Meta changed them in Jan, Apr, Jul and Oct 2026) | Recheck the rate card before Phase 2; D10 sets a monthly budget and a send-stop limit. |
| Verification takes longer than two weeks | Start this week; build and test on Meta's test number meanwhile. The Phase 2 gate is then reported as **Blocked: D06**, never passed on a mock. |
| India rates above are from third-party sources | Confirm in Meta's INR rate card (WhatsApp Manager → pricing) when the account exists. |

---

## 7. What the manager must start this week

1. **Decide which organization owns the WhatsApp account** (the NGO, the facility, or another legal entity). Its documents are used for verification, and an eligible non-profit or government body gets free service messages beyond 1,000.
2. **Create a Meta Business portfolio** for that organization and **start Business Verification**, with GST/PAN/incorporation documents whose name and address match exactly what is entered.
3. **Choose a dedicated phone number** that is not used on the ordinary WhatsApp app, and a **display name** matching the organization.
4. **Add a payment method** to the WhatsApp account.
5. **Name 3–5 staff with consenting test phones** for Phase 2 tests. No mothers' numbers.
6. **Ask the doctor for the first reminder wording** (D05). Templates need the doctor's approval before they go to Meta for approval. Claude prepares placeholders only.
7. **Approve the decision**: Meta direct, or another option.

---

## 8. Sources (checked 7 Nov 2026)

Meta (official):
- Pricing on the WhatsApp Business Platform: <https://developers.facebook.com/docs/whatsapp/pricing> and <https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing.md>
- Messaging limits: <https://developers.facebook.com/docs/whatsapp/messaging-limits>
- Cloud API get started (test number): <https://developers.facebook.com/docs/whatsapp/cloud-api/get-started>
- Cloud API media: <https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media>
- Webhook payload signing: <https://developers.facebook.com/docs/graph-api/webhooks/getting-started>
- Cloud API Local Storage: <https://developers.secure.facebook.com/docs/whatsapp/cloud-api/overview/local-storage/>

Providers (official pages):
- Gupshup pricing: <https://www.gupshup.ai/pricing>
- AiSensy pricing: <https://aisensy.com/pricing>; plan prices from July 2025: <https://news.aisensy.com/95654-pricing-update-effective-july-1-2025>
- Interakt pricing: <https://www.interakt.shop/pricing>

Third-party (used only where marked unverified):
- India per-message rates: <https://whautomate.com/whatsapp-business-api-pricing-india>, <https://msg91.com/guide/whatsapp-business-pricing-update>, <https://blueticks.co/blog/whatsapp-business-api-pricing-2026>, <https://instantdm.com/blog/whatsapp-business-api-pricing-2026-india-october-update>, <https://mindlytics.in/blog/whatsapp-business-api-pricing-india-2026>
- Gupshup per-message fee: <https://richautomate.in/blog/gupshup-pricing-india-2026>
- Business verification timing: <https://richautomate.in/blog/meta-business-verification-whatsapp-api-india-2026>, <https://www.zoko.io/post/whatsapp-business-api-no-gst-number>
- Local Storage processing window: <https://docs.360dialog.com/docs/hub/local-storage>, <https://www.infobip.com/docs/whatsapp/compliance/data-privacy>
