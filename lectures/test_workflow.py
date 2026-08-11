import json
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from .admin import LectureWorkflowAdmin, WorkflowJobAdmin
from .models import (
    Chapter,
    ContentSource,
    Course,
    ExtractionVersion,
    GenerationRequest,
    GenerationSourceSnapshot,
    LectureWorkflow,
    SlideDraft,
    SlideRevision,
    WorkflowAuditEvent,
    WorkflowJob,
    WorkflowJobEvent,
)
from .roles import assign_administrator, assign_teacher, ensure_roles
from .workflow import (
    ACTOR_ADMINISTRATOR,
    ACTOR_SYSTEM_WORKER,
    ACTOR_TEACHER,
    QueueConfigurationError,
    WorkflowActorContext,
    WorkflowConflict,
    cancel_job,
    claim_job,
    complete_job,
    create_workflow,
    fail_job,
    invalidate_workflow_for_slide_revision,
    jobs_visible_to,
    submit_job,
    system_worker_context,
    transition_workflow,
    validate_job_payload,
    workflow_actor_for_user,
    workflows_visible_to,
)


class WorkflowQueueApprovalTests(TestCase):
    def setUp(self):
        ensure_roles()
        self.teacher = assign_teacher(User.objects.create_user("teacher-t030"))
        self.other_teacher = assign_teacher(User.objects.create_user("other-t030"))
        self.administrator = assign_administrator(User.objects.create_user("admin-t030"))
        self.unassigned = User.objects.create_user("unassigned-t030")
        self.course = Course.objects.create(code="SYN-T030", title="Synthetic workflow", teacher=self.teacher)
        self.chapter = Chapter.objects.create(course=self.course, number=1, title="Synthetic chapter")
        self.generation = self._generation(self.teacher, self.chapter, "primary")
        self.teacher_actor = workflow_actor_for_user(self.teacher)
        self.admin_actor = workflow_actor_for_user(self.administrator)
        self.worker = system_worker_context(
            identity_reference="worker:synthetic-1", permitted_course_ids=[self.course.pk]
        )

    def _generation(self, teacher, chapter, suffix):
        generation = GenerationRequest.objects.create(
            chapter=chapter,
            requested_by=teacher,
            guidelines={"synthetic": True},
            generator_key="synthetic-t030",
            input_sha256=(suffix.encode().hex() + "0" * 64)[:64],
            status=GenerationRequest.Status.APPROVED,
        )
        source = ContentSource.objects.create(
            chapter=chapter,
            source_type=ContentSource.SourceType.INSTITUTIONAL,
            access_scope=ContentSource.AccessScope.AUTHORIZED_TEACHERS,
            title=f"Synthetic source {suffix}",
            rights_confirmed=True,
            rights_confirmed_by=teacher,
            processing_state=ContentSource.ProcessingState.READY,
        )
        extraction = ExtractionVersion.objects.create(
            source=source,
            version=1,
            status=ExtractionVersion.Status.COMPLETE,
            extractor="synthetic-t030",
        )
        GenerationSourceSnapshot.objects.create(
            generation=generation,
            source=source,
            extraction=extraction,
            source_file_sha256="a" * 64,
            extraction_version=1,
            source_title=source.title,
        )
        for position in (1, 2):
            slide = SlideDraft.objects.create(generation=generation, position=position)
            revision = SlideRevision.objects.create(
                slide=slide,
                version=1,
                title=f"Synthetic slide {position}",
                created_by_actor_id=teacher.pk,
            )
            slide.approved_revision = revision
            slide.save(update_fields=("approved_revision",))
        return generation

    def create(self, *, generation=None, actor=None, key="workflow:create"):
        return create_workflow(
            actor=actor or self.teacher_actor,
            generation_id=(generation or self.generation).pk,
            idempotency_key=key,
        )

    def transition(self, workflow, target, reason, actor, *, job=None, reference="", key=None):
        workflow.refresh_from_db()
        return transition_workflow(
            actor=actor,
            workflow_id=workflow.pk,
            target_state=target,
            reason_code=reason,
            expected_version=workflow.version,
            idempotency_key=key or f"transition:{workflow.version + 1}:{target}",
            job_id=job.pk if job else None,
            artifact_reference=reference,
        )

    def submit_complete(self, workflow, job_type, payload, key):
        job = submit_job(
            actor=self.teacher_actor,
            workflow_id=workflow.pk,
            job_type=job_type,
            payload=payload,
            idempotency_key=key,
        )
        claimed = claim_job(actor=self.worker, lease_seconds=60)
        self.assertEqual(claimed.pk, job.pk)
        return complete_job(
            actor=self.worker,
            job_id=job.pk,
            completion_idempotency_key=f"complete:{key}",
            result={"artifact_reference": f"result:{key}"},
        )

    def reach_draft(self, workflow):
        job = self.submit_complete(
            workflow,
            WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            {"generation_id": workflow.generation_id},
            f"job:draft:{workflow.pk}",
        )
        return self.transition(
            workflow,
            LectureWorkflow.State.SLIDE_NARRATION_DRAFT,
            "DRAFT_AVAILABLE",
            self.worker,
            job=job,
        )

    def reach_recording_ready(self, workflow):
        self.reach_draft(workflow)
        self.transition(
            workflow,
            LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
            "TEACHER_APPROVED_CURRENT_DRAFT",
            self.teacher_actor,
        )
        self.transition(
            workflow,
            LectureWorkflow.State.RECORDING_PENDING,
            "RECORDING_SCHEDULED",
            self.worker,
        )
        revisions = list(workflow.generation.slides.values_list("approved_revision_id", flat=True))
        job = self.submit_complete(
            workflow,
            WorkflowJob.JobType.RECORDING_READINESS,
            {"approved_slide_revision_ids": revisions},
            f"job:recording:{workflow.pk}",
        )
        return self.transition(
            workflow,
            LectureWorkflow.State.RECORDING_READY,
            "RECORDING_REFERENCE_READY",
            self.worker,
            job=job,
            reference=f"recording:synthetic-{workflow.pk}",
        )

    def reach_video_ready(self, workflow, *, suffix="first"):
        if workflow.state == LectureWorkflow.State.SOURCE_CONTENT_READY:
            self.reach_recording_ready(workflow)
        self.transition(
            workflow,
            LectureWorkflow.State.DRAFT_VIDEO_PENDING,
            "VIDEO_DRAFT_SCHEDULED" if suffix == "first" else "VIDEO_RESUBMITTED",
            self.worker,
        )
        workflow.refresh_from_db()
        job = self.submit_complete(
            workflow,
            WorkflowJob.JobType.DRAFT_VIDEO_READINESS,
            {"recording_reference": workflow.recording_reference},
            f"job:video:{workflow.pk}:{suffix}",
        )
        return self.transition(
            workflow,
            LectureWorkflow.State.DRAFT_VIDEO_READY,
            "VIDEO_REFERENCE_READY",
            self.worker,
            job=job,
            reference=f"video:synthetic-{workflow.pk}-{suffix}",
        )

    def test_complete_valid_state_path_requires_jobs_and_creates_audit_for_every_change(self):
        workflow = self.create()
        self.reach_video_ready(workflow)
        self.transition(
            workflow,
            LectureWorkflow.State.TEACHER_VIDEO_APPROVED,
            "TEACHER_APPROVED_VIDEO",
            self.teacher_actor,
        )
        self.transition(
            workflow,
            LectureWorkflow.State.FINAL_ADMIN_APPROVED,
            "ADMIN_APPROVED_FINAL",
            self.admin_actor,
        )
        workflow.refresh_from_db()
        job = self.submit_complete(
            workflow,
            WorkflowJob.JobType.EXPORT_READINESS,
            {"draft_video_reference": workflow.draft_video_reference},
            "job:export:primary",
        )
        self.transition(
            workflow,
            LectureWorkflow.State.EXPORT_READY,
            "EXPORT_HANDOFF_READY",
            self.worker,
            job=job,
            reference="export:synthetic-primary",
        )
        workflow.refresh_from_db()
        self.assertEqual(workflow.state, LectureWorkflow.State.EXPORT_READY)
        self.assertEqual(workflow.audit_events.count(), workflow.version)
        self.assertEqual(
            list(workflow.audit_events.values_list("sequence", flat=True)),
            list(range(1, workflow.version + 1)),
        )

    def test_skipped_backward_and_duplicate_or_stale_transitions_fail_closed(self):
        workflow = self.create()
        for target, actor, reason in (
            (LectureWorkflow.State.RECORDING_PENDING, self.worker, "RECORDING_SCHEDULED"),
            (LectureWorkflow.State.TEACHER_VIDEO_APPROVED, self.teacher_actor, "TEACHER_APPROVED_VIDEO"),
            (LectureWorkflow.State.FINAL_ADMIN_APPROVED, self.admin_actor, "ADMIN_APPROVED_FINAL"),
            (LectureWorkflow.State.EXPORT_READY, self.worker, "EXPORT_HANDOFF_READY"),
        ):
            with self.subTest(target=target), self.assertRaises(WorkflowConflict):
                self.transition(workflow, target, reason, actor)
        job = self.submit_complete(
            workflow,
            WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            {"generation_id": workflow.generation_id},
            "job:transition-conflict",
        )
        original_version = workflow.version
        self.transition(
            workflow,
            LectureWorkflow.State.SLIDE_NARRATION_DRAFT,
            "DRAFT_AVAILABLE",
            self.worker,
            job=job,
            key="transition:one",
        )
        with self.assertRaises(WorkflowConflict):
            transition_workflow(
                actor=self.worker,
                workflow_id=workflow.pk,
                target_state=LectureWorkflow.State.SLIDE_NARRATION_DRAFT,
                reason_code="DRAFT_AVAILABLE",
                expected_version=original_version,
                idempotency_key="transition:one",
                job_id=job.pk,
            )

    def test_teacher_admin_and_system_role_boundaries_are_non_substitutable(self):
        workflow = self.create()
        self.reach_draft(workflow)
        for actor in (self.admin_actor, self.worker):
            with self.subTest(actor=actor.actor_type), self.assertRaises(PermissionDenied):
                self.transition(
                    workflow,
                    LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
                    "TEACHER_APPROVED_CURRENT_DRAFT",
                    actor,
                )
        self.transition(
            workflow,
            LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
            "TEACHER_APPROVED_CURRENT_DRAFT",
            self.teacher_actor,
        )
        with self.assertRaises(PermissionDenied):
            self.transition(
                workflow,
                LectureWorkflow.State.RECORDING_PENDING,
                "RECORDING_SCHEDULED",
                self.teacher_actor,
            )
        video = self.create(generation=self._generation(self.teacher, self.chapter, "role-video"), key="workflow:role-video")
        self.reach_video_ready(video)
        self.transition(
            video,
            LectureWorkflow.State.TEACHER_VIDEO_APPROVED,
            "TEACHER_APPROVED_VIDEO",
            self.teacher_actor,
        )
        for actor in (self.teacher_actor, self.worker):
            with self.subTest(actor=actor.actor_type), self.assertRaises(PermissionDenied):
                self.transition(
                    video,
                    LectureWorkflow.State.FINAL_ADMIN_APPROVED,
                    "ADMIN_APPROVED_FINAL",
                    actor,
                )

    def test_cross_slide_approval_reference_and_malformed_actor_context_fail_closed(self):
        workflow = self.create()
        self.reach_draft(workflow)
        slides = list(workflow.generation.slides.order_by("pk"))
        slides[1].approved_revision = slides[0].approved_revision
        slides[1].save(update_fields=("approved_revision",))
        with self.assertRaises(ValidationError):
            self.transition(
                workflow,
                LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
                "TEACHER_APPROVED_CURRENT_DRAFT",
                self.teacher_actor,
            )
        malformed = WorkflowActorContext(
            "UNEXPECTED",
            "actor:malformed",
            self.teacher.pk,
            frozenset({self.course.pk}),
            self.teacher_actor.capabilities,
        )
        with self.assertRaises(PermissionDenied):
            submit_job(
                actor=malformed,
                workflow_id=workflow.pk,
                job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
                payload={"generation_id": workflow.generation_id},
                idempotency_key="job:malformed-actor",
            )

    def test_cross_teacher_cross_course_and_unassigned_contexts_are_rejected(self):
        other_course = Course.objects.create(code="OTHER-T030", title="Other", teacher=self.other_teacher)
        other_chapter = Chapter.objects.create(course=other_course, number=1, title="Other")
        other_generation = self._generation(self.other_teacher, other_chapter, "other")
        other_actor = workflow_actor_for_user(self.other_teacher)
        primary_workflow = self.create()
        forged_same_course = WorkflowActorContext(
            ACTOR_TEACHER,
            "provider:other-teacher",
            self.other_teacher.pk,
            frozenset({self.course.pk}),
            self.teacher_actor.capabilities,
        )
        self.assertFalse(workflows_visible_to(forged_same_course).filter(pk=primary_workflow.pk).exists())
        with self.assertRaises(PermissionDenied):
            submit_job(
                actor=forged_same_course,
                workflow_id=primary_workflow.pk,
                job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
                payload={"generation_id": self.generation.pk},
                idempotency_key="job:forged-teacher",
            )
        with self.assertRaises(PermissionDenied):
            self.create(generation=other_generation, actor=self.teacher_actor, key="workflow:cross")
        other_workflow = self.create(generation=other_generation, actor=other_actor, key="workflow:other")
        self.assertFalse(workflows_visible_to(self.teacher_actor).filter(pk=other_workflow.pk).exists())
        self.assertFalse(jobs_visible_to(self.teacher_actor).filter(workflow=other_workflow).exists())
        for user in (AnonymousUser(), self.unassigned):
            with self.subTest(user=str(user)), self.assertRaises(PermissionDenied):
                self.create(actor=workflow_actor_for_user(user), key=f"workflow:denied:{user}")

    def test_stale_slide_approval_blocks_progress_and_revision_invalidation_is_audited(self):
        workflow = self.create()
        self.reach_draft(workflow)
        self.transition(
            workflow,
            LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
            "TEACHER_APPROVED_CURRENT_DRAFT",
            self.teacher_actor,
        )
        slide = workflow.generation.slides.first()
        revision = SlideRevision.objects.create(
            slide=slide,
            version=2,
            title="Synthetic revised slide",
            created_by_actor_id=self.teacher.pk,
        )
        slide.current_version = 2
        slide.approved_revision = None
        slide.save(update_fields=("current_version", "approved_revision"))
        with self.assertRaises(ValidationError):
            self.transition(
                workflow,
                LectureWorkflow.State.RECORDING_PENDING,
                "RECORDING_SCHEDULED",
                self.worker,
            )
        workflow.refresh_from_db()
        invalidate_workflow_for_slide_revision(
            workflow=workflow,
            actor_identity_reference=f"user:{self.teacher.pk}",
            slide_id=slide.pk,
            revision_version=revision.version,
        )
        workflow.refresh_from_db()
        self.assertEqual(workflow.state, LectureWorkflow.State.SLIDE_NARRATION_DRAFT)
        self.assertEqual(workflow.slide_approval_fingerprint, "")
        self.assertEqual(workflow.audit_events.last().reason_code, "SLIDE_REVISION_INVALIDATED")

    def test_successful_job_with_stale_slide_revision_payload_cannot_advance(self):
        workflow = self.create()
        self.reach_draft(workflow)
        self.transition(
            workflow,
            LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
            "TEACHER_APPROVED_CURRENT_DRAFT",
            self.teacher_actor,
        )
        self.transition(
            workflow,
            LectureWorkflow.State.RECORDING_PENDING,
            "RECORDING_SCHEDULED",
            self.worker,
        )
        old_revisions = list(workflow.generation.slides.values_list("approved_revision_id", flat=True))
        old_job = self.submit_complete(
            workflow,
            WorkflowJob.JobType.RECORDING_READINESS,
            {"approved_slide_revision_ids": old_revisions},
            "job:stale-recording",
        )
        slide = workflow.generation.slides.first()
        revision = SlideRevision.objects.create(
            slide=slide,
            version=2,
            title="Synthetic current revision",
            created_by_actor_id=self.teacher.pk,
        )
        slide.current_version = 2
        slide.approved_revision = revision
        slide.save(update_fields=("current_version", "approved_revision"))
        workflow.refresh_from_db()
        invalidate_workflow_for_slide_revision(
            workflow=workflow,
            actor_identity_reference=f"user:{self.teacher.pk}",
            slide_id=slide.pk,
            revision_version=revision.version,
        )
        self.transition(
            workflow,
            LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
            "TEACHER_APPROVED_CURRENT_DRAFT",
            self.teacher_actor,
        )
        self.transition(
            workflow,
            LectureWorkflow.State.RECORDING_PENDING,
            "RECORDING_SCHEDULED",
            self.worker,
        )
        with self.assertRaises(ValidationError):
            self.transition(
                workflow,
                LectureWorkflow.State.RECORDING_READY,
                "RECORDING_REFERENCE_READY",
                self.worker,
                job=old_job,
                reference="recording:stale-denied",
            )

    def test_teacher_video_rejection_requires_resubmission_before_approval(self):
        workflow = self.create()
        self.reach_video_ready(workflow)
        old_job = workflow.jobs.get(job_type=WorkflowJob.JobType.DRAFT_VIDEO_READINESS)
        self.transition(
            workflow,
            LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED,
            "TEACHER_REQUESTED_VIDEO_REVISION",
            self.teacher_actor,
        )
        with self.assertRaises(WorkflowConflict):
            self.transition(
                workflow,
                LectureWorkflow.State.TEACHER_VIDEO_APPROVED,
                "TEACHER_APPROVED_VIDEO",
                self.teacher_actor,
            )
        self.transition(
            workflow,
            LectureWorkflow.State.DRAFT_VIDEO_PENDING,
            "VIDEO_RESUBMITTED",
            self.worker,
        )
        with self.assertRaises(ValidationError):
            self.transition(
                workflow,
                LectureWorkflow.State.DRAFT_VIDEO_READY,
                "VIDEO_REFERENCE_READY",
                self.worker,
                job=old_job,
                reference="video:stale-cycle",
            )
        workflow.refresh_from_db()
        job = self.submit_complete(
            workflow,
            WorkflowJob.JobType.DRAFT_VIDEO_READINESS,
            {"recording_reference": workflow.recording_reference},
            f"job:video:{workflow.pk}:revision-2",
        )
        self.transition(
            workflow,
            LectureWorkflow.State.DRAFT_VIDEO_READY,
            "VIDEO_REFERENCE_READY",
            self.worker,
            job=job,
            reference=f"video:synthetic-{workflow.pk}-revision-2",
        )
        self.transition(
            workflow,
            LectureWorkflow.State.TEACHER_VIDEO_APPROVED,
            "TEACHER_APPROVED_VIDEO",
            self.teacher_actor,
        )
        workflow.refresh_from_db()
        self.assertEqual(workflow.state, LectureWorkflow.State.TEACHER_VIDEO_APPROVED)

    def test_admin_before_teacher_and_export_before_admin_are_rejected(self):
        workflow = self.create()
        self.reach_video_ready(workflow)
        with self.assertRaises(WorkflowConflict):
            self.transition(
                workflow,
                LectureWorkflow.State.FINAL_ADMIN_APPROVED,
                "ADMIN_APPROVED_FINAL",
                self.admin_actor,
            )
        self.transition(
            workflow,
            LectureWorkflow.State.TEACHER_VIDEO_APPROVED,
            "TEACHER_APPROVED_VIDEO",
            self.teacher_actor,
        )
        with self.assertRaises(WorkflowConflict):
            self.transition(
                workflow,
                LectureWorkflow.State.EXPORT_READY,
                "EXPORT_HANDOFF_READY",
                self.worker,
                reference="export:denied",
            )

    def test_audit_records_and_admin_paths_are_read_only(self):
        workflow = self.create()
        workflow.state = LectureWorkflow.State.EXPORT_READY
        with self.assertRaises(ValueError):
            workflow.save()
        workflow.refresh_from_db()
        job = submit_job(
            actor=self.teacher_actor,
            workflow_id=workflow.pk,
            job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            payload={"generation_id": workflow.generation_id},
            idempotency_key="job:read-only",
        )
        job.status = WorkflowJob.Status.SUCCEEDED
        with self.assertRaises(ValueError):
            job.save()
        event = workflow.audit_events.get()
        event.reason_code = "CHANGED"
        with self.assertRaises(ValueError):
            event.save()
        with self.assertRaises(ValueError):
            event.delete()
        request = RequestFactory().get("/admin/")
        request.user = self.administrator
        for model_admin in (
            LectureWorkflowAdmin(LectureWorkflow, admin.site),
            WorkflowJobAdmin(WorkflowJob, admin.site),
            admin.site._registry[WorkflowAuditEvent],
            admin.site._registry[WorkflowJobEvent],
        ):
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))

    def test_submission_and_completion_are_idempotent_but_conflicts_are_rejected(self):
        workflow = self.create()
        kwargs = {
            "actor": self.teacher_actor,
            "workflow_id": workflow.pk,
            "job_type": WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            "payload": {"generation_id": workflow.generation_id},
            "idempotency_key": "job:idempotent",
        }
        first = submit_job(**kwargs)
        self.assertEqual(submit_job(**kwargs).pk, first.pk)
        with self.assertRaises(WorkflowConflict):
            submit_job(**{**kwargs, "max_attempts": 4})
        claim_job(actor=self.worker, lease_seconds=60)
        other_worker = system_worker_context(
            identity_reference="worker:synthetic-other", permitted_course_ids=[self.course.pk]
        )
        complete = {
            "actor": self.worker,
            "job_id": first.pk,
            "completion_idempotency_key": "complete:idempotent",
            "result": {"artifact_reference": "result:idempotent"},
        }
        with self.assertRaises(PermissionDenied):
            complete_job(**{**complete, "actor": other_worker})
        self.assertEqual(complete_job(**complete).pk, first.pk)
        self.assertEqual(complete_job(**complete).pk, first.pk)
        with self.assertRaises(PermissionDenied):
            complete_job(**{**complete, "actor": other_worker})
        with self.assertRaises(WorkflowConflict):
            complete_job(**{**complete, "result": {"artifact_reference": "result:different"}})

    def test_atomic_claim_lease_expiry_recovery_and_terminal_expiry(self):
        workflow = self.create()
        job = submit_job(
            actor=self.teacher_actor,
            workflow_id=workflow.pk,
            job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            payload={"generation_id": workflow.generation_id},
            idempotency_key="job:lease",
            max_attempts=2,
        )
        start = timezone.now()
        first = claim_job(actor=self.worker, lease_seconds=30, now=start)
        self.assertEqual(first.attempts, 1)
        self.assertIsNone(claim_job(actor=self.worker, lease_seconds=30, now=start))
        second = claim_job(actor=self.worker, lease_seconds=30, now=start + timedelta(seconds=31))
        self.assertEqual(second.pk, job.pk)
        self.assertEqual(second.attempts, 2)
        self.assertIsNone(claim_job(actor=self.worker, lease_seconds=30, now=start + timedelta(seconds=62)))
        job.refresh_from_db()
        self.assertEqual(job.status, WorkflowJob.Status.FAILED)
        self.assertEqual(job.failure_reason_code, "LEASE_EXPIRED")

    def test_lease_recovery_is_scoped_to_the_workers_permitted_courses(self):
        other_course = Course.objects.create(code="LEASE-OTHER", title="Other lease", teacher=self.other_teacher)
        other_chapter = Chapter.objects.create(course=other_course, number=1, title="Other lease")
        other_generation = self._generation(self.other_teacher, other_chapter, "lease-other")
        other_workflow = self.create(
            generation=other_generation,
            actor=workflow_actor_for_user(self.other_teacher),
            key="workflow:lease-other",
        )
        submit_job(
            actor=workflow_actor_for_user(self.other_teacher),
            workflow_id=other_workflow.pk,
            job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            payload={"generation_id": other_generation.pk},
            idempotency_key="job:lease-other",
        )
        other_worker = system_worker_context(
            identity_reference="worker:lease-other", permitted_course_ids=[other_course.pk]
        )
        start = timezone.now()
        other_job = claim_job(actor=other_worker, lease_seconds=30, now=start)
        self.assertIsNone(claim_job(actor=self.worker, lease_seconds=30, now=start + timedelta(seconds=31)))
        other_job.refresh_from_db()
        self.assertEqual(other_job.status, WorkflowJob.Status.RUNNING)
        self.assertEqual(other_job.attempts, 1)

    def test_retry_cancellation_terminal_failure_and_failed_jobs_cannot_advance(self):
        workflow = self.create()
        job = submit_job(
            actor=self.teacher_actor,
            workflow_id=workflow.pk,
            job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            payload={"generation_id": workflow.generation_id},
            idempotency_key="job:retry",
            max_attempts=2,
        )
        claim_job(actor=self.worker, lease_seconds=60)
        fail_job(
            actor=self.worker,
            job_id=job.pk,
            reason_code="RESOURCE_LIMIT",
            message="Synthetic resource ceiling reached.",
            retryable=True,
        )
        self.assertEqual(claim_job(actor=self.worker, lease_seconds=60).attempts, 2)
        fail_job(
            actor=self.worker,
            job_id=job.pk,
            reason_code="WORKER_ERROR",
            message="Synthetic worker failed safely.",
            retryable=True,
        )
        job.refresh_from_db()
        self.assertEqual(job.status, WorkflowJob.Status.FAILED)
        with self.assertRaises(ValidationError):
            self.transition(
                workflow,
                LectureWorkflow.State.SLIDE_NARRATION_DRAFT,
                "DRAFT_AVAILABLE",
                self.worker,
                job=job,
            )
        cancelled = submit_job(
            actor=self.teacher_actor,
            workflow_id=workflow.pk,
            job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            payload={"generation_id": workflow.generation_id},
            idempotency_key="job:cancel",
        )
        self.assertEqual(cancel_job(actor=self.teacher_actor, job_id=cancelled.pk).status, WorkflowJob.Status.CANCELLED)
        with self.assertRaises(ValidationError):
            self.transition(
                workflow,
                LectureWorkflow.State.SLIDE_NARRATION_DRAFT,
                "DRAFT_AVAILABLE",
                self.worker,
                job=cancelled,
            )

    def test_malformed_oversized_and_privacy_unsafe_job_inputs_are_rejected(self):
        workflow = self.create()
        invalid = (
            (WorkflowJob.JobType.SLIDE_NARRATION_DRAFT, {"generation_id": True}),
            (WorkflowJob.JobType.SLIDE_NARRATION_DRAFT, {"generation_id": workflow.generation_id, "command": "run"}),
            (WorkflowJob.JobType.DRAFT_VIDEO_READINESS, {"recording_reference": "C:\\private\\audio.wav"}),
            ("ARBITRARY_CODE", {"generation_id": workflow.generation_id}),
        )
        for job_type, payload in invalid:
            with self.subTest(job_type=job_type, payload=payload), self.assertRaises(ValidationError):
                validate_job_payload(job_type, payload, workflow)
        with self.assertRaises(ValidationError):
            validate_job_payload(
                WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
                {"generation_id": workflow.generation_id, "padding": "x" * 9000},
                workflow,
            )
        job = submit_job(
            actor=self.teacher_actor,
            workflow_id=workflow.pk,
            job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            payload={"generation_id": workflow.generation_id},
            idempotency_key="job:privacy",
        )
        claim_job(actor=self.worker, lease_seconds=60)
        with self.assertRaises(ValidationError):
            fail_job(
                actor=self.worker,
                job_id=job.pk,
                reason_code="WORKER_ERROR",
                message="Secret at C:\\private\\credentials.txt",
                retryable=False,
            )

    def test_sqlite_is_explicitly_single_worker_and_models_are_postgresql_portable(self):
        self.assertEqual(connection.vendor, "sqlite")
        workflow = self.create()
        submit_job(
            actor=self.teacher_actor,
            workflow_id=workflow.pk,
            job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
            payload={"generation_id": workflow.generation_id},
            idempotency_key="job:sqlite",
        )
        with override_settings(WORKFLOW_SQLITE_SINGLE_WORKER=False), self.assertRaises(QueueConfigurationError):
            claim_job(actor=self.worker, lease_seconds=60)
        for model in (LectureWorkflow, WorkflowAuditEvent, WorkflowJob, WorkflowJobEvent):
            self.assertFalse(model._meta.required_db_vendor)
            self.assertTrue(all(index.condition is None for index in model._meta.indexes))
        self.assertTrue(connection.features.supports_transactions)

    def test_authentication_provider_independence_uses_only_explicit_actor_facts(self):
        self.assertEqual(self.teacher_actor.actor_type, ACTOR_TEACHER)
        self.assertEqual(self.admin_actor.actor_type, ACTOR_ADMINISTRATOR)
        self.assertEqual(self.worker.actor_type, ACTOR_SYSTEM_WORKER)
        for context in (self.teacher_actor, self.admin_actor, self.worker):
            representation = repr(context)
            self.assertNotIn("session", representation.casefold())
            self.assertNotIn("crm", representation.casefold())
            self.assertNotIn("User:", representation)
        direct = WorkflowActorContext(
            ACTOR_TEACHER,
            "provider:synthetic-teacher",
            self.teacher.pk,
            frozenset({self.course.pk}),
            self.teacher_actor.capabilities,
        )
        self.assertEqual(self.create(actor=direct, key="workflow:provider-independent").generation, self.generation)

    def test_minimal_apis_are_scoped_and_reject_malformed_or_unexpected_json(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            "/api/workflows/",
            data=json.dumps({"generation_id": self.generation.pk, "idempotency_key": "api:create"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        workflow_id = response.json()["id"]
        self.assertEqual(self.client.get(f"/api/workflows/{workflow_id}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/workflows/{workflow_id}/audit/").status_code, 200)
        malformed = self.client.post("/api/workflows/", data="{", content_type="application/json")
        self.assertEqual(malformed.status_code, 400)
        unexpected = self.client.post(
            "/api/workflow-jobs/",
            data=json.dumps(
                {
                    "workflow_id": workflow_id,
                    "job_type": WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
                    "payload": {"generation_id": self.generation.pk},
                    "idempotency_key": "api:job",
                    "command": "not-allowed",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(unexpected.status_code, 400)
        submitted = self.client.post(
            "/api/workflow-jobs/",
            data=json.dumps(
                {
                    "workflow_id": workflow_id,
                    "job_type": WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
                    "payload": {"generation_id": self.generation.pk},
                    "idempotency_key": "api:valid-job",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(submitted.status_code, 201, submitted.content)
        job_id = submitted.json()["id"]
        self.client.force_login(self.administrator)
        claimed = self.client.post(
            "/api/workflow-jobs/claim/",
            data=json.dumps({"worker_identity_reference": "worker:api", "lease_seconds": 60}),
            content_type="application/json",
        )
        self.assertEqual(claimed.status_code, 200, claimed.content)
        self.assertEqual(claimed.json()["job"]["id"], job_id)
        completed = self.client.post(
            f"/api/workflow-jobs/{job_id}/complete/",
            data=json.dumps(
                {
                    "worker_identity_reference": "worker:api",
                    "completion_idempotency_key": "api:complete",
                    "result": {"artifact_reference": "result:api"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(completed.status_code, 200, completed.content)
        self.assertEqual(completed.json()["status"], WorkflowJob.Status.SUCCEEDED)
        self.client.force_login(self.other_teacher)
        self.assertEqual(self.client.get(f"/api/workflows/{workflow_id}/").status_code, 403)
