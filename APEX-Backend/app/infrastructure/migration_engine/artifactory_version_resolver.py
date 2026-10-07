"""Real-time Maven Central REST API Version Resolver.

Provides dynamic, real-time GA version resolution for Maven and Gradle dependencies
combining Maven Central REST API lookups, in-memory TTL caching, and safe fallback defaults.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
try:
    from cachetools import LRUCache
except ImportError:
    class LRUCache(dict):  # type: ignore[no-redef]
        def __init__(self, maxsize: int = 128) -> None:
            super().__init__()
            self.maxsize = maxsize

        def __setitem__(self, key: Any, value: Any) -> None:
            if len(self) >= self.maxsize and key not in self:
                oldest = next(iter(self))
                del self[oldest]
            super().__setitem__(key, value)

logger = logging.getLogger(__name__)

# In-memory TTL cache: { "groupId:artifactId": (version_string, expiry_timestamp) }
_VERSION_CACHE: LRUCache = LRUCache(maxsize=1000)
CACHE_TTL_SECONDS = 3600  # 1 hour cache

# Reliable fallback versions (used if network request fails or times out)
_FALLBACK_VERSIONS: dict[str, str] = {
    "org.springframework.boot:spring-boot-starter-parent": "3.2.5",
    "org.springframework.boot:spring-boot-gradle-plugin": "3.2.5",
    "org.projectlombok:lombok": "1.18.36",
    "org.projectlombok:lombok-mapstruct-binding": "0.2.0",
    "jakarta.persistence:jakarta.persistence-api": "3.1.0",
    "jakarta.servlet:jakarta.servlet-api": "6.0.0",
    "jakarta.annotation:jakarta.annotation-api": "2.1.1",
    "jakarta.validation:jakarta.validation-api": "3.0.2",
    "jakarta.transaction:jakarta.transaction-api": "2.0.1",
    "jakarta.ws.rs:jakarta.ws.rs-api": "3.1.0",
    "jakarta.xml.bind:jakarta.xml.bind-api": "4.0.2",
}


import base64

class ArtifactoryVersionResolver:
    """Dynamically resolves published General Availability (GA) versions from registries."""

    def __init__(
        self, 
        provider: str = "MAVEN_CENTRAL", 
        base_url: str = "https://search.maven.org", 
        username: str | None = None, 
        auth_token: str | None = None,
        timeout_seconds: float = 3.0
    ) -> None:
        self.provider = provider.upper()
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.auth_token = auth_token
        self.timeout = timeout_seconds

    def _get_auth_headers(self) -> dict[str, str]:
        headers = {"User-Agent": "JavaApex-Migration-Engine/2.0"}
        if self.username and self.auth_token:
            auth_str = f"{self.username}:{self.auth_token}"
            encoded = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {encoded}"
        elif self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def resolve_version(self, group_id: str, artifact_id: str, default_fallback: str | None = None) -> str:
        """Fetch the latest stable release version for group_id:artifact_id."""
        cache_key = f"{self.provider}:{self.base_url}:{group_id}:{artifact_id}"
        now = time.time()

        if cache_key in _VERSION_CACHE:
            version, expiry = _VERSION_CACHE[cache_key]
            if now < expiry:
                return version

        fallback = default_fallback or _FALLBACK_VERSIONS.get(f"{group_id}:{artifact_id}", "3.0.0")

        latest_ver = None
        try:
            if self.provider == "MAVEN_CENTRAL":
                latest_ver = self._resolve_maven_central(group_id, artifact_id)
            elif self.provider == "JFROG":
                latest_ver = self._resolve_jfrog(group_id, artifact_id)
            elif self.provider == "NEXUS":
                latest_ver = self._resolve_nexus(group_id, artifact_id)
            
            if latest_ver and self._is_valid_version(latest_ver):
                _VERSION_CACHE[cache_key] = (latest_ver, now + CACHE_TTL_SECONDS)
                logger.info("Resolved real-time %s version for %s:%s: %s", self.provider, group_id, artifact_id, latest_ver)
                return latest_ver
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch %s version for %s:%s: %s. Using fallback: %s", self.provider, group_id, artifact_id, exc, fallback)

        # Cache fallback to prevent rapid repeated failed network calls
        _VERSION_CACHE[cache_key] = (fallback, now + 300)  # 5 min retry TTL for fallback
        return fallback

    def _resolve_maven_central(self, group_id: str, artifact_id: str) -> str | None:
        query = f'g:"{group_id}" AND a:"{artifact_id}"'
        url = f"https://search.maven.org/solrsearch/select?q={urllib.parse.quote(query)}&rows=1&wt=json"
        req = urllib.request.Request(url, headers={"User-Agent": "JavaApex-Migration-Engine/2.0"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                docs = data.get("response", {}).get("docs", [])
                if docs and isinstance(docs, list):
                    return docs[0].get("latestVersion")
        return None

    def _resolve_jfrog(self, group_id: str, artifact_id: str) -> str | None:
        # JFrog Artifactory GAVC search API
        url = f"{self.base_url}/api/search/gavc?g={urllib.parse.quote(group_id)}&a={urllib.parse.quote(artifact_id)}"
        req = urllib.request.Request(url, headers=self._get_auth_headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                versions = []
                for res in results:
                    uri = res.get("uri", "")
                    # Extract version from uri (e.g. .../group/artifact/version/artifact-version.jar)
                    parts = uri.split("/")
                    if len(parts) > 2:
                        versions.append(parts[-2])
                
                # Filter GA versions and sort
                ga_versions = [v for v in set(versions) if self._is_valid_version(v)]
                if ga_versions:
                    # Very basic string sort fallback, ideal would be semver parsing
                    ga_versions.sort(reverse=True)
                    return ga_versions[0]
        return None

    def _resolve_nexus(self, group_id: str, artifact_id: str) -> str | None:
        # Nexus 3 Search API
        url = f"{self.base_url}/service/rest/v1/search?group={urllib.parse.quote(group_id)}&name={urllib.parse.quote(artifact_id)}&sort=version"
        req = urllib.request.Request(url, headers=self._get_auth_headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", [])
                if items and isinstance(items, list):
                    return items[0].get("version")
        return None

    def get_latest_spring_boot_version(self, target_java_version: str | int = 17, default_fallback: str = "3.2.5") -> str:
        """Resolve latest Spring Boot version compatible with target Java version."""
        try:
            target_major = int(str(target_java_version).strip())
        except ValueError:
            target_major = 17

        # Spring Boot 3 requires Java 17+
        if target_major < 17:
            return "2.7.18"  # Final Java 8/11 compatible Spring Boot 2.7 patch release

        resolved = self.resolve_version("org.springframework.boot", "spring-boot-starter-parent", default_fallback=default_fallback)
        return resolved

    def get_jakarta_artifact_coordinates(self, javax_artifact_id: str) -> tuple[str, str, str]:
        """Return (jakarta_group_id, jakarta_artifact_id, latest_version) for legacy javax artifact."""
        mapping = {
            "javax.persistence": ("jakarta.persistence", "jakarta.persistence-api", "3.1.0"),
            "javax.persistence-api": ("jakarta.persistence", "jakarta.persistence-api", "3.1.0"),
            "javax.servlet-api": ("jakarta.servlet", "jakarta.servlet-api", "6.0.0"),
            "javax.annotation-api": ("jakarta.annotation", "jakarta.annotation-api", "2.1.1"),
            "validation-api": ("jakarta.validation", "jakarta.validation-api", "3.0.2"),
            "javax.validation-api": ("jakarta.validation", "jakarta.validation-api", "3.0.2"),
            "javax.transaction-api": ("jakarta.transaction", "jakarta.transaction-api", "2.0.1"),
            "javax.ws.rs-api": ("jakarta.ws.rs", "jakarta.ws.rs-api", "3.1.0"),
        }

        if javax_artifact_id not in mapping:
            return ("jakarta.persistence", "jakarta.persistence-api", "3.1.0")

        gid, aid, fallback = mapping[javax_artifact_id]
        dynamic_ver = self.resolve_version(gid, aid, default_fallback=fallback)
        return (gid, aid, dynamic_ver)

    def _is_valid_version(self, version: str) -> bool:
        """Filter out milestone, release-candidate, or snapshot builds to ensure GA stability."""
        ver_lower = version.lower()
        unstable_tokens = ["m1", "m2", "m3", "m4", "m5", "rc1", "rc2", "rc3", "snapshot", "alpha", "beta"]
        return not any(token in ver_lower for token in unstable_tokens)


_global_resolver = ArtifactoryVersionResolver()


def get_version_resolver() -> ArtifactoryVersionResolver:
    return _global_resolver
