from decimal import Decimal

from django.test import SimpleTestCase

from form137.utils import (
    BLANK_FORM137_SUBJECTS,
    build_printable_grade_blocks,
)


class Form137PrintLayoutTests(SimpleTestCase):
    def test_printable_blocks_are_padded_with_blank_reference_block(self):
        grade_blocks = [
            {
                "grade_level": object(),
                "school_year": object(),
                "section_name": "Amethyst",
                "adviser_name": "Teacher",
                "subject_rows": [],
                "general_average": Decimal("93"),
            },
            {
                "grade_level": object(),
                "school_year": object(),
                "section_name": "Jasper",
                "adviser_name": "Teacher",
                "subject_rows": [],
                "general_average": Decimal("94"),
            },
        ]

        print_blocks = build_printable_grade_blocks(grade_blocks)

        self.assertEqual(len(print_blocks), 3)
        self.assertFalse(print_blocks[0]["is_blank"])
        self.assertFalse(print_blocks[1]["is_blank"])
        self.assertTrue(print_blocks[2]["is_blank"])
        self.assertEqual(
            [row["subject_name"] for row in print_blocks[2]["subject_rows"]],
            BLANK_FORM137_SUBJECTS,
        )

    def test_printable_blocks_do_not_trim_existing_blocks(self):
        grade_blocks = [
            {
                "grade_level": object(),
                "school_year": object(),
                "section_name": f"Section {index}",
                "adviser_name": "Teacher",
                "subject_rows": [],
                "general_average": Decimal("90"),
            }
            for index in range(4)
        ]

        print_blocks = build_printable_grade_blocks(grade_blocks)

        self.assertEqual(len(print_blocks), 4)
        self.assertFalse(any(block["is_blank"] for block in print_blocks))

    def test_populated_blocks_keep_full_reference_subject_grid(self):
        grade_blocks = [
            {
                "grade_level": object(),
                "school_year": object(),
                "section_name": "Amethyst",
                "adviser_name": "Teacher",
                "subject_rows": [
                    {
                        "subject_name": "Filipino",
                        "is_mapeh": False,
                        "is_mapeh_sub": False,
                        "q1": Decimal("90"),
                        "q2": None,
                        "q3": None,
                        "q4": None,
                        "final_grade": Decimal("90"),
                        "remarks": "Passed",
                    },
                    {
                        "subject_name": "Araling Panlipunan",
                        "is_mapeh": False,
                        "is_mapeh_sub": False,
                        "q1": Decimal("92"),
                        "q2": None,
                        "q3": None,
                        "q4": None,
                        "final_grade": Decimal("92"),
                        "remarks": "Passed",
                    },
                ],
                "general_average": Decimal("91"),
            }
        ]

        print_blocks = build_printable_grade_blocks(grade_blocks, minimum_blocks=1)
        subject_names = [row["display_name"] for row in print_blocks[0]["subject_rows"]]
        araling_row = print_blocks[0]["subject_rows"][4]
        english_row = print_blocks[0]["subject_rows"][1]

        self.assertEqual(subject_names, BLANK_FORM137_SUBJECTS)
        self.assertEqual(araling_row["subject_name"], "Araling Panlipunan")
        self.assertEqual(araling_row["q1"], Decimal("92"))
        self.assertIsNone(english_row["q1"])
