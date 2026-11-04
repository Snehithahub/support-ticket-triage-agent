---
id: PYO-03
title: Payout balance, queued payouts and payout fees
category: payouts
updated: 2026-10-14
---
# Payout balance, queued payouts and payout fees

This article is for merchants and finance teams managing Northwind Payouts. It explains how the payout balance works, what happens when it runs low, and what each payout costs.

## Your payout balance

Payouts are paid from your payout balance, which is separate from your payment settlement balance. Money you receive from customer payments settles to your bank account and does not automatically fund payouts. Keep enough in your payout balance to cover both the payout amounts and the payout fees.

## Queued payouts

If your payout balance is too low when you create a payout, the payout moves to `queued` instead of failing straight away.

- Queued payouts are processed automatically as soon as you top up the payout balance.
- Payouts that stay queued for 3 days are cancelled, and you need to create them again.
- A payout may also fail with `INSUFFICIENT_BALANCE`. See PYO-02 for failure codes.

To avoid delays, check your payout balance before large payout runs and top up in advance.

## Payout fees

| Mode | Fee per payout |
|---|---|
| IMPS and UPI, up to Rs 1,000 | Rs 3 |
| IMPS and UPI, above Rs 1,000 | Rs 5 |
| NEFT | Rs 3 |
| RTGS | Rs 10 |

All payout fees are charged plus GST at 18%. Fees are taken from your payout balance with each payout. If a payout is reversed by the beneficiary bank, both the amount and the payout fee are credited back to your payout balance.

## Account validation (penny drop)

Before the first payout to a new beneficiary, you can validate their bank account with a penny drop. Northwind Payouts sends Rs 1 to the account and returns the account holder name registered with the bank. Compare it with the name you expect before sending money.

- Fee: Rs 3 plus GST per validation.
- Validation catches wrong account numbers, IFSC mismatches and closed accounts early, which reduces reversed payouts.

## Still need help?

Email support@northwindpay.example with the payout ID (`pout_...`) and the date and amount of any top-up you made. See also: PYO-01, PYO-02.
