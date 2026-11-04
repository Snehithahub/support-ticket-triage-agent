---
id: INV-03
title: Understanding fees on your invoice
category: billing
updated: 2026-10-08
---
# Understanding fees on your invoice

This article explains each fee line on your monthly Northwind Pay tax invoice and how those fees relate to your settlements.

## Fee lines on your invoice

Your invoice shows total transaction fees, other charges, and GST. On the Standard plan, the rates are:

| Fee line | Rate |
|---|---|
| Domestic cards, netbanking, wallets, UPI | 2% per transaction |
| International cards, Diners, Amex | 3% per transaction |
| EMI | 2.5% per transaction |
| Instant refunds | 0.5% of refund amount (minimum Rs 5) |
| Instant Settlements | 0.25% of settled amount |
| Chargebacks (lost disputes only) | Rs 500 per chargeback |
| GST | 18% on all fees above |

If you are on the Growth or Enterprise plan, your transaction fee rates differ. See PRC-01.

A few things that do not appear as charges:

- **Normal refunds**: Northwind Pay does not charge a fee for normal refunds. However, the original transaction fee is not returned when you refund a payment.
- **Retrieval requests and won disputes**: no chargeback fee is charged.

## How fees are collected

Northwind Pay deducts fees from each settlement, so there is no separate bill to pay. Your settlement amount is captured payments minus fees, GST on fees, refunds, and dispute deductions.

The monthly invoice is a statement of the fees already deducted during the previous calendar month. It is generated on the 3rd and is available as a PDF in Dashboard > Reports > Invoices.

## Reconciling the invoice with settlements

1. Download the invoice for the month from Reports > Invoices.
2. Download the settlement reports for the same period from Reports > Settlements (CSV).
3. Add up the fees and GST deducted across those settlements.
4. Compare the totals with the invoice, and check other charges against your instant refunds, Instant Settlements, and lost disputes for the month.

If a fee looks wrong, contact support. Fees confirmed as charged incorrectly are corrected with a credit note on your next invoice. See INV-02.

## Still need help?

Email support@northwindpay.example with the invoice month, the fee line you are asking about, and the related settlement IDs (`setl_...`) or payment IDs (`pay_...`). See also: INV-01, INV-02, SET-03.
