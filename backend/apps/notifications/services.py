from django.db.models import Q

from apps.accounts.models import User

from .models import Notification


def admin_users():
    """Active superusers, and active users whose role is an admin one (its
    name has "admin" in it, e.g. "Admin" or "Super Admin")."""
    admin_role = Q(role__name__icontains='admin', role__is_active=True, role__deleted_at__isnull=True)
    return User.objects.filter(is_active=True).filter(Q(is_superuser=True) | admin_role).distinct()


def _describe(filed):
    """One line on what was asked for, e.g. "Maria Alva · Humana in TX"."""
    agent = filed.agent.name if filed.agent else '?'
    if filed.type == 'day_off':
        if filed.start_date == filed.end_date:
            return f'{agent} · {filed.start_date:%b %d, %Y}'
        return f'{agent} · {filed.start_date:%b %d} to {filed.end_date:%b %d, %Y}'
    carrier = filed.carrier.name if filed.carrier else '?'
    state = filed.state.code if filed.state else '?'
    return f'{agent} · {carrier} in {state}'


def notify_admins_of_request(filed, actor):
    """Tells every admin that a request is waiting, the filer too when they are one."""
    who = actor.full_name or actor.email
    title = f'{who} filed a {filed.get_type_display().lower()} request'
    body = _describe(filed)
    Notification.objects.bulk_create(
        Notification(
            recipient=admin,
            request=filed,
            title=title,
            body=body,
            link='/hr',
            created_by=actor,
            updated_by=actor,
        )
        for admin in admin_users()
    )
