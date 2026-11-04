---
id: CHK-02
title: Fixing common checkout integration errors
category: checkout
updated: 2026-09-24
---
# Fixing common checkout integration errors

This article is for developers whose Standard Checkout integration returns an error, does not open, or fails at the verification step. Find the symptom below and apply the matching fix.

## Order and amount errors

- **`BAD_REQUEST_ERROR: amount must be at least 100`**: amounts are always in paise, not rupees. The minimum is Rs 1, which is 100 paise. Multiply rupee values by 100 before calling `POST /v1/orders`.
- **`order_id is invalid`**: the order was created with a different key than the one passed to checkout, or test and live keys are mixed. Create the order and open checkout with keys from the same account and the same mode.
- **Amount or currency mismatch**: the amount or currency you pass to checkout must match the order exactly. Read both values from the order response instead of recalculating them in the browser.

## Checkout does not open

If nothing happens when the customer clicks Pay, check these in order:

1. **Script failed to load.** Open the browser developer console and confirm that `https://checkout.northwindpay.example/v1/checkout.js` loaded without errors.
2. **Content Security Policy.** If your site sets a Content Security Policy, allow checkout.northwindpay.example for scripts and frames. A blocked domain usually shows a CSP warning in the console.
3. **Popup blocker.** Open checkout directly from the customer's click, not from a delayed callback, so the browser does not treat it as an unwanted popup.

## Signature verification failed

When your server rejects a payment with `signature verification failed`, the cause is almost always one of these:

- **Wrong secret**: the signature uses your API Key Secret, not your webhook secret. Make sure the Key Secret matches the Key ID used to create the order, and trim any stray whitespace.
- **Wrong order of IDs**: the message is `order_id + "|" + payment_id`, in that order.
- **Wrong order ID**: use the `order_` ID returned by Northwind Pay, not the order number from your own database.

If verification fails but the payment shows `captured` in the Dashboard, fix the check rather than refunding the customer. See CHK-01 for a working example.

## Still need help?

Email support@northwindpay.example with the exact error message, the order ID (`order_...`), the payment ID (`pay_...`) if one was created, and your mode (test or live). See also: CHK-01, API-03, WHK-05.
