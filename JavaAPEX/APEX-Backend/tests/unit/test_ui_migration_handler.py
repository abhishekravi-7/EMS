import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.application.pipelines.frontend_migration.ui_migration_handler import UIMigrationHandler


class UIMigrationHandlerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_dir = Path(self.temp_dir)

        # Create dummy Java backend and JSP files
        views_dir = self.repo_dir / "src" / "main" / "webapp" / "WEB-INF" / "views"
        views_dir.mkdir(parents=True, exist_ok=True)

        self.jsp_file = views_dir / "user-profile.jsp"
        self.jsp_file.write_text(
            '<%@ page contentType="text/html" %>\n'
            '<div class="profile-card">\n'
            '    <h2>User: ${username}</h2>\n'
            '    <c:if test="${isLoggedIn}">\n'
            '        <p>Email: ${email}</p>\n'
            '    </c:if>\n'
            '    <c:forEach items="${orders}" var="order">\n'
            '        <p>Order ID: ${order.id}</p>\n'
            '    </c:forEach>\n'
            '    <input type="text" name="bio" value="${bio}">\n'
            '</div>',
            encoding="utf-8"
        )

        controller_dir = self.repo_dir / "src" / "main" / "java" / "com" / "example" / "controller"
        controller_dir.mkdir(parents=True, exist_ok=True)
        (controller_dir / "UserController.java").write_text(
            'package com.example.controller;\n'
            'import org.springframework.web.bind.annotation.*;\n'
            '@RestController\n'
            'public class UserController {\n'
            '    @GetMapping("/api/users/profile")\n'
            '    public String getProfile() { return "user-profile"; }\n'
            '}',
            encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_transpile_to_react_rule_based(self):
        handler = UIMigrationHandler(self.repo_dir, "React")
        jsp_content = self.jsp_file.read_text(encoding="utf-8")
        res = handler._transpile_to_react("UserProfileComponent", jsp_content)

        self.assertIn("export const UserProfileComponent: React.FC", res)
        self.assertIn('className="profile-card"', res)
        self.assertIn("{username}", res)
        self.assertIn("{(isLoggedIn) && (", res)
        self.assertIn("orders && orders.map((order: any, index: number) => (", res)
        self.assertIn("<input type=\"text\" name=\"bio\" value={bio} />", res)

    def test_transpile_to_angular_rule_based(self):
        handler = UIMigrationHandler(self.repo_dir, "Angular")
        jsp_content = self.jsp_file.read_text(encoding="utf-8")
        res = handler._transpile_to_angular("UserProfileComponent", jsp_content)

        self.assertIn("@Component({", res)
        self.assertIn("standalone: true", res)
        self.assertIn('class="profile-card"', res)
        self.assertIn("{{ username }}", res)
        self.assertIn('<ng-container *ngIf="isLoggedIn">', res)
        self.assertIn('<ng-container *ngFor="let order of orders">', res)

    def test_extract_files_ignores_comments_outside_code_blocks(self):
        handler = UIMigrationHandler(self.repo_dir, "React")
        llm_response = (
            "Here is the modernized component:\n\n"
            "### FILE: pages/UserProfile.tsx\n"
            "```tsx\n"
            "import React from 'react';\n"
            "export const UserProfile = () => <div>Profile</div>;\n"
            "```\n\n"
            "This component converts user-profile.jsp into React."
        )
        extracted = handler._extract_files(llm_response)
        self.assertIn("pages/UserProfile.tsx", extracted)
        code = extracted["pages/UserProfile.tsx"]
        self.assertIn("export const UserProfile", code)
        self.assertNotIn("This component converts user-profile.jsp into React", code)

    @patch("app.infrastructure.llm.chat_llm.ChatLLM.stream_chat")
    def test_full_run_react_migration(self, mock_stream):
        async def mock_generator(*args, **kwargs):
            yield (
                "### FILE: pages/UserProfile.tsx\n"
                "```tsx\n"
                "import React from 'react';\n"
                "export const UserProfile = () => <div>User Profile React</div>;\n"
                "```\n"
            )

        mock_stream.side_effect = mock_generator

        handler = UIMigrationHandler(self.repo_dir, "React")
        transformations = handler.run()

        self.assertEqual(len(transformations), 1)
        t = transformations[0]
        self.assertEqual(t["category"], "JSP -> React")
        self.assertEqual(t["targetSourceFile"], "pages/UserProfile.tsx")

        # Verify component file was created in frontend/src
        target_path = self.repo_dir / "frontend" / "src" / "pages" / "UserProfile.tsx"
        self.assertTrue(target_path.exists())
        self.assertIn("User Profile React", target_path.read_text(encoding="utf-8"))

    @patch("app.infrastructure.llm.chat_llm.ChatLLM.stream_chat")
    def test_full_run_angular_migration(self, mock_stream):
        async def mock_generator(*args, **kwargs):
            yield (
                "### FILE: pages/user-profile/user-profile.component.ts\n"
                "```ts\n"
                "import { Component } from '@angular/core';\n"
                "@Component({ selector: 'app-user-profile', template: '<div>User Profile Angular</div>' })\n"
                "export class UserProfileComponent {}\n"
                "```\n"
            )

        mock_stream.side_effect = mock_generator

        handler = UIMigrationHandler(self.repo_dir, "Angular")
        transformations = handler.run()

        self.assertEqual(len(transformations), 1)
        t = transformations[0]
        self.assertEqual(t["category"], "JSP -> Angular")
        self.assertEqual(t["targetSourceFile"], "pages/user-profile/user-profile.component.ts")

        # Verify component file was created in frontend/src
        target_path = self.repo_dir / "frontend" / "src" / "pages" / "user-profile" / "user-profile.component.ts"
        self.assertTrue(target_path.exists())
        self.assertIn("User Profile Angular", target_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
