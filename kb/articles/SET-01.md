---
id: SET-01
title: Settlement schedule and cycles
category: settlements
updated: 2026-09-08
---
# Settlement schedule and cycles

This article is for merchants who want to know when payments reach their bank account and how the settlement amount is calculated. It covers the standard cycle, international payments, holidays, and the settlement formula.

## Standard settlement cycle

Northwind Pay settles captured payments on a T+2 business day cycle, where T is the date the payment was captured. For example, a payment captured on a Monday is normally settled on Wednesday, as long as both days are business days.

Only captured payments are settled. Payments that are `pending`, `authorized`, or `failed` are not included until they are captured.

## International payments

Payments made with international cards and international payment methods settle on a T+7 business day cycle. If you accept both domestic and international payments, you will see them settle on different days, even when they were captured on the same date.

## Holidays and Sundays

Settlements are not processed on bank holidays or Sundays. If a settlement falls on one of these days, it moves to the next business day. Around long weekends or festival periods, several days of payments may arrive together in one larger settlement.

## How the settlement amount is calculated

Each settlement is calculated as:

**Settlement amount = captured payments - fees - GST on fees - refunds - dispute deductions**

| Component | What it includes |
|---|---|
| Captured payments | Payments captured in the settlement period |
| Fees | Transaction fees and any other charges, such as instant refunds |
| GST on fees | Tax charged on the fees |
| Refunds | Refunds processed and paid from your balance |
| Dispute deductions | Amounts held for chargebacks raised against your payments |

Because fees are deducted from each settlement, you do not pay Northwind Pay separately. If a settlement is lower than you expected, check for refunds and dispute deductions first.

To match a settlement against individual payments, download the settlement report from **Dashboard > Reports > Settlements**. See SET-03.

If a settlement has not arrived when expected, it may be on hold. See SET-02 for common reasons. If you need funds faster than the standard cycle, see SET-04 for Instant Settlements.

## Still need help?

Email support@northwindpay.example with the settlement ID (`setl_...`) or the capture dates of the payments you are asking about. See also: SET-02, SET-03, SET-04.
