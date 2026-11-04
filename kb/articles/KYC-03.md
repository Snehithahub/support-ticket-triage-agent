---
id: KYC-03
title: KYC verification timelines and account limits
category: kyc
updated: 2026-08-07
---
# KYC verification timelines and account limits

This article is for merchants who have submitted KYC, or are about to, and want to know how long verification takes and what they can do with their account in the meantime.

## How long verification takes

KYC verification takes 2-3 business days after all documents are submitted. The timeline starts only when every required document has been uploaded. If a document is missing or rejected, the clock restarts after you submit the corrected version.

To avoid delays:

- Submit all required documents together. See KYC-01.
- Check each document for clarity, expiry, and matching names before uploading.
- Make sure your website shows a refund policy, terms, and contact details.

## What you can do before KYC is verified

Before verification, your account works with limits:

| Feature | Before KYC verification | After KYC verification |
|---|---|---|
| Accepting payments | Up to Rs 50,000 in total | No KYC-related limit |
| Settlements | On hold | Paid on the normal cycle |
| Live API keys | Not available | Available |
| Instant Settlements | Not available | Available after 3 months of activity |

The Rs 50,000 limit is a total across all payments, not a daily or per-payment limit. Once you reach it, you cannot accept more payments until KYC is verified.

## What happens to held settlements

Payments you capture before verification are not lost. Settlements stay on hold until your KYC is verified. Once it is, the hold is lifted and your captured payments are settled through the normal settlement process. See SET-01 and SET-02.

## Checking your status

1. Log in to dashboard.northwindpay.example.
2. Open the KYC section to see whether your submission is pending, verified, or rejected.
3. If rejected, read the reason shown next to the document and resubmit. See KYC-02.

You can use test mode and test API keys at any time, even before KYC is verified, to build and test your integration. Test payments never move money.

## Still need help?

Contact support@northwindpay.example with your registered business name and the date you submitted your documents, if verification has taken longer than 3 business days. See also: KYC-01, KYC-02, SET-02.
