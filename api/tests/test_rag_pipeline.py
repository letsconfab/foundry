from sqlalchemy.orm import Session

from models import ConfabDeployment
from services import rag_pipeline


def test_normalize_rag_files_decodes_names_and_deduplicates():
    files = rag_pipeline._normalize_rag_files(
        [
            {"path": "confabs/3911/A%20Loving%20Organization.pdf", "size": 123},
            {"file_path": "confabs/3911/A%20Loving%20Organization.pdf", "size": 123},
            "PURPOSE.md",
        ],
        "confabs/3911",
    )

    assert files == [
        {
            "id": "confabs/3911/A%20Loving%20Organization.pdf",
            "path": "confabs/3911/A%20Loving%20Organization.pdf",
            "name": "A Loving Organization.pdf",
            "type": "file",
            "size": 123,
            "content_type": None,
            "updated_at": None,
        },
        {
            "id": "confabs/3911/PURPOSE.md",
            "path": "confabs/3911/PURPOSE.md",
            "name": "PURPOSE.md",
            "type": "file",
            "size": None,
            "content_type": None,
            "updated_at": None,
        },
    ]


async def test_list_rag_pipeline_documents_marks_expected_files(monkeypatch, db: Session, test_confab):
    deployment = ConfabDeployment(
        confab_id=test_confab.id,
        user_id=test_confab.user_id,
        status="running",
        profile_name="confab-1-test",
        model_id="confab-1-test",
        container_name="hermes-confab-1-test",
        profile_host_path="/tmp/confab-1-test",
        api_port=8700,
        api_server_key_hash="hash",
        api_base_url_external="http://localhost:8700/v1",
        api_base_url_internal="http://hermes-confab-1-test:8642/v1",
        rag_workspace=f"confabs/{test_confab.id}",
        rag_prefix=f"confabs/{test_confab.id}/",
        last_sync_result={
            "uploaded": 5,
            "indexed": True,
            "classical_indexed": True,
            "errors": [],
            "evaluation": {"status": "passed"},
        },
    )
    db.add(deployment)
    db.commit()

    async def fake_files(prefix):
        return [
            {"id": f"{prefix}/PURPOSE.md", "path": f"{prefix}/PURPOSE.md", "name": "PURPOSE.md", "type": "file"},
            {"id": f"{prefix}/extra.pdf", "path": f"{prefix}/extra.pdf", "name": "extra.pdf", "type": "file"},
        ]

    monkeypatch.setattr(rag_pipeline, "_list_raganything_files", fake_files)

    result = await rag_pipeline.list_rag_pipeline_documents(db, test_confab)

    assert result["deployment_status"] == "running"
    assert result["rag_workspace"] == f"confabs/{test_confab.id}"
    assert result["last_sync"]["uploaded"] == 5
    assert result["evaluation"] == {"status": "passed"}
    assert result["file_count"] == 2
    purpose = next(file for file in result["files"] if file["name"] == "PURPOSE.md")
    extra = next(file for file in result["files"] if file["name"] == "extra.pdf")
    assert purpose["expected"] is True
    assert extra["expected"] is False
    expected_purpose = next(item for item in result["expected_documents"] if item["name"] == "PURPOSE.md")
    assert expected_purpose["present_in_raganything"] is True


async def test_list_rag_pipeline_documents_returns_errors_when_raganything_unavailable(monkeypatch, db, test_confab):
    async def failing_files(_prefix):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(rag_pipeline, "_list_raganything_files", failing_files)

    result = await rag_pipeline.list_rag_pipeline_documents(db, test_confab)

    assert result["raganything_available"] is False
    assert result["files"] == []
    assert result["errors"] == ["connection refused"]
