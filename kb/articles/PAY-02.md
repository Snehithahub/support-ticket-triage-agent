---
id: PAY-02
title: Understanding payment decline codes
category: failed_payments
updated: 2026-08-05
---
# Understanding payment decline codes

This article is for merchants and developers who see a failed payment and want to know why it was declined. It lists the most common decline codes and what you or your customer can do about each one.

## Where to find the decline code

You can see the reason a payment failed in two places:

- In the Dashboard, open **Transactions > Payments**, select the payment (`pay_...`), and check the error details.
- In the API response or the `payment.failed` webhook event, which includes the error code.

## Common decline codes

| Code | Meaning | What to do |
|---|---|---|
| `BAD_REQUEST_CARD_DECLINED` | The card issuer declined the payment. | Ask the customer to contact their bank or use another card or method. |
| `INSUFFICIENT_FUNDS` | The account or card did not have enough balance. | Ask the customer to use another payment method or add funds. |
| `AUTHENTICATION_FAILED` | The OTP or 3DS check failed. | Ask the customer to retry and complete the OTP or 3DS step carefully. |
| `GATEWAY_TIMEOUT` | The customer's bank did not respond in time. | Ask the customer to retry after a short while, or use another method. |
| `UPI_COLLECT_EXPIRED` | The customer did not approve the UPI collect request within 5 minutes. | Ask the customer to retry and approve promptly in their UPI app. |
| `INVALID_VPA` | The UPI ID (VPA) entered does not exist or is mistyped. | Ask the customer to check and re-enter their UPI ID. |

## Which declines you can act on

Most declines are decided by the customer's bank, not by Northwind Pay or by you. You cannot override an issuer decline. What you can do:

- Show a clear message at checkout so the customer knows to retry or switch methods.
- Offer several payment methods so a customer whose card is declined can pay by UPI or netbanking instead.
- Enable retries on checkout so customers do not have to start over.

If you see a sudden rise in one code, such as `GATEWAY_TIMEOUT`, check the Payment Health page in the Dashboard. It can indicate a problem at a particular bank rather than with your integration.

## If the customer was debited

A declined payment should not result in a charge. If the customer says they were debited, see PAY-01. The bank reverses such debits automatically within 5-7 business days.

## Still need help?

Email support@northwindpay.example with the payment ID (`pay_...`), the decline code, and the time of the attempt. See also: PAY-01, PAY-03, PAY-04.
