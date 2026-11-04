---
id: PAY-03
title: Improving your payment success rate
category: failed_payments
updated: 2026-07-21
---
# Improving your payment success rate

This article is for merchants who want fewer failed payments at checkout. It covers the settings and checkout choices that have the biggest effect on success rate, and how to monitor it.

## Enable retries on checkout

Many failures are temporary, such as a bank timeout or a mistyped OTP. When retries are enabled, a customer whose payment fails can try again immediately, with the same method or a different one, without restarting their order.

1. Go to your checkout settings in the Dashboard.
2. Turn on retries for failed payments.
3. Test the flow in test mode to confirm customers see a retry option after a failure.

## Offer faster payment methods

### UPI intent

With UPI intent, the customer taps a button and their UPI app opens with the payment details already filled in. This avoids two common failure causes:

- `INVALID_VPA`, because the customer does not have to type their UPI ID.
- `UPI_COLLECT_EXPIRED`, because the customer approves the payment straight away instead of switching apps to find a collect request that expires after 5 minutes.

Offer UPI intent on mobile checkouts, and keep UPI collect as a fallback where intent is not available.

### Saved cards

Saved cards let returning customers pay without re-entering card details. This reduces typing errors and drop-offs, especially on mobile. Make sure the customer can clearly see which saved card will be charged.

## Monitor the Payment Health page

The Payment Health page in the Dashboard shows how your payments are performing. Use it to:

- Track your overall success rate over time.
- Spot which payment methods or banks are failing more than usual.
- Tell the difference between a problem at a specific bank and a problem with your own integration.

If one bank is showing many `GATEWAY_TIMEOUT` errors, the issue is usually on the bank's side and recovers on its own. If failures rise across all methods, check your integration and recent changes.

## Other good practices

- Offer several payment methods so customers have a fallback.
- Show clear error messages that tell the customer what to do next.
- Review decline codes regularly to find patterns. See PAY-02.

## Still need help?

Contact support@northwindpay.example with a few example payment IDs (`pay_...`) and the time range when you noticed the drop in success rate. See also: PAY-02, PAY-04, PAY-05.
