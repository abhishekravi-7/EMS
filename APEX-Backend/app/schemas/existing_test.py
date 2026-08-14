from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

class ExistingTestRunRequest(BaseModel):
    testClasses: List[str]

class ExistingTestClass(BaseModel):
    id: str
    className: str
    filePath: str
    framework: str
    methods: List[str]

class ExistingTestDiscoveryResponse(BaseModel):
    framework: str
    buildTool: str
    tests: List[ExistingTestClass]
    error: Optional[str] = None

class TestResultDetail(BaseModel):
    test_class: str
    test_method: str
    status: str
    execution_time_seconds: float
    error_message: Optional[str] = None

class ExistingTestStatusResponse(BaseModel):
    status: str
    discovered: int
    executed: int
    passed: int
    failed: int
    skipped: int
    results: List[TestResultDetail]
    logs: List[str]
    error: Optional[str] = None
