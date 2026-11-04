---
id: REF-04
title: Instant refunds
category: refunds
updated: 2026-08-27
---
# Instant refunds

This article is for merchants who want refunds to reach customers within minutes instead of days. It covers what instant refunds are, which payments are eligible, what they cost, and how to use them.

## What instant refunds are

A normal refund takes between 1 and 7 business days to reach the customer, depending on the payment method. An instant refund is credited to the customer within 30 minutes. Instant refunds are useful for order cancellations, failed deliveries, or any situation where a quick resolution improves the customer experience and reduces support contacts.

## Eligibility

Instant refunds are available for:

- Payments made by UPI.
- Payments made by supported cards.

Payments made through other methods, such as netbanking or wallets, are refunded on the normal timeline. The usual refund rules still apply: the payment must be captured, the refund must be created within 180 days of capture, and the total refunded cannot exceed the captured amount.

## Fees

Normal refunds have no Northwind Pay fee. Instant refunds are charged:

- 0.5% of the refund amount, with a minimum of Rs 5 per refund.
- GST on that fee.

For small refunds where 0.5% works out to less than Rs 5, the Rs 5 minimum applies instead. The original transaction fee on the payment is not returned in either case. Instant refund fees appear as other charges on your monthly invoice.

## How to issue an instant refund

1. Go to **Transactions > Payments** in the Dashboard and open the captured payment.
2. Click **Refund** and enter the full or partial amount.
3. Select the instant refund option if it is shown for this payment. If it is not shown, the payment method is not eligible.
4. Confirm the refund and note the refund ID (`rfnd_...`).

You can also request an instant refund through `POST /v1/payments/{id}/refunds` by specifying the instant speed option in the request. As with any refund, your balance must be enough to cover it.

## Still need help?

Email support@northwindpay.example with the payment ID (`pay_...`) and refund ID (`rfnd_...`), and say whether you selected the instant option. See also: REF-01, REF-02, REF-05.
