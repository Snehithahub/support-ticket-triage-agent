---
id: DSP-01
title: How disputes and chargebacks work
category: disputes
updated: 2026-07-22
---
# How disputes and chargebacks work

This article explains what a dispute is, the types of disputes you may receive, and how a dispute affects your settlements.

## What is a dispute?

A dispute is raised by your customer's bank, not by Northwind Pay. It usually starts when a customer questions a payment with their bank, for example because they do not recognize it, did not receive the goods, or believe they were charged incorrectly. The bank then contacts Northwind Pay, and you see the dispute in Dashboard > Disputes. Each dispute has an ID starting with `disp_` and is linked to the original payment ID (`pay_...`).

## Types of disputes

- **Retrieval request**: the bank asks for information about the payment. Funds are not reversed and there is no fee. Respond promptly, as an unanswered request can lead to a chargeback.
- **Chargeback**: the bank reverses the funds and you must show the payment was valid.
- **Pre-arbitration**: the bank challenges your response to a chargeback.
- **Arbitration**: the final stage, where the case is decided by the card network when the parties cannot agree.

## Dispute lifecycle

1. **Notification**: the dispute appears in Dashboard > Disputes, and you receive a `dispute.created` webhook if you subscribe to it.
2. **Response window**: you have 7 calendar days from the notification to submit evidence or accept the dispute. If you miss the deadline, the dispute is automatically accepted and counted as lost.
3. **Review**: the bank reviews your evidence. A decision typically takes 45-75 days after you submit it.
4. **Outcome**: the dispute is marked won or lost, and you receive a `dispute.won` or `dispute.lost` webhook.

## How disputes affect settlements

When a chargeback is raised, the disputed amount is deducted from your next settlement and put on hold. If you win, the held amount is released with the next settlement. If you accept or lose, the amount is not returned. A chargeback fee of Rs 500 plus GST is charged only if the dispute is lost.

If your open disputes total more than Rs 1,00,000, your settlements can be put on hold until they are resolved. Accounts with a chargeback rate above 1% of monthly transactions are placed under a risk review.

## Still need help?

Contact support@northwindpay.example with the dispute ID (`disp_...`) and the payment ID (`pay_...`). See also: DSP-02, DSP-03, DSP-04.
