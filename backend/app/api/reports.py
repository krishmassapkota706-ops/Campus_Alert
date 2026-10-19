"""Reports: ``/api/v1/reports`` (students) and ``/api/v1/admin/reports`` (maintainers)."""

from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from pydantic import Field

from ..errors import ValidationError
from ..models import ReportCategory, ReportStatus, Role
from ..security.auth import role_required
from ..services import reports as service
from ..validation import Schema, parse_body

bp = Blueprint("reports", __name__, url_prefix="/reports")
admin_bp = Blueprint("admin_reports", __name__, url_prefix="/admin/reports")

MAX_PER_PAGE = 100


class ReportBody(Schema):
    category: ReportCategory
    location: str = Field(min_length=1, max_length=200)
    details: str = Field(min_length=1, max_length=1000)


class StatusBody(Schema):
    status: ReportStatus


def _query_enum(name: str, enum_cls):
    raw = request.args.get(name)
    if raw is None:
        return None
    try:
        return enum_cls(raw)
    except ValueError:
        allowed = ", ".join(m.value for m in enum_cls)
        raise ValidationError({name: f"Must be one of: {allowed}."}) from None


def _pagination() -> tuple[int, int]:
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        raise ValidationError({"page": "page and per_page must be whole numbers."}) from None
    if page < 1 or not 1 <= per_page <= MAX_PER_PAGE:
        raise ValidationError(
            {"page": f"page must be at least 1 and per_page between 1 and {MAX_PER_PAGE}."}
        )
    return page, per_page


def _page_body(items: list[dict], total: int, page: int, per_page: int) -> dict:
    return {"reports": items, "page": page, "per_page": per_page, "total": total}


@bp.post("")
@jwt_required()
def submit_report():
    body = parse_body(ReportBody)
    report = service.submit_report(current_user, body.category, body.location, body.details)
    return {
        "report": report.to_dict(),
        "message": f"Report received. Your reference ID is {report.reference_id}.",
    }, 201


@bp.get("")
@jwt_required()
def list_reports():
    page, per_page = _pagination()
    category = _query_enum("category", ReportCategory)
    rows, total = service.list_own_reports(current_user, page, per_page, category)
    return _page_body([r.to_dict() for r in rows], total, page, per_page)


@bp.get("/<reference_id>")
@jwt_required()
def get_report(reference_id: str):
    return service.get_own_report(current_user, reference_id).to_dict()


@admin_bp.get("")
@role_required(Role.MAINTAINER)
def admin_list_reports():
    page, per_page = _pagination()
    category = _query_enum("category", ReportCategory)
    status = _query_enum("status", ReportStatus)
    rows, total = service.list_all_reports(page, per_page, category, status)
    return _page_body([r.to_dict() for r in rows], total, page, per_page)


@admin_bp.get("/<reference_id>")
@role_required(Role.MAINTAINER)
def admin_get_report(reference_id: str):
    report = service.get_report(reference_id)
    return {**report.to_dict(), "reporter": service.reporter_of(report)}


@admin_bp.patch("/<reference_id>")
@role_required(Role.MAINTAINER)
def admin_update_status(reference_id: str):
    body = parse_body(StatusBody)
    return service.set_status(service.get_report(reference_id), body.status).to_dict()
