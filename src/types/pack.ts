export type PackStatus = "draft" | "released";

export type ResponseType = "blank" | "single-choice" | "multi-choice" | "choice";

export interface PackSection {
  number: number;
  title: string;
  questionNumbers: number[];
  audio: string;
  pages: string[];
}

export interface PackManifest {
  packId: string;
  schemaVersion: number;
  status: PackStatus;
  title: string;
  sections: PackSection[];
  assets: {
    questions: string;
    answers: string;
    overlays: string;
    transcript: string;
  };
  build?: {
    sourceCommit?: string;
    builtAt?: string;
  };
}

export interface ChoiceOption {
  id: string;
  label: string;
}

export interface Question {
  id: string;
  number: number;
  section: number;
  responseType: ResponseType;
  page: string;
  focusOrder: number;
  selectionLimit: number | null;
  options: ChoiceOption[];
}

export interface AnswerEvidence {
  kind: string;
  source: string;
  page: number | null;
  detail?: string | null;
  sourceUrl?: string | null;
  accessedAt?: string | null;
}

export interface AnswerRule {
  questionIds: string[];
  accepted: string[][];
  orderIndependent: boolean;
  provenance?: AnswerEvidence[];
  reviewStatus?: "official" | "user-confirmed";
}

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface OverlayRegion {
  questionId: string;
  optionId: string | null;
  page: string;
  interactionType: "blank" | "choice-option";
  pixel: Rect;
  normalized: Rect;
  deterministicConfidence: number;
  visionConfidence: number;
  confidence: number;
  validationEvidence: string[];
}

export interface TranscriptSegment {
  order: number;
  speaker: string | null;
  text: string;
  answerRefs: number[];
  startTime: number | null;
  endTime: number | null;
}

export interface TranscriptSection {
  section: number;
  source?: {
    pdf: string;
    pages: number[];
  };
  segments: TranscriptSegment[];
  review?: {
    method: string;
    status: string;
    notes?: string;
  };
}

export interface LoadedPack {
  baseUrl: string;
  manifest: PackManifest;
  questions: Question[];
  answers: AnswerRule[];
  overlays: OverlayRegion[];
  transcript: TranscriptSection[];
  questionsById: Map<string, Question>;
  answersByQuestionId: Map<string, AnswerRule>;
  overlaysByQuestionId: Map<string, OverlayRegion[]>;
}

export type AnswerMap = Record<string, string>;

export interface QuestionResult {
  questionId: string;
  correct: boolean;
  expected: string[];
  actual: string;
}

export interface MarkResult {
  score: number;
  total: number;
  byQuestion: Record<string, QuestionResult>;
  incorrectIds: string[];
}
