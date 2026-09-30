import tree_sitter_java
from tree_sitter import Language, Parser

# Initialize the AST parser
JAVA_LANGUAGE = Language(tree_sitter_java.language())
parser = Parser(JAVA_LANGUAGE)

_JAVAX_PACKAGES = ("persistence", "servlet", "annotation", "validation", "ws.rs", "xml.bind", "transaction", "ejb", "jms", "mail")

def _walk_tree_and_replace(node, source_bytes, replacements):
    # Check Imports
    if node.type == 'import_declaration':
        for child in node.children:
            if child.type == 'scoped_identifier':
                text = source_bytes[child.start_byte:child.end_byte].decode('utf-8')
                if text.startswith("javax.") and any(pkg in text for pkg in _JAVAX_PACKAGES):
                    new_text = text.replace("javax.", "jakarta.", 1)
                    replacements.append((child.start_byte, child.end_byte, new_text.encode('utf-8')))
    
    # Check Annotations
    elif node.type == 'annotation':
        name_node = node.child_by_field_name('name')
        if name_node and name_node.type == 'scoped_identifier':
            text = source_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
            if text.startswith("javax.") and any(pkg in text for pkg in _JAVAX_PACKAGES):
                new_text = text.replace("javax.", "jakarta.", 1)
                replacements.append((name_node.start_byte, name_node.end_byte, new_text.encode('utf-8')))

    # Recursively check children
    for child in node.children:
        _walk_tree_and_replace(child, source_bytes, replacements)

def safe_migrate_java_syntax(source: str) -> str:
    """Safely migrates Java syntax (e.g. javax to jakarta) using Tree-sitter AST."""
    source_bytes = source.encode('utf-8')
    tree = parser.parse(source_bytes)
    
    replacements = []
    _walk_tree_and_replace(tree.root_node, source_bytes, replacements)
    
    # Apply replacements backwards so byte offsets don't shift
    replacements.sort(key=lambda x: x[0], reverse=True)
    for start_byte, end_byte, new_bytes in replacements:
        source_bytes = source_bytes[:start_byte] + new_bytes + source_bytes[end_byte:]
        
    return source_bytes.decode('utf-8')
