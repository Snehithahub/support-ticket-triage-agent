---
id: REF-02
title: Refund timelines by payment method
category: refunds
updated: 2026-09-18
---
# Refund timelines by payment method

This article is for merchants whose customers ask when a refund will reach their account. It lists the normal timelines for each payment method and explains how to use the ARN to help customers trace a refund.

## How long refunds take

Once a refund is processed by Northwind Pay, the time until the customer sees the money depends on how they originally paid. Normal refunds follow these timelines:

| Payment method | Normal refund timeline |
|---|---|
| Cards | 5-7 business days |
| UPI | 2-3 business days |
| Netbanking | 5-7 business days |
| Wallets | 1-2 business days |

These timelines count business days, so weekends and bank holidays add to the wait. If you need faster refunds for UPI or supported cards, you can use instant refunds, which are credited within 30 minutes for a fee. See REF-04 for details.

## Finding the ARN

When a refund reaches the `processed` state, it is assigned an ARN (Acquirer Reference Number). To find it:

1. Go to **Transactions > Payments** in the Dashboard.
2. Open the original payment and select the refund (`rfnd_...`) in its refund history.
3. Copy the ARN shown on the refund details.

The ARN is the reference the customer's bank uses to locate the credit. If a refund is still in the `created` state, it does not have an ARN yet.

## What to tell your customer

When a customer asks about a refund, share:

- The date you issued the refund and the amount.
- The expected timeline for their payment method from the table above.
- The ARN, once the refund is processed.

If the timeline has passed and the customer still cannot see the money, ask them to contact their bank or card issuer and quote the ARN. In most cases the bank has already received the credit and can confirm it from the ARN.

## When the timeline has passed

If the refund is still not `processed` after a reasonable time, or it shows as `failed`, the problem is likely on the refund itself rather than at the bank. See REF-03 for failed and stuck refunds, including what happens when the customer's account or card has been closed.

## Still need help?

Email support@northwindpay.example with the payment ID (`pay_...`), refund ID (`rfnd_...`), and the ARN if available. See also: REF-01, REF-03, REF-04.
