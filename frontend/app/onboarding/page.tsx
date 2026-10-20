// Session-gated content is resolved at request time, outside instant navigation.
export const instant = false;

import OnboardingView from "@/components/auth/onboarding-view";
export default function OnboardingPage() { return <OnboardingView />; }
