
import re

content = open("APEX-Backend/app/application/use_cases/start_migration.py", "r", encoding="utf-8").read()

# 1. def run signature
content = re.sub(
    r"<<<<<<< HEAD\n    def run\(self, job_id: str, current_user_id: int \| None = None, github_token: str \| None = None\) -> None:\n=======\n    def run\(\n        self,\n        job_id: str,\n        current_user_id: int \| None = None,\n        token: str \| None = None,\n    \) -> None:\n>>>>>>> [a-f0-9]+",
    "    def run(\n        self,\n        job_id: str,\n        current_user_id: int | None = None,\n        github_token: str | None = None,\n    ) -> None:",
    content
)

# 2. test pipeline / Stage 5
content = re.sub(
    r"<<<<<<< HEAD\n                    store\.update\(\n                        unit_test_details=executed_details,\n                        tests_run=total_cases,\n                        tests_passed=total_cases,\n                        test_summary=f\"Executed unit test suite cleanly \(\{total_cases\} test cases executed\)\.\",\n                        progressPercent=80,\n                    \)\n                    store\.append_logs\(\[f\"\[QUALITY CHECK\] Unit tests passed cleanly \(\{total_cases\} test cases\)\.\"\]\)\n                except Exception as test_exc:\n                    logger\.warning\(f\"Post-migration unit test execution notice for job \{job_id\}: \{test_exc\}\"\)\n                    store\.update\(progressPercent=80\)\n            # --- Stage 5: Code Deprecation & Publish ---\n=======\n(.*?)>>>>>>> [a-f0-9]+",
    r"\1",
    content,
    flags=re.DOTALL
)

# 3. Code deprecation log
content = re.sub(
    r"<<<<<<< HEAD\n            file_utils\.remove_tree\(paths\.migrated_repo_dir / \"\.git\"\)\n            publish_target_java = result\.effective_target_java_version or target_java\n            target_repo = self\._publish\(store, report, paths, publish_target_java, github_token=github_token\)\n            store\.append_logs\(\[f\"\[DEPRECATION\] Published migrated repository to: \{target_repo\}\"\]\)\n=======\n            store\.append_logs\(\[\"\[DEPRECATION\] Scanned codebase for deprecated Java APIs and updated modern construct references\.\"\]\)\n>>>>>>> [a-f0-9]+",
    "            store.append_logs([\"[DEPRECATION] Scanned codebase for deprecated Java APIs and updated modern construct references.\"])",
    content
)

# 3b. Update target_repo = self._publish call (line 622)
content = content.replace("target_repo = self._publish(store, report, paths, publish_target_java, token=token)", "target_repo = self._publish(store, report, paths, publish_target_java, github_token=github_token)")

# 4. Exceptions
content = re.sub(
    r"<<<<<<< HEAD\n        except \(LLMNotConfiguredError, ChatLLMNotConfiguredError\) as exc:\n            logger\.exception\(\"LLM not configured for job %s\", job_id\)\n            self\._fail\(store, job_id, \"LLM_NOT_CONFIGURED\"\)\n        except Exception as exc:  # noqa: BLE001 - report any unexpected failure cleanly\n            logger\.exception\(\"Unexpected migration failure for job %s\", job_id\)\n            self\._fail\(store, job_id, \"Migration failed due to an unexpected error\.\"\)\n=======\n        except Exception as exc:  # noqa: BLE001\n            import traceback\n            logger\.exception\(\"Migration job %s failed with an unexpected error\", job_id\)\n            err_trace = traceback\.format_exc\(\)\n            self\._fail\(store, job_id, f\"Migration failed due to an unexpected error\.\\n\{err_trace\}\"\)\n>>>>>>> [a-f0-9]+",
    "        except (LLMNotConfiguredError, ChatLLMNotConfiguredError) as exc:\n            logger.exception(\"LLM not configured for job %s\", job_id)\n            self._fail(store, job_id, \"LLM_NOT_CONFIGURED\")\n        except Exception as exc:  # noqa: BLE001\n            import traceback\n            logger.exception(\"Migration job %s failed with an unexpected error\", job_id)\n            err_trace = traceback.format_exc()\n            self._fail(store, job_id, f\"Migration failed due to an unexpected error.\\n{err_trace}\")",
    content
)

# 5. def _publish signature
content = re.sub(
    r"<<<<<<< HEAD\n        github_token: str \| None = None,\n=======\n        token: str \| None = None,\n>>>>>>> [a-f0-9]+",
    "        github_token: str | None = None,",
    content
)

# 6. Branch creator push args
content = re.sub(
    r"<<<<<<< HEAD\n                paths\.migrated_repo_dir, source_url, branch, commit_message=commit_message, token=github_token\n=======\n                paths\.migrated_repo_dir,\n                clean_url,\n                branch,\n                commit_message=commit_message,\n                token=effective_token,\n>>>>>>> [a-f0-9]+",
    "                paths.migrated_repo_dir,\n                clean_url,\n                branch,\n                commit_message=commit_message,\n                token=effective_token,",
    content
)

# 7. Repo creator create args
content = re.sub(
    r"<<<<<<< HEAD\n            token=github_token,\n=======\n            token=effective_token,\n>>>>>>> [a-f0-9]+",
    "            token=effective_token,",
    content
)

# 8. Fix effective_token declaration in _publish
content = content.replace("effective_token = (\n            (token or \"\").strip()", "effective_token = (\n            (github_token or \"\").strip()")

# 9. Duplicate token in repo_pusher.push
content = content.replace("            token=effective_token,\n            allow_force_update_existing=True,\n            token=github_token,\n", "            token=effective_token,\n            allow_force_update_existing=True,\n")

open("APEX-Backend/app/application/use_cases/start_migration.py", "w", encoding="utf-8").write(content)
print("Fixes applied.")

