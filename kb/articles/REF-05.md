---
id: REF-05
title: Refund fees and limits
category: refunds
updated: 2026-07-30
---
# Refund fees and limits

This article is for merchants who want to understand what a refund costs and the limits on how much and how late they can refund. It answers common questions about fees, amounts, and the refund window.

## Fees on refunds

- **Normal refunds are free.** Northwind Pay does not charge any fee to issue a normal refund.
- **The original transaction fee is not returned.** When a customer paid, a transaction fee was deducted from your settlement. That fee stays charged even if you refund the payment in full.
- **Instant refunds have a fee.** Instant refunds cost 0.5% of the refund amount (minimum Rs 5) plus GST. See REF-04.

For example, if you refund a domestic card payment in full, the customer receives the full captured amount, and the fee you paid on the original payment is not credited back to you.

## Amount limits

- The total of all refunds on a payment cannot exceed the captured amount.
- You can issue multiple partial refunds on the same payment, as long as their combined total stays within the captured amount.
- If you try to refund more than the remaining amount, the request is rejected. Check the payment's refund history to see how much has already been refunded.

## Time limit

Refunds are allowed within 180 days of the capture date. After 180 days, the Dashboard and API will not accept a refund for that payment. If you need to return money to a customer after that window, you must do so outside Northwind Pay, for example by bank transfer.

## Balance requirement

A refund is paid out of your Northwind Pay balance. If your balance is not enough, the refund is queued and processed once your next settlement covers it. Refunds are also deducted when your settlement amount is calculated, so a day with many refunds will lower that settlement. See SET-01 for how settlement amounts are calculated.

## Still need help?

Contact support@northwindpay.example with the payment ID (`pay_...`), refund ID (`rfnd_...`) if one was created, and the amount you tried to refund. See also: REF-01, REF-04, SET-01.
