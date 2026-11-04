---
id: DSP-02
title: Responding to a dispute with evidence
category: disputes
updated: 2026-07-22
---
# Responding to a dispute with evidence

This article explains how to contest a dispute, what evidence to submit, and what happens after you respond.

## Your response deadline

You must respond within 7 calendar days from the dispute notification. Calendar days include weekends and holidays. If you do not respond in time, the dispute is automatically accepted and treated as lost: the disputed amount is not returned and the chargeback fee applies.

Subscribe to the `dispute.created` webhook or check Dashboard > Disputes regularly so you can start gathering evidence the same day.

## Evidence that helps

Choose evidence that directly answers the customer's reason for the dispute. Useful evidence includes:

- **Proof of delivery or service usage**: courier tracking with delivery confirmation, signed delivery receipts, or login and usage history for digital services.
- **Invoice**: the invoice or receipt for the payment, showing items, amount, and customer details.
- **Customer communication**: emails, chat transcripts, or support tickets showing the customer received the product or agreed to the charge.
- **Refund and cancellation policy**: proof that your policy was shown at checkout, such as a screenshot of the checkout page.
- **IP, device, and 3DS details**: the customer's IP address and device information, and confirmation that 3DS authentication was completed.

Make sure files are clear and legible, and add a short note explaining how each document supports your case.

## How to submit evidence

1. Go to Dashboard > Disputes and open the dispute.
2. Review the reason given by the bank and the disputed amount.
3. Click Submit evidence.
4. Upload your documents and write a brief explanation.
5. Review and submit before the deadline.

You can also submit evidence through the API. If the customer's claim is valid, for example the order was never shipped, accepting the dispute may be the better choice. See DSP-03.

## After you submit

The bank typically takes 45-75 days after evidence submission to reach a decision, and this cannot be sped up. If you win, the held amount is released with your next settlement. If you lose, the amount is not returned and a fee of Rs 500 plus GST is charged. The bank may also escalate the case to pre-arbitration.

## Still need help?

Email support@northwindpay.example with the dispute ID (`disp_...`), the payment ID (`pay_...`), and a list of the evidence you have. See also: DSP-01, DSP-03, DSP-04.
