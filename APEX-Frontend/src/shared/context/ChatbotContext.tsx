/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from "react";
import type { StrategyPageContext } from "@/features/strategy/services/strategyService";

interface ChatbotState {
  repoUrl: string | null;
  strategyContext: StrategyPageContext | null;
}

interface ChatbotContextType extends ChatbotState {
  setContext: (state: Partial<ChatbotState>) => void;
}

const ChatbotContext = createContext<ChatbotContextType | undefined>(undefined);

export const ChatbotProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, setState] = useState<ChatbotState>({
    repoUrl: null,
    strategyContext: null,
  });

  const setContext = useCallback((newState: Partial<ChatbotState>) => {
    setState((prev) => {
      // Avoid unnecessary updates if the values are identical.
      const hasChange = Object.entries(newState).some(([key, value]) => {
        const prevValue = prev[key as keyof ChatbotState];
        if (value === prevValue) return false;

        // Deep comparison for objects using JSON.stringify
        if (value && typeof value === "object") {
          return JSON.stringify(prevValue) !== JSON.stringify(value);
        }
        return prevValue !== value;
      });

      if (!hasChange) return prev;
      return { ...prev, ...newState };
    });
  }, []);

  const value = useMemo(() => ({
    ...state,
    setContext,
  }), [state, setContext]);

  return (
    <ChatbotContext.Provider value={value}>
      {children}
    </ChatbotContext.Provider>
  );
};

export const useChatbot = (): ChatbotContextType => {
  const context = useContext(ChatbotContext);
  if (!context) {
    throw new Error("useChatbot must be used within a ChatbotProvider");
  }
  return context;
};
