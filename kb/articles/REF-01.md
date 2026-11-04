---
id: REF-01
title: How to issue a full or partial refund
category: refunds
updated: 2026-09-15
---
# How to issue a full or partial refund

This article is for merchants who need to return money to a customer. It explains how to refund a captured payment in full or in part from the Dashboard or through the API.

## Before you start

Check these conditions before you create a refund:

- The payment must be in the `captured` state. Payments that are only `authorized` cannot be refunded; uncaptured authorizations are voided instead.
- The refund must be created within 180 days of the capture date.
- The total of all refunds on a payment cannot exceed the captured amount.
- Your account balance must be enough to cover the refund. If it is not, the refund is queued until your next settlement covers it.

## Refund from the Dashboard

1. Log in to dashboard.northwindpay.example.
2. Go to **Transactions > Payments** and search for the payment ID (`pay_...`) or order ID (`order_...`).
3. Open the payment and click **Refund**.
4. Choose **Full refund** to return the entire remaining amount, or enter a smaller amount for a partial refund.
5. Optionally add a note for your records, then confirm.

The refund is created with a refund ID (`rfnd_...`) and appears under the payment's refund history.

## Refund through the API

Send an authenticated request to the refunds endpoint:

```
POST https://api.northwindpay.example/v1/payments/{id}/refunds
```

Replace `{id}` with the payment ID and authenticate with your Key ID and Key Secret. Specify the amount you want to refund in the request body: the full captured amount for a full refund, or a smaller amount for a partial refund. The response contains the new `rfnd_` ID and its status, which starts as `created`.

If you use webhooks, subscribe to `refund.created`, `refund.processed`, and `refund.failed` to track the refund without polling.

## Multiple partial refunds

You can issue more than one partial refund on the same payment, for example when a customer returns items from an order one at a time. Each partial refund gets its own `rfnd_` ID. The only limits are that every refund must fall within the 180-day window and the combined refunded amount cannot be more than the amount originally captured. Once the full captured amount has been refunded, the payment moves to the `refunded` state.

## Still need help?

Contact support@northwindpay.example with the payment ID (`pay_...`), any refund IDs (`rfnd_...`), and the error message you saw. See also: REF-02, REF-03, REF-05.
