"""Unit tests for GradleModernizer build manifest migration engine."""

import tempfile
from pathlib import Path
from app.infrastructure.migration_engine.gradle_modernizer import GradleModernizer


def test_gradle_modernizer_spring_boot_2_to_3_and_java_21():
    original_build_gradle = """plugins {
    id 'org.springframework.boot' version '2.7.12'
    id 'io.spring.dependency-management' version '1.0.15.RELEASE'
    id 'java'
}

group = 'com.employee'
version = '0.0.1-SNAPSHOT'
sourceCompatibility = '1.8'
targetCompatibility = '1.8'

repositories {
    mavenCentral()
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'javax.persistence:javax.persistence-api:2.2'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}
"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        dir_path = Path(tmp_dir)
        build_file = dir_path / "build.gradle"
        build_file.write_text(original_build_gradle, encoding="utf-8")

        modernizer = GradleModernizer()
        res = modernizer.modernize(dir_path, "21")

        assert res.modified is True
        assert res.spring_boot_before == "2.7.12"
        assert res.spring_boot_after == "3.2.5"

        updated_content = build_file.read_text(encoding="utf-8")

        # 1. Check Spring Boot plugin version updated
        assert "version '3.2.5'" in updated_content

        # 2. Check Java compatibility updated to 21
        assert "sourceCompatibility = '21'" in updated_content
        assert "targetCompatibility = '21'" in updated_content

        # 3. Check javax dependency upgraded to jakarta
        assert "jakarta.persistence-api:3.1.0" in updated_content

        # 4. Check structured upgrades list
        assert any(u["artifact_id"] == "spring-boot-gradle-plugin" and u["new_version"] == "3.2.5" for u in res.dependency_upgrades)
        assert any(u["artifact_id"] == "jakarta.persistence-api" for u in res.dependency_upgrades)
