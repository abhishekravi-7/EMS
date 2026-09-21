import React, { useEffect, useState } from "react";
import {
  FaCodeBranch,
  FaFolder,
  FaLayerGroup,
  FaSpinner,
  FaSyncAlt,
} from "react-icons/fa";
import { SiSpring } from "react-icons/si";
import { getRecentRepositories } from "../services/connectService";
import type { RecentRepository } from "../types/recentRepositories";

interface RecentRepositoriesTableProps {
  onSelectRepo?: (repoUrl: string) => void;
}

const FOLDER_COLORS = [
  "#3b82f6", // Blue
  "#0ea5e9", // Sky
  "#a855f7", // Purple
  "#ec4899", // Pink
  "#10b981", // Emerald
];

export const RecentRepositoriesTable: React.FC<RecentRepositoriesTableProps> = ({
  onSelectRepo,
}) => {
  const [repositories, setRepositories] = useState<RecentRepository[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const fetchRepos = async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const data = await getRecentRepositories();
      setRepositories(data);
    } catch (err) {
      console.warn("Failed to load recent repositories:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchRepos();
  }, []);

  const handleRowClick = (repo: RecentRepository) => {
    if (onSelectRepo && repo.repoUrl) {
      onSelectRepo(repo.repoUrl);
    }
  };

  return (
    <div className="recent-repos-card">
      <div className="recent-repos-header">
        <h3 className="recent-repos-title">Recent Repositories</h3>
        <button
          type="button"
          className="recent-repos-refresh-btn"
          onClick={() => fetchRepos(true)}
          title="Refresh recent repositories"
          disabled={loading || refreshing}
        >
          <FaSyncAlt className={refreshing ? "fa-spin" : ""} size={13} />
        </button>
      </div>

      {loading ? (
        <div className="recent-repos-loading">
          <FaSpinner className="fa-spin" size={24} color="#3b82f6" />
          <span>Loading recent repositories...</span>
        </div>
      ) : repositories.length === 0 ? (
        <div className="recent-repos-empty">
          <p>No recent repositories found. Connect a repository above to get started.</p>
        </div>
      ) : (
        <div className="recent-repos-table-wrapper">
          <table className="recent-repos-table">
            <thead>
              <tr>
                <th style={{ width: "22%" }}>Repository Name</th>
                <th style={{ width: "13%" }}>Owner</th>
                <th style={{ width: "16%" }}>Tech Stack</th>
                <th style={{ width: "13%" }}>Components</th>
                <th style={{ width: "12%" }}>Default Branch</th>
                <th style={{ width: "10%" }}>Visibility</th>
                <th style={{ width: "12%" }}>Last Updated</th>
                <th style={{ width: "10%", textAlign: "center" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {repositories.map((repo, idx) => {
                const folderColor = FOLDER_COLORS[idx % FOLDER_COLORS.length];
                const isPrivate =
                  repo.visibility.toLowerCase() === "private";
                const isPublic =
                  repo.visibility.toLowerCase() === "public";

                return (
                  <tr
                    key={repo.jobId || `${repo.owner}-${repo.repositoryName}-${idx}`}
                    className="recent-repos-row"
                    onClick={() => handleRowClick(repo)}
                    title={
                      repo.repoUrl
                        ? `Click to select ${repo.repositoryName}`
                        : undefined
                    }
                  >
                    {/* Repository Name */}
                    <td>
                      <div className="recent-repo-name-cell">
                        <div
                          className="recent-repo-folder-icon"
                          style={{ color: folderColor, borderColor: `${folderColor}33`, backgroundColor: `${folderColor}10` }}
                        >
                          <FaFolder size={15} />
                        </div>
                        <span className="recent-repo-name-text">
                          {repo.repositoryName}
                        </span>
                      </div>
                    </td>

                    {/* Owner */}
                    <td>
                      <span className="recent-repo-owner-text">
                        {repo.owner}
                      </span>
                    </td>

                    {/* Tech Stack */}
                    <td>
                      <div className="recent-repo-tech-cell">
                        <span className="recent-repo-tech-icon" style={{ color: "#38bdf8" }}>
                          <SiSpring size={14} />
                        </span>
                        <span className="recent-repo-tech-text">
                          {repo.techStack}
                        </span>
                      </div>
                    </td>

                    {/* Components */}
                    <td>
                      <div className="recent-repo-components-cell">
                        <FaLayerGroup size={13} className="recent-repo-comp-icon" />
                        <span>{repo.componentsCount}</span>
                      </div>
                    </td>

                    {/* Default Branch */}
                    <td>
                      <div className="recent-repo-branch-pill">
                        <FaCodeBranch size={11} className="recent-repo-branch-icon" />
                        <span>{repo.defaultBranch || "main"}</span>
                      </div>
                    </td>

                    {/* Visibility */}
                    <td>
                      <span
                        className={`recent-repo-badge-vis ${
                          isPrivate
                            ? "is-private"
                            : isPublic
                            ? "is-public"
                            : "is-local"
                        }`}
                      >
                        {repo.visibility}
                      </span>
                    </td>

                    {/* Last Updated */}
                    <td>
                      <span className="recent-repo-updated-text">
                        {repo.lastUpdatedFormatted || "Recently"}
                      </span>
                    </td>

                    {/* Status */}
                    <td style={{ textAlign: "center" }}>
                      <span
                        className={`recent-repo-badge-status ${
                          repo.status?.toLowerCase() === "analyzed"
                            ? "is-analyzed"
                            : repo.status?.toLowerCase() === "analyzing"
                            ? "is-analyzing"
                            : repo.status?.toLowerCase() === "failed"
                            ? "is-failed"
                            : "is-connected"
                        }`}
                      >
                        {repo.status || "Connected"}
                      </span>
                    </td>

                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
