"""Build the unsigned template without clauses 6.2 and 7.2 (pypdf only).

Run from any directory with `python scripts/build_framework_contract_variant.py`.
The source hash is locked: review the coordinates if the standard template changes.
Text-showing operations are removed, not covered by white rectangles. Page count,
unaffected pages and the signature area stay unchanged.
"""

import hashlib
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import FloatObject


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "static/documents/contrat_cadre_sous_traitance_template.pdf"
OUTPUT = SOURCE.with_name("contrat_cadre_sans_6_2_7_2_template.pdf")
SOURCE_SHA256 = "4ad1ba1f71880e320b33c732dd0fc5d3dd30caf4de4bd75e8b5398fae402cdc0"


def multiply(a, b):
    return [
        a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    ]


def edit_page(page, removed_ranges, moved_range, upward_shift):
    stream = page.get_contents()
    matrix = [1, 0, 0, 1, 0, 0]
    stack, operations = [], []
    remove_text = False
    removed = 0
    for operands, operator in stream.operations:
        if operator == b"q":
            stack.append(matrix[:])
        elif operator == b"Q":
            matrix = stack.pop()
        elif operator == b"cm":
            matrix = multiply([float(x) for x in operands], matrix)
        elif operator == b"BT":
            remove_text = False
        elif operator in {b"m", b"l"}:
            # Underlines belong to the moved headings and must follow them.
            top = float(page.mediabox.height) - (
                float(operands[0]) * matrix[1] + float(operands[1]) * matrix[3] + matrix[5]
            )
            if moved_range[0] <= top <= moved_range[1]:
                operands[1] = FloatObject(float(operands[1]) + upward_shift / matrix[3])
        elif operator == b"Tm":
            top = float(page.mediabox.height) - (
                float(operands[4]) * matrix[1] + float(operands[5]) * matrix[3] + matrix[5]
            )
            remove_text = any(start <= top <= end for start, end in removed_ranges)
            if moved_range[0] <= top <= moved_range[1]:
                assert matrix[1] == matrix[2] == 0 and matrix[3] != 0
                operands[5] = FloatObject(float(operands[5]) + upward_shift / matrix[3])
        elif operator in {b"Tj", b"TJ", b"'", b'"'} and remove_text:
            removed += 1
            continue
        operations.append((operands, operator))
    assert removed > 0 and not stack
    stream.operations = operations
    page.replace_contents(stream)


def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256, "Review the new source template first"
    reader = PdfReader(SOURCE)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    # 6.2 and the beginning of 7.2 are on page 7; 7.2 ends on page 8.
    edit_page(writer.pages[6], [(143, 204), (497, 721)], (238, 492), 95)
    edit_page(writer.pages[7], [(143, 274)], (279, 719), 136)
    packet = BytesIO()
    writer.write(packet)
    packet.seek(0)
    checked = PdfReader(packet)
    text = "\n".join(page.extract_text() or "" for page in checked.pages)
    assert "6.2 Le Sous" not in text
    assert "7.2 Cession" not in text
    assert "en autant d’exemplaires" not in text
    assert "Sous réserve du droit moral" not in text
    assert "7.1 Propriété" in text and "8. Intuitu personae" in text
    assert len(writer.pages) == 15
    writer.add_metadata({"/Title": "Contrat cadre - modèle sans les points 6.2 et 7.2"})
    with OUTPUT.open("wb") as destination:
        writer.write(destination)
    print(OUTPUT)


if __name__ == "__main__":
    main()
