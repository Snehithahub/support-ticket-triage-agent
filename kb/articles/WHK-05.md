---
id: WHK-05
title: Payment captured but order not updated on your site
category: webhooks
updated: 2026-10-06
---
# Payment captured but order not updated on your site

This article is for merchants and developers when a customer has paid, the payment shows as captured in Northwind Pay, but the order on your website is still unpaid or pending.

## Why this happens

Most integrations mark an order as paid in the browser success callback that runs after checkout. That callback can be skipped or fail:

- The customer closed the browser or lost their connection before the callback ran.
- The callback ran, but your server returned an error or timed out while updating the order.
- Signature verification on your server failed, so the order was not updated (see CHK-02).

In all of these cases Northwind Pay considers the payment captured. The money will settle to you on the normal cycle.

## What to do now

1. Find the payment in the Dashboard under Transactions > Payments and confirm its state is `captured`.
2. Call `GET /v1/orders/{id}/payments` with the `order_` ID to list every payment made against that order.
3. If a payment is captured, mark the order as paid on your site and fulfil it.
4. Do not refund the customer until you have checked. Refunding a captured payment for an order you then fulfil means you lose the sale, and the original transaction fee is not returned.

If the customer paid twice for the same order, the API response will show both payments. Fulfil once and refund the extra payment.

## Prevent it from happening again

- **Use webhooks as the source of truth.** Subscribe to `payment.captured` and `order.paid` and update the order from your webhook handler, not only from the browser callback.
- **Verify every webhook.** Check the `X-Northwind-Signature` header against the raw body before acting on the event.
- **Make updates idempotent.** Use the `X-Northwind-Event-Id` header to skip events you have already processed, because the same event may arrive more than once.
- **Respond quickly.** Return a 2xx status within 5 seconds and do slow work in the background, or deliveries will be retried.
- **Reconcile regularly.** A scheduled job that checks unpaid orders with `GET /v1/orders/{id}/payments` catches anything the webhook missed.

## Still need help?

Email support@northwindpay.example with the order ID (`order_...`), the payment ID (`pay_...`), and the `X-Northwind-Event-Id` of any webhook you received. See also: WHK-01, WHK-03, CHK-01.
