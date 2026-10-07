import React from "react";
import { 
  FaCheckCircle, 
  FaRegFileAlt, 
  FaWrench, 
  FaLayerGroup, 
  FaCode,
  FaShieldAlt,
  FaCoffee,
  FaRegCalendarAlt, 
  FaStopwatch,
  FaArrowRight
} from "react-icons/fa";
import type { MigrationResult } from "../services/resultService";
import { getMigrationElapsedSeconds } from "../utils/migrationTiming";
import { MigrationTimer } from "./MigrationTimer";

interface MigrationProgressViewProps {
  migrationJob: MigrationResult | null;
  migrationTimerNow: number;
  onCancel: () => void;
  onViewReport: () => void;
}

const formatDuration = (totalSeconds: number) => {
  const h = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
  const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
  const s = (totalSeconds % 60).toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
};

const formatDate = (dateStr: string | null | undefined) => {
  if (!dateStr) return "N/A";
  const date = new Date(dateStr);
  return date.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
};

const StatCard = ({ icon, iconBg, borderColor, number, title, subtitle }: any) => (
  <div style={{
    flex: 1,
    minWidth: '200px',
    backgroundColor: 'white',
    borderRadius: '8px',
    padding: '15px',
    display: 'flex',
    alignItems: 'flex-start',
    gap: '15px',
    border: '1px solid #e5e7eb',
    borderBottom: `3px solid ${borderColor}`,
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
  }}>
    <div style={{ backgroundColor: iconBg, padding: '12px', borderRadius: '8px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      {icon}
    </div>
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <span style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#111827', lineHeight: 1 }}>{number}</span>
      <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#374151', marginTop: '6px' }}>{title}</span>
      <span style={{ fontSize: '0.65rem', color: '#6b7280', marginTop: '4px' }}>{subtitle}</span>
    </div>
  </div>
);

export function MigrationProgressView({ migrationJob, migrationTimerNow, onCancel, onViewReport }: MigrationProgressViewProps) {
  const elapsedSeconds = getMigrationElapsedSeconds(migrationJob, migrationTimerNow);
  
  if (!migrationJob) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', fontFamily: 'sans-serif' }}>
      
      {/* Dark Blue Banner Area */}
      <div style={{
        background: 'linear-gradient(to right, #072a6c, #0d6efd)',
        borderRadius: '12px',
        padding: '20px 25px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        color: 'white',
        flexWrap: 'wrap',
        gap: '20px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{
            backgroundColor: 'rgba(255,255,255,0.1)',
            padding: '8px',
            borderRadius: '50%',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center'
          }}>
            <div style={{
              backgroundColor: 'white',
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center'
            }}>
              <FaCheckCircle color="#10b981" size={24} />
            </div>
          </div>
          <div>
            <h2 style={{ margin: 0, color: 'white', fontSize: '1.5rem', fontWeight: 'bold' }}>Migration Report</h2>
            <p style={{ margin: '6px 0 0 0', color: '#bfdbfe', fontSize: '0.9rem' }}>
              Your project has been successfully modernized from Java 8 to Java 17.
            </p>
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '25px', flexWrap: 'wrap' }}>
          {/* Version Transition Box */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            border: '1px solid rgba(255,255,255,0.2)', 
            borderRadius: '8px', 
            padding: '10px 16px', 
            gap: '15px', 
            backgroundColor: 'rgba(255,255,255,0.05)' 
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ backgroundColor: '#1e3a8a', padding: '8px', borderRadius: '50%' }}>
                 <FaCoffee color="white" size={12} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                 <span style={{ color: 'white', fontWeight: 'bold', fontSize: '0.9rem', lineHeight: 1 }}>Java 8</span>
                 <span style={{ color: '#93c5fd', fontSize: '0.65rem', marginTop: '2px' }}>Legacy</span>
              </div>
            </div>
            <span style={{ color: '#93c5fd', margin: '0 5px' }}>→</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ backgroundColor: '#1e3a8a', padding: '8px', borderRadius: '50%' }}>
                 <FaCoffee color="white" size={12} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                 <span style={{ color: 'white', fontWeight: 'bold', fontSize: '0.9rem', lineHeight: 1 }}>Java 17</span>
                 <span style={{ 
                   color: '#34d399', 
                   fontSize: '0.55rem', 
                   fontWeight: 'bold',
                   backgroundColor: 'rgba(16, 185, 129, 0.2)', 
                   padding: '2px 4px', 
                   borderRadius: '4px',
                   marginTop: '3px'
                 }}>MODERNIZED</span>
              </div>
            </div>
          </div>
          
          {/* Metadata: Date and Duration */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: '25px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#93c5fd', fontSize: '0.65rem', fontWeight: 'bold' }}>
                <FaRegCalendarAlt /> MIGRATION DATE
              </div>
              <div style={{ color: 'white', fontWeight: 'bold', fontSize: '0.85rem' }}>
                {formatDate(migrationJob.completed_at || migrationJob.started_at)}
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#93c5fd', fontSize: '0.65rem', fontWeight: 'bold' }}>
                <FaStopwatch /> DURATION
              </div>
              <div style={{ color: 'white', fontWeight: 'bold', fontSize: '0.85rem' }}>
                {formatDuration(elapsedSeconds)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {migrationJob.status !== "completed" && (
        <>
          <MigrationTimer migrationJob={migrationJob} migrationTimerNow={migrationTimerNow} />
          {/* Progress Bar */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem', fontWeight: 'bold', color: '#374151' }}>
              <span>Overall Progress</span>
              <span>{migrationJob?.progress_percent ?? 100}%</span>
            </div>
            <div style={{ width: '100%', backgroundColor: '#e5e7eb', borderRadius: '999px', height: '10px', overflow: 'hidden' }}>
              <div style={{ 
                width: `${migrationJob?.progress_percent ?? 100}%`, 
                height: '100%', 
                background: 'linear-gradient(to right, #1d4ed8, #60a5fa)',
                borderRadius: '999px' 
              }} />
            </div>
          </div>
        </>
      )}

      {/* Stats Grid */}
      <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
        <StatCard 
          icon={<FaRegFileAlt size={22} color="#2563eb" />}
          iconBg="#eff6ff"
          borderColor="#bfdbfe"
          number={migrationJob.files_modified || 0}
          title="Files Modified"
          subtitle={`${migrationJob.files_modified || 0} files modified`}
        />
        <StatCard 
          icon={<FaWrench size={22} color="#10b981" />}
          iconBg="#ecfdf5"
          borderColor="#a7f3d0"
          number={migrationJob.issues_fixed || 0}
          title="Issues Fixed"
          subtitle="All migration issues resolved"
        />
        <StatCard 
          icon={<FaLayerGroup size={22} color="#8b5cf6" />}
          iconBg="#f5f3ff"
          borderColor="#ddd6fe"
          number={migrationJob.dependencies?.length || 0}
          title="Dependencies Updated"
          subtitle={`${migrationJob.dependencies?.length || 0} total dependencies detected`}
        />
        <StatCard 
          icon={<FaCode size={22} color="#ec4899" />}
          iconBg="#fdf2f8"
          borderColor="#fbcfe8"
          number={migrationJob.conversion_types?.length || 1}
          title="Code Transformations"
          subtitle={`${migrationJob.conversion_types?.length || 1} transformations completed`}
        />
        <StatCard 
          icon={<FaShieldAlt size={22} color="#10b981" />}
          iconBg="#ecfdf5"
          borderColor="#a7f3d0"
          number={migrationJob.sonar_vulnerabilities || 0}
          title="Vulnerabilities"
          subtitle={`${migrationJob.sonar_vulnerabilities || 0} remaining across ${migrationJob.dependencies?.length || 0} scanned dependencies`}
        />
      </div>

      {/* Action Row */}
      <div style={{ display: 'flex', gap: '15px', marginTop: '10px' }}>
        {migrationJob.status === "completed" ? (
          <button 
            onClick={onViewReport}
            style={{
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '6px',
              fontWeight: 'bold',
              fontSize: '1rem',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
              cursor: 'pointer',
              boxShadow: '0 4px 6px -1px rgba(59, 130, 246, 0.3), 0 2px 4px -1px rgba(59, 130, 246, 0.15)',
              transition: 'all 0.2s ease-in-out'
            }}
          >
            View Migration Report <FaArrowRight size={16} />
          </button>
        ) : (
          <button
            style={{
              backgroundColor: '#ef4444',
              color: 'white',
              border: 'none',
              padding: '10px 20px',
              borderRadius: '6px',
              fontWeight: '600',
              cursor: 'pointer'
            }}
            onClick={onCancel}
          >
            Cancel Migration
          </button>
        )}
      </div>
    </div>
  );
}
