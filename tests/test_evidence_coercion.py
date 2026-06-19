from model_processing.evidence_coercion import coerce_center_x, coerce_int, coerce_non_negative_int, coerce_request_sub_index


def test_coerce_int_accepts_only_signed_integer_evidence():
    assert coerce_int(0) == 0
    assert coerce_int(-1) == -1
    assert coerce_int(" 12 ") == 12
    assert coerce_int("-12") == -12
    assert coerce_int("001") == 1

    assert coerce_int(None) is None
    assert coerce_int(True) is None
    assert coerce_int(False) is None
    assert coerce_int(1.0) is None
    assert coerce_int(1.5) is None
    assert coerce_int("1.0") is None
    assert coerce_int("-") is None


def test_coerce_non_negative_int_accepts_only_integer_evidence():
    assert coerce_non_negative_int(0) == 0
    assert coerce_non_negative_int(127) == 127
    assert coerce_non_negative_int(" 12 ") == 12
    assert coerce_non_negative_int("001") == 1

    assert coerce_non_negative_int(None) is None
    assert coerce_non_negative_int(True) is None
    assert coerce_non_negative_int(False) is None
    assert coerce_non_negative_int(-1) is None
    assert coerce_non_negative_int(1.0) is None
    assert coerce_non_negative_int("1.0") is None
    assert coerce_non_negative_int("-1") is None


def test_coerce_request_sub_index_accepts_deleted_sentinel():
    assert coerce_request_sub_index(None) is None
    assert coerce_request_sub_index(-1) == -1
    assert coerce_request_sub_index("-1") == -1
    assert coerce_request_sub_index(0) == 0
    assert coerce_request_sub_index(" 12 ") == 12

    assert coerce_request_sub_index(True) is None
    assert coerce_request_sub_index(-2) is None
    assert coerce_request_sub_index(1.5) is None
    assert coerce_request_sub_index("1.0") is None
    assert coerce_request_sub_index("bad") is None


def test_coerce_center_x_accepts_finite_numeric_first_coordinate():
    assert coerce_center_x([0.00001, 1.0, 2.0]) == 0.0
    assert coerce_center_x(["3.125", 0.0, 0.0]) == 3.125

    assert coerce_center_x(None) is None
    assert coerce_center_x([]) is None
    assert coerce_center_x(["bad"]) is None
    assert coerce_center_x([float("inf")]) is None
    assert coerce_center_x([float("nan")]) is None
