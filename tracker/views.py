import calendar
import math  # noqa: F401  (kept for future rounding changes)
from datetime import date

from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .forms import SignUpForm
from .models import AttendanceRecord

User = get_user_model()
STATUS_LABELS = dict(AttendanceRecord.Status.choices)
VALID_STATUSES = set(STATUS_LABELS.keys())
BOLD = Font(bold=True)
RED_BOLD = Font(bold=True, color="9B2C2C")

# ---------------------------------------------------------------------------
# Office-attendance policy
# Each month an employee must work from office on at least OFFICE_PERCENT % of
# their eligible working days. Eligible days = Mon-Fri days in the month minus
# privilege-leave days minus holidays (these days are excluded from the base).
#
# Statuses are matched by their label/key, so adjust the words below to match
# the values in AttendanceRecord.Status.
# ---------------------------------------------------------------------------
OFFICE_PERCENT = 60
OFFICE_WORDS = ("office",)
OFFICE_KEYS = {"wfo"}
PRIVILEGE_WORDS = ("privilege",)
PRIVILEGE_KEYS = {"pl"}
HOLIDAY_WORDS = ("holiday",)
HOLIDAY_KEYS = set()


def _classify(status):
    """Return 'office', 'pl', 'holiday' or 'other' for a stored status value."""
    key = str(status).lower()
    label = str(STATUS_LABELS.get(status, status)).lower()
    if key in PRIVILEGE_KEYS or any(w in label or w in key for w in PRIVILEGE_WORDS):
        return "pl"
    if key in HOLIDAY_KEYS or any(w in label or w in key for w in HOLIDAY_WORDS):
        return "holiday"
    if key in OFFICE_KEYS or any(w in label or w in key for w in OFFICE_WORDS):
        return "office"
    return "other"


def compute_policy(year, month, entries):
    """
    entries: iterable of (date, status) for ONE user in the given month.
    Only Monday-Friday entries are counted.
    """
    days_in_month = calendar.monthrange(year, month)[1]
    working_days = sum(
        1 for d in range(1, days_in_month + 1) if date(year, month, d).weekday() < 5
    )

    office = pl = holiday = other = 0
    for d, status in entries:
        if d.weekday() >= 5:
            continue
        kind = _classify(status)
        if kind == "office":
            office += 1
        elif kind == "pl":
            pl += 1
        elif kind == "holiday":
            holiday += 1
        else:
            other += 1

    eligible = max(working_days - pl - holiday, 0)
    required = -(-eligible * OFFICE_PERCENT // 100)  # ceil without floats
    remaining = max(required - office, 0)
    unrecorded = max(eligible - office - other, 0)
    return {
        "year": year,
        "month": month,
        "month_label": calendar.month_name[month],
        "percent_required": OFFICE_PERCENT,
        "working_days": working_days,
        "privilege_leave": pl,
        "holidays": holiday,
        "eligible_days": eligible,
        "required_days": required,
        "office_days": office,
        "remaining": remaining,
        "unrecorded": unrecorded,
        "achievable": remaining <= unrecorded,
        "met": office >= required,
        "achieved_percent": round(office * 100 / eligible, 1) if eligible else 0,
        # progress toward the required office days (capped at 100)
        "completed_percent": (
            min(100.0, round(office * 100 / required, 1)) if required else 100.0
        ),
    }


def register(request):
    if request.user.is_authenticated:
        return redirect("tracker")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("tracker")
    else:
        form = SignUpForm()
    return render(request, "tracker/register.html", {"form": form})


@login_required
def tracker_view(request):
    """
    Regular users: editable calendar with their own records embedded.
    Staff users: reports panel + a READ-ONLY calendar of a selected user.
    """
    today = date.today()
    context = {
        "current_year": today.year,
        "current_month": today.month,  # 1-indexed for the template
    }
    if request.user.is_staff:
        staff_users = User.objects.filter(is_staff=False).order_by("username")
        selected_user = None
        raw = request.GET.get("view_user", "")
        if raw:
            if not raw.isdigit():
                return HttpResponseBadRequest("Invalid user.")
            selected_user = get_object_or_404(staff_users, pk=int(raw))
        context["staff_users"] = staff_users
        context["months"] = [(i, calendar.month_name[i]) for i in range(1, 13)]
        context["selected_user"] = selected_user
        context["status_labels"] = STATUS_LABELS
        context["records"] = (
            {
                r.date.isoformat(): r.status
                for r in AttendanceRecord.objects.filter(user=selected_user)
            }
            if selected_user
            else {}
        )
    else:
        context["records"] = {
            r.date.isoformat(): r.status
            for r in AttendanceRecord.objects.filter(user=request.user)
        }
    return render(request, "tracker/tracker.html", context)


@login_required
@require_POST
def set_status(request):
    """Create, update, or clear a single day's status for the signed-in (non-staff) user only."""
    if request.user.is_staff:
        raise PermissionDenied  # staff can only download reports, not fill the calendar
    day = request.POST.get("date", "")
    status = request.POST.get("status", "")

    try:
        parsed_date = date.fromisoformat(day)
    except ValueError:
        return HttpResponseBadRequest("Invalid date.")

    if status == "":
        AttendanceRecord.objects.filter(user=request.user, date=parsed_date).delete()
        return JsonResponse({"ok": True, "date": day, "status": None})

    if status not in VALID_STATUSES:
        return HttpResponseBadRequest("Invalid status.")

    AttendanceRecord.objects.update_or_create(
        user=request.user, date=parsed_date, defaults={"status": status}
    )
    return JsonResponse({"ok": True, "date": day, "status": status})


def _resolve_target(request):
    """
    Return a User, or None meaning "all users" (staff only).
    Non-staff users can only ever get their own data.
    Assumes user_id was already validated as "", "all", or digits.
    """
    raw = request.GET.get("user_id", "")
    if raw in ("", str(request.user.pk)):
        return request.user
    if not request.user.is_staff:
        raise PermissionDenied
    if raw == "all":
        return None
    return get_object_or_404(User, pk=int(raw))


@login_required
def policy_summary(request):
    """JSON office-policy status for one user and month. Staff may pass user_id."""
    today = date.today()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if not (1900 <= year <= 2100 and 1 <= month <= 12):
            raise ValueError
    except ValueError:
        return HttpResponseBadRequest("Invalid year or month.")

    raw_user = request.GET.get("user_id", "")
    if raw_user == "all" or (raw_user and not raw_user.isdigit()):
        return HttpResponseBadRequest("Invalid user.")
    target = _resolve_target(request)  # 403 for non-staff asking for others

    entries = AttendanceRecord.objects.filter(
        user=target, date__year=year, date__month=month
    ).values_list("date", "status")
    return JsonResponse(compute_policy(year, month, entries))


@login_required
def download_report(request):
    """Export attendance as .xlsx (month or full year). Staff may pick any user or all users."""
    scope = request.GET.get("scope")

    try:
        year = int(request.GET.get("year", ""))
        if not 1900 <= year <= 2100:
            raise ValueError
    except ValueError:
        return HttpResponseBadRequest("A valid year is required.")

    raw_user = request.GET.get("user_id", "")
    if raw_user not in ("", "all") and not raw_user.isdigit():
        return HttpResponseBadRequest("Invalid user.")
    target = _resolve_target(request)  # 403 for non-staff, 404 if user missing

    qs = AttendanceRecord.objects.filter(date__year=year)
    if target is not None:
        qs = qs.filter(user=target)
        who = target.username
    else:
        qs = qs.select_related("user")
        who = "all_users"

    if scope == "month":
        try:
            month = int(request.GET.get("month", ""))
            if not 1 <= month <= 12:
                raise ValueError
        except ValueError:
            return HttpResponseBadRequest("A valid month is required.")
        qs = qs.filter(date__month=month)
        filename = f"attendance_{who}_{year}_{month:02d}.xlsx"
        sheet_title = "Month Report"
    elif scope == "year":
        filename = f"attendance_{who}_{year}_full_year.xlsx"
        sheet_title = "Year Report"
    else:
        return HttpResponseBadRequest("scope must be 'month' or 'year'.")

    include_user_col = target is None
    header = ["Date", "Day", "Month", "Status"]
    widths = [12, 12, 12, 18]
    if include_user_col:
        header.insert(0, "User")
        widths.insert(0, 18)

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.append(header)
    for cell in ws[1]:
        cell.font = BOLD

    counts = {}
    order = ("user__username", "date") if include_user_col else ("date",)
    for record in qs.order_by(*order):
        label = STATUS_LABELS.get(record.status, record.status)
        row = [
            record.date.isoformat(),
            record.date.strftime("%A"),
            record.date.strftime("%B"),
            label,
        ]
        if include_user_col:
            row.insert(0, record.user.username)
        ws.append(row)
        counts[label] = counts.get(label, 0) + 1

    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    if scope == "year":
        summary = wb.create_sheet("Summary")
        summary.append(["Status", "Days"])
        for cell in summary[1]:
            cell.font = BOLD
        for label, count in counts.items():
            summary.append([label, count])
        summary.column_dimensions["A"].width = 20
        summary.column_dimensions["B"].width = 8

    # --- Policy sheet: monthly office-attendance compliance ---
    if target is not None:
        policy_users = [target]
    else:
        policy_users = list(User.objects.filter(is_staff=False).order_by("username"))
    policy_months = [month] if scope == "month" else list(range(1, 13))

    grouped = {}
    for uid, d, st in qs.values_list("user_id", "date", "status"):
        grouped.setdefault((uid, d.month), []).append((d, st))

    pws = wb.create_sheet("Policy")
    pws.append([
        "Employee", "Month", "Working days", "Privilege leave", "Holidays",
        "Eligible days", f"Required office days ({OFFICE_PERCENT}%)",
        "Office days", "Shortfall", "Office % of eligible days",
        f"Target completed % (of {OFFICE_PERCENT}% policy)", "Result",
    ])
    for cell in pws[1]:
        cell.font = BOLD
    for u in policy_users:
        for m in policy_months:
            p = compute_policy(year, m, grouped.get((u.pk, m), []))
            pws.append([
                u.username, p["month_label"], p["working_days"], p["privilege_leave"],
                p["holidays"], p["eligible_days"], p["required_days"], p["office_days"],
                p["remaining"], p["achieved_percent"], p["completed_percent"],
                "Met" if p["met"] else "Not met",
            ])
            pws.cell(row=pws.max_row, column=10).number_format = '0.0"%"'
            pws.cell(row=pws.max_row, column=11).number_format = '0.0"%"'
            if not p["met"]:
                pws.cell(row=pws.max_row, column=12).font = RED_BOLD
    for i, width in enumerate([18, 12, 14, 16, 10, 14, 30, 12, 10, 24, 36, 10], start=1):
        pws.column_dimensions[get_column_letter(i)].width = width

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response