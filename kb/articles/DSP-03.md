---
id: DSP-03
title: Dispute fees and settlement deductions
category: disputes
updated: 2026-07-29
---
# Dispute fees and settlement deductions

This article explains how disputes affect your money: what is deducted from your settlements, what fees apply, and how to decide between accepting and contesting a dispute.

## Settlement deductions

When a chargeback is raised, the disputed amount is deducted from your next settlement and put on hold. This happens before the dispute is decided. Your settlement report in Dashboard > Reports > Settlements shows the deduction against the related `setl_` ID, so you can match it to the dispute.

Your settlement amount is calculated as captured payments minus fees, GST on fees, refunds, and dispute deductions.

If your open disputes total more than Rs 1,00,000, your settlements can be put on hold entirely until the disputes are resolved.

## Chargeback fee

| Situation | Fee |
|---|---|
| Retrieval request | No fee |
| Dispute won | No fee |
| Dispute lost | Rs 500 plus GST per chargeback |

The chargeback fee is charged only when a dispute is lost. It appears under other charges on your monthly tax invoice, with GST at 18%.

## Accept or contest?

**Accept** when the customer's claim is valid, for example if the goods were not delivered or the customer was charged twice. When you accept a dispute, the disputed amount is not returned to you.

**Contest** when you have clear evidence that the payment was valid, such as proof of delivery, an invoice, and customer communication. You must submit evidence within 7 calendar days of the notification. If you miss the deadline, the dispute is automatically accepted and treated as lost.

Before contesting, check that your evidence directly addresses the bank's stated reason. Weak evidence is likely to end in a lost dispute and the fee, after a decision period that typically takes 45-75 days.

## When you win

If the bank decides in your favor, the held amount is released with your next settlement, and no chargeback fee is charged. You also receive a `dispute.won` webhook if you subscribe to it.

## Still need help?

Contact support@northwindpay.example with the dispute ID (`disp_...`) and the settlement ID (`setl_...`) where the deduction appears. See also: DSP-01, DSP-02, SET-02.
