"""Unit tests for PomModernizer XML AST migration engine."""

import tempfile
from pathlib import Path
from app.infrastructure.migration_engine.pom_modernizer import PomModernizer


def test_pom_modernizer_spring_boot_2_to_3_and_java_21():
    original_pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
	<modelVersion>4.0.0</modelVersion>
	<parent>
		<groupId>org.springframework.boot</groupId>
		<artifactId>spring-boot-starter-parent</artifactId>
		<version>2.7.12</version>
		<relativePath/>
	</parent>
	<groupId>com.employee</groupId>
	<artifactId>system</artifactId>
	<version>0.0.1-SNAPSHOT</version>
	<properties>
		<java.version>8</java.version>
		<maven.compiler.source>8</maven.compiler.source>
		<maven.compiler.target>8</maven.compiler.target>
	</properties>
	<dependencies>
		<dependency>
			<groupId>javax.persistence</groupId>
			<artifactId>javax.persistence-api</artifactId>
			<version>2.2</version>
		</dependency>
	</dependencies>
	<build>
		<plugins>
			<plugin>
				<groupId>org.apache.maven.plugins</groupId>
				<artifactId>maven-compiler-plugin</artifactId>
				<configuration>
					<source>8</source>
					<target>8</target>
					<release>8</release>
				</configuration>
			</plugin>
		</plugins>
	</build>
</project>"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pom_path = Path(tmp_dir) / "pom.xml"
        pom_path.write_text(original_pom, encoding="utf-8")

        modernizer = PomModernizer()
        res = modernizer.modernize(pom_path, "21")

        assert res.modified is True
        assert res.spring_boot_before == "2.7.12"
        assert res.spring_boot_after == "3.2.5"

        updated_content = pom_path.read_text(encoding="utf-8")

        # 1. Check parent version updated
        assert "<version>3.2.5</version>" in updated_content

        # 2. Check Java properties updated
        assert "<java.version>21</java.version>" in updated_content
        assert "<maven.compiler.source>21</maven.compiler.source>" in updated_content
        assert "<maven.compiler.target>21</maven.compiler.target>" in updated_content

        # 3. Check maven-compiler-plugin configuration updated
        assert "<source>21</source>" in updated_content
        assert "<target>21</target>" in updated_content
        assert "<release>21</release>" in updated_content

        # 4. Check javax artifact updated to jakarta
        assert "jakarta.persistence-api" in updated_content

        # 5. Check structured upgrades list
        assert any(u["artifact_id"] == "spring-boot-starter-parent" and u["new_version"] == "3.2.5" for u in res.dependency_upgrades)
        assert any(u["artifact_id"] == "jakarta.persistence-api" for u in res.dependency_upgrades)

