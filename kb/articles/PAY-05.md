---
id: PAY-05
title: Payments stuck in pending or authorized state
category: failed_payments
updated: 2026-09-02
---
# Payments stuck in pending or authorized state

This article is for merchants who see payments that have not reached a final state. It explains what `pending` and `authorized` mean, how long each can last, and what happens if no action is taken.

## Payment states

A payment moves through these states:

- **created**: The payment has been started but the customer has not completed it.
- **authorized**: The bank has approved the payment and placed a hold on the customer's funds, but the money has not been captured.
- **captured**: The money has been collected and will be included in your settlement.
- **failed**: The payment did not go through.
- **refunded**: The captured amount has been refunded.

A payment can also show as `pending` while Northwind Pay waits for confirmation from the bank.

## Pending payments

Payments can stay `pending` for up to 30 minutes while waiting for bank confirmation. UPI payments can stay pending for up to 2 hours. After that, the payment moves automatically to `captured` or `failed`. You do not need to do anything.

While a payment is pending:

- Avoid asking the customer to pay again, which can cause a double debit.
- Hold the order in a waiting state rather than cancelling it.
- Rely on the `payment.captured` or `payment.failed` webhook to update the order once the final state is known.

## Authorized payments

If your integration captures payments manually, a payment stays `authorized` until you capture it. Authorized payments not captured within 5 days are automatically voided, and the customer's bank releases the hold on their funds.

To capture an authorized payment:

1. Go to **Transactions > Payments** and open the payment.
2. Confirm the order can be fulfilled.
3. Capture the payment from the Dashboard or through the API.

If you do not want to complete the order, you can let the authorization expire. The hold is released by the bank, not by Northwind Pay, so the exact time the customer sees the funds again depends on their bank.

## Avoiding stuck authorizations

- Capture payments as soon as you confirm the order.
- Subscribe to the `payment.authorized` event so your system knows when a capture is needed.
- Review authorized payments daily if you capture manually.

## Still need help?

Contact support@northwindpay.example with the payment ID (`pay_...`), its current state, and when the payment was created. See also: PAY-01, PAY-04, REF-01.
