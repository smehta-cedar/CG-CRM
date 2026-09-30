from django.db import migrations, models


def copy_policy_types(apps, schema_editor):
    """Each contract covers the policy types of the carrier policies it
    covered before."""
    AgencyCarrierContract = apps.get_model('contracts', 'AgencyCarrierContract')
    for contract in AgencyCarrierContract.objects.prefetch_related('policies'):
        type_ids = {policy.policy_type_id for policy in contract.policies.all()}
        if type_ids:
            contract.policy_types.set(type_ids)


class Migration(migrations.Migration):
    """Agency contracts cover policy types instead of carrier policies."""

    dependencies = [
        ('contracts', '0003_remove_agency_contract_login'),
        ('policies', '0005_certification_scope'),
    ]

    operations = [
        migrations.AddField(
            model_name='agencycarriercontract',
            name='policy_types',
            field=models.ManyToManyField(blank=True, related_name='agency_contracts', to='policies.policytype'),
        ),
        migrations.RunPython(copy_policy_types, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='agencycarriercontract',
            name='policies',
        ),
    ]
