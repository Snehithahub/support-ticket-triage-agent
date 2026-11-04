---
id: DSP-04
title: Reducing chargebacks
category: disputes
updated: 2026-07-29
---
# Reducing chargebacks

This article gives practical steps to prevent disputes and keep your chargeback rate low.

## Why your chargeback rate matters

Each lost chargeback costs you the disputed amount plus a fee of Rs 500 plus GST. Beyond the direct cost, accounts with a chargeback rate above 1% of monthly transactions are placed under a risk review, which can put your settlements on hold. Risk reviews usually complete in 3-5 business days.

Track your dispute count against your monthly transaction volume in the Dashboard so you can act well before you reach that threshold.

## Prevent disputes before they start

- **Be recognizable**: customers often dispute charges they do not recognize. Use your brand name consistently on your website, checkout, receipts, and emails.
- **Show clear policies**: display your refund and cancellation policy at checkout, and keep your terms and contact details easy to find.
- **Describe products accurately**: set honest expectations about what the customer receives and when.
- **Send confirmations**: email an order confirmation and invoice right after payment, and share tracking details once the order ships.
- **Use 3DS authentication**: authenticated card payments give you stronger evidence if a fraud dispute is raised.

## Make refunds easier than disputes

Many chargebacks come from customers who could not reach the merchant. Respond to support requests quickly and refund promptly when a complaint is valid. A normal refund has no Northwind Pay fee, so it usually costs far less than a lost dispute. You can refund within 180 days of capture from Dashboard > Transactions > Payments.

After refunding, share the ARN with the customer so they can confirm the credit with their bank instead of raising a dispute.

## Handle the disputes you do receive

1. Subscribe to the `dispute.created` webhook so you hear about disputes immediately.
2. Respond within 7 calendar days with relevant evidence, such as proof of delivery, invoices, and customer communication.
3. Review each dispute's reason and fix the underlying issue, such as a confusing product page or slow delivery.
4. Watch for patterns, such as repeated disputes from the same device or IP address, which can point to fraud.

## Still need help?

Contact support@northwindpay.example with recent dispute IDs (`disp_...`) and any patterns you have noticed. See also: DSP-01, DSP-02, PAY-03.
