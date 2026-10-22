import json
import sys
from pathlib import Path

import pytest


SOLVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLVER_DIR))

import bin_packer


TEST03_DIR = Path(__file__).parent / "test03"
BOX = {
    "Reference": "TEST-BOX",
    "Width": 10,
    "Length": 10,
    "Depth": 10,
    "Active": True,
}
ITEM = {
    "ItemCode": "TEST-ITEM",
    "Width": 1,
    "Length": 1,
    "Depth": 1,
}


def write_json(tmp_path, data, name="input.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def test_combined_file_rejects_top_level_array(tmp_path, capsys):
    input_path = write_json(tmp_path, [])

    exit_code = bin_packer.main(["bin_packer.py", str(input_path)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "must be an object with 'boxes' and 'items' keys" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_combined_file_with_empty_boxes_reaches_packer(tmp_path, capsys):
    input_path = write_json(tmp_path, {"boxes": [], "items": [ITEM]})

    exit_code = bin_packer.main(["bin_packer.py", str(input_path)])
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert exit_code == 1
    assert result["success"] is False
    assert result["error"] == "No active box types were provided."
    assert captured.err == ""


@pytest.mark.parametrize("payload", [{"items": [ITEM]}, {"boxes": [BOX]}])
def test_combined_file_requires_boxes_and_items_keys(tmp_path, capsys, payload):
    input_path = write_json(tmp_path, payload)

    exit_code = bin_packer.main(["bin_packer.py", str(input_path)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.err == (
        "Combined JSON file must contain both a 'boxes' and an 'items' key.\n"
    )
    assert captured.out == ""


@pytest.mark.parametrize(
    ("boxes_key", "items_key"),
    [("boxes", "items"), ("Boxes", "Items"), ("box", "item"), ("Box", "Item")],
)
def test_combined_file_accepts_existing_key_variations(
    tmp_path, capsys, boxes_key, items_key
):
    input_path = write_json(
        tmp_path, {boxes_key: [BOX], items_key: [ITEM]}, name="combined.json"
    )

    exit_code = bin_packer.main(["bin_packer.py", str(input_path)])
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert exit_code == 0
    assert result["success"] is True
    assert captured.err == ""


def test_test03_works_as_combined_and_two_file_input(tmp_path, capsys):
    boxes_path = TEST03_DIR / "boxes.json"
    items_path = TEST03_DIR / "items.json"
    combined_path = write_json(
        tmp_path,
        {
            "boxes": json.loads(boxes_path.read_text()),
            "items": json.loads(items_path.read_text()),
        },
        name="combined.json",
    )

    combined_exit = bin_packer.main(["bin_packer.py", str(combined_path)])
    combined_output = capsys.readouterr()
    two_file_exit = bin_packer.main(
        ["bin_packer.py", str(boxes_path), str(items_path)]
    )
    two_file_output = capsys.readouterr()

    combined_result = json.loads(combined_output.out)
    assert combined_exit == two_file_exit
    assert combined_exit == (0 if combined_result["success"] else 1)
    assert combined_result["bins_used"] > 0
    assert combined_result == json.loads(two_file_output.out)
    assert combined_output.err == two_file_output.err == ""
