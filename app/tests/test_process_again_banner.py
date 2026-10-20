"""A failed Process again says so on the recording page (v1.141.1): the
earlier transcript had stayed and looked like the new one landing with the
old speakers and names."""

import pytest
from core import viewer
from core.jobs import Job, JobState, Reason
from core.models import User
from core.recordings import Batch
from tests.helpers import signed_in
from tests.test_prepare import a_recording

PASSWORD = "a-long-enough-password"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


def test_the_page_says_the_last_process_again_failed(admin, tmp_path, settings, client):
    recording = a_recording(admin, tmp_path, settings)
    assert viewer.replacement_failed(recording) == ""
    again = Batch.objects.create(user=admin, is_reprocessing=True)
    job = Job.objects.create(
        recording=recording,
        batch=again,
        state=JobState.FAILED,
        failure_class=Reason.INTERNAL,
    )
    assert viewer.replacement_failed(recording) == Reason.MESSAGES[Reason.INTERNAL]
    signed_in(client, admin)
    page = client.get(f"/recording/{recording.pk}").content.decode()
    assert "The last Process again did not finish:" in page
    assert Reason.MESSAGES[Reason.INTERNAL] in page
    assert "This is the earlier transcript, kept." in page
    # Once it runs again, or lands, the banner goes.
    job.state = JobState.RUNNING
    job.save(update_fields=["state"])
    assert viewer.replacement_failed(recording) == ""
    assert viewer.being_replaced(recording) is True
