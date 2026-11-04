---
id: PAY-01
title: Customer was charged but the payment failed
category: failed_payments
updated: 2026-08-12
---
# Customer was charged but the payment failed

This article is for merchants whose customer says money was debited from their account, but the payment shows as `failed` in the Dashboard. It explains why this happens, when the customer gets the money back, and what you should tell them.

## Why this happens

Sometimes a customer's bank debits the amount but the confirmation never reaches Northwind Pay, or arrives after the payment has already been marked as failed. This can happen because of a bank timeout, a dropped connection during authentication, or a delay at the customer's bank. In these cases, Northwind Pay never received the money and the payment stays `failed`. You will not be settled for it.

Before you respond, check the payment's state. If it shows `pending`, wait: payments can stay pending for up to 30 minutes (UPI up to 2 hours) before they move to `captured` or `failed`. See PAY-05.

## When the customer gets the money back

If the payment is `failed` and the customer was debited, the customer's bank automatically reverses the amount within 5-7 business days. Merchants cannot speed up this reversal, and Northwind Pay cannot trigger it on the bank's behalf.

Do not issue a refund for a failed payment. There is nothing to refund, because the payment was never captured.

## What to share with the customer

1. Open the payment in **Transactions > Payments** using the payment ID (`pay_...`) or order ID.
2. Note the bank reference number:
   - **RRN** for UPI payments.
   - **ARN** for card payments.
3. Tell the customer the payment failed, that their bank will reverse the debit automatically within 5-7 business days, and give them the reference number.

If the customer has not received the reversal after 5-7 business days, they should contact their bank and quote the RRN or ARN. The bank can trace the debit using that reference.

## Avoiding duplicate charges

If the customer retries and the second payment succeeds, they may briefly see two debits. The failed one will still be reversed by their bank. Let them know so they do not raise a dispute for the reversed amount.

## Still need help?

Contact support@northwindpay.example with the payment ID (`pay_...`), the RRN or ARN, and the date and amount of the debit. See also: PAY-02, PAY-04, PAY-05.
