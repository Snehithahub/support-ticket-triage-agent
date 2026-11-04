---
id: SET-06
title: Why is my settlement amount lower than expected?
category: settlements
updated: 2026-10-09
---
# Why is my settlement amount lower than expected?

This article is for merchants and finance teams who see a bank credit smaller than the total of their captured payments. It explains what is deducted before a settlement is paid and how to match each deduction.

## What is deducted from a settlement

Every settlement follows the same formula:

**Settlement amount = captured payments - fees - GST on fees - refunds - dispute deductions**

- **Fees (MDR)**: the merchant discount rate for each payment, for example 2% on domestic payments on the Standard plan or 3% on international cards.
- **GST on fees**: 18% on all fees.
- **Other charges**: instant refund fees, instant settlement fees, and chargeback fees for lost disputes are also deducted from settlements.
- **Refunds**: refunds you issued are deducted, including refunds that were queued earlier because your balance was low.
- **Dispute deductions**: when a chargeback is raised, the disputed amount is held from the next settlement.

Fees are never billed separately. Your monthly tax invoice is a statement of fees already deducted.

## Worked example

Suppose a single domestic payment of Rs 10,000 is captured at 2% MDR:

| Item | Amount |
|---|---|
| Captured payment | Rs 10,000 |
| Fee at 2% MDR | Rs 200 |
| GST at 18% on the fee | Rs 36 |
| Total deducted | Rs 236 |
| Amount settled | Rs 9,764 |

If you also refunded a customer or had a chargeback in the same period, those amounts would be subtracted as well.

## Other reasons the total looks low

- **Payments not yet due**: domestic payments settle T+2 business days after capture and international payments T+7 business days, so recent payments may be in a later settlement.
- **Holidays**: settlements do not run on bank holidays or Sundays and move to the next business day.
- **Settlement on hold**: if a whole settlement is missing rather than reduced, it may be on hold. See SET-02.

## Match it using the settlement report

1. Go to **Dashboard > Reports > Settlements** and download the CSV.
2. Filter by the `setl_` ID or by the UTR shown on your bank statement.
3. Add up the captured payments, then subtract the fee, GST, refund (`rfnd_...`) and dispute (`disp_...`) lines.
4. Compare the result with the amount credited to your bank.

## Still need help?

Email support@northwindpay.example with the settlement ID (`setl_...`), the UTR, and the amount you expected. See also: SET-03, SET-01, INV-03.
