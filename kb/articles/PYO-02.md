---
id: PYO-02
title: Payout failed, reversed or stuck in processing
category: payouts
updated: 2026-10-13
---
# Payout failed, reversed or stuck in processing

This article is for merchants whose payout did not reach the beneficiary. It explains each payout state, what the failure codes mean, and when to contact support.

## Payout states

- **queued**: your payout balance is too low. The payout is sent automatically once you top up, and is cancelled if it stays queued for 3 days.
- **pending**: waiting for approval in your approval workflow.
- **processing**: sent to the banking network and waiting for confirmation.
- **processed**: the transfer completed.
- **reversed**: the beneficiary bank returned the money after the payout was sent.
- **rejected**: the payout was rejected, for example by an approver in your approval workflow.
- **failed**: the payout could not be completed.

## Failure codes and what to do

| Code | Meaning | What to do |
|---|---|---|
| `INVALID_IFSC` | The IFSC does not match a valid bank branch. | Confirm the IFSC with the beneficiary and retry. |
| `ACCOUNT_CLOSED` | The beneficiary account is closed. | Ask the beneficiary for an active account. |
| `BENEFICIARY_BANK_DOWN` | The beneficiary's bank is unavailable. | Retry later or use another mode. |
| `NPCI_TIMEOUT` | The network did not respond in time. | Retry later. |
| `INSUFFICIENT_BALANCE` | Your payout balance is too low. | Top up your payout balance. |

Before retrying a failed payout, check that no earlier attempt for the same beneficiary was processed, so you do not pay twice.

## Reversed payouts

A payout is reversed when the beneficiary bank sends the money back. Common reasons are a closed account, an invalid account number, an IFSC mismatch, or a frozen account. Both the payout amount and the payout fee are credited back to your payout balance. Correct the beneficiary details, ideally validate the account first (see PYO-03), and send a new payout.

## Payout stuck in processing

Most payouts complete within the typical times in PYO-01. If a payout has been in `processing` for more than 24 hours, do not send a duplicate payout. Contact support with the payout ID and the UTR so the transfer can be traced with the bank.

## Still need help?

Email support@northwindpay.example with the payout ID (`pout_...`), the UTR if available, the failure code, and the beneficiary's bank name. See also: PYO-01, PYO-03.
