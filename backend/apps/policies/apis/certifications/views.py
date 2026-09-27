from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.policies.models import Certification, CertificationNote
from apps.policies.utils import (
    CERTIFICATION_NOTE_FIELDS,
    certification_queryset,
    certification_snapshot,
    diff_snapshots,
    filter_certifications,
    get_certification_or_404,
    record_certification_note,
    save_certification,
)
from apps.policies.validators import (
    ensure_dates_in_order,
    ensure_pair_free,
    resolve_agent,
    resolve_policy_type,
)

from . import swagger
from .serializers import (
    CertificationCreateSerializer,
    CertificationListQuerySerializer,
    CertificationNoteSerializer,
    CertificationSerializer,
    CertificationUpdateSerializer,
)

CAN_MANAGE_CERTIFICATIONS = module_permission('certifications')


@swagger.certification_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CERTIFICATIONS])
def certification_list(request):
    # Check the ?agent= and ?policy_type= values; bad ones give a 400.
    query = CertificationListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    certifications = filter_certifications(
        certification_queryset(),
        agent=filters.get('agent'),
        policy_type=filters.get('policy_type'),
    )

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, certifications.order_by('policy_type__name', 'agent__name'))
    serializer = CertificationSerializer(page, many=True)
    return APIResponse(serializer.data, 'Certifications fetched successfully.', meta=meta)


@swagger.certification_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CERTIFICATIONS])
def certification_create(request):
    serializer = CertificationCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    agent = resolve_agent(data['agent'])
    policy_type = resolve_policy_type(data['policy_type'])
    # Both were sent, so the pair is reported as the policy type being taken for the agent.
    ensure_pair_free(agent, policy_type, field='policy_type')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    ensure_dates_in_order(start_date, end_date)

    with transaction.atomic():
        certification = Certification.objects.create(
            agent=agent,
            policy_type=policy_type,
            start_date=start_date,
            end_date=end_date,
            is_active=data.get('is_active', True),
            created_by=request.user,
            updated_by=request.user,
        )
        # The note lists every filled field, as the certification now reads.
        record_certification_note(
            certification,
            request.user,
            CertificationNote.KIND_ADDED,
            diff_snapshots({}, certification_snapshot(certification), CERTIFICATION_NOTE_FIELDS),
        )

    return APIResponse(
        CertificationSerializer(certification).data,
        'Certification created successfully.',
        status=status.HTTP_201_CREATED,
    )


@swagger.certification_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CERTIFICATIONS])
def certification_detail(request, pk):
    certification = get_certification_or_404(pk)

    if request.method == 'GET':
        return APIResponse(CertificationSerializer(certification).data, 'Certification fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = CertificationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        if 'agent' in fields:
            fields['agent'] = resolve_agent(fields['agent'])
        if 'policy_type' in fields:
            fields['policy_type'] = resolve_policy_type(fields['policy_type'])

        # The pair only has to be free when it is actually changing. The error
        # sits under the side that was sent: the one the user chose.
        agent = fields.get('agent', certification.agent)
        policy_type = fields.get('policy_type', certification.policy_type)
        if agent != certification.agent or policy_type != certification.policy_type:
            ensure_pair_free(
                agent,
                policy_type,
                field='policy_type' if 'policy_type' in fields else 'agent',
                exclude=certification,
            )

        ensure_dates_in_order(
            fields.get('start_date', certification.start_date),
            fields.get('end_date', certification.end_date),
        )

        before = certification_snapshot(certification)
        with transaction.atomic():
            save_certification(certification, request.user, **fields)
            record_certification_note(
                certification,
                request.user,
                CertificationNote.KIND_EDITED,
                diff_snapshots(before, certification_snapshot(certification), CERTIFICATION_NOTE_FIELDS),
            )
        return APIResponse(CertificationSerializer(certification).data, 'Certification updated successfully.')

    # DELETE: soft delete; the pair can be added again.
    certification.delete(user=request.user)
    return APIResponse(None, 'Certification deleted successfully.')


@swagger.certification_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CERTIFICATIONS])
def certification_notes(request, pk):
    certification = get_certification_or_404(pk)
    # Newest first (the model's ordering). Not paginated: a certification has a handful.
    notes = certification.notes.select_related('created_by')
    return APIResponse(CertificationNoteSerializer(notes, many=True).data, 'Certification notes fetched successfully.')
