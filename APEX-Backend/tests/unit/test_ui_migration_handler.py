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

        self.assertGreaterEqual(len(transformations), 1)
        t = transformations[0]
        self.assertEqual(t["category"], "JSP -> React")
        self.assertEqual(t["targetSourceFile"], "pages/UserProfile.tsx")

        # Verify component file was created in frontend/src
        target_path = self.repo_dir / "frontend" / "src" / "pages" / "UserProfile.tsx"
        self.assertTrue(target_path.exists())
        self.assertIn("User Profile React", target_path.read_text(encoding="utf-8"))

        # Verify App.tsx router was created for route isolation
        app_path = self.repo_dir / "frontend" / "src" / "App.tsx"
        self.assertTrue(app_path.exists())
        self.assertIn("BrowserRouter", app_path.read_text(encoding="utf-8"))

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

        self.assertGreaterEqual(len(transformations), 1)
        t = transformations[0]
        self.assertEqual(t["category"], "JSP -> Angular")
        self.assertEqual(t["targetSourceFile"], "pages/user-profile/user-profile.component.ts")

        # Verify component file was created in frontend/src
        target_path = self.repo_dir / "frontend" / "src" / "pages" / "user-profile" / "user-profile.component.ts"
        self.assertTrue(target_path.exists())
        self.assertIn("User Profile Angular", target_path.read_text(encoding="utf-8"))

    def test_footer_jsp_has_no_form_boilerplate(self):
        """Pure footer/content JSP must NOT generate useState, formData, handleSubmit, or handleInputChange."""
        footer_jsp = (
            '<footer>\n'
            '  <a href="#!">\n'
            '    <i class="fab fa-facebook-f"></i>\n'
            '  </a>\n'
            '</footer>'
        )
        handler = UIMigrationHandler(self.repo_dir, "React")
        res_react = handler._transpile_to_react("FooterComponent", footer_jsp)

        self.assertNotIn("useState", res_react)
        self.assertNotIn("formData", res_react)
        self.assertNotIn("handleSubmit", res_react)
        self.assertNotIn("handleInputChange", res_react)
        self.assertNotIn("onSubmit", res_react)
        self.assertIn('className="fab fa-facebook-f"', res_react)

        handler_ng = UIMigrationHandler(self.repo_dir, "Angular")
        res_ng = handler_ng._transpile_to_angular("FooterComponent", footer_jsp)
        self.assertNotIn("formData", res_ng)
        self.assertNotIn("onSubmit", res_ng)
        self.assertNotIn("FormsModule", res_ng)

    def test_form_jsp_generates_controlled_form_state(self):
        """JSP with form and inputs MUST generate typed form state and handlers."""
        form_jsp = (
            '<form action="/login" method="POST">\n'
            '  <input type="text" name="username" placeholder="Username" required>\n'
            '  <input type="password" name="password" placeholder="Password" required>\n'
            '  <button type="submit">Log In</button>\n'
            '</form>'
        )
        handler = UIMigrationHandler(self.repo_dir, "React")
        res = handler._transpile_to_react("LoginComponent", form_jsp)

        self.assertIn("useState", res)
        self.assertIn("formData", res)
        self.assertIn("'username': ''", res)
        self.assertIn("'password': ''", res)
        self.assertIn("handleInputChange", res)
        self.assertIn("handleSubmit", res)
        self.assertIn("onSubmit={handleSubmit}", res)

    def test_jstl_and_el_transformation(self):
        """JSTL loops and conditionals must translate to idiomatic React expressions."""
        jstl_jsp = (
            '<div class="box">\n'
            '  <c:if test="${isActive}">\n'
            '    <span>Active</span>\n'
            '  </c:if>\n'
            '  <c:forEach items="${products}" var="product">\n'
            '    <div>${product.title}</div>\n'
            '  </c:forEach>\n'
            '</div>'
        )
        handler = UIMigrationHandler(self.repo_dir, "React")
        res = handler._transpile_to_react("BoxComponent", jstl_jsp)

        self.assertIn("{(isActive) && (", res)
        self.assertIn("products && products.map((product: any, index: number) => (", res)
        self.assertIn("{product.title}", res)

    def test_jsf_component_transformation(self):
        """JSF tags (h:form, h:inputText, h:commandButton) must map to appropriate components."""
        jsf_content = (
            '<h:form>\n'
            '  <h:inputText value="#{userBean.name}" />\n'
            '  <h:commandButton value="Save" action="#{userBean.save}" />\n'
            '</h:form>'
        )
        handler = UIMigrationHandler(self.repo_dir, "React")
        res_react = handler._transpile_to_react("UserViewComponent", jsf_content)

        self.assertIn("<form", res_react)
        self.assertIn("<input type=\"text\"", res_react)
        self.assertIn("<button type=\"submit\">Save</button>", res_react)

        handler_ng = UIMigrationHandler(self.repo_dir, "Angular")
        res_ng = handler_ng._transpile_to_angular("UserViewComponent", jsf_content)
        self.assertIn("<form", res_ng)
        self.assertIn("(ngSubmit)=\"onSubmit()\"", res_ng)

    def test_two_pass_validation_and_sanitization(self):
        """Pass 1 auto-corrects JSX attributes; Pass 2 cleans phantom boilerplate."""
        from app.application.pipelines.frontend_migration.ui_migration_handler import (
            extract_source_facts,
        )
        handler = UIMigrationHandler(self.repo_dir, "React")

        footer_source = '<footer><a href="#!"><i class="icon"></i></a></footer>'
        facts = extract_source_facts(Path("footer.jsp"), footer_source)

        hallucinated_code = (
            "import React, { useState } from 'react';\n"
            "export const Footer = () => {\n"
            "  const [formData, setFormData] = useState({});\n"
            "  const handleInputChange = (e) => {};\n"
            "  const handleSubmit = (e) => {};\n"
            "  return <footer class=\"foot\"><input name=\"bogus\"><label for=\"x\">X</label></footer>;\n"
            "};\n"
            "export default Footer;"
        )

        sanitized, is_valid, errors = handler._validate_and_sanitize(hallucinated_code, "React", facts)

        # Pass 1 syntax fixes
        self.assertIn('className="foot"', sanitized)
        self.assertIn('htmlFor="x"', sanitized)
        self.assertIn('<input name="bogus" />', sanitized)

        # Pass 2 boilerplate stripping for non-form source
        self.assertNotIn("formData", sanitized)
        self.assertNotIn("handleInputChange", sanitized)
        self.assertNotIn("handleSubmit", sanitized)
        self.assertNotIn("useState", sanitized)
        self.assertTrue(is_valid)

    def test_data_driven_accuracy_calculation(self):
        """Accuracy must be dynamically calculated based on preserved elements, not hardcoded."""
        from app.application.pipelines.frontend_migration.ui_migration_handler import (
            extract_source_facts,
        )
        handler = UIMigrationHandler(self.repo_dir, "React")

        source = (
            '<form action="/api/save">\n'
            '  <input type="text" name="title">\n'
            '  <c:if test="${show}"><span>Visible</span></c:if>\n'
            '  <button type="submit">Submit</button>\n'
            '</form>'
        )
        facts = extract_source_facts(Path("edit.jsp"), source)

        # High fidelity code preserving all elements
        good_code = (
            "export const Edit = () => (\n"
            "  <form>\n"
            "    <input name=\"title\" />\n"
            "    {show && <span>Visible</span>}\n"
            "    <button type=\"submit\">Submit</button>\n"
            "  </form>\n"
            ");"
        )
        meta = handler._calculate_accuracy(facts, good_code, "React", is_valid=True)
        self.assertGreaterEqual(meta["accuracy"], 90.0)
        self.assertGreaterEqual(meta["uiQualityScore"], 80.0)
        self.assertEqual(meta["total_elements"], 4)  # input + condition + button + EL expr
        self.assertEqual(meta["preserved_elements"], 4)

    def test_dynamic_design_system_detection(self):
        """Design system must be detected dynamically from target repository configuration."""
        import json
        handler = UIMigrationHandler(self.repo_dir, "React")
        # 1. When no package.json exists -> modern_css
        self.assertEqual(handler._detect_frontend_design_system(), "modern_css")

        # 2. When package.json has @mui/material -> mui
        handler._cached_design_system = None
        pkg_dir = self.repo_dir / "frontend"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "package.json").write_text(json.dumps({"dependencies": {"@mui/material": "^5.0.0"}}), encoding="utf-8")
        self.assertEqual(handler._detect_frontend_design_system(), "mui")

        # 3. When package.json has tailwindcss -> tailwind
        handler._cached_design_system = None
        (pkg_dir / "package.json").write_text(json.dumps({"devDependencies": {"tailwindcss": "^3.0.0"}}), encoding="utf-8")
        self.assertEqual(handler._detect_frontend_design_system(), "tailwind")

        # 4. When target framework is Angular with @angular/material -> angular_material
        handler_ng = UIMigrationHandler(self.repo_dir, "Angular")
        (pkg_dir / "package.json").write_text(json.dumps({"dependencies": {"@angular/material": "^17.0.0"}}), encoding="utf-8")
        self.assertEqual(handler_ng._detect_frontend_design_system(), "angular_material")

    def test_page_type_detection(self):
        """Page structure type must be dynamically inferred from actual source constructs."""
        from app.application.pipelines.frontend_migration.ui_migration_handler import extract_source_facts

        # Auth view
        auth_jsp = '<form><input type="text" name="u"><input type="password" name="p"></form>'
        facts_auth = extract_source_facts(Path("login.jsp"), auth_jsp)
        self.assertEqual(facts_auth.page_type, "auth")

        # Layout partial
        footer_jsp = '<footer><p>&copy; 2026</p></footer>'
        facts_footer = extract_source_facts(Path("footer.jsp"), footer_jsp)
        self.assertEqual(facts_footer.page_type, "layout_partial")

        # Data table view
        table_jsp = '<table><c:forEach items="${items}" var="i"><tr><td>${i.name}</td></tr></c:forEach></table>'
        facts_table = extract_source_facts(Path("users-list.jsp"), table_jsp)
        self.assertEqual(facts_table.page_type, "data_table")

    def test_obsolete_presentation_cleanup(self):
        """Legacy markup (table border=1, center, font, spacer br) must be safely modernized."""
        legacy_jsp = (
            '<center>\n'
            '  <font color="red">Notice</font>\n'
            '  <table border="1" cellpadding="5" cellspacing="0">\n'
            '    <tr><td>Cell</td></tr>\n'
            '  </table>\n'
            '  <br><br>\n'
            '</center>'
        )
        handler = UIMigrationHandler(self.repo_dir, "React")
        res = handler._transpile_to_react("LegacyComponent", legacy_jsp)

        self.assertNotIn('<center', res)
        self.assertNotIn('<font', res)
        self.assertNotIn('border="1"', res)
        self.assertIn('className="modern-table-wrapper"', res)
        self.assertIn('className="modern-table"', res)
        self.assertIn('className="text-center"', res)

    def test_ui_modernization_quality_score_greater_than_80(self):
        """Measurable UI quality score must exceed 80% for modernized components."""
        from app.application.pipelines.frontend_migration.ui_migration_handler import extract_source_facts
        handler = UIMigrationHandler(self.repo_dir, "React")

        source = (
            '<div class="container">\n'
            '  <h2>Orders</h2>\n'
            '  <table><tr><td>${order.status}</td></tr></table>\n'
            '</div>'
        )
        facts = extract_source_facts(Path("orders.jsp"), source)

        modern_code = (
            "import React from 'react';\n"
            "export const Orders = () => (\n"
            "  <div className=\"modern-container\">\n"
            "    <div className=\"modern-card\">\n"
            "      <h2>Orders</h2>\n"
            "      <div className=\"modern-table-wrapper\">\n"
            "        <table className=\"modern-table\">\n"
            "          <tbody><tr><td><span className=\"badge badge-info\">{status}</span></td></tr></tbody>\n"
            "        </table>\n"
            "      </div>\n"
            "    </div>\n"
            "  </div>\n"
            ");\n"
            "export default Orders;\n"
        )
        meta = handler._calculate_accuracy(facts, modern_code, "React", is_valid=True)
        self.assertGreaterEqual(meta["uiQualityScore"], 80.0)


if __name__ == "__main__":
    unittest.main()


