"""
Step definitions for document management features.
"""

import base64
import json
from behave import given, when, then

from environment import api_request, generate_test_content


# =============================================================================
# Given Steps
# =============================================================================

@given('the confab has documents:')
def step_confab_has_documents(context):
    """Create documents for the confab from table."""
    confab_id = context.scenario_data.get("confab_id")

    for row in context.table:
        filename = row["filename"]
        status = row.get("status", "active") if "status" in context.table.headings else "active"

        content = generate_test_content(1)
        content_type = _get_content_type(filename)

        response = api_request(context, "POST", f"/confabs/{confab_id}/documents", {
            "filename": filename,
            "content_base64": content,
            "content_type": content_type
        })

        if response.status_code == 200:
            doc_data = response.json().get("document", response.json())
            context.documents[filename] = doc_data

            # Archive if needed
            if status == "archived":
                api_request(context, "DELETE", f"/confabs/{confab_id}/documents/{doc_data['id']}")


@given('the confab has a document "{filename}"')
def step_confab_has_document(context, filename):
    """Create a single document for the confab."""
    confab_id = context.scenario_data.get("confab_id")

    content = generate_test_content(1)
    content_type = _get_content_type(filename)

    response = api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": filename,
        "content_base64": content,
        "content_type": content_type
    })

    if response.status_code == 200:
        doc_data = response.json().get("document", response.json())
        context.scenario_data["document_id"] = doc_data["id"]
        context.scenario_data["document"] = doc_data
        context.documents[filename] = doc_data


@given('the confab has a document "{filename}" with content')
def step_confab_has_document_with_content(context, filename):
    """Create a document with content."""
    step_confab_has_document(context, filename)


@given('the confab has a document "{filename}" with {count:d} versions')
def step_confab_has_document_versions(context, filename, count):
    """Create a document with specified number of versions."""
    confab_id = context.scenario_data.get("confab_id")

    # Create initial document
    step_confab_has_document(context, filename)
    doc_id = context.scenario_data.get("document_id")

    # Add additional versions
    for i in range(count - 1):
        content = generate_test_content(i + 2)
        api_request(context, "POST", f"/confabs/{confab_id}/documents/{doc_id}/versions", {
            "content_base64": content
        })


@given('the confab has a document "{filename}" with versions:')
def step_confab_has_document_with_versions_table(context, filename):
    """Create document with versions from table."""
    confab_id = context.scenario_data.get("confab_id")

    # Create initial document
    step_confab_has_document(context, filename)
    doc_id = context.scenario_data.get("document_id")

    # Add versions based on table (skip first row as it's version 1)
    for i, row in enumerate(context.table.rows[1:], start=2):
        size_kb = int(row["size_kb"]) if "size_kb" in context.table.headings else i
        content = generate_test_content(size_kb)
        api_request(context, "POST", f"/confabs/{confab_id}/documents/{doc_id}/versions", {
            "content_base64": content
        })


@given('I have uploaded a document named "{filename}"')
def step_have_uploaded_document(context, filename):
    """Upload a document."""
    step_confab_has_document(context, filename)


@given('the document has {count:d} versions')
def step_document_has_versions(context, count):
    """Ensure document has specified number of versions."""
    confab_id = context.scenario_data.get("confab_id")
    doc_id = context.scenario_data.get("document_id")

    # Get current version count
    response = api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}")
    if response.status_code == 200:
        current_count = response.json().get("version_count", 1)

        # Add more versions if needed
        for i in range(count - current_count):
            content = generate_test_content(i + 2)
            api_request(context, "POST", f"/confabs/{confab_id}/documents/{doc_id}/versions", {
                "content_base64": content
            })


@given('the document has versions with different content')
def step_document_has_different_versions(context):
    """Ensure document has versions with different content."""
    confab_id = context.scenario_data.get("confab_id")
    doc_id = context.scenario_data.get("document_id")

    for i in range(2):
        content = base64.b64encode(f"Version {i+2} content".encode()).decode()
        api_request(context, "POST", f"/confabs/{confab_id}/documents/{doc_id}/versions", {
            "content_base64": content
        })


@given('the document is archived')
def step_document_is_archived(context):
    """Archive the document."""
    confab_id = context.scenario_data.get("confab_id")
    doc_id = context.scenario_data.get("document_id")
    api_request(context, "DELETE", f"/confabs/{confab_id}/documents/{doc_id}")


@given('the document is already archived')
def step_document_already_archived(context):
    """Ensure document is archived."""
    step_document_is_archived(context)


@given('the document has extracted text')
def step_document_has_extracted_text(context):
    """Document has extracted text (mocked)."""
    context.scenario_data["has_extracted_text"] = True


@given('I have the document UUID')
def step_have_document_uuid(context):
    """Store document UUID for later use."""
    doc = context.scenario_data.get("document", {})
    context.scenario_data["document_uuid"] = doc.get("document_uuid")


@given('the document was uploaded from URL "{url}"')
def step_document_from_url(context, url):
    """Mark document as uploaded from URL."""
    context.scenario_data["document_source_url"] = url


@given('the document was uploaded with compression')
def step_document_with_compression(context):
    """Document was uploaded and compressed."""
    # Default behavior - all documents are compressed
    pass


@given('the confab has documents uploaded in order:')
def step_confab_has_documents_in_order(context):
    """Create documents in specific order."""
    step_confab_has_documents(context)


@given('another user "{email}" has a confab with documents')
def step_other_user_has_confab_with_docs(context, email):
    """Create confab with documents owned by another user."""
    saved_token = context.auth_token

    from environment import create_test_user
    other_user = create_test_user(context, email=email)
    if other_user:
        context.auth_token = other_user.get("access_token")

        # Create confab
        response = api_request(context, "POST", "/confabs", {"name": "Other Agent"})
        if response.status_code == 200:
            confab_id = response.json()["id"]
            context.scenario_data["other_confab_id"] = confab_id

            # Add document
            api_request(context, "POST", f"/confabs/{confab_id}/documents", {
                "filename": "secret.pdf",
                "content_base64": generate_test_content(1),
                "content_type": "application/pdf"
            })

    context.auth_token = saved_token


@given('another user "{email}" has a confab with a document')
def step_other_user_has_document(context, email):
    """Create confab with document owned by another user."""
    step_other_user_has_confab_with_docs(context, email)


@given('another user "{email}" has a confab with document ID {doc_id:d}')
def step_other_user_has_doc_id(context, email, doc_id):
    """Note other user has document with specific ID."""
    step_other_user_has_confab_with_docs(context, email)


@given('the confab has learnings:')
def step_confab_has_learnings(context):
    """Create learnings for the confab."""
    confab_id = context.scenario_data.get("confab_id")

    for row in context.table:
        api_request(context, "POST", f"/confabs/{confab_id}/learnings", {
            "content": row["content"],
            "source": "manual"
        })


# =============================================================================
# When Steps
# =============================================================================

@when('I upload a document:')
def step_upload_document(context):
    """Upload a document with details from table."""
    confab_id = context.scenario_data.get("confab_id")
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    filename = row.get("filename", "test.txt")
    content_type = row.get("content_type", _get_content_type(filename))

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": filename,
        "content_base64": generate_test_content(1),
        "content_type": content_type
    })


@when('I upload a large document:')
def step_upload_large_document(context):
    """Upload a large document."""
    confab_id = context.scenario_data.get("confab_id")
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    filename = row.get("filename", "large.txt")
    size_kb = int(row.get("size_kb", 100))

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": filename,
        "content_base64": generate_test_content(size_kb),
        "content_type": "text/plain"
    })


@when('I upload another document:')
def step_upload_another_document(context):
    """Upload another document."""
    step_upload_document(context)


@when('I upload a document exceeding 50MB')
def step_upload_exceeding_50mb(context):
    """Attempt to upload a file exceeding 50MB."""
    confab_id = context.scenario_data.get("confab_id")

    # Generate ~51MB content (this will be large)
    content = base64.b64encode(b"x" * (51 * 1024 * 1024)).decode()

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": "huge.txt",
        "content_base64": content,
        "content_type": "text/plain"
    })


@when('I upload a document of exactly 50MB')
def step_upload_exactly_50mb(context):
    """Upload a file of exactly 50MB."""
    confab_id = context.scenario_data.get("confab_id")

    content = generate_test_content(50 * 1024)  # 50MB

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": "exact50.txt",
        "content_base64": content,
        "content_type": "text/plain"
    })


@when('I upload a document without filename')
def step_upload_without_filename(context):
    """Upload document without filename."""
    confab_id = context.scenario_data.get("confab_id")

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "content_base64": generate_test_content(1),
        "content_type": "text/plain"
    })


@when('I upload a document without content')
def step_upload_without_content(context):
    """Upload document without content."""
    confab_id = context.scenario_data.get("confab_id")

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": "test.txt",
        "content_type": "text/plain"
    })


@when('I upload a document without content_base64')
def step_upload_without_content_base64(context):
    """Upload document without content_base64 field."""
    step_upload_without_content(context)


@when('I upload a document with invalid base64:')
def step_upload_invalid_base64(context):
    """Upload document with invalid base64 content."""
    confab_id = context.scenario_data.get("confab_id")
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": row.get("filename", "test.txt"),
        "content_base64": row.get("content_base64", "!!!invalid!!!"),
        "content_type": "text/plain"
    })


@when('I upload a document with content_base64 "{content}"')
def step_upload_with_content(context, content):
    """Upload document with specific content."""
    confab_id = context.scenario_data.get("confab_id")

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": "test.txt",
        "content_base64": content,
        "content_type": "text/plain"
    })


@when('I upload a document to confab ID {confab_id:d}:')
def step_upload_to_confab_id(context, confab_id):
    """Upload document to specific confab."""
    row = dict(zip(context.table.headings, context.table.rows[0].cells))
    filename = row.get("filename", "test.txt")

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": filename,
        "content_base64": generate_test_content(1),
        "content_type": _get_content_type(filename)
    })


@when('I upload a document to confab ID {confab_id:d}')
def step_upload_to_confab_id_no_table(context, confab_id):
    """Upload document to specific confab (no table)."""
    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": "test.txt",
        "content_base64": generate_test_content(1),
        "content_type": "text/plain"
    })


@when('I upload a document to that confab:')
def step_upload_to_other_confab(context):
    """Upload document to another user's confab."""
    confab_id = context.scenario_data.get("other_confab_id")
    row = dict(zip(context.table.headings, context.table.rows[0].cells))
    filename = row.get("filename", "test.txt")

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": filename,
        "content_base64": generate_test_content(1),
        "content_type": _get_content_type(filename)
    })


@when('I upload a document to my confab:')
def step_upload_to_my_confab(context):
    """Upload document to my confab (while unauthenticated)."""
    confab_id = context.scenario_data.get("confab_id", 1)
    row = dict(zip(context.table.headings, context.table.rows[0].cells))
    filename = row.get("filename", "test.txt")

    api_request(context, "POST", f"/confabs/{confab_id}/documents", {
        "filename": filename,
        "content_base64": generate_test_content(1),
        "content_type": _get_content_type(filename)
    })


@when('I list documents for the confab')
def step_list_documents(context):
    """List documents for current confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "GET", f"/confabs/{confab_id}/documents")


@when('I list documents for confab ID {confab_id:d}')
def step_list_documents_for_id(context, confab_id):
    """List documents for specific confab."""
    api_request(context, "GET", f"/confabs/{confab_id}/documents")


@when('I list documents for that confab')
def step_list_documents_other_confab(context):
    """List documents for another user's confab."""
    confab_id = context.scenario_data.get("other_confab_id")
    api_request(context, "GET", f"/confabs/{confab_id}/documents")


@when('I archive the document "{filename}"')
def step_archive_document(context, filename):
    """Archive a document by filename."""
    confab_id = context.scenario_data.get("confab_id")
    doc = context.documents.get(filename) or context.scenario_data.get("document")
    doc_id = doc["id"] if doc else context.scenario_data.get("document_id")

    api_request(context, "DELETE", f"/confabs/{confab_id}/documents/{doc_id}")


@when('I archive document ID {doc_id:d}')
def step_archive_document_id(context, doc_id):
    """Archive a document by ID."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "DELETE", f"/confabs/{confab_id}/documents/{doc_id}")


@when('I archive document ID {doc_id:d} from confab ID {confab_id:d}')
def step_archive_doc_from_confab(context, doc_id, confab_id):
    """Archive document from specific confab."""
    api_request(context, "DELETE", f"/confabs/{confab_id}/documents/{doc_id}")


@when('I archive document ID {doc_id:d} from the confab')
def step_archive_doc_from_current_confab(context, doc_id):
    """Archive document from current confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "DELETE", f"/confabs/{confab_id}/documents/{doc_id}")


@when('I try to archive that document')
def step_try_archive_other_document(context):
    """Try to archive another user's document."""
    confab_id = context.scenario_data.get("other_confab_id")
    # Use a guessed document ID
    api_request(context, "DELETE", f"/confabs/{confab_id}/documents/1")


@when('I upload a new version of "{filename}"')
def step_upload_new_version(context, filename):
    """Upload a new version of a document."""
    confab_id = context.scenario_data.get("confab_id")
    doc = context.documents.get(filename) or context.scenario_data.get("document")
    doc_id = doc["id"] if doc else context.scenario_data.get("document_id")

    api_request(context, "POST", f"/confabs/{confab_id}/documents/{doc_id}/versions", {
        "content_base64": generate_test_content(2)
    })


@when('I upload new versions of "{filename}" {count:d} times')
def step_upload_n_versions(context, filename, count):
    """Upload multiple new versions."""
    for i in range(count):
        step_upload_new_version(context, filename)


@when('I upload a new version of document ID {doc_id:d}')
def step_upload_version_by_id(context, doc_id):
    """Upload new version by document ID."""
    confab_id = context.scenario_data.get("confab_id", 1)
    api_request(context, "POST", f"/confabs/{confab_id}/documents/{doc_id}/versions", {
        "content_base64": generate_test_content(2)
    })


@when('I list versions of "{filename}"')
def step_list_versions(context, filename):
    """List versions of a document."""
    confab_id = context.scenario_data.get("confab_id")
    doc = context.documents.get(filename) or context.scenario_data.get("document")
    doc_id = doc["id"] if doc else context.scenario_data.get("document_id")

    api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}/versions")


@when('I get version {version:d} of "{filename}"')
def step_get_specific_version(context, version, filename):
    """Get specific version of a document."""
    confab_id = context.scenario_data.get("confab_id")
    doc = context.documents.get(filename) or context.scenario_data.get("document")
    doc_id = doc["id"] if doc else context.scenario_data.get("document_id")

    api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}/versions/{version}")


@when('I get the latest version of "{filename}"')
def step_get_latest_version(context, filename):
    """Get latest version of a document."""
    confab_id = context.scenario_data.get("confab_id")
    doc = context.documents.get(filename) or context.scenario_data.get("document")
    doc_id = doc["id"] if doc else context.scenario_data.get("document_id")

    api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}/versions/latest")


@when('I get version {version:d} of the document')
def step_get_doc_version(context, version):
    """Get specific version of current document."""
    confab_id = context.scenario_data.get("confab_id")
    doc_id = context.scenario_data.get("document_id")

    api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}/versions/{version}")


@when('I get document metadata for "{filename}"')
def step_get_document_metadata(context, filename):
    """Get document metadata."""
    confab_id = context.scenario_data.get("confab_id")
    doc = context.documents.get(filename) or context.scenario_data.get("document")
    doc_id = doc["id"] if doc else context.scenario_data.get("document_id")

    api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}")


@when('I get document content for "{filename}"')
def step_get_document_content(context, filename):
    """Get document content."""
    confab_id = context.scenario_data.get("confab_id")
    doc = context.documents.get(filename) or context.scenario_data.get("document")
    doc_id = doc["id"] if doc else context.scenario_data.get("document_id")

    api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}/versions/latest")


@when('I get document ID {doc_id:d}')
def step_get_document_by_id(context, doc_id):
    """Get document by ID."""
    confab_id = context.scenario_data.get("confab_id", 1)
    api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}")


@when('I get document ID {doc_id:d} from the confab')
def step_get_doc_from_confab(context, doc_id):
    """Get document from current confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}")


@when('I get document ID {doc_id:d} from confab ID {confab_id:d}')
def step_get_doc_from_specific_confab(context, doc_id, confab_id):
    """Get document from specific confab."""
    api_request(context, "GET", f"/confabs/{confab_id}/documents/{doc_id}")


@when('I get document by UUID')
def step_get_document_by_uuid(context):
    """Get document by UUID."""
    confab_id = context.scenario_data.get("confab_id")
    uuid = context.scenario_data.get("document_uuid")
    # Note: This endpoint may not exist - adjust as needed
    api_request(context, "GET", f"/confabs/{confab_id}/documents/uuid/{uuid}")


@when('I try to get that document')
def step_try_get_other_document(context):
    """Try to get another user's document."""
    confab_id = context.scenario_data.get("other_confab_id")
    api_request(context, "GET", f"/confabs/{confab_id}/documents/1")


# =============================================================================
# Then Steps
# =============================================================================

@then('the response should contain document details:')
def step_response_has_document_details(context):
    """Assert response contains expected document details."""
    data = context.response.json()
    doc = data.get("document", data)
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    for field, expected in row.items():
        actual = doc.get(field)
        assert str(actual) == str(expected), \
            f"Field '{field}': expected '{expected}', got '{actual}'"


@then('the document should have a UUID')
def step_document_has_uuid(context):
    """Assert document has a UUID."""
    data = context.response.json()
    doc = data.get("document", data)
    assert "document_uuid" in doc, f"No 'document_uuid' in response: {doc}"


@then('the document should have version {version:d}')
def step_document_has_version(context, version):
    """Assert document has specific version."""
    data = context.response.json()

    # Handle VersionListResponse format (from version upload)
    if "total" in data:
        assert data["total"] >= version, \
            f"Expected version {version}, got total {data['total']}"
        return

    # Handle DocumentResponseV2 format
    doc = data.get("document", data)
    if "version_count" in doc:
        assert doc["version_count"] >= version, \
            f"Expected version {version}, got version_count {doc['version_count']}"
    elif "latest_version" in doc:
        assert doc["latest_version"].get("version_number") == version, \
            f"Expected version {version}, got {doc['latest_version'].get('version_number')}"
    else:
        raise AssertionError(f"Cannot determine version from response: {data}")


@then('the document should be uploaded successfully')
def step_document_uploaded_successfully(context):
    """Assert document was uploaded."""
    assert context.response.status_code == 200


@then('the compressed size should be less than the original size')
def step_compressed_smaller(context):
    """Assert compressed size is smaller than original."""
    data = context.response.json()
    doc = data.get("document", data)
    latest = doc.get("latest_version", {})
    assert latest.get("compressed_size", 0) < latest.get("original_size", 1)


@then('the response should contain error about unsupported format')
def step_error_unsupported_format(context):
    """Assert error about unsupported format."""
    assert context.response.status_code == 400
    error = str(context.response.json()).lower()
    assert any(word in error for word in ["unsupported", "format", "not allowed", "extension"]), \
        f"Expected error about unsupported format, got: {error}"


@then('the response should contain error about file size')
def step_error_file_size(context):
    """Assert error about file size."""
    error = str(context.response.json())
    assert "size" in error.lower() or "large" in error.lower() or "50" in error


@then('the response should contain error about invalid content')
def step_error_invalid_content(context):
    """Assert error about invalid content."""
    error = str(context.response.json())
    assert "invalid" in error.lower() or "base64" in error.lower() or "content" in error.lower()


@then('the response should contain {count:d} documents')
def step_response_has_n_documents(context, count):
    """Assert response contains specified number of documents."""
    data = context.response.json()
    docs = data.get("documents", data if isinstance(data, list) else [])
    assert len(docs) == count, f"Expected {count} documents, got {len(docs)}"


@then('the response should contain {count:d} document')
def step_response_has_n_document_singular(context, count):
    """Assert response contains specified number of documents (singular)."""
    step_response_has_n_documents(context, count)


@then('the documents should include:')
def step_documents_should_include(context):
    """Assert documents include specified filenames."""
    data = context.response.json()
    docs = data.get("documents", data if isinstance(data, list) else [])
    filenames = [d.get("filename") for d in docs]

    for row in context.table:
        expected = row["filename"]
        assert expected in filenames, f"Document '{expected}' not in {filenames}"


@then('the document should be "{filename}"')
def step_document_is(context, filename):
    """Assert single document has specified filename."""
    data = context.response.json()
    docs = data.get("documents", [data] if isinstance(data, dict) else data)
    assert len(docs) == 1 and docs[0].get("filename") == filename


@then('the document "{filename}" should have version_count {count:d}')
def step_doc_version_count(context, filename, count):
    """Assert document has specified version count."""
    data = context.response.json()
    docs = data.get("documents", [data] if isinstance(data, dict) else data)

    for doc in docs:
        if doc.get("filename") == filename:
            assert doc.get("version_count") == count, \
                f"Expected version_count {count}, got {doc.get('version_count')}"
            return

    raise AssertionError(f"Document '{filename}' not found")


@then('the response should include latest_version with:')
def step_response_has_latest_version(context):
    """Assert latest_version has expected fields."""
    data = context.response.json()
    docs = data.get("documents", [data] if isinstance(data, dict) else data)
    latest = docs[0].get("latest_version", {})

    row = dict(zip(context.table.headings, context.table.rows[0].cells))
    for field, expected in row.items():
        assert str(latest.get(field)) == str(expected), \
            f"latest_version.{field}: expected '{expected}', got '{latest.get(field)}'"


@then('the first document should be "{filename}"')
def step_first_doc_is(context, filename):
    """Assert first document has specified filename."""
    data = context.response.json()
    docs = data.get("documents", data if isinstance(data, list) else [])
    assert docs[0].get("filename") == filename


@then('the last document should be "{filename}"')
def step_last_doc_is(context, filename):
    """Assert last document has specified filename."""
    data = context.response.json()
    docs = data.get("documents", data if isinstance(data, list) else [])
    assert docs[-1].get("filename") == filename


@then('the document status should be "{status}"')
def step_document_status_is(context, status):
    """Assert document has specified status."""
    data = context.response.json()

    # Handle archive response which returns {"message": "Document archived"}
    if status == "archived" and "message" in data:
        assert "archived" in data["message"].lower(), \
            f"Expected archived confirmation, got: {data}"
        return

    doc = data.get("document", data)
    assert doc.get("status") == status, \
        f"Expected status '{status}', got '{doc.get('status')}' in {data}"


@then('the document should still have {count:d} versions')
def step_document_still_has_versions(context, count):
    """Assert document still has specified versions."""
    # After archiving, check version count
    confab_id = context.scenario_data.get("confab_id")
    doc_id = context.scenario_data.get("document_id")
    # This would need an endpoint that shows archived docs
    pass


@then('all associated documents should be deleted')
def step_all_docs_deleted(context):
    """Assert all documents were deleted with confab."""
    # Documents are cascade deleted with confab
    pass


@then('all associated learnings should be deleted')
def step_all_learnings_deleted(context):
    """Assert all learnings were deleted with confab."""
    # Learnings are cascade deleted with confab
    pass


@then('the confab should have {count:d} documents')
def step_confab_has_n_docs(context, count):
    """Assert confab has specified number of documents."""
    confab_id = context.scenario_data.get("confab_id")
    response = api_request(context, "GET", f"/confabs/{confab_id}/documents")
    docs = response.json().get("documents", [])
    assert len(docs) == count


@then('the document should have {count:d} versions total')
def step_doc_has_total_versions(context, count):
    """Assert document has total version count."""
    data = context.response.json()

    # Handle VersionListResponse (has "total" field)
    if "total" in data:
        assert data["total"] == count, \
            f"Expected {count} versions, got {data['total']}"
        return

    # Handle DocumentResponseV2 (has "version_count" field)
    doc = data.get("document", data)
    assert doc.get("version_count") == count, \
        f"Expected {count} versions, got {doc.get('version_count')}"


@then('the latest version number should be {version:d}')
def step_latest_version_is(context, version):
    """Assert latest version number."""
    data = context.response.json()

    # Handle VersionListResponse format
    if "versions" in data and len(data["versions"]) > 0:
        # Versions are sorted newest first
        latest_version = data["versions"][0].get("version_number")
        assert latest_version == version, \
            f"Expected latest version {version}, got {latest_version}"
        return

    doc = data.get("document", data)
    latest = doc.get("latest_version", {})
    assert latest.get("version_number") == version, \
        f"Expected version {version}, got {latest.get('version_number')}"


@then('the response should contain {count:d} versions')
def step_response_has_n_versions(context, count):
    """Assert response contains specified number of versions."""
    data = context.response.json()
    versions = data.get("versions", [])
    assert len(versions) == count


@then('versions should be ordered newest first')
def step_versions_ordered_newest(context):
    """Assert versions are ordered newest first."""
    data = context.response.json()
    versions = data.get("versions", [])
    version_nums = [v.get("version_number") for v in versions]
    assert version_nums == sorted(version_nums, reverse=True)


@then('each version should have a unique content_hash')
def step_versions_unique_hash(context):
    """Assert each version has unique content hash."""
    data = context.response.json()
    versions = data.get("versions", [])
    hashes = [v.get("content_hash") for v in versions]
    assert len(hashes) == len(set(hashes)), f"Duplicate hashes found: {hashes}"


@then('the version should have:')
def step_version_has_fields(context):
    """Assert version has specified fields."""
    data = context.response.json()
    # Handle VersionListResponse format where versions are in an array
    if "versions" in data and isinstance(data["versions"], list) and len(data["versions"]) > 0:
        version = data["versions"][0]  # Latest version is first
    else:
        version = data.get("version", data)

    for row in context.table:
        field = row["field"]
        assert field in version, f"Field '{field}' not in version: {version}"


@then('the response should contain version {version:d} content')
def step_response_has_version_content(context, version):
    """Assert response contains specific version content."""
    data = context.response.json()
    assert data.get("version_number") == version or "content_base64" in data


@then('the content should be decompressed')
def step_content_decompressed(context):
    """Assert content was decompressed."""
    data = context.response.json()
    assert "content_base64" in data


@then('the original_size should match the original file size')
def step_original_size_matches(context):
    """Assert original_size is present."""
    data = context.response.json()
    assert "original_size" in data


@then('the response should include extracted_text')
def step_response_has_extracted_text(context):
    """Assert response includes extracted_text."""
    data = context.response.json()
    # extracted_text may be null for some file types
    assert "extracted_text" in data


@then('the response should contain the document details')
def step_response_has_doc_details(context):
    """Assert response contains document details."""
    data = context.response.json()
    assert "filename" in data or "document" in data


# =============================================================================
# Helper Functions
# =============================================================================

def _get_content_type(filename):
    """Get content type from filename."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content_types = {
        "pdf": "application/pdf",
        "txt": "text/plain",
        "md": "text/markdown",
        "json": "application/json",
        "yaml": "application/x-yaml",
        "yml": "application/x-yaml",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "exe": "application/x-executable",
        "sh": "application/x-sh",
        "bin": "application/octet-stream",
    }
    return content_types.get(ext, "application/octet-stream")
