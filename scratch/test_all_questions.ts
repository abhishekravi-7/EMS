import {
  DEFAULT_CENTRALIZED_CONTEXT,
  detectIntent,
  getRelevantContext,
  generateContextAwareAnswer,
} from "../APEX-Frontend/src/shared/services/chatService";

const questions = [
  "What Java version is my project using?",
  "What is the target Java version?",
  "How many files are in the repository?",
  "What frameworks are detected?",
  "How many dependencies are there?",
  "What is my migration readiness?",
  "What are my biggest migration risks?",
  "Are there any security vulnerabilities?",
  "What should I fix first?",
  "Explain dependency injection.",
  "What is Java 21?",
  "Why is my migration taking so long?",
  "What should I do next?",
  "Tell me more about that.",
  "Can you explain the previous issue in simple terms?",
];

console.log("=== Testing 15 Evaluation Questions ===");

const history: any[] = [];

for (let i = 0; i < questions.length; i++) {
  const q = questions[i];
  const { intent, resolvedTopic } = detectIntent(q, history);
  const relevantCtx = getRelevantContext(intent, DEFAULT_CENTRALIZED_CONTEXT);
  const result = generateContextAwareAnswer(q, DEFAULT_CENTRALIZED_CONTEXT, history);

  console.log(`\n--------------------------------------------------`);
  console.log(`Q${i + 1}: "${q}"`);
  console.log(`Intent: ${intent}${resolvedTopic ? ` (topic: ${resolvedTopic})` : ""}`);
  console.log(`Relevant Context Keys:`, Object.keys(relevantCtx));
  console.log(`Answer:\n${result.answer}`);

  // Push into history to simulate conversational progression
  history.push({ role: "user", content: q, id: `u_${i}`, createdAt: "" });
  history.push({ role: "assistant", content: result.answer, id: `a_${i}`, createdAt: "" });
}
