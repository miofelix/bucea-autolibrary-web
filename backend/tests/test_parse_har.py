from app.scripts.parse_har import classify, redact_param_pairs, summarize_body


def test_redact_param_pairs_masks_account_and_secret_fields():
    redacted = redact_param_pairs(
        [
            {"name": "username", "value": "202400000000"},
            {"name": "password", "value": "secret"},
            {"name": "captchaId", "value": "captcha-id"},
            {"name": "answer", "value": "abcd"},
            {"name": "date", "value": "2026-05-26"},
        ]
    )

    values = {item["name"]: item["value"] for item in redacted}
    assert values["username"] == "***"
    assert values["password"] == "***"
    assert values["captchaId"] == "***"
    assert values["answer"] == "***"
    assert values["date"] == "2026-05-26"


def test_classify_known_library_endpoints():
    assert classify({"request": {"url": "https://host/seat/login"}}) == ["login"]
    assert classify({"request": {"url": "https://host/seat/auth/signIn"}}) == ["login"]
    assert classify({"request": {"url": "https://host/seat/auth/createCaptcha"}}) == ["captcha"]
    assert classify({"request": {"url": "https://host/seat/freeBook/ajaxGetRooms"}}) == ["room"]
    assert classify({"request": {"url": "https://host/seat/freeBook/ajaxSearch"}}) == ["seat"]
    assert classify({"request": {"url": "https://host/seat/freeBook/ajaxGetTime"}}) == ["seat_time"]
    assert classify({"request": {"url": "https://host/seat/selfRes"}}) == ["reserve"]


def test_classify_static_assets_separately():
    assert classify({"request": {"url": "https://host/seat/assets/app.js"}}) == ["static"]


def test_summarize_body_masks_cancel_record_id():
    summary = summarize_body(
        {
            "mimeType": "application/x-www-form-urlencoded",
            "params": [
                {"name": "SYNCHRONIZER_TOKEN", "value": "token"},
                {"name": "id", "value": "1231019"},
            ],
        },
        "/reservation/cancel",
    )

    values = {item["name"]: item["value"] for item in summary["params"]}
    assert values["SYNCHRONIZER_TOKEN"] == "***"
    assert values["id"] == "***"
