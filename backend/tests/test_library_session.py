from app.library.csrf import CsrfBundle
from app.library.session import LibrarySession


def test_with_login_returns_new_instance_with_cookies_set() -> None:
    base = LibrarySession(library_user_id=1)
    csrf = CsrfBundle(token="tok", uri="/self", authid="-1")

    updated = base.with_login(
        cookies={"JSESSIONID": "abcdef"},
        sys_username="202404020113",
        sys_token="syst",
        csrf=csrf,
        user_info={"userCheckedIn": False},
    )

    assert base.cookies == {}
    assert base.logged_in is False
    assert updated.cookies == {"JSESSIONID": "abcdef"}
    assert updated.logged_in is True
    assert updated.csrf == csrf
    assert updated.user_info == {"userCheckedIn": False}


def test_cleared_drops_all_session_state() -> None:
    session = LibrarySession(
        library_user_id=7,
        sys_username="x",
        sys_token="y",
        csrf=CsrfBundle(token="a", uri="/self", authid="-1"),
        cookies={"a": "b"},
        logged_in=True,
    )
    cleared = session.cleared()
    assert cleared.library_user_id == 7
    assert cleared.cookies == {}
    assert cleared.logged_in is False
    assert cleared.csrf is None


def test_with_csrf_returns_new_instance() -> None:
    session = LibrarySession(library_user_id=1)
    bundle = CsrfBundle(token="t", uri="/self", authid="-1")
    new = session.with_csrf(bundle)
    assert session.csrf is None
    assert new.csrf == bundle
