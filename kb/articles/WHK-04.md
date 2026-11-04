---
id: WHK-04
title: Webhook events reference
category: webhooks
updated: 2026-09-10
---
# Webhook events reference

This article lists every webhook event Northwind Pay sends and explains when each one fires, so you can choose which events to subscribe to.

## Available events

| Event | When it fires |
|---|---|
| `payment.authorized` | The customer's bank has authorized the payment, but it has not been captured yet. |
| `payment.captured` | The payment has been captured and will be included in a future settlement. |
| `payment.failed` | The payment failed, for example because of a decline, failed authentication, or bank timeout. |
| `refund.created` | A full or partial refund has been created from the Dashboard or API. |
| `refund.processed` | The refund has been processed and an ARN is available. |
| `refund.failed` | The refund could not be completed, for example because the customer's account or card is closed. |
| `settlement.processed` | A settlement has been processed to your bank account. |
| `dispute.created` | The customer's bank has raised a dispute on a payment. |
| `dispute.won` | The dispute was decided in your favor. |
| `dispute.lost` | The dispute was decided against you or accepted. |
| `order.paid` | An order has received a successful payment. |

## Which events to subscribe to

- **Order fulfillment**: `order.paid` and `payment.captured` to confirm payment before shipping, and `payment.failed` to prompt the customer to retry.
- **Authorize-then-capture flows**: `payment.authorized`, so you can capture in time. Authorized payments not captured within 5 days are auto-voided.
- **Refund tracking**: `refund.created`, `refund.processed`, and `refund.failed`, so your support team can share the ARN or follow up on failures.
- **Finance and reconciliation**: `settlement.processed`.
- **Dispute handling**: `dispute.created`, so you can start gathering evidence within the 7-calendar-day response window, plus `dispute.won` and `dispute.lost`.

Subscribe only to the events you use. Fewer events means less load on your endpoint.

## Things to keep in mind

- One payment can trigger several events over its life, such as `payment.authorized` followed by `payment.captured`.
- Events may arrive more than once. Use the `X-Northwind-Event-Id` header to skip duplicates.
- Do not rely on events arriving in order. If order matters, fetch the latest state through the API.
- A pending payment does not trigger a final event until it moves to captured or failed, which can take up to 30 minutes, or up to 2 hours for UPI.

## Still need help?

Contact support@northwindpay.example with the event type, the `X-Northwind-Event-Id`, and the related ID (`pay_...`, `rfnd_...`, `setl_...`, or `disp_...`). See also: WHK-01, WHK-03, DSP-01.
