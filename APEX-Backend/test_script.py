from app.infrastructure.analyzers.api_endpoint_detector import ApiEndpointDetector
import tempfile
from pathlib import Path

td = tempfile.TemporaryDirectory()
root = Path(td.name)
java_file = root / "TestController.java"
java_file.write_text(
    'import org.springframework.web.bind.annotation.*;\n'
    '@RestController\n'
    '@RequestMapping("/api")\n'
    'public class TestController {\n'
    '    @GetMapping("/test")\n'
    '    public String test() { return "ok"; }\n'
    '}'
)
print(ApiEndpointDetector().detect(root))
