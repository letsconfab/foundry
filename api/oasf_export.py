"""
OASF Export Module - Generates agent.oasf.yaml from Confab data.

Follows the Open Agent Specification Format (OASF) structure:
https://github.com/agntcy/oasf
"""

import yaml
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from models import Confab, ConfabLearning, User
from sqlalchemy.orm import Session


@dataclass
class OASFAuthor:
    """OASF author entry."""
    name: str
    email: Optional[str] = None
    url: Optional[str] = None


@dataclass
class OASFLanguageModel:
    """OASF language model configuration module."""
    provider: str
    model: str
    api_base: Optional[str] = None
    temperature: Optional[float] = None


@dataclass
class OASFGuardrail:
    """OASF guardrail rule."""
    id: str
    rule: str
    severity: str = "error"
    enabled: bool = True


@dataclass
class OASFTestScenario:
    """OASF test scenario."""
    id: str
    name: str
    input: str
    expected_behavior: str
    tags: List[str] = field(default_factory=list)


@dataclass
class OASFKnowledge:
    """OASF knowledge entry (learning)."""
    id: str
    content: str
    summary: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    source: str = "manual"
    status: str = "approved"
    created_at: Optional[str] = None


@dataclass
class OASFRecord:
    """OASF Record - the primary data structure for agent representation."""
    name: str
    version: str
    schema_version: str
    description: str
    authors: List[OASFAuthor]
    created_at: str
    skills: List[int]
    domains: List[str]

    # Core content
    purpose: Optional[str] = None
    guardrails: List[OASFGuardrail] = field(default_factory=list)
    tests: List[OASFTestScenario] = field(default_factory=list)
    knowledge: List[OASFKnowledge] = field(default_factory=list)

    # Runtime configuration
    language_model: Optional[OASFLanguageModel] = None

    # Metadata
    annotations: Dict[str, Any] = field(default_factory=dict)


def generate_oasf_record(confab: Confab, db: Session) -> OASFRecord:
    """
    Generate an OASF Record from a Confab model.

    Args:
        confab: The Confab model instance
        db: Database session for loading related data

    Returns:
        OASFRecord dataclass ready for export
    """
    # Get author (owner)
    owner = db.query(User).filter(User.id == confab.user_id).first()
    authors = []
    if owner:
        authors.append(OASFAuthor(
            name=owner.name,
            email=owner.email
        ))

    # Parse guardrails from JSON
    guardrails = []
    if confab.guardrails:
        for i, g in enumerate(confab.guardrails):
            if isinstance(g, dict):
                guardrails.append(OASFGuardrail(
                    id=g.get("id", f"guardrail-{i+1}"),
                    rule=g.get("rule", str(g)),
                    severity=g.get("severity", "error"),
                    enabled=g.get("enabled", True)
                ))
            else:
                guardrails.append(OASFGuardrail(
                    id=f"guardrail-{i+1}",
                    rule=str(g)
                ))

    # Parse tests from JSON
    tests = []
    if confab.tests:
        for i, t in enumerate(confab.tests):
            if isinstance(t, dict):
                tests.append(OASFTestScenario(
                    id=t.get("id", f"test-{i+1}"),
                    name=t.get("name", f"Test {i+1}"),
                    input=t.get("input", ""),
                    expected_behavior=t.get("expected_behavior", ""),
                    tags=t.get("tags", [])
                ))

    # Load approved learnings as knowledge
    knowledge = []
    learnings = db.query(ConfabLearning).filter(
        ConfabLearning.confab_id == confab.id,
        ConfabLearning.status == "approved"
    ).all()
    for learning in learnings:
        knowledge.append(OASFKnowledge(
            id=f"learning-{learning.id}",
            content=learning.content,
            summary=learning.summary,
            tags=learning.tags or [],
            source=learning.source,
            status=learning.status,
            created_at=learning.created_at.isoformat() if learning.created_at else None
        ))

    # Build language model config
    language_model = None
    if confab.model_provider and confab.model_name:
        language_model = OASFLanguageModel(
            provider=confab.model_provider,
            model=confab.model_name,
            temperature=confab.temperature
        )

    # Build the record
    record = OASFRecord(
        name=confab.name,
        version=confab.version,
        schema_version=confab.oasf_schema_version or "1.0.0",
        description=confab.description or "",
        authors=authors,
        created_at=confab.created_at.isoformat() if confab.created_at else datetime.now().isoformat(),
        skills=confab.skills or [],
        domains=confab.domains or [],
        purpose=confab.purpose,
        guardrails=guardrails,
        tests=tests,
        knowledge=knowledge,
        language_model=language_model,
        annotations={
            "foundry_id": confab.id,
            "status": confab.status
        }
    )

    return record


def oasf_record_to_dict(record: OASFRecord) -> Dict[str, Any]:
    """
    Convert an OASFRecord to a dictionary suitable for YAML export.
    Filters out None values and empty lists for cleaner output.
    """
    def clean_dict(d):
        """Recursively remove None values and empty collections."""
        if isinstance(d, dict):
            return {k: clean_dict(v) for k, v in d.items()
                    if v is not None and v != [] and v != {}}
        elif isinstance(d, list):
            return [clean_dict(i) for i in d if i is not None]
        else:
            return d

    # Convert dataclass to dict
    result = {}

    # Core fields
    result["name"] = record.name
    result["version"] = record.version
    result["schema_version"] = record.schema_version
    result["description"] = record.description
    result["created_at"] = record.created_at

    # Authors
    if record.authors:
        result["authors"] = [asdict(a) for a in record.authors]

    # Skills and domains
    if record.skills:
        result["skills"] = record.skills
    if record.domains:
        result["domains"] = record.domains

    # Purpose (as module)
    if record.purpose:
        result["purpose"] = record.purpose

    # Guardrails (as module)
    if record.guardrails:
        result["guardrails"] = [asdict(g) for g in record.guardrails]

    # Tests (as module)
    if record.tests:
        result["tests"] = [asdict(t) for t in record.tests]

    # Knowledge (as module)
    if record.knowledge:
        result["knowledge"] = [asdict(k) for k in record.knowledge]

    # Language model (as module)
    if record.language_model:
        result["language_model"] = asdict(record.language_model)

    # Annotations
    if record.annotations:
        result["annotations"] = record.annotations

    return clean_dict(result)


def export_confab_to_oasf_yaml(confab: Confab, db: Session) -> str:
    """
    Export a Confab to OASF YAML format.

    Args:
        confab: The Confab model instance
        db: Database session

    Returns:
        YAML string representation of the OASF record
    """
    record = generate_oasf_record(confab, db)
    record_dict = oasf_record_to_dict(record)

    # Generate YAML with nice formatting
    yaml_content = yaml.dump(
        record_dict,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120
    )

    # Add header comment
    header = f"""# OASF Agent Definition
# Generated by Let's Confab Foundry
# https://github.com/agntcy/oasf

"""

    return header + yaml_content


def generate_purpose_md(confab: Confab) -> str:
    """Generate PURPOSE.md content from confab purpose."""
    return f"""# {confab.name}

## Purpose

{confab.purpose or "Purpose not yet defined."}

## Description

{confab.description or "No description provided."}

---
*Generated by Let's Confab Foundry*
"""


def generate_guardrails_md(confab: Confab) -> str:
    """Generate GUARDRAILS.md content from confab guardrails."""
    content = f"""# Guardrails for {confab.name}

"""

    if confab.guardrails:
        for i, g in enumerate(confab.guardrails, 1):
            if isinstance(g, dict):
                rule = g.get("rule", str(g))
                severity = g.get("severity", "error")
                enabled = g.get("enabled", True)
                status = "enabled" if enabled else "disabled"
                content += f"## Rule {i} [{severity}] ({status})\n\n{rule}\n\n"
            else:
                content += f"## Rule {i}\n\n{g}\n\n"
    else:
        content += "No guardrails defined yet.\n"

    content += """---
*Generated by Let's Confab Foundry*
"""
    return content


def generate_tests_md(confab: Confab) -> str:
    """Generate TESTS.md content from confab tests."""
    content = f"""# Test Scenarios for {confab.name}

"""

    if confab.tests:
        for i, t in enumerate(confab.tests, 1):
            if isinstance(t, dict):
                name = t.get("name", f"Test {i}")
                input_text = t.get("input", "")
                expected = t.get("expected_behavior", "")
                tags = t.get("tags", [])

                content += f"## {name}\n\n"
                if tags:
                    content += f"**Tags:** {', '.join(tags)}\n\n"
                content += f"**Input:**\n```\n{input_text}\n```\n\n"
                content += f"**Expected Behavior:**\n{expected}\n\n"
            else:
                content += f"## Test {i}\n\n{t}\n\n"
    else:
        content += "No test scenarios defined yet.\n"

    content += """---
*Generated by Let's Confab Foundry*
"""
    return content


def generate_all_export_files(confab: Confab, db: Session) -> Dict[str, str]:
    """
    Generate all export files for a confab.

    Returns:
        Dict mapping filename to content:
        - agent.oasf.yaml
        - PURPOSE.md
        - GUARDRAILS.md
        - TESTS.md
    """
    return {
        "agent.oasf.yaml": export_confab_to_oasf_yaml(confab, db),
        "PURPOSE.md": generate_purpose_md(confab),
        "GUARDRAILS.md": generate_guardrails_md(confab),
        "TESTS.md": generate_tests_md(confab),
    }
