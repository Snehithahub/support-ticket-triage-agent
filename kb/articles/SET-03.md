---
id: SET-03
title: Reconciling settlements with reports
category: settlements
updated: 2026-08-14
---
# Reconciling settlements with reports

This article is for finance teams and merchants who need to match money received in the bank against individual payments. It explains how to download settlement reports and read the IDs and references in them.

## Download the settlement report

1. Log in to dashboard.northwindpay.example.
2. Go to **Dashboard > Reports > Settlements**.
3. Choose the date range you want to reconcile.
4. Download the report as a CSV file.

Users with the Finance role can download reports, which lets your accounts team reconcile without access to other settings.

## Key identifiers in the report

Each line in the report links a payment to the settlement it was paid in:

- **Payment ID (`pay_...`)**: The individual payment.
- **Order ID (`order_...`)**: Your order reference, if you created orders.
- **Refund ID (`rfnd_...`)**: Appears on lines for refunds deducted from the settlement.
- **Dispute ID (`disp_...`)**: Appears on lines for dispute deductions.
- **Settlement ID (`setl_...`)**: The settlement the line belongs to.
- **UTR**: The bank reference number for the transfer to your bank account.

The UTR is what appears on your bank statement. Use it to match a bank credit to a `setl_` ID, then use the `setl_` ID to find every payment, refund, and deduction in that settlement.

## Matching the amounts

Every settlement follows the same formula:

**Settlement amount = captured payments - fees - GST on fees - refunds - dispute deductions**

To reconcile a settlement:

1. Filter the report by the `setl_` ID.
2. Add up the captured payment amounts.
3. Subtract the fees and GST on fees.
4. Subtract refunds and any dispute deductions.
5. Compare the result with the amount credited under the matching UTR on your bank statement.

## Common mismatches

- **A payment is missing:** It may have been captured too recently, or it is an international payment on the T+7 business day cycle. See SET-01.
- **The total is lower than expected:** Look for refund or dispute lines in the same settlement.
- **No credit in the bank:** The settlement may be on hold. See SET-02.
- **Fees look different from your plan:** Compare against your monthly tax invoice, which lists fees already deducted.

## Still need help?

Email support@northwindpay.example with the settlement ID (`setl_...`), the UTR, and the line or amount that does not match. See also: SET-01, SET-02, SET-04.
