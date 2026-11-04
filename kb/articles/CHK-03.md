---
id: CHK-03
title: Creating and managing Payment Links
category: checkout
updated: 2026-10-02
---
# Creating and managing Payment Links

This article is for merchants who want to collect payments without building a checkout page. It explains how to create Payment Links, what each link state means, and how expiry and partial payments work.

## Create a payment link

You can create links from the Dashboard or the API.

**From the Dashboard:**

1. Log in to dashboard.northwindpay.example.
2. Go to **Dashboard > Payment Links** and choose to create a new link.
3. Enter the amount, a description, and the customer's contact details.
4. Choose the expiry and whether partial payments are allowed.
5. Send the link to the customer by SMS or email.

**From the API:** call `POST /v1/payment_links` with the same details. This is useful when you send links in bulk or from your own billing system.

## Link states

| State | Meaning |
|---|---|
| created | The link is active and waiting for payment. |
| partially_paid | The customer has paid part of the amount. |
| paid | The full amount has been paid. |
| expired | The expiry date passed before full payment. |
| cancelled | You cancelled the link. |

A paid link cannot be reused. Create a new link for each new payment you want to collect.

## Expiry and partial payments

- **Expiry**: links expire after 30 days by default. You can set a longer expiry of up to 180 days when you create the link.
- **Partial payments**: you can allow partial payments on individual links. The link stays `partially_paid` until the full amount is collected, then moves to `paid`.
- **Cancelling**: cancel a link if the customer no longer needs to pay, for example after an order change. Cancelled and expired links cannot accept payments.

Payments made through a link appear in your payments list with their own payment ID and settle on the normal cycle. Subscribe to the `order.paid` and `payment.captured` webhooks if your systems need to know when a link is paid.

## Still need help?

Email support@northwindpay.example with the payment link details, the link state, and any payment ID (`pay_...`) the customer received. See also: CHK-01, WHK-04, SET-01.
