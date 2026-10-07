from django.db import transaction
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.policies.models import Certification, CertificationNote
from apps.policies.utils import (
    CERTIFICATION_NOTE_FIELDS,
    certification_due_date,
    certification_queryset,
    certification_snapshot,
    delete_file_on_commit,
    diff_snapshots,
    filter_certifications,
    get_certification_or_404,
    record_certification_note,
    save_certification,
    upload_name,
)
from apps.policies.validators import ensure_pdf, resolve_agent, resolve_carrier

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
    # Check the ?agent=, ?carrier= and ?line_of_business= values; bad ones give a 400.
    query = CertificationListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    certifications = filter_certifications(
        certification_queryset(),
        agent=filters.get('agent'),
        carrier=filters.get('carrier'),
        line_of_business=filters.get('line_of_business'),
    )

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, certifications.order_by('agent__name', 'due_date', 'carrier__name', 'line_of_business'))
    serializer = CertificationSerializer(page, many=True)
    return APIResponse(serializer.data, 'Certifications fetched successfully.', meta=meta)


@swagger.certification_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CERTIFICATIONS])
def certification_create(request):
    serializer = CertificationCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # Nothing else is checked: a certification is an add-on.
    agent = resolve_agent(data['agent'])
    carrier = resolve_carrier(data['carrier']) if data.get('carrier') else None
    upload = data.get('file')
    if upload is not None:
        ensure_pdf(upload)

    with transaction.atomic():
        certification = Certification.objects.create(
            agent=agent,
            carrier=carrier,
            line_of_business=data.get('line_of_business', ''),
            due_date=data.get('due_date') or certification_due_date(),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            is_verified=data.get('is_verified', False),
            file=upload,
            file_name=upload_name(upload) if upload is not None else '',
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

        # Nothing else is checked: a certification is an add-on.
        if 'agent' in fields:
            fields['agent'] = resolve_agent(fields['agent'])
        if 'carrier' in fields:
            fields['carrier'] = resolve_carrier(fields['carrier']) if fields['carrier'] else None

        # A new PDF replaces the stored one; no file in the request keeps it.
        replaced = None
        if 'file' in fields:
            ensure_pdf(fields['file'])
            fields['file_name'] = upload_name(fields['file'])
            replaced = certification.file.name or None

        before = certification_snapshot(certification)
        with transaction.atomic():
            save_certification(certification, request.user, **fields)
            if replaced:
                delete_file_on_commit(certification.file, replaced)
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


@swagger.certification_file
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CERTIFICATIONS])
def certification_file(request, pk):
    certification = get_certification_or_404(pk)
    if not certification.file:
        raise NotFound('This certification has no file.')
    try:
        handle = certification.file.open('rb')
    except FileNotFoundError:
        raise NotFound('This certification has no file.')
    # The stored name is random; the download carries the name it was uploaded with.
    return FileResponse(handle, as_attachment=True, filename=certification.file_name, content_type='application/pdf')
