from typing import Any


def build_filter_conditions(params: Any) -> tuple[list[str], dict]:
    """
    Build SQL WHERE clause fragments and bind params from a SearchRequest.
    Conditions apply to aliases: d = documents, m = document_metadata.
    Returns (conditions, bind_params).
    """
    conditions: list[str] = []
    bind: dict = {}

    # Always exclude parent container documents unless explicitly requested
    if not params.include_parents:
        conditions.append(
            "d.id NOT IN (SELECT DISTINCT parent_document_id FROM documents WHERE parent_document_id IS NOT NULL)"
        )

    # Always restrict to complete documents
    conditions.append("d.status = 'complete'")

    if params.doc_type:
        conditions.append("d.doc_type = :doc_type")
        bind["doc_type"] = params.doc_type

    if params.source:
        conditions.append("d.source = :source")
        bind["source"] = params.source

    if params.jurisdiction:
        conditions.append("m.jurisdiction = :jurisdiction")
        bind["jurisdiction"] = params.jurisdiction.upper()

    if params.facility_name:
        conditions.append("m.facility_name ILIKE :facility_name")
        bind["facility_name"] = f"%{params.facility_name}%"

    if params.inspector_name:
        conditions.append("m.inspector_name ILIKE :inspector_name")
        bind["inspector_name"] = f"%{params.inspector_name}%"

    if params.reference_number:
        conditions.append("m.reference_number = :reference_number")
        bind["reference_number"] = params.reference_number

    if params.categories:
        # OR logic: document must have at least one of the selected categories
        conditions.append("m.categories && CAST(:categories AS text[])")
        bind["categories"] = list(params.categories)

    if params.species:
        # OR logic: document must mention at least one of the selected species
        conditions.append("m.species && CAST(:species AS text[])")
        bind["species"] = list(params.species)

    if params.date_from:
        conditions.append("m.inspection_date >= :date_from")
        bind["date_from"] = params.date_from

    if params.date_to:
        conditions.append("m.inspection_date <= :date_to")
        bind["date_to"] = params.date_to

    return conditions, bind


def where_clause(conditions: list[str]) -> str:
    return "WHERE " + " AND ".join(conditions) if conditions else ""
