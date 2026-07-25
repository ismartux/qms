from submissions.models import Submission, SubmissionResponse


def submissions_qs(plant=None, template=None, department=None):
    qs = Submission.objects.filter(workflow_state="SUBMITTED")

    if plant:
        qs = qs.filter(plant=plant)

    if template:
        qs = qs.filter(template_version__template=template)

    if department:
        qs = qs.filter(template_version__template__department=department)

    return qs


def nc_responses_qs(plant=None, template=None):
    qs = SubmissionResponse.objects.filter(
        is_non_conformance=True,
        submission__workflow_state="SUBMITTED"
    )

    if plant:
        qs = qs.filter(submission__plant=plant)

    if template:
        qs = qs.filter(submission__template_version__template=template)

    return qs
