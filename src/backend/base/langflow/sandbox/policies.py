"""Security policy for sandboxed component execution: single sandbox profile only."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .sandbox_context import SandboxConfig

from loguru import logger


def is_lock_mode_enabled() -> bool:
    """Check if component locking mode is enabled via LANGFLOW_SANDBOX_LOCK_COMPONENTS."""
    return os.getenv('LANGFLOW_SANDBOX_LOCK_COMPONENTS', 'false').lower() in ('true', '1', 'yes')


# Essential environment variables
ENV = {
    "MATPLOTLIB_BACKEND": "Agg",  # Headless plotting
    "PYTHONPATH": "/opt/langflow/src/backend/base:/opt/src:/app/.venv/lib/python3.12/site-packages",
    "PYTHONUNBUFFERED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "TMPDIR": "/tmp",
    "TMP": "/tmp",
    "TEMP": "/tmp"
}

def get_dynamic_bind_mounts():
    """Get bind mounts that work in both dev and production environments."""
    import os
    
    base_mounts = [
        "/usr/bin:/usr/bin",
        "/usr/local/bin:/usr/local/bin", 
        "/usr/lib:/usr/lib",
        "/usr/local/lib:/usr/local/lib",
        "/lib:/lib",
        "/lib64:/lib64",
        "/app/.venv:/app/.venv",
        "/dev/null:/dev/null",
        "/dev/zero:/dev/zero",
        "/dev/urandom:/dev/urandom"
    ]
    
    # Add langflow source paths if they exist (dev environment)
    if os.path.exists("/app/src/backend/base"):
        base_mounts.extend([
            "/app/src/backend/base:/opt/langflow/src/backend/base",
            "/app/src:/opt/src",
        ])
    
    # Add component executor - try multiple locations
    executor_paths = [
        "/app/src/backend/base/langflow/sandbox/component_executor.py",
        "/app/.venv/lib/python3.12/site-packages/langflow/sandbox/component_executor.py"
    ]
    
    for executor_path in executor_paths:
        if os.path.exists(executor_path):
            base_mounts.append(f"{executor_path}:/opt/executor.py")
            break
    
    # Add config directory if it exists
    if os.path.exists("/var/lib/langflow"):
        base_mounts.append("/var/lib/langflow:/var/lib/langflow")
    
    return base_mounts

# Bind mounts for file system access
BINDMOUNTS_RO = get_dynamic_bind_mounts()

# Note: RW bind mounts are now dynamically generated per execution
# to prevent cross-tenant filesystem access in multi-tenant deployments
BINDMOUNTS_RW = [
    # Dynamic temp directory will be added per execution
]

@dataclass
class NsjailConfig:
    """nsjail-specific configuration parameters for sandboxing."""
    mode: str = "o"  # once mode
    hostname: str = "langflow-sandbox"
    user: str = "nobody"
    group: str = "nogroup"
    time_limit: int = 30
    max_cpus: int = 1  # Always 1 for sandbox
    rlimit_cpu: int = 30
    rlimit_as: int = 134217728  # 128MB in bytes
    rlimit_fsize: int = 10485760  # 10MB in bytes
    rlimit_nofile: int = 32
    disable_clone_newnet: bool = False
    disable_clone_newuser: bool = False
    disable_clone_newpid: bool = False
    chroot: str = ""
    bindmount_ro: List[str] = field(default_factory=lambda: BINDMOUNTS_RO.copy())
    bindmount_rw: List[str] = field(default_factory=lambda: BINDMOUNTS_RW.copy())
    execution_id: Optional[str] = None  # Used for unique temp directories
    tmpfs: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=lambda: ENV.copy())
    seccomp_policy: str = ""

    def add_execution_temp_mount(self, execution_id: str, host_temp_dir: str):
        """Add execution-specific temporary directory mount."""
        # Remove any existing temp mounts first
        self.bindmount_rw = [mount for mount in self.bindmount_rw if not mount.endswith(":/tmp")]
        
        # Add the new temp mount
        temp_mount = f"{host_temp_dir}:/tmp"
        self.bindmount_rw.append(temp_mount)
        logger.debug(f"Added execution-specific temp mount: {temp_mount}")
    
    def to_command_args(self) -> List[str]:
        args = [
            "--mode", self.mode,
            "--hostname", self.hostname,
            "--user", self.user,
            "--group", self.group,
            "--time_limit", str(self.time_limit),
            "--max_cpus", str(self.max_cpus),
            "--rlimit_cpu", str(self.rlimit_cpu),
            "--rlimit_as", str(self.rlimit_as),
            "--rlimit_fsize", str(self.rlimit_fsize),
            "--rlimit_nofile", str(self.rlimit_nofile),
        ]
        if self.disable_clone_newnet:
            args.append("--disable_clone_newnet")
        if self.disable_clone_newuser:
            args.append("--disable_clone_newuser")
        if self.disable_clone_newpid:
            args.append("--disable_clone_newpid")
        if self.chroot:
            args.extend(["--chroot", self.chroot])
        for mount in self.bindmount_ro:
            args.extend(["--bindmount_ro", mount])
        for mount in self.bindmount_rw:
            args.extend(["--bindmount", mount])
        for tmpfs in self.tmpfs:
            args.extend(["--tmpfs", tmpfs])
        for key, value in self.env.items():
            args.extend(["--env", f"{key}={value}"])
        if self.seccomp_policy:
            args.extend(["--seccomp_policy", self.seccomp_policy])
        return args

@dataclass
class SandboxProfile:
    """Simplified sandbox profile with only essential configurable settings."""
    # Core security settings (configurable)
    allow_secrets_for_untrusted: bool = False
    network_enabled: bool = False
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 128
    max_code_size_kb: int = 50
    
    # Environment parameters (configurable)
    env_params: List[str] = field(default_factory=list)
    
    # Internal settings (not configurable)
    nsjail_config: NsjailConfig = field(default_factory=NsjailConfig)
    description: str = "Simplified sandbox profile for untrusted code."
    
    def _update_nsjail_config(self):
        """Update nsjail configuration based on current profile settings."""
        # Apply settings to nsjail config
        self.nsjail_config.rlimit_as = self.max_memory_mb * 1024 * 1024
        self.nsjail_config.rlimit_cpu = self.max_execution_time_seconds
        self.nsjail_config.time_limit = self.max_execution_time_seconds + 10
        self.nsjail_config.disable_clone_newnet = not self.network_enabled
        
        # Clear and rebuild environment variables
        user_env = {}
        for env_var in self.env_params:
            if env_var in os.environ:
                user_env[env_var] = os.environ[env_var]
        
        # Combine env with user env
        self.nsjail_config.env.update(user_env)
        
        # Network configuration with DNS resolution  
        # disable_clone_newnet = True means disable network namespace isolation (allow network)
        # disable_clone_newnet = False means enable network namespace isolation (block network)
        self.nsjail_config.disable_clone_newnet = self.network_enabled
        
        # Seccomp policies - always apply base sandbox restrictions
        if self.network_enabled:
            # Network enabled - apply base policy only (allows network)
            policy_path = self._get_seccomp_policy_path("seccomp.default.policy")
            self.nsjail_config.seccomp_policy = policy_path
            # Add DNS resolution
            if "/etc/resolv.conf:/etc/resolv.conf" not in self.nsjail_config.bindmount_ro:
                self.nsjail_config.bindmount_ro.append("/etc/resolv.conf:/etc/resolv.conf")
        else:
            # Network disabled - apply base policy + network restrictions
            policy_path = self._get_seccomp_policy_path("seccomp.no-network.policy")
            self.nsjail_config.seccomp_policy = policy_path

    def _get_seccomp_policy_path(self, policy_filename: str) -> str:
        """Find the correct path for seccomp policy files."""
        import os
        from pathlib import Path
        
        # Try multiple possible locations
        possible_paths = [
            # Development paths
            f"/app/src/backend/base/langflow/sandbox/{policy_filename}",
            f"src/backend/base/langflow/sandbox/{policy_filename}",
            # Production paths
            f"/app/.venv/lib/python3.12/site-packages/langflow/sandbox/{policy_filename}",
            # Relative to this file
            str(Path(__file__).parent / policy_filename),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.debug(f"Found seccomp policy at: {path}")
                return path
        
        # Fallback: return the first path and let nsjail handle the error
        logger.warning(f"Could not find seccomp policy {policy_filename}, tried: {possible_paths}")
        return possible_paths[0]

    def validate_code_size(self, code: str) -> tuple[bool, str]:
        code_size_kb = len(code.encode('utf-8')) / 1024
        if code_size_kb > self.max_code_size_kb:
            return False, f"Code size ({code_size_kb:.1f}KB) exceeds limit ({self.max_code_size_kb}KB) for sandboxed code."
        return True, ""

class SecurityPolicy:
    """Manages the single sandbox security profile."""
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.profile = self._initialize_profile()
        self._apply_local_overrides()
        self.profile._update_nsjail_config()  # Initialize nsjail config once with final values

    def _initialize_profile(self) -> SandboxProfile:
        """Initialize the sandbox profile with default settings."""
        max_code_kb = self.config.untrusted_max_code_kb or int(os.getenv('LANGFLOW_UNTRUSTED_MAX_CODE_KB', '50'))
        
        return SandboxProfile(
            allow_secrets_for_untrusted=False,
            network_enabled=False,
            max_execution_time_seconds=30,
            max_memory_mb=128,
            max_code_size_kb=max_code_kb,
            env_params=[],
            description="Default secure sandbox profile"
        )

    def get_profile(self) -> SandboxProfile:
        """Return the active sandbox profile."""
        return self.profile
    
    def is_lock_mode_enabled(self) -> bool:
        """Check if component locking mode is enabled via LANGFLOW_SANDBOX_LOCK_COMPONENTS."""
        return self.config.lock_components

    def _apply_local_overrides(self):
        """Apply local configuration overrides from config.json."""
        import json
        from pathlib import Path
        config_file = Path(__file__).parent / "config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    overrides = json.load(f)
                self._apply_profile_overrides(overrides)
            except Exception as e:
                logger.warning(f"Failed to load profile overrides from {config_file}: {e}")

    def _apply_profile_overrides(self, overrides: dict):
        """Apply configuration overrides to the profile."""
        profile = self.profile
        
        # Apply flat configuration settings
        configurable_keys = [
            "allow_secrets_for_untrusted", 
            "network_enabled", 
            "max_execution_time_seconds", 
            "max_memory_mb", 
            "max_code_size_kb"
        ]
        
        for key in configurable_keys:
            if key in overrides and overrides[key] is not None:
                setattr(profile, key, overrides[key])
        
        # Handle environment parameters
        if "env_params" in overrides and overrides["env_params"]:
            env_params = overrides["env_params"]
            if isinstance(env_params, list):
                profile.env_params = env_params.copy()
            else:
                logger.warning("env_params must be a list of environment variable names, ignoring")
        
