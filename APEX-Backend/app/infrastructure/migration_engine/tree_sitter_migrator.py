import logging
import re

logger = logging.getLogger(__name__)

_JAVAX_PACKAGES = ("persistence", "servlet", "annotation", "validation", "ws.rs", "xml.bind", "transaction", "ejb", "jms", "mail")

try:
    import tree_sitter_java
    from tree_sitter import Language, Parser

    JAVA_LANGUAGE = Language(tree_sitter_java.language())
    parser = Parser(JAVA_LANGUAGE)
    _HAS_TREE_SITTER = True
except Exception as e:
    logger.warning("Tree-sitter Java parser could not be initialized: %s. Falling back to pattern-based migration.", e)
    parser = None
    _HAS_TREE_SITTER = False


def _walk_tree_and_replace(node, source_bytes, replacements):
    # Check Imports
    if node.type == "import_declaration":
        for child in node.children:
            if child.type == "scoped_identifier":
                text = source_bytes[child.start_byte:child.end_byte].decode("utf-8")
                if text.startswith("javax.") and any(pkg in text for pkg in _JAVAX_PACKAGES):
                    new_text = text.replace("javax.", "jakarta.", 1)
                    replacements.append((child.start_byte, child.end_byte, new_text.encode("utf-8")))

    # Check Annotations
    elif node.type == "annotation":
        name_node = node.child_by_field_name("name")
        if name_node and name_node.type == "scoped_identifier":
            text = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8")
            if text.startswith("javax.") and any(pkg in text for pkg in _JAVAX_PACKAGES):
                new_text = text.replace("javax.", "jakarta.", 1)
                replacements.append((name_node.start_byte, name_node.end_byte, new_text.encode("utf-8")))

    # Recursively check children
    for child in node.children:
        _walk_tree_and_replace(child, source_bytes, replacements)


def _fallback_migrate_java_syntax(source: str) -> str:
    """Fallback migration using regex when tree-sitter is unavailable."""
    result = source
    for pkg in _JAVAX_PACKAGES:
        pattern = r"\bjavax\." + re.escape(pkg)
        result = re.sub(pattern, f"jakarta.{pkg}", result)
    return result


def safe_migrate_java_syntax(source: str) -> str:
    """Safely migrates Java syntax (e.g. javax to jakarta) using Tree-sitter AST with regex fallback."""
    if not _HAS_TREE_SITTER or parser is None:
        return _fallback_migrate_java_syntax(source)
    try:
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)

        replacements = []
        _walk_tree_and_replace(tree.root_node, source_bytes, replacements)

        # Apply replacements backwards so byte offsets don't shift
        replacements.sort(key=lambda x: x[0], reverse=True)
        for start_byte, end_byte, new_bytes in replacements:
            source_bytes = source_bytes[:start_byte] + new_bytes + source_bytes[end_byte:]

        return source_bytes.decode("utf-8")
    except Exception as e:
        logger.error("Error during tree-sitter AST migration: %s. Using fallback.", e)
        return _fallback_migrate_java_syntax(source)
