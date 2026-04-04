export type InterviewScope = "mine" | "all";

export type InterviewCardAction = "assign_date" | "interview";

export type InterviewBoardCard = {
  applicationId: string;
  candidateFullName: string;
  line1: string;
  line2: string;
  timeLabel: string | null;
  action: InterviewCardAction;
  highlight: boolean;
  scheduledAtIso: string | null;
};

export type InterviewBoardColumn = {
  id: string;
  title: string;
  cards: InterviewBoardCard[];
};

export type InterviewBoardFilters = {
  search: string;
  program: string | null;
  scope: InterviewScope;
};
