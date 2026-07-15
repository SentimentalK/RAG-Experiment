import React, { createContext, useContext, useEffect, useState } from "react";
import type { BaselineEvaluation } from "../types/evaluation";
import { StaticEvaluationDataSource } from "../data/static-evaluation-data-source";

interface BaselineContextValue {
  data: BaselineEvaluation | null;
  loading: boolean;
  error: Error | null;
}

const BaselineContext = createContext<BaselineContextValue | undefined>(undefined);

const dataSource = new StaticEvaluationDataSource();

export const BaselineProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [data, setData] = useState<BaselineEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let mounted = true;
    dataSource
      .loadBaseline()
      .then((baseline) => {
        if (mounted) {
          setData(baseline);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err);
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  return (
    <BaselineContext.Provider value={{ data, loading, error }}>
      {children}
    </BaselineContext.Provider>
  );
};

export const useBaselineEvaluation = () => {
  const context = useContext(BaselineContext);
  if (context === undefined) {
    throw new Error("useBaselineEvaluation must be used within a BaselineProvider");
  }
  return context;
};
