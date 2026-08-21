"""Generate ground-truth extraction fixtures for the 12 sample invoices.

These fixtures represent what a correct LLM extraction should return (the raw,
pre-normalization shape: tax_rate as an integer percent). They power:
  * offline mode (replay extraction without an LLM / API key), and
  * unit tests for normalize / verify / partner-matching.

Run:  python3 tests/fixtures/_generate.py
"""
import json
import pathlib

HERE = pathlib.Path(__file__).parent


def line(desc, qty, unit, price, amount, rate):
    return {
        "description": desc,
        "quantity": qty,
        "unit": unit,
        "unit_price": price,
        "amount": amount,
        "tax_rate": rate,
    }


def invoice(**kw):
    kw.setdefault("currency", "JPY")
    kw.setdefault("confidence", 0.97)
    kw.setdefault("notes", "")
    return kw


FIXTURES = {}

FIXTURES["invoice_01"] = invoice(
    invoice_number="YM-2026-0107", issue_date="2026-01-07", due_date="2026-02-28",
    supplier_name="株式会社山田製作所", supplier_registration_no="T1010001000101",
    lines=[
        line("精密部品A-100", 120, "個", 1250, 150000, 10),
        line("精密部品B-220", 40, "個", 3400, 136000, 10),
        line("梱包・輸送費", None, "式", None, 18000, 10),
    ],
    subtotal=304000, tax_amount=30400, total_amount=334400,
)

# 26-line, two-page invoice. qty 6..31, unit_price 930 stepping +130.
_l2 = []
for i in range(26):
    qty = 6 + i
    price = 930 + 130 * i
    _l2.append(line(f"治具部材 No.{i + 1:03d}", qty, "個", price, qty * price, 10))
FIXTURES["invoice_02"] = invoice(
    invoice_number="OSK-26-0112", issue_date="2026-01-12", due_date="2026-02-20",
    supplier_name="大阪機械工業株式会社", supplier_registration_no="T4040004000404",
    lines=_l2, subtotal=1419080, tax_amount=141908, total_amount=1560988,
    notes="Two-page PDF; 26 line items.",
)

FIXTURES["invoice_03"] = invoice(
    invoice_number="TF-2026-0115", issue_date="2026-01-15", due_date="2026-02-15",
    supplier_name="東京フーズ株式会社", supplier_registration_no="T3030003000303",
    lines=[
        line("業務用コーヒー豆 1kg", 24, "袋", 2800, 67200, 8),
        line("紙コップ 100個入", 30, "個", 1200, 36000, 10),
        line("ミネラルウォーター 2L", 48, "本", 180, 8640, 8),
        line("配送手数料", None, "式", None, 3500, 10),
    ],
    subtotal=115340, tax_amount=10017, total_amount=125357,
    notes="Mixed tax rates (8% and 10%).",
)

FIXTURES["invoice_04"] = invoice(
    invoice_number="SATO-260118", issue_date="2026-01-18", due_date="2026-03-31",
    supplier_name="有限会社佐藤商店", supplier_registration_no="T2020002000202",
    lines=[
        line("事務用品セット", 15, "セット", 4800, 72000, 10),
        line("コピー用紙 A4", 60, "箱", 2450, 147000, 10),
    ],
    subtotal=219000, tax_amount=21900, total_amount=240900,
    notes="Handwritten '受領 1/20 経理' received stamp (ignored).",
)

FIXTURES["invoice_05"] = invoice(
    invoice_number="MIT-2026-011", issue_date="2026-01-20", due_date="2026-02-28",
    supplier_name="みらいITソリューションズ株式会社", supplier_registration_no="T5050005000505",
    lines=[
        line("基幹システム保守 (1月分)", None, "式", None, 280000, 10),
        line("障害対応 (時間外)", 6, "時間", 12000, 72000, 10),
        line("VPN回線利用料", None, "式", None, 45000, 10),
    ],
    subtotal=397000, tax_amount=39700, total_amount=436700,
)

FIXTURES["invoice_06"] = invoice(
    invoice_number="YM-2026-0122", issue_date="2026-01-22", due_date="2026-02-28",
    supplier_name="ヤマダ製作所", supplier_registration_no="T1010001000101",
    lines=[
        line("表面処理加工", 200, "個", 340, 68000, 10),
        line("特急対応費", None, "式", None, 25000, 10),
    ],
    subtotal=93000, tax_amount=9300, total_amount=102300,
    notes="Supplier printed as alias 'ヤマダ製作所' (master name is 株式会社山田製作所).",
)

FIXTURES["invoice_07"] = invoice(
    invoice_number="YM-2026-0107", issue_date="2026-01-07", due_date="2026-02-28",
    supplier_name="株式会社山田製作所", supplier_registration_no="T1010001000101",
    lines=[
        line("精密部品A-100", 120, "個", 1250, 150000, 10),
        line("精密部品B-220", 40, "個", 3400, 136000, 10),
        line("梱包・輸送費", None, "式", None, 18000, 10),
    ],
    subtotal=304000, tax_amount=30400, total_amount=334400,
    notes="Scanned copy of the same invoice as invoice_01 (duplicate).",
)

FIXTURES["invoice_08"] = invoice(
    invoice_number="TF-2026-0125", issue_date="2026-01-25", due_date="2026-02-25",
    supplier_name="東京フーズ株式会社", supplier_registration_no="T3030003000303",
    lines=[
        line("冷凍食材セット", 12, "箱", 8600, 103200, 8),
        line("保冷配送料", None, "式", None, 6800, 10),
    ],
    subtotal=110000, tax_amount=8936, total_amount=118936,
    notes="Mixed tax; red handwritten note altering the bank account number (ignored).",
)

FIXTURES["invoice_09"] = invoice(
    invoice_number="OSK-26-0128", issue_date="2026-01-28", due_date="2026-02-20",
    supplier_name="大阪機械工業株式会社", supplier_registration_no="T4040004000404",
    lines=[
        line("シャフト加工", 37, "個", 2733, 101121, 10),
        line("熱処理", 37, "個", 891, 32967, 10),
    ],
    subtotal=134088, tax_amount=13408, total_amount=147497,
    notes="Image-only PDF (no text layer); non-round unit prices.",
)

FIXTURES["invoice_10"] = invoice(
    invoice_number="SSL-2026-0203", issue_date="2026-02-03", due_date="2026-03-31",
    supplier_name="新星ロジスティクス株式会社", supplier_registration_no="T9090009000909",
    lines=[
        line("倉庫保管料 (1月分)", None, "式", None, 120000, 10),
        line("入出庫作業", 340, "件", 220, 74800, 10),
    ],
    subtotal=194800, tax_amount=19480, total_amount=214280,
    notes="Supplier is NOT in the partner master -> cannot be auto-registered.",
)

FIXTURES["invoice_11"] = invoice(
    invoice_number="SATO-260205", issue_date="2026-02-05", due_date="2026-03-31",
    supplier_name="有限会社佐藤商店", supplier_registration_no="T2020002000202",
    lines=[
        line("清掃用品一式", None, "式", None, 34500, 10),
        line("トイレットペーパー", 40, "箱", 1980, 79200, 10),
    ],
    subtotal=113700, tax_amount=11370, total_amount=125070,
    notes="Dates printed in Reiwa era (令和8年 = 2026).",
)

FIXTURES["invoice_12"] = invoice(
    invoice_number="MIT-2026-014", issue_date="2026-02-10", due_date="2026-03-31",
    supplier_name="みらいITソリューションズ株式会社", supplier_registration_no="T5050005000505",
    lines=[
        line("業務システム改修", None, "式", None, 450000, 10),
        line("追加ライセンス", 5, "本", 24000, 120000, 10),
        line("値引き", None, "式", None, -30000, 10),
    ],
    subtotal=540000, tax_amount=54000, total_amount=594000,
    notes="Negative discount line (△30,000).",
)


def main():
    for name, data in FIXTURES.items():
        (HERE / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"Wrote {len(FIXTURES)} fixtures to {HERE}")


if __name__ == "__main__":
    main()
