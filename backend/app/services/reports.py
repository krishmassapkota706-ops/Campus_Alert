"""Report submission and retrieval.

The reporter is never stored in plain text: see ``app/security/crypto.py``.
Students find their own reports through the blind index; only maintainers can
decrypt who filed a report.
"""

from sqlalchemy.exc import IntegrityError

from ..errors import NotFound
from ..extensions import db
from ..models import Report, ReportCategory, ReportStatus, User, new_reference_id
from ..security.crypto import get_cipher

_REFERENCE_RETRIES = 5


def _reporter_index(user: User) -> str:
    return get_cipher().blind_index(str(user.id))


def submit_report(user: User, category: ReportCategory, location: str, details: str) -> Report:
    """Save a report. Returns only after the row is committed (no false confirmations)."""
    cipher = get_cipher()
    for attempt in range(_REFERENCE_RETRIES):
        report = Report(
            reference_id=new_reference_id(category),
            category=category,
            location_text=location,
            details=details,
            reporter_ref_enc=cipher.encrypt(str(user.id)),
            reporter_ref_idx=_reporter_index(user),
        )
        db.session.add(report)
        try:
            db.session.commit()
            return report
        except IntegrityError:  # reference ID collision; extremely unlikely
            db.session.rollback()
            if attempt == _REFERENCE_RETRIES - 1:
                raise
    raise AssertionError("unreachable")


def _paginate(query, page: int, per_page: int) -> tuple[list[Report], int]:
    total = db.session.scalar(db.select(db.func.count()).select_from(query.subquery()))
    rows = db.session.scalars(
        query.order_by(Report.created_at.desc(), Report.id.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    ).all()
    return list(rows), total


def list_own_reports(
    user: User, page: int, per_page: int, category: ReportCategory | None = None
) -> tuple[list[Report], int]:
    query = db.select(Report).filter_by(reporter_ref_idx=_reporter_index(user))
    if category:
        query = query.filter_by(category=category)
    return _paginate(query, page, per_page)


def get_own_report(user: User, reference_id: str) -> Report:
    report = db.session.scalar(
        db.select(Report).filter_by(
            reference_id=reference_id.upper(), reporter_ref_idx=_reporter_index(user)
        )
    )
    if report is None:
        raise NotFound("Report not found.")
    return report


# ---- Maintainer views ----


def list_all_reports(
    page: int,
    per_page: int,
    category: ReportCategory | None = None,
    status: ReportStatus | None = None,
) -> tuple[list[Report], int]:
    query = db.select(Report)
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)
    return _paginate(query, page, per_page)


def get_report(reference_id: str) -> Report:
    report = db.session.scalar(db.select(Report).filter_by(reference_id=reference_id.upper()))
    if report is None:
        raise NotFound("Report not found.")
    return report


def set_status(report: Report, status: ReportStatus) -> Report:
    report.status = status
    db.session.commit()
    return report


def reporter_of(report: Report) -> dict | None:
    """Decrypt the reporter for a maintainer. ``None`` if the account no longer exists."""
    user_id = int(get_cipher().decrypt(report.reporter_ref_enc))
    user = db.session.get(User, user_id)
    if user is None:
        return None
    return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone}
