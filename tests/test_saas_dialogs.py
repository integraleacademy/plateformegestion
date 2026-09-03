from pathlib import Path


def test_confirmed_saas_dialog_submits_without_replaying_inline_confirmation():
    source = (
        Path(__file__).resolve().parents[1] / "static" / "js" / "saas-dialogs.js"
    ).read_text(encoding="utf-8")

    assert "HTMLFormElement.prototype.submit.call(form);" in source
    assert "form.requestSubmit()" not in source
