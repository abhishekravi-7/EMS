import { useState } from "react";
import type { PersistedWizardFormState } from "@/shared/utils/migrationWizardStorage";

export function useModernizationState(persistedFormState: PersistedWizardFormState | null) {
  const [runTests, setRunTests] = useState(persistedFormState?.runTests ?? true);
  const [useLLMTests, setUseLLMTests] = useState(true);
  const [selectedLLMProvider, setSelectedLLMProvider] = useState("groq");
  const [runSonar, setRunSonar] = useState(persistedFormState?.runSonar ?? true);
  const [runCycode, setRunCycode] = useState(persistedFormState?.runCycode ?? false);
  const [runFossa, setRunFossa] = useState(persistedFormState?.runFossa ?? false);
  const [runFunctionalTests, setRunFunctionalTests] = useState(
    (persistedFormState as { runFunctionalTests?: boolean } | null)?.runFunctionalTests ?? true
  );
  const [fixBusinessLogic, setFixBusinessLogic] = useState(
    persistedFormState?.fixBusinessLogic ?? true
  );
  const [selectedTestSources, setSelectedTestSources] = useState<{
    llm: boolean;
    functionalDoc: boolean;
    existing: boolean;
  }>(
    persistedFormState?.selectedTestSources ?? {
      llm: true,
      functionalDoc: false,
      existing: true,
    }
  );

  return {
    runTests,
    setRunTests,
    useLLMTests,
    setUseLLMTests,
    selectedLLMProvider,
    setSelectedLLMProvider,
    runSonar,
    setRunSonar,
    runFossa,
    setRunFossa,
    runCycode,
    setRunCycode,
    runFunctionalTests,
    setRunFunctionalTests,
    fixBusinessLogic,
    setFixBusinessLogic,
    selectedTestSources,
    setSelectedTestSources,
  };
}
