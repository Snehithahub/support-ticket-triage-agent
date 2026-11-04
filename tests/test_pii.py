import pytest

from triagedesk.normalize import detect_language, normalize_ticket, strip_quoted_and_signature
from triagedesk.pii import luhn_ok, mask_pii


@pytest.mark.parametrize(
    "text,kind",
    [
        ("mail priya.sharma@kurtakraft.in now", "EMAIL"),
        ("call +91 98765 43210", "PHONE"),
        ("call 9876543210", "PHONE"),
        ("card 4111 1111 1111 1111 failed", "CARD"),
        ("PAN ABCDE1234F", "PAN"),
        ("aadhaar 2345 6789 0124", "AADHAAR"),
        ("pay to rahul@okbharat", "UPI_ID"),
        ("account 123456789012345", "ACCOUNT_NUMBER"),
        ("my password: hunter2, help", "SECRET"),
    ],
)
def test_masks_each_pii_type(text, kind):
    res = mask_pii(text)
    assert kind in res.found
    assert f"[{kind}_1]" in res.text


def test_keeps_gateway_ids_amounts_and_non_luhn_numbers():
    text = "pay_N3x9QbV2kL7mTz rfnd_9Hk2 setl_X1 amount 150000 order 1234567812345678"
    res = mask_pii(text)
    assert "pay_N3x9QbV2kL7mTz" in res.text and "rfnd_9Hk2" in res.text and "150000" in res.text
    assert "CARD" not in res.found  # 1234567812345678 fails Luhn


def test_upi_rrn_and_utr_are_not_masked():
    # 12-digit RRNs look like Aadhaar numbers and account numbers; support needs them.
    for text in ("RRN 412345678901 for the UPI payment", "UTR 234567890124 settled", "ref 2345 6789 0123"):
        assert mask_pii(text).text == text


def test_aadhaar_needs_checksum_and_context_or_spacing():
    assert "AADHAAR" in mask_pii("my aadhaar is 234567890124").found  # context word, valid checksum
    assert "AADHAAR" not in mask_pii("my aadhaar is 234567890123").found  # bad Verhoeff checksum
    assert "AADHAAR" in mask_pii("id 2345 6789 0124").found  # printed 4-4-4 format


def test_secret_mask_keeps_punctuation():
    assert mask_pii("password: hunter2, thanks").text == "password: [SECRET_1], thanks"


def test_luhn():
    assert luhn_ok("4111111111111111") and not luhn_ok("4111111111111112")


def test_strip_quoted_reply_and_signature():
    body = (
        "Settlement not received for 3 days.\n\nRegards,\nPriya Sharma\nOps Lead\n\n"
        "On Mon, 3 Nov 2026 at 10:02, Northwind Pay Support <support@northwindpay.example> wrote:\n"
        "> Please share the settlement id"
    )
    assert strip_quoted_and_signature(body) == "Settlement not received for 3 days."


def test_strip_gt_quotes_and_mobile_footer():
    assert strip_quoted_and_signature("Hi\n> old\nNew text\nSent from my iPhone") == "Hi\nNew text"


def test_language_detection():
    assert detect_language("bhai settlement abhi tak nahi aaya, 3 din ho gaye") == "hinglish"
    assert detect_language("Our webhook endpoint returns 500 and events are not delivered.") == "en"
    assert detect_language("Bonjour, je voudrais savoir pourquoi mon paiement a été refusé par la banque.") == "fr"


def test_normalize_ticket_masks_and_records_types():
    n = normalize_ticket("Refund", "Customer rahul@example.com was charged twice\n\nThanks,\nRavi\n9876543210")
    assert "[EMAIL_1]" in n.masked_text and "9876543210" not in n.clean_text
    assert n.pii_types == ["EMAIL"]
