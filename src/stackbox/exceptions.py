class StackboxError(Exception):
    """Base exception for all STACKBOX errors."""


class PreflightError(StackboxError):
    """Host prerequisite check failed."""


class PortConflictError(PreflightError):
    """Required port is already in use on the host."""


class ZuulAPIError(StackboxError):
    """Zuul API request failed."""


class JobResolutionError(StackboxError):
    """Could not resolve Zuul job definition."""


class ContainerError(StackboxError):
    """Container operation failed."""


class ImageBuildError(ContainerError):
    """Container image build failed."""


class BootstrapError(StackboxError):
    """Service bootstrap step failed."""


class ConfigGenerationError(StackboxError):
    """Config file generation failed."""
