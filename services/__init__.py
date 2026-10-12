"""Services package for universal web applier."""

from services.page_lifecycle_service import PageLifecycleService
from services.dom_verifier import DOMDataMatcher
from services.field_interaction_service import FieldInteractionService
from services.form_application_pipeline import FormApplicationPipeline, FormPipelineResult
from services.form_filler_service import FormFillerService
from services.inspection_formatter_service import InspectionFormatterService
from services.inspection_service import InspectionService
from services.reactive_interaction_service import ReactiveInteractionService
from services.schema_merger import SchemaMerger
from services.target_descriptor import TargetDescriptor, TargetDescriptorParser

__all__ = [
    "PageLifecycleService",
    "DOMDataMatcher",
    "FieldInteractionService",
    "FormApplicationPipeline",
    "FormFillerService",
    "FormPipelineResult",
    "InspectionFormatterService",
    "InspectionService",
    "ReactiveInteractionService",
    "SchemaMerger",
    "TargetDescriptor",
    "TargetDescriptorParser",
]
