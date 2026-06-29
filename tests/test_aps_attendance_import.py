import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import aps_extract_students_from_text


APS_STUDENTS_TEXT = """
Liste stagiaires - APS JUILLET 2026
# Nom Prénom Email Téléphone
Dates de formation du 01/07/2026 au 31/07/2026
1 BONELLO Rafael r.bonello@orange.fr 07 62 10 00 43
2 CONTRERAS Sean sean.contreras067@gmail.com 07 75 75 92 79
3 FACQ Maxime maximesherco07@gmail.com 07 80 34 84 75
4 FELICHI Shmild shmild.felichi@example.fr 06 10 10 10 10
5 LASSOUAG Océane oceane.lassouag@example.fr 06 20 20 20 20
6 LAVAUX Jason jason.lavaux@example.fr 06 30 30 30 30
7 LAVIALLE Nael nael.lavialle@example.fr 06 40 40 40 40
8 MOLINARI Abdelkrim abdelkrim.molinari@example.fr 06 50 50 50 50
9 PLET Franck, Guy springer83600@gmail.com 06 11 86 50 49
10 SELEONE Leliano leliano.seleone@example.fr 06 60 60 60 60
11 SHUSHANYAN Suren suren.shushanyan@example.fr 06 70 70 70 70
12 YESSAD Rayan rayan.yessad@example.fr 06 80 80 80 80
13 ZAHER Hicham hicham.zaher@example.fr 06 90 90 90 90
https://example.test/trainees/print
Page 1 / 1
13 numéros trouvés
"""


def test_aps_attendance_pdf_text_parser_keeps_only_numbered_student_rows():
    students = aps_extract_students_from_text(APS_STUDENTS_TEXT)

    assert len(students) == 13
    assert [(student["lastName"], student["firstName"]) for student in students] == [
        ("BONELLO", "Rafael"),
        ("CONTRERAS", "Sean"),
        ("FACQ", "Maxime"),
        ("FELICHI", "Shmild"),
        ("LASSOUAG", "Océane"),
        ("LAVAUX", "Jason"),
        ("LAVIALLE", "Nael"),
        ("MOLINARI", "Abdelkrim"),
        ("PLET", "Franck, Guy"),
        ("SELEONE", "Leliano"),
        ("SHUSHANYAN", "Suren"),
        ("YESSAD", "Rayan"),
        ("ZAHER", "Hicham"),
    ]
    assert students[0] == {
        "lastName": "BONELLO",
        "firstName": "Rafael",
        "email": "r.bonello@orange.fr",
        "phone": "07 62 10 00 43",
    }
    assert students[8] == {
        "lastName": "PLET",
        "firstName": "Franck, Guy",
        "email": "springer83600@gmail.com",
        "phone": "06 11 86 50 49",
    }
    assert all(student["lastName"] != "TROUVÉS" for student in students)
