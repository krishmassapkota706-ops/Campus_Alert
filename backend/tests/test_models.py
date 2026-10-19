from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import EmergencyContact, Report, ReportCategory, Role, User, new_reference_id
from app.security.crypto import FieldCipher, derive_dev_key, get_cipher
from app.seed import DEMO_STUDENT_EMAIL, seed_demo_data


def make_user(db, email="jack@jacks.sdstate.edu", **kwargs):
    user = User(email=email, name=kwargs.pop("name", "Jack Rabbit"), **kwargs)
    user.set_password("correct horse battery")
    db.session.add(user)
    db.session.commit()
    return user


def test_password_is_hashed_and_checkable(db):
    user = make_user(db)
    assert "correct horse" not in user.password_hash
    assert user.check_password("correct horse battery")
    assert not user.check_password("wrong")


def test_user_defaults(db):
    user = make_user(db)
    assert user.role is Role.STUDENT
    assert not user.is_verified
    assert user.created_at.tzinfo is UTC


def test_email_is_unique(db):
    make_user(db)
    with pytest.raises(IntegrityError):
        make_user(db)


def test_deleting_user_deletes_contacts(db):
    user = make_user(db)
    user.contacts.append(EmergencyContact(name="Mom", phone="+16055550199"))
    db.session.commit()

    db.session.delete(user)
    db.session.commit()
    assert db.session.scalar(db.select(db.func.count()).select_from(EmergencyContact)) == 0


def test_user_to_dict_has_no_password_hash(db):
    assert "password_hash" not in make_user(db).to_dict()


def test_naive_datetimes_are_rejected(db):
    user = make_user(db)
    user.email_verified_at = datetime(2026, 10, 1)
    with pytest.raises(Exception, match="Naive datetimes"):
        db.session.commit()


def test_reference_ids_are_prefixed_and_readable():
    assert new_reference_id(ReportCategory.EMERGENCY).startswith("EMG-")
    ref = new_reference_id(ReportCategory.MAINTENANCE)
    assert ref.startswith("RPT-") and len(ref) == 10
    assert not set(ref[4:]) & set("01OI")


def test_cipher_round_trip_and_blind_index():
    cipher = FieldCipher(derive_dev_key("unit"), "hmac-key")
    token = cipher.encrypt("42")
    assert token != "42"
    assert cipher.decrypt(token) == "42"
    assert cipher.encrypt("42") != token  # randomised ciphertext
    assert cipher.blind_index("42") == cipher.blind_index("42")
    assert cipher.blind_index("42") != cipher.blind_index("43")


def test_cipher_rejects_wrong_key():
    token = FieldCipher(derive_dev_key("a"), "k").encrypt("42")
    with pytest.raises(ValueError):
        FieldCipher(derive_dev_key("b"), "k").decrypt(token)


def test_seed_is_idempotent_and_never_stores_plain_user_id(db):
    first = seed_demo_data()
    assert first == {"users": 2, "contacts": 1, "reports": 2}
    assert seed_demo_data() == {"users": 0, "contacts": 0, "reports": 0}

    student = db.session.scalar(db.select(User).filter_by(email=DEMO_STUDENT_EMAIL))
    reports = db.session.scalars(db.select(Report)).all()
    for report in reports:
        assert report.reporter_ref_enc != str(student.id)
        assert get_cipher().decrypt(report.reporter_ref_enc) == str(student.id)
