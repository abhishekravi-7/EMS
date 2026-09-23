import asyncio
import logging
import os
import re
from pathlib import Path

from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.prompt_templates import (
    UI_MODERNIZATION_SYSTEM_PROMPT,
    FRONTEND_FOLDER_STRUCTURE_SYSTEM_PROMPT,
    build_ui_modernization_prompt,
    build_frontend_folder_structure_prompt,
)
from app.infrastructure.migration_engine.diff_utils import generate_diff_lines
from app.shared import file_utils

logger = logging.getLogger(__name__)


class UIMigrationHandler:
    def __init__(self, migrated_repo_dir: Path, target_framework: str, mode: str | None = None):
        self.migrated_repo_dir = migrated_repo_dir
        self.target_framework = target_framework
        self.mode = mode
        self.llm = ChatLLM()

    def run(self) -> list[dict]:
        """Run the UI migration synchronously and return the list of transformations."""
        return asyncio.run(self._run_async())

    async def _run_async(self) -> list[dict]:
        if self.mode and self.mode.startswith("JSP"):
            jsp_jsf_extensions = (".jsp", ".jspf", ".jspx")
        elif self.mode and self.mode.startswith("JSF"):
            jsp_jsf_extensions = (".jsf", ".xhtml")
        else:
            jsp_jsf_extensions = (".jsp", ".jspf", ".jspx", ".jsf", ".xhtml")
        
        # Base directory for modernization
        frontend_base = self.migrated_repo_dir / "frontend" / "src"
        frontend_base.mkdir(parents=True, exist_ok=True)

        files_to_process = []
        backend_context_files = []
        shared_includes = []
        java_entities = []
        endpoints = []

        for root, _, files in os.walk(self.migrated_repo_dir):
            if "frontend" in root or "target" in root or "build" in root:
                continue
            for file in files:
                full_path = Path(root) / file
                if file.lower().endswith(jsp_jsf_extensions):
                    if any(inc in file.lower() for inc in ["nav", "footer", "header", "sidebar", "allcss", "include"]):
                        shared_includes.append(file)
                    files_to_process.append(full_path)
                elif file.lower().endswith(".java"):
                    content = ""
                    try:
                        content = full_path.read_text(encoding="utf-8")
                    except Exception:
                        continue

                    is_controller = "controller" in root.lower() or "@controller" in content.lower() or "@restcontroller" in content.lower()
                    is_entity = "model" in root.lower() or "entity" in root.lower() or "dto" in root.lower() or "@entity" in content.lower()

                    if is_entity:
                        java_entities.append(file.replace(".java", ""))

                    if is_controller or is_entity:
                        rel_path = full_path.relative_to(self.migrated_repo_dir)
                        backend_context_files.append(f"// FILE: {rel_path}\n{content}")

                        # Extract potential endpoints for planning
                        if is_controller:
                            matches = re.findall(r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\((?:value\s*=\s*)?["\']([^"\']+)["\']', content)
                            endpoints.extend(matches)

        if not files_to_process:
            logger.info("No JSP/JSF files found for UI modernization.")
            return []

        backend_context = "\n\n".join(backend_context_files)

        # Planning Phase: Generate Folder Structure
        logger.info("Generating UI modernization plan (folder structure)...")
        module_name = self.migrated_repo_dir.name

        planning_prompt = build_frontend_folder_structure_prompt(
            module_name=module_name,
            jsp_page_list=[f.name for f in files_to_process],
            shared_includes=shared_includes,
            endpoint_list=endpoints,
            entity_list=java_entities,
            auth_requirement="Not pre-detected; infer only from supplied JSP/JSF and backend evidence.",
            csrf_yes_no="Not pre-detected; infer only from supplied backend evidence.",
            target_framework=self.target_framework,
        )

        ui_plan = ""
        try:
            async for chunk in self.llm.stream_chat(
                system_prompt=FRONTEND_FOLDER_STRUCTURE_SYSTEM_PROMPT,
                user_prompt=planning_prompt,
                endpoint="ui_modernization_planning",
                max_tokens=2000,
            ):
                ui_plan += chunk
            logger.info("UI Modernization Plan generated:\n%s", ui_plan)
        except Exception as e:
            logger.warning("Failed to generate UI modernization plan: %s", e)
            ui_plan = f"Standard {self.target_framework} folder structure."

        # Augmented context for each file modernization
        augmented_context = f"{backend_context}\n\nUI MODERNIZATION PLAN / FOLDER STRUCTURE:\n{ui_plan}"

        logger.info(f"Starting UI modernization for {len(files_to_process)} files targeting {self.target_framework}.")

        transformations = []
        # Process files sequentially
        for fp in files_to_process:
            try:
                res = await self._process_file(fp, frontend_base, augmented_context)
                if res and isinstance(res, dict):
                    transformations.append(res)
            except Exception as exc:
                logger.error(f"Error modernizing file {fp.name}: {exc}")
            await asyncio.sleep(1.0)
                
        return transformations

    @staticmethod
    def _resolve_generated_file_path(frontend_base: Path, file_name: str) -> Path:
        """Keep model-generated files inside the migration frontend workspace."""
        normalized_name = file_name.replace("\\", "/").strip()
        relative_path = Path(normalized_name)
        allowed_extensions = {".ts", ".tsx", ".js", ".jsx", ".css", ".scss"}
        if (
            not normalized_name
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative_path.suffix.lower() not in allowed_extensions
        ):
            raise ValueError(f"Invalid generated frontend path: {file_name}")

        base = frontend_base.resolve()
        candidate = (base / relative_path).resolve()
        if candidate != base and base not in candidate.parents:
            raise ValueError(f"Generated frontend path escapes workspace: {file_name}")
        return candidate

    async def _process_file(self, file_path: Path, frontend_base: Path, backend_context: str) -> dict | None:
        logger.info(f"Modernizing {file_path.name}...")
        source_code = file_utils.read_text(file_path)
        if not source_code.strip():
            logger.warning(f"File {file_path.name} is empty, skipping.")
            return None
        
        prompt = build_ui_modernization_prompt(
            source_file_path=str(file_path.relative_to(self.migrated_repo_dir)),
            source_code=source_code,
            target_framework=self.target_framework,
            backend_context=backend_context
        )
        
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            full_response = ""
            try:
                async for chunk in self.llm.stream_chat(
                    system_prompt=UI_MODERNIZATION_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    endpoint="ui_modernization",
                    first_token_timeout=20.0,
                    max_tokens=4000,
                ):
                    full_response += chunk
                
                extracted_files = self._extract_files(full_response)
                if not extracted_files:
                    raise ValueError(f"No component code extracted from LLM response for {file_path.name}")
                
                after_text_blocks = []
                target_source_file_display_parts = []
                
                for file_name, code in extracted_files.items():
                    # If LLM didn't provide a path, determine it based on file type and framework
                    if "/" not in file_name:
                        ext = ".tsx" if "react" in self.target_framework.lower() else ".ts"
                        if file_name == "generated_component":
                            clean_name = "".join(p.capitalize() for p in file_path.stem.replace("-", "_").split("_"))
                            if "angular" in self.target_framework.lower():
                                file_name = f"pages/{file_path.stem.lower()}/{file_path.stem.lower()}.component.ts"
                            else:
                                file_name = f"pages/{clean_name}{ext}"
                        elif file_name.endswith(".service.ts") or file_name.endswith("Api.ts"):
                            file_name = f"api/{file_name}"
                        elif file_name.endswith(".css") or file_name.endswith(".scss"):
                            file_name = f"styles/{file_name}"
                        else:
                            file_name = f"components/{file_name}"

                    new_file_path = self._resolve_generated_file_path(frontend_base, file_name)
                    new_file_path.parent.mkdir(parents=True, exist_ok=True)
                    new_file_path.write_text(code, encoding="utf-8")
                    
                    after_text_blocks.append(f"// --- {file_name} ---\n{code}")
                    target_source_file_display_parts.append(file_name)
                
                after_text = "\n\n".join(after_text_blocks)
                target_source_file_display = ", ".join(target_source_file_display_parts)
                
                is_jsp = file_path.suffix.lower() in (".jsp", ".jspf", ".jspx")
                is_react = "react" in self.target_framework.lower()
                category = "JSP -> React" if is_jsp and is_react else "JSP -> Angular" if is_jsp else "JSF -> React" if is_react else "JSF -> Angular"
                icon = "⚛️" if is_react else "🚀"

                try:
                    rel_source_path = str(file_path.relative_to(self.migrated_repo_dir)).replace("\\", "/")
                except ValueError:
                    rel_source_path = file_path.name

                transformation_record = generate_diff_lines(
                    file_name=file_path.name,
                    before_text=source_code,
                    after_text=after_text,
                    category=category,
                    icon=icon,
                    target_source_file=target_source_file_display,
                    source_file=rel_source_path,
                )
                
                file_path.unlink(missing_ok=True)
                logger.info(f"Successfully modernized {file_path.name} to {target_source_file_display}")
                return transformation_record
            except Exception as e:
                logger.warning(f"Attempt {attempt}/{max_attempts} failed to modernize {file_path.name} via LLM: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(2 * attempt)
                else:
                    logger.info(f"Falling back to direct syntax transformation for {file_path.name}")
                    return self._generate_rule_based_transformation(file_path, frontend_base / "components", source_code)
            finally:
                await asyncio.sleep(1)

    def _generate_rule_based_transformation(self, file_path: Path, frontend_dir: Path, source_code: str) -> dict:
        """Transforms JSP/JSF code into modern component code using direct syntax mapping."""
        is_jsp = file_path.suffix.lower() in (".jsp", ".jspf", ".jspx")
        is_react = "react" in self.target_framework.lower()
        ext = ".tsx" if is_react else ".ts"
        
        # Derive component name: list-todos.jsp -> ListTodosComponent
        clean_stem = "".join(part.capitalize() for part in file_path.stem.replace("-", " ").replace("_", " ").split())
        comp_name = f"{clean_stem}Component" if not clean_stem.endswith("Component") else clean_stem
        
        target_file_name = f"{comp_name}{ext}"
        target_file_path = frontend_dir / target_file_name
        
        category = "JSP -> React" if is_jsp and is_react else "JSP -> Angular" if is_jsp else "JSF -> React" if is_react else "JSF -> Angular"
        icon = "⚛️" if is_react else "🚀"
        
        if is_react:
            after_text = self._transpile_to_react(comp_name, source_code)
        else:
            after_text = self._transpile_to_angular(comp_name, source_code)
            
        target_file_path.parent.mkdir(parents=True, exist_ok=True)
        target_file_path.write_text(after_text, encoding="utf-8")
        
        try:
            rel_source_path = str(file_path.relative_to(self.migrated_repo_dir)).replace("\\", "/")
        except ValueError:
            rel_source_path = file_path.name
            
        record = generate_diff_lines(
            file_name=file_path.name,
            before_text=source_code,
            after_text=after_text,
            category=category,
            icon=icon,
            target_source_file=target_file_name,
            source_file=rel_source_path,
        )
        file_path.unlink(missing_ok=True)
        logger.info(f"Successfully modernized {file_path.name} to {target_file_name}")
        return record

    def _transpile_to_react(self, comp_name: str, source_code: str) -> str:
        """Converts JSP/JSF HTML structure into a valid React functional component."""
        lines = []
        in_scriptlet = False
        
        for line in source_code.splitlines():
            stripped = line.strip()
            # Skip JSP directives, tags and comments
            if stripped.startswith("<%@") or stripped.startswith("<%--") or stripped.startswith("<!--"):
                continue
            if "<%" in stripped and "%>" in stripped:
                line = re.sub(r"<%[=]?.*?%>", "", line)
            elif "<%" in stripped:
                in_scriptlet = True
                continue
            elif "%>" in stripped:
                in_scriptlet = False
                continue
            if in_scriptlet:
                continue

            # Convert c:out -> {expr}
            line = re.sub(r'<c:out\s+value=["\'](?:\$\{)?([^}"\']+)\}?["\']\s*/>', r'{\1}', line)

            # Convert c:forEach -> {items && items.map((var: any, index: number) => ( ... ))}
            line = re.sub(r'<c:forEach\s+items=["\'](?:\$\{)?([^}"\']+)\}?["\']\s+var=["\']([^"\']+)["\']>', r'{\1 && \1.map((\2: any, index: number) => (', line)
            line = line.replace('</c:forEach>', '))}')

            # Convert c:if -> {(test) && ( ... )}
            line = re.sub(r'<c:if\s+test=["\'](?:\$\{)?([^}"\']+)\}?["\']>', r'{(\1) && (', line)
            line = line.replace('</c:if>', ')}').replace('</c:when>', ')}').replace('<c:otherwise>', ': (').replace('</c:otherwise>', ')').replace('</c:choose>', '}')

            # Convert attribute value="${expr}" to value={expr} in JSX
            line = re.sub(r'="\$\{([^}]+)\}"', r'={\1}', line)
            line = re.sub(r'=\'\$\{([^}]+)\}\'', r'={\1}', line)

            # Convert JSP EL ${expr} and JSF #{expr} to JSX {expr}
            line = re.sub(r'\$\{([^}]+)\}', r'{\1}', line)
            line = re.sub(r'#\{([^}]+)\}', r'{\1}', line)

            # Replace class= with className=
            line = re.sub(r'\bclass="', 'className="', line)
            line = re.sub(r"\bclass='", "className='", line)
            # Replace for= with htmlFor=
            line = re.sub(r'\bfor="', 'htmlFor="', line)
            line = re.sub(r"<form(\s|>)", r'<form onSubmit={handleSubmit}\1', line, count=1)
            # Ensure void elements are self-closing
            line = re.sub(r'<(input|img|br|hr)([^>]*?[^/])>', r'<\1\2 />', line)
            
            lines.append("        " + line)
            
        jsx_body = "\n".join(lines).strip()
        if not jsx_body:
            jsx_body = f'<div><h3>{comp_name}</h3><p>Modernized view component.</p></div>'

        model_names = sorted({
            name
            for name in re.findall(r"\{\s*([A-Za-z_$][\w$]*)", jsx_body)
            if name not in {"true", "false", "null", "undefined"}
        })
        model_destructure = ", ".join(model_names)
        model_line = f"    const {{ {model_destructure} }} = data;\n" if model_destructure else ""

        return f'''import React, {{ useState }} from 'react';

type {comp_name}Props = {{
    data?: Record<string, any>;
    onSubmit?: (formData: Record<string, any>) => void | Promise<void>;
}};

export const {comp_name}: React.FC<{comp_name}Props> = ({{ data = {{}}, onSubmit }}) => {{
    const [formData, setFormData] = useState<Record<string, any>>({{}});
{model_line}

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {{
        const {{ name, value }} = e.target;
        setFormData((prev) => ({{ ...prev, [name]: value }}));
    }};

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {{
        e.preventDefault();
        await onSubmit?.(formData);
    }};

    return (
        <div className="{comp_name.lower()}-wrapper" onChange={{handleInputChange}}>
            {jsx_body}
        </div>
    );
}};

export default {comp_name};
'''

    def _transpile_to_angular(self, comp_name: str, source_code: str) -> str:
        """Converts JSP/JSF HTML structure into a valid Angular component."""
        lines = []
        for line in source_code.splitlines():
            stripped = line.strip()
            if stripped.startswith("<%@") or stripped.startswith("<%--") or stripped.startswith("<!--"):
                continue

            # Convert c:out -> {{ expr }}
            line = re.sub(r'<c:out\s+value=["\'](?:\$\{)?([^}"\']+)\}?["\']\s*/>', r'{{ \1 }}', line)

            # Convert c:forEach -> <ng-container *ngFor="let var of items">
            line = re.sub(r'<c:forEach\s+items=["\'](?:\$\{)?([^}"\']+)\}?["\']\s+var=["\']([^"\']+)["\']>', r'<ng-container *ngFor="let \2 of \1">', line)
            line = line.replace('</c:forEach>', '</ng-container>')

            # Convert c:if -> <ng-container *ngIf="cond">
            line = re.sub(r'<c:if\s+test=["\'](?:\$\{)?([^}"\']+)\}?["\']>', r'<ng-container *ngIf="\1">', line)
            line = line.replace('</c:if>', '</ng-container>')

            # Convert JSP EL ${expr} and JSF #{expr} to Angular {{ expr }}
            line = re.sub(r'\$\{([^}]+)\}', r'{{ \1 }}', line)
            line = re.sub(r'#\{([^}]+)\}', r'{{ \1 }}', line)

            line = re.sub(r'<form(\s|>)', r'<form (ngSubmit)="onSubmit()"\1', line, count=1)
            line = re.sub(
                r'(<(?:input|select|textarea)\b[^>]*\bname=["\']([^"\']+)["\'][^>]*)',
                r'\1 [(ngModel)]="formData[\'\2\']"',
                line,
                count=1,
            )

            lines.append("    " + line)
            
        template_body = "\n".join(lines).strip()
        if not template_body:
            template_body = f'<h3>{comp_name}</h3><p>Modernized Angular view component.</p>'
        selector = "app-" + comp_name.lower().replace("component", "")
        
        return f'''import {{ Component, OnInit }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ FormsModule }} from '@angular/forms';

@Component({{
  selector: '{selector}',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="{comp_name.lower()}-container">
      {template_body}
    </div>
  `,
  styles: [`
    .{comp_name.lower()}-container {{
      padding: 1rem;
    }}
  `]
}})
export class {comp_name} implements OnInit {{
  formData: Record<string, any> = {{}};

  ngOnInit(): void {{}}

  onSubmit(): void {{}}
}}

export default {comp_name};
'''

    def _extract_files(self, response: str) -> dict[str, str]:
        extracted_files = {}
        lines = response.splitlines()
        current_file = None
        current_code = []
        in_code_block = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("### FILE:"):
                if current_file and current_code:
                    code_text = "\n".join(current_code).strip()
                    if code_text:
                        extracted_files[current_file] = code_text
                current_file = stripped.replace("### FILE:", "").strip()
                current_code = []
                in_code_block = False
                continue
                
            if current_file:
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block:
                    current_code.append(line)
                    
        if current_file and current_code:
            code_text = "\n".join(current_code).strip()
            if code_text:
                extracted_files[current_file] = code_text
            
        if not extracted_files:
            code = self._extract_code_block_legacy(response)
            if code.strip():
                extracted_files["generated_component"] = code.strip()
            
        return extracted_files

    def _extract_code_block_legacy(self, response: str) -> str:
        lines = response.splitlines()
        code_lines = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                code_lines.append(line)
        return "\n".join(code_lines) if code_lines else response
