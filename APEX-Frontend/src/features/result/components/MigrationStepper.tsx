import React from "react";
import { FaCheck, FaTimes } from "react-icons/fa";
import "./MigrationStepper.css";

export type StepStatus = "pending" | "in_progress" | "completed" | "failed";

export interface MigrationStepItem {
  id: number;
  stepId: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string; color?: string }>;
  status: StepStatus;
}

export interface MigrationStepperProps {
  steps: MigrationStepItem[];
  currentStep: number;
  selectedStepId?: string;
  onStepClick?: (stepId: string) => void;
}

/**
 * MigrationStepper - Fully dynamic vertical migration stepper component
 * Matches the reference design with circular icon nodes, centered vertical connector lines,
 * live execution visual states (Completed, In Progress, Pending), and click-to-filter logs.
 */
export const MigrationStepper: React.FC<MigrationStepperProps> = ({
  steps,
  currentStep,
  selectedStepId,
  onStepClick,
}) => {
  return (
    <div className="migration-steps-vertical-list" role="list" aria-label="Migration Steps">
      {steps.map((step, idx) => {
        const isCompleted = step.status === "completed";
        const isCurrent = step.status === "in_progress";
        const isPending = step.status === "pending";
        const isFailed = step.status === "failed";
        const isLast = idx === steps.length - 1;
        const isSelected = selectedStepId === step.stepId;
        const StepIcon = step.icon;

        return (
          <div
            key={step.id}
            role="button"
            tabIndex={0}
            className={`migration-step-row state-${step.status} ${
              isSelected ? "is-selected-step" : ""
            } ${isCurrent ? "is-current-row" : ""}`}
            onClick={() => onStepClick?.(step.stepId)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onStepClick?.(step.stepId);
              }
            }}
            title={`Click to view logs for ${step.title}`}
            aria-selected={isSelected}
            aria-current={isCurrent ? "step" : undefined}
          >
            {/* Circular Icon Node & Center Connector Line */}
            <div className="step-indicator-col">
              <div
                className={`step-circle circle-${step.status} ${isCurrent ? "is-current-step" : ""}`}
                aria-label={`Step ${step.id} status: ${step.status}`}
              >
                {isCompleted ? (
                  <FaCheck className="check-svg" size={16} color="#ffffff" />
                ) : isFailed ? (
                  <FaTimes className="fail-svg" size={15} color="#ffffff" />
                ) : isCurrent ? (
                  <>
                    <div className="pulse-outer-ring" />
                    <StepIcon size={18} color="#2563eb" className="step-icon-svg pulse-icon" />
                  </>
                ) : (
                  <StepIcon size={18} color="#334155" className="step-icon-svg" />
                )}
              </div>

              {!isLast && (
                <div
                  className={`step-vertical-connector ${
                    isCompleted ? "connector-completed" : "connector-pending"
                  }`}
                  aria-hidden="true"
                />
              )}
            </div>

            {/* Step Title & Description */}
            <div className="step-content-col">
              <div className="step-title-text">{step.title}</div>
              <div className="step-desc-text">{step.description}</div>
            </div>

            {/* Status Badge on Right */}
            <div className="step-badge-col">
              {isCompleted && (
                <span className="badge-pill badge-completed">
                  Completed
                </span>
              )}
              {isCurrent && (
                <span className="badge-pill badge-in-progress">
                  In Progress
                </span>
              )}
              {isPending && (
                <span className="badge-pill badge-pending">
                  Pending
                </span>
              )}
              {isFailed && (
                <span className="badge-pill badge-failed">
                  Failed
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default MigrationStepper;
