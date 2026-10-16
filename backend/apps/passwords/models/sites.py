from django.db import models
from django.db.models.functions import Lower

from apps.agency.models import Agency
from apps.agents.models import Agent
from apps.base.models import BaseModel

from .passwords import PASSWORD_STATUSES


class Site(BaseModel):
    """A place a portal login is used that isn't a carrier, e.g. a quoting
    tool: a name, unique whatever its case among live sites, and an optional
    link. Managed from the site password form only (Passwords module)."""

    name = models.CharField(max_length=255)
    # The site's portal sign-in page. Blank when none.
    link = models.URLField(max_length=2000, blank=True)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_site_name_alive',
                violation_error_message='A site with this name already exists.',
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        super().save(*args, **kwargs)


class SitePassword(BaseModel):
    """One portal login at one site, the site counterpart of Password: the
    portal username and password, for an agent or the agency (exactly one).
    Stored as entered, like Password; access is the `passwords` module."""

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='site_passwords', null=True, blank=True)
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='site_passwords', null=True, blank=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='passwords')
    # Both may be blank while the status is pending (the API enforces it).
    username = models.CharField(max_length=255, blank=True)
    portal_password = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=PASSWORD_STATUSES, default='active')

    class Meta(BaseModel.Meta):
        constraints = [
            # One password per agent at each site; a deleted one can be replaced.
            models.UniqueConstraint(
                fields=['agent', 'site'],
                condition=models.Q(deleted_at__isnull=True, agent__isnull=False),
                name='uniq_site_password_agent_alive',
                violation_error_message='This agent already has a password at this site.',
            ),
            # And one agency password at each site.
            models.UniqueConstraint(
                fields=['agency', 'site'],
                condition=models.Q(deleted_at__isnull=True, agency__isnull=False),
                name='uniq_site_password_agency_alive',
                violation_error_message='The agency already has a password at this site.',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(agent__isnull=False, agency__isnull=True)
                    | models.Q(agent__isnull=True, agency__isnull=False)
                ),
                name='site_password_agent_or_agency',
                violation_error_message='A password belongs to an agent or the agency.',
            ),
        ]

    def __str__(self):
        return f'{self.party} @ {self.site}'

    @property
    def party(self):
        """Who the login belongs to: the agent, or the agency."""
        return self.agent or self.agency

    def save(self, *args, **kwargs):
        self.username = self.username.strip()
        super().save(*args, **kwargs)
