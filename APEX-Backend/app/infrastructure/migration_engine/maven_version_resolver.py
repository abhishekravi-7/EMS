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
import xml.etree.ElementTree as ET
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
_CANDIDATE_CACHE: LRUCache = LRUCache(maxsize=1000)
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


class MavenVersionResolver:
    """Dynamically resolves published General Availability (GA) versions from Maven Central."""

    def __init__(self, timeout_seconds: float = 3.0) -> None:
        self.timeout = timeout_seconds

    def resolve_version(self, group_id: str, artifact_id: str, default_fallback: str | None = None) -> str:
        """Fetch the latest stable release version for group_id:artifact_id."""
        cache_key = f"{group_id}:{artifact_id}"
        now = time.time()

        if cache_key in _VERSION_CACHE:
            version, expiry = _VERSION_CACHE[cache_key]
            if now < expiry:
                return version

        fallback = default_fallback or _FALLBACK_VERSIONS.get(cache_key, "3.0.0")

        # Try Maven Central Search API
        try:
            query = f'g:"{group_id}" AND a:"{artifact_id}"'
            url = f"https://search.maven.org/solrsearch/select?q={urllib.parse.quote(query)}&rows=1&wt=json"

            req = urllib.request.Request(url, headers={"User-Agent": "JavaApex-Migration-Engine/2.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    docs = data.get("response", {}).get("docs", [])
                    if docs and isinstance(docs, list):
                        latest_ver = docs[0].get("latestVersion")
                        if latest_ver and self._is_valid_version(latest_ver):
                            _VERSION_CACHE[cache_key] = (latest_ver, now + CACHE_TTL_SECONDS)
                            logger.info("Resolved real-time Maven Central version for %s: %s", cache_key, latest_ver)
                            return latest_ver
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch Maven Central version for %s: %s. Using fallback: %s", cache_key, exc, fallback)

        # Cache fallback to prevent rapid repeated failed network calls
        _VERSION_CACHE[cache_key] = (fallback, now + 300)  # 5 min retry TTL for fallback
        return fallback

    def resolve_candidate_versions(self, group_id: str, artifact_id: str, limit: int = 12) -> list[str]:
        """Return real stable releases published on Maven Central, newest first."""
        cache_key = f"{group_id}:{artifact_id}"
        now = time.time()
        cached = _CANDIDATE_CACHE.get(cache_key)
        if cached and cached[1] > now:
            return cached[0][:limit]

        try:
            query = f'g:"{group_id}" AND a:"{artifact_id}"'
            params = urllib.parse.urlencode({
                "q": query,
                "core": "gav",
                "rows": min(max(limit * 3, 20), 100),
                "wt": "json",
                "sort": "timestamp desc",
            })
            url = f"https://search.maven.org/solrsearch/select?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "JavaApex-Migration-Engine/2.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    return []
                data = json.loads(resp.read().decode("utf-8"))
            docs = data.get("response", {}).get("docs", [])
            versions: list[str] = []
            for doc in docs if isinstance(docs, list) else []:
                version = str(doc.get("v") or "").strip()
                if version and self._is_valid_version(version) and version not in versions:
                    versions.append(version)
            _CANDIDATE_CACHE[cache_key] = (versions, now + CACHE_TTL_SECONDS)
            return versions[:limit]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to resolve Maven Central candidate versions for %s: %s", cache_key, exc)
            return []

    def get_spring_framework_version_for_boot(self, spring_boot_version: str) -> str | None:
        """Read Spring Framework's managed version from the Spring Boot BOM."""
        try:
            version = urllib.parse.quote(str(spring_boot_version).strip(), safe=".")
            url = (
                "https://repo.maven.apache.org/maven2/org/springframework/boot/"
                f"spring-boot-dependencies/{version}/spring-boot-dependencies-{version}.pom"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "JavaApex-Migration-Engine/2.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    return None
                root = ET.fromstring(resp.read())
            for element in root.iter():
                if element.tag.rsplit("}", 1)[-1] == "spring-framework.version" and element.text:
                    return element.text.strip()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to read Spring Framework version managed by Boot %s: %s", spring_boot_version, exc)
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


_global_resolver = MavenVersionResolver()


def get_version_resolver() -> MavenVersionResolver:
    return _global_resolver
