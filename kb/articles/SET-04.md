---
id: SET-04
title: Instant Settlements
category: settlements
updated: 2026-10-02
---
# Instant Settlements

This article is for merchants who need funds in their bank account faster than the standard settlement cycle. It explains what Instant Settlements are, who can use them, what they cost, and the daily limit.

## What Instant Settlements are

Normally, captured payments are settled on a T+2 business day cycle, or T+7 business days for international payments. Instant Settlements let you request an on-demand settlement of your available balance instead of waiting for the scheduled cycle. This is useful when you need working capital quickly, for example to pay suppliers or cover a busy sales period.

## Eligibility

You can use Instant Settlements if both of these are true:

- Your account is KYC-verified.
- Your account has at least 3 months of activity on Northwind Pay.

If your settlements are currently on hold, for example because of a risk review or a bank account verification issue, resolve the hold first. See SET-02.

## Fees and limits

| Item | Detail |
|---|---|
| Fee | 0.25% of the settled amount |
| Tax | GST on the fee |
| Daily limit | Up to Rs 5,00,000 per day |

The fee is deducted from the amount settled, so the credit to your bank is the requested amount minus the fee and GST. Instant Settlement fees appear as other charges on your monthly tax invoice. Any amount you do not settle instantly continues on the standard cycle at no extra cost.

## How to request an Instant Settlement

1. Log in to dashboard.northwindpay.example.
2. Open the settlements section and select the Instant Settlement option.
3. Enter the amount you want to settle, up to your available balance and within the daily limit.
4. Review the fee and confirm.

The request creates a settlement with its own settlement ID (`setl_...`), which you can find in the settlement report under **Dashboard > Reports > Settlements**.

### If the option is not available

If you cannot see the Instant Settlement option, check that your KYC is verified and that your account has been active for at least 3 months. If both are true and the option is still missing, contact support.

## Still need help?

Contact support@northwindpay.example with your account details, the amount you tried to settle, and the settlement ID (`setl_...`) if one was created. See also: SET-01, SET-02, KYC-03.
