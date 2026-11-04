---
id: PAY-04
title: Troubleshooting UPI payment failures
category: failed_payments
updated: 2026-08-19
---
# Troubleshooting UPI payment failures

This article is for merchants whose customers have trouble paying by UPI. It explains the most common UPI errors, why UPI payments can stay pending, and what to tell customers.

## Common UPI errors

### Collect request expired

Error code: `UPI_COLLECT_EXPIRED`

With UPI collect, Northwind Pay sends a payment request to the customer's UPI app. The customer must approve it within 5 minutes. If they do not, the request expires and the payment fails.

Common causes:

- The customer did not notice the request in their UPI app.
- The customer switched apps and came back too late.
- The customer entered the wrong UPI ID and the request went elsewhere.

What to do: ask the customer to retry and approve the request promptly. On mobile, offering UPI intent avoids this problem because the UPI app opens directly. See PAY-03.

### Invalid UPI ID

Error code: `INVALID_VPA`

The UPI ID (VPA) the customer entered does not exist or has a typo. Ask the customer to check the UPI ID in their UPI app and enter it again exactly, or to pay using UPI intent instead of typing it.

## UPI payment stuck in pending

UPI payments can stay `pending` for up to 2 hours while Northwind Pay waits for confirmation from the customer's bank. During this time:

- Do not ask the customer to pay again unless they want to, as this can lead to two debits.
- Do not mark the order as failed yet.

After the waiting period, the payment moves automatically to `captured` or `failed`. If you use webhooks, listen for `payment.captured` or `payment.failed` to update the order. See PAY-05.

## Customer debited but payment failed

If a UPI payment ends as `failed` but the customer was debited, their bank reverses the amount automatically within 5-7 business days. You cannot speed this up. Share the RRN (the UPI bank reference number) from the payment details so the customer can follow up with their bank. See PAY-01.

## Checklist for UPI issues

1. Check the payment state and decline code in **Transactions > Payments**.
2. If `pending`, wait for the final state.
3. If `failed`, share the reason and ask the customer to retry.
4. If the customer was debited, share the RRN.

## Still need help?

Email support@northwindpay.example with the payment ID (`pay_...`), the RRN, and the customer's UPI app if known. See also: PAY-01, PAY-02, PAY-05.
