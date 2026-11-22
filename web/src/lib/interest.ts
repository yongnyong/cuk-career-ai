import { jobById } from "./data/catalog";
import type { Profile } from "./types";

export function careerInterestOf(profile: Pick<Profile, "careerInterest" | "jobId">) {
  if (profile.careerInterest === 'startup' || profile.careerInterest === 'employment') return profile.careerInterest;
  return profile.jobId === "founder" || jobById(profile.jobId)?.base === "founder" ? "startup" : "employment";
}
