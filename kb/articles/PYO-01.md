---
id: PYO-01
title: Payout modes, limits and timelines
category: payouts
updated: 2026-10-12
---
# Payout modes, limits and timelines

This article is for merchants using Northwind Payouts to send money to vendors, sellers or customers. It explains the transfer modes available, their limits, and how long each usually takes.

## How payouts work

Northwind Payouts sends money from your payout balance to a beneficiary's bank account or UPI ID. The payout balance is separate from the balance that receives your payment settlements, so you need to fund it before sending payouts. Every payout gets an ID that starts with `pout_`, which you can use to track it.

## Modes at a glance

| Mode | Limit per payout | Availability | Typical processing time |
|---|---|---|---|
| IMPS | Up to Rs 5,00,000 | 24x7 | Within 30 minutes |
| UPI | Up to Rs 1,00,000 | 24x7 | Within 30 minutes |
| NEFT | No upper limit | 24x7, half-hourly batches | Within 2 hours |
| RTGS | Minimum Rs 2,00,000 | Banking days | Within 2 hours on banking days |

Processing times are typical, not guaranteed. The beneficiary's bank can take longer to credit the account, especially when its systems are slow.

## Choosing a mode

- **IMPS**: a good default for urgent bank transfers within its limit, at any time of day.
- **UPI**: suited to smaller payouts when you have the beneficiary's UPI ID rather than account details.
- **NEFT**: use for large amounts that are not urgent. Because NEFT runs in half-hourly batches, a payout waits for the next batch before it is sent.
- **RTGS**: use for single high-value transfers at or above the minimum. RTGS payouts are processed on banking days only.

Fees differ by mode. See PYO-03 for the fee for each mode and for account validation before a first payout.

## Tracking a payout

Each payout moves through states such as queued, pending, processing and processed. A payout in `pending` is waiting for approval if your account uses an approval workflow. Once a payout is processed, the bank reference (UTR) is available so the beneficiary can trace the credit with their bank.

If a payout stays in `processing` for more than 24 hours, or ends up failed or reversed, see PYO-02.

## Still need help?

Email support@northwindpay.example with the payout ID (`pout_...`), the mode used, and the UTR if one is shown. See also: PYO-02, PYO-03.
