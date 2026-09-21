export interface RecentRepository {
  jobId: string;
  repositoryName: string;
  owner: string;
  techStack: string;
  componentsCount: string;
  defaultBranch: string;
  visibility: "Private" | "Public" | "Local" | string;
  lastUpdated: string;
  lastUpdatedFormatted: string;
  status: "Analyzed" | "Connected" | "In Progress" | "Queued" | string;
  repoUrl?: string;
}

export interface RecentRepositoriesResponse {
  repositories: RecentRepository[];
}
