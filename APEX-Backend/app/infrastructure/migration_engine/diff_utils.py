from typing import Dict, List, Any
import difflib

def generate_diff_lines(
    file_name: str,
    before_text: str,
    after_text: str,
    category: str,
    icon: str,
    target_source_file: str = None,
    source_file: str = None,
) -> Dict[str, Any]:
    """
    Generates a unified diff record compatible with the frontend's Before & After
    Differentiator (diffData shape).

    For JSP/JSF → React/Angular transformations the source file is deleted and a
    brand-new target file is generated, so these records always carry
    status="Added".  The diff lines still contain the original JSP/JSF content
    as "removed" lines and the generated component code as "added" lines so the
    Result page can display a meaningful before/after view.

    Fields returned:
        file            – display name shown in the sidebar (target filename)
        sourceFile      – original source path (JSP/JSF) for frontend filters
        category        – e.g. "JSP -> React" | "JSF -> Angular"
        icon            – emoji used in the sidebar badge
        status          – "Added" | "Modified" | "Removed"
        additions       – count of added lines (generated code)
        deletions       – count of removed lines (original source)
        beforeLines     – line-by-line original content with type annotations
        afterLines      – line-by-line generated content with type annotations
        targetSourceFile – generated component filename(s), if provided
    """
    before_lines: List[Dict[str, Any]] = []
    after_lines: List[Dict[str, Any]] = []

    before_split = before_text.splitlines() if before_text else []
    after_split = after_text.splitlines() if after_text else []

    differ = difflib.ndiff(before_split, after_split)

    b_num = 1
    a_num = 1

    for line in differ:
        code = line[:2]
        text = line[2:]

        if code == "  ":
            before_lines.append({"num": b_num, "text": text, "type": "normal"})
            after_lines.append({"num": a_num, "text": text, "type": "normal"})
            b_num += 1
            a_num += 1
        elif code == "- ":
            before_lines.append({"num": b_num, "text": f"- {text}", "type": "removed"})
            b_num += 1
        elif code == "+ ":
            after_lines.append({"num": a_num, "text": f"+ {text}", "type": "added"})
            a_num += 1
        # Ignore "?" (intraline difference markers)

    additions_count = sum(1 for l in after_lines if l["type"] == "added")
    deletions_count = sum(1 for l in before_lines if l["type"] == "removed")

    # JSP/JSF → Modern-framework transformations always produce a *new* file
    # (the source is deleted and a generated component is written), so the
    # canonical status for UI transformations is "Added".
    status = "Added"

    result: Dict[str, Any] = {
        "file": file_name,
        "category": category,
        "icon": icon,
        "status": status,
        "additions": additions_count,
        "deletions": deletions_count,
        "beforeLines": before_lines,
        "afterLines": after_lines,
    }

    if target_source_file:
        result["targetSourceFile"] = target_source_file

    # Preserve the original source path (e.g. "src/main/webapp/login.jsp") so
    # the frontend can identify JSP vs JSF entries without parsing the category.
    if source_file:
        result["sourceFile"] = source_file

    return result
