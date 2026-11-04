---
id: REF-03
title: Refund failed or stuck
category: refunds
updated: 2026-09-22
---
# Refund failed or stuck

This article is for merchants whose refund shows as failed, or has not moved forward as expected. It explains refund states, common causes, and what to do next.

## Refund states

Every refund has one of three states:

- **created**: The refund request has been accepted and is waiting to be sent to the bank.
- **processed**: The refund has been sent and an ARN (Acquirer Reference Number) is available.
- **failed**: The refund could not be completed.

You can see the state on the refund details in **Transactions > Payments**, or by subscribing to the `refund.created`, `refund.processed`, and `refund.failed` webhook events.

## Refund stuck in created

The most common reason a refund stays in `created` is low account balance. A refund needs sufficient balance to be processed. If your balance is too low, the refund is queued and is processed automatically once your next settlement covers it. You do not need to create the refund again; doing so may result in refunding the customer twice.

If your balance is sufficient and the refund has stayed in `created` for an unusually long time, contact support with the refund ID.

## Failed refunds

### Why refunds fail

A refund can fail when the customer's destination can no longer receive money, most often because:

- The customer's bank account has been closed.
- The customer's card has been closed or replaced.

### What happens after a failure

Northwind Pay retries failed refunds automatically for 3 days. If the refund still cannot be completed:

1. The refund amount is credited back to your merchant balance.
2. The refund remains in the `failed` state.
3. You must refund the customer by another method, such as a bank transfer, after confirming their current details directly with them.

Keep a record of how you refunded the customer outside Northwind Pay, since the original payment will not show that refund.

## Customer says the refund is missing

If the refund is `processed` but the customer cannot see it, check the normal timeline for their payment method in REF-02. Once that time has passed, give the customer the ARN so their bank can trace the credit.

## Still need help?

Contact support@northwindpay.example with the payment ID (`pay_...`), refund ID (`rfnd_...`), and the refund's current state. See also: REF-01, REF-02, SET-02.
