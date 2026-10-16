from django.db.models import Q

from apps.accounts.models import User

from .models import Notification


def admin_users():
    """Active superusers, and active users holding any admin role (its name
    has "admin" in it, e.g. "Admin" or "Super Admin")."""
    # One filter() call, so all three conditions apply to the same role.
    admin_role = Q(roles__name__icontains='admin', roles__is_active=True, roles__deleted_at__isnull=True)
    return User.objects.filter(is_active=True).filter(Q(is_superuser=True) | admin_role).distinct()


def _describe(filed):
    """One line on what was asked for, e.g. "Maria Alva · Humana in TX"."""
    if filed.type == 'merch':
        product = filed.product.name if filed.product else 'merch'
        return f'{filed.buyer_name} · {product} ({filed.quantity} × {filed.size})'
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


def notify_agent_of_decision(filed, actor, previous_status):
    """Tells the linked agent user when HR approves or denies their request.

    Merch orders and agents with no sign-in account are skipped. Only fires
    when status newly becomes approved or denied (not on note-only edits).
    """
    if filed.type == 'merch' or not filed.agent_id:
        return
    if filed.status not in ('approved', 'denied') or filed.status == previous_status:
        return
    recipient = User.objects.filter(agent_id=filed.agent_id, is_active=True).first()
    if recipient is None:
        return
    decision = filed.get_status_display().lower()
    title = f'Your {filed.get_type_display().lower()} request was {decision}'
    Notification.objects.create(
        recipient=recipient,
        request=filed,
        title=title,
        body=_describe(filed),
        link='/agent/calendar',
        created_by=actor,
        updated_by=actor,
    )
