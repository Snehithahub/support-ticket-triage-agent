---
id: API-02
title: Test mode vs live mode
category: api_keys
updated: 2026-08-12
---
# Test mode vs live mode

This article explains the difference between test mode and live mode in Northwind Pay, and how to move your integration from one to the other safely.

## How the two modes differ

Test mode and live mode are fully separate environments within the same account:

- **Separate keys**: test keys have a Key ID starting with `nw_test_`; live keys start with `nw_live_`. Each mode has its own Key Secret.
- **Separate data**: payments, refunds, and orders created in test mode do not appear in live mode, and the reverse is also true.
- **No real money**: test payments never move money. They are never settled to your bank account.

Both modes use the same API base URL, api.northwindpay.example/v1. The key you authenticate with decides which mode a request runs in.

## When to use each mode

Use test mode to build and verify your integration: creating orders, completing checkout, handling payment failures, issuing refunds, and receiving webhooks. You can keep using test mode at any time, even after you go live, to try out changes safely.

Use live mode to accept real payments from customers. Live keys are available only after your KYC is verified. Until then, you can continue building in test mode.

## Switching to live mode

1. Confirm your KYC is verified in the Dashboard.
2. Toggle the Dashboard to live mode.
3. Go to Settings > API Keys and generate a live key pair. Only Owner and Admin users can do this.
4. Replace the test Key ID and Key Secret on your server with the live ones.
5. Check that your webhook endpoints and subscribed events are set up for live mode under Settings > Webhooks.
6. Make a small real payment and refund it to confirm the end-to-end flow.

## Common mistakes

- **Mixing keys**: using a test Key ID with a live Key Secret, or the reverse, returns `401 AUTHENTICATION_ERROR`.
- **Looking in the wrong mode**: if a payment you just made is missing from the Dashboard, check that the Dashboard mode matches the key your server used.
- **Testing with live keys**: live payments move real money and incur fees, so run test scenarios in test mode.
- **Hardcoded keys**: store keys in environment variables so you can switch modes without code changes.

## Still need help?

Email support@northwindpay.example with your Key ID (never the Key Secret), the mode you are using, and an example payment ID (`pay_...`) or order ID (`order_...`). See also: API-01, API-03, KYC-03.
