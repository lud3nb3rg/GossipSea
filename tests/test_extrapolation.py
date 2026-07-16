from extrapolation import COMMON_EMAIL_DOMAINS, generate_emails, generate_usernames


def test_generate_usernames_produces_common_variants():
    usernames = generate_usernames("Jean", "Dupont")

    assert "jeandupont" in usernames
    assert "jean.dupont" in usernames
    assert "jean_dupont" in usernames
    assert "jean-dupont" in usernames
    assert "dupontjean" in usernames
    assert "jdupont" in usernames
    assert "jeand" in usernames


def test_generate_usernames_strips_accents_and_lowercases():
    usernames = generate_usernames("Éric", "Dûpont")

    assert "ericdupont" in usernames
    assert all(u == u.lower() for u in usernames)


def test_generate_usernames_adds_birth_year_variants():
    usernames = generate_usernames("Jean", "Dupont", birth_date="1990-05-14")

    assert "jeandupont1990" in usernames
    assert "jeandupont90" in usernames


def test_generate_usernames_dedupes_preserving_order():
    usernames = generate_usernames("Jean", "Dupont")

    assert len(usernames) == len(set(usernames))


def test_generate_usernames_without_names_returns_empty():
    assert generate_usernames("", "Dupont") == []
    assert generate_usernames("Jean", "") == []


def test_generate_emails_covers_every_common_domain():
    emails = generate_emails("jdupont")

    assert len(emails) == len(COMMON_EMAIL_DOMAINS)
    assert "jdupont@gmail.com" in emails
    assert "jdupont@orange.fr" in emails
    assert all(email.startswith("jdupont@") for email in emails)
