from invoice_intake.partners import (
    BY_ALIAS, BY_NAME, BY_REGISTRATION, UNMATCHED, match_partner,
)

# Mirrors the accounting API's partner master.
PARTNERS = [
    {"partner_code": "P-1001", "name": "株式会社山田製作所",
     "aliases": ["ヤマダ製作所", "山田製作所"], "registration_no": "T1010001000101"},
    {"partner_code": "P-1002", "name": "有限会社佐藤商店",
     "aliases": ["佐藤商店"], "registration_no": "T2020002000202"},
]


def test_match_by_registration_number_is_strongest():
    # Even with a messy name, the registration number resolves it.
    p, method = match_partner(PARTNERS, "山田せいさくしょ？", "T1010001000101")
    assert p["partner_code"] == "P-1001"
    assert method == BY_REGISTRATION


def test_match_by_exact_name():
    p, method = match_partner(PARTNERS, "有限会社佐藤商店", None)
    assert p["partner_code"] == "P-1002"
    assert method == BY_NAME


def test_match_by_alias():
    # invoice_06 prints the alias "ヤマダ製作所".
    p, method = match_partner(PARTNERS, "ヤマダ製作所", None)
    assert p["partner_code"] == "P-1001"
    assert method == BY_ALIAS


def test_unknown_supplier_is_unmatched():
    # invoice_10's supplier is not in the master.
    p, method = match_partner(PARTNERS, "新星ロジスティクス株式会社", "T9090009000909")
    assert p is None
    assert method == UNMATCHED
